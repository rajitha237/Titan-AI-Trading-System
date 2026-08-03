"""Continuous autonomous Binance Futures testnet service.

Default mode is analysis-only. Testnet order submission requires an explicit
``--execute-trades`` flag.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.service.graceful_shutdown import (
    ShutdownController,
)
from app.service.health_monitor import (
    evaluate_service_health,
)
from app.service.heartbeat import (
    write_heartbeat,
)
from app.service.scheduler import (
    DEFAULT_INTERVAL_SECONDS,
    normalize_interval,
    sleep_until_next_cycle,
)
from app.trader.auto_testnet_runner import (
    run_auto_testnet_cycle,
)

SERVICE_LOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "service"
    / "autonomous_cycles.jsonl"
)

DEFAULT_BALANCE = 30.0
DEFAULT_RISK_PERCENT = 1.0
DEFAULT_LEVERAGE = 5.0
DEFAULT_SCAN_LIMIT = 20
DEFAULT_MAXIMUM_CONSECUTIVE_ERRORS = 5


@dataclass(frozen=True)
class AutonomousServiceConfig:
    execute_trade: bool = False
    interval_seconds: float = (
        DEFAULT_INTERVAL_SECONDS
    )
    balance: float = DEFAULT_BALANCE
    risk_percent: float = (
        DEFAULT_RISK_PERCENT
    )
    leverage: float = DEFAULT_LEVERAGE
    scan_limit: int = DEFAULT_SCAN_LIMIT
    maximum_cycles: int | None = None
    maximum_consecutive_errors: int = (
        DEFAULT_MAXIMUM_CONSECUTIVE_ERRORS
    )

    def normalized(self) -> "AutonomousServiceConfig":
        maximum_cycles = self.maximum_cycles

        if maximum_cycles is not None:
            maximum_cycles = max(
                1,
                int(maximum_cycles),
            )

        return AutonomousServiceConfig(
            execute_trade=bool(
                self.execute_trade
            ),
            interval_seconds=normalize_interval(
                self.interval_seconds
            ),
            balance=max(
                0.0,
                float(self.balance),
            ),
            risk_percent=max(
                0.0,
                float(self.risk_percent),
            ),
            leverage=max(
                0.0,
                float(self.leverage),
            ),
            scan_limit=max(
                1,
                min(
                    int(self.scan_limit),
                    100,
                ),
            ),
            maximum_cycles=maximum_cycles,
            maximum_consecutive_errors=max(
                1,
                int(
                    self.maximum_consecutive_errors
                ),
            ),
        )


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


def _append_cycle_log(
    record: dict,
) -> None:
    SERVICE_LOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SERVICE_LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


def _cycle_summary(
    *,
    cycle_number: int,
    result: dict,
    health: dict,
    execute_trade: bool,
) -> dict:
    execution = result.get("execution")
    execution = (
        execution
        if isinstance(execution, dict)
        else {}
    )

    return {
        "timestamp": _utc_now(),
        "cycle_number": cycle_number,
        "execute_trade": execute_trade,
        "status": result.get("status"),
        "mode": result.get("mode"),
        "symbol": result.get("symbol"),
        "cycle_id": result.get("cycle_id"),
        "learning_status": result.get(
            "learning_status"
        ),
        "learning_adjustment": result.get(
            "learning_adjustment",
            0.0,
        ),
        "execution_submitted": bool(
            execution.get(
                "submitted",
                False,
            )
        ),
        "execution_status": execution.get(
            "status"
        ),
        "health": health,
    }


async def run_autonomous_service(
    config: AutonomousServiceConfig,
    *,
    shutdown_controller: (
        ShutdownController | None
    ) = None,
) -> dict:
    """Run non-overlapping cycles until shutdown or configured limit."""
    config = config.normalized()
    controller = (
        shutdown_controller
        or ShutdownController()
    )

    installed_signals: list[str] = []

    try:
        installed_signals = (
            controller.install_signal_handlers()
        )
    except RuntimeError:
        installed_signals = []

    cycle_number = 0
    consecutive_errors = 0
    last_result: dict = {}
    stop_reason = "completed"

    write_heartbeat(
        status="starting",
        cycle_number=cycle_number,
        execute_trade=config.execute_trade,
        interval_seconds=(
            config.interval_seconds
        ),
    )

    while not controller.requested:
        cycle_number += 1

        try:
            result = await run_auto_testnet_cycle(
                execute_trade=(
                    config.execute_trade
                ),
                balance=config.balance,
                risk_percent=(
                    config.risk_percent
                ),
                leverage=config.leverage,
                scan_limit=config.scan_limit,
            )

            if not isinstance(result, dict):
                raise RuntimeError(
                    "Auto Testnet Runner returned "
                    "a non-dictionary result"
                )

            last_result = result

            if (
                str(
                    result.get(
                        "status",
                        "",
                    )
                ).lower()
                == "error"
            ):
                consecutive_errors += 1
            else:
                consecutive_errors = 0

        except Exception as error:
            consecutive_errors += 1
            last_result = {
                "status": "error",
                "mode": "SERVICE_BOUNDARY",
                "reason": (
                    "Autonomous service caught "
                    "an unhandled cycle exception"
                ),
                "error": str(error),
                "execution": {
                    "status": "error",
                    "submitted": False,
                    "mode": "SERVICE_BOUNDARY",
                },
            }

        health = evaluate_service_health(
            result=last_result,
            consecutive_errors=(
                consecutive_errors
            ),
            maximum_consecutive_errors=(
                config.maximum_consecutive_errors
            ),
        )

        _append_cycle_log(
            _cycle_summary(
                cycle_number=cycle_number,
                result=last_result,
                health=health,
                execute_trade=(
                    config.execute_trade
                ),
            )
        )

        write_heartbeat(
            status=health["status"],
            cycle_number=cycle_number,
            execute_trade=config.execute_trade,
            interval_seconds=(
                config.interval_seconds
            ),
            last_result=last_result,
            error=last_result.get("error"),
        )

        print(
            "[TitanAI]",
            f"cycle={cycle_number}",
            f"status={last_result.get('status')}",
            f"mode={last_result.get('mode')}",
            "submitted="
            f"{bool(last_result.get('execution', {}).get('submitted', False))}",
            f"health={health.get('status')}",
            flush=True,
        )

        if (
            consecutive_errors
            >= config.maximum_consecutive_errors
        ):
            stop_reason = (
                "maximum_consecutive_errors"
            )
            controller.request(stop_reason)
            break

        if (
            config.maximum_cycles is not None
            and cycle_number
            >= config.maximum_cycles
        ):
            stop_reason = "maximum_cycles"
            controller.request(stop_reason)
            break

        shutdown_during_wait = (
            await sleep_until_next_cycle(
                interval_seconds=(
                    config.interval_seconds
                ),
                shutdown_event=controller._event,
            )
        )

        if shutdown_during_wait:
            stop_reason = (
                controller.reason
                or "shutdown_requested"
            )
            break

    if controller.reason:
        stop_reason = controller.reason

    final_health = evaluate_service_health(
        result=last_result,
        consecutive_errors=consecutive_errors,
        maximum_consecutive_errors=(
            config.maximum_consecutive_errors
        ),
    )

    write_heartbeat(
        status="stopped",
        cycle_number=cycle_number,
        execute_trade=config.execute_trade,
        interval_seconds=(
            config.interval_seconds
        ),
        last_result=last_result,
    )

    return {
        "status": "stopped",
        "version": (
            "autonomous_testnet_service_v1"
        ),
        "stop_reason": stop_reason,
        "cycles_completed": cycle_number,
        "execute_trade": config.execute_trade,
        "interval_seconds": (
            config.interval_seconds
        ),
        "signals_installed": (
            installed_signals
        ),
        "consecutive_errors": (
            consecutive_errors
        ),
        "health": final_health,
        "last_result": last_result,
        "service_log": str(
            SERVICE_LOG_PATH
        ),
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run TitanAI continuous Binance "
            "Futures testnet cycles."
        )
    )

    parser.add_argument(
        "--execute-trades",
        action="store_true",
        help=(
            "Explicitly allow Binance Futures "
            "testnet order submission."
        ),
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
    )
    parser.add_argument(
        "--balance",
        type=float,
        default=DEFAULT_BALANCE,
    )
    parser.add_argument(
        "--risk-percent",
        type=float,
        default=DEFAULT_RISK_PERCENT,
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=DEFAULT_LEVERAGE,
    )
    parser.add_argument(
        "--scan-limit",
        type=int,
        default=DEFAULT_SCAN_LIMIT,
    )
    parser.add_argument(
        "--maximum-cycles",
        type=int,
        default=None,
        help=(
            "Optional bounded run for testing."
        ),
    )
    parser.add_argument(
        "--maximum-consecutive-errors",
        type=int,
        default=(
            DEFAULT_MAXIMUM_CONSECUTIVE_ERRORS
        ),
    )

    return parser


def main() -> int:
    arguments = (
        build_argument_parser()
        .parse_args()
    )

    config = AutonomousServiceConfig(
        execute_trade=(
            arguments.execute_trades
        ),
        interval_seconds=(
            arguments.interval_seconds
        ),
        balance=arguments.balance,
        risk_percent=(
            arguments.risk_percent
        ),
        leverage=arguments.leverage,
        scan_limit=arguments.scan_limit,
        maximum_cycles=(
            arguments.maximum_cycles
        ),
        maximum_consecutive_errors=(
            arguments.maximum_consecutive_errors
        ),
    )

    try:
        result = asyncio.run(
            run_autonomous_service(
                config
            )
        )

    except KeyboardInterrupt:
        print(
            "\nTitanAI autonomous service "
            "stopped by keyboard interrupt."
        )
        return 0

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
