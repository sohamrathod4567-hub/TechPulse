"""
Unit tests for TechPulse database table initialization (init_db.py).
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from techpulse.database.init_db import create_tables
from techpulse.database.models import Base, Job, JobSkill, Skill


class TestInitDB(unittest.TestCase):
    """Test suite for database table creation and error handling."""

    def test_create_tables_invokes_metadata_create_all(self):
        """Verify create_tables invokes Base.metadata.create_all with engine and checkfirst."""
        mock_engine = MagicMock()
        mock_engine.url.render_as_string.return_value = "postgresql+psycopg://user:***@localhost/db"

        with patch.object(Base.metadata, "create_all") as mock_create_all:
            result = create_tables(engine=mock_engine, checkfirst=True)

            self.assertTrue(result)
            mock_create_all.assert_called_once_with(bind=mock_engine, checkfirst=True)

    def test_existing_tables_not_recreated(self):
        """Verify idempotency: existing tables are not recreated unnecessarily."""
        engine = create_engine("sqlite:///:memory:")

        # 1. First execution creates the table
        success_first = create_tables(engine=engine, checkfirst=True)
        self.assertTrue(success_first)

        inspector = inspect(engine)
        initial_tables = inspector.get_table_names()
        self.assertIn("jobs", initial_tables)

        # 2. Second execution checks first and does not fail or recreate
        success_second = create_tables(engine=engine, checkfirst=True)
        self.assertTrue(success_second)

        inspector_second = inspect(engine)
        self.assertEqual(inspector_second.get_table_names(), initial_tables)

    def test_database_error_handling_graceful(self):
        """Verify database errors are caught gracefully and return False when raise_on_error=False."""
        mock_engine = MagicMock()
        mock_engine.url.render_as_string.return_value = "postgresql+psycopg://user:***@localhost/db"

        with patch.object(
            Base.metadata,
            "create_all",
            side_effect=OperationalError("mock query", {}, Exception("Connection refused")),
        ):
            # When raise_on_error is False (default), returns False without raising
            result = create_tables(engine=mock_engine, raise_on_error=False)
            self.assertFalse(result)

    def test_database_error_handling_raises(self):
        """Verify database errors are re-raised when raise_on_error=True."""
        mock_engine = MagicMock()
        mock_engine.url.render_as_string.return_value = "postgresql+psycopg://user:***@localhost/db"

        with patch.object(
            Base.metadata,
            "create_all",
            side_effect=SQLAlchemyError("Simulated database failure"),
        ):
            with self.assertRaises(SQLAlchemyError):
                create_tables(engine=mock_engine, raise_on_error=True)

    def test_models_registered_in_metadata(self):
        """Verify that Job, Skill, and JobSkill models are registered in Base.metadata before create_all."""
        self.assertIn("jobs", Base.metadata.tables)
        self.assertIn("skills", Base.metadata.tables)
        self.assertIn("job_skills", Base.metadata.tables)
        self.assertEqual(Job.__tablename__, "jobs")
        self.assertEqual(Skill.__tablename__, "skills")
        self.assertEqual(JobSkill.__tablename__, "job_skills")
        self.assertIs(Job.metadata, Base.metadata)
        self.assertIs(Skill.metadata, Base.metadata)
        self.assertIs(JobSkill.metadata, Base.metadata)


if __name__ == "__main__":
    unittest.main()
