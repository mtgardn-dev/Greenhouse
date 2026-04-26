from __future__ import annotations

import re
from collections.abc import Sequence

import pandas as pd


DATE_COLUMN_CANDIDATES = ("last_changed", "last_updated", "time", "timestamp", "date", "datetime")
STAT_SUFFIXES = ("min", "mean", "max")
BASE_ALIASES = {
    "temp": "temperature",
    "temperature": "temperature",
    "humid": "humidity",
    "humidity": "humidity",
}


def detect_date_column(columns: Sequence[str]) -> str | None:
    lower_map = {column.lower().strip(): column for column in columns}

    for candidate in DATE_COLUMN_CANDIDATES:
        for lower, original in lower_map.items():
            if candidate in lower:
                return original

    return columns[0] if len(columns) else None


def extract_daily_stat_groups(columns: Sequence[str]) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {}

    for column in columns:
        normalized = re.sub(r"[\s\-]+", "_", column.strip().lower())

        for suffix in STAT_SUFFIXES:
            marker = f"_{suffix}"
            if not normalized.endswith(marker):
                continue

            base = normalized[: -len(marker)]
            base = "_".join(BASE_ALIASES.get(part, part) for part in base.split("_"))
            groups.setdefault(base, {})[suffix] = column
            break

    return {base: stats for base, stats in groups.items() if all(suffix in stats for suffix in STAT_SUFFIXES)}


def prepare_daily_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    date_column = detect_date_column(df.columns)
    if date_column is None:
        raise ValueError("No date column found.")

    prepared = df.copy()
    prepared[date_column] = pd.to_datetime(prepared[date_column], errors="coerce")
    prepared = prepared.dropna(subset=[date_column]).sort_values(date_column).reset_index(drop=True)
    return prepared, date_column
