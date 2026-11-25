"""
Unit tests for the GET /analytics/overview API endpoint.
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

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from techpulse.api.dependencies import get_db
from techpulse.api.main import app
from techpulse.database.models import Base, Job


class TestAnalyticsEndpoint(unittest.TestCase):
    """Test suite for GET /analytics/overview endpoint with isolated in-memory test database."""

    @classmethod
    def setUpClass(cls):
        # Create an isolated in-memory SQLite database for testing
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.test_engine)
        cls.TestingSessionLocal = sessionmaker(
            bind=cls.test_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        # Apply FastAPI dependency override
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        # Clean up dependency override
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.test_engine)

    def setUp(self):
        # Clear jobs table before each test
        with self.TestingSessionLocal() as session:
            session.query(Job).delete()
            session.commit()

    def test_empty_database_returns_zeros(self):
        """Verify GET /analytics/overview safely returns zeros when database is empty."""
        response = self.client.get("/analytics/overview")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_jobs"], 0)
        self.assertEqual(data["remote_jobs"], 0)
        self.assertEqual(data["non_remote_jobs"], 0)
        self.assertEqual(data["jobs_with_location"], 0)
        self.assertEqual(data["unique_companies"], 0)
        self.assertEqual(data["unique_locations"], 0)

    def test_analytics_overview_known_sample(self):
        """Verify GET /analytics/overview calculates accurate statistics for a known dataset."""
        with self.TestingSessionLocal() as session:
            sample_jobs = [
                Job(
                    id=1,
                    slug="job-1",
                    title="Backend Engineer",
                    company_name="Alpha Tech",
                    description="Python role",
                    location="Berlin",
                    remote=False,
                    url="https://example.com/1",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=2,
                    slug="job-2",
                    title="Frontend Engineer",
                    company_name="Alpha Tech",
                    description="React role",
                    location="Berlin",
                    remote=False,
                    url="https://example.com/2",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=3,
                    slug="job-3",
                    title="DevOps Lead",
                    company_name="Beta Corp",
                    description="Cloud role",
                    location="Munich",
                    remote=True,
                    url="https://example.com/3",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=4,
                    slug="job-4",
                    title="Data Analyst",
                    company_name="Gamma LLC",
                    description="SQL role",
                    location=None,
                    remote=True,
                    url="https://example.com/4",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
            ]
            session.add_all(sample_jobs)
            session.commit()

        response = self.client.get("/analytics/overview")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        # 4 total jobs
        self.assertEqual(data["total_jobs"], 4)
        # 2 remote (id=3, 4)
        self.assertEqual(data["remote_jobs"], 2)
        # 2 non-remote (id=1, 2)
        self.assertEqual(data["non_remote_jobs"], 2)
        # 3 with location (Berlin, Berlin, Munich)
        self.assertEqual(data["jobs_with_location"], 3)
        # 3 distinct companies (Alpha Tech, Beta Corp, Gamma LLC)
        self.assertEqual(data["unique_companies"], 3)
        # 2 distinct locations (Berlin, Munich)
        self.assertEqual(data["unique_locations"], 2)

    def test_null_and_empty_locations(self):
        """Verify null, empty, and whitespace-only locations are excluded from location counts."""
        with self.TestingSessionLocal() as session:
            jobs = [
                Job(
                    id=1,
                    slug="job-valid-loc-1",
                    title="Role 1",
                    company_name="Company A",
                    description="Desc",
                    location="Hamburg",
                    remote=False,
                    url="https://example.com/1",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=2,
                    slug="job-valid-loc-2",
                    title="Role 2",
                    company_name="Company B",
                    description="Desc",
                    location=" Hamburg ",  # Trimmed should equal Hamburg
                    remote=False,
                    url="https://example.com/2",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=3,
                    slug="job-null-loc",
                    title="Role 3",
                    company_name="Company C",
                    description="Desc",
                    location=None,  # Null location
                    remote=True,
                    url="https://example.com/3",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=4,
                    slug="job-empty-loc",
                    title="Role 4",
                    company_name="Company D",
                    description="Desc",
                    location="",  # Empty string
                    remote=True,
                    url="https://example.com/4",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=5,
                    slug="job-whitespace-loc",
                    title="Role 5",
                    company_name="Company E",
                    description="Desc",
                    location="   ",  # Whitespace only
                    remote=True,
                    url="https://example.com/5",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
            ]
            session.add_all(jobs)
            session.commit()

        response = self.client.get("/analytics/overview")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_jobs"], 5)
        # Only jobs 1 and 2 have non-null, non-empty locations
        self.assertEqual(data["jobs_with_location"], 2)
        # Distinct non-empty locations is just "Hamburg" (1)
        self.assertEqual(data["unique_locations"], 1)

    def test_remote_and_non_remote_counts(self):
        """Verify remote and non-remote counts are mutually exclusive and sum to total jobs."""
        with self.TestingSessionLocal() as session:
            jobs = [
                Job(
                    id=i,
                    slug=f"job-{i}",
                    title=f"Role {i}",
                    company_name="Company X",
                    description="Desc",
                    remote=(i % 3 == 0),  # 3, 6, 9 are remote (3 jobs)
                    url=f"https://example.com/{i}",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                for i in range(1, 11)  # 10 jobs total
            ]
            session.add_all(jobs)
            session.commit()

        response = self.client.get("/analytics/overview")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_jobs"], 10)
        self.assertEqual(data["remote_jobs"], 3)
        self.assertEqual(data["non_remote_jobs"], 7)
        self.assertEqual(data["remote_jobs"] + data["non_remote_jobs"], data["total_jobs"])

    def test_unique_companies_distinct(self):
        """Verify multiple jobs from the same company correctly count as 1 unique company."""
        with self.TestingSessionLocal() as session:
            jobs = [
                Job(
                    id=1,
                    slug="job-1",
                    title="Engineer 1",
                    company_name="Acme Corp",
                    description="Desc",
                    url="https://example.com/1",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=2,
                    slug="job-2",
                    title="Engineer 2",
                    company_name="Acme Corp",
                    description="Desc",
                    url="https://example.com/2",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=3,
                    slug="job-3",
                    title="Engineer 3",
                    company_name="Acme Corp",
                    description="Desc",
                    url="https://example.com/3",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=4,
                    slug="job-4",
                    title="Designer 1",
                    company_name="DesignLab",
                    description="Desc",
                    url="https://example.com/4",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
            ]
            session.add_all(jobs)
            session.commit()

        response = self.client.get("/analytics/overview")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_jobs"], 4)
        self.assertEqual(data["unique_companies"], 2)

    def test_existing_endpoints_still_working(self):
        """Verify existing /health, GET /jobs, and GET /jobs/{job_id} continue functioning."""
        with self.TestingSessionLocal() as session:
            job = Job(
                id=1,
                slug="job-test-1",
                title="Test Role",
                company_name="Test Company",
                description="Test Desc",
                url="https://example.com/test",
                inserted_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(job)
            session.commit()

        # Health
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "healthy")

        # Jobs list
        res_jobs = self.client.get("/jobs")
        self.assertEqual(res_jobs.status_code, 200)
        self.assertEqual(res_jobs.json()["total"], 1)

        # Single job
        res_job = self.client.get("/jobs/1")
        self.assertEqual(res_job.status_code, 200)
        self.assertEqual(res_job.json()["id"], 1)


if __name__ == "__main__":
    unittest.main()
