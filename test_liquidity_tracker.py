import asyncio
from app.services.market_snapshot import get_market_snapshot


async def main():
    for i in range(5):
        s = await get_market_snapshot("BTCUSDT")
        print("=" * 70)
        print("Sample:", i + 1)
        print(s["liquidity"])
        print(s["liquidity_trend"])
        await asyncio.sleep(5)


asyncio.run(main())