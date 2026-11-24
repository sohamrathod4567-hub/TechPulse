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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

    def __repr__(self) -> str:
        """User-friendly string representation of the Job instance."""
        return (
            f"<Job(id={self.id!r}, slug={self.slug!r}, "
            f"title={self.title!r}, company_name={self.company_name!r})>"
        )
