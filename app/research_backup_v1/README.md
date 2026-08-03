# TitanAI Research Engine MVP

Install dependencies:

```bash
pip install pandas numpy ta httpx
```

Copy `app/research` into the TitanAI project, then run:

```bash
python -m app.research.demo_runner --symbols BTCUSDT,ETHUSDT,SOLUSDT --timeframes 15m,1h --months 3
```

The demo downloads USD-M Futures candles, stores CSV data, generates features,
runs a next-candle-entry backtest with fees/slippage, stores SQLite reports, and
prints the strongest symbol/timeframe result.

This is a research MVP, not evidence of guaranteed live profitability. Run
multi-year, out-of-sample, walk-forward and parameter-stability tests before
using research results in production execution.
