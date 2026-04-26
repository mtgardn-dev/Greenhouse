from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings


APP_ORG = "GardnerGreenhouse"
APP_NAME = "GreenhouseLogViewer"


@dataclass
class AppConfig:
    device_address: str = "192.168.1.200"
    device_username: str = "mtgardn"
    device_password: str = ""
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
        saved_device_address = self.settings.value("device_address", "192.168.1.200")
        saved_device_username = self.settings.value("device_username", "mtgardn")
        if "@" in saved_device_address:
            legacy_username, legacy_address = saved_device_address.split("@", 1)
            if not saved_device_username or saved_device_username == legacy_username:
                saved_device_username = legacy_username
                saved_device_address = legacy_address

        return AppConfig(
            device_address=saved_device_address,
            device_username=saved_device_username,
            device_password=self.settings.value("device_password", ""),
            remote_csv_path=self.settings.value("remote_csv_path", ""),
            output_dir=self.settings.value("output_dir", str(Path.home() / "GreenhouseLogs")),
        )

    def save(self, config: AppConfig) -> None:
        self.settings.setValue("device_address", config.device_address)
        self.settings.setValue("device_username", config.device_username)
        self.settings.setValue("device_password", config.device_password)
        self.settings.setValue("remote_csv_path", config.remote_csv_path)
        self.settings.setValue("output_dir", config.output_dir)

    def load_last_browse_dir(self) -> str:
        return self.settings.value("last_browse_dir", str(Path.home()))

    def save_last_browse_dir(self, directory: str) -> None:
        self.settings.setValue("last_browse_dir", directory)
