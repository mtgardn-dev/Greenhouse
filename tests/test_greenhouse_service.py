from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from core.services.greenhouse_service import filter_dataframe, load_csv


class GreenhouseServiceTests(unittest.TestCase):
    def test_load_csv_detects_datetime_and_daily_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "greenhouse.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "recorded_date,temp_min,temp_mean,temp_max,humidity_min,humidity_mean,humidity_max,notes",
                        "2026-04-03,10,12,15,40,50,60,a",
                        "invalid,11,13,16,41,51,61,b",
                        "2026-04-01,9,11,14,39,49,59,c",
                    ]
                ),
                encoding="utf-8",
            )

            result = load_csv(csv_path)

            self.assertEqual(result.time_col, "recorded_date")
            self.assertEqual(list(result.dataframe[result.time_col].dt.strftime("%Y-%m-%d")), ["2026-04-01", "2026-04-03"])
            self.assertEqual(
                result.numeric_cols,
                [
                    "temp_min",
                    "temp_mean",
                    "temp_max",
                    "humidity_min",
                    "humidity_mean",
                    "humidity_max",
                ],
            )
            self.assertEqual(
                result.daily_metric_groups,
                {
                    "temperature": {"min": "temp_min", "mean": "temp_mean", "max": "temp_max"},
                    "humidity": {"min": "humidity_min", "mean": "humidity_mean", "max": "humidity_max"},
                },
            )

    def test_filter_dataframe_supports_specified_year(self) -> None:
        df = pd.DataFrame(
            {
                "recorded_date": pd.to_datetime(["2025-12-31", "2026-01-01", "2026-07-04"]),
                "temp_mean": [10.0, 11.0, 12.0],
            }
        )

        filtered = filter_dataframe(
            dataframe=df,
            time_col="recorded_date",
            selected_range="Specified year",
            year_text="2026",
            now=pd.Timestamp("2026-04-25"),
        )

        self.assertEqual(list(filtered["recorded_date"].dt.strftime("%Y-%m-%d")), ["2026-01-01", "2026-07-04"])

    def test_filter_dataframe_supports_custom_range(self) -> None:
        df = pd.DataFrame(
            {
                "recorded_date": pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"]),
                "temp_mean": [10.0, 11.0, 12.0],
            }
        )

        filtered = filter_dataframe(
            dataframe=df,
            time_col="recorded_date",
            selected_range="Custom range",
            year_text="",
            start_date=date(2026, 4, 2),
            end_date=date(2026, 4, 3),
        )

        self.assertEqual(list(filtered["recorded_date"].dt.strftime("%Y-%m-%d")), ["2026-04-02", "2026-04-03"])


if __name__ == "__main__":
    unittest.main()
