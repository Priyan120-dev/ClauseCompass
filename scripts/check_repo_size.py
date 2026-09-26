#!/usr/bin/env python3
"""Cross-platform script to verify that repository size is strictly under 10 MB."""
import os
import sys
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "ENV",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".coverage",
    "htmlcov",
}

def get_tracked_or_repo_size(root: Path) -> int:
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".venv")]
        for f in filenames:
            file_path = Path(dirpath) / f
            try:
                total_size += file_path.stat().st_size
            except OSError:
                pass
    return total_size

def main() -> int:
    total_bytes = get_tracked_or_repo_size(REPO_ROOT)
    total_kb = total_bytes / 1024
    total_mb = total_bytes / (1024 * 1024)

    print(f"Total workspace size (excluding venv/git): {total_mb:.2f} MB ({total_kb:.1f} KB, {total_bytes} bytes)")
    if total_bytes > MAX_BYTES:
        print(f"ERROR: Repository size {total_mb:.2f} MB exceeds 10 MB limit!", file=sys.stderr)
        return 1
    print("SUCCESS: Repository size is strictly under 10 MB.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
