from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from fastapi import Depends, FastAPI
import pandas as pd
from pydantic import BaseModel, Field
from pydantic import field_validator

from data_api.collectors.market_collector import MarketCollector
from data_api.collectors.news_collector import NewsCollector
from data_api.collectors.browser_collector import BrowserCollector
from data_api.collectors.reddit_collector import RedditCollector
from data_api.collectors.macro_collector import MacroCollector
from data_api.collectors.desktop_collector import DesktopCollector
from data_api.collectors.finance_query_stream import FinanceQueryStream
from data_api.collectors.stock_market_collector import StockMarketCollector
from data_api.collectors.trading_strategy_collector import TradingStrategyCollector
from data_api.collectors.trading_mistakes_collector import TradingMistakesCollector
from data_api.collectors.vision_extractor import VisionExtractor
from data_api.config.settings import get_settings
from data_api.jobs.pipeline import run_full_collection
from data_api.processors.sentiment import SentimentProcessor
from data_api.storage.file_store import FileStore

from contextlib import asynccontextmanager
import asyncio
from src.canonical.feature_store_engine import FeatureStoreEngine, FeatureStoreConfig
from src.canonical.stream_worker import StreamWorker
from src.canonical.learning_loop import NeuroplasticityLoop
from src.canonical.paper_broker import PaperBroker
from src.canonical.orchestrator import AnalysisOrchestrator
from src.canonical.realtime_runtime import (
    KafkaTickConsumer,
    RealTimeDecisionLoop,
    RedisFeatureCache,
    RealtimeRuntimeService,
)

settings = get_settings()

# Initialize Canonical Background Tasks
fse_config = FeatureStoreConfig(persist_offline=True)
global_engine = FeatureStoreEngine(fse_config)
stream_worker = StreamWorker(engine=global_engine)
neuro_loop = NeuroplasticityLoop(
    data_dir=str(fse_config.offline_store_path), 
    registry_db="model_registry.db"
)
paper_broker = PaperBroker(db_path="exports/paper_broker.db")
realtime_runtime_service: RealtimeRuntimeService | None = None

if settings.realtime_mode_enabled:
    realtime_orchestrator = AnalysisOrchestrator(exports_dir="exports")
    realtime_consumer = KafkaTickConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.tick_topic,
    )
    realtime_cache = RedisFeatureCache(redis_url=settings.redis_url)
    realtime_decision_loop = RealTimeDecisionLoop(
        consumer=realtime_consumer,
        cache=realtime_cache,
        orchestrator=realtime_orchestrator,
        model_name="forecast_model",
    )
    realtime_runtime_service = RealtimeRuntimeService(realtime_decision_loop)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    await stream_worker.start()
    neuro_task = asyncio.create_task(neuro_loop.start())
    if realtime_runtime_service is not None:
        await realtime_runtime_service.start()
    yield
    # Shutdown actions
    await stream_worker.stop()
    await neuro_loop.stop()
    if realtime_runtime_service is not None:
        await realtime_runtime_service.stop()
    neuro_task.cancel()
    try:
        await neuro_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Volt Data API", version="0.1.0", lifespan=lifespan)


@dataclass
class AppDependencies:
    """Container for runtime service dependencies used by API endpoints."""

    market_collector: MarketCollector
    news_collector: NewsCollector
    browser_collector: BrowserCollector
    reddit_collector: RedditCollector
    macro_collector: MacroCollector
    desktop_collector: DesktopCollector
    stock_market_collector: StockMarketCollector
    trading_strategy_collector: TradingStrategyCollector
    trading_mistakes_collector: TradingMistakesCollector
    sentiment_processor: SentimentProcessor
    raw_store: FileStore
    processed_store: FileStore
    export_store: FileStore


@lru_cache(maxsize=1)
def get_dependencies() -> AppDependencies:
    """Return default application dependencies.

    This function enables dependency injection while preserving current
    module-level singletons for backward compatibility and tests.
    """
    return AppDependencies(
        market_collector=MarketCollector(fcs_api_key=settings.fcs_api_key),
        news_collector=NewsCollector(
            tokeninsight_api_key=settings.tokeninsight_api_key,
            tokeninsight_enabled=settings.tokeninsight_enabled,
            rss_feeds=settings.rss_feeds,
        ),
        browser_collector=BrowserCollector(
            headless=settings.browser_headless,
            timeout_ms=settings.browser_timeout_ms,
        ),
        reddit_collector=RedditCollector(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        ),
        macro_collector=MacroCollector(fred_api_key=settings.fred_api_key),
        desktop_collector=DesktopCollector(
            vision_extractor=VisionExtractor(enabled=settings.vision_enabled)
        ),
        stock_market_collector=StockMarketCollector(),
        trading_strategy_collector=TradingStrategyCollector(
            reddit_client_id=settings.reddit_client_id,
            reddit_client_secret=settings.reddit_client_secret,
            reddit_user_agent=settings.reddit_user_agent,
        ),
        trading_mistakes_collector=TradingMistakesCollector(
            reddit_client_id=settings.reddit_client_id,
            reddit_client_secret=settings.reddit_client_secret,
            reddit_user_agent=settings.reddit_user_agent,
        ),
        sentiment_processor=SentimentProcessor(),
        raw_store=FileStore(settings.raw_dir),
        processed_store=FileStore(settings.processed_dir),
        export_store=FileStore(settings.export_dir),
    )


class CollectMarketRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: settings.crypto_symbols + settings.macro_symbols)
    interval: str = "1d"
    lookback_days: int = 30
    
    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v):
        """Validate symbols is non-empty list of non-empty strings."""
        if not v:
            raise ValueError("symbols list cannot be empty")
        if not isinstance(v, list):
            raise ValueError("symbols must be a list")
        for symbol in v:
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("Each symbol must be a non-empty string")
        return [symbol.strip().upper() for symbol in v]
    
    @field_validator('interval')
    @classmethod
    def validate_interval(cls, v):
        """Validate interval is valid."""
        valid_intervals = {'1m', '5m', '15m', '30m', '1h', '1d', '1wk'}
        if v not in valid_intervals:
            raise ValueError(f"interval must be one of {valid_intervals}")
        return v
    
    @field_validator('lookback_days')
    @classmethod
    def validate_lookback_days(cls, v):
        """Validate lookback_days is positive and reasonable."""
        if v < 1 or v > 365:
            raise ValueError("lookback_days must be between 1 and 365")
        return v


class CollectNewsRequest(BaseModel):
    sources: List[str] = Field(default_factory=list)
    limit_per_feed: int = 50

    @field_validator('sources')
    @classmethod
    def validate_sources(cls, v):
        if any((not isinstance(item, str) or not item.strip()) for item in v):
            raise ValueError("sources must contain non-empty strings")
        return [item.strip().lower() for item in v]
    
    @field_validator('limit_per_feed')
    @classmethod
    def validate_limit_per_feed(cls, v):
        """Validate limit_per_feed is positive and reasonable."""
        if v < 1:
            raise ValueError("limit_per_feed must be positive")
        if v > 1000:
            raise ValueError("limit_per_feed cannot exceed 1000")
        return v


class BrowserRequest(BaseModel):
    max_rows_per_target: int = 50

    @field_validator("max_rows_per_target")
    @classmethod
    def validate_max_rows_per_target(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_rows_per_target must be positive")
        if v > 1000:
            raise ValueError("max_rows_per_target cannot exceed 1000")
        return v


class RedditRequest(BaseModel):
    subreddits: List[str] = Field(default_factory=lambda: settings.reddit_subreddits)
    query: str = settings.reddit_query
    limit_per_subreddit: int = settings.reddit_limit_per_subreddit

    @field_validator("subreddits")
    @classmethod
    def validate_subreddits(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("subreddits list cannot be empty")
        if any((not isinstance(name, str) or not name.strip()) for name in v):
            raise ValueError("subreddits must be non-empty strings")
        return v

    @field_validator("limit_per_subreddit")
    @classmethod
    def validate_limit_per_subreddit(cls, v: int) -> int:
        if v < 1:
            raise ValueError("limit_per_subreddit must be positive")
        if v > 1000:
            raise ValueError("limit_per_subreddit cannot exceed 1000")
        return v


class MacroRequest(BaseModel):
    series: Dict[str, str] = Field(default_factory=lambda: settings.fred_series)

    @field_validator("series")
    @classmethod
    def validate_series(cls, v: Dict[str, str]) -> Dict[str, str]:
        if not v:
            raise ValueError("series cannot be empty")
        for alias, series_id in v.items():
            if not alias.strip() or not series_id.strip():
                raise ValueError("series alias and id must be non-empty")
        return v


class DesktopRequest(BaseModel):
    targets: Dict[str, str] = Field(default_factory=lambda: settings.desktop_targets)

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, v: Dict[str, str]) -> Dict[str, str]:
        if not v:
            raise ValueError("targets cannot be empty")
        return v


class StockMarketRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: settings.stock_symbols)
    period: str = settings.stock_market_period
    interval: str = settings.stock_market_interval

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("symbols list cannot be empty")
        if any((not isinstance(s, str) or not s.strip()) for s in v):
            raise ValueError("symbols must be non-empty strings")
        return v

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        valid_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
        if v not in valid_periods:
            raise ValueError(f"period must be one of {valid_periods}")
        return v

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        valid_intervals = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}
        if v not in valid_intervals:
            raise ValueError(f"interval must be one of {valid_intervals}")
        return v


class TradingStrategyRequest(BaseModel):
    subreddits: List[str] = Field(default_factory=lambda: settings.trading_strategy_subreddits)
    query: str = settings.trading_strategy_query
    limit_per_subreddit: int = settings.trading_strategy_limit_per_subreddit

    @field_validator("subreddits")
    @classmethod
    def validate_subreddits(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("subreddits list cannot be empty")
        if any((not isinstance(name, str) or not name.strip()) for name in v):
            raise ValueError("subreddits must be non-empty strings")
        return v

    @field_validator("limit_per_subreddit")
    @classmethod
    def validate_limit_per_subreddit(cls, v: int) -> int:
        if v < 1:
            raise ValueError("limit_per_subreddit must be positive")
        if v > 1000:
            raise ValueError("limit_per_subreddit cannot exceed 1000")
        return v


class TradingMistakesRequest(BaseModel):
    subreddits: List[str] = Field(default_factory=lambda: settings.trading_mistakes_subreddits)
    queries: List[str] = Field(default_factory=lambda: settings.trading_mistakes_queries)
    limit_per_subreddit: int = settings.trading_mistakes_limit_per_subreddit

    @field_validator("subreddits")
    @classmethod
    def validate_subreddits(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("subreddits list cannot be empty")
        if any((not isinstance(name, str) or not name.strip()) for name in v):
            raise ValueError("subreddits must be non-empty strings")
        return v

    @field_validator("queries")
    @classmethod
    def validate_queries(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("queries list cannot be empty")
        if any((not isinstance(q, str) or not q.strip()) for q in v):
            raise ValueError("queries must be non-empty strings")
        return v

    @field_validator("limit_per_subreddit")
    @classmethod
    def validate_limit_per_subreddit(cls, v: int) -> int:
        if v < 1:
            raise ValueError("limit_per_subreddit must be positive")
        if v > 1000:
            raise ValueError("limit_per_subreddit cannot exceed 1000")
        return v


class FinanceQueryStreamRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: settings.crypto_symbols + settings.stock_symbols)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("symbols list cannot be empty")
        if any((not isinstance(sym, str) or not sym.strip()) for sym in v):
            raise ValueError("symbols must be non-empty strings")
        return v


class PaperCloseRequest(BaseModel):
    exit_price: float

    @field_validator("exit_price")
    @classmethod
    def validate_exit_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("exit_price must be positive")
        return v


class ProcessSentimentRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("text must be a non-empty string")
        if len(v) > 5000:
            raise ValueError("text must be under 5000 characters")
        return v.strip()


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint.
    
    Returns:
        JSON with status and service name.
    """
    return {"status": "ok", "service": "volt-data-api"}


@app.post("/collect/market")
def collect_market(payload: CollectMarketRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect market data from Yahoo Finance with FCS/Binance fallback.
    
    Args:
        payload: MarketRequest with symbols, interval, and lookback_days.
    
    Returns:
        JSON with status, row count, and file path.
    """
    df = deps.market_collector.fetch(payload.symbols, payload.interval, payload.lookback_days)
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "market")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/news")
def collect_news(payload: CollectNewsRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect news from RSS feeds and score sentiment.
    
    Fetches articles, analyzes sentiment, and saves both raw
    and scored data.
    
    Args:
        payload: NewsRequest with limit_per_feed.
    
    Returns:
        JSON with status, row count, and file paths for raw and scored data.
    """
    selected_feeds = None
    if payload.sources:
        selected_feeds = {key: settings.rss_feeds[key] for key in payload.sources if key in settings.rss_feeds}
    if selected_feeds:
        news_df = deps.news_collector.fetch(feeds=selected_feeds, limit_per_feed=payload.limit_per_feed)
    else:
        news_df = deps.news_collector.fetch(limit_per_feed=payload.limit_per_feed)
    if news_df.empty:
        return {"status": "no_data", "rows": "0"}

    scored_df = deps.sentiment_processor.score_news(news_df)
    news_file = deps.raw_store.save(news_df, "news")
    scored_file = deps.processed_store.save(scored_df, "news_scored")

    return {
        "status": "ok",
        "rows": str(len(news_df)),
        "news_file": str(news_file),
        "news_scored_file": str(scored_file),
    }


@app.post("/process/sentiment")
def process_sentiment(payload: ProcessSentimentRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, float | str]:
    """Analyze sentiment for a single text payload."""
    single = deps.sentiment_processor.score_news(
        pd.DataFrame(
            {
                "title": [payload.text],
                "summary": [""],
            }
        )
    )
    if single.empty:
        return {
            "text": payload.text,
            "sentiment_neg": 0.0,
            "sentiment_neu": 0.0,
            "sentiment_pos": 0.0,
            "sentiment_compound": 0.0,
        }
    row = single.iloc[0]
    return {
        "text": payload.text,
        "sentiment_neg": float(row["sentiment_neg"]),
        "sentiment_neu": float(row["sentiment_neu"]),
        "sentiment_pos": float(row["sentiment_pos"]),
        "sentiment_compound": float(row["sentiment_compound"]),
    }


@app.post("/collect/browser")
def collect_browser(payload: BrowserRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect browser-rendered market pages with Playwright."""
    df = deps.browser_collector.fetch(
        targets=settings.browser_targets,
        max_rows_per_target=payload.max_rows_per_target,
    )
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "browser")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/reddit")
def collect_reddit(payload: RedditRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect Reddit posts via the official Reddit API (PRAW)."""
    df = deps.reddit_collector.fetch(
        subreddits=payload.subreddits,
        query=payload.query,
        limit_per_subreddit=payload.limit_per_subreddit,
    )
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "reddit")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/macro")
def collect_macro(payload: MacroRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect macroeconomic series from FRED."""
    df = deps.macro_collector.fetch(series_map=payload.series)
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "macro")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/desktop")
def collect_desktop(payload: DesktopRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect desktop snapshots and optional vision-extracted rows."""
    df = deps.desktop_collector.fetch(targets=payload.targets)
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "desktop")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/stock-market")
def collect_stock_market(payload: StockMarketRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect historical stock market data with technical indicators."""
    df = deps.stock_market_collector.fetch(
        symbols=payload.symbols,
        period=payload.period,
        interval=payload.interval,
    )
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "stock_market")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/trading-strategy")
def collect_trading_strategy(payload: TradingStrategyRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect trading strategies and discussions from Reddit."""
    df = deps.trading_strategy_collector.fetch(
        subreddits=payload.subreddits,
        query=payload.query,
        limit_per_subreddit=payload.limit_per_subreddit,
    )
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "trading_strategy")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/trading-mistakes")
def collect_trading_mistakes(payload: TradingMistakesRequest, deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Collect trading mistakes and financial error discussions from Reddit."""
    df = deps.trading_mistakes_collector.fetch(
        subreddits=payload.subreddits,
        queries=payload.queries,
        limit_per_subreddit=payload.limit_per_subreddit,
    )
    if df.empty:
        return {"status": "no_data", "rows": "0"}
    output_path = deps.raw_store.save(df, "trading_mistakes")
    return {"status": "ok", "rows": str(len(df)), "file": str(output_path)}


@app.post("/collect/full")
def collect_full(deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Run full collection pipeline and return execution summary."""
    return run_full_collection(
        settings,
        market_collector=deps.market_collector,
        news_collector=deps.news_collector,
        browser_collector=deps.browser_collector,
        reddit_collector=deps.reddit_collector,
        macro_collector=deps.macro_collector,
        desktop_collector=deps.desktop_collector,
        stock_market_collector=deps.stock_market_collector,
        trading_strategy_collector=deps.trading_strategy_collector,
        trading_mistakes_collector=deps.trading_mistakes_collector,
        sentiment_processor=deps.sentiment_processor,
        raw_store=deps.raw_store,
        processed_store=deps.processed_store,
        export_store=deps.export_store,
    )


@app.post("/stream/finance-query/config")
def finance_query_stream_config(payload: FinanceQueryStreamRequest) -> Dict[str, object]:
    """Return optional Finance Query websocket config for real-time streaming clients."""
    stream = FinanceQueryStream(
        enabled=settings.finance_query_stream_enabled,
        ws_url=settings.finance_query_ws_url,
        channels=settings.finance_query_channels,
    )
    return stream.stream_config(payload.symbols)


def _latest_or_empty(store: FileStore, prefix: str) -> str:
    """Return latest file path for prefix or empty string if not found."""
    candidate: Path | None = store.latest_file(prefix)
    return str(candidate) if candidate else ""


@app.get("/datasets/latest")
def latest_datasets(deps: AppDependencies = Depends(get_dependencies)) -> Dict[str, str]:
    """Get paths to most recent data files.
    
    Returns:
        Dict with keys: market, news, browser, reddit, macro, desktop, stock_market, trading_strategy, trading_mistakes, news_scored, training_export
    """
    return {
        "market": _latest_or_empty(deps.raw_store, "market"),
        "news": _latest_or_empty(deps.raw_store, "news"),
        "browser": _latest_or_empty(deps.raw_store, "browser"),
        "reddit": _latest_or_empty(deps.raw_store, "reddit"),
        "macro": _latest_or_empty(deps.raw_store, "macro"),
        "desktop": _latest_or_empty(deps.raw_store, "desktop"),
        "stock_market": _latest_or_empty(deps.raw_store, "stock_market"),
        "trading_strategy": _latest_or_empty(deps.raw_store, "trading_strategy"),
        "trading_mistakes": _latest_or_empty(deps.raw_store, "trading_mistakes"),
        "news_scored": _latest_or_empty(deps.processed_store, "news_scored"),
        "training_export": _latest_or_empty(deps.export_store, "training_export"),
    }


@app.get("/paper/pnl")
def paper_pnl() -> Dict[str, object]:
    """Return realized PnL from currently open virtual paper trades."""
    return paper_broker.get_pnl()


@app.post("/paper/close/{trade_id}")
def paper_close_trade(trade_id: str, payload: PaperCloseRequest) -> Dict[str, object]:
    """Close a virtual trade and return realized PnL summary for that trade."""
    return paper_broker.close_trade(trade_id=trade_id, exit_price=payload.exit_price)

@app.post("/stream/ingest")
async def ingest_stream_data(payload: dict):
    """Ingest a single websocket tick or array of ticks into the Canonical Feature Store."""
    import json
    await stream_worker.on_message(json.dumps(payload))
    return {"status": "buffered", "queued": len(stream_worker._buffer)}
