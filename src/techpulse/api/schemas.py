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
