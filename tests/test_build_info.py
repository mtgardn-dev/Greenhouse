from __future__ import annotations

import json
from pathlib import Path

from core.build_info import format_build_info_lines, load_build_info_from_path


def test_load_build_info_from_path_reads_packaged_metadata(tmp_path: Path) -> None:
    metadata_path = tmp_path / "version.json"
    metadata_path.write_text(
        json.dumps(
            {
                "app_name": "GreenhouseLogViewer",
                "app_display_name": "Greenhouse Log Viewer",
                "build_tag": "v0.0.1",
                "version": "0.0.1",
                "commit": "abc1234",
                "built_at_utc": "2026-04-27T12:34:56Z",
            }
        ),
        encoding="utf-8",
    )

    info = load_build_info_from_path(metadata_path)

    assert info.app_name == "GreenhouseLogViewer"
    assert info.app_display_name == "Greenhouse Log Viewer"
    assert info.build_tag == "v0.0.1"
    assert info.version == "0.0.1"
    assert info.commit == "abc1234"
    assert info.built_at_utc == "2026-04-27T12:34:56Z"


def test_format_build_info_lines_includes_version_details() -> None:
    lines = format_build_info_lines(
        load_build_info_from_path(
            Path(__file__).parent / "fixtures" / "build_info.json"
        )
    )

    assert "Application: Greenhouse Log Viewer" in lines
    assert "Version: 0.0.1" in lines
    assert "Build tag: v0.0.1" in lines
    assert "Commit: abc1234" in lines
