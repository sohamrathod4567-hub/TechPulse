"""
Unit tests for the GET /jobs API endpoint.
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
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from techpulse.api.dependencies import get_db
from techpulse.api.main import app
from techpulse.database.models import Base, Job


class TestJobsEndpoint(unittest.TestCase):
    """Test suite for GET /jobs endpoint with isolated in-memory test database."""

    @classmethod
    def setUpClass(cls):
        # Create an isolated in-memory SQLite database for testing
        # Completely independent from the development PostgreSQL database
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

    def _seed_jobs(self, count: int = 25):
        """Helper to insert a given number of deterministic test jobs."""
        with self.TestingSessionLocal() as session:
            jobs = [
                Job(
                    id=i + 1,
                    slug=f"job-slug-{i + 1:03d}",
                    title=f"Engineer {i + 1:03d}",
                    company_name=f"Company {((i % 3) + 1)}",
                    description=f"Job description for position {i + 1}.",
                    location="Berlin" if i % 2 == 0 else None,
                    remote=bool(i % 2 == 1),
                    url=f"https://example.com/jobs/{i + 1}",
                    tags=["Python", "FastAPI"] if i % 2 == 0 else ["Data", "SQL"],
                    job_types=["Full-time"],
                    created_at=datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc),
                    inserted_at=datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc),
                )
                for i in range(count)
            ]
            session.add_all(jobs)
            session.commit()

    def test_empty_database_response(self):
        """Verify GET /jobs returns total=0 and jobs=[] when no jobs exist."""
        response = self.client.get("/jobs")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["jobs"], [])

    def test_successful_job_retrieval_and_structure(self):
        """Verify GET /jobs returns HTTP 200 with accurate total and schema structure."""
        self._seed_jobs(5)

        response = self.client.get("/jobs")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("total", data)
        self.assertIn("jobs", data)
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["jobs"]), 5)

        first_job = data["jobs"][0]
        expected_fields = {
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
        self.assertTrue(expected_fields.issubset(set(first_job.keys())))
        self.assertEqual(first_job["slug"], "job-slug-001")
        self.assertEqual(first_job["title"], "Engineer 001")

    def test_ascending_id_ordering(self):
        """Verify retrieved jobs are ordered by ascending ID."""
        self._seed_jobs(10)

        response = self.client.get("/jobs?limit=10")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        ids = [j["id"] for j in data["jobs"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(ids, list(range(1, 11)))

    def test_default_pagination(self):
        """Verify default limit is 20 and offset is 0."""
        self._seed_jobs(25)

        response = self.client.get("/jobs")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 25)
        self.assertEqual(len(data["jobs"]), 20)  # Default limit=20
        self.assertEqual(data["jobs"][0]["id"], 1)
        self.assertEqual(data["jobs"][-1]["id"], 20)

    def test_custom_limit_and_offset(self):
        """Verify pagination with custom limit and offset."""
        self._seed_jobs(25)

        # Page 2: 5 items starting from index 10 (items 11-15)
        response = self.client.get("/jobs?limit=5&offset=10")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 25)
        self.assertEqual(len(data["jobs"]), 5)
        self.assertEqual(data["jobs"][0]["id"], 11)
        self.assertEqual(data["jobs"][-1]["id"], 15)

    def test_offset_beyond_total(self):
        """Verify offset greater than total count returns total count and empty jobs list."""
        self._seed_jobs(10)

        response = self.client.get("/jobs?limit=10&offset=50")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 10)
        self.assertEqual(data["jobs"], [])

    def test_invalid_limit_below_minimum(self):
        """Verify limit < 1 returns HTTP 422 Unprocessable Entity."""
        response = self.client.get("/jobs?limit=0")
        self.assertEqual(response.status_code, 422)

    def test_invalid_limit_above_maximum(self):
        """Verify limit > 100 returns HTTP 422 Unprocessable Entity."""
        response = self.client.get("/jobs?limit=101")
        self.assertEqual(response.status_code, 422)

    def test_invalid_offset_negative(self):
        """Verify negative offset returns HTTP 422 Unprocessable Entity."""
        response = self.client.get("/jobs?offset=-1")
        self.assertEqual(response.status_code, 422)

    def test_health_check_still_working(self):
        """Verify existing /health endpoint continues functioning alongside /jobs."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy", "application": "TechPulse API"})

    def test_filter_by_title_partial_and_case_insensitive(self):
        """Verify filtering by title supports partial and case-insensitive matching."""
        self._seed_jobs(10)

        # 1. Lowercase partial match
        response = self.client.get("/jobs?title=engineer")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 10)
        self.assertEqual(len(data["jobs"]), 10)
        for job in data["jobs"]:
            self.assertIn("engineer", job["title"].lower())

        # 2. Uppercase partial match
        response = self.client.get("/jobs?title=ENGINEER")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 10)

        # 3. Specific substring match
        response = self.client.get("/jobs?title=005")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["jobs"]), 1)
        self.assertEqual(data["jobs"][0]["title"], "Engineer 005")

    def test_filter_by_company_partial_and_case_insensitive(self):
        """Verify filtering by company supports partial and case-insensitive matching."""
        self._seed_jobs(12)  # Company 1 (4), Company 2 (4), Company 3 (4)

        # Lowercase search
        response = self.client.get("/jobs?company=company 2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 4)
        for job in data["jobs"]:
            self.assertEqual(job["company_name"], "Company 2")

        # Uppercase partial substring
        response = self.client.get("/jobs?company=PANY 3")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 4)
        for job in data["jobs"]:
            self.assertEqual(job["company_name"], "Company 3")

    def test_filter_by_location_partial_and_case_insensitive(self):
        """Verify filtering by location supports partial, case-insensitive match and handles null locations."""
        self._seed_jobs(10)  # Even indices (0, 2, 4, 6, 8) have location='Berlin', odd have location=None

        # Case-insensitive partial search
        response = self.client.get("/jobs?location=ber")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["jobs"]), 5)
        for job in data["jobs"]:
            self.assertIsNotNone(job["location"])
            self.assertIn("ber", job["location"].lower())

        # Uppercase search
        response = self.client.get("/jobs?location=BERLIN")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 5)

    def test_filter_by_remote_boolean(self):
        """Verify filtering by remote flag correctly separates remote and non-remote jobs."""
        self._seed_jobs(10)  # 5 remote=True, 5 remote=False

        # Remote = true
        response_remote = self.client.get("/jobs?remote=true")
        self.assertEqual(response_remote.status_code, 200)
        data_remote = response_remote.json()
        self.assertEqual(data_remote["total"], 5)
        self.assertEqual(len(data_remote["jobs"]), 5)
        for job in data_remote["jobs"]:
            self.assertTrue(job["remote"])

        # Remote = false
        response_onsite = self.client.get("/jobs?remote=false")
        self.assertEqual(response_onsite.status_code, 200)
        data_onsite = response_onsite.json()
        self.assertEqual(data_onsite["total"], 5)
        self.assertEqual(len(data_onsite["jobs"]), 5)
        for job in data_onsite["jobs"]:
            self.assertFalse(job["remote"])

    def test_filter_multiple_simultaneous_conditions(self):
        """Verify multiple filters combine using SQL AND logic."""
        self._seed_jobs(30)

        # Filter: title containing 'engineer' AND company containing '1' AND remote=false AND location='ber'
        response = self.client.get(
            "/jobs?title=engineer&company=1&remote=false&location=ber"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # In seed: even i has remote=False, location="Berlin", company = (i % 3) + 1
        # i % 2 == 0 and (i % 3) + 1 == 1 -> i % 6 == 0 -> i in [0, 6, 12, 18, 24] (5 matches)
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["jobs"]), 5)
        for job in data["jobs"]:
            self.assertIn("engineer", job["title"].lower())
            self.assertIn("1", job["company_name"])
            self.assertFalse(job["remote"])
            self.assertEqual(job["location"], "Berlin")

    def test_filter_total_count_matches_filtered_results(self):
        """Verify total reflects the number of filtered records, independent of pagination limit."""
        self._seed_jobs(25)  # 13 non-remote, 12 remote

        # Request with remote=true and limit=4
        response = self.client.get("/jobs?remote=true&limit=4")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Total must be 12 (the filtered total), while jobs list has only 4 items
        self.assertEqual(data["total"], 12)
        self.assertEqual(len(data["jobs"]), 4)

    def test_filter_with_pagination(self):
        """Verify pagination (limit and offset) operates correctly on filtered datasets."""
        self._seed_jobs(25)  # 12 remote jobs: IDs 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24

        # Page 1: 5 items
        res_page1 = self.client.get("/jobs?remote=true&limit=5&offset=0")
        self.assertEqual(res_page1.status_code, 200)
        data_p1 = res_page1.json()
        self.assertEqual(data_p1["total"], 12)
        self.assertEqual(len(data_p1["jobs"]), 5)
        ids_p1 = [j["id"] for j in data_p1["jobs"]]
        self.assertEqual(ids_p1, [2, 4, 6, 8, 10])

        # Page 2: 5 items
        res_page2 = self.client.get("/jobs?remote=true&limit=5&offset=5")
        self.assertEqual(res_page2.status_code, 200)
        data_p2 = res_page2.json()
        self.assertEqual(data_p2["total"], 12)
        self.assertEqual(len(data_p2["jobs"]), 5)
        ids_p2 = [j["id"] for j in data_p2["jobs"]]
        self.assertEqual(ids_p2, [12, 14, 16, 18, 20])

        # Page 3: remaining 2 items
        res_page3 = self.client.get("/jobs?remote=true&limit=5&offset=10")
        self.assertEqual(res_page3.status_code, 200)
        data_p3 = res_page3.json()
        self.assertEqual(data_p3["total"], 12)
        self.assertEqual(len(data_p3["jobs"]), 2)
        ids_p3 = [j["id"] for j in data_p3["jobs"]]
        self.assertEqual(ids_p3, [22, 24])

    def test_filter_no_matching_records(self):
        """Verify filtering for non-existent criteria returns total=0 and empty jobs list."""
        self._seed_jobs(10)

        response = self.client.get("/jobs?title=NonExistentJobTitle999")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["jobs"], [])

    def test_get_job_by_id_success(self):
        """Verify GET /jobs/{job_id} retrieves an existing job with matching ID and values."""
        self._seed_jobs(5)

        response = self.client.get("/jobs/3")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], 3)
        self.assertEqual(data["slug"], "job-slug-003")
        self.assertEqual(data["title"], "Engineer 003")
        self.assertEqual(data["company_name"], "Company 3")
        self.assertEqual(data["url"], "https://example.com/jobs/3")

    def test_get_job_by_id_response_structure(self):
        """Verify GET /jobs/{job_id} returns all fields specified in the JobResponse schema."""
        self._seed_jobs(1)

        response = self.client.get("/jobs/1")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        expected_fields = {
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
        self.assertEqual(set(data.keys()), expected_fields)
        self.assertIsInstance(data["id"], int)
        self.assertIsInstance(data["slug"], str)
        self.assertIsInstance(data["title"], str)
        self.assertIsInstance(data["company_name"], str)
        self.assertIsInstance(data["description"], str)
        self.assertIsInstance(data["remote"], bool)
        self.assertIsInstance(data["url"], str)
        self.assertIsInstance(data["tags"], list)
        self.assertIsInstance(data["job_types"], list)
        self.assertIsInstance(data["inserted_at"], str)
        self.assertIsInstance(data["updated_at"], str)

    def test_get_job_by_id_with_nullable_fields(self):
        """Verify GET /jobs/{job_id} correctly returns jobs with null location and created_at fields."""
        with self.TestingSessionLocal() as session:
            job = Job(
                id=99,
                slug="job-with-nulls",
                title="Remote Role Without Location",
                company_name="Acme Corp",
                description="Description for role with nullable attributes.",
                location=None,  # Nullable
                remote=True,
                url="https://example.com/jobs/99",
                tags=["Python"],
                job_types=["Contract"],
                created_at=None,  # Nullable
                inserted_at=datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc),
            )
            session.add(job)
            session.commit()

        response = self.client.get("/jobs/99")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], 99)
        self.assertIsNone(data["location"])
        self.assertIsNone(data["created_at"])
        self.assertTrue(data["remote"])

    def test_get_job_by_id_nonexistent_returns_404(self):
        """Verify GET /jobs/{job_id} returns HTTP 404 when the job does not exist."""
        self._seed_jobs(3)

        response = self.client.get("/jobs/9999")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
        self.assertEqual(data["detail"], "Job with ID 9999 not found")

    def test_get_job_by_id_invalid_id_returns_422(self):
        """Verify GET /jobs/{job_id} returns HTTP 422 for non-positive or non-integer job IDs."""
        invalid_ids = ["0", "-1", "-100", "abc", "1.5"]
        for invalid_id in invalid_ids:
            with self.subTest(invalid_id=invalid_id):
                response = self.client.get(f"/jobs/{invalid_id}")
                self.assertEqual(
                    response.status_code,
                    422,
                    f"Expected 422 for invalid job_id='{invalid_id}', got {response.status_code}",
                )



if __name__ == "__main__":
    unittest.main()
