"""Human-readable TitanAI end-to-end analysis-only pipeline demo."""

from __future__ import annotations

import asyncio
from typing import Any

from app.trader.auto_testnet_runner import run_auto_testnet_cycle


def passed(value: bool) -> str:
    return "PASS" if value else "CHECK"


def mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


async def main() -> None:
    result = await run_auto_testnet_cycle(
        execute_trade=False,
        balance=30.0,
        risk_percent=1.0,
        leverage=5.0,
        scan_limit=5,
    )

    execution = mapping(result.get("execution"))
    best_setup = mapping(result.get("best_setup"))
    validation = mapping(result.get("validation"))
    confirmation = mapping(result.get("confirmation"))
    quality = mapping(result.get("trade_quality"))
    risk = mapping(result.get("risk_plan"))
    plan = mapping(result.get("trade_plan"))

    institutional_present = all(
        key in best_setup
        for key in (
            "live_market_regime",
            "institutional_strategy",
            "institutional_probability",
            "adaptive_score",
            "research_confluence",
        )
    ) if best_setup else False

    print("=" * 64)
    print("TitanAI End-to-End Analysis Test")
    print("=" * 64)
    print(f"Runner schema           {passed(result.get('version') == 'v27')}")
    print(f"Scanner result          {passed(isinstance(result.get('scan'), dict))}")
    print(f"Institutional fields    {passed(institutional_present)}")
    print(f"Confirmation attached   {passed(bool(confirmation))}")
    print(f"Validator attached      {passed(bool(validation))}")
    print(f"Trade quality attached  {passed(bool(quality))}")
    print(f"Risk plan attached      {passed(bool(risk))}")
    print(f"Trade plan attached     {passed(bool(plan))}")
    print(f"Order submitted         {execution.get('submitted')}")
    print(f"Execution mode          {execution.get('mode')}")
    print(f"Execution status        {execution.get('status')}")
    print(f"System status           {result.get('status')}")
    print(f"Selected symbol         {result.get('symbol')}")
    print(f"Candidates evaluated    {result.get('candidates_evaluated')}")
    print("=" * 64)

    safe = execution.get("submitted") is False
    print(
        "OVERALL STATUS          ",
        "PASS" if safe else "FAIL: ORDER WAS SUBMITTED",
    )

    if result.get("execution_blocks"):
        print("\nExecution blocks:")
        for block in result["execution_blocks"]:
            print("-", block)


if __name__ == "__main__":
    asyncio.run(main())
