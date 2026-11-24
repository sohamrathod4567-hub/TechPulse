"""
FastAPI Dependencies for TechPulse.

Provides reusable dependencies for FastAPI request handling, including
SQLAlchemy database session lifecycle management.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

# Ensure 'src' is in sys.path
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy.orm import Session, sessionmaker
from techpulse.database.connection import get_engine

# Factory for creating database sessions bound to the existing singleton engine
# Reuses the engine without creating a duplicate engine instance
SessionLocal = sessionmaker(
    bind=get_engine(),
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a dedicated SQLAlchemy database session per request.

    Yields:
        Session: An active SQLAlchemy Session object.

    Ensures:
        The session is closed cleanly in a finally block after the request is finished,
        releasing the underlying connection back to the connection pool.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
