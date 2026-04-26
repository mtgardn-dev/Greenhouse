#!/usr/bin/env python3
"""
Greenhouse Log Viewer

Qt6 desktop app for retrieving a Home Assistant greenhouse CSV log from a Raspberry Pi
and graphing selected metrics over a chosen date range.

Recommended install on macOS:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install PySide6 pandas matplotlib

Run:

    python greenhouse_log_viewer.py

Notes:
- Uses scp to retrieve the CSV from the Raspberry Pi.
- Assumes SSH access is already configured, e.g. mtgardn@192.168.1.200.
- Stores settings in macOS user settings through QSettings.
"""

from __future__ import annotations

import sys
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from PySide6.QtCore import Qt, QSettings, QDate
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.daily_metrics import extract_daily_stat_groups, prepare_daily_dataframe


APP_ORG = "GardnerGreenhouse"
APP_NAME = "GreenhouseLogViewer"


@dataclass
class AppConfig:
    device_address: str = "mtgardn@192.168.1.200"
    remote_csv_path: str = ""
    output_dir: str = str(Path.home() / "GreenhouseLogs")

    @property
    def local_csv_path(self) -> Path:
        remote_name = Path(self.remote_csv_path).name or "greenhouse_log.csv"
        return Path(self.output_dir).expanduser() / remote_name


class ConfigStore:
    def __init__(self) -> None:
        self.settings = QSettings(APP_ORG, APP_NAME)

    def load(self) -> AppConfig:
        return AppConfig(
            device_address=self.settings.value("device_address", "mtgardn@192.168.1.200"),
            remote_csv_path=self.settings.value("remote_csv_path", ""),
            output_dir=self.settings.value("output_dir", str(Path.home() / "GreenhouseLogs")),
        )

    def save(self, config: AppConfig) -> None:
        self.settings.setValue("device_address", config.device_address)
        self.settings.setValue("remote_csv_path", config.remote_csv_path)
        self.settings.setValue("output_dir", config.output_dir)


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None, config: AppConfig) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(650)

        self.device_edit = QLineEdit(config.device_address)
        self.remote_csv_edit = QLineEdit(config.remote_csv_path)
        self.output_dir_edit = QLineEdit(config.output_dir)

        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self.browse_output_dir)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_edit, 1)
        output_row.addWidget(browse_button)

        form = QFormLayout()
        form.addRow("Pi SSH address:", self.device_edit)
        form.addRow("Remote CSV path:", self.remote_csv_edit)
        form.addRow("Local output directory:", output_row)

        help_label = QLabel(
            "Example remote CSV path: /home/mtgardn/greenhouse_logs/greenhouse_daily_log.csv\n"
            "The Capture button will run: scp <Pi SSH address>:<Remote CSV path> <Local output directory>/"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #555;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(help_label)
        layout.addWidget(buttons)

    def browse_output_dir(self) -> None:
        current = self.output_dir_edit.text().strip() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", current)
        if directory:
            self.output_dir_edit.setText(directory)

    def config(self) -> AppConfig:
        return AppConfig(
            device_address=self.device_edit.text().strip(),
            remote_csv_path=self.remote_csv_edit.text().strip(),
            output_dir=self.output_dir_edit.text().strip(),
        )


class PlotCanvas(FigureCanvas):
    def __init__(self) -> None:
        self.figure = Figure(figsize=(10, 6), constrained_layout=True)
        super().__init__(self.figure)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def clear_plot(self) -> None:
        self.figure.clear()
        self.draw_idle()

    def plot_metrics(self, df: pd.DataFrame, time_col: str, metric_cols: list[str], title: str) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        for col in metric_cols:
            ax.plot(df[time_col], df[col], label=col)

        ax.set_title(title)
        ax.set_xlabel("Date / Time")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        self.figure.autofmt_xdate()
        self.draw_idle()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Greenhouse Log Viewer")
        self.resize(1200, 800)

        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.dataframe: Optional[pd.DataFrame] = None
        self.time_col: Optional[str] = None
        self.numeric_cols: list[str] = []
        self.daily_metric_groups: dict[str, dict[str, str]] = {}

        self._build_ui()
        self.refresh_settings_display()
        self.log_status("Ready.")

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)

        header = QFrame()
        header.setFrameShape(QFrame.StyledPanel)
        header_layout = QHBoxLayout(header)

        title = QLabel("Greenhouse Log Viewer")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.open_settings)

        capture_button = QPushButton("Capture")
        capture_button.clicked.connect(self.capture_csv)

        graph_button = QPushButton("Graph")
        graph_button.clicked.connect(self.generate_graph)

        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.close)

        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(settings_button)
        header_layout.addWidget(capture_button)
        header_layout.addWidget(graph_button)
        header_layout.addWidget(exit_button)

        main_layout.addWidget(header)

        self.status_frame = QGroupBox("Status / Configuration")
        status_layout = QGridLayout(self.status_frame)

        self.device_label = QLabel()
        self.remote_file_label = QLabel()
        self.output_dir_label = QLabel()
        self.local_file_label = QLabel()
        self.rows_label = QLabel("No data loaded")

        status_layout.addWidget(QLabel("Pi address:"), 0, 0)
        status_layout.addWidget(self.device_label, 0, 1)
        status_layout.addWidget(QLabel("Remote CSV:"), 1, 0)
        status_layout.addWidget(self.remote_file_label, 1, 1)
        status_layout.addWidget(QLabel("Output directory:"), 2, 0)
        status_layout.addWidget(self.output_dir_label, 2, 1)
        status_layout.addWidget(QLabel("Local CSV:"), 3, 0)
        status_layout.addWidget(self.local_file_label, 3, 1)
        status_layout.addWidget(QLabel("Loaded data:"), 4, 0)
        status_layout.addWidget(self.rows_label, 4, 1)

        main_layout.addWidget(self.status_frame)

        controls = QGroupBox("Graph Options")
        controls_layout = QGridLayout(controls)

        self.range_combo = QComboBox()
        self.range_combo.addItems(["Last 30 days", "Last 3 months", "Year to date", "Specified year", "Custom range", "All data"])
        self.range_combo.currentTextChanged.connect(self.on_range_changed)

        self.year_edit = QLineEdit(str(date.today().year))
        self.year_edit.setMaximumWidth(100)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate(date.today().year, 1, 1))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())

        self.metric_list = QListWidget()
        self.metric_list.setSelectionMode(QListWidget.MultiSelection)
        self.metric_list.setMinimumHeight(90)

        controls_layout.addWidget(QLabel("Date window:"), 0, 0)
        controls_layout.addWidget(self.range_combo, 0, 1)
        controls_layout.addWidget(QLabel("Year:"), 0, 2)
        controls_layout.addWidget(self.year_edit, 0, 3)
        controls_layout.addWidget(QLabel("Start:"), 1, 0)
        controls_layout.addWidget(self.start_date_edit, 1, 1)
        controls_layout.addWidget(QLabel("End:"), 1, 2)
        controls_layout.addWidget(self.end_date_edit, 1, 3)
        controls_layout.addWidget(QLabel("Metrics:"), 2, 0)
        controls_layout.addWidget(self.metric_list, 2, 1, 1, 3)

        main_layout.addWidget(controls)

        self.plot_canvas = PlotCanvas()
        main_layout.addWidget(self.plot_canvas, stretch=1)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
        main_layout.addWidget(self.log_box)

        self.on_range_changed(self.range_combo.currentText())

    def refresh_settings_display(self) -> None:
        self.device_label.setText(self.config.device_address or "Not set")
        self.remote_file_label.setText(self.config.remote_csv_path or "Not set")
        self.output_dir_label.setText(self.config.output_dir or "Not set")
        self.local_file_label.setText(str(self.config.local_csv_path))

    def log_status(self, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_box.append(f"[{stamp}] {message}")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self, self.config)
        if dialog.exec() == QDialog.Accepted:
            new_config = dialog.config()
            if not new_config.device_address or not new_config.remote_csv_path or not new_config.output_dir:
                QMessageBox.warning(self, "Missing settings", "Pi address, remote CSV path, and output directory are required.")
                return
            self.config = new_config
            self.config_store.save(self.config)
            self.refresh_settings_display()
            self.log_status("Settings saved.")

    def capture_csv(self) -> None:
        if not self.config.device_address or not self.config.remote_csv_path or not self.config.output_dir:
            QMessageBox.warning(self, "Missing settings", "Open Settings and fill in the Pi address, remote CSV path, and output directory.")
            return

        output_dir = Path(self.config.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        source = f"{self.config.device_address}:{self.config.remote_csv_path}"
        destination = str(output_dir) + "/"
        command = ["scp", source, destination]

        self.log_status(f"Capturing CSV from {source}")

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
        except subprocess.TimeoutExpired:
            self.log_status("Capture failed: scp timed out.")
            QMessageBox.critical(self, "Capture failed", "scp timed out.")
            return
        except FileNotFoundError:
            self.log_status("Capture failed: scp command not found.")
            QMessageBox.critical(self, "Capture failed", "scp command not found on this Mac.")
            return

        if result.returncode != 0:
            error_text = result.stderr.strip() or result.stdout.strip() or "Unknown scp error"
            self.log_status(f"Capture failed: {error_text}")
            QMessageBox.critical(self, "Capture failed", error_text)
            return

        self.refresh_settings_display()
        self.log_status(f"Capture complete: {self.config.local_csv_path}")
        self.load_csv(self.config.local_csv_path)

    def load_csv(self, csv_path: Path) -> None:
        if not csv_path.exists():
            self.log_status(f"Local CSV not found: {csv_path}")
            return

        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            self.log_status(f"Failed to read CSV: {exc}")
            QMessageBox.critical(self, "CSV error", f"Failed to read CSV:\n{exc}")
            return

        try:
            df, time_col = prepare_daily_dataframe(df)
        except ValueError:
            self.log_status("No timestamp/date column detected.")
            QMessageBox.warning(self, "CSV error", "Could not detect a timestamp/date column.")
            return

        numeric_cols = []
        for col in df.columns:
            if col == time_col:
                continue
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() > 0:
                df[col] = converted
                numeric_cols.append(col)

        self.dataframe = df
        self.time_col = time_col
        self.numeric_cols = numeric_cols
        self.daily_metric_groups = extract_daily_stat_groups(df.columns)
        self.rows_label.setText(f"{len(df):,} rows, timestamp column: {time_col}")
        self.populate_metric_list()
        self.log_status(
            f"Loaded CSV: {len(df):,} rows; {len(numeric_cols)} numeric metrics found; "
            f"{len(self.daily_metric_groups)} daily metric groups detected."
        )

    def detect_time_column(self, df: pd.DataFrame) -> Optional[str]:
        candidates = ["last_changed", "last_updated", "time", "timestamp", "date", "datetime"]
        lower_map = {col.lower().strip(): col for col in df.columns}

        for candidate in candidates:
            for lower, original in lower_map.items():
                if candidate in lower:
                    return original
        return df.columns[0] if len(df.columns) else None

    def populate_metric_list(self) -> None:
        self.metric_list.clear()
        preferred = ["temp", "temperature", "humid", "humidity"]

        for col in self.numeric_cols:
            item = QListWidgetItem(col)
            col_lower = col.lower()
            if any(token in col_lower for token in preferred):
                item.setSelected(True)
            self.metric_list.addItem(item)

    def selected_metrics(self) -> list[str]:
        return [item.text() for item in self.metric_list.selectedItems()]

    def on_range_changed(self, text: str) -> None:
        year_mode = text == "Specified year"
        custom_mode = text == "Custom range"
        self.year_edit.setEnabled(year_mode)
        self.start_date_edit.setEnabled(custom_mode)
        self.end_date_edit.setEnabled(custom_mode)

    def filtered_dataframe(self) -> Optional[pd.DataFrame]:
        if self.dataframe is None or self.time_col is None:
            self.load_csv(self.config.local_csv_path)

        if self.dataframe is None or self.time_col is None:
            return None

        df = self.dataframe.copy()
        now = pd.Timestamp.now()
        selected_range = self.range_combo.currentText()

        if selected_range == "Last 30 days":
            start = now - pd.Timedelta(days=30)
            df = df[df[self.time_col] >= start]
        elif selected_range == "Last 3 months":
            start = now - pd.DateOffset(months=3)
            df = df[df[self.time_col] >= start]
        elif selected_range == "Year to date":
            start = pd.Timestamp(year=now.year, month=1, day=1)
            df = df[df[self.time_col] >= start]
        elif selected_range == "Specified year":
            try:
                year = int(self.year_edit.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid year", "Enter a valid year, such as 2026.")
                return None
            start = pd.Timestamp(year=year, month=1, day=1)
            end = pd.Timestamp(year=year + 1, month=1, day=1)
            df = df[(df[self.time_col] >= start) & (df[self.time_col] < end)]
        elif selected_range == "Custom range":
            start_qdate = self.start_date_edit.date()
            end_qdate = self.end_date_edit.date()
            start = pd.Timestamp(start_qdate.year(), start_qdate.month(), start_qdate.day())
            end = pd.Timestamp(end_qdate.year(), end_qdate.month(), end_qdate.day()) + pd.Timedelta(days=1)
            df = df[(df[self.time_col] >= start) & (df[self.time_col] < end)]

        return df

    def generate_graph(self) -> None:
        df = self.filtered_dataframe()
        if df is None:
            return

        metrics = self.selected_metrics()
        if not metrics:
            QMessageBox.warning(self, "No metrics selected", "Select at least one metric to graph.")
            return

        if df.empty:
            QMessageBox.warning(self, "No data", "No rows match the selected date window.")
            return

        self.plot_canvas.plot_metrics(
            df=df,
            time_col=self.time_col,
            metric_cols=metrics,
            title=f"Greenhouse Metrics — {self.range_combo.currentText()}",
        )
        self.log_status(f"Graph generated for {len(df):,} rows and metrics: {', '.join(metrics)}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORG)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
