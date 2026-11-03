"""Collect daily Google Analytics and Meta Ads data into Google Sheets."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import google.auth
import requests
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.auth.transport.requests import AuthorizedSession

LOGGER = logging.getLogger("daily_marketing_report")
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]
GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v26.0")
LOOKBACK_DAYS = 7
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
GRAPH_API = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

GA4_HEADERS = [
    "date",
    "session_source_medium",
    "session_campaign",
    "sessions",
    "total_users",
    "active_users",
    "new_users",
    "engaged_sessions",
    "engagement_rate",
    "screen_page_views",
    "key_events",
    "total_revenue",
]
META_ADS_HEADERS = [
    "date",
    "account_id",
    "campaign_id",
    "campaign_name",
    "adset_id",
    "adset_name",
    "ad_id",
    "ad_name",
    "publisher_platform",
    "platform_position",
    "impressions",
    "reach",
    "frequency",
    "spend",
    "clicks",
    "inline_link_clicks",
    "outbound_clicks",
    "ctr",
    "cpc",
    "cpm",
]
META_ADS_FIELDS = ",".join(
    header
    for header in META_ADS_HEADERS
    if header not in {"date", "publisher_platform", "platform_position"}
)
META_ADS_BREAKDOWNS = "publisher_platform,platform_position"


def _reporting_dates() -> tuple[str, str]:
    """Return a seven-day lookback ending yesterday in São Paulo."""
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=LOOKBACK_DAYS - 1)
    return start_date.isoformat(), end_date.isoformat()


def _date_from_ga4(value: str) -> str:
    return date(int(value[:4]), int(value[4:6]), int(value[6:8])).isoformat()


def _number(value: Any, *, integer: bool = False) -> int | float | str:
    if value is None or value == "":
        return ""
    try:
        return int(value) if integer else float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Expected a numeric API value, received {value!r}."
        ) from error


def _meta_numeric_value(
    value: Any, *, integer: bool = False
) -> int | float | str:
    if isinstance(value, list):
        if not value:
            return ""
        value = sum(float(item.get("value", 0)) for item in value)
    elif isinstance(value, dict):
        value = value.get("value", "")
    return _number(value, integer=integer)


def _ga4_rows(response: Any) -> list[list[Any]]:
    rows = []
    for report_row in response.rows:
        dimensions = [item.value for item in report_row.dimension_values]
        metrics = [item.value for item in report_row.metric_values]
        numeric_metrics = [
            _number(value, integer=index in {0, 1, 2, 3, 4, 6, 7})
            for index, value in enumerate(metrics)
        ]
        rows.append(
            [
                _date_from_ga4(dimensions[0]),
                dimensions[1],
                dimensions[2],
                *numeric_metrics,
            ]
        )
    return rows


def _meta_ads_rows(records: list[dict[str, Any]]) -> list[list[Any]]:
    integer_metrics = {"impressions", "reach", "clicks", "inline_link_clicks"}
    rows = []
    for record in records:
        rows.append(
            [
                record.get("date_start", ""),
                record.get("account_id", ""),
                record.get("campaign_id", ""),
                record.get("campaign_name", ""),
                record.get("adset_id", ""),
                record.get("adset_name", ""),
                record.get("ad_id", ""),
                record.get("ad_name", ""),
                record.get("publisher_platform", ""),
                record.get("platform_position", ""),
                *[
                    _meta_numeric_value(
                        record.get(header, ""),
                        integer=header in integer_metrics,
                    )
                    for header in META_ADS_HEADERS[10:]
                ],
            ]
        )
    return rows


def _sheets_range(sheet_name: str, end_column: str = "ZZ") -> str:
    return f"'{sheet_name}'!A:{end_column}"


def _normalize_spreadsheet_id(value: str) -> str:
    value = value.strip()
    if "://" in value:
        parsed_url = urlparse(value)
        path_parts = parsed_url.path.strip("/").split("/")
        if (
            parsed_url.hostname != "docs.google.com"
            or len(path_parts) < 3
            or path_parts[:2] != ["spreadsheets", "d"]
        ):
            raise ValueError(
                "SPREADSHEET_ID must be a Google Sheets ID or spreadsheet URL."
            )
        value = path_parts[2]

    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(
            "SPREADSHEET_ID must be a Google Sheets ID or spreadsheet URL."
        )
    return value


def _column_name(column_number: int) -> str:
    name = ""
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _ensure_sheet(session: AuthorizedSession, spreadsheet_id: str, title: str):
    response = session.get(
        f"{SHEETS_API}/{spreadsheet_id}",
        params={"fields": "sheets.properties(sheetId,title)"},
        timeout=30,
    )
    response.raise_for_status()
    sheets = response.json().get("sheets", [])
    if any(sheet["properties"]["title"] == title for sheet in sheets):
        return

    response = session.post(
        f"{SHEETS_API}/{spreadsheet_id}:batchUpdate",
        json={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        timeout=30,
    )
    if response.ok:
        return

    error = response.json().get("error", {})
    if error.get("status") == "ALREADY_EXISTS":
        return
    raise RuntimeError(
        f"Could not create worksheet {title}: "
        f"{error.get('message', response.status_code)}"
    )


def _upsert_rows(
    session: AuthorizedSession,
    spreadsheet_id: str,
    sheet_name: str,
    headers: list[str],
    rows: list[list[Any]],
    key_columns: list[int],
) -> int:
    """Insert or replace rows in an automation-owned worksheet by key."""
    if not rows:
        LOGGER.info("No rows to write to %s", sheet_name)
        return 0

    if any(len(row) != len(headers) for row in rows):
        raise ValueError(f"Rows for {sheet_name} do not match its header.")

    _ensure_sheet(session, spreadsheet_id, sheet_name)
    quoted_range = quote(_sheets_range(sheet_name), safe="!'")
    response = session.get(
        f"{SHEETS_API}/{spreadsheet_id}/values/{quoted_range}",
        params={"valueRenderOption": "UNFORMATTED_VALUE"},
        timeout=30,
    )
    response.raise_for_status()
    existing = response.json().get("values", [])

    if existing and existing[0] != headers:
        raise ValueError(
            f"Unexpected header in {sheet_name}; refusing to overwrite it."
        )

    if not existing:
        response = session.put(
            f"{SHEETS_API}/{spreadsheet_id}/values/"
            f"{quote(f'{sheet_name}!A1', safe='!')}",
            params={"valueInputOption": "RAW"},
            json={"values": [headers]},
            timeout=30,
        )
        response.raise_for_status()
        existing = [headers]

    existing_rows = existing[1:]
    existing_by_key = {}
    for row_index, row in enumerate(existing_rows, start=2):
        padded = row + [""] * (len(headers) - len(row))
        existing_by_key[tuple(str(padded[index]) for index in key_columns)] = (
            row_index
        )

    updates = []
    additions = []
    for row in rows:
        key = tuple(str(row[index]) for index in key_columns)
        row_index = existing_by_key.get(key)
        if row_index is None:
            additions.append(row)
        else:
            end_column = _column_name(len(headers))
            updates.append(
                {
                    "range": (
                        f"'{sheet_name}'!A{row_index}:"
                        f"{end_column}{row_index}"
                    ),
                    "values": [row],
                }
            )

    if updates:
        response = session.post(
            f"{SHEETS_API}/{spreadsheet_id}/values:batchUpdate",
            json={
                "valueInputOption": "RAW",
                "data": updates,
            },
            timeout=60,
        )
        response.raise_for_status()

    if additions:
        append_range = quote(
            f"'{sheet_name}'!A:{_column_name(len(headers))}", safe="!:'"
        )
        response = session.post(
            f"{SHEETS_API}/{spreadsheet_id}/values/{append_range}:append",
            params={
                "valueInputOption": "RAW",
                "insertDataOption": "INSERT_ROWS",
            },
            json={"values": additions},
            timeout=60,
        )
        response.raise_for_status()

    return len(rows)


def _collect_ga4(
    client: BetaAnalyticsDataClient, property_id: str
) -> list[list[Any]]:
    start_date, end_date = _reporting_dates()
    response = client.run_report(
        RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="sessionSourceMedium"),
                Dimension(name="sessionCampaignName"),
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="activeUsers"),
                Metric(name="newUsers"),
                Metric(name="engagedSessions"),
                Metric(name="engagementRate"),
                Metric(name="screenPageViews"),
                Metric(name="keyEvents"),
                Metric(name="totalRevenue"),
            ],
            limit=250_000,
        )
    )
    return _ga4_rows(response)


def _meta_get(
    access_token: str, path: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    url = f"{GRAPH_API}/{path}"
    request_params = dict(params or {})
    request_params["access_token"] = access_token
    try:
        response = requests.get(url, params=request_params, timeout=60)
    except requests.RequestException:
        raise RuntimeError(
            "Meta Graph API request could not be completed."
        ) from None
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok or "error" in payload:
        error = payload.get("error", {})
        raise RuntimeError(
            "Meta Graph API request failed "
            f"(HTTP {response.status_code}, "
            f"code {error.get('code', 'unknown')}): "
            f"{error.get('message', 'No error details returned')}"
        )
    return payload


def _collect_meta_ads(access_token: str, account_id: str) -> list[list[Any]]:
    start_date, end_date = _reporting_dates()
    account_path = (
        account_id if account_id.startswith("act_") else f"act_{account_id}"
    )
    params = {
        "level": "ad",
        "time_increment": 1,
        "time_range": json.dumps(
            {"since": start_date, "until": end_date}, separators=(",", ":")
        ),
        "fields": META_ADS_FIELDS,
        "breakdowns": META_ADS_BREAKDOWNS,
        "limit": 500,
    }

    records = []
    payload = _meta_get(access_token, f"{account_path}/insights", params)
    records.extend(payload.get("data", []))
    while payload.get("paging", {}).get("next"):
        try:
            response = requests.get(payload["paging"]["next"], timeout=60)
        except requests.RequestException:
            raise RuntimeError("Meta Ads pagination request failed.") from None
        try:
            next_payload = response.json()
        except ValueError:
            next_payload = {}
        if not response.ok or "error" in next_payload:
            error = next_payload.get("error", {})
            raise RuntimeError(
                "Meta Ads pagination failed "
                f"(HTTP {response.status_code}, "
                f"code {error.get('code', 'unknown')}): "
                f"{error.get('message', 'No error details returned')}"
            )
        payload = next_payload
        records.extend(payload.get("data", []))
    return _meta_ads_rows(records)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    spreadsheet_value = os.environ.get("SPREADSHEET_ID")
    property_id = os.environ.get("GA4_PROPERTY_ID")
    meta_account_id = os.environ.get("META_AD_ACCOUNT_ID")
    meta_access_token = os.environ.get("META_ACCESS_TOKEN")

    if not spreadsheet_value:
        raise RuntimeError("SPREADSHEET_ID variable is required.")
    spreadsheet_id = _normalize_spreadsheet_id(spreadsheet_value)
    if not property_id and not meta_account_id:
        raise RuntimeError(
            "Configure GA4_PROPERTY_ID, META_AD_ACCOUNT_ID, or both."
        )
    if meta_account_id and not meta_access_token:
        raise RuntimeError(
            "META_ACCESS_TOKEN secret is required when Meta Ads is enabled."
        )

    credentials, _ = google.auth.default(scopes=SCOPES)
    sheets_session = AuthorizedSession(credentials)

    if property_id:
        ga4_client = BetaAnalyticsDataClient(credentials=credentials)
        ga4_rows = _collect_ga4(ga4_client, property_id)
        count = _upsert_rows(
            sheets_session,
            spreadsheet_id,
            "Coleta_GA4_Diario",
            GA4_HEADERS,
            ga4_rows,
            [0, 1, 2],
        )
        LOGGER.info("Upserted %d GA4 rows.", count)

    if meta_account_id and meta_access_token:
        meta_rows = _collect_meta_ads(meta_access_token, meta_account_id)
        count = _upsert_rows(
            sheets_session,
            spreadsheet_id,
            "Coleta_MetaAds_Diario",
            META_ADS_HEADERS,
            meta_rows,
            [0, 1, 2, 4, 6, 8, 9],
        )
        LOGGER.info("Upserted %d Meta Ads rows.", count)


if __name__ == "__main__":
    main()
