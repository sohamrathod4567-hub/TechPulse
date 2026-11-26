"""
Database Table Initialization Module for TechPulse.

This module provides functions to create and verify database tables registered
in the SQLAlchemy metadata catalog.

Usage:
    # Run from command line:
    python -m src.techpulse.database.init_db
    or
    python src/techpulse/database/init_db.py

    # Use programmatically:
    from techpulse.database.init_db import create_tables
    create_tables()
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

# ---------------------------------------------------------------------------
# Path & Environment Setup
# ---------------------------------------------------------------------------
# Resolve project paths dynamically using pathlib (no hardcoded absolute paths)
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import connection engine factory
from techpulse.database.connection import get_engine

# CRITICAL: Import all models before invoking create_all().
# SQLAlchemy's declarative Base registers models dynamically into Base.metadata
# when their Python class definitions are imported and evaluated.
from techpulse.database.models import Base, Job, JobSkill, Skill

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("techpulse.database.init_db")


def create_tables(
    engine: Optional[Engine] = None,
    checkfirst: bool = True,
    raise_on_error: bool = False,
) -> bool:
    """
    Create all database tables registered with SQLAlchemy Base.metadata.

    Uses `Base.metadata.create_all(bind=engine, checkfirst=checkfirst)`.
    If tables already exist and checkfirst=True, SQLAlchemy inspects the database
    first and does not attempt to recreate existing tables.

    Args:
        engine: Optional SQLAlchemy Engine. If None, retrieves the default engine.
        checkfirst: Whether to check if tables exist before issuing CREATE TABLE. Defaults to True.
        raise_on_error: If True, re-raises caught SQLAlchemyError exceptions. Defaults to False.

    Returns:
        bool: True if tables were created or verified successfully, False otherwise.

    Raises:
        SQLAlchemyError: If database table creation fails and raise_on_error is True.
    """
    target_engine = engine or get_engine()
    safe_url = target_engine.url.render_as_string(hide_password=True)
    registered_tables: List[str] = list(Base.metadata.tables.keys())

    logger.info("Preparing to initialize database tables on: %s", safe_url)
    logger.info("Registered models/tables in metadata (%d): %s", len(registered_tables), registered_tables)

    try:
        # Create all tables registered under Base.metadata
        Base.metadata.create_all(bind=target_engine, checkfirst=checkfirst)
        logger.info(
            "Database table creation completed successfully on %s. Tables verified: %s",
            safe_url,
            registered_tables,
        )
        return True

    except SQLAlchemyError as exc:
        logger.error(
            "Failed to create database tables on %s. Error: %s",
            safe_url,
            exc,
        )
        if raise_on_error:
            raise
        return False
    except Exception as exc:
        logger.error(
            "An unexpected error occurred while creating database tables: %s",
            exc,
        )
        if raise_on_error:
            raise
        return False


def main() -> None:
    """CLI entrypoint to run database initialization."""
    print("\n" + "=" * 70)
    print("TECHPULSE - DATABASE TABLE INITIALIZATION")
    print("=" * 70)

    try:
        engine = get_engine()
        safe_url = engine.url.render_as_string(hide_password=True)
        registered_tables = list(Base.metadata.tables.keys())

        print(f"Target Database : {safe_url}")
        print(f"Registered Models: {', '.join(registered_tables)}")
        print("-" * 70)

        success = create_tables(engine=engine, raise_on_error=True)
        if success:
            print("[SUCCESS] All database tables were created or verified successfully!")
            print(f"Active Tables   : {', '.join(registered_tables)}")
            print("=" * 70 + "\n")
        else:
            print("[FAILURE] Failed to initialize database tables.")
            print("=" * 70 + "\n")
            sys.exit(1)

    except Exception as exc:
        print(f"\n[FAILURE] Database table initialization failed: {exc}")
        print("=" * 70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
