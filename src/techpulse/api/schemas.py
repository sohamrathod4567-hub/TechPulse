"""
Pydantic Schemas for TechPulse API.

Provides data transfer objects (DTOs) and response models for API endpoints,
with support for serializing SQLAlchemy ORM instances.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobResponse(BaseModel):
    """
    Schema representing a job listing in API responses.

    Configured with `from_attributes=True` for seamless serialization
    from SQLAlchemy Job ORM objects.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: int = Field(..., description="Unique surrogate primary key identifier")
    slug: str = Field(..., description="Unique URL-friendly job slug")
    title: str = Field(..., description="Job designation or title")
    company_name: str = Field(..., description="Name of the hiring organization")
    description: str = Field(..., description="Full text description of the job")
    location: Optional[str] = Field(None, description="City or geographic location (None for remote)")
    remote: bool = Field(False, description="Whether the position is fully remote")
    url: str = Field(..., description="Direct URL to original job posting")
    tags: List[str] = Field(default_factory=list, description="Skill and industry tags")
    job_types: List[str] = Field(default_factory=list, description="Employment types (e.g. Full-time, Freelance)")
    created_at: Optional[datetime] = Field(None, description="Original publication timestamp")
    inserted_at: datetime = Field(..., description="Record insertion timestamp")
    updated_at: datetime = Field(..., description="Record last modification timestamp")


class JobListResponse(BaseModel):
    """
    Paginated response schema for job listings.

    Attributes:
        total: Total number of matching records in the database.
        jobs: List of paginated JobResponse items for the current page.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    total: int = Field(..., description="Total number of jobs in database")
    jobs: List[JobResponse] = Field(..., description="Paginated list of job postings")


class AnalyticsOverviewResponse(BaseModel):
    """
    Schema representing aggregate analytics overview statistics across job listings.

    Attributes:
        total_jobs: Total number of jobs in the database.
        remote_jobs: Number of jobs where remote is true.
        non_remote_jobs: Number of jobs where remote is false.
        jobs_with_location: Number of jobs with a non-null, non-empty location.
        unique_companies: Number of distinct hiring companies.
        unique_locations: Number of distinct non-null, non-empty locations.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    total_jobs: int = Field(..., ge=0, description="Total number of jobs in database")
    remote_jobs: int = Field(..., ge=0, description="Number of fully remote jobs")
    non_remote_jobs: int = Field(..., ge=0, description="Number of on-site or hybrid non-remote jobs")
    jobs_with_location: int = Field(..., ge=0, description="Number of jobs with a non-null, non-empty location")
    unique_companies: int = Field(..., ge=0, description="Number of distinct hiring companies")
    unique_locations: int = Field(..., ge=0, description="Number of distinct non-null, non-empty locations")


class TitleCount(BaseModel):
    """
    Schema representing a job title and its frequency count.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    title: str = Field(..., description="Job designation or title")
    job_count: int = Field(..., ge=0, description="Number of job postings with this title")


class TopTitlesResponse(BaseModel):
    """
    Response schema for the top job titles analytics endpoint.

    Attributes:
        total_titles: Total number of distinct non-null, non-empty job titles in the database.
        titles: List of top job titles sorted by frequency descending, then title ascending.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    total_titles: int = Field(..., ge=0, description="Total number of distinct non-null, non-empty job titles")
    titles: List[TitleCount] = Field(..., description="List of top job titles and their posting counts")


class CompanyCount(BaseModel):
    """
    Schema representing a hiring company and its job posting frequency count.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    company_name: str = Field(..., description="Hiring organization name")
    job_count: int = Field(..., ge=0, description="Number of job postings by this company")


class TopCompaniesResponse(BaseModel):
    """
    Response schema for the top hiring companies analytics endpoint.

    Attributes:
        total_companies: Total number of distinct valid hiring companies in the database.
        companies: List of top hiring companies sorted by frequency descending, then company_name ascending.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    total_companies: int = Field(..., ge=0, description="Total number of distinct valid hiring companies")
    companies: List[CompanyCount] = Field(..., description="List of top hiring companies and their posting counts")



