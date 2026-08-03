# TitanAI Research Engine v2

Research Engine v2 adds:

- ADX and stricter trend filters
- market-regime detection
- higher-timeframe proxy alignment
- stricter SK/Fibonacci confirmation
- chronological train/validation/test separation
- parameter sweep selected without seeing test results
- unseen-test approval
- anchored walk-forward robustness checks
- feature-vector similarity statistics
- Wilson confidence-bound probability reporting
- safe historical-edge output for the live scanner

## Install

```bash
pip install pandas numpy ta httpx
```

## Demo

Start with at least six months:

```bash
python -m app.research.demo_runner \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT \
  --timeframes 15m,1h \
  --months 6
```

A strategy is approved only when validation, unseen test, drawdown, minimum
trade sample, and walk-forward rules all pass. An approved result is still not
a guarantee of live profit.
