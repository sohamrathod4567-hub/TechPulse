"""
Unit tests for TechPulse Data Cleaner.
"""

import sys
import unittest
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd

from techpulse.etl.data_cleaner import (
    remove_duplicates,
    handle_missing_values,
    clean_html_text,
    convert_dates,
    standardize_text,
    validate_data,
)


class TestDataCleaner(unittest.TestCase):
    def test_remove_duplicates(self):
        df = pd.DataFrame({
            "slug": ["job-1", "job-1", "job-2"],
            "title": ["Dev 1", "Dev 1", "Dev 2"],
        })
        cleaned = remove_duplicates(df, "slug")
        self.assertEqual(len(cleaned), 2)
        self.assertListEqual(cleaned["slug"].tolist(), ["job-1", "job-2"])

    def test_handle_missing_values(self):
        df = pd.DataFrame({
            "title": ["Software Engineer", "", None, "Data Analyst"],
            "company_name": ["TechCorp", "Google", "Meta", None],
            "tags": [None, "[]", None, "['AI']"],
            "job_types": [None, None, "[]", "['Full-time']"],
        })
        cleaned = handle_missing_values(df)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned["title"].iloc[0], "Software Engineer")
        self.assertEqual(cleaned["tags"].iloc[0], "[]")
        self.assertEqual(cleaned["job_types"].iloc[0], "[]")

    def test_clean_html_text(self):
        raw_html = (
            "<h2>About the Role</h2>"
            "<p>We are hiring! Contact &amp; join us.</p>"
            "<ul><li>Python &amp; Pandas</li><li>FastAPI</li></ul>"
        )
        cleaned = clean_html_text(raw_html)
        self.assertIn("About the Role", cleaned)
        self.assertIn("Contact & join us.", cleaned)
        self.assertIn("• Python & Pandas", cleaned)
        self.assertIn("• FastAPI", cleaned)
        self.assertNotIn("<", cleaned)
        self.assertNotIn(">", cleaned)

    def test_convert_dates(self):
        df = pd.DataFrame({
            "created_at": [1795429844, "invalid_timestamp", None],
        })
        cleaned = convert_dates(df, "created_at")
        self.assertEqual(cleaned["created_at"].iloc[0], "2026-11-23 10:30:44")
        self.assertTrue(pd.isna(cleaned["created_at"].iloc[1]))
        self.assertTrue(pd.isna(cleaned["created_at"].iloc[2]))

    def test_standardize_text(self):
        df = pd.DataFrame({
            "slug": ["  job-slug-1  "],
            "location": ["   "],
            "company_name": ["Acme Corp"],
        })
        cleaned = standardize_text(df)
        self.assertEqual(cleaned["slug"].iloc[0], "job-slug-1")
        self.assertTrue(pd.isna(cleaned["location"].iloc[0]))
        self.assertEqual(cleaned["company_name"].iloc[0], "Acme Corp")

    def test_validate_data(self):
        df_before = pd.DataFrame({"title": ["A", "B", "C"]})
        df_after = pd.DataFrame({"title": ["A", "B"]})
        summary = validate_data(df_before, df_after)
        self.assertEqual(summary["records_before"], 3)
        self.assertEqual(summary["records_after"], 2)
        self.assertEqual(summary["records_removed"], 1)


if __name__ == "__main__":
    unittest.main()
