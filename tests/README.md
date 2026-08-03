# TitanAI Test Suite v1

This suite replaces long Python REPL test blocks with repeatable commands.

## Install

Copy the `tests` folder into the TitanAI project root.

## Offline test

```bash
python tests/run_full_system_test.py
```

Offline tests cover:

- Research feature generation
- Chronological train/validation/test separation
- SK feature output
- Pattern similarity dtype safety
- Strategy signal values
- Backtester/report schema
- Wilson probability bounds
- Institutional regime/strategy/research/probability/adaptive-score pipeline

## Optional live public-data test

After offline tests pass:

```bash
python tests/run_full_system_test.py --live
```

The live test calls the current portfolio scanner and Binance public market
services. It does not submit an order.

## Direct unittest command

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
