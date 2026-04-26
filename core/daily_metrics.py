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
TEMPERATURE_UPPER_PRESET_LABEL = "Temperature: Upper (min, mean, max)"
TEMPERATURE_LOWER_PRESET_LABEL = "Temperature: Lower (min, mean, max)"
HUMIDITY_UPPER_PRESET_LABEL = "Humidity: Upper (min, mean, max)"
HUMIDITY_LOWER_PRESET_LABEL = "Humidity: Lower (min, mean, max)"
METRIC_PRESET_LABELS = (
    TEMPERATURE_LOWER_PRESET_LABEL,
    TEMPERATURE_UPPER_PRESET_LABEL,
    HUMIDITY_LOWER_PRESET_LABEL,
    HUMIDITY_UPPER_PRESET_LABEL,
)


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


def _unique_preserving_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _collect_preset_metrics(
    daily_metric_groups: dict[str, dict[str, str]],
    numeric_cols: Sequence[str],
    include_tokens: tuple[str, ...],
    exclude_tokens: tuple[str, ...] = (),
) -> list[str]:
    metrics: list[str] = []

    for group_name, stats in daily_metric_groups.items():
        normalized_group_name = group_name.lower()
        if any(token in normalized_group_name for token in include_tokens) and not any(
            token in normalized_group_name for token in exclude_tokens
        ):
            metrics.extend(stats.values())

    if not metrics:
        metrics.extend(
            column
            for column in numeric_cols
            if any(token in column.lower() for token in include_tokens)
            and not any(token in column.lower() for token in exclude_tokens)
        )

    return _unique_preserving_order(metrics)


def build_metric_presets(
    numeric_cols: Sequence[str],
    daily_metric_groups: dict[str, dict[str, str]],
) -> dict[str, list[str]]:
    presets: dict[str, list[str]] = {label: [] for label in METRIC_PRESET_LABELS}

    presets[TEMPERATURE_UPPER_PRESET_LABEL] = _collect_preset_metrics(
        daily_metric_groups,
        numeric_cols,
        ("temp", "temperature"),
        ("lower", "low", "bottom", "indoor", "inside"),
    )
    presets[TEMPERATURE_LOWER_PRESET_LABEL] = _collect_preset_metrics(
        daily_metric_groups,
        numeric_cols,
        ("temp", "temperature"),
        ("upper", "high", "higher", "top", "outdoor", "outside"),
    )
    presets[HUMIDITY_UPPER_PRESET_LABEL] = _collect_preset_metrics(
        daily_metric_groups,
        numeric_cols,
        ("humid", "humidity"),
        ("lower", "low", "bottom", "indoor", "inside"),
    )
    presets[HUMIDITY_LOWER_PRESET_LABEL] = _collect_preset_metrics(
        daily_metric_groups,
        numeric_cols,
        ("humid", "humidity"),
        ("upper", "high", "higher", "top", "outdoor", "outside"),
    )

    return presets
