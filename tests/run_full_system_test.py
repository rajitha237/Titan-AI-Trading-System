"""Run TitanAI offline tests and optional live scanner smoke test."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(command: list[str]) -> int:
    print("\n$", " ".join(command), flush=True)
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also run Binance public live-data scanner smoke tests",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)

    print("=" * 56)
    print("TitanAI System Test Report")
    print("=" * 56)

    syntax_targets = [
        "app/research",
        "app/ai/market_regime_engine_v2.py",
        "app/ai/institutional_strategy_selector.py",
        "app/ai/research_confluence_engine.py",
        "app/ai/institutional_probability_engine.py",
        "app/ai/adaptive_score_engine.py",
        "app/trader/portfolio_scanner.py",
        "tests",
    ]

    compile_code = run_command(
        [sys.executable, "-m", "compileall", "-q", *syntax_targets]
    )
    if compile_code != 0:
        print("\nOVERALL STATUS: FAIL (syntax/import compilation)")
        return compile_code

    environment = os.environ.copy()
    if args.live:
        environment["TITANAI_RUN_LIVE_TESTS"] = "1"

    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    ]

    print("\n$", " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        check=False,
        env=environment,
    )

    print("\n" + "=" * 56)
    print(
        "OVERALL STATUS:",
        "PASS" if completed.returncode == 0 else "FAIL",
    )
    if not args.live:
        print(
            "Live scanner test skipped. Use --live after offline PASS."
        )
    print("=" * 56)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
