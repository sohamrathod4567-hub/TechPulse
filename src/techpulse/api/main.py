"""
Main FastAPI Application for TechPulse.

This module initializes the FastAPI backend application for the
TechPulse job market intelligence platform and registers core system
and resource endpoints.
"""

from typing import Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from techpulse.api.dependencies import get_db
from techpulse.api.schemas import JobListResponse, JobResponse
from techpulse.database.models import Job

# Instantiate the FastAPI application with metadata
app = FastAPI(
    title="TechPulse API",
    description="Job market intelligence platform",
    version="1.0.0",
)


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
    summary="Service Health Check",
    tags=["System"],
)
def health_check() -> Dict[str, str]:
    """
    Check the health status of the TechPulse API service.

    Returns:
        Dict[str, str]: Service status and application name confirming the API is operational.
    """
    return {
        "status": "healthy",
        "application": "TechPulse API",
    }


@app.get(
    "/jobs",
    status_code=status.HTTP_200_OK,
    response_model=JobListResponse,
    summary="List Job Postings",
    tags=["Jobs"],
)
def list_jobs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of job records to return (1-100)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of job records to skip from the start",
    ),
    title: Optional[str] = Query(
        default=None,
        description="Case-insensitive partial match on job title",
    ),
    company: Optional[str] = Query(
        default=None,
        description="Case-insensitive partial match on hiring company name",
    ),
    location: Optional[str] = Query(
        default=None,
        description="Case-insensitive partial match on job location",
    ),
    remote: Optional[bool] = Query(
        default=None,
        description="Filter by remote job status (true/false)",
    ),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """
    Retrieve paginated technology job postings ordered by ascending ID with optional filtering.

    Features:
        - Retrieves the total count of matching jobs directly in PostgreSQL.
        - Applies optional filters (title, company, location, remote) at the database level using SQL AND conjunction.
        - Case-insensitive partial matching for textual fields (title, company_name, location).
        - Exact boolean matching for remote status.
        - Applies pagination (OFFSET and LIMIT) directly in SQL for optimal performance.
        - Orders listings deterministically by ascending ID.
    """
    # Build filter conditions
    conditions = []
    if title is not None and title.strip():
        conditions.append(Job.title.ilike(f"%{title.strip()}%"))
    if company is not None and company.strip():
        conditions.append(Job.company_name.ilike(f"%{company.strip()}%"))
    if location is not None and location.strip():
        conditions.append(Job.location.ilike(f"%{location.strip()}%"))
    if remote is not None:
        conditions.append(Job.remote == remote)

    # Base query for counting matching records
    count_stmt = select(func.count(Job.id))

    # Base query for retrieving paginated job records
    jobs_stmt = select(Job)

    # Apply identical filter conditions to both queries
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        jobs_stmt = jobs_stmt.where(*conditions)

    # Apply deterministic ordering and SQL pagination
    jobs_stmt = jobs_stmt.order_by(Job.id.asc()).offset(offset).limit(limit)

    total_count = db.scalar(count_stmt) or 0
    jobs = db.scalars(jobs_stmt).all()

    return JobListResponse(total=total_count, jobs=jobs)


@app.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=JobResponse,
    summary="Get Job Posting by ID",
    tags=["Jobs"],
)
def get_job(
    job_id: int = Path(
        ...,
        ge=1,
        description="The unique positive integer ID of the job posting",
    ),
    db: Session = Depends(get_db),
) -> Job:
    """
    Retrieve a single job posting by its unique primary key identifier.

    Args:
        job_id (int): Positive integer identifier of the job record.
        db (Session): Database session injected via dependency.

    Returns:
        JobResponse: Full job posting record details serialized as Pydantic model.

    Raises:
        HTTPException: 404 Not Found if no job exists with the given ID.
        HTTPException: 422 Unprocessable Entity if job_id is not a positive integer.
    """
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    return job

