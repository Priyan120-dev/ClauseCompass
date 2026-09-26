# Stage 1: Build & Runtime
FROM python:3.11-slim

# Prevent Python from writing .pyc and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install security updates and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN adduser --disabled-password --gecos "" clauseuser && chown -R clauseuser:clauseuser /app
USER clauseuser

# Copy application files
COPY --chown=clauseuser:clauseuser app/ ./app/
COPY --chown=clauseuser:clauseuser static/ ./static/
COPY --chown=clauseuser:clauseuser samples/ ./samples/

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

EXPOSE 8000

# Start Uvicorn server (Cloud Run injects PORT environment variable)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
