"""
Skill Database Backfill ETL Module for TechPulse.

Populates the 'skills' table from the canonical skill taxonomy and extracts
skills from all existing Job records to populate the 'job_skills' junction table.

Features:
- Pure canonical taxonomy insertion: 66 skills across 9 categories.
- Deduplication and idempotency: Safe to execute repeatedly without duplicating
  skills or job-skill associations.
- Atomic transaction management: Ensures all-or-nothing execution with automatic
  rollback upon failure.
- Structured metrics: Captures detailed execution statistics including unmatched skills.
- Isolation: Accepts custom Engine or Session for headless testing in SQLite.

Usage from CLI:
    python -m techpulse.etl.skill_backfill
    or
    python src/techpulse/etl/skill_backfill.py

Programmatic usage:
    from techpulse.etl.skill_backfill import SkillBackfill, backfill_skills
    metrics = backfill_skills()
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Path & Environment Setup
# ---------------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techpulse.database.connection import get_engine
from techpulse.database.models import Job, JobSkill, Skill
from techpulse.etl.skill_extractor import extract_skills, get_taxonomy

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("techpulse.etl.skill_backfill")


# ---------------------------------------------------------------------------
# Metrics Data Structure
# ---------------------------------------------------------------------------
@dataclass
class BackfillMetrics:
    """
    Structured metrics capturing the results of a skill backfill operation.
    """

    total_taxonomy_skills: int = 0
    skills_inserted: int = 0
    skills_existing: int = 0
    total_jobs_analyzed: int = 0
    jobs_with_skills: int = 0
    jobs_without_skills: int = 0
    total_associations_identified: int = 0
    associations_inserted: int = 0
    associations_existing: int = 0
    distinct_skills_detected: int = 0
    unmatched_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a standard Python dictionary."""
        return {
            "total_taxonomy_skills": self.total_taxonomy_skills,
            "skills_inserted": self.skills_inserted,
            "skills_existing": self.skills_existing,
            "total_jobs_analyzed": self.total_jobs_analyzed,
            "jobs_with_skills": self.jobs_with_skills,
            "jobs_without_skills": self.jobs_without_skills,
            "total_associations_identified": self.total_associations_identified,
            "associations_inserted": self.associations_inserted,
            "associations_existing": self.associations_existing,
            "distinct_skills_detected": self.distinct_skills_detected,
            "unmatched_skills": list(self.unmatched_skills),
        }

    def format_summary(self) -> str:
        """Format backfill metrics into a human-readable summary table."""
        lines = [
            "=" * 70,
            "TECHPULSE - SKILL DATABASE BACKFILL METRICS",
            "=" * 70,
            f"Taxonomy Skills (Total)       : {self.total_taxonomy_skills}",
            f"Skills Inserted               : {self.skills_inserted}",
            f"Skills Already Existing       : {self.skills_existing}",
            "-" * 70,
            f"Total Jobs Analyzed           : {self.total_jobs_analyzed}",
            f"Jobs With >= 1 Skill Detected : {self.jobs_with_skills}",
            f"Jobs With 0 Skills Detected   : {self.jobs_without_skills}",
            "-" * 70,
            f"Total Associations Identified : {self.total_associations_identified}",
            f"Associations Inserted         : {self.associations_inserted}",
            f"Associations Already Existing : {self.associations_existing}",
            f"Distinct Skills Detected      : {self.distinct_skills_detected}",
        ]
        if self.unmatched_skills:
            lines.append("-" * 70)
            lines.append(f"UNMATCHED SKILLS DETECTED     : {', '.join(self.unmatched_skills)}")
        lines.append("=" * 70)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Skill Backfill Engine
# ---------------------------------------------------------------------------
class SkillBackfill:
    """
    Coordinates idempotent database backfill of canonical skills and job-skill associations.
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        session: Optional[Session] = None,
    ) -> None:
        """
        Initialize the SkillBackfill manager.

        Args:
            engine: Optional SQLAlchemy Engine. Defaults to get_engine().
            session: Optional active SQLAlchemy Session. When provided, backfill executes
                     inside this session and respects its transaction boundary.
        """
        if engine is not None:
            self.engine = engine
        elif session is not None and session.bind is not None and isinstance(session.bind, Engine):
            self.engine = session.bind
        else:
            self.engine = get_engine()
        self._external_session = session

    def run(self) -> BackfillMetrics:
        """
        Execute the backfill process within an atomic transaction.

        Returns:
            BackfillMetrics: Backfill execution metrics and statistics.
        """
        if self._external_session is not None:
            return self._run_with_session(self._external_session, owns_session=False)

        with Session(bind=self.engine) as session:
            return self._run_with_session(session, owns_session=True)

    def _run_with_session(self, session: Session, owns_session: bool) -> BackfillMetrics:
        """
        Internal implementation handling transactional flow and execution.
        """
        metrics = BackfillMetrics()
        taxonomy = get_taxonomy()
        metrics.total_taxonomy_skills = len(taxonomy)

        logger.info(
            "Starting skill database backfill across %d canonical taxonomy skills...",
            metrics.total_taxonomy_skills,
        )

        # Determine appropriate transaction context
        # If the session is already in a transaction, use a SAVEPOINT (begin_nested)
        # to ensure atomic rollback without preempting the outer transaction.
        if session.in_transaction():
            trans_ctx = session.begin_nested()
        else:
            trans_ctx = session.begin()

        with trans_ctx:
            # Phase 1: Populate canonical skills table from taxonomy
            skill_map = self._populate_skills(session, taxonomy, metrics)

            # Phase 2: Extract skills from all jobs and populate job_skills
            self._associate_jobs(session, skill_map, metrics)

        logger.info(
            "Skill database backfill completed successfully. "
            "Skills: %d inserted, %d existing. "
            "Associations: %d inserted, %d existing.",
            metrics.skills_inserted,
            metrics.skills_existing,
            metrics.associations_inserted,
            metrics.associations_existing,
        )
        return metrics

    def _populate_skills(
        self,
        session: Session,
        taxonomy: Dict[str, Any],
        metrics: BackfillMetrics,
    ) -> Dict[str, Skill]:
        """
        Insert canonical skills into the skills table, reusing existing records.

        Args:
            session: Active database session.
            taxonomy: Canonical taxonomy dictionary mapping skill name to SkillDefinition.
            metrics: Metrics object to populate.

        Returns:
            Dict[str, Skill]: Lookup map of canonical skill name to Skill database instance.
        """
        # Query existing skills
        existing_skills_stmt = select(Skill)
        existing_skills = session.execute(existing_skills_stmt).scalars().all()
        skill_map: Dict[str, Skill] = {s.name: s for s in existing_skills}
        metrics.skills_existing = len(skill_map)

        new_skills: List[Skill] = []
        for name, skill_def in taxonomy.items():
            if name not in skill_map:
                skill_record = Skill(name=skill_def.name, category=skill_def.category)
                session.add(skill_record)
                skill_map[name] = skill_record
                new_skills.append(skill_record)

        if new_skills:
            # Flush new Skill records to PostgreSQL/SQLite to assign primary keys (id)
            session.flush()
            metrics.skills_inserted = len(new_skills)
            logger.info("Inserted %d new canonical skills from taxonomy.", len(new_skills))
        else:
            logger.info("All %d taxonomy skills already exist in database.", len(skill_map))

        return skill_map

    def _associate_jobs(
        self,
        session: Session,
        skill_map: Dict[str, Skill],
        metrics: BackfillMetrics,
    ) -> None:
        """
        Extract skills for all jobs and populate job_skills association records.

        Args:
            session: Active database session.
            skill_map: Mapping of canonical skill names to Skill database instances.
            metrics: Metrics object to populate.
        """
        # Load existing associations to guarantee idempotency and avoid duplicates
        existing_associations_stmt = select(JobSkill.job_id, JobSkill.skill_id)
        existing_associations: Set[Tuple[int, int]] = set(
            session.execute(existing_associations_stmt).all()
        )

        # Retrieve all jobs in deterministic primary key order
        jobs_stmt = select(Job).order_by(Job.id)
        jobs = session.execute(jobs_stmt).scalars().all()
        metrics.total_jobs_analyzed = len(jobs)

        distinct_skills: Set[str] = set()
        unmatched_skills: Set[str] = set()
        associations_inserted = 0
        associations_existing = 0

        for job in jobs:
            # Combine title and description with newline separator as specified
            title_text = job.title or ""
            desc_text = job.description or ""
            combined_text = f"{title_text}\n{desc_text}"

            # Call existing pure-Python skill extractor
            extracted_skill_names = extract_skills(combined_text)

            if extracted_skill_names:
                metrics.jobs_with_skills += 1
            else:
                metrics.jobs_without_skills += 1

            for skill_name in extracted_skill_names:
                distinct_skills.add(skill_name)
                metrics.total_associations_identified += 1

                skill_obj = skill_map.get(skill_name)
                if skill_obj is None:
                    unmatched_skills.add(skill_name)
                    logger.warning(
                        "Extracted skill '%s' for job ID %d not found in Skill database map!",
                        skill_name,
                        job.id,
                    )
                    continue

                pair = (job.id, skill_obj.id)
                if pair in existing_associations:
                    associations_existing += 1
                else:
                    new_assoc = JobSkill(job_id=job.id, skill_id=skill_obj.id)
                    session.add(new_assoc)
                    existing_associations.add(pair)
                    associations_inserted += 1

        metrics.associations_inserted = associations_inserted
        metrics.associations_existing = associations_existing
        metrics.distinct_skills_detected = len(distinct_skills)
        metrics.unmatched_skills = sorted(list(unmatched_skills))

        if unmatched_skills:
            logger.error(
                "Backfill encountered %d unmatched skill names: %s",
                len(unmatched_skills),
                metrics.unmatched_skills,
            )

        logger.info(
            "Analyzed %d jobs: %d with detected skills, %d without. "
            "Associations: %d inserted, %d already existing.",
            metrics.total_jobs_analyzed,
            metrics.jobs_with_skills,
            metrics.jobs_without_skills,
            metrics.associations_inserted,
            metrics.associations_existing,
        )


# ---------------------------------------------------------------------------
# Convenience Function & CLI Entrypoint
# ---------------------------------------------------------------------------
def backfill_skills(
    engine: Optional[Engine] = None,
    session: Optional[Session] = None,
) -> BackfillMetrics:
    """
    Execute the skill database backfill.

    Args:
        engine: Optional SQLAlchemy Engine. Defaults to get_engine().
        session: Optional active SQLAlchemy Session. When provided, executes
                 within that session's transaction context.

    Returns:
        BackfillMetrics: Summary metrics of the backfill operation.
    """
    return SkillBackfill(engine=engine, session=session).run()


def main() -> None:
    """CLI entrypoint to execute the skill database backfill."""
    print("\n" + "=" * 70)
    print("TECHPULSE - TECHNICAL SKILL DATABASE BACKFILL")
    print("=" * 70)

    try:
        engine = get_engine()
        safe_url = engine.url.render_as_string(hide_password=True)
        print(f"Target Database : {safe_url}")
        print("-" * 70)

        backfill = SkillBackfill(engine=engine)
        metrics = backfill.run()

        print("\n" + metrics.format_summary() + "\n")
        print("[SUCCESS] Technical skill backfill completed successfully!\n")

    except Exception as exc:
        logger.exception("Skill database backfill failed: %s", exc)
        print(f"\n[FAILURE] Skill database backfill failed: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = ["SkillBackfill", "BackfillMetrics", "backfill_skills", "main"]
