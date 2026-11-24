"""
Unit tests for the TechPulse API health endpoint.
"""

import sys
import unittest
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from techpulse.api.main import app


class TestHealthEndpoint(unittest.TestCase):
    """Test suite for GET /health endpoint."""

    @classmethod
    def setUpClass(cls):
        """Initialize FastAPI TestClient."""
        cls.client = TestClient(app)

    def test_health_check_status_code(self):
        """Verify that GET /health returns HTTP 200 OK."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_check_payload(self):
        """Verify that GET /health returns the exact expected JSON response."""
        response = self.client.get("/health")
        expected_payload = {
            "status": "healthy",
            "application": "TechPulse API",
        }
        self.assertEqual(response.json(), expected_payload)

    def test_health_check_content_type(self):
        """Verify that response header has application/json content type."""
        response = self.client.get("/health")
        self.assertIn("application/json", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
