"""TitanAI Deployment Checklist v35.3."""

from __future__ import annotations

from pathlib import Path
from typing import Any


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)


def build_deployment_checklist(
    *,
    project_root: Path | str | None = None,
) -> dict:
    root = Path(
        project_root or PROJECT_ROOT
    )

    required_paths = {
        "runner": (
            root
            / "app"
            / "trader"
            / "auto_testnet_runner.py"
        ),
        "requirements": (
            root / "requirements.txt"
        ),
        "env_example": (
            root / ".env.example"
        ),
        "tests": (
            root / "tests"
        ),
        "data_directory": (
            root / "app" / "data"
        ),
        "backup_directory": (
            root / "app" / "backups"
        ),
    }

    checks = {
        name: path.exists()
        for name, path in (
            required_paths.items()
        )
    }

    warnings = []

    if not checks["backup_directory"]:
        warnings.append(
            "Backup directory has not been "
            "created yet"
        )

    critical = {
        name: checks[name]
        for name in (
            "runner",
            "requirements",
            "env_example",
            "tests",
        )
    }

    ready = all(
        critical.values()
    )

    return {
        "status": (
            "ready"
            if ready
            else "blocked"
        ),
        "version": "v35.3",
        "ready": ready,
        "project_root": str(root),
        "checks": checks,
        "paths": {
            name: str(path)
            for name, path in (
                required_paths.items()
            )
        },
        "warnings": warnings,
        "testnet_only": True,
    }
