"""
TitanAI AI Learning Engine v3

Learns from journal history:
- symbol activity
- execution behavior
- confidence
- quality score
- order flow / whale behavior
"""

from collections import defaultdict

from app.trader.trade_journal import get_journal_entries


def summarize_learning() -> dict:
    entries = get_journal_entries()

    symbol_stats = defaultdict(lambda: {
        "cycles": 0,
        "executed": 0,
        "skipped": 0,
        "closed": 0,
        "buy_signals": 0,
        "hold_signals": 0,
        "sell_signals": 0,
        "confidence_total": 0,
        "confidence_count": 0,
        "quality_total": 0,
        "quality_count": 0,
        "aggressive_buyers": 0,
        "aggressive_sellers": 0,
        "balanced_flow": 0,
        "whale_buy_total": 0,
        "whale_sell_total": 0,
    })

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        symbol = entry.get("symbol") or "UNKNOWN"
        stats = symbol_stats[symbol]
        stats["cycles"] += 1

        final_decision = entry.get("final_decision") or {}
        best_setup = entry.get("best_setup") or {}
        best_final_decision = best_setup.get("final_decision") or {}

        decision = (
            final_decision.get("decision")
            or best_final_decision.get("decision")
        )

        if decision == "BUY":
            stats["buy_signals"] += 1
        elif decision == "SELL":
            stats["sell_signals"] += 1
        elif decision == "HOLD":
            stats["hold_signals"] += 1

        execution = entry.get("execution") or {}
        execution_status = execution.get("status")

        if execution_status == "executed":
            stats["executed"] += 1
        elif execution_status == "skipped":
            stats["skipped"] += 1

        position_manager = entry.get("position_manager") or {}
        if position_manager.get("status") == "closed":
            stats["closed"] += 1

        confidence_data = entry.get("confidence") or {}
        confidence = confidence_data.get("confidence")

        if confidence is not None:
            stats["confidence_total"] += float(confidence)
            stats["confidence_count"] += 1

        trade_quality = entry.get("trade_quality") or {}
        quality_score = trade_quality.get("quality_score")

        if quality_score is not None:
            stats["quality_total"] += float(quality_score)
            stats["quality_count"] += 1

        order_flow = (
            best_setup.get("order_flow")
            or best_setup.get("ai_score", {}).get("order_flow")
            or {}
        )

        pressure = order_flow.get("pressure")

        if pressure == "AGGRESSIVE_BUYERS":
            stats["aggressive_buyers"] += 1
        elif pressure == "AGGRESSIVE_SELLERS":
            stats["aggressive_sellers"] += 1
        elif pressure == "BALANCED":
            stats["balanced_flow"] += 1

        whale_buy_count = order_flow.get("whale_buy_count", 0)
        whale_sell_count = order_flow.get("whale_sell_count", 0)

        stats["whale_buy_total"] += whale_buy_count or 0
        stats["whale_sell_total"] += whale_sell_count or 0

    learning = {}

    for symbol, stats in symbol_stats.items():
        avg_confidence = (
            stats["confidence_total"] / stats["confidence_count"]
            if stats["confidence_count"] else 0
        )

        avg_quality = (
            stats["quality_total"] / stats["quality_count"]
            if stats["quality_count"] else 0
        )

        execution_rate = (
            stats["executed"] / stats["cycles"] * 100
            if stats["cycles"] else 0
        )

        learning[symbol] = {
            "cycles": stats["cycles"],
            "executed": stats["executed"],
            "skipped": stats["skipped"],
            "closed": stats["closed"],
            "execution_rate": round(execution_rate, 2),
            "buy_signals": stats["buy_signals"],
            "sell_signals": stats["sell_signals"],
            "hold_signals": stats["hold_signals"],
            "avg_confidence": round(avg_confidence, 2),
            "avg_quality": round(avg_quality, 2),
            "order_flow": {
                "aggressive_buyers": stats["aggressive_buyers"],
                "aggressive_sellers": stats["aggressive_sellers"],
                "balanced": stats["balanced_flow"],
            },
            "whales": {
                "buy_total": stats["whale_buy_total"],
                "sell_total": stats["whale_sell_total"],
            },
        }

    return {
        "status": "success",
        "total_entries": len(entries),
        "symbols": learning,
    }