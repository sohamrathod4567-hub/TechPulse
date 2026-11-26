"""
Unit tests for TechPulse Skill and JobSkill SQLAlchemy models and relationships.

Tests metadata, column specifications, constraints, composite primary keys,
foreign keys with cascade deletion, and bidirectional ORM relationships
using isolated in-memory SQLite instances.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
    select,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.schema import CreateTable

from techpulse.database.models import Base, Job, JobSkill, Skill


class TestSkillModelMetadata(unittest.TestCase):
    """Test suite for Skill model structure, columns, constraints, and indexes."""

    def test_base_inheritance(self) -> None:
        """Verify Skill inherits from DeclarativeBase."""
        self.assertTrue(issubclass(Skill, Base))

    def test_table_name(self) -> None:
        """Verify table name is 'skills'."""
        self.assertEqual(Skill.__tablename__, "skills")
        self.assertEqual(Skill.__table__.name, "skills")

    def test_expected_columns_exist(self) -> None:
        """Verify all required columns exist in the 'skills' table definition."""
        expected_columns = {"id", "name", "category"}
        actual_columns = set(Skill.__table__.columns.keys())
        self.assertEqual(expected_columns, actual_columns)

    def test_primary_key(self) -> None:
        """Verify 'id' is an integer primary key with autoincrement."""
        id_col = Skill.__table__.columns["id"]
        self.assertTrue(id_col.primary_key)
        self.assertIsInstance(id_col.type, Integer)

    def test_column_types_and_nullability(self) -> None:
        """Verify data types and not-null constraints for Skill columns."""
        cols = Skill.__table__.columns

        self.assertIsInstance(cols["name"].type, String)
        self.assertEqual(cols["name"].type.length, 100)
        self.assertFalse(cols["name"].nullable)

        self.assertIsInstance(cols["category"].type, String)
        self.assertEqual(cols["category"].type.length, 100)
        self.assertFalse(cols["category"].nullable)

    def test_unique_constraint_on_name(self) -> None:
        """Verify unique constraint on 'name' prevents duplicate canonical skills."""
        unique_constraints = [
            c for c in Skill.__table__.constraints if isinstance(c, UniqueConstraint)
        ]
        name_constraint = next(
            (c for c in unique_constraints if [col.name for col in c.columns] == ["name"]),
            None,
        )
        self.assertIsNotNone(name_constraint, "Unique constraint on 'name' not found")
        self.assertEqual(name_constraint.name, "uq_skills_name")

    def test_category_index(self) -> None:
        """Verify index exists for 'category' to optimize categorical filtering."""
        index_map = {idx.name: [col.name for col in idx.columns] for idx in Skill.__table__.indexes}
        self.assertIn("ix_skills_category", index_map)
        self.assertEqual(index_map["ix_skills_category"], ["category"])

    def test_repr(self) -> None:
        """Verify string representation of Skill instance."""
        skill = Skill(id=1, name="Python", category="Programming Languages")
        self.assertIn("Python", repr(skill))
        self.assertIn("Programming Languages", repr(skill))

    def test_ddl_compilation_for_postgresql(self) -> None:
        """Verify Skill DDL compiles cleanly against PostgreSQL dialect."""
        ddl = str(CreateTable(Skill.__table__).compile(dialect=postgresql.dialect()))
        self.assertIn("CREATE TABLE skills", ddl)
        self.assertIn("SERIAL NOT NULL", ddl)
        self.assertIn("VARCHAR(100) NOT NULL", ddl)
        self.assertIn("CONSTRAINT uq_skills_name UNIQUE (name)", ddl)


class TestJobSkillModelMetadata(unittest.TestCase):
    """Test suite for JobSkill association model structure, keys, and foreign keys."""

    def test_base_inheritance(self) -> None:
        """Verify JobSkill inherits from DeclarativeBase."""
        self.assertTrue(issubclass(JobSkill, Base))

    def test_table_name(self) -> None:
        """Verify table name is 'job_skills'."""
        self.assertEqual(JobSkill.__tablename__, "job_skills")
        self.assertEqual(JobSkill.__table__.name, "job_skills")

    def test_expected_columns_exist(self) -> None:
        """Verify required columns exist in the 'job_skills' table."""
        expected_columns = {"job_id", "skill_id"}
        actual_columns = set(JobSkill.__table__.columns.keys())
        self.assertEqual(expected_columns, actual_columns)

    def test_composite_primary_key(self) -> None:
        """Verify (job_id, skill_id) forms a composite primary key."""
        pk_cols = [c.name for c in JobSkill.__table__.primary_key.columns]
        self.assertEqual(sorted(pk_cols), ["job_id", "skill_id"])
        self.assertTrue(JobSkill.__table__.columns["job_id"].primary_key)
        self.assertTrue(JobSkill.__table__.columns["skill_id"].primary_key)

    def test_foreign_keys_and_ondelete_cascade(self) -> None:
        """Verify foreign keys target jobs.id and skills.id with ON DELETE CASCADE."""
        cols = JobSkill.__table__.columns

        # job_id foreign key
        job_fks = list(cols["job_id"].foreign_keys)
        self.assertEqual(len(job_fks), 1)
        self.assertEqual(job_fks[0].target_fullname, "jobs.id")
        self.assertEqual(job_fks[0].ondelete, "CASCADE")
        self.assertFalse(cols["job_id"].nullable)

        # skill_id foreign key
        skill_fks = list(cols["skill_id"].foreign_keys)
        self.assertEqual(len(skill_fks), 1)
        self.assertEqual(skill_fks[0].target_fullname, "skills.id")
        self.assertEqual(skill_fks[0].ondelete, "CASCADE")
        self.assertFalse(cols["skill_id"].nullable)

    def test_skill_id_index(self) -> None:
        """Verify B-tree index exists on skill_id for skill-based analytics queries."""
        index_map = {idx.name: [col.name for col in idx.columns] for idx in JobSkill.__table__.indexes}
        self.assertIn("ix_job_skills_skill_id", index_map)
        self.assertEqual(index_map["ix_job_skills_skill_id"], ["skill_id"])

    def test_repr(self) -> None:
        """Verify string representation of JobSkill instance."""
        js = JobSkill(job_id=42, skill_id=7)
        self.assertIn("42", repr(js))
        self.assertIn("7", repr(js))

    def test_ddl_compilation_for_postgresql(self) -> None:
        """Verify JobSkill DDL compiles cleanly against PostgreSQL dialect."""
        ddl = str(CreateTable(JobSkill.__table__).compile(dialect=postgresql.dialect()))
        self.assertIn("CREATE TABLE job_skills", ddl)
        self.assertIn("FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE", ddl)
        self.assertIn("FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE CASCADE", ddl)
        self.assertIn("PRIMARY KEY (job_id, skill_id)", ddl)


class TestJobSkillRelationshipsAndConstraints(unittest.TestCase):
    """Integration test suite executing ORM operations and constraints in isolated SQLite."""

    def setUp(self) -> None:
        """Create an isolated in-memory SQLite database with foreign keys enabled."""
        self.engine = create_engine("sqlite:///:memory:")

        # Enable SQLite foreign key enforcement
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        """Dispose of the in-memory engine and drop all tables."""
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_unique_canonical_skill_name_enforced(self) -> None:
        """Verify that inserting two skills with the same name raises an IntegrityError."""
        with Session(self.engine) as session:
            s1 = Skill(name="Python", category="Programming Languages")
            session.add(s1)
            session.commit()

            s2 = Skill(name="Python", category="Data Science and AI")
            session.add(s2)
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_duplicate_job_skill_association_rejected(self) -> None:
        """Verify that composite primary key rejects duplicate (job_id, skill_id) associations."""
        with Session(self.engine) as session:
            job = Job(
                slug="python-backend-dev",
                title="Python Backend Developer",
                company_name="Acme Corp",
                description="FastAPI microservices",
                url="https://example.com/jobs/1",
                remote=True,
            )
            skill = Skill(name="FastAPI", category="Backend")
            session.add_all([job, skill])
            session.commit()

            job_id = job.id
            skill_id = skill.id

            # First association succeeds
            js1 = JobSkill(job_id=job_id, skill_id=skill_id)
            session.add(js1)
            session.commit()

        # In a separate session, attempting to insert duplicate (job_id, skill_id) triggers IntegrityError
        with Session(self.engine) as session2:
            js2 = JobSkill(job_id=job_id, skill_id=skill_id)
            session2.add(js2)
            with self.assertRaises(IntegrityError):
                session2.commit()

    def test_create_associations_through_job_skills(self) -> None:
        """Verify creating associations authoritatively through Job.job_skills."""
        with Session(self.engine) as session:
            job = Job(
                slug="backend-dev-auth",
                title="Backend Developer",
                company_name="TechCorp",
                description="Python and FastAPI",
                url="https://example.com/jobs/10",
                remote=True,
            )
            s_python = Skill(name="Python", category="Programming Languages")
            s_fastapi = Skill(name="FastAPI", category="Backend")
            session.add_all([job, s_python, s_fastapi])
            session.commit()

            # Create associations through authoritative Job.job_skills
            job.job_skills.append(JobSkill(skill=s_python))
            job.job_skills.append(JobSkill(skill=s_fastapi))
            session.commit()

            # Verify reading associated skills through Job.skills
            queried_job = session.scalar(select(Job).filter_by(slug="backend-dev-auth"))
            self.assertIsNotNone(queried_job)
            self.assertEqual(len(queried_job.skills), 2)
            self.assertEqual({s.name for s in queried_job.skills}, {"Python", "FastAPI"})

            # Verify reading associated jobs through Skill.jobs
            queried_skill = session.scalar(select(Skill).filter_by(name="Python"))
            self.assertIsNotNone(queried_skill)
            self.assertEqual(len(queried_skill.jobs), 1)
            self.assertEqual(queried_skill.jobs[0].title, "Backend Developer")

    def test_job_associated_with_multiple_skills(self) -> None:
        """Verify that a single job can be associated with multiple skills through job_skills."""
        with Session(self.engine) as session:
            job = Job(
                slug="fullstack-engineer-1",
                title="Fullstack Engineer",
                company_name="Tech Solutions",
                description="Python, React, and PostgreSQL stack",
                url="https://example.com/jobs/2",
                remote=False,
            )
            s_python = Skill(name="Python", category="Programming Languages")
            s_react = Skill(name="React", category="Frontend")
            s_postgres = Skill(name="PostgreSQL", category="Databases")

            job.job_skills.extend([
                JobSkill(skill=s_python),
                JobSkill(skill=s_react),
                JobSkill(skill=s_postgres),
            ])
            session.add(job)
            session.commit()

            # Query back from database and read via Job.skills
            queried_job = session.scalar(select(Job).filter_by(slug="fullstack-engineer-1"))
            self.assertIsNotNone(queried_job)
            self.assertEqual(len(queried_job.skills), 3)
            self.assertEqual(len(queried_job.job_skills), 3)
            skill_names = {s.name for s in queried_job.skills}
            self.assertEqual(skill_names, {"Python", "React", "PostgreSQL"})

    def test_skill_associated_with_multiple_jobs(self) -> None:
        """Verify that a single skill can be associated with multiple jobs through job_skills."""
        with Session(self.engine) as session:
            skill = Skill(name="Docker", category="DevOps and Infrastructure")
            j1 = Job(
                slug="devops-eng-1",
                title="DevOps Engineer",
                company_name="Cloud Inc",
                description="Container orchestration",
                url="https://example.com/jobs/3",
                remote=True,
            )
            j2 = Job(
                slug="backend-dev-2",
                title="Backend Developer",
                company_name="Data Corp",
                description="Backend containerization",
                url="https://example.com/jobs/4",
                remote=False,
            )

            skill.job_skills.extend([
                JobSkill(job=j1),
                JobSkill(job=j2),
            ])
            session.add(skill)
            session.commit()

            # Query back from database and read via Skill.jobs
            queried_skill = session.scalar(select(Skill).filter_by(name="Docker"))
            self.assertIsNotNone(queried_skill)
            self.assertEqual(len(queried_skill.jobs), 2)
            self.assertEqual(len(queried_skill.job_skills), 2)
            job_titles = {j.title for j in queried_skill.jobs}
            self.assertEqual(job_titles, {"DevOps Engineer", "Backend Developer"})

    def test_removing_association(self) -> None:
        """Verify removing a JobSkill association updates Job.skills and purges junction row."""
        with Session(self.engine) as session:
            job = Job(
                slug="polyglot-eng-1",
                title="Polyglot Engineer",
                company_name="Innovate Ltd",
                description="Go and Python",
                url="https://example.com/jobs/20",
                remote=True,
            )
            s_go = Skill(name="Go", category="Programming Languages")
            s_python = Skill(name="Python", category="Programming Languages")

            js_go = JobSkill(job=job, skill=s_go)
            js_python = JobSkill(job=job, skill=s_python)
            session.add_all([job, s_go, s_python, js_go, js_python])
            session.commit()

            # Verify initial associations
            self.assertEqual(len(job.skills), 2)
            self.assertEqual(len(job.job_skills), 2)

            # Remove the Go association via authoritative job_skills
            job.job_skills.remove(js_go)
            session.delete(js_go)
            session.commit()

            # Refresh and verify
            session.refresh(job)
            self.assertEqual(len(job.job_skills), 1)
            self.assertEqual(len(job.skills), 1)
            self.assertEqual(job.skills[0].name, "Python")

            # Verify junction row in database
            remaining_js = session.scalars(select(JobSkill).filter_by(job_id=job.id)).all()
            self.assertEqual(len(remaining_js), 1)
            self.assertEqual(remaining_js[0].skill_id, s_python.id)

            # Target skill 'Go' remains completely intact in skills table
            go_in_db = session.scalar(select(Skill).filter_by(name="Go"))
            self.assertIsNotNone(go_in_db)

    def test_no_duplicate_inserts_or_conflicting_writes(self) -> None:
        """Verify viewonly=True prevents duplicate INSERT statements and conflicting writes."""
        with Session(self.engine) as session:
            job = Job(
                slug="conflict-check-1",
                title="Conflict Test Job",
                company_name="Audit Corp",
                description="Testing write isolation",
                url="https://example.com/jobs/30",
                remote=False,
            )
            skill = Skill(name="PostgreSQL", category="Databases")
            session.add_all([job, skill])
            session.commit()

            # Add via authoritative JobSkill
            js = JobSkill(job_id=job.id, skill_id=skill.id)
            session.add(js)

            # Attempting to mutate viewonly relationship in-memory does not generate duplicate INSERTs
            job.skills.append(skill)
            session.commit()

            # Verify exactly ONE junction row exists in database
            js_rows = session.scalars(
                select(JobSkill).filter_by(job_id=job.id, skill_id=skill.id)
            ).all()
            self.assertEqual(len(js_rows), 1)

    def test_foreign_key_cascade_delete_job(self) -> None:
        """Verify deleting a job cascades to delete its job_skills junction rows."""
        with Session(self.engine) as session:
            job = Job(
                slug="cloud-architect-1",
                title="Cloud Architect",
                company_name="Enterprise Systems",
                description="Terraform and AWS",
                url="https://example.com/jobs/5",
                remote=True,
            )
            skill = Skill(name="AWS", category="Cloud")
            job.job_skills.append(JobSkill(skill=skill))
            session.add(job)
            session.commit()

            job_id = job.id
            skill_id = skill.id

            # Verify junction row exists
            js_record = session.scalar(
                select(JobSkill).filter_by(job_id=job_id, skill_id=skill_id)
            )
            self.assertIsNotNone(js_record)

            # Delete the job
            session.delete(job)
            session.commit()

            # Junction row must be deleted
            remaining_js = session.scalars(select(JobSkill).filter_by(job_id=job_id)).all()
            self.assertEqual(len(remaining_js), 0)

            # Target skill must remain intact
            remaining_skill = session.scalar(select(Skill).filter_by(id=skill_id))
            self.assertIsNotNone(remaining_skill)
            self.assertEqual(remaining_skill.name, "AWS")

    def test_foreign_key_cascade_delete_skill(self) -> None:
        """Verify deleting a skill cascades to delete its job_skills junction rows."""
        with Session(self.engine) as session:
            job = Job(
                slug="ml-engineer-1",
                title="ML Engineer",
                company_name="AI Labs",
                description="PyTorch models",
                url="https://example.com/jobs/6",
                remote=True,
            )
            skill = Skill(name="PyTorch", category="Data Science and AI")
            job.job_skills.append(JobSkill(skill=skill))
            session.add(job)
            session.commit()

            job_id = job.id
            skill_id = skill.id

            # Delete the skill
            session.delete(skill)
            session.commit()

            # Junction row must be deleted
            remaining_js = session.scalars(select(JobSkill).filter_by(skill_id=skill_id)).all()
            self.assertEqual(len(remaining_js), 0)

            # Target job must remain intact
            remaining_job = session.scalar(select(Job).filter_by(id=job_id))
            self.assertIsNotNone(remaining_job)
            self.assertEqual(remaining_job.title, "ML Engineer")

    def test_direct_relational_joins(self) -> None:
        """Verify standard relational joins can be executed via Job.skills and Skill.jobs."""
        with Session(self.engine) as session:
            j = Job(
                slug="k8s-specialist-1",
                title="Kubernetes Specialist",
                company_name="Platform Co",
                description="Kubernetes clusters",
                url="https://example.com/jobs/7",
                remote=True,
            )
            s = Skill(name="Kubernetes", category="DevOps and Infrastructure")
            j.job_skills.append(JobSkill(skill=s))
            session.add(j)
            session.commit()

            # Join Job -> Skill
            stmt_job = select(Job).join(Job.skills).where(Skill.name == "Kubernetes")
            matched_job = session.scalar(stmt_job)
            self.assertIsNotNone(matched_job)
            self.assertEqual(matched_job.slug, "k8s-specialist-1")

            # Join Skill -> Job
            stmt_skill = select(Skill).join(Skill.jobs).where(Job.slug == "k8s-specialist-1")
            matched_skill = session.scalar(stmt_skill)
            self.assertIsNotNone(matched_skill)
            self.assertEqual(matched_skill.name, "Kubernetes")


if __name__ == "__main__":
    unittest.main()
