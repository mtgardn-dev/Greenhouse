from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings


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

