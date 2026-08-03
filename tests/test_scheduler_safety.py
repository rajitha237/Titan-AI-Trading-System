"""Scheduler safety tests."""

from __future__ import annotations

import asyncio
import unittest

from app.service.scheduler import (
    MINIMUM_INTERVAL_SECONDS,
    normalize_interval,
    sleep_until_next_cycle,
)


class SchedulerSafetyTests(
    unittest.TestCase
):
    def test_minimum_interval_is_enforced(self):
        self.assertEqual(
            normalize_interval(1),
            MINIMUM_INTERVAL_SECONDS,
        )

    def test_shutdown_interrupts_wait(self):
        async def run_test() -> bool:
            event = asyncio.Event()
            event.set()

            return await sleep_until_next_cycle(
                interval_seconds=60,
                shutdown_event=event,
            )

        self.assertTrue(
            asyncio.run(run_test())
        )


if __name__ == "__main__":
    unittest.main()
