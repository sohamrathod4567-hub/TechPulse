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

    def test_top_titles_empty_database(self):
        """Verify GET /analytics/top-titles returns total_titles=0 and empty list on empty database."""
        response = self.client.get("/analytics/top-titles")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_titles"], 0)
        self.assertEqual(data["titles"], [])

    def test_top_titles_counts_and_ordering(self):
        """Verify top titles calculates correct job counts and orders by count descending."""
        with self.TestingSessionLocal() as session:
            # 4x "Python Developer", 3x "DevOps Engineer", 2x "Data Scientist", 1x "QA Engineer"
            titles_data = (
                ["Python Developer"] * 4
                + ["DevOps Engineer"] * 3
                + ["Data Scientist"] * 2
                + ["QA Engineer"] * 1
            )
            jobs = [
                Job(
                    id=i + 1,
                    slug=f"job-top-{i + 1}",
                    title=title,
                    company_name="Tech Corp",
                    description="Job desc",
                    url=f"https://example.com/{i + 1}",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                for i, title in enumerate(titles_data)
            ]
            session.add_all(jobs)
            session.commit()

        response = self.client.get("/analytics/top-titles")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_titles"], 4)
        self.assertEqual(len(data["titles"]), 4)

        expected = [
            ("Python Developer", 4),
            ("DevOps Engineer", 3),
            ("Data Scientist", 2),
            ("QA Engineer", 1),
        ]
        for idx, (exp_title, exp_count) in enumerate(expected):
            self.assertEqual(data["titles"][idx]["title"], exp_title)
            self.assertEqual(data["titles"][idx]["job_count"], exp_count)

    def test_top_titles_alphabetical_tie_breaker(self):
        """Verify titles with identical job counts are ordered alphabetically ascending."""
        with self.TestingSessionLocal() as session:
            # Identical counts (2 each): "Zebra Dev", "Alpha Dev", "Beta Dev"
            titles_data = ["Zebra Dev", "Zebra Dev", "Alpha Dev", "Alpha Dev", "Beta Dev", "Beta Dev"]
            jobs = [
                Job(
                    id=i + 1,
                    slug=f"job-tie-{i + 1}",
                    title=title,
                    company_name="Tech Corp",
                    description="Job desc",
                    url=f"https://example.com/{i + 1}",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                for i, title in enumerate(titles_data)
            ]
            session.add_all(jobs)
            session.commit()

        response = self.client.get("/analytics/top-titles")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_titles"], 3)
        self.assertEqual(len(data["titles"]), 3)

        # Count is 2 for all, so alphabetical order: Alpha Dev, Beta Dev, Zebra Dev
        self.assertEqual(data["titles"][0]["title"], "Alpha Dev")
        self.assertEqual(data["titles"][0]["job_count"], 2)
        self.assertEqual(data["titles"][1]["title"], "Beta Dev")
        self.assertEqual(data["titles"][1]["job_count"], 2)
        self.assertEqual(data["titles"][2]["title"], "Zebra Dev")
        self.assertEqual(data["titles"][2]["job_count"], 2)

    def test_top_titles_limit_and_total_titles_independence(self):
        """Verify total_titles reflects all distinct titles regardless of the requested limit."""
        with self.TestingSessionLocal() as session:
            jobs = [
                Job(
                    id=i + 1,
                    slug=f"job-dist-{i + 1}",
                    title=f"Role {i + 1:02d}",
                    company_name="Tech Corp",
                    description="Job desc",
                    url=f"https://example.com/{i + 1}",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                for i in range(15)  # 15 distinct titles
            ]
            session.add_all(jobs)
            session.commit()

        # Request with limit=5
        response = self.client.get("/analytics/top-titles?limit=5")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        # total_titles must be 15 even though titles only has 5 items
        self.assertEqual(data["total_titles"], 15)
        self.assertEqual(len(data["titles"]), 5)

    def test_top_titles_default_limit(self):
        """Verify default limit is 10 when not specified."""
        with self.TestingSessionLocal() as session:
            jobs = [
                Job(
                    id=i + 1,
                    slug=f"job-def-{i + 1}",
                    title=f"Role {i + 1:02d}",
                    company_name="Tech Corp",
                    description="Job desc",
                    url=f"https://example.com/{i + 1}",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                for i in range(15)
            ]
            session.add_all(jobs)
            session.commit()

        response = self.client.get("/analytics/top-titles")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_titles"], 15)
        self.assertEqual(len(data["titles"]), 10)  # Default limit=10

    def test_top_titles_limit_validation(self):
        """Verify limit must be between 1 and 50, returning 422 for invalid values."""
        invalid_limits = [0, -1, 51, 100, "abc"]
        for lim in invalid_limits:
            with self.subTest(limit=lim):
                response = self.client.get(f"/analytics/top-titles?limit={lim}")
                self.assertEqual(
                    response.status_code,
                    422,
                    f"Expected 422 for limit={lim}, got {response.status_code}",
                )

    def test_top_titles_excludes_null_or_empty_titles(self):
        """Verify empty and whitespace-only titles are excluded from top titles and total count."""
        with self.TestingSessionLocal() as session:
            jobs = [
                Job(
                    id=1,
                    slug="job-valid-1",
                    title="Valid Title",
                    company_name="Tech Corp",
                    description="Job desc",
                    url="https://example.com/1",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=2,
                    slug="job-empty-1",
                    title="",
                    company_name="Tech Corp",
                    description="Job desc",
                    url="https://example.com/2",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
                Job(
                    id=3,
                    slug="job-whitespace-1",
                    title="   ",
                    company_name="Tech Corp",
                    description="Job desc",
                    url="https://example.com/3",
                    inserted_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ),
            ]
            session.add_all(jobs)
            session.commit()

        response = self.client.get("/analytics/top-titles")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_titles"], 1)
        self.assertEqual(len(data["titles"]), 1)
        self.assertEqual(data["titles"][0]["title"], "Valid Title")
        self.assertEqual(data["titles"][0]["job_count"], 1)



if __name__ == "__main__":
    unittest.main()
