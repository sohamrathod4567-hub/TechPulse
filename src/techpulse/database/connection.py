"""
Database Connection and Engine Management for TechPulse.

This module provides functions to configure, construct, and test database
connections using SQLAlchemy 2.x and the Psycopg 3 driver for PostgreSQL.

Features:
- Validates all required database environment variables from .env.
- Safely constructs the connection URL using SQLAlchemy's URL.create().
- Connects using the Psycopg 3 driver ('postgresql+psycopg').
- Implements test_connection() executing 'SELECT version()' to verify connectivity.
- Enforces security: database credentials and passwords are never logged or printed.

Usage:
    # Run test from command line:
    python src/techpulse/database/connection.py

    # Use programmatically:
    from techpulse.database.connection import get_engine, test_connection
    engine = get_engine()
    version = test_connection()python src/techpulse/database/connection.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ---------------------------------------------------------------------------
# Path & Environment Setup
# ---------------------------------------------------------------------------
# Resolve project paths dynamically using pathlib (no hardcoded absolute paths)
# File location: <PROJECT_ROOT>/src/techpulse/database/connection.py
# parents[0] -> .../src/techpulse/database
# parents[1] -> .../src/techpulse
# parents[2] -> .../src
# parents[3] -> .../TechPulse (Project Root)
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
SRC_DIR = PROJECT_ROOT / "src"

# Ensure 'src' is in sys.path so the module can be run directly or imported cleanly
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Load database credentials from the project's .env file
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("techpulse.database.connection")

# Expected environment variables for PostgreSQL connection
REQUIRED_ENV_VARS = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]

# Cached singleton Engine instance
_engine: Optional[Engine] = None


def load_database_config() -> Dict[str, Any]:
    """
    Load and validate database credentials from environment variables.

    Ensures that DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, and DB_NAME are all
    defined and non-empty. Also validates that DB_PORT is a valid integer.

    Returns:
        Dict[str, Any]: Validated dictionary containing user, password, host, port, and database.

    Raises:
        ValueError: If any required variable is missing or if DB_PORT is invalid.
    """
    # Refresh/load environment variables from .env
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f"Missing required database environment variable(s): {', '.join(missing_vars)}. "
            f"Please verify that these are set in your .env file."
        )

    port_raw = os.getenv("DB_PORT", "").strip()
    try:
        port = int(port_raw)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}.")
    except ValueError as exc:
        raise ValueError(
            f"Invalid DB_PORT value '{port_raw}'. Must be an integer between 1 and 65535."
        ) from exc

    return {
        "user": os.getenv("DB_USER", "").strip(),
        "password": os.getenv("DB_PASSWORD", ""),
        "host": os.getenv("DB_HOST", "").strip(),
        "port": port,
        "database": os.getenv("DB_NAME", "").strip(),
    }


def get_database_url() -> URL:
    """
    Construct a secure database connection URL using SQLAlchemy's URL.create().

    Uses the Psycopg 3 driver via the 'postgresql+psycopg' driver name.
    SQLAlchemy's URL object safely isolates the password and automatically
    masks it (e.g. as '***') whenever rendered or logged.

    Returns:
        URL: SQLAlchemy URL object configured for PostgreSQL with Psycopg 3.
    """
    config = load_database_config()

    # Safely construct the connection URL using SQLAlchemy URL.create()
    return URL.create(
        drivername="postgresql+psycopg",
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )


def get_engine(
    echo: bool = False,
    force_new: bool = False,
    **kwargs: Any,
) -> Engine:
    """
    Create or retrieve a SQLAlchemy Engine configured with the Psycopg 3 driver.

    Args:
        echo: If True, SQLAlchemy logs executed SQL statements. Defaults to False.
        force_new: If True, creates a brand-new Engine instead of the cached one.
        **kwargs: Additional parameters passed to sqlalchemy.create_engine().

    Returns:
        Engine: Configured SQLAlchemy Engine instance.
    """
    global _engine

    if _engine is not None and not force_new:
        return _engine

    url = get_database_url()

    # Never log passwords: render_as_string(hide_password=True) guarantees masking
    safe_url_str = url.render_as_string(hide_password=True)
    logger.info("Initializing SQLAlchemy Engine for: %s", safe_url_str)

    new_engine = create_engine(
        url,
        echo=echo,
        **kwargs,
    )

    if not force_new:
        _engine = new_engine

    return new_engine


def test_connection(
    engine: Optional[Engine] = None,
    raise_on_error: bool = False,
) -> Optional[str]:
    """
    Test the PostgreSQL database connection by executing 'SELECT version()'.

    Opens a connection from the engine pool, executes the query, logs the result,
    and returns the database server version string.

    Handles connection errors gracefully without leaking credentials.

    Args:
        engine: Optional SQLAlchemy Engine. If None, uses default engine.
        raise_on_error: If True, re-raises caught exceptions. Defaults to False.

    Returns:
        Optional[str]: PostgreSQL version string on success, or None on failure.

    Raises:
        SQLAlchemyError: If connection or execution fails and raise_on_error is True.
        ValueError: If required environment variables are missing and raise_on_error is True.
    """
    try:
        target_engine = engine or get_engine()
        safe_url = target_engine.url.render_as_string(hide_password=True)
        logger.info("Testing database connection to %s...", safe_url)

        with target_engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version_str = result.scalar()

        logger.info("Connection successful! Server version: %s", version_str)
        return str(version_str) if version_str else "Unknown"

    except (SQLAlchemyError, ValueError) as exc:
        logger.error("Database connection failed. Details: %s", exc)
        if raise_on_error:
            raise
        return None
    except Exception as exc:
        logger.error("An unexpected error occurred during database connection test: %s", exc)
        if raise_on_error:
            raise
        return None


def main() -> None:
    """CLI entrypoint to test database connection."""
    print("\n" + "=" * 70)
    print("TECHPULSE - DATABASE CONNECTION TEST")
    print("=" * 70)

    try:
        config = load_database_config()
        # Display configuration safely without showing password
        print(f"Target Host     : {config['host']}")
        print(f"Target Port     : {config['port']}")
        print(f"Database Name   : {config['database']}")
        print(f"Database User   : {config['user']}")
        print("Database Pass   : [PROTECTED]")
        print("-" * 70)

        version = test_connection(raise_on_error=True)
        print("[SUCCESS] Connected successfully to PostgreSQL!")
        print(f"PostgreSQL Version: {version}")
        print("=" * 70 + "\n")
    except Exception as exc:
        print(f"\n[FAILURE] Unable to connect to PostgreSQL: {exc}")
        print("=" * 70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
