"""`uv run aradict`: download and verify the database if needed, then start the app."""

from __future__ import annotations

import os

import uvicorn

from .data import ensure_db


def main() -> None:
    if "ARADICT_DB_PATH" not in os.environ:  # a custom path is the caller's responsibility
        ensure_db()
    # No access log: its request lines would record every looked-up word (PRD: no query text in telemetry).
    uvicorn.run("aradict.app:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")), access_log=False)


if __name__ == "__main__":
    main()
