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

"""Tools for exporting MCP data to local files."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def _write_csv(
    output_path: str,
    headers: List[str],
    rows: List[List[Any]],
    overwrite: bool = False,
) -> str:
    """Writes CSV data without replacing an existing file by default."""
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".csv":
        raise ValueError("output_path must have a .csv extension.")
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"File already exists: {path}. Set overwrite=true to replace it."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)
        writer.writerows(
            [
                json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
                for value in row
            ]
            for row in rows
        )

    return str(path)


def export_records_to_csv(
    records: List[Dict[str, Any]],
    output_path: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Saves records returned by any MCP data tool as a local CSV file.

    Pass the records array from a read-only MCP tool (for example, Meta Ads
    insights or Taplio post analytics). Nested values are serialized as JSON.
    The output file is created on the machine running this MCP server.

    Args:
        records: List of objects to export.
        output_path: Destination path for the CSV file.
        overwrite: Whether to replace an existing file at `output_path`.

    Returns:
        The absolute output path, number of records, and exported columns.
    """
    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        raise ValueError("records must be a list of objects.")

    headers = list(dict.fromkeys(key for record in records for key in record))
    rows = [
        [record.get(header, "") for header in headers] for record in records
    ]
    path = _write_csv(output_path, headers, rows, overwrite=overwrite)

    return {
        "file_path": path,
        "row_count": len(records),
        "columns": headers,
    }
