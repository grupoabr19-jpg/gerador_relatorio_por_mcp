"""Tests for daily marketing data collection helpers."""

import unittest
from unittest.mock import Mock

from scripts.daily_marketing_report import (
    GA4_HEADERS,
    META_ADS_HEADERS,
    _ga4_rows,
    _meta_ads_rows,
    _upsert_rows,
)


class TestReportRowConversion(unittest.TestCase):
    def test_converts_ga4_rows_to_sheet_schema(self):
        response = Mock()
        response.rows = [
            Mock(
                dimension_values=[
                    Mock(value="20261102"),
                    Mock(value="instagram / social"),
                    Mock(value="brand"),
                ],
                metric_values=[
                    Mock(value="12"),
                    Mock(value="10"),
                    Mock(value="9"),
                    Mock(value="4"),
                    Mock(value="7"),
                    Mock(value="0.58"),
                    Mock(value="32"),
                    Mock(value="2"),
                    Mock(value="0"),
                ],
            )
        ]

        self.assertEqual(
            _ga4_rows(response),
            [
                [
                    "2026-11-02",
                    "instagram / social",
                    "brand",
                    12,
                    10,
                    9,
                    4,
                    7,
                    0.58,
                    32,
                    2,
                    0.0,
                ]
            ],
        )
        self.assertEqual(len(GA4_HEADERS), 12)

    def test_converts_meta_ads_rows_and_preserves_breakdowns(self):
        rows = _meta_ads_rows(
            [
                {
                    "date_start": "2026-11-02",
                    "account_id": "123",
                    "campaign_id": "c1",
                    "adset_id": "s1",
                    "ad_id": "a1",
                    "publisher_platform": "instagram",
                    "platform_position": "reels",
                    "spend": "20.00",
                    "reach": "500",
                }
            ]
        )

        self.assertEqual(len(rows[0]), len(META_ADS_HEADERS))
        self.assertEqual(rows[0][0], "2026-11-02")
        self.assertEqual(rows[0][8:10], ["instagram", "reels"])
        self.assertEqual(rows[0][11], 500)
        self.assertEqual(rows[0][13], 20.0)


class TestSheetUpsert(unittest.TestCase):
    def test_updates_existing_key_and_appends_new_key(self):
        session = Mock()
        metadata_response = Mock()
        metadata_response.json.return_value = {
            "sheets": [{"properties": {"title": "Coleta_GA4_Diario"}}]
        }
        metadata_response.raise_for_status.return_value = None
        values_response = Mock()
        values_response.json.return_value = {
            "values": [
                ["date", "source", "sessions"],
                ["2026-11-01", "google / organic", "10"],
            ]
        }
        values_response.raise_for_status.return_value = None
        session.get.side_effect = [metadata_response, values_response]
        update_response = Mock()
        update_response.raise_for_status.return_value = None
        append_response = Mock()
        append_response.raise_for_status.return_value = None
        session.post.side_effect = [update_response, append_response]

        count = _upsert_rows(
            session,
            "sheet-id",
            "Coleta_GA4_Diario",
            ["date", "source", "sessions"],
            [
                ["2026-11-01", "google / organic", "12"],
                ["2026-11-02", "google / organic", "8"],
            ],
            [0, 1],
        )

        self.assertEqual(count, 2)
        update_body = session.post.call_args_list[0].kwargs["json"]
        append_body = session.post.call_args_list[1].kwargs["json"]
        self.assertEqual(
            update_body["data"][0]["values"],
            [["2026-11-01", "google / organic", "12"]],
        )
        self.assertEqual(
            append_body["values"],
            [["2026-11-02", "google / organic", "8"]],
        )

    def test_refuses_unexpected_existing_headers(self):
        session = Mock()
        metadata_response = Mock()
        metadata_response.json.return_value = {
            "sheets": [{"properties": {"title": "Coleta_GA4_Diario"}}]
        }
        metadata_response.raise_for_status.return_value = None
        values_response = Mock()
        values_response.json.return_value = {"values": [["manual data"]]}
        values_response.raise_for_status.return_value = None
        session.get.side_effect = [metadata_response, values_response]

        with self.assertRaisesRegex(ValueError, "Unexpected header"):
            _upsert_rows(
                session,
                "sheet-id",
                "Coleta_GA4_Diario",
                ["date", "source"],
                [["2026-11-01", "google / organic"]],
                [0, 1],
            )


if __name__ == "__main__":
    unittest.main()
