from __future__ import annotations

import pandas as pd

from core.daily_metrics import (
    METRIC_PRESET_LABELS,
    HUMIDITY_LOWER_PRESET_LABEL,
    HUMIDITY_UPPER_PRESET_LABEL,
    TEMPERATURE_LOWER_PRESET_LABEL,
    TEMPERATURE_UPPER_PRESET_LABEL,
    build_metric_presets,
    detect_date_column,
    extract_daily_stat_groups,
    prepare_daily_dataframe,
)


def test_detect_date_column_prefers_date_like_names() -> None:
    columns = ["room", "recorded_date", "temperature_min"]

    assert detect_date_column(columns) == "recorded_date"


def test_extract_daily_stat_groups_normalizes_temperature_and_humidity() -> None:
    columns = [
        "recorded_date",
        "temp_min",
        "temp_mean",
        "temp_max",
        "humidity_min",
        "humidity_mean",
        "humidity_max",
        "soil_moisture",
    ]

    groups = extract_daily_stat_groups(columns)

    assert groups == {
        "temperature": {
            "min": "temp_min",
            "mean": "temp_mean",
            "max": "temp_max",
        },
        "humidity": {
            "min": "humidity_min",
            "mean": "humidity_mean",
            "max": "humidity_max",
        },
    }


def test_prepare_daily_dataframe_sorts_and_drops_invalid_dates() -> None:
    df = pd.DataFrame(
        {
            "recorded_date": ["2026-04-03", "invalid", "2026-04-01"],
            "temp_min": [11.0, 12.0, 10.0],
        }
    )

    prepared, date_column = prepare_daily_dataframe(df)

    assert date_column == "recorded_date"
    assert list(prepared[date_column].dt.strftime("%Y-%m-%d")) == ["2026-04-01", "2026-04-03"]


def test_build_metric_presets_includes_upper_and_lower_temperature_and_humidity_sets() -> None:
    presets = build_metric_presets(
        numeric_cols=[
            "temp_upper_min",
            "temp_upper_mean",
            "temp_upper_max",
            "temp_lower_min",
            "temp_lower_mean",
            "temp_lower_max",
            "humidity_upper_min",
            "humidity_upper_mean",
            "humidity_upper_max",
            "humidity_lower_min",
            "humidity_lower_mean",
            "humidity_lower_max",
            "soil_moisture",
        ],
        daily_metric_groups={
            "temp_upper": {
                "min": "temp_upper_min",
                "mean": "temp_upper_mean",
                "max": "temp_upper_max",
            },
            "temp_lower": {
                "min": "temp_lower_min",
                "mean": "temp_lower_mean",
                "max": "temp_lower_max",
            },
            "humidity_upper": {
                "min": "humidity_upper_min",
                "mean": "humidity_upper_mean",
                "max": "humidity_upper_max",
            },
            "humidity_lower": {
                "min": "humidity_lower_min",
                "mean": "humidity_lower_mean",
                "max": "humidity_lower_max",
            },
        },
    )

    assert list(presets) == list(METRIC_PRESET_LABELS)
    assert presets[TEMPERATURE_UPPER_PRESET_LABEL] == [
        "temp_upper_min",
        "temp_upper_mean",
        "temp_upper_max",
    ]
    assert presets[TEMPERATURE_LOWER_PRESET_LABEL] == [
        "temp_lower_min",
        "temp_lower_mean",
        "temp_lower_max",
    ]
    assert presets[HUMIDITY_UPPER_PRESET_LABEL] == [
        "humidity_upper_min",
        "humidity_upper_mean",
        "humidity_upper_max",
    ]
    assert presets[HUMIDITY_LOWER_PRESET_LABEL] == [
        "humidity_lower_min",
        "humidity_lower_mean",
        "humidity_lower_max",
    ]
