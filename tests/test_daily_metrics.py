from __future__ import annotations

import unittest

import pandas as pd

from core.daily_metrics import detect_date_column, extract_daily_stat_groups, prepare_daily_dataframe


class DailyMetricsTests(unittest.TestCase):
    def test_detect_date_column_prefers_date_like_names(self) -> None:
        columns = ["room", "recorded_date", "temperature_min"]

        self.assertEqual(detect_date_column(columns), "recorded_date")

    def test_extract_daily_stat_groups_normalizes_temperature_and_humidity(self) -> None:
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

        self.assertEqual(
            groups,
            {
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
            },
        )

    def test_prepare_daily_dataframe_sorts_and_drops_invalid_dates(self) -> None:
        df = pd.DataFrame(
            {
                "recorded_date": ["2026-04-03", "invalid", "2026-04-01"],
                "temp_min": [11.0, 12.0, 10.0],
            }
        )

        prepared, date_column = prepare_daily_dataframe(df)

        self.assertEqual(date_column, "recorded_date")
        self.assertEqual(list(prepared[date_column].dt.strftime("%Y-%m-%d")), ["2026-04-01", "2026-04-03"])


if __name__ == "__main__":
    unittest.main()
