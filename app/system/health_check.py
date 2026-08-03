"""
TitanAI System Health Check
"""

import asyncio

from app.services.market_snapshot import get_market_snapshot
from app.trader.portfolio_scanner import scan_portfolio
from app.memory.memory_engine import get_memory_records
from app.learning.learning_engine import summarize_learning
from app.strategy.strategy_store import load_strategy_settings


async def run_health_check() -> dict:
    checks = {}

    try:
        snapshot = await get_market_snapshot("BTCUSDT")
        checks["market_snapshot"] = {
            "status": "ok",
            "price": snapshot.get("price"),
            "order_flow": snapshot.get("order_flow", {}).get("pressure"),
            "liquidity": snapshot.get("liquidity", {}).get("pressure"),
        }
    except Exception as e:
        checks["market_snapshot"] = {"status": "failed", "error": str(e)}

    try:
        scan = await scan_portfolio(limit=5)
        checks["portfolio_scanner"] = {
            "status": "ok",
            "best_symbol": scan.get("best_setup", {}).get("symbol"),
            "tested": scan.get("total_symbols"),
            "errors": len(scan.get("errors", [])),
        }
    except Exception as e:
        checks["portfolio_scanner"] = {"status": "failed", "error": str(e)}

    try:
        memory = get_memory_records()
        checks["memory_engine"] = {
            "status": "ok",
            "records": len(memory),
        }
    except Exception as e:
        checks["memory_engine"] = {"status": "failed", "error": str(e)}

    try:
        learning = summarize_learning()
        checks["learning_engine"] = {
            "status": "ok",
            "entries": learning.get("total_entries"),
        }
    except Exception as e:
        checks["learning_engine"] = {"status": "failed", "error": str(e)}

    try:
        strategy = load_strategy_settings()
        checks["strategy_store"] = {
            "status": "ok",
            "strategies": len(strategy.get("settings", {})),
            "updated_at": strategy.get("updated_at"),
        }
    except Exception as e:
        checks["strategy_store"] = {"status": "failed", "error": str(e)}

    total = len(checks)
    passed = len([c for c in checks.values() if c["status"] == "ok"])
    health_percent = round((passed / total) * 100, 2) if total else 0

    return {
        "status": "ready" if health_percent == 100 else "warning",
        "health_percent": health_percent,
        "passed": passed,
        "total": total,
        "checks": checks,
    }


if __name__ == "__main__":
    result = asyncio.run(run_health_check())

    print("=" * 60)
    print("TitanAI Health Check")
    print("=" * 60)
    print("Status:", result["status"])
    print("Health:", str(result["health_percent"]) + "%")
    print("Passed:", result["passed"], "/", result["total"])
    print("-" * 60)

    for name, check in result["checks"].items():
        icon = "✅" if check["status"] == "ok" else "❌"
        print(icon, name, check)

    print("=" * 60)