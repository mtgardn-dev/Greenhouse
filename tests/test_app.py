from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from core.app import MainWindow
from core.daily_metrics import (
    HUMIDITY_LOWER_PRESET_LABEL,
    HUMIDITY_UPPER_PRESET_LABEL,
    TEMPERATURE_LOWER_PRESET_LABEL,
    TEMPERATURE_UPPER_PRESET_LABEL,
    build_metric_presets,
)


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _build_window() -> MainWindow:
    _app()
    window = MainWindow()
    window.numeric_cols = [
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
    ]
    window.daily_metric_groups = {
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
    }
    window.populate_metric_list()
    window.metric_presets = build_metric_presets(window.numeric_cols, window.daily_metric_groups)
    return window


def test_apply_metric_preset_replaces_selected_metrics() -> None:
    window = _build_window()

    window.apply_metric_preset(TEMPERATURE_UPPER_PRESET_LABEL)
    upper_temp_metrics = window.selected_metrics()

    window.apply_metric_preset(HUMIDITY_UPPER_PRESET_LABEL)
    upper_humidity_metrics = window.selected_metrics()

    window.apply_metric_preset(TEMPERATURE_LOWER_PRESET_LABEL)
    lower_metrics = window.selected_metrics()

    assert upper_temp_metrics == [
        "temp_upper_min",
        "temp_upper_mean",
        "temp_upper_max",
    ]
    assert upper_humidity_metrics == [
        "humidity_upper_min",
        "humidity_upper_mean",
        "humidity_upper_max",
    ]
    assert lower_metrics == [
        "temp_lower_min",
        "temp_lower_mean",
        "temp_lower_max",
    ]


def test_clear_preset_button_clears_selection() -> None:
    window = _build_window()

    window.apply_metric_preset(HUMIDITY_UPPER_PRESET_LABEL)
    assert window.selected_metrics()

    window.clear_preset_button.click()

    assert window.selected_metrics() == []


def test_generate_graph_warns_when_no_data_loaded(monkeypatch) -> None:
    window = _build_window()
    window.dataframe = None
    window.time_col = None

    recorded: dict[str, str] = {}

    def fake_warning(parent, title, message):
        recorded["title"] = title
        recorded["message"] = message
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    window.generate_graph()

    assert recorded["title"] == "No data"
    assert "Load a CSV" in recorded["message"]


def test_generate_graph_clears_metrics_after_success(monkeypatch) -> None:
    window = _build_window()
    window.dataframe = window.dataframe or None
    window.time_col = "recorded_date"
    window.dataframe = __import__("pandas").DataFrame(
        {
            "recorded_date": __import__("pandas").to_datetime(["2026-04-01", "2026-04-02"]),
            "temp_upper_min": [10, 11],
            "temp_upper_mean": [12, 13],
            "temp_upper_max": [14, 15],
        }
    )
    window.numeric_cols = ["temp_upper_min", "temp_upper_mean", "temp_upper_max"]
    window.daily_metric_groups = {
        "temp_upper": {
            "min": "temp_upper_min",
            "mean": "temp_upper_mean",
            "max": "temp_upper_max",
        }
    }
    window.populate_metric_list()
    window.metric_presets = build_metric_presets(window.numeric_cols, window.daily_metric_groups)
    window.apply_metric_preset(TEMPERATURE_UPPER_PRESET_LABEL)

    class FakeDialog:
        def exec(self) -> int:
            return 1

    monkeypatch.setattr("core.app.GraphDialog", lambda *args, **kwargs: FakeDialog())

    window.generate_graph()

    assert window.selected_metrics() == []
