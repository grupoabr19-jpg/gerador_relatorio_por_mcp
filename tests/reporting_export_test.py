"""Test cases for reporting export tools."""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from analytics_mcp.tools.reporting.export import export_report_to_csv


class TestExportReportToCsv(unittest.IsolatedAsyncioTestCase):
    """Test cases for exporting reports to CSV."""

    @patch(
        "analytics_mcp.tools.reporting.export.run_report",
        new_callable=AsyncMock,
    )
    async def test_exports_all_pages(self, run_report):
        run_report.side_effect = [
            {
                "dimension_headers": [{"name": "date"}],
                "metric_headers": [{"name": "activeUsers"}],
                "row_count": 3,
                "rows": [
                    {
                        "dimension_values": [{"value": "20260101"}],
                        "metric_values": [{"value": "10"}],
                    },
                    {
                        "dimension_values": [{"value": "20260102"}],
                        "metric_values": [{"value": "20"}],
                    },
                ],
            },
            {
                "dimension_headers": [{"name": "date"}],
                "metric_headers": [{"name": "activeUsers"}],
                "row_count": 3,
                "rows": [
                    {
                        "dimension_values": [{"value": "20260103"}],
                        "metric_values": [{"value": "30"}],
                    }
                ],
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "report.csv")
            with patch(
                "analytics_mcp.tools.reporting.export._REPORT_PAGE_SIZE", 2
            ):
                result = await export_report_to_csv(
                    property_id=123,
                    date_ranges=[
                        {"start_date": "2026-01-01", "end_date": "today"}
                    ],
                    dimensions=["date"],
                    metrics=["activeUsers"],
                    output_path=str(path),
                )

            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.reader(csv_file))

        self.assertEqual(result["file_path"], str(path.resolve()))
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(
            rows,
            [
                ["date", "activeUsers"],
                ["20260101", "10"],
                ["20260102", "20"],
                ["20260103", "30"],
            ],
        )
        self.assertEqual(
            [call.kwargs["offset"] for call in run_report.await_args_list],
            [0, 2],
        )

    @patch(
        "analytics_mcp.tools.reporting.export.run_report",
        new_callable=AsyncMock,
    )
    async def test_does_not_overwrite_existing_file_by_default(
        self, run_report
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "report.csv")
            path.write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                await export_report_to_csv(
                    property_id=123,
                    date_ranges=[],
                    dimensions=[],
                    metrics=[],
                    output_path=str(path),
                )

        run_report.assert_not_awaited()

    async def test_requires_csv_extension(self):
        with self.assertRaisesRegex(ValueError, r"\.csv"):
            await export_report_to_csv(
                property_id=123,
                date_ranges=[],
                dimensions=[],
                metrics=[],
                output_path="report.json",
            )
