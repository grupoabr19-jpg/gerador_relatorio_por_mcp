# Copyright 2026 Google LLC All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tools for exporting Google Analytics reports."""

from pathlib import Path
from typing import Any, Dict, List

from analytics_mcp.tools.export import _write_csv
from analytics_mcp.tools.reporting.core import run_report

_REPORT_PAGE_SIZE = 100_000


async def export_report_to_csv(
    property_id: int | str,
    date_ranges: List[Dict[str, Any]],
    dimensions: List[str],
    metrics: List[str],
    output_path: str,
    dimension_filter: Dict[str, Any] = None,
    metric_filter: Dict[str, Any] = None,
    order_bys: List[Dict[str, Any]] = None,
    currency_code: str = None,
    return_property_quota: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Runs a Google Analytics report and saves all rows to a local CSV file.

    The output file is created on the machine running this MCP server. Existing
    files are not overwritten unless `overwrite` is true.

    Args:
        property_id: The Google Analytics property ID.
        date_ranges: Date ranges to include in the report.
        dimensions: Dimensions to include in the report.
        metrics: Metrics to include in the report.
        output_path: Destination path for the CSV file.
        dimension_filter: Optional Data API dimension filter.
        metric_filter: Optional Data API metric filter.
        order_bys: Optional Data API ordering.
        currency_code: Optional ISO 4217 currency code.
        return_property_quota: Whether to return property quota in the response.
        overwrite: Whether to replace an existing file at `output_path`.

    Returns:
        The absolute output path and number of exported rows.
    """
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".csv":
        raise ValueError("output_path must have a .csv extension.")
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"File already exists: {path}. Set overwrite=true to replace it."
        )

    report_rows = []
    dimension_headers = None
    metric_headers = None
    offset = 0

    while True:
        report = await run_report(
            property_id=property_id,
            date_ranges=date_ranges,
            dimensions=dimensions,
            metrics=metrics,
            dimension_filter=dimension_filter,
            metric_filter=metric_filter,
            order_bys=order_bys,
            limit=_REPORT_PAGE_SIZE,
            offset=offset,
            currency_code=currency_code,
            return_property_quota=return_property_quota,
        )
        if dimension_headers is None:
            dimension_headers = report.get("dimension_headers", [])
            metric_headers = report.get("metric_headers", [])

        page_rows = report.get("rows", [])
        report_rows.extend(page_rows)
        offset += len(page_rows)

        row_count = report.get("row_count")
        if (
            not page_rows
            or (row_count is not None and offset >= int(row_count))
            or len(page_rows) < _REPORT_PAGE_SIZE
        ):
            break

    headers = [
        header["name"] for header in dimension_headers + metric_headers
    ]
    rows = [
        [
            value.get("value", "")
            for value in row.get("dimension_values", [])
            + row.get("metric_values", [])
        ]
        for row in report_rows
    ]
    file_path = _write_csv(
        str(path), headers, rows, overwrite=overwrite
    )
    return {"file_path": file_path, "row_count": len(report_rows)}
