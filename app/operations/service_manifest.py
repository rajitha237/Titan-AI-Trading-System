"""TitanAI Service Manifest v35.3."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def build_service_manifest(
    *,
    project_root: Path | str,
    interval_seconds: int = 300,
) -> dict:
    root = Path(project_root).resolve()
    python_path = (
        root / ".venv-1" / "bin" / "python"
    )

    if not python_path.exists():
        python_path = Path(
            sys.executable
        )

    return {
        "version": "v35.3",
        "service_name": (
            "com.titanai.testnet"
        ),
        "project_root": str(root),
        "python_path": str(
            python_path
        ),
        "working_directory": str(root),
        "launcher_module": (
            "app.operations.startup_launcher"
        ),
        "interval_seconds": max(
            60,
            int(interval_seconds),
        ),
        "testnet_only": True,
        "mainnet_supported": False,
    }


def write_service_manifest(
    *,
    project_root: Path | str,
    destination: Path | str,
    interval_seconds: int = 300,
) -> dict:
    manifest = build_service_manifest(
        project_root=project_root,
        interval_seconds=(
            interval_seconds
        ),
    )

    destination = Path(destination)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    destination.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": "success",
        "version": "v35.3",
        "destination": str(
            destination
        ),
        "manifest": manifest,
    }
