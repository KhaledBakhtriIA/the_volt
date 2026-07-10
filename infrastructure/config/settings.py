import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


def _split_csv_env(name: str, default: List[str]) -> List[str]:
    """Read a CSV env var into a normalized list with fallback default."""
    value = os.getenv(name, "")
    if not value.strip():
        return default
    return [token.strip() for token in value.split(",") if token.strip()]


def _bool_env(name: str, default: bool) -> bool:
    """Read a bool env var with permissive truthy/falsey parsing."""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _browser_targets_env(name: str, default: Dict[str, str]) -> Dict[str, str]:
    """Read browser targets from env as `name=url,name=url` mapping."""
    value = os.getenv(name, "").strip()
    if not value:
        return default

    targets: Dict[str, str] = {}
    for item in value.split(","):
        token = item.strip()
        if not token or "=" not in token:
            continue
        key, url = token.split("=", 1)
        key = key.strip().lower()
        url = url.strip()
        if key and url:
            targets[key] = url

    return targets or default


DEFAULT_BROWSER_TARGETS: Dict[str, str] = {
    "tradingview": "https://www.tradingview.com/markets/cryptocurrencies/prices-all/",
    "investing": "https://www.investing.com/crypto/",
}

DEFAULT_DESKTOP_TARGETS: Dict[str, str] = {
    "trading_terminal": "active_screen",
}

DEFAULT_FRED_SERIES: Dict[str, str] = {
    "fed_funds_rate": "FEDFUNDS",
    "cpi_all_items": "CPIAUCSL",
    "real_gdp": "GDPC1",
    "m2_money_stock": "M2SL",
}

DEFAULT_RSS_FEEDS: Dict[str, str] = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "bitcoinmagazine": "https://bitcoinmagazine.com/.rss/full/",
}

# frozen=True enforces immutability after construction.
# All configuration must be set at startup via environment variables.
# Never mutate settings at runtime — create a new instance if needed.
@dataclass(frozen=True)
class Settings:
    """Application runtime settings loaded from environment variables."""
    host: str = os.getenv("DATA_API_HOST", "127.0.0.1")
    port: int = int(os.getenv("DATA_API_PORT", "8000"))
    interval: str = os.getenv("DATA_API_INTERVAL", "1d")
    lookback_days: int = int(os.getenv("DATA_API_LOOKBACK_DAYS", "365"))
    browser_enabled: bool = _bool_env("DATA_API_BROWSER_ENABLED", False)
    browser_headless: bool = _bool_env("DATA_API_BROWSER_HEADLESS", True)
    browser_timeout_ms: int = int(os.getenv("DATA_API_BROWSER_TIMEOUT_MS", "30000"))
    reddit_enabled: bool = _bool_env("DATA_API_REDDIT_ENABLED", False)
    macro_enabled: bool = _bool_env("DATA_API_MACRO_ENABLED", False)
    desktop_enabled: bool = _bool_env("DATA_API_DESKTOP_ENABLED", False)
    vision_enabled: bool = _bool_env("DATA_API_VISION_ENABLED", False)
    stock_market_enabled: bool = _bool_env("DATA_API_STOCK_MARKET_ENABLED", False)
    trading_strategy_enabled: bool = _bool_env("DATA_API_TRADING_STRATEGY_ENABLED", False)
    trading_mistakes_enabled: bool = _bool_env("DATA_API_TRADING_MISTAKES_ENABLED", False)
    tokeninsight_enabled: bool = _bool_env("DATA_API_TOKENINSIGHT_ENABLED", False)
    finance_query_stream_enabled: bool = _bool_env("DATA_API_FINANCE_QUERY_STREAM_ENABLED", False)
    realtime_mode_enabled: bool = _bool_env("DATA_API_REALTIME_MODE_ENABLED", False)
    require_human_approval: bool = _bool_env("REQUIRE_HUMAN_APPROVAL", False)
    reddit_client_id: str = os.getenv("DATA_API_REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.getenv("DATA_API_REDDIT_CLIENT_SECRET", "")
    reddit_user_agent: str = os.getenv("DATA_API_REDDIT_USER_AGENT", "volt-data-api/1.0")
    fred_api_key: str = os.getenv("DATA_API_FRED_API_KEY", "")
    fcs_api_key: str = os.getenv("DATA_API_FCS_API_KEY", "")
    tokeninsight_api_key: str = os.getenv("DATA_API_TOKENINSIGHT_API_KEY", "")
    finance_query_ws_url: str = os.getenv("DATA_API_FINANCE_QUERY_WS_URL", "wss://stream.financequery.com/ws")
    kafka_bootstrap_servers: str = os.getenv("DATA_API_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    tick_topic: str = os.getenv("DATA_API_TICK_TOPIC", "volt_ticks")
    redis_url: str = os.getenv("DATA_API_REDIS_URL", "redis://localhost:6379/0")
    finance_query_channels: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_FINANCE_QUERY_CHANNELS",
            ["ticker", "trades", "orderbook"],
        )
    )
    desktop_capture_interval_seconds: int = int(os.getenv("DATA_API_DESKTOP_CAPTURE_INTERVAL_SECONDS", "5"))
    data_root: Path = Path(os.getenv("DATA_API_DATA_ROOT", "data_api/data"))
    raw_dir: Path = field(init=False)
    processed_dir: Path = field(init=False)
    export_dir: Path = field(init=False)
    crypto_symbols: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_CRYPTO_SYMBOLS",
            [
                "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
                "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "MATIC-USD",
                "LTC-USD", "DOT-USD", "ATOM-USD", "ICP-USD", "NEAR-USD",
                "OP-USD", "ARB-USD", "UNI-USD", "AAVE-USD", "ZEC-USD",
            ],
        )
    )
    stock_symbols: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_STOCK_SYMBOLS",
            [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
                "TSLA", "META", "NFLX", "ADBE", "INTC",
                "JPM", "GS", "BAC", "WFC", "C",
                "XOM", "CVX", "COP", "SLB", "MRO",
                "KO", "PEP", "JNJ", "PG", "MCD",
                "WMT", "HD", "DIS", "CMCSA", "ABBV",
                "PM", "SO", "NEE", "DD", "DOW",
            ],
        )
    )
    macro_symbols: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_MACRO_SYMBOLS",
            ["GC=F", "CL=F", "DX-Y.NYB", "^TNX", "^GSPC", "^IXIC", "^DJI"],
        )
    )
    browser_targets: Dict[str, str] = field(
        default_factory=lambda: _browser_targets_env(
            "DATA_API_BROWSER_TARGETS",
            DEFAULT_BROWSER_TARGETS,
        )
    )
    desktop_targets: Dict[str, str] = field(
        default_factory=lambda: _browser_targets_env(
            "DATA_API_DESKTOP_TARGETS",
            DEFAULT_DESKTOP_TARGETS,
        )
    )
    reddit_subreddits: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_REDDIT_SUBREDDITS",
            ["cryptocurrency", "bitcoin", "ethtrader", "stocks"],
        )
    )
    reddit_query: str = os.getenv("DATA_API_REDDIT_QUERY", "market")
    reddit_limit_per_subreddit: int = int(os.getenv("DATA_API_REDDIT_LIMIT_PER_SUBREDDIT", "50"))
    fred_series: Dict[str, str] = field(
        default_factory=lambda: _browser_targets_env(
            "DATA_API_FRED_SERIES",
            DEFAULT_FRED_SERIES,
        )
    )
    stock_market_period: str = os.getenv("DATA_API_STOCK_MARKET_PERIOD", "1y")
    stock_market_interval: str = os.getenv("DATA_API_STOCK_MARKET_INTERVAL", "1d")
    trading_strategy_subreddits: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_TRADING_STRATEGY_SUBREDDITS",
            ["stocks", "investing", "daytraders", "wallstreetbets", "options", "Forex"],
        )
    )
    trading_strategy_query: str = os.getenv("DATA_API_TRADING_STRATEGY_QUERY", "strategy")
    trading_strategy_limit_per_subreddit: int = int(os.getenv("DATA_API_TRADING_STRATEGY_LIMIT_PER_SUBREDDIT", "100"))
    trading_mistakes_subreddits: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_TRADING_MISTAKES_SUBREDDITS",
            ["stocks", "investing", "wallstreetbets", "options", "Forex", "daytraders"],
        )
    )
    trading_mistakes_queries: List[str] = field(
        default_factory=lambda: _split_csv_env(
            "DATA_API_TRADING_MISTAKES_QUERIES",
            ["loss", "mistake", "bad trade", "liquidated", "margin call", "blew account"],
        )
    )
    trading_mistakes_limit_per_subreddit: int = int(os.getenv("DATA_API_TRADING_MISTAKES_LIMIT_PER_SUBREDDIT", "100"))
    rss_feeds: Dict[str, str] = field(
        default_factory=lambda: _browser_targets_env(
            "DATA_API_RSS_FEEDS",
            DEFAULT_RSS_FEEDS,
        )
    )

    def __post_init__(self) -> None:
        raw_dir = self.data_root / "raw"
        processed_dir = self.data_root / "processed"
        export_dir = self.data_root / "exports"
        object.__setattr__(self, "raw_dir", raw_dir)
        object.__setattr__(self, "processed_dir", processed_dir)
        object.__setattr__(self, "export_dir", export_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Create and return application settings instance."""
    return Settings()
