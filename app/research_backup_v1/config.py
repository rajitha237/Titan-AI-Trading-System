from dataclasses import dataclass, field
from pathlib import Path

FUTURES_BASE_URL = 'https://fapi.binance.com'
KLINES_PATH = '/fapi/v1/klines'

@dataclass(frozen=True)
class ResearchConfig:
    symbols: tuple[str, ...] = ('BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT')
    timeframes: tuple[str, ...] = ('15m','1h','4h')
    months: int = 6
    request_limit: int = 1000
    request_timeout_seconds: float = 20.0
    fee_rate: float = 0.0004
    slippage_rate: float = 0.0002
    initial_balance: float = 1000.0
    risk_per_trade_percent: float = 1.0
    minimum_score: float = 70.0
    minimum_sample_size: int = 20
    data_dir: Path = field(default_factory=lambda: Path('app/data/research'))
    @property
    def report_dir(self) -> Path:
        return self.data_dir / 'reports'
    @property
    def database_path(self) -> Path:
        return self.data_dir / 'research_results.db'
