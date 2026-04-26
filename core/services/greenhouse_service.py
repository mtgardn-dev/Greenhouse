from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from core.daily_metrics import extract_daily_stat_groups, prepare_daily_dataframe
from core.services.config_store import AppConfig


@dataclass
class LoadResult:
    dataframe: pd.DataFrame
    time_col: str
    numeric_cols: list[str]
    daily_metric_groups: dict[str, dict[str, str]]


def capture_csv(config: AppConfig, timeout_seconds: int = 60) -> subprocess.CompletedProcess[str]:
    output_dir = Path(config.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    destination = str(output_dir) + "/"
    source = build_remote_source(config.device_username, config.device_address, config.remote_csv_path)
    command = build_capture_command(config, source, destination)

    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout_seconds)


def build_remote_source(username: str, device_address: str, remote_csv_path: str) -> str:
    host = device_address.split("@", 1)[-1].strip()
    user = username.strip() or device_address.split("@", 1)[0].strip()
    return f"{user}@{host}:{remote_csv_path}"


def build_capture_command(config: AppConfig, source: str, destination: str) -> list[str]:
    device_password = getattr(config, "device_password", "")
    if device_password.strip():
        sshpass_path = shutil.which("sshpass")
        if sshpass_path:
            return [
                sshpass_path,
                "-p",
                device_password,
                "scp",
                "-o",
                "StrictHostKeyChecking=accept-new",
                source,
                destination,
            ]

        raise RuntimeError(
            "A password was entered, but sshpass is not installed. "
            "Install sshpass or set up SSH key-based access for non-interactive capture."
        )

    return [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        source,
        destination,
    ]


def describe_capture_failure(stderr: str, stdout: str = "") -> str:
    error_text = stderr.strip() or stdout.strip() or "Unknown scp error"
    lower = error_text.lower()

    if "permission denied" in lower and "publickey" in lower:
        return (
            "SSH authentication failed. The Pi rejected the login for key-based access. "
            "Check that your SSH key is installed for the Pi user, the username is correct, "
            "and the remote path is reachable."
        )

    if "permission denied" in lower:
        return (
            "SSH permission was denied. Check the Pi SSH address, user name, and that the Pi accepts "
            "your SSH key or password."
        )

    return error_text


def load_csv(csv_path: Path) -> LoadResult:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    dataframe = pd.read_csv(csv_path)
    dataframe, time_col = prepare_daily_dataframe(dataframe)

    numeric_cols: list[str] = []
    for column in dataframe.columns:
        if column == time_col:
            continue

        converted = pd.to_numeric(dataframe[column], errors="coerce")
        if converted.notna().sum() > 0:
            dataframe[column] = converted
            numeric_cols.append(column)

    daily_metric_groups = extract_daily_stat_groups(dataframe.columns)
    return LoadResult(
        dataframe=dataframe,
        time_col=time_col,
        numeric_cols=numeric_cols,
        daily_metric_groups=daily_metric_groups,
    )


def filter_dataframe(
    dataframe: pd.DataFrame,
    time_col: str,
    selected_range: str,
    year_text: str,
    start_date: date | None = None,
    end_date: date | None = None,
    now: pd.Timestamp | None = None,
) -> pd.DataFrame:
    now = now or pd.Timestamp.now()
    filtered = dataframe.copy()

    if selected_range == "Last 30 days":
        start = now - pd.Timedelta(days=30)
        return filtered[filtered[time_col] >= start]

    if selected_range == "Last 3 months":
        start = now - pd.DateOffset(months=3)
        return filtered[filtered[time_col] >= start]

    if selected_range == "Year to date":
        start = pd.Timestamp(year=now.year, month=1, day=1)
        return filtered[filtered[time_col] >= start]

    if selected_range == "Specified year":
        try:
            year = int(year_text.strip())
        except ValueError as exc:
            raise ValueError("Enter a valid year, such as 2026.") from exc

        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year + 1, month=1, day=1)
        return filtered[(filtered[time_col] >= start) & (filtered[time_col] < end)]

    if selected_range == "Custom range":
        if start_date is None or end_date is None:
            raise ValueError("Select both a start date and an end date.")

        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        return filtered[(filtered[time_col] >= start) & (filtered[time_col] < end)]

    return filtered
