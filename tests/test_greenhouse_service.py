from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from core.services.greenhouse_service import build_capture_command, build_remote_source, capture_csv, describe_capture_failure, filter_dataframe, load_csv


def test_load_csv_detects_datetime_and_daily_groups(tmp_path: Path) -> None:
    csv_path = tmp_path / "greenhouse.csv"
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

    assert result.time_col == "recorded_date"
    assert list(result.dataframe[result.time_col].dt.strftime("%Y-%m-%d")) == ["2026-04-01", "2026-04-03"]
    assert result.numeric_cols == [
        "temp_min",
        "temp_mean",
        "temp_max",
        "humidity_min",
        "humidity_mean",
        "humidity_max",
    ]
    assert result.daily_metric_groups == {
        "temperature": {"min": "temp_min", "mean": "temp_mean", "max": "temp_max"},
        "humidity": {"min": "humidity_min", "mean": "humidity_mean", "max": "humidity_max"},
    }


def test_filter_dataframe_supports_specified_year() -> None:
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

    assert list(filtered["recorded_date"].dt.strftime("%Y-%m-%d")) == ["2026-01-01", "2026-07-04"]


def test_filter_dataframe_supports_custom_range() -> None:
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

    assert list(filtered["recorded_date"].dt.strftime("%Y-%m-%d")) == ["2026-04-02", "2026-04-03"]


def test_describe_capture_failure_translates_ssh_permission_denied() -> None:
    message = describe_capture_failure("Permission denied (publickey,password).")

    assert "SSH authentication failed" in message


def test_build_remote_source_uses_separate_username_and_host() -> None:
    source = build_remote_source("mtgardn", "192.168.1.200", "/home/mtgardn/greenhouse.csv")

    assert source == "mtgardn@192.168.1.200:/home/mtgardn/greenhouse.csv"


def test_build_remote_source_normalizes_legacy_combined_host() -> None:
    source = build_remote_source("mtgardn", "mtgardn@192.168.1.200", "/home/mtgardn/greenhouse.csv")

    assert source == "mtgardn@192.168.1.200:/home/mtgardn/greenhouse.csv"


def test_build_capture_command_prefers_sshpass_when_password_is_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.services.greenhouse_service.shutil.which", lambda _: "/usr/bin/sshpass")

    command = build_capture_command(
        config=type(
            "Config",
            (),
            {
                "device_username": "mtgardn",
                "device_address": "192.168.1.200",
                "device_password": "secret",
                "remote_csv_path": "/home/mtgardn/greenhouse.csv",
                "output_dir": str(tmp_path),
            },
        )(),
        source="mtgardn@192.168.1.200:/home/mtgardn/greenhouse.csv",
        destination=f"{tmp_path}/",
    )

    assert command[:3] == ["/usr/bin/sshpass", "-p", "secret"]
    assert command[3] == "scp"


def test_build_capture_command_requires_sshpass_for_password_auth(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.services.greenhouse_service.shutil.which", lambda _: None)

    with pytest.raises(RuntimeError, match="sshpass is not installed"):
        build_capture_command(
            config=type(
                "Config",
                (),
                {
                    "device_username": "mtgardn",
                    "device_address": "192.168.1.200",
                    "device_password": "secret",
                    "remote_csv_path": "/home/mtgardn/greenhouse.csv",
                    "output_dir": str(tmp_path),
                },
            )(),
            source="mtgardn@192.168.1.200:/home/mtgardn/greenhouse.csv",
            destination=f"{tmp_path}/",
        )


def test_build_capture_command_uses_batch_mode_without_password(tmp_path: Path) -> None:
    command = build_capture_command(
        config=type(
            "Config",
            (),
            {
                "device_username": "mtgardn",
                "device_address": "192.168.1.200",
                "device_password": "",
                "remote_csv_path": "/home/mtgardn/greenhouse.csv",
                "output_dir": str(tmp_path),
            },
        )(),
        source="mtgardn@192.168.1.200:/home/mtgardn/greenhouse.csv",
        destination=f"{tmp_path}/",
    )

    assert command[:4] == ["scp", "-o", "BatchMode=yes", "-o"]


def test_capture_csv_uses_batch_mode(monkeypatch, tmp_path: Path) -> None:
    recorded = {}

    def fake_run(command, capture_output, text, check, timeout):
        recorded["command"] = command
        recorded["capture_output"] = capture_output
        recorded["text"] = text
        recorded["check"] = check
        recorded["timeout"] = timeout

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("core.services.greenhouse_service.subprocess.run", fake_run)

    config_path = tmp_path / "logs"
    result = capture_csv(
        config=type(
            "Config",
            (),
            {
                "device_username": "mtgardn",
                "device_address": "192.168.1.200",
                "remote_csv_path": "/home/mtgardn/greenhouse.csv",
                "output_dir": str(config_path),
            },
        )(),
    )

    assert result.returncode == 0
    assert recorded["command"][:4] == ["scp", "-o", "BatchMode=yes", "-o"]
    assert "ConnectTimeout=15" in recorded["command"]
