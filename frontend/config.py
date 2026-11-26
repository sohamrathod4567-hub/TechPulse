"""
Frontend Configuration for TechPulse Dashboard.

Manages application settings, API endpoints, and environment variable overrides.
"""

from __future__ import annotations

import os

# Environment variable name for custom API base URL
TECHPULSE_API_URL_ENV = "TECHPULSE_API_URL"

# Default local backend URL
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"

# Default network timeout for API requests in seconds
DEFAULT_REQUEST_TIMEOUT = 5.0

# Application branding and layout constants
APP_TITLE = "TechPulse | Job Market Intelligence"
APP_SUBTITLE = "AI-Powered Technical Labor Market Analytics"


def get_api_base_url() -> str:
    """
    Retrieve the configured FastAPI backend base URL.

    Checks the TECHPULSE_API_URL environment variable first, falling back to
    DEFAULT_API_BASE_URL ('http://127.0.0.1:8000'). Normalizes the string by
    trimming whitespace and removing trailing slashes.

    Returns:
        str: Fully qualified API base URL without trailing slash.
    """
    raw_url = os.getenv(TECHPULSE_API_URL_ENV, DEFAULT_API_BASE_URL)
    return raw_url.strip().rstrip("/")


def get_request_timeout() -> float:
    """
    Retrieve the request timeout in seconds.

    Returns:
        float: Timeout duration.
    """
    return DEFAULT_REQUEST_TIMEOUT
