"""
Unit tests for TechPulse API dependencies (dependencies.py).
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

from sqlalchemy import text
from sqlalchemy.orm import Session
from techpulse.api.dependencies import SessionLocal, get_db
from techpulse.database.connection import get_engine


class TestApiDependencies(unittest.TestCase):
    """Test suite for FastAPI database session dependencies."""

    def test_session_uses_existing_engine(self):
        """Verify that SessionLocal reuses the existing singleton engine."""
        expected_engine = get_engine()
        session = SessionLocal()
        try:
            self.assertIs(session.bind, expected_engine)
        finally:
            session.close()

    def test_get_db_yields_session_instance(self):
        """Verify that get_db generator yields a valid SQLAlchemy Session instance."""
        db_gen = get_db()
        session = next(db_gen)
        self.assertIsInstance(session, Session)
        # Advance generator to execute finally block
        try:
            next(db_gen)
        except StopIteration:
            pass

    def test_get_db_closes_session_in_finally(self):
        """Verify that get_db guarantees session.close() is called when generator terminates."""
        mock_session = MagicMock()

        with patch("techpulse.api.dependencies.SessionLocal", return_value=mock_session):
            db_gen = get_db()
            yielded_session = next(db_gen)
            self.assertIs(yielded_session, mock_session)
            mock_session.close.assert_not_called()

            # End generator
            try:
                next(db_gen)
            except StopIteration:
                pass

            mock_session.close.assert_called_once()

    def test_get_db_closes_session_on_exception(self):
        """Verify session is closed even if an exception occurs during request execution."""
        mock_session = MagicMock()

        with patch("techpulse.api.dependencies.SessionLocal", return_value=mock_session):
            db_gen = get_db()
            next(db_gen)
            # Throw exception into generator simulating endpoint failure
            with self.assertRaises(RuntimeError):
                db_gen.throw(RuntimeError("Simulated endpoint failure"))

            mock_session.close.assert_called_once()

    def test_live_session_query(self):
        """Verify that a session provided by get_db can query the PostgreSQL database."""
        db_gen = get_db()
        session = next(db_gen)
        try:
            result = session.execute(text("SELECT 1;")).scalar()
            self.assertEqual(result, 1)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass


if __name__ == "__main__":
    unittest.main()
