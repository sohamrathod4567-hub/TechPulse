"""
Main FastAPI Application for TechPulse.

This module initializes the FastAPI backend application for the
TechPulse job market intelligence platform and registers core system endpoints.
"""

from typing import Dict

from fastapi import FastAPI, status

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
