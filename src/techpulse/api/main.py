"""
Main FastAPI Application for TechPulse.

This module initializes the FastAPI backend application for the
TechPulse job market intelligence platform.
"""

from fastapi import FastAPI

# Instantiate the FastAPI application with metadata
app = FastAPI(
    title="TechPulse API",
    description="Job market intelligence platform",
    version="1.0.0",
)
