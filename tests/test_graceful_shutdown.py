"""Graceful shutdown tests."""

from __future__ import annotations

import asyncio
import unittest

from app.service.graceful_shutdown import (
    ShutdownController,
)


class GracefulShutdownTests(
    unittest.TestCase
):
    def test_request_sets_reason_and_event(self):
        controller = ShutdownController()

        controller.request("unit_test")

        self.assertTrue(
            controller.requested
        )
        self.assertEqual(
            controller.reason,
            "unit_test",
        )

    def test_wait_completes_after_request(self):
        async def run_test() -> bool:
            controller = (
                ShutdownController()
            )
            controller.request(
                "unit_test"
            )
            await controller.wait()

            return controller.requested

        self.assertTrue(
            asyncio.run(run_test())
        )


if __name__ == "__main__":
    unittest.main()
