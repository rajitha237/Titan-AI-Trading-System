import asyncio

from app.services.whale_engine import analyze_whale_activity


async def main():
    for i in range(5):
        result = await analyze_whale_activity("BTCUSDT")

        print("=" * 70)
        print(f"Sample {i + 1}")
        print(result)

        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())