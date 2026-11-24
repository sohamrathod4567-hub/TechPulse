"""
Unit tests for TechPulse Job SQLAlchemy model metadata and constraints.
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import CreateTable

from techpulse.database.models import Base, Job


class TestJobModel(unittest.TestCase):
    """Test suite for Job model structure, metadata, constraints, and indexes."""

    def test_base_inheritance(self):
        """Verify that Base is a DeclarativeBase and Job inherits from it."""
        self.assertTrue(issubclass(Base, DeclarativeBase))
        self.assertTrue(issubclass(Job, Base))

    def test_table_name(self):
        """Verify table name is 'jobs'."""
        self.assertEqual(Job.__tablename__, "jobs")
        self.assertEqual(Job.__table__.name, "jobs")

    def test_expected_columns_exist(self):
        """Verify all 13 required columns exist in the table definition."""
        expected_columns = {
            "id",
            "slug",
            "title",
            "company_name",
            "description",
            "location",
            "remote",
            "url",
            "tags",
            "job_types",
            "created_at",
            "inserted_at",
            "updated_at",
        }
        actual_columns = set(Job.__table__.columns.keys())
        self.assertEqual(expected_columns, actual_columns)

    def test_primary_key(self):
        """Verify 'id' is an integer primary key."""
        id_col = Job.__table__.columns["id"]
        self.assertTrue(id_col.primary_key)
        self.assertIsInstance(id_col.type, Integer)

    def test_column_types_and_nullability(self):
        """Verify specific PostgreSQL-compatible types and nullability rules."""
        cols = Job.__table__.columns

        # String columns
        self.assertIsInstance(cols["slug"].type, String)
        self.assertEqual(cols["slug"].type.length, 255)
        self.assertFalse(cols["slug"].nullable)

        self.assertIsInstance(cols["title"].type, String)
        self.assertEqual(cols["title"].type.length, 255)
        self.assertFalse(cols["title"].nullable)

        self.assertIsInstance(cols["company_name"].type, String)
        self.assertEqual(cols["company_name"].type.length, 255)
        self.assertFalse(cols["company_name"].nullable)

        self.assertIsInstance(cols["location"].type, String)
        self.assertEqual(cols["location"].type.length, 255)
        self.assertTrue(cols["location"].nullable)  # Remote jobs may not have a city

        # Text columns
        self.assertIsInstance(cols["description"].type, Text)
        self.assertFalse(cols["description"].nullable)

        self.assertIsInstance(cols["url"].type, Text)
        self.assertFalse(cols["url"].nullable)

        # Boolean column
        self.assertIsInstance(cols["remote"].type, Boolean)
        self.assertFalse(cols["remote"].nullable)

        # JSONB columns
        self.assertIsInstance(cols["tags"].type, JSONB)
        self.assertFalse(cols["tags"].nullable)

        self.assertIsInstance(cols["job_types"].type, JSONB)
        self.assertFalse(cols["job_types"].nullable)

        # DateTime columns (timezone-aware)
        for dt_col in ["created_at", "inserted_at", "updated_at"]:
            self.assertIsInstance(cols[dt_col].type, DateTime)
            self.assertTrue(cols[dt_col].type.timezone)

        self.assertTrue(cols["created_at"].nullable)
        self.assertFalse(cols["inserted_at"].nullable)
        self.assertFalse(cols["updated_at"].nullable)
        self.assertIsNotNone(cols["inserted_at"].server_default)
        self.assertIsNotNone(cols["updated_at"].server_default)
        self.assertIsNotNone(cols["updated_at"].onupdate)

    def test_unique_constraint_on_slug(self):
        """Verify unique constraint exists for the 'slug' field."""
        unique_constraints = [
            c for c in Job.__table__.constraints if isinstance(c, UniqueConstraint)
        ]
        slug_constraint = next(
            (c for c in unique_constraints if [col.name for col in c.columns] == ["slug"]),
            None,
        )
        self.assertIsNotNone(slug_constraint, "Unique constraint on 'slug' was not found")
        self.assertEqual(slug_constraint.name, "uq_jobs_slug")

    def test_indexes(self):
        """Verify B-tree indexes exist for title, company_name, location, and created_at."""
        index_map = {idx.name: [col.name for col in idx.columns] for idx in Job.__table__.indexes}

        self.assertIn("ix_jobs_title", index_map)
        self.assertEqual(index_map["ix_jobs_title"], ["title"])

        self.assertIn("ix_jobs_company_name", index_map)
        self.assertEqual(index_map["ix_jobs_company_name"], ["company_name"])

        self.assertIn("ix_jobs_location", index_map)
        self.assertEqual(index_map["ix_jobs_location"], ["location"])

        self.assertIn("ix_jobs_created_at", index_map)
        self.assertEqual(index_map["ix_jobs_created_at"], ["created_at"])

    def test_ddl_compilation_for_postgresql(self):
        """Verify DDL compiles cleanly against PostgreSQL dialect."""
        ddl = str(CreateTable(Job.__table__).compile(dialect=postgresql.dialect()))
        self.assertIn("CREATE TABLE jobs", ddl)
        self.assertIn("SERIAL NOT NULL", ddl)
        self.assertIn("JSONB NOT NULL", ddl)
        self.assertIn("TIMESTAMP WITH TIME ZONE", ddl)
        self.assertIn("CONSTRAINT uq_jobs_slug UNIQUE (slug)", ddl)

    def test_in_memory_instance_creation(self):
        """Verify in-memory model instantiation without touching the database."""
        job = Job(
            slug="senior-python-dev-12345",
            title="Senior Python Developer",
            company_name="Tech Innovations GmbH",
            description="Leading AI and backend pipelines.",
            location="Berlin",
            remote=True,
            url="https://example.com/jobs/senior-python-dev-12345",
            tags=["Python", "FastAPI", "SQLAlchemy"],
            job_types=["Full-time"],
            created_at=datetime.now(timezone.utc),
        )

        self.assertEqual(job.title, "Senior Python Developer")
        self.assertEqual(job.company_name, "Tech Innovations GmbH")
        self.assertTrue(job.remote)
        self.assertListEqual(job.tags, ["Python", "FastAPI", "SQLAlchemy"])
        self.assertIn("senior-python-dev-12345", repr(job))


if __name__ == "__main__":
    unittest.main()
