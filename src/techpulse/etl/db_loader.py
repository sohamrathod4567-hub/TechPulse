"""
Database Loading Module for TechPulse.

This module is responsible for the Loading (L) phase of the TechPulse ETL pipeline.
It reads the latest processed CSV dataset from data/processed/, parses and validates
fields into types compatible with the SQLAlchemy Job model, and persists records
into PostgreSQL using transactions and conflict handling.

Usage from command line:
    python -m src.techpulse.etl.db_loader
    or
    python src/techpulse/etl/db_loader.py

Programmatic usage:
    from techpulse.etl.db_loader import DatabaseLoader, load_jobs
    results = load_jobs()
"""

from __future__ import annotations

import ast
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import Connection, Engine, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

# ---------------------------------------------------------------------------
# Path & Environment Setup
# ---------------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import database connection and models
from techpulse.database.connection import get_engine
from techpulse.database.models import Job

DEFAULT_PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("techpulse.etl.db_loader")


# ---------------------------------------------------------------------------
# Data Conversion and Validation Helpers
# ---------------------------------------------------------------------------

def parse_list_field(value: Any) -> List[str]:
    """
    Parse tags and job_types from strings/literals into Python lists of strings.

    Handles:
        - Python list objects: passed through.
        - String list representations: e.g. "['Python', 'FastAPI']" or '["AI"]'.
        - Comma-delimited strings: e.g. "Python, SQL".
        - None, NaN, empty strings: returns empty list [].

    Args:
        value: Raw value from DataFrame or dictionary.

    Returns:
        List[str]: Clean list of string items.
    """
    if isinstance(value, list):
        return [str(item).strip() for item in value if item is not None and str(item).strip()]

    if value is None or pd.isna(value):
        return []

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned in ("[]", "{}"):
            return []

        # 1. Try ast.literal_eval for Python list syntax (single quotes)
        try:
            parsed = ast.literal_eval(cleaned)
            if isinstance(parsed, (list, tuple, set)):
                return [str(item).strip() for item in parsed if item is not None and str(item).strip()]
        except (ValueError, SyntaxError):
            pass

        # 2. Try json.loads for standard JSON syntax (double quotes)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if item is not None and str(item).strip()]
        except Exception:
            pass

        # 3. Fallback: treat as comma-separated values
        items = [part.strip().strip("'\"") for part in cleaned.split(",")]
        return [item for item in items if item]

    return []


def parse_datetime_field(value: Any) -> Optional[datetime]:
    """
    Convert raw timestamp values into timezone-aware UTC datetime objects.

    Handles:
        - Existing datetime instances: normalizes to UTC.
        - Numeric Unix timestamps: converted to UTC datetime.
        - Standard date/time strings: formatted as 'YYYY-MM-DD HH:MM:SS' or ISO.
        - Null, NaN, or invalid values: returns None.

    Args:
        value: Raw timestamp value.

    Returns:
        Optional[datetime]: Timezone-aware UTC datetime or None.
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # Numeric Unix timestamps (int or float)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None

    if isinstance(value, str):
        val_str = value.strip()
        if not val_str:
            return None

        # Check if string is a numeric timestamp
        try:
            ts_num = float(val_str)
            return datetime.fromtimestamp(ts_num, tz=timezone.utc)
        except ValueError:
            pass

        # Try common date/time formats
        known_formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        )
        for fmt in known_formats:
            try:
                dt = datetime.strptime(val_str, fmt)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                pass

        # Fallback to dateutil parser if available
        try:
            import dateutil.parser
            parsed_dt = dateutil.parser.parse(val_str)
            if parsed_dt.tzinfo is None:
                return parsed_dt.replace(tzinfo=timezone.utc)
            return parsed_dt.astimezone(timezone.utc)
        except Exception:
            return None

    return None


def validate_and_convert_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate mandatory fields and convert all data types for a single job listing.

    Required fields: slug, title, company_name, description, url.
    Optional / nullable: location, created_at.

    Args:
        row: Raw dictionary representing a single job record.

    Returns:
        Optional[Dict[str, Any]]: Cleaned dictionary ready for insertion, or None if invalid.
    """
    slug = str(row.get("slug") or "").strip()
    title = str(row.get("title") or "").strip()
    company_name = str(row.get("company_name") or "").strip()
    description = str(row.get("description") or "").strip()
    url = str(row.get("url") or "").strip()

    # Validate essential non-empty fields
    if not (slug and title and company_name and description and url):
        return None

    # Parse boolean remote
    remote_raw = row.get("remote")
    if isinstance(remote_raw, bool):
        remote = remote_raw
    elif isinstance(remote_raw, (int, float)):
        remote = bool(remote_raw)
    elif isinstance(remote_raw, str):
        remote = remote_raw.strip().lower() in ("true", "1", "yes", "t", "y")
    else:
        remote = False

    # Handle nullable location
    location_raw = row.get("location")
    if location_raw is None or pd.isna(location_raw):
        location = None
    else:
        loc_clean = str(location_raw).strip()
        location = loc_clean if loc_clean else None

    # Parse tags, job_types, and created_at
    tags = parse_list_field(row.get("tags"))
    job_types = parse_list_field(row.get("job_types"))
    created_at = parse_datetime_field(row.get("created_at"))

    return {
        "slug": slug,
        "title": title,
        "company_name": company_name,
        "description": description,
        "location": location,
        "remote": remote,
        "url": url,
        "tags": tags,
        "job_types": job_types,
        "created_at": created_at,
    }


def get_latest_processed_file(processed_dir: Optional[Path] = None) -> Path:
    """
    Locate the newest processed CSV file in data/processed/.

    Args:
        processed_dir: Directory containing processed CSV files. Defaults to data/processed/.

    Returns:
        Path: Path to the most recent CSV file.

    Raises:
        FileNotFoundError: If the directory does not exist or contains no CSV files.
    """
    directory = processed_dir or DEFAULT_PROCESSED_DATA_DIR
    if not directory.exists():
        raise FileNotFoundError(f"Processed data directory does not exist: {directory}")

    csv_files = list(directory.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No processed CSV files found in: {directory}")

    latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
    logger.info("Identified latest processed CSV file: %s", latest_file.name)
    return latest_file


# ---------------------------------------------------------------------------
# Database Loader Class
# ---------------------------------------------------------------------------

class DatabaseLoader:
    """
    Handles loading processed job market data from CSV into PostgreSQL.

    Attributes:
        engine (Engine): SQLAlchemy Engine connection pool.
        processed_dir (Path): Source directory for processed CSV files.
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        processed_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize the DatabaseLoader with an engine and source directory.

        Args:
            engine: Optional SQLAlchemy Engine. Defaults to get_engine().
            processed_dir: Optional custom path to processed data directory.
        """
        self.engine = engine or get_engine()
        self.processed_dir = processed_dir or DEFAULT_PROCESSED_DATA_DIR

    def read_csv(self, file_path: Path) -> pd.DataFrame:
        """
        Read the processed CSV file into a Pandas DataFrame.

        Args:
            file_path: Path to the CSV file.

        Returns:
            pd.DataFrame: Loaded dataset.
        """
        logger.info("Reading processed data from: %s", file_path)
        df = pd.read_csv(file_path)
        logger.info("Loaded %d rows from CSV.", len(df))
        return df

    def prepare_records(self, df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], int]:
        """
        Convert DataFrame rows into validated dictionaries and deduplicate within batch.

        Args:
            df: Input DataFrame.

        Returns:
            Tuple[List[Dict[str, Any]], int]: List of valid records and count of invalid rows.
        """
        valid_records: List[Dict[str, Any]] = []
        seen_slugs: set[str] = set()
        failed_count = 0
        in_batch_duplicates = 0

        for _, row in df.iterrows():
            record = validate_and_convert_row(row.to_dict())
            if record is None:
                failed_count += 1
                continue

            slug = record["slug"]
            if slug in seen_slugs:
                # Deduplicate within the same batch to prevent PostgreSQL ON CONFLICT error
                in_batch_duplicates += 1
                continue

            seen_slugs.add(slug)
            valid_records.append(record)

        if failed_count > 0:
            logger.warning("Validation failed for %d row(s). These rows will be skipped.", failed_count)
        if in_batch_duplicates > 0:
            logger.info("Deduplicated %d duplicate slug(s) within the input batch.", in_batch_duplicates)

        return valid_records, failed_count

    def insert_records(
        self,
        records: List[Dict[str, Any]],
        conflict_strategy: str = "update",
        connection: Optional[Connection] = None,
    ) -> Dict[str, int]:
        """
        Insert records into PostgreSQL using transactions and ON CONFLICT handling.

        Supported conflict strategies:
            - 'update': (Upsert) If slug exists, update mutable fields and set updated_at.
            - 'skip': If slug exists, do nothing (skip).

        Args:
            records: Validated list of job dictionaries.
            conflict_strategy: 'update' (default) or 'skip'.
            connection: Optional existing database Connection. If None, initiates an
                        atomic transaction via self.engine.begin().

        Returns:
            Dict[str, int]: Counts for 'inserted', 'updated', and 'skipped'.
        """
        if not records:
            logger.info("No records to insert.")
            return {"inserted": 0, "updated": 0, "skipped": 0}

        def _execute(conn: Connection) -> Dict[str, int]:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0

            if conflict_strategy == "update":
                # Construct PostgreSQL ON CONFLICT (slug) DO UPDATE
                stmt = pg_insert(Job).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["slug"],
                    set_={
                        "title": stmt.excluded.title,
                        "company_name": stmt.excluded.company_name,
                        "description": stmt.excluded.description,
                        "location": stmt.excluded.location,
                        "remote": stmt.excluded.remote,
                        "url": stmt.excluded.url,
                        "tags": stmt.excluded.tags,
                        "job_types": stmt.excluded.job_types,
                        "created_at": stmt.excluded.created_at,
                        "updated_at": func.now(),
                    },
                ).returning(Job.id, Job.slug, text("(xmax = 0) AS is_inserted"))

                results = conn.execute(stmt).fetchall()
                for row in results:
                    is_inserted = row[2]
                    if is_inserted:
                        inserted_count += 1
                    else:
                        updated_count += 1

            elif conflict_strategy == "skip":
                # Construct PostgreSQL ON CONFLICT (slug) DO NOTHING
                stmt = pg_insert(Job).values(records)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["slug"]
                ).returning(Job.id, Job.slug)

                results = conn.execute(stmt).fetchall()
                inserted_count = len(results)
                skipped_count = len(records) - inserted_count

            else:
                raise ValueError(
                    f"Unknown conflict strategy '{conflict_strategy}'. Expected 'update' or 'skip'."
                )

            logger.info(
                "Database operation complete. Inserted: %d, Updated: %d, Skipped: %d",
                inserted_count,
                updated_count,
                skipped_count,
            )
            return {
                "inserted": inserted_count,
                "updated": updated_count,
                "skipped": skipped_count,
            }

        logger.info(
            "Executing database load for %d records (conflict strategy: '%s')...",
            len(records),
            conflict_strategy,
        )

        if connection is not None:
            return _execute(connection)

        # Atomic transaction: automatically commits on success, rolls back on error
        with self.engine.begin() as conn:
            return _execute(conn)

    def load_csv(
        self,
        file_path: Optional[Path] = None,
        conflict_strategy: str = "update",
    ) -> Dict[str, Any]:
        """
        Execute full database loading pipeline from a processed CSV file.

        Args:
            file_path: Optional explicit CSV path. If None, finds latest in data/processed/.
            conflict_strategy: Conflict resolution ('update' or 'skip'). Defaults to 'update'.

        Returns:
            Dict[str, Any]: Detailed metrics of the loading operation.
        """
        csv_file = file_path or get_latest_processed_file(self.processed_dir)
        logger.info("=== Starting TechPulse Database Loading Pipeline ===")
        logger.info("Source file: %s", csv_file)

        df = self.read_csv(csv_file)
        total_records = len(df)

        valid_records, failed_count = self.prepare_records(df)
        counts = self.insert_records(valid_records, conflict_strategy=conflict_strategy)

        metrics = {
            "total_records": total_records,
            "valid_records": len(valid_records),
            "inserted": counts["inserted"],
            "updated": counts["updated"],
            "skipped": counts["skipped"],
            "failed": failed_count,
            "file_path": str(csv_file),
            "conflict_strategy": conflict_strategy,
        }

        logger.info(
            "=== TechPulse Database Loading Completed ===\n"
            "Total: %d | Inserted: %d | Updated: %d | Skipped: %d | Failed: %d",
            total_records,
            metrics["inserted"],
            metrics["updated"],
            metrics["skipped"],
            metrics["failed"],
        )
        return metrics


def load_jobs(
    file_path: Optional[Path] = None,
    engine: Optional[Engine] = None,
    conflict_strategy: str = "update",
) -> Dict[str, Any]:
    """
    Convenience function to run the database loading pipeline.

    Args:
        file_path: Optional path to processed CSV. Defaults to newest in data/processed/.
        engine: Optional SQLAlchemy Engine. Defaults to default PostgreSQL engine.
        conflict_strategy: 'update' (upsert) or 'skip'. Defaults to 'update'.

    Returns:
        Dict[str, Any]: Summary metrics of the operation.
    """
    loader = DatabaseLoader(engine=engine)
    return loader.load_csv(file_path=file_path, conflict_strategy=conflict_strategy)


def main() -> None:
    """CLI entrypoint for running the database loader."""
    try:
        metrics = load_jobs()
        print("\n" + "=" * 70)
        print("TECHPULSE - DATABASE LOADING COMPLETE")
        print("=" * 70)
        print(f"Source File       : {metrics['file_path']}")
        print(f"Conflict Strategy : {metrics['conflict_strategy']}")
        print(f"Total Rows Read   : {metrics['total_records']}")
        print(f"Valid Rows        : {metrics['valid_records']}")
        print("-" * 70)
        print(f"Jobs Inserted     : {metrics['inserted']}")
        print(f"Jobs Updated      : {metrics['updated']}")
        print(f"Jobs Skipped      : {metrics['skipped']}")
        print(f"Jobs Failed       : {metrics['failed']}")
        print("=" * 70 + "\n")
    except Exception as exc:
        logger.exception("Database loading pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
