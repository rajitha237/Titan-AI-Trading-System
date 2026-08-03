"""Live historical-edge service backed by unseen-test evidence."""

from __future__ import annotations

from app.research.config import ResearchConfig
from app.research.research_store import get_report


def get_historical_edge(
    symbol: str,
    timeframe: str = "15m",
    *,
    config: ResearchConfig | None = None,
) -> dict:
    config = config or ResearchConfig()
    report = get_report(
        config.database_path,
        symbol.upper(),
        timeframe,
    )

    if not report:
        return {
            "status": "missing",
            "decision": "NEUTRAL",
            "confidence_adjustment": 0.0,
            "sample_size": 0,
            "reason": "No v2 unseen-test report exists",
        }

    test = report.get("test_report", {})
    approved = report.get("approved") is True
    sample = int(test.get("trade_count", 0))
    expectancy = float(test.get("expectancy_r", 0.0))
    profit_factor = float(test.get("profit_factor", 0.0))

    if approved:
        adjustment = min(
            8.0,
            max(2.0, expectancy * 20),
        )
        decision = "SUPPORT"
        reason = (
            "Train, validation, unseen test, and walk-forward "
            "requirements passed"
        )
    elif sample >= config.minimum_test_trades and (
        expectancy < 0 or profit_factor < 0.9
    ):
        adjustment = -8.0
        decision = "OPPOSE"
        reason = "Unseen-test evidence is negative"
    else:
        adjustment = 0.0
        decision = "WATCH"
        reason = "Evidence is insufficient or mixed"

    return {
        "status": "ready",
        "decision": decision,
        "confidence_adjustment": adjustment,
        "sample_size": sample,
        "reason": reason,
        "approved": approved,
        "report": report,
    }
