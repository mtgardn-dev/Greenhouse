from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


APP_DISPLAY_NAME = "Greenhouse Log Viewer"
APP_NAME = "GreenhouseLogViewer"
DEFAULT_BUILD_TAG = "v0.0.0"
DEFAULT_VERSION = "0.0.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BuildInfo:
    app_name: str = APP_NAME
    app_display_name: str = APP_DISPLAY_NAME
    version: str = DEFAULT_VERSION
    build_tag: str = DEFAULT_BUILD_TAG
    commit: str = "unknown"
    built_at_utc: str = "unknown"
    source: str = "source"


def _normalize_build_tag(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_BUILD_TAG
    return text if text.startswith(("v", "V")) else f"v{text}"


def _normalize_version(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_VERSION
    return text[1:] if text.startswith(("v", "V")) else text


def _build_info_from_payload(payload: dict[str, object], source: str = "packaged") -> BuildInfo:
    build_tag = _normalize_build_tag(payload.get("build_tag") or payload.get("tag") or payload.get("version"))
    version = _normalize_version(payload.get("version") or build_tag)
    commit = str(payload.get("commit") or "unknown").strip() or "unknown"
    built_at_utc = str(payload.get("built_at_utc") or "unknown").strip() or "unknown"
    app_name = str(payload.get("app_name") or APP_NAME).strip() or APP_NAME
    app_display_name = str(payload.get("app_display_name") or APP_DISPLAY_NAME).strip() or APP_DISPLAY_NAME

    return BuildInfo(
        app_name=app_name,
        app_display_name=app_display_name,
        version=version,
        build_tag=build_tag,
        commit=commit,
        built_at_utc=built_at_utc,
        source=source,
    )


def load_build_info_from_path(path: Path) -> BuildInfo:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Build metadata at {path} must be a JSON object.")
    return _build_info_from_payload(payload, source=str(path))


def _candidate_metadata_paths() -> list[Path]:
    candidates: list[Path] = []
    bundle_root = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else PROJECT_ROOT

    for root in (bundle_root, PROJECT_ROOT / "build"):
        candidates.append(root / "bootstrap_data" / "version.json")
        candidates.append(root / "version.json")

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate)
    return unique_candidates


def _git_build_info() -> BuildInfo:
    def run_git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()

    tag = run_git("describe", "--tags", "--abbrev=0") or run_git("describe", "--tags", "--always", "--dirty")
    build_tag = _normalize_build_tag(tag)
    version = _normalize_version(tag or build_tag)
    commit = run_git("rev-parse", "--short", "HEAD") or "unknown"

    return BuildInfo(
        version=version,
        build_tag=build_tag,
        commit=commit,
        source="git",
    )


def load_build_info() -> BuildInfo:
    for path in _candidate_metadata_paths():
        if not path.is_file():
            continue

        try:
            return load_build_info_from_path(path)
        except Exception:
            continue

    return _git_build_info()


def format_build_info_lines(info: BuildInfo) -> list[str]:
    return [
        f"Application: {info.app_display_name}",
        f"Version: {info.version}",
        f"Build tag: {info.build_tag}",
        f"Commit: {info.commit}",
        f"Built at UTC: {info.built_at_utc}",
    ]
