#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pprint import pprint
from app.operations.startup_launcher import launch_once_sync


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one validated TitanAI Testnet cycle"
    )
    parser.add_argument("--execute-trade", action="store_true")
    parser.add_argument("--scan-limit", type=int, default=5)
    args = parser.parse_args()
    result = launch_once_sync(
        execute_trade=args.execute_trade,
        scan_limit=max(1, args.scan_limit),
    )
    pprint(result)
    return 0 if result.get("status") not in {"error", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
