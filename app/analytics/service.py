"""Production-grade realised-PnL analytics for TitanAI's SQLite journal."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "titanai_journal.db"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result and result not in (float("inf"), float("-inf")) else default
    except (TypeError, ValueError):
        return default


def _parse_time(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class PnLEvent:
    id: int
    created_at: str
    symbol: str
    event_type: str
    realised_pnl: float
    cycle_id: int | None = None


class AnalyticsService:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    def _load_events(self) -> list[PnLEvent]:
        if not self.db_path.exists():
            return []
        with self._connect() as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "trade_events" not in tables:
                return []
            rows = connection.execute(
                """SELECT id, created_at, cycle_id, symbol, event_type, realised_pnl
                   FROM trade_events
                   WHERE realised_pnl IS NOT NULL
                   ORDER BY created_at ASC, id ASC"""
            ).fetchall()
        return [
            PnLEvent(
                id=int(row["id"]), created_at=str(row["created_at"]),
                cycle_id=row["cycle_id"], symbol=str(row["symbol"] or "UNKNOWN").upper(),
                event_type=str(row["event_type"] or "UNKNOWN").upper(),
                realised_pnl=_number(row["realised_pnl"]),
            ) for row in rows
        ]

    @staticmethod
    def _streaks(values: Iterable[float]) -> tuple[int, int]:
        best_win = best_loss = current_win = current_loss = 0
        for value in values:
            if value > 0:
                current_win += 1; current_loss = 0; best_win = max(best_win, current_win)
            elif value < 0:
                current_loss += 1; current_win = 0; best_loss = max(best_loss, current_loss)
            else:
                current_win = current_loss = 0
        return best_win, best_loss

    @staticmethod
    def _drawdown(values: Iterable[float]) -> tuple[float, list[dict[str, float]]]:
        equity = peak = max_drawdown = 0.0
        curve: list[dict[str, float]] = []
        for index, pnl in enumerate(values, start=1):
            equity += pnl; peak = max(peak, equity); drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)
            curve.append({"trade": index, "equity": round(equity, 8), "drawdown": round(drawdown, 8)})
        return max_drawdown, curve

    def snapshot(self) -> dict[str, Any]:
        events = self._load_events()
        pnl_values = [event.realised_pnl for event in events]
        wins = [v for v in pnl_values if v > 0]
        losses = [v for v in pnl_values if v < 0]
        gross_profit = sum(wins); gross_loss = abs(sum(losses)); total = sum(pnl_values)
        max_dd, equity_curve = self._drawdown(pnl_values)
        max_win_streak, max_loss_streak = self._streaks(pnl_values)

        by_day: dict[str, float] = defaultdict(float)
        by_week: dict[str, float] = defaultdict(float)
        by_month: dict[str, float] = defaultdict(float)
        by_symbol: dict[str, dict[str, Any]] = defaultdict(lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        for event in events:
            timestamp = _parse_time(event.created_at)
            by_day[timestamp.date().isoformat()] += event.realised_pnl
            iso = timestamp.isocalendar(); by_week[f"{iso.year}-W{iso.week:02d}"] += event.realised_pnl
            by_month[timestamp.strftime("%Y-%m")] += event.realised_pnl
            item = by_symbol[event.symbol]; item["trades"] += 1; item["pnl"] += event.realised_pnl
            item["wins" if event.realised_pnl > 0 else "losses" if event.realised_pnl < 0 else "trades"] += 1 if event.realised_pnl != 0 else 0

        symbol_rows = []
        for symbol, item in by_symbol.items():
            trades = item["trades"]
            symbol_rows.append({"symbol": symbol, **item, "pnl": round(item["pnl"], 8), "win_rate": round(item["wins"] / trades * 100, 2) if trades else 0.0})
        symbol_rows.sort(key=lambda row: row["pnl"], reverse=True)

        trade_count = len(events)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "database": str(self.db_path),
            "summary": {
                "closed_trades": trade_count, "wins": len(wins), "losses": len(losses),
                "win_rate": round(len(wins) / trade_count * 100, 2) if trade_count else 0.0,
                "total_realised_pnl": round(total, 8),
                "average_trade": round(total / trade_count, 8) if trade_count else 0.0,
                "average_win": round(gross_profit / len(wins), 8) if wins else 0.0,
                "average_loss": round(sum(losses) / len(losses), 8) if losses else 0.0,
                "largest_win": round(max(wins), 8) if wins else 0.0,
                "largest_loss": round(min(losses), 8) if losses else 0.0,
                "gross_profit": round(gross_profit, 8), "gross_loss": round(gross_loss, 8),
                "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (None if not gross_profit else "infinite"),
                "expectancy": round(total / trade_count, 8) if trade_count else 0.0,
                "max_drawdown": round(max_dd, 8),
                "max_consecutive_wins": max_win_streak, "max_consecutive_losses": max_loss_streak,
            },
            "equity_curve": equity_curve,
            "daily_pnl": [{"period": k, "pnl": round(v, 8)} for k, v in sorted(by_day.items())],
            "weekly_pnl": [{"period": k, "pnl": round(v, 8)} for k, v in sorted(by_week.items())],
            "monthly_pnl": [{"period": k, "pnl": round(v, 8)} for k, v in sorted(by_month.items())],
            "symbol_performance": symbol_rows,
        }


def get_analytics_snapshot(db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any]:
    return AnalyticsService(db_path).snapshot()
