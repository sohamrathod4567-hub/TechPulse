"""
Unit tests for TechPulse Frontend API Client (frontend/api/client.py).

Tests configuration resolution, HTTP request handling, connection and timeout errors,
HTTP status code handling, JSON parsing errors, health checks, and specific API methods.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src and project root are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
for p in (str(PROJECT_ROOT), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import requests
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout as ReqTimeout

from frontend.api.client import (
    APIConnectionError,
    APIResponseError,
    TechPulseAPIError,
    TechPulseClient,
    get_api_client,
)
from frontend.config import (
    DEFAULT_API_BASE_URL,
    TECHPULSE_API_URL_ENV,
    get_api_base_url,
    get_request_timeout,
)


class TestFrontendApiConfig(unittest.TestCase):
    """Test suite for frontend configuration helpers."""

    def test_default_api_base_url(self):
        """Verify default URL is returned when TECHPULSE_API_URL is unset."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_api_base_url(), DEFAULT_API_BASE_URL)

    def test_custom_api_base_url_from_env(self):
        """Verify environment variable override and trailing slash stripping."""
        custom_url = "http://api.production.internal:8080/ "
        with patch.dict(os.environ, {TECHPULSE_API_URL_ENV: custom_url}):
            self.assertEqual(get_api_base_url(), "http://api.production.internal:8080")

    def test_get_request_timeout_returns_float(self):
        """Verify request timeout returns expected float."""
        self.assertIsInstance(get_request_timeout(), float)
        self.assertGreater(get_request_timeout(), 0.0)


class TestTechPulseClient(unittest.TestCase):
    """Test suite for TechPulseClient HTTP interactions and error handling."""

    def setUp(self):
        self.client = TechPulseClient(base_url="http://testbackend:8000", timeout=2.0)

    def test_get_successful_json(self):
        """Verify successful GET request parses and returns JSON data."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "service": "TechPulse"}

        with patch.object(self.client._session, "get", return_value=mock_response) as mock_get:
            result = self.client.get("/health")
            self.assertEqual(result, {"status": "healthy", "service": "TechPulse"})
            mock_get.assert_called_once_with(
                "http://testbackend:8000/health",
                params=None,
                timeout=2.0,
            )

    def test_get_with_query_params_and_none_filtering(self):
        """Verify query parameters are passed and None values are omitted."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.json.return_value = {"total": 5}

        with patch.object(self.client._session, "get", return_value=mock_response) as mock_get:
            params = {"limit": 10, "empty_param": None}
            self.client.get("/analytics/top-skills", params=params)
            mock_get.assert_called_once_with(
                "http://testbackend:8000/analytics/top-skills",
                params={"limit": 10},
                timeout=2.0,
            )

    def test_get_connection_error_raises_api_connection_error(self):
        """Verify network ConnectionError is caught and re-raised as APIConnectionError."""
        with patch.object(
            self.client._session,
            "get",
            side_effect=ReqConnectionError("Connection refused"),
        ):
            with self.assertRaises(APIConnectionError) as ctx:
                self.client.get("/health")
            self.assertIn("Unable to connect to the TechPulse backend", str(ctx.exception))

    def test_get_timeout_raises_api_connection_error(self):
        """Verify request Timeout is caught and re-raised as APIConnectionError."""
        with patch.object(
            self.client._session,
            "get",
            side_effect=ReqTimeout("Timed out"),
        ):
            with self.assertRaises(APIConnectionError) as ctx:
                self.client.get("/health")
            self.assertIn("timed out after 2.0s", str(ctx.exception))

    def test_get_http_404_raises_api_response_error(self):
        """Verify 404 response raises APIResponseError with extracted message."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.json.return_value = {"detail": "Job not found"}

        with patch.object(self.client._session, "get", return_value=mock_response):
            with self.assertRaises(APIResponseError) as ctx:
                self.client.get("/jobs/99999")
            self.assertEqual(ctx.exception.status_code, 404)
            self.assertIn("Job not found", str(ctx.exception))

    def test_get_http_422_validation_error_format(self):
        """Verify 422 validation error message list is parsed into clean detail string."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = False
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [{"loc": ["query", "limit"], "msg": "Input should be less than or equal to 50"}]
        }

        with patch.object(self.client._session, "get", return_value=mock_response):
            with self.assertRaises(APIResponseError) as ctx:
                self.client.get("/analytics/top-skills", params={"limit": 100})
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertIn("Input should be less than or equal to 50", str(ctx.exception))

    def test_get_invalid_json_raises_api_response_error(self):
        """Verify non-JSON response payload raises APIResponseError."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(self.client._session, "get", return_value=mock_response):
            with self.assertRaises(APIResponseError) as ctx:
                self.client.get("/health")
            self.assertIn("Invalid data received", str(ctx.exception))

    def test_check_health_true(self):
        """Verify check_health returns True when status is healthy."""
        with patch.object(self.client, "get_health", return_value={"status": "healthy"}):
            self.assertTrue(self.client.check_health())

    def test_check_health_false_on_unhealthy_or_exception(self):
        """Verify check_health returns False when status is not healthy or connection fails."""
        with patch.object(self.client, "get_health", return_value={"status": "degraded"}):
            self.assertFalse(self.client.check_health())

        with patch.object(self.client, "get_health", side_effect=APIConnectionError("offline")):
            self.assertFalse(self.client.check_health())

    def test_specific_analytics_methods(self):
        """Verify all specific analytics and job methods invoke get with expected paths."""
        with patch.object(self.client, "get") as mock_get:
            self.client.get_analytics_overview()
            mock_get.assert_called_with("/analytics/overview")

            self.client.get_top_titles(limit=5)
            mock_get.assert_called_with("/analytics/top-titles", params={"limit": 5})

            self.client.get_top_companies(limit=5)
            mock_get.assert_called_with("/analytics/top-companies", params={"limit": 5})

            self.client.get_locations(limit=5)
            mock_get.assert_called_with("/analytics/locations", params={"limit": 5})

            self.client.get_remote_distribution()
            mock_get.assert_called_with("/analytics/remote-distribution")

            self.client.get_top_skills(limit=5)
            mock_get.assert_called_with("/analytics/top-skills", params={"limit": 5})

            self.client.get_skill_categories(limit=5)
            mock_get.assert_called_with("/analytics/skill-categories", params={"limit": 5})

            self.client.get_skills_by_location(location="Paris", limit=5)
            mock_get.assert_called_with("/analytics/skills-by-location", params={"location": "Paris", "limit": 5})

            self.client.get_jobs(skip=10, limit=20)
            mock_get.assert_called_with("/jobs", params={"skip": 10, "limit": 20})

            self.client.get_job_by_id(job_id=42)
            mock_get.assert_called_with("/jobs/42")

    def test_get_api_client_singleton(self):
        """Verify get_api_client returns a valid TechPulseClient instance."""
        client = get_api_client()
        self.assertIsInstance(client, TechPulseClient)


if __name__ == "__main__":
    unittest.main()
