"""In-memory sliding window rate limiter per client IP address with safe X-Forwarded-For parsing."""
import ipaddress
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings


class InMemoryRateLimiter:
    """Thread-safe in-memory rate limiter using sliding timestamp window."""

    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.window_seconds = 60.0
        self.records: dict[str, deque[float]] = defaultdict(deque)

    def check_rate_limit(self, client_ip: str) -> None:
        """Check if request from client_ip is within the allowed limit."""
        now = time.time()
        timestamps = self.records[client_ip]

        # Evict timestamps older than the window
        while timestamps and timestamps[0] <= now - self.window_seconds:
            timestamps.popleft()

        if len(timestamps) >= self.limit:
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)

    def clear(self) -> None:
        """Clear all rate limit records (useful for testing)."""
        self.records.clear()


limiter = InMemoryRateLimiter(requests_per_minute=settings.rate_limit_per_minute)


def extract_client_ip(request: Request) -> str:
    """Safely extract and validate client IP from X-Forwarded-For or socket address."""
    fallback_ip = request.client.host if request.client and request.client.host else "127.0.0.1"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the leftmost untrusted client IP
        candidate = forwarded.split(",")[0].strip()
        try:
            # Validate that it is a genuine IPv4 or IPv6 address
            validated = ipaddress.ip_address(candidate)
            return str(validated)
        except ValueError:
            # If spoofed or malformed, fallback to direct peer IP
            return fallback_ip

    return fallback_ip


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency to enforce rate limiting by validated client IP."""
    client_ip = extract_client_ip(request)
    limiter.check_rate_limit(client_ip)
