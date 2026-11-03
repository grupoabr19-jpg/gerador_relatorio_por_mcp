"""Tests for daily marketing data collection helpers."""

import unittest
from datetime import date
from unittest.mock import Mock

from scripts.daily_marketing_report import (
    GA4_HEADERS,
    META_ADS_HEADERS,
    _ga4_backfill_start_date,
    _ga4_daily_rows,
    _ga4_rows,
    _meta_ads_rows,
    _normalize_spreadsheet_id,
    _upsert_rows,
)


class TestReportRowConversion(unittest.TestCase):
    def test_ga4_backfill_fills_gap_and_reloads_recent_window(self):
        self.assertEqual(
            _ga4_backfill_start_date(
                [["Date"], ["2026-09-14"], ["2026-09-15"]],
                "2026-11-02",
            ),
            "2026-09-16",
        )
        self.assertEqual(
            _ga4_backfill_start_date(
                [["Date"], ["2026-11-01"], ["2026-11-02"]],
                "2026-11-02",
            ),
            "2026-10-27",
        )

    def test_ga4_backfill_parses_sheet_serial_dates(self):
        serial_date = (date(2026, 11, 2) - date(1899, 12, 30)).days
        self.assertEqual(
            _ga4_backfill_start_date([["Date"], [serial_date]], "2026-11-02"),
            "2026-10-27",
        )

    def test_normalizes_spreadsheet_id_or_full_url(self):
        spreadsheet_id = "1goIR1S7rAzNLwTnCAeVbHp-Ko0l7M44p6B0RfUaM16w"
        self.assertEqual(
            _normalize_spreadsheet_id(spreadsheet_id), spreadsheet_id
        )
        self.assertEqual(
            _normalize_spreadsheet_id(
                "https://docs.google.com/spreadsheets/d/"
                f"{spreadsheet_id}/edit?gid=362856036#gid=362856036"
            ),
            spreadsheet_id,
        )

    def test_rejects_non_spreadsheet_url(self):
        with self.assertRaisesRegex(ValueError, "Google Sheets ID"):
            _normalize_spreadsheet_id("https://example.com/not-a-sheet")

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

    def test_ga4_daily_rows_match_existing_percentage_format(self):
        response = Mock()
        response.rows = [
            Mock(
                dimension_values=[Mock(value="20260915")],
                metric_values=[
                    Mock(value="67"),
                    Mock(value="55"),
                    Mock(value="52"),
                    Mock(value="50"),
                    Mock(value="49"),
                    Mock(value="0.7313"),
                    Mock(value="120"),
                    Mock(value="87"),
                    Mock(value="0"),
                ],
            )
        ]

        self.assertEqual(
            _ga4_daily_rows(response),
            [["2026-09-15", 67, 55, 52, 50, 49, 73.13, 120, 87, 0.0]],
        )

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

    def test_upsert_matches_sheet_serial_date_to_iso_date(self):
        serial_date = (date(2026, 9, 15) - date(1899, 12, 30)).days
        session = Mock()
        metadata_response = Mock()
        metadata_response.json.return_value = {
            "sheets": [{"properties": {"title": "Dados_GA4"}}]
        }
        metadata_response.raise_for_status.return_value = None
        values_response = Mock()
        values_response.json.return_value = {
            "values": [
                ["Date", "Sessions"],
                [serial_date, 40],
            ]
        }
        values_response.raise_for_status.return_value = None
        session.get.side_effect = [metadata_response, values_response]
        update_response = Mock()
        update_response.raise_for_status.return_value = None
        session.post.return_value = update_response

        _upsert_rows(
            session,
            "sheet-id",
            "Dados_GA4",
            ["Date", "Sessions"],
            [["2026-09-15", 42]],
            [0],
        )

        self.assertEqual(session.post.call_count, 1)
        update_body = session.post.call_args.kwargs["json"]
        self.assertEqual(
            update_body["data"][0]["range"], "'Dados_GA4'!A2:B2"
        )
        self.assertEqual(update_body["data"][0]["values"], [["2026-09-15", 42]])

    def test_sorts_daily_sheet_by_date_after_upsert(self):
        session = Mock()
        metadata_response = Mock()
        metadata_response.json.return_value = {
            "sheets": [
                {"properties": {"title": "Dados_GA4", "sheetId": 73}}
            ]
        }
        metadata_response.raise_for_status.return_value = None
        values_response = Mock()
        values_response.json.return_value = {
            "values": [
                ["Date", "Sessions"],
                ["2026-09-16", 10],
                ["2026-09-15", 12],
            ]
        }
        values_response.raise_for_status.return_value = None
        session.get.side_effect = [metadata_response, values_response]
        update_response = Mock()
        update_response.raise_for_status.return_value = None
        sort_response = Mock()
        sort_response.raise_for_status.return_value = None
        session.post.side_effect = [update_response, sort_response]

        _upsert_rows(
            session,
            "sheet-id",
            "Dados_GA4",
            ["Date", "Sessions"],
            [["2026-09-16", 10]],
            [0],
            sort_key_index=0,
        )

        sort_request = session.post.call_args_list[-1].kwargs["json"]
        self.assertEqual(
            sort_request["requests"][0]["sortRange"]["range"],
            {
                "sheetId": 73,
                "startRowIndex": 1,
                "endRowIndex": 3,
                "startColumnIndex": 0,
                "endColumnIndex": 2,
            },
        )
        self.assertEqual(
            sort_request["requests"][0]["sortRange"]["sortSpecs"],
            [{"dimensionIndex": 0, "sortOrder": "ASCENDING"}],
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
