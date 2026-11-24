"""
Unit tests for TechPulse Database Connection.
"""

import sys
import unittest
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techpulse.database.connection import (
    get_database_url,
    get_engine,
    load_database_config,
    test_connection,
)


class TestDatabaseConnection(unittest.TestCase):
    def test_load_database_config_keys(self):
        config = load_database_config()
        self.assertIn("user", config)
        self.assertIn("password", config)
        self.assertIn("host", config)
        self.assertIn("port", config)
        self.assertIn("database", config)
        self.assertIsInstance(config["port"], int)

    def test_database_url_driver_and_masking(self):
        url = get_database_url()
        # Ensure Psycopg 3 driver is specified
        self.assertEqual(url.drivername, "postgresql+psycopg")
        # Ensure password masking in render_as_string
        rendered = url.render_as_string(hide_password=True)
        self.assertNotIn(url.password, rendered if url.password else "")
        self.assertIn("***", rendered)

    def test_database_connection_execution(self):
        # Execute test_connection against running PostgreSQL
        version = test_connection(raise_on_error=True)
        self.assertIsNotNone(version)
        self.assertIn("PostgreSQL", version)


if __name__ == "__main__":
    unittest.main()
