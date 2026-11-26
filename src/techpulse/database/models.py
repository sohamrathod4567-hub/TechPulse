"""
SQLAlchemy Declarative Models for TechPulse.

This module defines the declarative Base and ORM models representing the
TechPulse data schema.

Models:
    - Job: Represents raw and cleaned technology job postings collected from APIs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.x Declarative Base class.

    Serves as the root class for all ORM models in TechPulse. Maintains
    the metadata registry mapping Python classes to relational database tables.
    """
    pass


class Job(Base):
    """
    Job Model representing technology job listings.

    Maps to the 'jobs' table in PostgreSQL. Contains listing metadata,
    company details, textual descriptions, categorical tags, employment types,
    and audit timestamps.

    Attributes:
        id (int): Primary key, auto-incrementing surrogate identifier.
        slug (str): Unique URL-friendly slug identifying the job post.
        title (str): Job title / designation.
        company_name (str): Name of the hiring company.
        description (str): Full text of the job description.
        location (str, optional): Geographic location or city of the job (null for remote).
        remote (bool): Flag indicating whether the position is remote.
        url (str): Web link / URL to the original job posting.
        tags (List[str]): Technical and industry skill tags (JSONB array).
        job_types (List[str]): Employment types e.g. Full-time, Freelance (JSONB array).
        created_at (datetime, optional): Original job publication timestamp (timezone-aware).
        inserted_at (datetime): Timestamp when record was inserted into TechPulse DB.
        updated_at (datetime): Timestamp when record was last updated in TechPulse DB.
    """

    __tablename__ = "jobs"

    __table_args__ = (
        # Unique constraint to prevent duplicate ingestion of the same job posting
        UniqueConstraint("slug", name="uq_jobs_slug"),
        # B-tree indexes for frequently queried search and filter columns
        Index("ix_jobs_title", "title"),
        Index("ix_jobs_company_name", "company_name"),
        Index("ix_jobs_location", "location"),
        Index("ix_jobs_created_at", "created_at"),
    )

    # 1. Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Surrogate primary key",
    )

    # 2. Unique Business Identifier
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Unique slug identifier from job board",
    )

    # 3. Core Job Details (Indexed)
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Job title or role",
    )

    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Hiring organization name",
    )

    # 4. Long Text & URLs
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Full job description text",
    )

    location: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Geographic location (nullable for remote)",
    )

    remote: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether role is remote",
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="URL to job posting",
    )

    # 5. Semi-structured JSONB arrays for high-performance indexing and queries
    tags: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        doc="Skill and industry tags stored as JSONB array",
    )

    job_types: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        doc="Employment types stored as JSONB array",
    )

    # 6. Audit & Publication Timestamps (Timezone-Aware)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Original publication datetime from API",
    )

    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Record creation timestamp in TechPulse",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Record last modified timestamp in TechPulse",
    )

    # 7. Relational Skill Associations
    job_skills: Mapped[List[JobSkill]] = relationship(
        "JobSkill",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        doc="Authoritative association records connecting this job to extracted skills",
    )

    skills: Mapped[List[Skill]] = relationship(
        "Skill",
        secondary="job_skills",
        back_populates="jobs",
        viewonly=True,
        doc="Canonical skills associated with this job posting (read-only query view)",
    )

    def __repr__(self) -> str:
        """User-friendly string representation of the Job instance."""
        return (
            f"<Job(id={self.id!r}, slug={self.slug!r}, "
            f"title={self.title!r}, company_name={self.company_name!r})>"
        )


class Skill(Base):
    """
    Skill Model representing canonical technical skills in the TechPulse taxonomy.

    Maps to the 'skills' table in PostgreSQL. Stores canonical skill names,
    their taxonomy category, and relational links to job postings.

    Attributes:
        id (int): Primary key, auto-incrementing identifier.
        name (str): Unique canonical skill name (e.g. 'Python', 'PostgreSQL').
        category (str): Taxonomy category (e.g. 'Programming Languages', 'Databases').
        job_skills (List[JobSkill]): Association records connecting to jobs.
        jobs (List[Job]): Jobs mentioning this skill.
    """

    __tablename__ = "skills"

    __table_args__ = (
        UniqueConstraint("name", name="uq_skills_name"),
        Index("ix_skills_category", "category"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Primary key identifier for skill",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Unique canonical skill name",
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Taxonomy category of the technical skill",
    )

    # Relational Associations
    job_skills: Mapped[List[JobSkill]] = relationship(
        "JobSkill",
        back_populates="skill",
        cascade="all, delete-orphan",
        passive_deletes=True,
        doc="Authoritative association records connecting this skill to jobs",
    )

    jobs: Mapped[List[Job]] = relationship(
        "Job",
        secondary="job_skills",
        back_populates="skills",
        viewonly=True,
        doc="Job postings requiring or mentioning this skill (read-only query view)",
    )

    def __repr__(self) -> str:
        """User-friendly string representation of the Skill instance."""
        return f"<Skill(id={self.id!r}, name={self.name!r}, category={self.category!r})>"


class JobSkill(Base):
    """
    JobSkill Association Model linking Jobs to their extracted canonical Skills.

    Maps to the 'job_skills' junction table. Uses a composite primary key
    `(job_id, skill_id)` to ensure unique associations, and CASCADE deletion
    so that removing a Job or Skill automatically cleans up junction entries.

    Attributes:
        job_id (int): Foreign key referencing jobs.id (primary key component).
        skill_id (int): Foreign key referencing skills.id (primary key component, indexed).
        job (Job): Associated Job instance.
        skill (Skill): Associated Skill instance.
    """

    __tablename__ = "job_skills"

    __table_args__ = (
        Index("ix_job_skills_skill_id", "skill_id"),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="Foreign key referencing jobs.id",
    )

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="Foreign key referencing skills.id",
    )

    # Relational Back-references
    job: Mapped[Job] = relationship(
        "Job",
        back_populates="job_skills",
        doc="Job instance associated with this junction record",
    )

    skill: Mapped[Skill] = relationship(
        "Skill",
        back_populates="job_skills",
        doc="Skill instance associated with this junction record",
    )

    def __repr__(self) -> str:
        """User-friendly string representation of the JobSkill instance."""
        return f"<JobSkill(job_id={self.job_id!r}, skill_id={self.skill_id!r})>"


__all__ = ["Base", "Job", "Skill", "JobSkill"]
