"""
Unit tests for TechPulse Database Loader (db_loader.py).
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from techpulse.database.connection import get_engine
from techpulse.database.models import Job
from techpulse.etl.db_loader import (
    DatabaseLoader,
    parse_datetime_field,
    parse_list_field,
    validate_and_convert_row,
)


class TestDBLoaderConversions(unittest.TestCase):
    """Test suite for parsing and validation helpers."""

    def test_parse_list_field_python_literals(self):
        """Test parsing Python list literal strings with single quotes."""
        val = "['Python', 'SQLAlchemy']"
        self.assertEqual(parse_list_field(val), ["Python", "SQLAlchemy"])

    def test_parse_list_field_json(self):
        """Test parsing valid JSON array strings."""
        val = '["FastAPI", "Docker"]'
        self.assertEqual(parse_list_field(val), ["FastAPI", "Docker"])

    def test_parse_list_field_empty_and_null(self):
        """Test empty representations and nulls return empty lists."""
        self.assertEqual(parse_list_field("[]"), [])
        self.assertEqual(parse_list_field(None), [])
        self.assertEqual(parse_list_field(float("nan")), [])
        self.assertEqual(parse_list_field("   "), [])

    def test_parse_list_field_comma_separated(self):
        """Test comma separated string fallback."""
        val = "Python, PostgreSQL, Pandas"
        self.assertEqual(parse_list_field(val), ["Python", "PostgreSQL", "Pandas"])

    def test_parse_datetime_field_strings(self):
        """Test parsing formatted datetime strings into timezone-aware datetimes."""
        dt = parse_datetime_field("2026-11-23 10:30:44")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 11)
        self.assertEqual(dt.day, 23)
        self.assertEqual(dt.hour, 10)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_parse_datetime_field_unix_timestamp(self):
        """Test parsing numeric unix timestamps."""
        dt = parse_datetime_field(1795429844)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_parse_datetime_field_invalid(self):
        """Test that invalid timestamps safely return None."""
        self.assertIsNone(parse_datetime_field(None))
        self.assertIsNone(parse_datetime_field(""))
        self.assertIsNone(parse_datetime_field("not-a-timestamp"))

    def test_validate_and_convert_row_valid(self):
        """Test validation and normalization of a complete valid row."""
        raw_row = {
            "slug": "senior-engineer-101",
            "title": "Senior Engineer",
            "company_name": "Tech Corp",
            "description": "Building data platforms.",
            "location": "Berlin",
            "remote": True,
            "url": "https://example.com/jobs/101",
            "tags": "['Python', 'SQL']",
            "job_types": "['Full-time']",
            "created_at": "2026-11-23 10:30:44",
        }
        converted = validate_and_convert_row(raw_row)
        self.assertIsNotNone(converted)
        self.assertEqual(converted["slug"], "senior-engineer-101")
        self.assertEqual(converted["location"], "Berlin")
        self.assertTrue(converted["remote"])
        self.assertEqual(converted["tags"], ["Python", "SQL"])
        self.assertEqual(converted["created_at"].tzinfo, timezone.utc)

    def test_validate_and_convert_row_nullable_location(self):
        """Test that missing location is converted to None for remote roles."""
        raw_row = {
            "slug": "remote-dev-202",
            "title": "Remote Developer",
            "company_name": "Global Inc",
            "description": "100% remote job.",
            "location": None,
            "remote": "true",
            "url": "https://example.com/jobs/202",
            "tags": "[]",
            "job_types": "[]",
            "created_at": None,
        }
        converted = validate_and_convert_row(raw_row)
        self.assertIsNotNone(converted)
        self.assertIsNone(converted["location"])
        self.assertIsNone(converted["created_at"])
        self.assertTrue(converted["remote"])

    def test_validate_and_convert_row_missing_required(self):
        """Test that rows missing required fields return None."""
        invalid_row = {
            "slug": "",  # Empty slug -> should fail
            "title": "Engineer",
            "company_name": "Company",
            "description": "Desc",
            "url": "http://example.com",
        }
        self.assertIsNone(validate_and_convert_row(invalid_row))

    def test_prepare_records_deduplication(self):
        """Test in-batch deduplication of identical slugs."""
        df = pd.DataFrame([
            {"slug": "job-1", "title": "Dev 1", "company_name": "C1", "description": "D1", "url": "U1"},
            {"slug": "job-1", "title": "Dev 1 Duplicate", "company_name": "C1", "description": "D1", "url": "U1"},
            {"slug": "job-2", "title": "Dev 2", "company_name": "C2", "description": "D2", "url": "U2"},
            {"slug": "", "title": "Invalid", "company_name": "C3", "description": "D3", "url": "U3"},
        ])
        loader = DatabaseLoader(engine=MagicMock())
        valid_records, failed_count = loader.prepare_records(df)

        self.assertEqual(len(valid_records), 2)
        self.assertEqual(failed_count, 1)
        self.assertEqual([r["slug"] for r in valid_records], ["job-1", "job-2"])


class TestDBLoaderDatabaseIntegration(unittest.TestCase):
    """Integration test suite executing transactional operations against PostgreSQL."""

    @classmethod
    def setUpClass(cls):
        cls.engine = get_engine()

    def setUp(self):
        """Clean up any test records before each test."""
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM jobs WHERE slug LIKE :p"), {"p": "test-%"})

    def tearDown(self):
        """Clean up any test records after each test."""
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM jobs WHERE slug LIKE :p"), {"p": "test-%"})

    def test_insert_and_conflict_update_strategy(self):
        """Test inserting and updating records using 'update' conflict strategy inside an isolated transaction."""
        loader = DatabaseLoader(engine=self.engine)

        test_records = [
            {
                "slug": "test-integration-slug-1",
                "title": "Software Engineer",
                "company_name": "TestCorp",
                "description": "Initial description.",
                "location": "Berlin",
                "remote": False,
                "url": "https://example.com/jobs/slug-1",
                "tags": ["Python"],
                "job_types": ["Full-time"],
                "created_at": datetime.now(timezone.utc),
            }
        ]

        with self.engine.connect() as conn:
            trans = conn.begin()
            try:
                # 1. First insert
                counts1 = loader.insert_records(test_records, conflict_strategy="update", connection=conn)
                self.assertEqual(counts1["inserted"], 1)
                self.assertEqual(counts1["updated"], 0)

                # 2. Second insert with modified title -> should trigger UPDATE
                test_records[0]["title"] = "Senior Software Engineer"
                counts2 = loader.insert_records(test_records, conflict_strategy="update", connection=conn)
                self.assertEqual(counts2["inserted"], 0)
                self.assertEqual(counts2["updated"], 1)

                # Verify title was updated in the database
                current_title = conn.execute(
                    text("SELECT title FROM jobs WHERE slug = :s"),
                    {"s": "test-integration-slug-1"},
                ).scalar()
                self.assertEqual(current_title, "Senior Software Engineer")
            finally:
                trans.rollback()

    def test_insert_and_conflict_skip_strategy(self):
        """Test inserting and skipping duplicates using 'skip' conflict strategy inside an isolated transaction."""
        loader = DatabaseLoader(engine=self.engine)

        test_records = [
            {
                "slug": "test-integration-slug-2",
                "title": "Data Scientist",
                "company_name": "DataCorp",
                "description": "Initial description.",
                "location": "Paris",
                "remote": True,
                "url": "https://example.com/jobs/slug-2",
                "tags": ["Pandas", "ML"],
                "job_types": ["Full-time"],
                "created_at": datetime.now(timezone.utc),
            }
        ]

        with self.engine.connect() as conn:
            trans = conn.begin()
            try:
                # 1. First insert
                counts1 = loader.insert_records(test_records, conflict_strategy="skip", connection=conn)
                self.assertEqual(counts1["inserted"], 1)
                self.assertEqual(counts1["skipped"], 0)

                # 2. Second insert -> should trigger SKIP
                counts2 = loader.insert_records(test_records, conflict_strategy="skip", connection=conn)
                self.assertEqual(counts2["inserted"], 0)
                self.assertEqual(counts2["skipped"], 1)
            finally:
                trans.rollback()

    def test_transaction_rollback_on_failure(self):
        """Verify that transactions roll back on failure, preventing partial batches."""
        loader = DatabaseLoader(engine=self.engine)

        # Force a database error by providing an invalid column value (NOT NULL violation)
        invalid_batch = [
            {
                "slug": "test-rollback-1",
                "title": "Engineer",
                "company_name": "Corp",
                "description": "Desc",
                "url": "http://test.com",
                "remote": False,
                "tags": [],
                "job_types": [],
                "created_at": None,
            },
            {
                "slug": "test-rollback-2",
                "title": None,  # NOT NULL violation in database
                "company_name": "Corp",
                "description": "Desc",
                "url": "http://test.com",
                "remote": False,
                "tags": [],
                "job_types": [],
                "created_at": None,
            },
        ]

        # The batch should raise SQLAlchemyError and rollback completely
        with self.assertRaises(SQLAlchemyError):
            loader.insert_records(invalid_batch, conflict_strategy="update")

        # Verify test-rollback-1 was NOT saved due to transaction rollback
        with self.engine.connect() as conn:
            exists = conn.execute(
                text("SELECT count(*) FROM jobs WHERE slug = :s"),
                {"s": "test-rollback-1"},
            ).scalar()
            self.assertEqual(exists, 0)


if __name__ == "__main__":
    unittest.main()
