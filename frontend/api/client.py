"""
HTTP API Client for TechPulse Frontend.

Provides a robust, centralized client to interface with the TechPulse FastAPI backend.
Handles request timeouts, connection failures, HTTP status codes, and JSON parsing
errors gracefully with custom exception hierarchies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from frontend.config import get_api_base_url, get_request_timeout

logger = logging.getLogger("techpulse.frontend.api")


class TechPulseAPIError(Exception):
    """Base exception for all TechPulse API client errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class APIConnectionError(TechPulseAPIError):
    """Raised when the client cannot establish a connection to the backend service."""

    pass


class APIResponseError(TechPulseAPIError):
    """Raised when the backend returns a non-2xx HTTP status code or malformed response."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TechPulseClient:
    """
    Centralized HTTP client for communicating with the TechPulse FastAPI service.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Initialize the API client.

        Args:
            base_url: Optional override for the backend base URL. Defaults to configuration.
            timeout: Optional override for request timeout in seconds. Defaults to configuration.
        """
        self.base_url = (base_url or get_api_base_url()).rstrip("/")
        self.timeout = timeout if timeout is not None else get_request_timeout()
        self._session = requests.Session()

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP GET request against the specified backend endpoint.

        Args:
            endpoint: Relative API path (e.g. '/health', '/analytics/overview').
            params: Optional query parameters dictionary.

        Returns:
            Dict[str, Any]: Parsed JSON response dictionary.

        Raises:
            APIConnectionError: If connection fails or times out.
            APIResponseError: If backend responds with an error code or invalid JSON.
        """
        clean_endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{clean_endpoint}"

        # Clean None values from query parameters
        clean_params = {k: v for k, v in params.items() if v is not None} if params else None

        try:
            response = self._session.get(
                url,
                params=clean_params,
                timeout=self.timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection failed to %s: %s", url, exc)
            raise APIConnectionError(
                f"Unable to connect to the TechPulse backend at {self.base_url}. "
                "Please verify that the FastAPI server is running."
            ) from exc
        except requests.exceptions.Timeout as exc:
            logger.error("Request to %s timed out after %.1fs: %s", url, self.timeout, exc)
            raise APIConnectionError(
                f"Request to TechPulse API timed out after {self.timeout}s. "
                "The server may be overloaded."
            ) from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Network request failed for %s: %s", url, exc)
            raise APIConnectionError(f"Network error communicating with API: {exc}") from exc

        # Handle non-success HTTP status codes
        if not response.ok:
            status_code = response.status_code
            detail = self._extract_error_detail(response)
            logger.warning("HTTP %d from %s: %s", status_code, url, detail)
            raise APIResponseError(
                f"API error ({status_code}): {detail}",
                status_code=status_code,
            )

        # Parse JSON payload
        try:
            return response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            logger.error("Invalid JSON response from %s: %s", url, exc)
            raise APIResponseError(
                "Invalid data received from TechPulse API. Expected JSON payload.",
                status_code=response.status_code,
            ) from exc

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract a readable error message from response JSON or status text."""
        try:
            data = response.json()
            if isinstance(data, dict):
                detail = data.get("detail")
                if isinstance(detail, list) and detail:
                    # FastAPI validation error format
                    first_err = detail[0]
                    if isinstance(first_err, dict) and "msg" in first_err:
                        return str(first_err["msg"])
                elif detail:
                    return str(detail)
        except Exception:
            pass

        return response.reason or f"HTTP {response.status_code}"

    # -----------------------------------------------------------------------
    # System and Health Check Methods
    # -----------------------------------------------------------------------

    def check_health(self) -> bool:
        """
        Check if the FastAPI backend service is reachable and healthy.

        Returns:
            bool: True if backend responds 200 OK with healthy status, False otherwise.
        """
        try:
            data = self.get_health()
            return data.get("status") == "healthy"
        except Exception:
            return False

    def get_health(self) -> Dict[str, Any]:
        """Retrieve backend service health status."""
        return self.get("/health")

    # -----------------------------------------------------------------------
    # Analytics Endpoints
    # -----------------------------------------------------------------------

    def get_analytics_overview(self) -> Dict[str, Any]:
        """Retrieve aggregate analytics overview."""
        return self.get("/analytics/overview")

    def get_top_titles(self, limit: int = 10) -> Dict[str, Any]:
        """Retrieve top job titles by posting frequency."""
        return self.get("/analytics/top-titles", params={"limit": limit})

    def get_top_companies(self, limit: int = 10) -> Dict[str, Any]:
        """Retrieve top hiring companies by posting frequency."""
        return self.get("/analytics/top-companies", params={"limit": limit})

    def get_locations(self, limit: int = 10) -> Dict[str, Any]:
        """Retrieve job posting frequency by location."""
        return self.get("/analytics/locations", params={"limit": limit})

    def get_remote_distribution(self) -> Dict[str, Any]:
        """Retrieve remote work distribution counts and percentages."""
        return self.get("/analytics/remote-distribution")

    def get_top_skills(self, limit: int = 10) -> Dict[str, Any]:
        """Retrieve top technical skills by job demand."""
        return self.get("/analytics/top-skills", params={"limit": limit})

    def get_skill_categories(self, limit: int = 10) -> Dict[str, Any]:
        """Retrieve skill metrics aggregated by taxonomy category."""
        return self.get("/analytics/skill-categories", params={"limit": limit})

    def get_skills_by_location(self, location: str, limit: int = 10) -> Dict[str, Any]:
        """Retrieve top skills demanded in a specific geographic location."""
        return self.get("/analytics/skills-by-location", params={"location": location, "limit": limit})

    # -----------------------------------------------------------------------
    # Job Listings Endpoints
    # -----------------------------------------------------------------------

    def get_jobs(self, skip: int = 0, limit: int = 20) -> Dict[str, Any]:
        """Retrieve paginated job listings."""
        return self.get("/jobs", params={"skip": skip, "limit": limit})

    def get_job_by_id(self, job_id: int) -> Dict[str, Any]:
        """Retrieve a specific job listing by its ID."""
        return self.get(f"/jobs/{job_id}")


# Reusable singleton client instance
_default_client: Optional[TechPulseClient] = None


def get_api_client() -> TechPulseClient:
    """
    Get or create the singleton TechPulse API client instance.

    Returns:
        TechPulseClient: Configured API client.
    """
    global _default_client
    if _default_client is None:
        _default_client = TechPulseClient()
    return _default_client
