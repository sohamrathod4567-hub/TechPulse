"""
Unit tests for the GET /analytics/skills-by-location API endpoint.

Tests location-specific skill counts, category assignments, case-insensitivity, whitespace trimming,
NULL/blank location exclusions, descending sorting, alphabetical tie-breaking, limit boundaries,
missing parameter validation, and regression invariance using an isolated in-memory SQLite database.
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


class TestApiSkillsByLocation(unittest.TestCase):
    """Test suite for GET /analytics/skills-by-location endpoint."""

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
        location: Optional[str] = "Paris",
        remote: bool = False,
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
        """Verify GET /analytics/skills-by-location returns empty skills and 0 total on empty database."""
        response = self.client.get("/analytics/skills-by-location?location=Paris")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["location"], "Paris")
        self.assertEqual(data["total_skills"], 0)
        self.assertEqual(data["skills"], [])

    def test_location_with_no_matching_jobs(self):
        """Verify requesting a location with no matching jobs returns HTTP 200 with 0 skills."""
        job = self._create_job(location="Berlin", slug="berlin-job")
        skill = self._create_skill("Python", "Programming Languages")
        self._create_association(job.id, skill.id)

        response = self.client.get("/analytics/skills-by-location?location=Paris")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["location"], "Paris")
        self.assertEqual(data["total_skills"], 0)
        self.assertEqual(data["skills"], [])

    def test_correct_skill_counts_and_categories_for_location(self):
        """Verify accurate job counts and category mapping for jobs in the queried location."""
        job_paris_1 = self._create_job(location="Paris", slug="paris-1")
        job_paris_2 = self._create_job(location="Paris", slug="paris-2")
        job_berlin = self._create_job(location="Berlin", slug="berlin-1")

        python = self._create_skill("Python", "Programming Languages")
        docker = self._create_skill("Docker", "DevOps and Infrastructure")

        # Paris: Python on both jobs (count=2), Docker on job 1 (count=1)
        self._create_association(job_paris_1.id, python.id)
        self._create_association(job_paris_2.id, python.id)
        self._create_association(job_paris_1.id, docker.id)

        # Berlin: Python on job_berlin (must NOT be counted in Paris)
        self._create_association(job_berlin.id, python.id)

        response = self.client.get("/analytics/skills-by-location?location=Paris")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["location"], "Paris")
        self.assertEqual(data["total_skills"], 2)
        self.assertEqual(len(data["skills"]), 2)

        first = data["skills"][0]
        self.assertEqual(first["skill"], "Python")
        self.assertEqual(first["category"], "Programming Languages")
        self.assertEqual(first["job_count"], 2)

        second = data["skills"][1]
        self.assertEqual(second["skill"], "Docker")
        self.assertEqual(second["category"], "DevOps and Infrastructure")
        self.assertEqual(second["job_count"], 1)

    def test_case_insensitive_location_matching(self):
        """Verify locations match case-insensitively across query parameter and database records."""
        job = self._create_job(location="pArIs", slug="paris-case")
        skill = self._create_skill("Python", "Programming Languages")
        self._create_association(job.id, skill.id)

        # Query in uppercase
        res_upper = self.client.get("/analytics/skills-by-location?location=PARIS")
        self.assertEqual(res_upper.status_code, 200)
        data_upper = res_upper.json()
        self.assertEqual(data_upper["location"], "PARIS")
        self.assertEqual(data_upper["total_skills"], 1)
        self.assertEqual(data_upper["skills"][0]["skill"], "Python")

        # Query in lowercase
        res_lower = self.client.get("/analytics/skills-by-location?location=paris")
        self.assertEqual(res_lower.status_code, 200)
        data_lower = res_lower.json()
        self.assertEqual(data_lower["location"], "paris")
        self.assertEqual(data_lower["total_skills"], 1)

    def test_trimming_whitespace_from_query_and_job_location(self):
        """Verify leading and trailing whitespace is stripped from both query parameter and stored location."""
        job = self._create_job(location="   Paris   ", slug="paris-ws")
        skill = self._create_skill("Python", "Programming Languages")
        self._create_association(job.id, skill.id)

        response = self.client.get("/analytics/skills-by-location?location=%20%20Paris%20%20")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["location"], "Paris")
        self.assertEqual(data["total_skills"], 1)
        self.assertEqual(data["skills"][0]["skill"], "Python")

    def test_handling_null_and_blank_job_locations(self):
        """Verify jobs with NULL or blank locations are never matched or cause errors."""
        j_null = self._create_job(location=None, slug="job-null")
        j_blank = self._create_job(location="", slug="job-blank")
        j_spaces = self._create_job(location="   ", slug="job-spaces")
        j_paris = self._create_job(location="Paris", slug="job-valid-paris")

        skill = self._create_skill("Python", "Programming Languages")
        self._create_association(j_null.id, skill.id)
        self._create_association(j_blank.id, skill.id)
        self._create_association(j_spaces.id, skill.id)
        self._create_association(j_paris.id, skill.id)

        response = self.client.get("/analytics/skills-by-location?location=Paris")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 1)
        self.assertEqual(data["skills"][0]["job_count"], 1)

    def test_multiple_skills_from_one_job_and_distinct_counting(self):
        """Verify multiple skills in one job are correctly reported and job counts are distinct."""
        job = self._create_job(location="Paris", slug="multi-skill-paris")

        py = self._create_skill("Python", "Programming Languages")
        fastapi = self._create_skill("FastAPI", "Backend")

        self._create_association(job.id, py.id)
        self._create_association(job.id, fastapi.id)

        response = self.client.get("/analytics/skills-by-location?location=Paris")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 2)
        skill_counts = {s["skill"]: s["job_count"] for s in data["skills"]}
        self.assertEqual(skill_counts, {"Python": 1, "FastAPI": 1})

    def test_descending_count_ordering(self):
        """Verify skills are sorted primarily by job_count descending."""
        jobs = [self._create_job(location="Paris", slug=f"paris-ord-{i}") for i in range(5)]

        s_a = self._create_skill("SkillA", "Cat")  # 1 job
        s_b = self._create_skill("SkillB", "Cat")  # 3 jobs
        s_c = self._create_skill("SkillC", "Cat")  # 5 jobs
        s_d = self._create_skill("SkillD", "Cat")  # 2 jobs

        self._create_association(jobs[0].id, s_a.id)

        for j in jobs[:3]:
            self._create_association(j.id, s_b.id)

        for j in jobs:
            self._create_association(j.id, s_c.id)

        for j in jobs[:2]:
            self._create_association(j.id, s_d.id)

        response = self.client.get("/analytics/skills-by-location?location=Paris")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        names = [s["skill"] for s in data["skills"]]
        counts = [s["job_count"] for s in data["skills"]]

        self.assertEqual(names, ["SkillC", "SkillB", "SkillD", "SkillA"])
        self.assertEqual(counts, [5, 3, 2, 1])

    def test_alphabetical_tie_breaking(self):
        """Verify skills with matching job_counts sort alphabetically by skill name ascending."""
        job1 = self._create_job(location="Paris", slug="paris-tie-1")
        job2 = self._create_job(location="Paris", slug="paris-tie-2")

        # 3 skills with 2 jobs each
        s_ts = self._create_skill("TypeScript", "Programming Languages")
        s_go = self._create_skill("Go", "Programming Languages")
        s_py = self._create_skill("Python", "Programming Languages")

        for s in [s_ts, s_go, s_py]:
            self._create_association(job1.id, s.id)
            self._create_association(job2.id, s.id)

        response = self.client.get("/analytics/skills-by-location?location=Paris")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        names = [s["skill"] for s in data["skills"]]
        self.assertEqual(names, ["Go", "Python", "TypeScript"])

    def test_total_skills_independent_of_limit(self):
        """Verify total_skills reports the complete count of active skills in location independent of limit."""
        jobs = [self._create_job(location="Paris", slug=f"paris-lim-{i}") for i in range(15)]
        for i, j in enumerate(jobs):
            skill = self._create_skill(f"Skill-{i:02d}", "Category")
            self._create_association(j.id, skill.id)

        response = self.client.get("/analytics/skills-by-location?location=Paris&limit=5")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_skills"], 15)
        self.assertEqual(len(data["skills"]), 5)

    def test_missing_and_whitespace_only_location_validation(self):
        """Verify HTTP 422 is returned when location parameter is missing or whitespace-only."""
        # Missing location parameter
        res_missing = self.client.get("/analytics/skills-by-location")
        self.assertEqual(res_missing.status_code, 422)

        # Empty string location
        res_empty = self.client.get("/analytics/skills-by-location?location=")
        self.assertEqual(res_empty.status_code, 422)

        # Whitespace-only location
        res_spaces = self.client.get("/analytics/skills-by-location?location=%20%20%20")
        self.assertEqual(res_spaces.status_code, 422)

    def test_limit_boundaries_and_invalid_values(self):
        """Verify limit query parameter constraints (minimum 1, maximum 50, type validation)."""
        job = self._create_job(location="Paris", slug="paris-bnd")
        skill = self._create_skill("Python", "Programming Languages")
        self._create_association(job.id, skill.id)

        # Valid boundaries: 1 and 50
        res_1 = self.client.get("/analytics/skills-by-location?location=Paris&limit=1")
        self.assertEqual(res_1.status_code, 200)
        self.assertEqual(len(res_1.json()["skills"]), 1)

        res_50 = self.client.get("/analytics/skills-by-location?location=Paris&limit=50")
        self.assertEqual(res_50.status_code, 200)

        # Invalid limits: < 1
        res_0 = self.client.get("/analytics/skills-by-location?location=Paris&limit=0")
        self.assertEqual(res_0.status_code, 422)

        res_neg = self.client.get("/analytics/skills-by-location?location=Paris&limit=-5")
        self.assertEqual(res_neg.status_code, 422)

        # Invalid limits: > 50
        res_51 = self.client.get("/analytics/skills-by-location?location=Paris&limit=51")
        self.assertEqual(res_51.status_code, 422)

        res_100 = self.client.get("/analytics/skills-by-location?location=Paris&limit=100")
        self.assertEqual(res_100.status_code, 422)

        # Non-integer limit
        res_abc = self.client.get("/analytics/skills-by-location?location=Paris&limit=abc")
        self.assertEqual(res_abc.status_code, 422)

    def test_regression_other_analytics_endpoints(self):
        """Verify other analytics endpoints continue to operate without regression."""
        job = self._create_job(
            title="Full Stack Engineer",
            company_name="Google",
            slug="job-reg-loc",
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

        # 6. Top skills
        res_skills = self.client.get("/analytics/top-skills")
        self.assertEqual(res_skills.status_code, 200)
        self.assertEqual(res_skills.json()["total_skills"], 1)

        # 7. Skill categories
        res_cats = self.client.get("/analytics/skill-categories")
        self.assertEqual(res_cats.status_code, 200)
        self.assertEqual(res_cats.json()["total_categories"], 1)


if __name__ == "__main__":
    unittest.main()
