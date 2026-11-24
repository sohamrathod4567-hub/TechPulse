"""
Database package for TechPulse.

Provides database connection management, engine instantiation, connection testing,
SQLAlchemy declarative models, and schema initialization.
"""

import sys
from pathlib import Path

# Ensure 'src' is in sys.path so submodules can import from 'techpulse'
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from techpulse.database.connection import (
    get_database_url,
    get_engine,
    load_database_config,
    test_connection,
)
from techpulse.database.models import (
    Base,
    Job,
)
from techpulse.database.init_db import (
    create_tables,
)

__all__ = [
    "Base",
    "Job",
    "create_tables",
    "get_database_url",
    "get_engine",
    "load_database_config",
    "test_connection",
]
