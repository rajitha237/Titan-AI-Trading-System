"""Signal-aware graceful shutdown controller."""

from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShutdownController:
    """Coordinate a safe stop without interrupting an active cycle."""

    _event: asyncio.Event = field(
        default_factory=asyncio.Event,
    )
    reason: str | None = None

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def request(self, reason: str = "shutdown_requested") -> None:
        self.reason = reason
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def install_signal_handlers(
        self,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> list[str]:
        """Install SIGINT/SIGTERM handlers when supported."""
        active_loop = loop or asyncio.get_running_loop()
        installed: list[str] = []

        for sig in (
            signal.SIGINT,
            signal.SIGTERM,
        ):
            try:
                active_loop.add_signal_handler(
                    sig,
                    self.request,
                    sig.name,
                )
                installed.append(sig.name)
            except (
                NotImplementedError,
                RuntimeError,
                ValueError,
            ):
                # Some environments do not allow loop signal handlers.
                continue

        return installed
