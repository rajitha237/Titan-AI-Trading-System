"""Start TitanAI as a long-running testnet scheduler."""

from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.trader.scheduler import TitanAIScheduler, install_signal_handlers
from app.trader.scheduler_config import SchedulerConfig


def configure_logging(level: str) -> None:
    log_path = Path("app/data/titanai_scheduler.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)


async def main() -> None:
    config = SchedulerConfig.from_env()
    configure_logging(config.log_level)

    scheduler = TitanAIScheduler(config)
    install_signal_handlers(scheduler)

    print("TitanAI scheduler starting...")
    print(f"Interval: {config.interval_seconds:.1f} seconds")
    print(f"Trade execution enabled: {config.execute_trades}")
    if not config.execute_trades:
        print("Analysis-only safety mode is active.")
        print("Use TITANAI_EXECUTE_TRADES=true to enable TESTNET execution.")

    await scheduler.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass