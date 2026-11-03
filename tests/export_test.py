"""Test cases for generic MCP data export tools."""

import csv
import tempfile
import unittest
from pathlib import Path

from analytics_mcp.tools.export import export_records_to_csv


class TestExportRecordsToCsv(unittest.TestCase):
    """Test cases for exporting generic records to CSV."""

    def test_exports_union_of_record_columns(self):
        records = [
            {"campaign": "Launch", "spend": "12.5"},
            {"campaign": "Retarget", "impressions": "250"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "meta.csv")
            result = export_records_to_csv(records, str(path))

            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.reader(csv_file))

        self.assertEqual(
            rows,
            [
                ["campaign", "spend", "impressions"],
                ["Launch", "12.5", ""],
                ["Retarget", "", "250"],
            ],
        )
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(
            result["columns"], ["campaign", "spend", "impressions"]
        )

    def test_serializes_nested_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "analytics.csv")
            export_records_to_csv(
                [{"post": "1", "metrics": {"likes": 5}}],
                str(path),
            )

            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.reader(csv_file))

        self.assertEqual(rows[1], ["1", '{"likes": 5}'])

    def test_rejects_non_object_records(self):
        with self.assertRaisesRegex(ValueError, "list of objects"):
            export_records_to_csv([{"ok": True}, "invalid"], "data.csv")

    def test_does_not_overwrite_existing_file_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "data.csv")
            path.write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                export_records_to_csv([], str(path))

            self.assertEqual(path.read_text(encoding="utf-8"), "existing")

    def test_overwrites_existing_file_when_requested(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "data.csv")
            path.write_text("existing", encoding="utf-8")

            result = export_records_to_csv(
                [{"value": "new"}], str(path), overwrite=True
            )

            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.reader(csv_file))

        self.assertEqual(rows, [["value"], ["new"]])
        self.assertEqual(result["row_count"], 1)
