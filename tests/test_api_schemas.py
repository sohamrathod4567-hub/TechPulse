"""
Unit tests for TechPulse API Pydantic schemas (schemas.py).
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

from pydantic import ValidationError
from techpulse.api.schemas import (
    AnalyticsOverviewResponse,
    JobListResponse,
    JobResponse,
)
from techpulse.database.models import Job


class TestApiSchemas(unittest.TestCase):
    """Test suite for JobResponse Pydantic schema."""

    def setUp(self):
        self.valid_data = {
            "id": 1,
            "slug": "senior-python-dev-123",
            "title": "Senior Python Developer",
            "company_name": "Tech Corp",
            "description": "Designing high-scale distributed backend systems.",
            "location": "Berlin",
            "remote": True,
            "url": "https://example.com/jobs/123",
            "tags": ["Python", "FastAPI", "PostgreSQL"],
            "job_types": ["Full-time"],
            "created_at": datetime(2026, 11, 23, 10, 30, 44, tzinfo=timezone.utc),
            "inserted_at": datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc),
        }

    def test_job_response_from_dict(self):
        """Verify JobResponse initializes and validates from dictionary data."""
        job_schema = JobResponse(**self.valid_data)
        self.assertEqual(job_schema.id, 1)
        self.assertEqual(job_schema.slug, "senior-python-dev-123")
        self.assertEqual(job_schema.title, "Senior Python Developer")
        self.assertTrue(job_schema.remote)
        self.assertEqual(job_schema.tags, ["Python", "FastAPI", "PostgreSQL"])

    def test_job_response_from_orm_object(self):
        """Verify JobResponse serializes from a SQLAlchemy Job ORM object via model_validate."""
        orm_job = Job(
            id=42,
            slug="data-engineer-456",
            title="Lead Data Engineer",
            company_name="DataPulse AG",
            description="Leading ETL pipelines with SQLAlchemy and PostgreSQL.",
            location="Paris",
            remote=False,
            url="https://example.com/jobs/456",
            tags=["SQL", "Pandas", "PostgreSQL"],
            job_types=["Permanent"],
            created_at=datetime(2026, 11, 20, 8, 15, 0, tzinfo=timezone.utc),
            inserted_at=datetime(2026, 11, 24, 10, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 24, 10, 0, 0, tzinfo=timezone.utc),
        )

        job_schema = JobResponse.model_validate(orm_job)
        self.assertEqual(job_schema.id, 42)
        self.assertEqual(job_schema.slug, "data-engineer-456")
        self.assertEqual(job_schema.company_name, "DataPulse AG")
        self.assertFalse(job_schema.remote)
        self.assertEqual(job_schema.tags, ["SQL", "Pandas", "PostgreSQL"])
        self.assertEqual(job_schema.job_types, ["Permanent"])

    def test_job_response_nullable_fields(self):
        """Verify JobResponse permits None for location and created_at."""
        data_with_nulls = self.valid_data.copy()
        data_with_nulls["location"] = None
        data_with_nulls["created_at"] = None

        job_schema = JobResponse(**data_with_nulls)
        self.assertIsNone(job_schema.location)
        self.assertIsNone(job_schema.created_at)

    def test_job_response_missing_required_fields_raises(self):
        """Verify validation error when mandatory fields are missing."""
        invalid_data = self.valid_data.copy()
        del invalid_data["slug"]  # Remove required field

        with self.assertRaises(ValidationError):
            JobResponse(**invalid_data)

    def test_job_response_json_serialization(self):
        """Verify model_dump_json produces valid JSON."""
        job_schema = JobResponse(**self.valid_data)
        json_output = job_schema.model_dump_json()
        self.assertIn('"slug":"senior-python-dev-123"', json_output)
        self.assertIn('"remote":true', json_output)

    def test_job_list_response(self):
        """Verify JobListResponse schema wraps total count and list of jobs."""
        job_schema = JobResponse(**self.valid_data)
        list_response = JobListResponse(total=1, jobs=[job_schema])
        self.assertEqual(list_response.total, 1)
        self.assertEqual(len(list_response.jobs), 1)
        self.assertEqual(list_response.jobs[0].slug, "senior-python-dev-123")
        dumped = list_response.model_dump()
        self.assertIn("total", dumped)
        self.assertIn("jobs", dumped)

    def test_analytics_overview_response(self):
        """Verify AnalyticsOverviewResponse schema validation and serialization."""
        data = {
            "total_jobs": 300,
            "remote_jobs": 50,
            "non_remote_jobs": 250,
            "jobs_with_location": 260,
            "unique_companies": 180,
            "unique_locations": 110,
        }
        schema = AnalyticsOverviewResponse(**data)
        self.assertEqual(schema.total_jobs, 300)
        self.assertEqual(schema.remote_jobs, 50)
        self.assertEqual(schema.non_remote_jobs, 250)
        self.assertEqual(schema.jobs_with_location, 260)
        self.assertEqual(schema.unique_companies, 180)
        self.assertEqual(schema.unique_locations, 110)

        # Negative values should fail validation
        with self.assertRaises(ValidationError):
            AnalyticsOverviewResponse(
                total_jobs=-1,
                remote_jobs=0,
                non_remote_jobs=0,
                jobs_with_location=0,
                unique_companies=0,
                unique_locations=0,
            )



if __name__ == "__main__":
    unittest.main()
