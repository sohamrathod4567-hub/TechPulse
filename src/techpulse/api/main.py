"""
Main FastAPI Application for TechPulse.

This module initializes the FastAPI backend application for the
TechPulse job market intelligence platform and registers core system
and resource endpoints.
"""

from typing import Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from techpulse.api.dependencies import get_db
from techpulse.api.schemas import (
    AnalyticsOverviewResponse,
    CompanyCount,
    JobListResponse,
    JobResponse,
    LocationCount,
    LocationsResponse,
    RemoteDistributionResponse,
    SkillCategoriesResponse,
    SkillCategoryCount,
    SkillCount,
    SkillLocationCount,
    SkillsByLocationResponse,
    TitleCount,
    TopCompaniesResponse,
    TopSkillsResponse,
    TopTitlesResponse,
)
from techpulse.database.models import Job, JobSkill, Skill

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


@app.get(
    "/analytics/overview",
    status_code=status.HTTP_200_OK,
    response_model=AnalyticsOverviewResponse,
    summary="Get Analytics Overview",
    tags=["Analytics"],
)
def get_analytics_overview(
    db: Session = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """
    Compute and return high-level aggregate statistics across all job listings.

    Calculations are performed entirely in SQL using aggregate functions:
        - total_jobs: COUNT(Job.id)
        - remote_jobs: COUNT(CASE WHEN remote IS true THEN 1 END)
        - non_remote_jobs: COUNT(CASE WHEN remote IS false THEN 1 END)
        - jobs_with_location: COUNT(CASE WHEN location IS NOT NULL AND TRIM(location) != '' THEN 1 END)
        - unique_companies: COUNT(DISTINCT company_name)
        - unique_locations: COUNT(DISTINCT CASE WHEN location IS NOT NULL AND TRIM(location) != '' THEN TRIM(location) END)

    Returns:
        AnalyticsOverviewResponse: Aggregated counts and uniqueness metrics.
    """
    stmt = select(
        func.count(Job.id).label("total_jobs"),
        func.count(case((Job.remote.is_(True), 1))).label("remote_jobs"),
        func.count(case((Job.remote.is_(False), 1))).label("non_remote_jobs"),
        func.count(
            case(
                (
                    and_(
                        Job.location.is_not(None),
                        func.trim(Job.location) != "",
                    ),
                    1,
                )
            )
        ).label("jobs_with_location"),
        func.count(func.distinct(Job.company_name)).label("unique_companies"),
        func.count(
            func.distinct(
                case(
                    (
                        and_(
                            Job.location.is_not(None),
                            func.trim(Job.location) != "",
                        ),
                        func.trim(Job.location),
                    )
                )
            )
        ).label("unique_locations"),
    )

    row = db.execute(stmt).one()
    data = row._mapping

    return AnalyticsOverviewResponse(
        total_jobs=data["total_jobs"] or 0,
        remote_jobs=data["remote_jobs"] or 0,
        non_remote_jobs=data["non_remote_jobs"] or 0,
        jobs_with_location=data["jobs_with_location"] or 0,
        unique_companies=data["unique_companies"] or 0,
        unique_locations=data["unique_locations"] or 0,
    )


@app.get(
    "/analytics/top-titles",
    status_code=status.HTTP_200_OK,
    response_model=TopTitlesResponse,
    summary="Get Top Job Titles by Frequency",
    tags=["Analytics"],
)
def get_top_titles(
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of top job titles to return (1-50)",
    ),
    db: Session = Depends(get_db),
) -> TopTitlesResponse:
    """
    Retrieve top job titles ranked by listing frequency with tie-breaking alphabetically.

    Features:
        - Groups job listings by title and computes occurrence count.
        - Sorts primarily by job_count descending, secondarily by title ascending.
        - Calculates the total number of distinct non-null, non-empty titles.
        - Limits result set within range [1, 50] (default 10).
        - Safely handles empty databases.
    """
    # Query total distinct non-null, non-empty titles count
    total_count_stmt = select(func.count(func.distinct(Job.title))).where(
        Job.title.is_not(None),
        func.trim(Job.title) != "",
    )
    total_titles = db.scalar(total_count_stmt) or 0

    # Query top titles grouped, sorted, and limited in SQL
    titles_stmt = (
        select(
            Job.title,
            func.count(Job.id).label("job_count"),
        )
        .where(
            Job.title.is_not(None),
            func.trim(Job.title) != "",
        )
        .group_by(Job.title)
        .order_by(func.count(Job.id).desc(), Job.title.asc())
        .limit(limit)
    )
    rows = db.execute(titles_stmt).all()
    titles = [
        TitleCount(title=row.title, job_count=row.job_count)
        for row in rows
    ]

    return TopTitlesResponse(total_titles=total_titles, titles=titles)


@app.get(
    "/analytics/top-companies",
    status_code=status.HTTP_200_OK,
    response_model=TopCompaniesResponse,
    summary="Get Top Hiring Companies by Posting Frequency",
    tags=["Analytics"],
)
def get_top_companies(
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of top hiring companies to return (1-50)",
    ),
    db: Session = Depends(get_db),
) -> TopCompaniesResponse:
    """
    Retrieve top hiring companies ranked by job posting frequency with alphabetical tie-breaking.

    Features:
        - Excludes NULL, empty, and whitespace-only company names.
        - Groups job listings by company_name and computes occurrence count.
        - Sorts primarily by job_count descending, secondarily by company_name ascending.
        - Calculates the total number of distinct valid company names.
        - Limits result set within range [1, 50] (default 10).
        - Safely handles empty databases.
    """
    # 1. Total distinct valid company names count (independent of limit)
    total_count_stmt = select(func.count(func.distinct(Job.company_name))).where(
        Job.company_name.is_not(None),
        func.trim(Job.company_name) != "",
    )
    total_companies = db.scalar(total_count_stmt) or 0

    # 2. Grouped, counted, sorted, and limited companies query
    companies_stmt = (
        select(
            Job.company_name,
            func.count(Job.id).label("job_count"),
        )
        .where(
            Job.company_name.is_not(None),
            func.trim(Job.company_name) != "",
        )
        .group_by(Job.company_name)
        .order_by(func.count(Job.id).desc(), Job.company_name.asc())
        .limit(limit)
    )
    rows = db.execute(companies_stmt).all()
    companies = [
        CompanyCount(company_name=row.company_name, job_count=row.job_count)
        for row in rows
    ]

    return TopCompaniesResponse(total_companies=total_companies, companies=companies)


@app.get(
    "/analytics/locations",
    status_code=status.HTTP_200_OK,
    response_model=LocationsResponse,
    summary="Get Job Locations by Posting Frequency",
    tags=["Analytics"],
)
def get_locations(
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of top locations to return (1-50)",
    ),
    db: Session = Depends(get_db),
) -> LocationsResponse:
    """
    Retrieve job locations ranked by posting frequency with alphabetical tie-breaking.

    Features:
        - Excludes NULL, empty, and whitespace-only locations.
        - Normalizes locations using SQL TRIM to prevent duplicate groupings caused by whitespace.
        - Groups job listings by normalized location and computes occurrence counts.
        - Sorts primarily by job_count descending, secondarily by location ascending.
        - Calculates the total number of distinct valid normalized locations.
        - Limits result set within range [1, 50] (default 10).
        - Safely handles empty databases.
    """
    # 1. Total distinct valid normalized locations count (independent of limit)
    total_count_stmt = select(
        func.count(func.distinct(func.trim(Job.location)))
    ).where(
        Job.location.is_not(None),
        func.trim(Job.location) != "",
    )
    total_locations = db.scalar(total_count_stmt) or 0

    # 2. Grouped, counted, sorted, and limited locations query
    locations_stmt = (
        select(
            func.trim(Job.location).label("location"),
            func.count(Job.id).label("job_count"),
        )
        .where(
            Job.location.is_not(None),
            func.trim(Job.location) != "",
        )
        .group_by(func.trim(Job.location))
        .order_by(func.count(Job.id).desc(), func.trim(Job.location).asc())
        .limit(limit)
    )
    rows = db.execute(locations_stmt).all()
    locations = [
        LocationCount(location=row.location, job_count=row.job_count)
        for row in rows
    ]

    return LocationsResponse(total_locations=total_locations, locations=locations)


@app.get(
    "/analytics/remote-distribution",
    status_code=status.HTTP_200_OK,
    response_model=RemoteDistributionResponse,
    summary="Get Remote Work Distribution",
    tags=["Analytics"],
)
def get_remote_distribution(
    db: Session = Depends(get_db),
) -> RemoteDistributionResponse:
    """
    Compute distribution counts and percentages of remote, non-remote, and unspecified jobs.

    Features:
        - Classifies listings into remote (remote = TRUE), non-remote (remote = FALSE), and unspecified (remote IS NULL).
        - Computes all counts directly in SQL via aggregate CASE expressions.
        - Calculates percentages using total_jobs as denominator, rounded to two decimal places.
        - Returns 0.0 for all percentages when total_jobs is zero.
        - Safely handles empty databases.
    """
    stmt = select(
        func.count(Job.id).label("total_jobs"),
        func.count(case((Job.remote.is_(True), 1))).label("remote_jobs"),
        func.count(case((Job.remote.is_(False), 1))).label("non_remote_jobs"),
        func.count(case((Job.remote.is_(None), 1))).label("unspecified_jobs"),
    )
    row = db.execute(stmt).one()
    data = row._mapping

    total_jobs = data["total_jobs"] or 0
    remote_jobs = data["remote_jobs"] or 0
    non_remote_jobs = data["non_remote_jobs"] or 0
    unspecified_jobs = data["unspecified_jobs"] or 0

    if total_jobs > 0:
        remote_percentage = round((remote_jobs / total_jobs) * 100.0, 2)
        non_remote_percentage = round((non_remote_jobs / total_jobs) * 100.0, 2)
        unspecified_percentage = round((unspecified_jobs / total_jobs) * 100.0, 2)
    else:
        remote_percentage = 0.0
        non_remote_percentage = 0.0
        unspecified_percentage = 0.0

    return RemoteDistributionResponse(
        total_jobs=total_jobs,
        remote_jobs=remote_jobs,
        non_remote_jobs=non_remote_jobs,
        unspecified_jobs=unspecified_jobs,
        remote_percentage=remote_percentage,
        non_remote_percentage=non_remote_percentage,
        unspecified_percentage=unspecified_percentage,
    )


@app.get(
    "/analytics/top-skills",
    status_code=status.HTTP_200_OK,
    response_model=TopSkillsResponse,
    summary="Get Top Technical Skills by Job Posting Frequency",
    tags=["Analytics"],
)
def get_top_skills(
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of top technical skills to return (1-50)",
    ),
    db: Session = Depends(get_db),
) -> TopSkillsResponse:
    """
    Retrieve top technical skills ranked by job posting frequency with alphabetical tie-breaking.

    Features:
        - Joins Skill and JobSkill to compute posting frequencies.
        - Counts distinct jobs per skill to prevent duplicate counts.
        - Excludes skills with zero job associations.
        - Calculates total number of distinct skills with >= 1 job association independent of limit.
        - Sorts primarily by job_count descending, secondarily by skill name ascending.
        - Limits result set within range [1, 50] (default 10).
        - Safely handles empty databases.
    """
    # 1. Total distinct skills with at least one job association (independent of limit)
    total_skills_stmt = (
        select(func.count(func.distinct(Skill.id)))
        .select_from(Skill)
        .join(JobSkill, Skill.id == JobSkill.skill_id)
    )
    total_skills = db.scalar(total_skills_stmt) or 0

    # 2. Grouped, counted, sorted, and limited skills query
    skills_stmt = (
        select(
            Skill.name.label("skill"),
            Skill.category.label("category"),
            func.count(func.distinct(JobSkill.job_id)).label("job_count"),
        )
        .select_from(Skill)
        .join(JobSkill, Skill.id == JobSkill.skill_id)
        .group_by(Skill.id, Skill.name, Skill.category)
        .order_by(
            func.count(func.distinct(JobSkill.job_id)).desc(),
            Skill.name.asc(),
        )
        .limit(limit)
    )
    rows = db.execute(skills_stmt).all()
    skills = [
        SkillCount(
            skill=row.skill,
            category=row.category,
            job_count=row.job_count,
        )
        for row in rows
    ]

    return TopSkillsResponse(total_skills=total_skills, skills=skills)


@app.get(
    "/analytics/skill-categories",
    status_code=status.HTTP_200_OK,
    response_model=SkillCategoriesResponse,
    summary="Get Technical Skill Analytics by Taxonomy Category",
    tags=["Analytics"],
)
def get_skill_categories(
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of skill categories to return (1-50)",
    ),
    db: Session = Depends(get_db),
) -> SkillCategoriesResponse:
    """
    Retrieve skill taxonomy categories ranked by distinct job demand with alphabetical tie-breaking.

    Features:
        - Joins Skill and JobSkill to compute aggregate category demand metrics.
        - Calculates:
            * skill_count: distinct skills in category with >= 1 job association.
            * total_job_associations: total association records in category.
            * unique_jobs: distinct jobs associated with >= 1 skill in category.
        - Excludes categories with zero detected job associations.
        - Calculates total number of active categories independent of limit.
        - Sorts primarily by unique_jobs descending, secondarily by category name ascending.
        - Limits result set within range [1, 50] (default 10).
        - Safely handles empty databases.
    """
    # 1. Total distinct categories with at least one job association (independent of limit)
    total_categories_stmt = (
        select(func.count(func.distinct(Skill.category)))
        .select_from(Skill)
        .join(JobSkill, Skill.id == JobSkill.skill_id)
    )
    total_categories = db.scalar(total_categories_stmt) or 0

    # 2. Grouped, calculated, sorted, and limited categories query
    categories_stmt = (
        select(
            Skill.category.label("category"),
            func.count(func.distinct(Skill.id)).label("skill_count"),
            func.count(JobSkill.job_id).label("total_job_associations"),
            func.count(func.distinct(JobSkill.job_id)).label("unique_jobs"),
        )
        .select_from(Skill)
        .join(JobSkill, Skill.id == JobSkill.skill_id)
        .group_by(Skill.category)
        .order_by(
            func.count(func.distinct(JobSkill.job_id)).desc(),
            Skill.category.asc(),
        )
        .limit(limit)
    )
    rows = db.execute(categories_stmt).all()
    categories = [
        SkillCategoryCount(
            category=row.category,
            skill_count=row.skill_count,
            total_job_associations=row.total_job_associations,
            unique_jobs=row.unique_jobs,
        )
        for row in rows
    ]

    return SkillCategoriesResponse(total_categories=total_categories, categories=categories)


@app.get(
    "/analytics/skills-by-location",
    status_code=status.HTTP_200_OK,
    response_model=SkillsByLocationResponse,
    summary="Get Top Technical Skills Demanded by Geographic Location",
    tags=["Analytics"],
)
def get_skills_by_location(
    location: str = Query(
        ...,
        description="Geographic location to filter skills by (case-insensitive, trimmed)",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of top skills to return (1-50)",
    ),
    db: Session = Depends(get_db),
) -> SkillsByLocationResponse:
    """
    Retrieve top technical skills demanded in a specific geographic location.

    Features:
        - Requires a non-empty location query parameter.
        - Trims leading and trailing whitespace from the location input.
        - Returns HTTP 422 if location is empty or whitespace-only.
        - Matches Job.location case-insensitively and whitespace-insensitively in SQL.
        - Filters out NULL and blank locations in SQL.
        - Joins Job, JobSkill, and Skill models.
        - Computes distinct job counts per skill to prevent duplicate counts.
        - Excludes skills without associations in the specified location.
        - Calculates total distinct skills in the location independently of the limit.
        - Sorts primarily by job_count descending, secondarily by skill name ascending.
        - Returns HTTP 200 with total_skills=0 and empty skills list if no jobs match.
    """
    normalized_location = location.strip() if location else ""
    if not normalized_location:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Query parameter 'location' must not be empty or whitespace-only.",
        )

    # 1. Total distinct skills associated with jobs in this location (independent of limit)
    total_skills_stmt = (
        select(func.count(func.distinct(Skill.id)))
        .select_from(Skill)
        .join(JobSkill, Skill.id == JobSkill.skill_id)
        .join(Job, Job.id == JobSkill.job_id)
        .where(
            Job.location.is_not(None),
            func.lower(func.trim(Job.location)) == normalized_location.lower(),
        )
    )
    total_skills = db.scalar(total_skills_stmt) or 0

    # 2. Grouped, counted, sorted, and limited skills query
    skills_stmt = (
        select(
            Skill.name.label("skill"),
            Skill.category.label("category"),
            func.count(func.distinct(Job.id)).label("job_count"),
        )
        .select_from(Skill)
        .join(JobSkill, Skill.id == JobSkill.skill_id)
        .join(Job, Job.id == JobSkill.job_id)
        .where(
            Job.location.is_not(None),
            func.lower(func.trim(Job.location)) == normalized_location.lower(),
        )
        .group_by(Skill.id, Skill.name, Skill.category)
        .order_by(
            func.count(func.distinct(Job.id)).desc(),
            Skill.name.asc(),
        )
        .limit(limit)
    )
    rows = db.execute(skills_stmt).all()
    skills = [
        SkillLocationCount(
            skill=row.skill,
            category=row.category,
            job_count=row.job_count,
        )
        for row in rows
    ]

    return SkillsByLocationResponse(
        location=normalized_location,
        total_skills=total_skills,
        skills=skills,
    )



