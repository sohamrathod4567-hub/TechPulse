"""
Unit tests for the GET /analytics/top-skills API endpoint.

Tests skill job counts, category mappings, descending sorting, alphabetical tie-breaking,
limit filtering, boundary validations, empty database behavior, and regression invariance
using an isolated in-memory SQLite database.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from techpulse.api.dependencies import get_db
from techpulse.api.main import app
from techpulse.database.models import Base, Job, JobSkill, Skill


class TestApiSkillAnalytics(unittest.TestCase):
    """Test suite for GET /analytics/top-skills endpoint."""

    @classmethod
    def setUpClass(cls):
        """Set up an isolated in-memory SQLite test database with dependency overrides."""
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(cls.test_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        """Clean up test engine and dependency overrides."""
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.test_engine)
        cls.test_engine.dispose()

    def setUp(self):
        """Clear junction and entity tables before each test."""
        with self.TestingSessionLocal() as session:
            session.query(JobSkill).delete()
            session.query(Skill).delete()
            session.query(Job).delete()
            session.commit()

    def _create_job(
        self,
        title: str = "Software Engineer",
        company_name: str = "TestCorp",
        slug: Optional[str] = None,
        remote: bool = False,
        location: str = "Berlin",
    ) -> Job:
        """Helper to create and persist a Job record."""
        slug_value = slug or f"test-job-{title.lower().replace(' ', '-')[:25]}-{id(object())}"
        job = Job(
            slug=slug_value,
            title=title,
            company_name=company_name,
            description=f"Description for {title}",
            location=location,
            remote=remote,
            url=f"https://example.com/jobs/{slug_value}",
            tags=["software"],
            job_types=["full-time"],
            created_at=datetime.now(timezone.utc),
            inserted_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        with self.TestingSessionLocal() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def _create_skill(self, name: str, category: str) -> Skill:
        """Helper to create and persist a Skill record."""
        skill = Skill(name=name, category=category)
        with self.TestingSessionLocal() as session:
            session.add(skill)
            session.commit()
            session.refresh(skill)
            return skill

    def _create_association(self, job_id: int, skill_id: int) -> JobSkill:
        """Helper to create and persist a JobSkill junction association."""
        assoc = JobSkill(job_id=job_id, skill_id=skill_id)
        with self.TestingSessionLocal() as session:
            session.add(assoc)
            session.commit()
            session.refresh(assoc)
            return assoc

    def test_empty_database_returns_zeros(self):
        """Verify GET /analytics/top-skills safely returns empty list and 0 total on empty database."""
        response = self.client.get("/analytics/top-skills")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 0)
        self.assertEqual(data["skills"], [])

    def test_correct_job_counts_and_category_returned(self):
        """Verify accurate job counts and category mapping per skill."""
        job1 = self._create_job(slug="job-1")
        job2 = self._create_job(slug="job-2")
        job3 = self._create_job(slug="job-3")

        python_skill = self._create_skill("Python", "Programming Languages")
        docker_skill = self._create_skill("Docker", "DevOps and Infrastructure")

        # Python associated with 3 jobs; Docker with 1 job
        self._create_association(job1.id, python_skill.id)
        self._create_association(job2.id, python_skill.id)
        self._create_association(job3.id, python_skill.id)
        self._create_association(job1.id, docker_skill.id)

        response = self.client.get("/analytics/top-skills")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 2)
        self.assertEqual(len(data["skills"]), 2)

        first = data["skills"][0]
        self.assertEqual(first["skill"], "Python")
        self.assertEqual(first["category"], "Programming Languages")
        self.assertEqual(first["job_count"], 3)

        second = data["skills"][1]
        self.assertEqual(second["skill"], "Docker")
        self.assertEqual(second["category"], "DevOps and Infrastructure")
        self.assertEqual(second["job_count"], 1)

    def test_descending_count_ordering(self):
        """Verify skills are ordered primarily by job_count descending."""
        jobs = [self._create_job(slug=f"job-{i}") for i in range(5)]

        skill_a = self._create_skill("SkillA", "CategoryA")  # 1 job
        skill_b = self._create_skill("SkillB", "CategoryB")  # 3 jobs
        skill_c = self._create_skill("SkillC", "CategoryC")  # 5 jobs
        skill_d = self._create_skill("SkillD", "CategoryD")  # 2 jobs

        # A: job 0
        self._create_association(jobs[0].id, skill_a.id)
        # B: jobs 0, 1, 2
        for j in jobs[:3]:
            self._create_association(j.id, skill_b.id)
        # C: jobs 0, 1, 2, 3, 4
        for j in jobs:
            self._create_association(j.id, skill_c.id)
        # D: jobs 0, 1
        for j in jobs[:2]:
            self._create_association(j.id, skill_d.id)

        response = self.client.get("/analytics/top-skills")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        names = [s["skill"] for s in data["skills"]]
        counts = [s["job_count"] for s in data["skills"]]

        self.assertEqual(names, ["SkillC", "SkillB", "SkillD", "SkillA"])
        self.assertEqual(counts, [5, 3, 2, 1])

    def test_alphabetical_tie_breaking(self):
        """Verify that skills with identical job_counts break ties by skill name ascending."""
        job1 = self._create_job(slug="job-tie-1")
        job2 = self._create_job(slug="job-tie-2")

        # 3 skills with exactly 2 job associations each
        skill_ts = self._create_skill("TypeScript", "Programming Languages")
        skill_go = self._create_skill("Go", "Programming Languages")
        skill_py = self._create_skill("Python", "Programming Languages")

        for s in [skill_ts, skill_go, skill_py]:
            self._create_association(job1.id, s.id)
            self._create_association(job2.id, s.id)

        response = self.client.get("/analytics/top-skills")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        names = [s["skill"] for s in data["skills"]]
        self.assertEqual(names, ["Go", "Python", "TypeScript"])

    def test_total_skills_independent_of_limit(self):
        """Verify total_skills reports the complete count of active skills regardless of limit."""
        jobs = [self._create_job(slug=f"job-lim-{i}") for i in range(15)]
        for i, j in enumerate(jobs):
            skill = self._create_skill(f"Skill-{i:02d}", "Category")
            self._create_association(j.id, skill.id)

        # Request limit=5 when 15 skills exist
        response = self.client.get("/analytics/top-skills?limit=5")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 15)
        self.assertEqual(len(data["skills"]), 5)

    def test_exclusion_of_skills_with_zero_associations(self):
        """Verify skills present in taxonomy/database but with zero job associations are excluded."""
        job = self._create_job(slug="job-active")
        active_skill = self._create_skill("PostgreSQL", "Databases")
        unused_skill = self._create_skill("Redis", "Databases")

        self._create_association(job.id, active_skill.id)
        # unused_skill has NO associations

        response = self.client.get("/analytics/top-skills")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 1)
        self.assertEqual(len(data["skills"]), 1)
        self.assertEqual(data["skills"][0]["skill"], "PostgreSQL")

    def test_default_limit_is_10(self):
        """Verify default limit is 10 when query parameter is omitted."""
        jobs = [self._create_job(slug=f"job-def-{i}") for i in range(15)]
        for i, j in enumerate(jobs):
            skill = self._create_skill(f"Skill-{i:02d}", "Category")
            self._create_association(j.id, skill.id)

        response = self.client.get("/analytics/top-skills")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 15)
        self.assertEqual(len(data["skills"]), 10)

    def test_limit_boundaries_and_validations(self):
        """Verify limit parameter constraints (minimum 1, maximum 50, type validation)."""
        job = self._create_job(slug="job-bnd")
        skill = self._create_skill("Python", "Programming Languages")
        self._create_association(job.id, skill.id)

        # Valid boundaries: 1 and 50
        res_1 = self.client.get("/analytics/top-skills?limit=1")
        self.assertEqual(res_1.status_code, 200)
        self.assertEqual(len(res_1.json()["skills"]), 1)

        res_50 = self.client.get("/analytics/top-skills?limit=50")
        self.assertEqual(res_50.status_code, 200)

        # Invalid limits: < 1
        res_0 = self.client.get("/analytics/top-skills?limit=0")
        self.assertEqual(res_0.status_code, 422)

        res_neg = self.client.get("/analytics/top-skills?limit=-5")
        self.assertEqual(res_neg.status_code, 422)

        # Invalid limits: > 50
        res_51 = self.client.get("/analytics/top-skills?limit=51")
        self.assertEqual(res_51.status_code, 422)

        res_100 = self.client.get("/analytics/top-skills?limit=100")
        self.assertEqual(res_100.status_code, 422)

        # Non-integer limit
        res_abc = self.client.get("/analytics/top-skills?limit=abc")
        self.assertEqual(res_abc.status_code, 422)

    def test_regression_other_analytics_endpoints(self):
        """Verify other analytics endpoints continue to operate without regression."""
        job = self._create_job(
            title="Full Stack Engineer",
            company_name="Google",
            slug="job-reg",
            remote=True,
            location="Berlin",
        )
        skill = self._create_skill("Python", "Programming Languages")
        self._create_association(job.id, skill.id)

        # 1. Overview
        res_overview = self.client.get("/analytics/overview")
        self.assertEqual(res_overview.status_code, 200)
        self.assertEqual(res_overview.json()["total_jobs"], 1)

        # 2. Top titles
        res_titles = self.client.get("/analytics/top-titles")
        self.assertEqual(res_titles.status_code, 200)
        self.assertEqual(res_titles.json()["total_titles"], 1)

        # 3. Top companies
        res_companies = self.client.get("/analytics/top-companies")
        self.assertEqual(res_companies.status_code, 200)
        self.assertEqual(res_companies.json()["total_companies"], 1)

        # 4. Locations
        res_locations = self.client.get("/analytics/locations")
        self.assertEqual(res_locations.status_code, 200)
        self.assertEqual(res_locations.json()["total_locations"], 1)

        # 5. Remote distribution
        res_remote = self.client.get("/analytics/remote-distribution")
        self.assertEqual(res_remote.status_code, 200)
        self.assertEqual(res_remote.json()["total_jobs"], 1)


if __name__ == "__main__":
    unittest.main()
