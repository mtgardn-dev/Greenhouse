from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
    QScrollArea,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.daily_metrics import (
    METRIC_PRESET_LABELS,
    TEMPERATURE_LOWER_PRESET_LABEL,
    build_metric_presets,
)
from core.services.config_store import APP_NAME, APP_ORG, AppConfig, ConfigStore
from core.services.greenhouse_service import (
    capture_csv as capture_greenhouse_csv,
    describe_capture_failure,
    filter_dataframe as filter_greenhouse_dataframe,
    load_csv as load_greenhouse_csv,
)


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None, config: AppConfig, config_store: ConfigStore) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(650)
        self.config_store = config_store

        self.username_edit = QLineEdit(config.device_username)
        self.device_edit = QLineEdit(config.device_address)
        self.remote_csv_edit = QLineEdit(config.remote_csv_path)
        self.output_dir_edit = QLineEdit(config.output_dir)
        self.password_edit = QLineEdit(config.device_password)
        self.last_browse_dir = self.config_store.load_last_browse_dir()
        self.password_visible = False

        for widget in (self.username_edit, self.device_edit, self.remote_csv_edit, self.output_dir_edit):
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.password_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.password_edit.setEchoMode(QLineEdit.Password)

        self.password_toggle_button = QPushButton("Show")
        self.password_toggle_button.clicked.connect(self.toggle_password_visibility)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_output_dir)

        password_row = QHBoxLayout()
        password_row.addWidget(self.password_edit, 1)
        password_row.addWidget(self.password_toggle_button)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_edit, 1)
        output_row.addWidget(browse_button)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("Pi username:", self.username_edit)
        form.addRow("Pi host / address:", self.device_edit)
        form.addRow("Pi password:", password_row)
        form.addRow("Remote CSV path:", self.remote_csv_edit)
        form.addRow("Local output directory:", output_row)

        help_label = QLabel(
            "Example remote CSV path: /home/mtgardn/greenhouse_logs/greenhouse_daily_log.csv\n"
            "The Capture button will run: scp <Pi username>@<Pi host>:<Remote CSV path> <Local output directory>/\n"
            "If a password is entered, sshpass must be installed for non-interactive capture."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #555;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addLayout(form)
        layout.addWidget(help_label)
        layout.addWidget(buttons)

    def browse_output_dir(self) -> None:
        current = self.output_dir_edit.text().strip() or self.last_browse_dir or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", current)
        if directory:
            self.output_dir_edit.setText(directory)
            self.last_browse_dir = directory
            self.config_store.save_last_browse_dir(directory)

    def toggle_password_visibility(self) -> None:
        self.password_visible = not self.password_visible
        self.password_edit.setEchoMode(QLineEdit.Normal if self.password_visible else QLineEdit.Password)
        self.password_toggle_button.setText("Hide" if self.password_visible else "Show")

    def config(self) -> AppConfig:
        return AppConfig(
            device_username=self.username_edit.text().strip(),
            device_address=self.device_edit.text().strip(),
            device_password=self.password_edit.text(),
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


class GraphDialog(QDialog):
    def __init__(self, parent: QWidget | None, df: pd.DataFrame, time_col: str, metric_cols: list[str], title: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Graph")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        summary = QLabel(f"Metrics: {', '.join(metric_cols)}")
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.plot_canvas = PlotCanvas()
        self.plot_canvas.plot_metrics(df=df, time_col=time_col, metric_cols=metric_cols, title=title)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)

        layout.addWidget(summary)
        layout.addWidget(self.plot_canvas, stretch=1)
        layout.addWidget(buttons)


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
        self.metric_presets: dict[str, list[str]] = {label: [] for label in METRIC_PRESET_LABELS}

        self._build_ui()
        self.refresh_settings_display()
        self.log_status("Ready.")

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        main_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._build_status_scroll_area())
        main_layout.addWidget(self._build_controls_frame())

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
        self.log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(self.log_box)

        self.on_range_changed(self.range_combo.currentText())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setFrameShape(QFrame.StyledPanel)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(10)
        header_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

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
        return header

    def _build_status_frame(self) -> QGroupBox:
        self.status_frame = QGroupBox("Status / Configuration")
        self.status_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        status_layout = QGridLayout(self.status_frame)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.setHorizontalSpacing(12)
        status_layout.setVerticalSpacing(8)
        status_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.device_label = QLabel()
        self.username_label = QLabel()
        self.remote_file_label = QLabel()
        self.output_dir_label = QLabel()
        self.local_file_label = QLabel()
        self.rows_label = QLabel("No data loaded")

        for label in (self.username_label, self.device_label, self.remote_file_label, self.output_dir_label, self.local_file_label, self.rows_label):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        status_layout.addWidget(QLabel("Pi username:"), 0, 0)
        status_layout.addWidget(self.username_label, 0, 1)
        status_layout.addWidget(QLabel("Pi address:"), 1, 0)
        status_layout.addWidget(self.device_label, 1, 1)
        status_layout.addWidget(QLabel("Remote CSV:"), 2, 0)
        status_layout.addWidget(self.remote_file_label, 2, 1)
        status_layout.addWidget(QLabel("Output directory:"), 3, 0)
        status_layout.addWidget(self.output_dir_label, 3, 1)
        status_layout.addWidget(QLabel("Local CSV:"), 4, 0)
        status_layout.addWidget(self.local_file_label, 4, 1)
        status_layout.addWidget(QLabel("Loaded data:"), 5, 0)
        status_layout.addWidget(self.rows_label, 5, 1)

        status_layout.setColumnStretch(1, 1)
        return self.status_frame

    def _build_status_scroll_area(self) -> QScrollArea:
        status_scroll_area = QScrollArea()
        status_scroll_area.setWidgetResizable(True)
        status_scroll_area.setFrameShape(QFrame.NoFrame)
        status_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        status_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        status_scroll_area.setMinimumHeight(160)
        status_scroll_area.setWidget(self._build_status_frame())
        return status_scroll_area

    def _build_controls_frame(self) -> QGroupBox:
        controls = QGroupBox("Graph Options")
        controls.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)
        controls_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        date_row.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.range_combo = QComboBox()
        self.range_combo.addItems(["Last 30 days", "Last 3 months", "Year to date", "Specified year", "Custom range", "All data"])
        self.range_combo.currentTextChanged.connect(self.on_range_changed)

        self.year_edit = QLineEdit(str(date.today().year))
        self.year_edit.setMaximumWidth(100)
        self.year_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate(date.today().year, 1, 1))
        self.start_date_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.metric_list = QListWidget()
        self.metric_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.metric_list.setMinimumHeight(240)
        self.metric_list.setMaximumHeight(280)
        self.metric_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.metric_preset_combo = QComboBox()
        self.metric_preset_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.metric_preset_combo.addItems(METRIC_PRESET_LABELS)

        self.metric_preset_button = QPushButton("Apply Preset")
        self.metric_preset_button.clicked.connect(self.apply_selected_metric_preset)

        self.clear_preset_button = QPushButton("Clear Preset")
        self.clear_preset_button.clicked.connect(self.clear_metric_selection)

        date_row.addWidget(QLabel("Date window:"))
        date_row.addWidget(self.range_combo)
        date_row.addWidget(QLabel("Year:"))
        date_row.addWidget(self.year_edit)
        date_row.addWidget(QLabel("Start:"))
        date_row.addWidget(self.start_date_edit)
        date_row.addWidget(QLabel("End:"))
        date_row.addWidget(self.end_date_edit)
        date_row.addStretch(1)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(12)
        preset_row.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        preset_row.addWidget(QLabel("Metric set:"))
        preset_row.addWidget(self.metric_preset_combo, 1)
        preset_row.addWidget(self.metric_preset_button)
        preset_row.addWidget(self.clear_preset_button)
        preset_row.addStretch(1)

        controls_layout.addLayout(date_row)
        controls_layout.addLayout(preset_row)
        controls_layout.addWidget(QLabel("Metrics:"))
        controls_layout.addWidget(self.metric_list)

        return controls

    def refresh_settings_display(self) -> None:
        self.username_label.setText(self.config.device_username or "Not set")
        self.device_label.setText(self.config.device_address or "Not set")
        self.remote_file_label.setText(self.config.remote_csv_path or "Not set")
        self.output_dir_label.setText(self.config.output_dir or "Not set")
        self.local_file_label.setText(str(self.config.local_csv_path))

    def log_status(self, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_box.append(f"[{stamp}] {message}")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self, self.config, self.config_store)
        if dialog.exec() == QDialog.Accepted:
            new_config = dialog.config()
            if not new_config.device_username or not new_config.device_address or not new_config.remote_csv_path or not new_config.output_dir:
                QMessageBox.warning(self, "Missing settings", "Pi username, host/address, remote CSV path, and output directory are required.")
                return

            self.config = new_config
            self.config_store.save(self.config)
            self.refresh_settings_display()
            self.log_status("Settings saved.")

    def capture_csv(self) -> None:
        if (
            not self.config.device_username
            or not self.config.device_address
            or not self.config.remote_csv_path
            or not self.config.output_dir
        ):
            QMessageBox.warning(self, "Missing settings", "Open Settings and fill in the Pi username, host/address, remote CSV path, and output directory.")
            return

        self.log_status(f"Capturing CSV from {self.config.device_address}:{self.config.remote_csv_path}")

        try:
            result = capture_greenhouse_csv(self.config)
        except subprocess.TimeoutExpired:
            self.log_status("Capture failed: scp timed out.")
            QMessageBox.critical(self, "Capture failed", "scp timed out.")
            return
        except FileNotFoundError:
            self.log_status("Capture failed: scp command not found.")
            QMessageBox.critical(self, "Capture failed", "scp command not found on this Mac.")
            return
        except RuntimeError as exc:
            self.log_status(f"Capture failed: {exc}")
            QMessageBox.critical(self, "Capture failed", str(exc))
            return

        if result.returncode != 0:
            error_text = describe_capture_failure(result.stderr, result.stdout)
            self.log_status(f"Capture failed: {error_text}")
            QMessageBox.critical(self, "Capture failed", error_text)
            return

        self.refresh_settings_display()
        self.log_status(f"Capture complete: {self.config.local_csv_path}")
        self.load_csv(self.config.local_csv_path)

    def load_csv(self, csv_path: Path) -> None:
        try:
            result = load_greenhouse_csv(csv_path)
        except FileNotFoundError:
            self.log_status(f"Local CSV not found: {csv_path}")
            return
        except Exception as exc:
            self.log_status(f"Failed to read CSV: {exc}")
            QMessageBox.critical(self, "CSV error", f"Failed to read CSV:\n{exc}")
            return

        self.dataframe = result.dataframe
        self.time_col = result.time_col
        self.numeric_cols = result.numeric_cols
        self.daily_metric_groups = result.daily_metric_groups
        self.rows_label.setText(f"{len(result.dataframe):,} rows, timestamp column: {result.time_col}")
        self.populate_metric_list()
        self.refresh_metric_presets()
        self.apply_default_metric_preset()
        self.log_status(
            f"Loaded CSV: {len(result.dataframe):,} rows; {len(result.numeric_cols)} numeric metrics found; "
            f"{len(result.daily_metric_groups)} daily metric groups detected."
        )

    def populate_metric_list(self) -> None:
        self.metric_list.clear()

        for col in self.numeric_cols:
            item = QListWidgetItem(col)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.metric_list.addItem(item)

    def selected_metrics(self) -> list[str]:
        selected: list[str] = []
        seen: set[str] = set()

        for item in self.metric_list.selectedItems():
            if item.text() not in seen:
                selected.append(item.text())
                seen.add(item.text())

        for index in range(self.metric_list.count()):
            item = self.metric_list.item(index)
            if item.checkState() == Qt.Checked and item.text() not in seen:
                selected.append(item.text())
                seen.add(item.text())

        return selected

    def refresh_metric_presets(self) -> None:
        current_label = self.metric_preset_combo.currentText()
        self.metric_presets = build_metric_presets(self.numeric_cols, self.daily_metric_groups)

        self.metric_preset_combo.blockSignals(True)
        self.metric_preset_combo.clear()
        for label in METRIC_PRESET_LABELS:
            self.metric_preset_combo.addItem(label)
        self.metric_preset_combo.setCurrentText(current_label if current_label in self.metric_presets else TEMPERATURE_LOWER_PRESET_LABEL)
        self.metric_preset_combo.blockSignals(False)

    def apply_selected_metric_preset(self) -> None:
        self.apply_metric_preset(self.metric_preset_combo.currentText())

    def apply_default_metric_preset(self) -> None:
        self.metric_preset_combo.setCurrentText(TEMPERATURE_LOWER_PRESET_LABEL)
        self.apply_metric_preset(TEMPERATURE_LOWER_PRESET_LABEL)

    def apply_metric_preset(self, label: str) -> None:
        metric_names = self.metric_presets.get(label, [])
        selected = set(metric_names)
        self.metric_list.clearSelection()
        for index in range(self.metric_list.count()):
            item = self.metric_list.item(index)
            item.setCheckState(Qt.Checked if item.text() in selected else Qt.Unchecked)
            item.setSelected(item.text() in selected)

    def clear_metric_selection(self) -> None:
        self.metric_list.clearSelection()
        for index in range(self.metric_list.count()):
            item = self.metric_list.item(index)
            item.setCheckState(Qt.Unchecked)

    def on_range_changed(self, text: str) -> None:
        year_mode = text == "Specified year"
        custom_mode = text == "Custom range"
        self.year_edit.setEnabled(year_mode)
        self.start_date_edit.setEnabled(custom_mode)
        self.end_date_edit.setEnabled(custom_mode)

    def filtered_dataframe(self) -> Optional[pd.DataFrame]:
        if self.dataframe is None or self.time_col is None:
            return None

        selected_range = self.range_combo.currentText()
        try:
            start_date = self._qdate_to_date(self.start_date_edit.date()) if selected_range == "Custom range" else None
            end_date = self._qdate_to_date(self.end_date_edit.date()) if selected_range == "Custom range" else None
            return filter_greenhouse_dataframe(
                dataframe=self.dataframe,
                time_col=self.time_col,
                selected_range=selected_range,
                year_text=self.year_edit.text(),
                start_date=start_date,
                end_date=end_date,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid date range", str(exc))
            return None

    def generate_graph(self) -> None:
        df = self.filtered_dataframe()
        if df is None:
            QMessageBox.warning(self, "No data", "Load a CSV before graphing metrics.")
            self.log_status("Graph requested but no CSV data is loaded.")
            return

        metrics = self.selected_metrics()
        if not metrics:
            QMessageBox.warning(self, "No metrics selected", "Select at least one metric to graph.")
            return

        if df.empty:
            QMessageBox.warning(self, "No data", "No rows match the selected date window.")
            return

        dialog = GraphDialog(
            self,
            df=df,
            time_col=self.time_col,
            metric_cols=metrics,
            title=f"Greenhouse Metrics - {self.range_combo.currentText()}",
        )
        self._graph_dialog = dialog
        dialog.exec()
        self.log_status(f"Graph generated for {len(df):,} rows and metrics: {', '.join(metrics)}")
        self.clear_metric_selection()

    @staticmethod
    def _qdate_to_date(value: QDate) -> date:
        return date(value.year(), value.month(), value.day())


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORG)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()
    return app.exec()
