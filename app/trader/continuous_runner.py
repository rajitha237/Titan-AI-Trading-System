"""
TitanAI Continuous Runner v3
Auto cycle + position monitoring + dynamic quantity safe mode
"""

import asyncio
from datetime import datetime

from app.trader.auto_testnet_runner import run_auto_testnet_cycle


async def run_forever(
    quantity: float | None = None,
    interval_seconds: int = 60,
    execute_trade: bool = False,
):
    print("=" * 80)
    print("TitanAI Continuous Runner Started")
    print("Dynamic quantity:", quantity is None)
    print("Execute trade:", execute_trade)
    print("Interval seconds:", interval_seconds)
    print("=" * 80)

    while True:
        try:
            print("=" * 80)
            print(f"TitanAI cycle started: {datetime.utcnow().isoformat()}")

            result = await run_auto_testnet_cycle(
                quantity=quantity,
                execute_trade=execute_trade,
            )

            print("Status:", result.get("status"))
            print("Symbol:", result.get("symbol"))
            print("Price:", result.get("price"))
            print("Quantity:", result.get("quantity"))
            print("Quantity error:", result.get("quantity_error"))
            print("Position:", result.get("position_manager"))
            print("Confidence:", result.get("confidence"))
            print("Trade Quality:", result.get("trade_quality"))
            print("Execution:", result.get("execution"))

        except KeyboardInterrupt:
            print("TitanAI runner stopped by user.")
            break

        except Exception as e:
            print("TitanAI cycle error:", str(e))

        print(f"Sleeping {interval_seconds} seconds...")
        await asyncio.sleep(interval_seconds)