"""TitanAI asynchronous scheduler v18 with Telegram notifications."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.notifications.notification_manager import NotificationManager
from app.trader.auto_testnet_runner import run_auto_testnet_cycle
from app.trader.scheduler_config import SchedulerConfig

LOGGER = logging.getLogger("titanai.scheduler")
HEALTH_FILE = Path(__file__).resolve().parents[1] / "data" / "scheduler_health.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_health(payload: dict[str, Any]) -> None:
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = HEALTH_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(HEALTH_FILE)


class TitanAIScheduler:
    def __init__(self, config: SchedulerConfig) -> None:
        self.config = config
        self.notifications = NotificationManager()
        self._stop_event = asyncio.Event()
        self._cycle_lock = asyncio.Lock()
        self._cycle_number = 0
        self._last_success_at: str | None = None
        self._last_error: str | None = None

    def request_stop(self) -> None:
        LOGGER.info("Shutdown requested")
        self._stop_event.set()

    async def _wait_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return

    async def run_one_cycle(self) -> dict[str, Any]:
        if self._cycle_lock.locked():
            return {
                "status": "skipped",
                "reason": "Previous scheduler cycle is still running",
            }

        async with self._cycle_lock:
            self._cycle_number += 1
            started_at = _utc_now()
            LOGGER.info("Starting cycle %s", self._cycle_number)

            try:
                result = await run_auto_testnet_cycle(
                    execute_trade=self.config.execute_trades,
                    balance=self.config.balance,
                    risk_percent=self.config.risk_percent,
                    leverage=self.config.leverage,
                    current_daily_pnl=self.config.current_daily_pnl,
                    scan_limit=self.config.scan_limit,
                )

                self._last_success_at = _utc_now()
                self._last_error = None
                execution = result.get("execution", {}) or {}

                LOGGER.info(
                    "Cycle %s complete: status=%s execution=%s symbol=%s",
                    self._cycle_number,
                    result.get("status"),
                    execution.get("status"),
                    result.get("symbol"),
                )

                notification_results = await self.notifications.process_cycle_result(
                    result,
                    cycle_number=self._cycle_number,
                )
                notification_errors = [
                    item.get("reason")
                    for item in notification_results
                    if item.get("status") == "error"
                ]
                if notification_errors:
                    LOGGER.warning(
                        "Telegram notification errors: %s",
                        notification_errors,
                    )

                _write_health(
                    {
                        "status": "healthy",
                        "running": True,
                        "cycle_number": self._cycle_number,
                        "cycle_started_at": started_at,
                        "last_success_at": self._last_success_at,
                        "last_error": None,
                        "execute_trades": self.config.execute_trades,
                        "telegram": {
                            "events_processed": len(notification_results),
                            "errors": notification_errors,
                        },
                        "last_result": {
                            "status": result.get("status"),
                            "symbol": result.get("symbol"),
                            "execution_status": execution.get("status"),
                            "reason": execution.get("reason", result.get("reason")),
                        },
                    }
                )
                return result

            except asyncio.CancelledError:
                raise

            except Exception as error:
                self._last_error = str(error)
                LOGGER.exception("Cycle %s failed", self._cycle_number)

                alert_result = await self.notifications.notify_error(
                    self._last_error,
                    cycle_number=self._cycle_number,
                )

                _write_health(
                    {
                        "status": "error",
                        "running": True,
                        "cycle_number": self._cycle_number,
                        "cycle_started_at": started_at,
                        "last_success_at": self._last_success_at,
                        "last_error": self._last_error,
                        "execute_trades": self.config.execute_trades,
                        "telegram_alert": alert_result,
                    }
                )
                return {"status": "error", "error": self._last_error}

    async def run_forever(self) -> None:
        LOGGER.info(
            "TitanAI scheduler started: interval=%.1fs execute_trades=%s",
            self.config.interval_seconds,
            self.config.execute_trades,
        )

        startup_result = await self.notifications.notify_startup(
            execute_trades=self.config.execute_trades,
            interval_seconds=self.config.interval_seconds,
        )
        if startup_result.get("status") == "error":
            LOGGER.warning(
                "Telegram startup notification failed: %s",
                startup_result.get("reason"),
            )

        _write_health(
            {
                "status": "starting",
                "running": True,
                "started_at": _utc_now(),
                "execute_trades": self.config.execute_trades,
                "telegram_startup": startup_result,
            }
        )

        while not self._stop_event.is_set():
            result = await self.run_one_cycle()
            delay = (
                self.config.error_retry_seconds
                if result.get("status") == "error"
                else self.config.interval_seconds
            )
            await self._wait_or_stop(delay)

        shutdown_result = await self.notifications.notify_shutdown()
        _write_health(
            {
                "status": "stopped",
                "running": False,
                "stopped_at": _utc_now(),
                "cycle_number": self._cycle_number,
                "last_success_at": self._last_success_at,
                "last_error": self._last_error,
                "execute_trades": self.config.execute_trades,
                "telegram_shutdown": shutdown_result,
            }
        )
        LOGGER.info("TitanAI scheduler stopped")


def install_signal_handlers(scheduler: TitanAIScheduler) -> None:
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, scheduler.request_stop)
        except (NotImplementedError, RuntimeError):
            pass