"""TitanAI Service Supervisor v35.1.

The supervisor evaluates consecutive failures and determines whether a service
cycle should continue, pause, or request a graceful shutdown. It does not
restart processes and does not modify exchange state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceSupervisor:
    warning_threshold: int = 2
    critical_threshold: int = 3
    _consecutive_failures: int = 0
    _last_status: str = "UNKNOWN"
    _last_reason: str | None = None

    def observe(
        self,
        health_report: dict | None,
    ) -> dict:
        report = (
            health_report
            if isinstance(
                health_report,
                dict,
            )
            else {}
        )

        status = str(
            report.get(
                "status",
                "CRITICAL",
            )
        ).upper()

        if status == "HEALTHY":
            self._consecutive_failures = 0
            action = "CONTINUE"
            reason = None

        elif status == "WARNING":
            self._consecutive_failures += 1
            action = (
                "PAUSE"
                if self._consecutive_failures
                >= max(
                    1,
                    self.warning_threshold,
                )
                else "CONTINUE"
            )
            reason = (
                "Repeated warning-level "
                "operational health"
            )

        else:
            self._consecutive_failures += 1
            action = (
                "SHUTDOWN_REQUESTED"
                if self._consecutive_failures
                >= max(
                    1,
                    self.critical_threshold,
                )
                else "PAUSE"
            )
            reason = (
                "Critical operational health"
            )

        self._last_status = status
        self._last_reason = reason

        return {
            "status": "success",
            "version": "v35.1",
            "health_status": status,
            "action": action,
            "consecutive_failures": (
                self._consecutive_failures
            ),
            "warning_threshold": (
                self.warning_threshold
            ),
            "critical_threshold": (
                self.critical_threshold
            ),
            "reason": reason,
            "read_only": True,
        }

    def snapshot(self) -> dict:
        return {
            "status": "success",
            "version": "v35.1",
            "last_health_status": (
                self._last_status
            ),
            "last_reason": self._last_reason,
            "consecutive_failures": (
                self._consecutive_failures
            ),
            "warning_threshold": (
                self.warning_threshold
            ),
            "critical_threshold": (
                self.critical_threshold
            ),
            "read_only": True,
        }


GLOBAL_SERVICE_SUPERVISOR = (
    ServiceSupervisor()
)


def supervise_service_health(
    health_report: dict | None,
) -> dict:
    return GLOBAL_SERVICE_SUPERVISOR.observe(
        health_report
    )
