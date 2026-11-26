"""
Unit tests for TechPulse Skill Database Backfill (skill_backfill.py).

Tests taxonomy population, job skill extraction, association creation,
idempotency, transaction rollback, and job invariance using isolated
in-memory SQLite databases.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from techpulse.database.models import Base, Job, JobSkill, Skill
from techpulse.etl.skill_backfill import (
    BackfillMetrics,
    SkillBackfill,
    backfill_skills,
)
from techpulse.etl.skill_extractor import SKILL_TAXONOMY, get_taxonomy


class TestSkillBackfill(unittest.TestCase):
    """Test suite for the SkillBackfill ETL module."""

    def setUp(self) -> None:
        """Initialize an isolated in-memory SQLite database with foreign keys enabled."""
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.session = Session(bind=self.engine)

    def tearDown(self) -> None:
        """Close session and dispose of the in-memory database."""
        self.session.close()
        self.engine.dispose()

    def _create_job(
        self,
        title: str,
        description: str,
        slug: Optional[str] = None,
        company_name: str = "TestCorp",
        location: Optional[str] = "Berlin, Germany",
        remote: bool = False,
        tags: Optional[List[str]] = None,
        job_types: Optional[List[str]] = None,
    ) -> Job:
        """Helper to create and persist a Job record in the test database."""
        slug_value = slug or f"test-job-{title.lower().replace(' ', '-')[:30]}"
        job = Job(
            slug=slug_value,
            title=title,
            company_name=company_name,
            description=description,
            location=location,
            remote=remote,
            url=f"https://example.com/jobs/{slug_value}",
            tags=tags or ["software", "engineering"],
            job_types=job_types or ["full-time"],
            created_at=datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.session.add(job)
        self.session.commit()
        return job

    def test_all_taxonomy_skills_inserted(self) -> None:
        """Verify all 66 canonical taxonomy skills are inserted into an empty skills table."""
        backfill = SkillBackfill(engine=self.engine)
        metrics = backfill.run()

        self.assertEqual(metrics.total_taxonomy_skills, 66)
        self.assertEqual(metrics.skills_inserted, 66)
        self.assertEqual(metrics.skills_existing, 0)

        skills_in_db = self.session.execute(select(Skill)).scalars().all()
        self.assertEqual(len(skills_in_db), 66)

        db_names = {s.name for s in skills_in_db}
        expected_names = set(get_taxonomy().keys())
        self.assertEqual(db_names, expected_names)

    def test_correct_skill_categories_stored(self) -> None:
        """Verify each inserted skill record preserves its exact taxonomy category."""
        backfill = SkillBackfill(engine=self.engine)
        backfill.run()

        skills_in_db = self.session.execute(select(Skill)).scalars().all()
        taxonomy = get_taxonomy()

        for skill in skills_in_db:
            expected_category = taxonomy[skill.name].category
            self.assertEqual(
                skill.category,
                expected_category,
                f"Mismatch for skill '{skill.name}': got '{skill.category}', expected '{expected_category}'",
            )

    def test_existing_skills_reused(self) -> None:
        """Verify pre-existing skills are detected, reused, and not duplicated or overwritten."""
        # Pre-insert Python and PostgreSQL
        python_skill = Skill(name="Python", category="Programming Languages")
        pg_skill = Skill(name="PostgreSQL", category="Databases")
        self.session.add_all([python_skill, pg_skill])
        self.session.commit()

        initial_python_id = python_skill.id
        initial_pg_id = pg_skill.id

        backfill = SkillBackfill(engine=self.engine)
        metrics = backfill.run()

        self.assertEqual(metrics.skills_existing, 2)
        self.assertEqual(metrics.skills_inserted, 64)

        all_skills = self.session.execute(select(Skill)).scalars().all()
        self.assertEqual(len(all_skills), 66)

        refreshed_python = self.session.execute(
            select(Skill).filter_by(name="Python")
        ).scalar_one()
        refreshed_pg = self.session.execute(
            select(Skill).filter_by(name="PostgreSQL")
        ).scalar_one()

        self.assertEqual(refreshed_python.id, initial_python_id)
        self.assertEqual(refreshed_pg.id, initial_pg_id)

    def test_multiple_skills_associated_with_one_job(self) -> None:
        """Verify that multiple skills in a job posting create multiple JobSkill records."""
        job = self._create_job(
            title="Senior Full-Stack Engineer (Python / React)",
            description=(
                "We are looking for a senior developer proficient in Python, Django, "
                "React, TypeScript, Docker, and AWS."
            ),
        )

        backfill = SkillBackfill(engine=self.engine)
        metrics = backfill.run()

        self.assertEqual(metrics.total_jobs_analyzed, 1)
        self.assertEqual(metrics.jobs_with_skills, 1)
        self.assertEqual(metrics.jobs_without_skills, 0)
        self.assertEqual(metrics.associations_inserted, 6)

        refreshed_job = self.session.execute(
            select(Job).filter_by(id=job.id)
        ).scalar_one()
        self.assertEqual(len(refreshed_job.job_skills), 6)

        associated_skill_names = {s.name for s in refreshed_job.skills}
        expected_names = {"Python", "Django", "React", "TypeScript", "Docker", "AWS"}
        self.assertEqual(associated_skill_names, expected_names)

    def test_one_skill_associated_with_multiple_jobs(self) -> None:
        """Verify that a single canonical skill can be associated with multiple distinct jobs."""
        job1 = self._create_job(
            title="Backend Python Developer",
            description="Build scalable APIs using Python and FastAPI.",
            slug="job-1-backend-python",
        )
        job2 = self._create_job(
            title="Data Engineer",
            description="Develop ETL pipelines with Python and Apache Spark.",
            slug="job-2-data-engineer",
        )
        job3 = self._create_job(
            title="Machine Learning Engineer",
            description="Train computer vision models using Python and PyTorch.",
            slug="job-3-ml-engineer",
        )

        backfill = SkillBackfill(engine=self.engine)
        metrics = backfill.run()

        self.assertEqual(metrics.total_jobs_analyzed, 3)
        self.assertEqual(metrics.jobs_with_skills, 3)

        python_skill = self.session.execute(
            select(Skill).filter_by(name="Python")
        ).scalar_one()

        self.assertEqual(len(python_skill.job_skills), 3)
        associated_job_ids = {js.job_id for js in python_skill.job_skills}
        self.assertEqual(associated_job_ids, {job1.id, job2.id, job3.id})

    def test_jobs_with_no_extracted_skills_handled(self) -> None:
        """Verify jobs with no technical skills are handled without creating associations."""
        job = self._create_job(
            title="Office Manager",
            description="Manage office facilities, organize team catering, and handle mail reception.",
        )

        backfill = SkillBackfill(engine=self.engine)
        metrics = backfill.run()

        self.assertEqual(metrics.total_jobs_analyzed, 1)
        self.assertEqual(metrics.jobs_with_skills, 0)
        self.assertEqual(metrics.jobs_without_skills, 1)
        self.assertEqual(metrics.associations_inserted, 0)
        self.assertEqual(metrics.total_associations_identified, 0)

        refreshed_job = self.session.execute(
            select(Job).filter_by(id=job.id)
        ).scalar_one()
        self.assertEqual(len(refreshed_job.job_skills), 0)
        self.assertEqual(len(refreshed_job.skills), 0)

    def test_duplicate_associations_prevented(self) -> None:
        """Verify existing associations are recognized and no duplicate rows are inserted."""
        job = self._create_job(
            title="Python Developer",
            description="Must know Python and Docker.",
        )

        # Pre-seed Skill and an existing JobSkill association for Python
        python_skill = Skill(name="Python", category="Programming Languages")
        self.session.add(python_skill)
        self.session.flush()

        existing_assoc = JobSkill(job_id=job.id, skill_id=python_skill.id)
        self.session.add(existing_assoc)
        self.session.commit()

        backfill = SkillBackfill(engine=self.engine)
        metrics = backfill.run()

        # Total identified: Python and Docker (2)
        # Python already exists -> associations_existing = 1
        # Docker is new -> associations_inserted = 1
        self.assertEqual(metrics.total_associations_identified, 2)
        self.assertEqual(metrics.associations_existing, 1)
        self.assertEqual(metrics.associations_inserted, 1)

        job_skills = self.session.execute(
            select(JobSkill).filter_by(job_id=job.id)
        ).scalars().all()
        self.assertEqual(len(job_skills), 2)

    def test_idempotency_running_twice_does_not_change_counts(self) -> None:
        """Verify running the backfill twice produces identical database counts."""
        self._create_job("Python Backend", "Python, FastAPI, PostgreSQL", slug="job-1")
        self._create_job("Frontend React", "React, TypeScript, CSS", slug="job-2")
        self._create_job("DevOps", "Docker, Kubernetes, Linux", slug="job-3")

        backfill = SkillBackfill(engine=self.engine)

        # Run 1: initial backfill
        metrics1 = backfill.run()
        self.assertEqual(metrics1.skills_inserted, 66)
        self.assertEqual(metrics1.skills_existing, 0)
        self.assertGreater(metrics1.associations_inserted, 0)
        self.assertEqual(metrics1.associations_existing, 0)

        skills_count_1 = len(self.session.execute(select(Skill)).scalars().all())
        assocs_count_1 = len(self.session.execute(select(JobSkill)).scalars().all())
        self.assertEqual(skills_count_1, 66)

        # Run 2: second backfill on same database
        metrics2 = backfill.run()
        self.assertEqual(metrics2.skills_inserted, 0)
        self.assertEqual(metrics2.skills_existing, 66)
        self.assertEqual(metrics2.associations_inserted, 0)
        self.assertEqual(metrics2.associations_existing, metrics1.associations_inserted)

        skills_count_2 = len(self.session.execute(select(Skill)).scalars().all())
        assocs_count_2 = len(self.session.execute(select(JobSkill)).scalars().all())

        self.assertEqual(skills_count_2, skills_count_1)
        self.assertEqual(assocs_count_2, assocs_count_1)

    def test_failed_transaction_rolls_back_correctly(self) -> None:
        """Verify that an exception during backfill rolls back all changes atomically."""
        self._create_job("Python Dev", "Python programming required.")

        backfill = SkillBackfill(engine=self.engine)

        # Simulate a crash during the association phase after skills are populated
        with patch.object(
            backfill,
            "_associate_jobs",
            side_effect=RuntimeError("Simulated association failure"),
        ):
            with self.assertRaises(RuntimeError):
                backfill.run()

        # Database must be completely unmutated: 0 skills, 0 job_skills
        skills_in_db = self.session.execute(select(Skill)).scalars().all()
        assocs_in_db = self.session.execute(select(JobSkill)).scalars().all()

        self.assertEqual(len(skills_in_db), 0)
        self.assertEqual(len(assocs_in_db), 0)

    def test_existing_job_records_remain_unchanged(self) -> None:
        """Verify that backfill never modifies any column or timestamp on Job records."""
        job = self._create_job(
            title="Senior Python Architect",
            description="Design microservices with Python and Kubernetes.",
            company_name="TechCorp International",
            location="Munich, Germany",
            remote=True,
            tags=["architecture", "microservices"],
            job_types=["full-time", "contract"],
        )

        # Capture snapshot of all Job column values
        snapshot = {
            "id": job.id,
            "slug": job.slug,
            "title": job.title,
            "company_name": job.company_name,
            "description": job.description,
            "location": job.location,
            "remote": job.remote,
            "url": job.url,
            "tags": list(job.tags),
            "job_types": list(job.job_types),
            "created_at": job.created_at,
            "inserted_at": job.inserted_at,
            "updated_at": job.updated_at,
        }

        backfill = SkillBackfill(engine=self.engine)
        backfill.run()

        self.session.expire_all()
        refreshed_job = self.session.execute(
            select(Job).filter_by(id=job.id)
        ).scalar_one()

        for col_name, expected_val in snapshot.items():
            actual_val = getattr(refreshed_job, col_name)
            self.assertEqual(
                actual_val,
                expected_val,
                f"Job column '{col_name}' was unexpectedly modified! Got {actual_val!r}, expected {expected_val!r}",
            )

    def test_unmatched_skills_reported(self) -> None:
        """Verify unmatched skill names returned by extractor are reported in metrics."""
        job = self._create_job("Developer", "Python and MysterySkill")

        backfill = SkillBackfill(engine=self.engine)

        with patch(
            "techpulse.etl.skill_backfill.extract_skills",
            return_value=["Python", "UnknownQuantumSkill"],
        ):
            metrics = backfill.run()

            self.assertIn("UnknownQuantumSkill", metrics.unmatched_skills)
            self.assertEqual(metrics.associations_inserted, 1)  # Only Python inserted

    def test_backfill_with_provided_session(self) -> None:
        """Verify backfill can execute within an existing caller-provided session."""
        self._create_job("Python Dev", "Python and Docker")

        # Call with explicit session
        metrics = backfill_skills(session=self.session)

        self.assertEqual(metrics.skills_inserted, 66)
        self.assertEqual(metrics.associations_inserted, 2)

        skills_count = len(self.session.execute(select(Skill)).scalars().all())
        self.assertEqual(skills_count, 66)

    def test_metrics_to_dict_and_format_summary(self) -> None:
        """Verify BackfillMetrics serialization and formatting."""
        metrics = BackfillMetrics(
            total_taxonomy_skills=66,
            skills_inserted=66,
            skills_existing=0,
            total_jobs_analyzed=10,
            jobs_with_skills=8,
            jobs_without_skills=2,
            total_associations_identified=25,
            associations_inserted=25,
            associations_existing=0,
            distinct_skills_detected=15,
            unmatched_skills=["TestSkill"],
        )

        data = metrics.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["total_taxonomy_skills"], 66)
        self.assertEqual(data["unmatched_skills"], ["TestSkill"])

        summary = metrics.format_summary()
        self.assertIn("TECHPULSE - SKILL DATABASE BACKFILL METRICS", summary)
        self.assertIn("UNMATCHED SKILLS DETECTED     : TestSkill", summary)


if __name__ == "__main__":
    unittest.main()
