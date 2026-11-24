"""
Data Cleaning and Transformation Module for TechPulse.

This module is responsible for the Transformation (T) phase of the TechPulse ETL pipeline.
It reads the latest raw job listings CSV file from data/raw/, applies structured cleaning
and normalization operations using Pandas, and saves the transformed dataset into data/processed/.

Pipeline stages:
    Raw CSV -> Load Data -> Remove Duplicates -> Handle Missing Values ->
    Clean HTML -> Convert Dates -> Standardise Text -> Validate -> Save Processed CSV

Usage from command line:
    python src/techpulse/etl/data_cleaner.py
    or
    python -m src.techpulse.etl.data_cleaner
"""

from __future__ import annotations

import html
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Path & Environment Setup
# ---------------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[3]
SRC_DIR = PROJECT_ROOT / "src"

# Ensure 'src' is in sys.path so the module can be run directly or imported cleanly
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("techpulse.etl.data_cleaner")


# ---------------------------------------------------------------------------
# Individual Modular Cleaning Functions
# ---------------------------------------------------------------------------

def get_latest_raw_file(raw_dir: Optional[Path] = None) -> Path:
    """
    Locate the most recent raw CSV file in the raw data directory.

    Args:
        raw_dir: Directory containing raw CSV files. Defaults to data/raw/.

    Returns:
        Path: Absolute path to the latest raw CSV file.

    Raises:
        FileNotFoundError: If the directory does not exist or contains no CSV files.
    """
    directory = raw_dir or DEFAULT_RAW_DATA_DIR
    if not directory.exists():
        raise FileNotFoundError(f"Raw data directory does not exist: {directory}")

    csv_files = list(directory.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in raw data directory: {directory}")

    # Select the file with the newest modification time
    latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
    logger.info("Found latest raw data file: %s (last modified: %s)",
                latest_file.name, datetime.fromtimestamp(latest_file.stat().st_mtime))
    return latest_file


def load_data(file_path: Path) -> pd.DataFrame:
    """
    Read a raw CSV file into a Pandas DataFrame.

    Args:
        file_path: Path to the CSV file to load.

    Returns:
        pd.DataFrame: Loaded DataFrame.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file is empty or cannot be parsed.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Target CSV file does not exist: {file_path}")

    logger.info("Loading raw dataset from: %s", file_path)
    try:
        df = pd.read_csv(file_path)
    except pd.errors.EmptyDataError as exc:
        logger.error("CSV file is empty: %s", file_path)
        raise ValueError(f"CSV file is empty: {file_path}") from exc
    except Exception as exc:
        logger.error("Failed to parse CSV file: %s (%s)", file_path, exc)
        raise

    logger.info("Raw dataset loaded successfully. Shape: %s (Rows: %d, Columns: %d)",
                df.shape, len(df), len(df.columns))
    return df


def remove_duplicates(df: pd.DataFrame, subset_col: str = "slug") -> pd.DataFrame:
    """
    Remove duplicate job postings based on the specified unique identifier.

    Args:
        df: Input DataFrame.
        subset_col: Column name to identify duplicates. Defaults to 'slug'.

    Returns:
        pd.DataFrame: Deduplicated DataFrame.
    """
    initial_count = len(df)
    if subset_col not in df.columns:
        logger.warning("Column '%s' not found for duplicate removal. Skipping.", subset_col)
        return df

    # Check for duplicates before dropping
    duplicate_count = df.duplicated(subset=[subset_col]).sum()
    if duplicate_count > 0:
        df_cleaned = df.drop_duplicates(subset=[subset_col], keep="first").copy()
        logger.info("Removed %d duplicate record(s) based on '%s'. Rows: %d -> %d",
                    duplicate_count, subset_col, initial_count, len(df_cleaned))
        return df_cleaned

    logger.info("No duplicate records found based on '%s'.", subset_col)
    return df.copy()


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing values according to business requirements:
    1. Remove records missing essential identifiers: 'title' or 'company_name'.
    2. Safely populate missing 'tags' and 'job_types' with empty list representations '[]'.

    Args:
        df: Input DataFrame.

    Returns:
        pd.DataFrame: DataFrame with missing values handled and invalid rows dropped.
    """
    initial_count = len(df)
    df_cleaned = df.copy()

    # Identify records missing essential fields (title or company_name)
    title_missing = df_cleaned["title"].isna() | (df_cleaned["title"].astype(str).str.strip() == "")
    company_missing = df_cleaned["company_name"].isna() | (df_cleaned["company_name"].astype(str).str.strip() == "")
    essential_missing_mask = title_missing | company_missing

    dropped_count = essential_missing_mask.sum()
    if dropped_count > 0:
        df_cleaned = df_cleaned[~essential_missing_mask].copy()
        logger.warning(
            "Dropped %d record(s) missing mandatory 'title' or 'company_name'. Rows: %d -> %d",
            dropped_count, initial_count, len(df_cleaned)
        )
    else:
        logger.info("All records contain mandatory 'title' and 'company_name'. None dropped.")

    # Safely handle missing tags and job_types
    if "tags" in df_cleaned.columns:
        tags_null_count = df_cleaned["tags"].isna().sum()
        df_cleaned["tags"] = df_cleaned["tags"].fillna("[]")
        df_cleaned["tags"] = df_cleaned["tags"].replace(r"^\s*$", "[]", regex=True)
        if tags_null_count > 0:
            logger.info("Safely filled %d missing 'tags' entries with '[]'.", tags_null_count)

    if "job_types" in df_cleaned.columns:
        jt_null_count = df_cleaned["job_types"].isna().sum()
        df_cleaned["job_types"] = df_cleaned["job_types"].fillna("[]")
        df_cleaned["job_types"] = df_cleaned["job_types"].replace(r"^\s*$", "[]", regex=True)
        if jt_null_count > 0:
            logger.info("Safely filled %d missing 'job_types' entries with '[]'.", jt_null_count)

    return df_cleaned


def clean_html_text(raw_html: Any) -> str:
    """
    Transform raw HTML job description into human-readable plain text.

    Steps:
    1. Unescape HTML entities (&amp; -> &, &quot; -> ", etc.).
    2. Convert block elements (<p>, <h1-6>, <div>, <br>) into natural line breaks.
    3. Convert list items (<li>) into readable bullet points ('• ').
    4. Strip all remaining HTML tags.
    5. Clean up orphaned bullet points and normalize spacing.

    Args:
        raw_html: Raw HTML string or non-string object.

    Returns:
        str: Cleaned, structured plain text.
    """
    if not isinstance(raw_html, str) or not raw_html.strip():
        return ""

    # 1. Unescape HTML entities
    text = html.unescape(raw_html)

    # 2. Convert break and block tags to line breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?h[1-6][^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "\n• ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|div|section|article|blockquote|tr)[^>]*>", "\n\n", text, flags=re.IGNORECASE)

    # 3. Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # 4. Clean up bullet points orphaned by nested tags like <li><p>
    text = re.sub(r"•\s*\n\s*", "• ", text)

    # 5. Normalize whitespace line by line
    cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(cleaned_lines)

    # 6. Collapse excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_html_descriptions(df: pd.DataFrame, col: str = "description") -> pd.DataFrame:
    """
    Apply HTML cleaning to the job description column.

    Args:
        df: Input DataFrame.
        col: Name of description column. Defaults to 'description'.

    Returns:
        pd.DataFrame: DataFrame with cleaned plain text descriptions.
    """
    if col not in df.columns:
        logger.warning("Column '%s' not found for HTML cleaning. Skipping.", col)
        return df

    df_cleaned = df.copy()
    logger.info("Cleaning HTML markup and formatting text for '%s' column...", col)
    df_cleaned[col] = df_cleaned[col].apply(clean_html_text)
    logger.info("Successfully cleaned HTML across all %d descriptions.", len(df_cleaned))
    return df_cleaned


def convert_dates(df: pd.DataFrame, col: str = "created_at") -> pd.DataFrame:
    """
    Convert Unix epoch timestamps (seconds) to formatted datetime strings (YYYY-MM-DD HH:MM:SS).

    Safely coerces invalid or out-of-range timestamps to missing values (pd.NA).

    Args:
        df: Input DataFrame.
        col: Name of timestamp column. Defaults to 'created_at'.

    Returns:
        pd.DataFrame: DataFrame with standardized datetime strings.
    """
    if col not in df.columns:
        logger.warning("Column '%s' not found for date transformation. Skipping.", col)
        return df

    df_cleaned = df.copy()
    logger.info("Converting '%s' Unix timestamps to human-readable datetimes...", col)

    # Convert numeric seconds to datetime; errors='coerce' maps malformed values to NaT
    datetime_series = pd.to_datetime(df_cleaned[col], unit="s", errors="coerce")
    invalid_count = datetime_series.isna().sum()

    if invalid_count > 0:
        logger.warning("Found %d invalid/unparseable timestamp(s) in '%s'. Coerced to null.",
                       invalid_count, col)

    # Format as standard readable string YYYY-MM-DD HH:MM:SS
    df_cleaned[col] = datetime_series.dt.strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Successfully converted '%s' column to datetime strings.", col)
    return df_cleaned


def standardize_text(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize text columns:
    1. Remove unnecessary leading and trailing whitespace.
    2. Convert empty or whitespace-only strings into standard null values (pd.NA).

    Args:
        df: Input DataFrame.

    Returns:
        pd.DataFrame: Standardized DataFrame.
    """
    df_cleaned = df.copy()
    # String columns to clean
    text_columns = ["slug", "company_name", "title", "description", "url", "location"]

    logger.info("Standardizing text fields and normalizing whitespace...")
    for col in text_columns:
        if col in df_cleaned.columns:
            # Strip whitespace on valid string values
            df_cleaned[col] = df_cleaned[col].apply(
                lambda val: val.strip() if isinstance(val, str) else val
            )
            # Replace empty or whitespace-only strings with pd.NA
            df_cleaned[col] = df_cleaned[col].replace(r"^\s*$", pd.NA, regex=True)

    logger.info("Text standardization complete across all textual columns.")
    return df_cleaned


def validate_data(df_before: pd.DataFrame, df_after: pd.DataFrame) -> Dict[str, Any]:
    """
    Validate the transformed dataset against the initial raw dataset and report metrics.

    Args:
        df_before: Raw DataFrame before cleaning.
        df_after: Cleaned DataFrame after all transformations.

    Returns:
        Dict[str, Any]: Validation summary dictionary with counts and missing value metrics.
    """
    records_before = len(df_before)
    records_after = len(df_after)
    records_removed = records_before - records_after
    missing_after = df_after.isna().sum().to_dict()

    summary: Dict[str, Any] = {
        "records_before": records_before,
        "records_after": records_after,
        "records_removed": records_removed,
        "columns_count": len(df_after.columns),
        "missing_values_after": missing_after,
    }

    logger.info("=== Data Cleaning Validation Report ===")
    logger.info("Records before cleaning: %d", records_before)
    logger.info("Records after cleaning : %d (removed %d)", records_after, records_removed)
    logger.info("Missing values summary after cleaning:")
    for column, count in missing_after.items():
        if count > 0:
            logger.info("  - %s: %d missing (%.1f%%)", column, count, (count / records_after) * 100)
        else:
            logger.info("  - %s: 0 missing", column)

    return summary


def save_processed_data(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
) -> Path:
    """
    Save the transformed DataFrame as a CSV file in data/processed/.

    Automatically creates the target directory if missing and uses timestamped
    filenames to prevent destructive overwriting.

    Args:
        df: The transformed Pandas DataFrame.
        output_dir: Directory where processed CSV will be written. Defaults to data/processed/.
        filename: Optional explicit filename. If not given, uses timestamped name.

    Returns:
        Path: Path to the generated CSV file.
    """
    destination_dir = output_dir or DEFAULT_PROCESSED_DATA_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_filename = filename or f"jobs_processed_{timestamp_str}.csv"
    destination_path = destination_dir / target_filename

    # Protect existing files from accidental overwrite
    if destination_path.exists() and filename:
        stem = destination_path.stem
        suffix = destination_path.suffix
        destination_path = destination_dir / f"{stem}_{timestamp_str}{suffix}"
        logger.warning("Target file existed. Preserved data by saving to: %s", destination_path.name)

    logger.info("Saving cleaned dataset (%d rows) to: %s", len(df), destination_path)
    df.to_csv(destination_path, index=False, encoding="utf-8")

    file_size_bytes = destination_path.stat().st_size
    logger.info(
        "Processed CSV written successfully. File size: %d bytes (~%.2f KB) at %s",
        file_size_bytes, file_size_bytes / 1024.0, destination_path
    )
    return destination_path


# ---------------------------------------------------------------------------
# DataCleaner Pipeline Class
# ---------------------------------------------------------------------------

class DataCleaner:
    """
    Orchestrates the data cleaning and transformation pipeline for job postings.

    Attributes:
        raw_dir (Path): Source directory containing raw CSV files.
        processed_dir (Path): Destination directory for cleaned CSV files.
    """

    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize the DataCleaner with configurable source and target paths.

        Args:
            raw_dir: Directory containing raw CSV files.
            processed_dir: Directory to save transformed CSV files.
        """
        self.raw_dir = raw_dir or DEFAULT_RAW_DATA_DIR
        self.processed_dir = processed_dir or DEFAULT_PROCESSED_DATA_DIR

    def run(
        self,
        input_file: Optional[Path] = None,
        output_filename: Optional[str] = None,
    ) -> Tuple[Path, Dict[str, Any]]:
        """
        Execute the full data cleaning workflow:
            1. Identify latest raw CSV (or use input_file)
            2. Load raw CSV
            3. Remove duplicate listings
            4. Handle missing values
            5. Clean HTML descriptions
            6. Convert dates
            7. Standardize text
            8. Validate cleaned data
            9. Save processed CSV

        Args:
            input_file: Optional path to a specific raw CSV file.
            output_filename: Optional custom filename for processed CSV.

        Returns:
            Tuple[Path, Dict[str, Any]]: Path to the created CSV and validation summary.
        """
        logger.info("=== Starting TechPulse Data Cleaning Pipeline ===")

        # Step 1: Locate input file
        raw_csv_path = input_file or get_latest_raw_file(self.raw_dir)

        # Step 2: Load data
        df_raw = load_data(raw_csv_path)

        # Step 3: Remove duplicates
        df = remove_duplicates(df_raw, subset_col="slug")

        # Step 4: Handle missing values
        df = handle_missing_values(df)

        # Step 5: Clean HTML descriptions
        df = clean_html_descriptions(df, col="description")

        # Step 6: Convert dates
        df = convert_dates(df, col="created_at")

        # Step 7: Standardize text
        df = standardize_text(df)

        # Step 8: Validate transformed data
        validation_report = validate_data(df_raw, df)

        # Step 9: Save processed CSV
        processed_file_path = save_processed_data(
            df,
            output_dir=self.processed_dir,
            filename=output_filename,
        )

        logger.info("=== TechPulse Data Cleaning Pipeline Completed Successfully ===")
        return processed_file_path, validation_report


def clean_jobs(
    input_file: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Convenience function to run the full job data cleaning pipeline.

    Args:
        input_file: Optional explicit raw CSV file path.
        output_dir: Optional explicit processed directory.
        filename: Optional explicit output CSV filename.

    Returns:
        Tuple[Path, Dict[str, Any]]: Saved CSV file path and validation summary.
    """
    cleaner = DataCleaner(processed_dir=output_dir)
    return cleaner.run(input_file=input_file, output_filename=filename)


def main() -> None:
    """CLI entrypoint for running the data cleaner."""
    try:
        output_file, validation = clean_jobs()
        print("\n" + "=" * 70)
        print("TECHPULSE - DATA CLEANING & TRANSFORMATION COMPLETE")
        print("=" * 70)
        print(f"Input Records     : {validation['records_before']}")
        print(f"Cleaned Records   : {validation['records_after']}")
        print(f"Records Dropped   : {validation['records_removed']}")
        print(f"Output File       : {output_file}")
        print(f"Output File Size  : {output_file.stat().st_size:,} bytes")
        print("-" * 70)
        print("Missing Values After Cleaning:")
        for col, count in validation["missing_values_after"].items():
            status = "CLEAN" if count == 0 else f"{count} missing"
            print(f"  - {col:<15} : {status}")
        print("=" * 70)
    except Exception as exc:
        logger.exception("Data cleaning pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
