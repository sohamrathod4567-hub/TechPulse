"""
Job Data Collector Module for TechPulse.

This module is responsible for the Extraction (E) phase of the TechPulse ETL pipeline.
It connects to the Arbeitnow public Job Board API, retrieves raw job postings,
extracts the relevant fields, structures them into a Pandas DataFrame, and saves
the resulting dataset as a CSV file in the project's raw data directory.

Usage from command line:
    python src/techpulse/etl/job_collector.py
    or
    python -m src.techpulse.etl.job_collector
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path & Environment Setup
# ---------------------------------------------------------------------------
# Resolve project paths dynamically using pathlib (no hardcoded absolute paths)
# File location: <PROJECT_ROOT>/src/techpulse/etl/job_collector.py
# parents[0] -> .../src/techpulse/etl
# parents[1] -> .../src/techpulse
# parents[2] -> .../src
# parents[3] -> .../TechPulse (Project Root)
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
SRC_DIR = PROJECT_ROOT / "src"

# Ensure 'src' is in sys.path so the module can be run directly or imported cleanly
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Load environment variables from .env file if one exists
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("techpulse.etl.job_collector")

# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------
ARBEITNOW_API_URL = os.getenv(
    "ARBEITNOW_API_URL", "https://www.arbeitnow.com/api/job-board-api"
)
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT", "15"))
DEFAULT_RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

# The 10 required fields to extract from each job listing
REQUIRED_FIELDS: List[str] = [
    "slug",
    "company_name",
    "title",
    "description",
    "remote",
    "url",
    "tags",
    "job_types",
    "location",
    "created_at",
]


class JobCollector:
    """
    Handles fetching, extracting, and persisting job listings from the Arbeitnow API.
    
    Attributes:
        api_url (str): The target REST API endpoint URL.
        output_dir (Path): The directory path where collected CSV files will be stored.
        timeout (int): Network request timeout in seconds.
    """

    def __init__(
        self,
        api_url: str = ARBEITNOW_API_URL,
        output_dir: Optional[Path] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Initialize the JobCollector with API settings and destination directory.

        Args:
            api_url: The API URL endpoint. Defaults to Arbeitnow job board API.
            output_dir: Directory where the raw CSV will be saved. Defaults to data/raw/.
            timeout: Timeout duration in seconds for HTTP requests. Defaults to 15s.
        """
        self.api_url = api_url
        self.output_dir = output_dir or DEFAULT_RAW_DATA_DIR
        self.timeout = timeout
        self.headers = {
            "User-Agent": "TechPulse/0.1.0 (Job Market Intelligence Platform; Python/3.14)",
            "Accept": "application/json",
        }

    def fetch_jobs(self, page: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch raw job listings from the Arbeitnow public API.

        Handles network errors, HTTP error codes, and JSON decoding issues.

        Args:
            page: Optional page number to fetch for paginated endpoints.

        Returns:
            List[Dict[str, Any]]: A list of raw job dictionaries returned by the API.

        Raises:
            requests.exceptions.RequestException: If an unrecoverable network or HTTP error occurs.
            ValueError: If the response is not valid JSON or lacks the expected data structure.
        """
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page

        logger.info("Requesting job listings from: %s (params: %s)", self.api_url, params)

        try:
            response = requests.get(
                self.api_url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )
            # Raise an HTTPError for 4xx or 5xx client/server status codes
            response.raise_for_status()

        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out after %d seconds: %s", self.timeout, exc)
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network connection failed while reaching %s: %s", self.api_url, exc)
            raise
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "HTTP error response received: %s (Status code: %s)",
                exc,
                getattr(exc.response, "status_code", "Unknown"),
            )
            raise
        except requests.exceptions.RequestException as exc:
            logger.error("An unexpected network error occurred: %s", exc)
            raise

        # Parse JSON payload
        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to decode response as JSON: %s", exc)
            raise ValueError(f"Invalid JSON returned by API: {exc}") from exc

        # Validate response structure
        if not isinstance(payload, dict) or "data" not in payload:
            logger.error(
                "Unexpected API response format. Missing top-level 'data' key. Keys: %s",
                list(payload.keys()) if isinstance(payload, dict) else type(payload),
            )
            raise ValueError("API response JSON is missing expected 'data' key.")

        raw_jobs = payload.get("data", [])
        if not isinstance(raw_jobs, list):
            logger.error("'data' field in API response is not a list: %s", type(raw_jobs))
            raise ValueError("Expected 'data' field to be a list of job listings.")

        logger.info("Successfully received %d job listings from API.", len(raw_jobs))
        return raw_jobs

    def extract_fields(self, raw_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract the 10 target fields from each raw job listing dictionary.

        Target fields:
            1. slug
            2. company_name
            3. title
            4. description
            5. remote
            6. url
            7. tags
            8. job_types
            9. location
            10. created_at

        Args:
            raw_jobs: List of raw job dictionaries.

        Returns:
            List[Dict[str, Any]]: List of normalized dictionaries containing only the 10 fields.
        """
        logger.info("Extracting %d required fields from %d raw jobs...", len(REQUIRED_FIELDS), len(raw_jobs))
        extracted_jobs: List[Dict[str, Any]] = []

        for index, job in enumerate(raw_jobs):
            if not isinstance(job, dict):
                logger.warning("Skipping job item at index %d because it is not a dictionary.", index)
                continue

            record: Dict[str, Any] = {
                "slug": job.get("slug"),
                "company_name": job.get("company_name"),
                "title": job.get("title"),
                "description": job.get("description"),
                "remote": job.get("remote"),
                "url": job.get("url"),
                "tags": job.get("tags") if job.get("tags") is not None else [],
                "job_types": job.get("job_types") if job.get("job_types") is not None else [],
                "location": job.get("location"),
                "created_at": job.get("created_at"),
            }
            extracted_jobs.append(record)

        logger.info(
            "Successfully extracted %d job records with clean field schemas.",
            len(extracted_jobs),
        )
        return extracted_jobs

    def to_dataframe(self, jobs_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Convert extracted job dictionaries into a Pandas DataFrame.

        Enforces column order according to REQUIRED_FIELDS.

        Args:
            jobs_data: List of extracted job dictionaries.

        Returns:
            pd.DataFrame: Pandas DataFrame with the structured job data.
        """
        logger.info("Converting %d records into a Pandas DataFrame...", len(jobs_data))
        df = pd.DataFrame(jobs_data, columns=REQUIRED_FIELDS)
        logger.info(
            "DataFrame created successfully with shape: %s (Rows: %d, Columns: %d)",
            df.shape,
            len(df),
            len(df.columns),
        )
        return df

    def save_to_csv(
        self,
        df: pd.DataFrame,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Save the DataFrame as a CSV file in data/raw/.

        To prevent accidentally overwriting previous data collections, a timestamped
        filename is generated automatically (e.g., 'jobs_raw_YYYYMMDD_HHMMSS.csv')
        unless a specific filename is given. If an explicit filename already exists,
        a timestamp is appended to avoid destructive overwrites.

        Args:
            df: The DataFrame containing job listings.
            filename: Optional custom filename. Defaults to a timestamped name.

        Returns:
            Path: The resolved path to the newly written CSV file.
        """
        # Automatically ensure destination directory exists (Requirement 6)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured output directory exists: %s", self.output_dir)

        # Generate a sensible timestamped filename to prevent data overwrite
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not filename:
            target_filename = f"jobs_raw_{timestamp_str}.csv"
        else:
            target_filename = filename

        destination_path = self.output_dir / target_filename

        # If a custom filename was specified but already exists, protect historical data
        if destination_path.exists():
            stem = destination_path.stem
            suffix = destination_path.suffix
            protected_filename = f"{stem}_{timestamp_str}{suffix}"
            destination_path = self.output_dir / protected_filename
            logger.warning(
                "Target file already existed. Protected existing data by writing to: %s",
                destination_path.name,
            )

        logger.info("Exporting DataFrame to CSV: %s", destination_path)
        # Use index=False so the DataFrame integer index is not stored as an extra column
        df.to_csv(destination_path, index=False, encoding="utf-8")

        file_size_bytes = destination_path.stat().st_size
        logger.info(
            "CSV export completed. File size: %d bytes (~%.2f KB) at %s",
            file_size_bytes,
            file_size_bytes / 1024.0,
            destination_path,
        )
        return destination_path

    def run(self, filename: Optional[str] = None) -> Path:
        """
        Execute the complete collection workflow end-to-end:
            1. Fetch listings from the Arbeitnow API.
            2. Extract the 10 target fields.
            3. Convert records into a Pandas DataFrame.
            4. Persist the DataFrame to CSV in data/raw/.

        Args:
            filename: Optional custom CSV filename.

        Returns:
            Path: Path to the generated CSV file.
        """
        logger.info("=== Starting TechPulse Job Data Collection ===")
        raw_jobs = self.fetch_jobs()
        extracted_jobs = self.extract_fields(raw_jobs)
        df = self.to_dataframe(extracted_jobs)
        saved_file = self.save_to_csv(df, filename=filename)
        logger.info("=== TechPulse Job Data Collection Finished Successfully ===")
        return saved_file


def collect_jobs(
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
) -> Path:
    """
    Convenience function to run the Arbeitnow job collection pipeline.

    Args:
        output_dir: Optional custom directory to save CSV. Defaults to data/raw/.
        filename: Optional custom filename for the CSV.

    Returns:
        Path: Path to the created CSV file.
    """
    collector = JobCollector(output_dir=output_dir)
    return collector.run(filename=filename)


def main() -> None:
    """CLI entrypoint for executing the job collector script."""
    try:
        csv_file = collect_jobs()
        print("\n" + "=" * 70)
        print("TECHPULSE - JOB COLLECTION COMPLETE")
        print("=" * 70)
        print(f"Output File : {csv_file}")
        print(f"File Size   : {csv_file.stat().st_size:,} bytes")
        print("=" * 70)
    except Exception as exc:
        logger.exception("Job collection pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
