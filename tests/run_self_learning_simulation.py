"""Run the deterministic Self-Learning v2 simulation."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_self_learning_simulation",
        "-v",
    ]

    print("=" * 64)
    print("TitanAI Self-Learning v2 Simulation")
    print("=" * 64)

    completed = subprocess.run(command, check=False)

    print("=" * 64)
    print(
        "OVERALL STATUS:",
        "PASS" if completed.returncode == 0 else "FAIL",
    )
    print("=" * 64)

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
