from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import pandas as pd

from data_api.collectors.browser_collector import BrowserCollector
from data_api.collectors.desktop_collector import DesktopCollector
from data_api.collectors.macro_collector import MacroCollector
from data_api.collectors.market_collector import MarketCollector
from data_api.collectors.news_collector import NewsCollector
from data_api.collectors.reddit_collector import RedditCollector
from data_api.collectors.stock_market_collector import StockMarketCollector
from data_api.collectors.trading_strategy_collector import TradingStrategyCollector
from data_api.collectors.trading_mistakes_collector import TradingMistakesCollector
from data_api.collectors.vision_extractor import VisionExtractor
from data_api.config.settings import Settings
from data_api.processors.sentiment import SentimentProcessor
from data_api.processors.technical_indicators import TechnicalIndicatorProcessor
from data_api.storage.file_store import FileStore


def _build_training_export(market_df: pd.DataFrame, news_sentiment_df: pd.DataFrame) -> pd.DataFrame:
    """Build merged training dataset from market and daily news sentiment."""
    if market_df.empty:
        return pd.DataFrame()

    market = market_df.copy()
    market["timestamp"] = pd.to_datetime(market["timestamp"], utc=True, errors="coerce")
    market = market.dropna(subset=["timestamp"])

    # Add technical indicators by symbol
    market = TechnicalIndicatorProcessor.add_indicators_to_df(market, "close")

    news_daily = pd.DataFrame()
    if not news_sentiment_df.empty:
        news = news_sentiment_df.copy()
        news["published"] = pd.to_datetime(news["published"], utc=True, errors="coerce")
        news = news.dropna(subset=["published"])
        news["day"] = news["published"].dt.floor("d")
        news_daily = (
            news.groupby("day", as_index=False)
            .agg(
                news_count=("title", "count"),
                sentiment_compound_mean=("sentiment_compound", "mean"),
                sentiment_pos_mean=("sentiment_pos", "mean"),
                sentiment_neg_mean=("sentiment_neg", "mean"),
            )
            .sort_values("day")
        )

    market["day"] = market["timestamp"].dt.floor("d")
    merged = market.merge(news_daily, how="left", on="day")
    merged["news_count"] = merged["news_count"].fillna(0)
    for col in ["sentiment_compound_mean", "sentiment_pos_mean", "sentiment_neg_mean"]:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0.0)

    return merged.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def run_full_collection(
    settings: Settings,
    market_collector: MarketCollector | None = None,
    news_collector: NewsCollector | None = None,
    browser_collector: BrowserCollector | None = None,
    reddit_collector: RedditCollector | None = None,
    macro_collector: MacroCollector | None = None,
    desktop_collector: DesktopCollector | None = None,
    stock_market_collector: StockMarketCollector | None = None,
    trading_strategy_collector: TradingStrategyCollector | None = None,
    trading_mistakes_collector: TradingMistakesCollector | None = None,
    sentiment_processor: SentimentProcessor | None = None,
    raw_store: FileStore | None = None,
    processed_store: FileStore | None = None,
    export_store: FileStore | None = None,
) -> Dict[str, str]:
    """Run full data collection pipeline with optional dependency injection."""
    market_collector = market_collector or MarketCollector(fcs_api_key=settings.fcs_api_key)
    news_collector = news_collector or NewsCollector(
        tokeninsight_api_key=settings.tokeninsight_api_key,
        tokeninsight_enabled=settings.tokeninsight_enabled,
    )
    browser_collector = browser_collector or BrowserCollector(
        headless=settings.browser_headless,
        timeout_ms=settings.browser_timeout_ms,
    )
    reddit_collector = reddit_collector or RedditCollector(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )
    macro_collector = macro_collector or MacroCollector(fred_api_key=settings.fred_api_key)
    desktop_collector = desktop_collector or DesktopCollector(
        vision_extractor=VisionExtractor(enabled=settings.vision_enabled)
    )
    stock_market_collector = stock_market_collector or StockMarketCollector()
    trading_strategy_collector = trading_strategy_collector or TradingStrategyCollector(
        reddit_client_id=settings.reddit_client_id,
        reddit_client_secret=settings.reddit_client_secret,
        reddit_user_agent=settings.reddit_user_agent,
    )
    trading_mistakes_collector = trading_mistakes_collector or TradingMistakesCollector(
        reddit_client_id=settings.reddit_client_id,
        reddit_client_secret=settings.reddit_client_secret,
        reddit_user_agent=settings.reddit_user_agent,
    )
    sentiment_processor = sentiment_processor or SentimentProcessor()

    raw_store = raw_store or FileStore(settings.raw_dir)
    processed_store = processed_store or FileStore(settings.processed_dir)
    export_store = export_store or FileStore(settings.export_dir)

    # Collect from crypto, stocks, and macro symbols
    symbols = settings.crypto_symbols + settings.stock_symbols + settings.macro_symbols
    market_df = market_collector.fetch(symbols=symbols, interval=settings.interval, lookback_days=settings.lookback_days)
    news_df = news_collector.fetch()
    browser_df = pd.DataFrame()
    reddit_df = pd.DataFrame()
    macro_df = pd.DataFrame()
    desktop_df = pd.DataFrame()
    stock_market_df = pd.DataFrame()
    trading_strategy_df = pd.DataFrame()
    trading_mistakes_df = pd.DataFrame()

    if settings.browser_enabled:
        browser_df = browser_collector.fetch(targets=settings.browser_targets)
    if settings.reddit_enabled:
        reddit_df = reddit_collector.fetch(
            subreddits=settings.reddit_subreddits,
            query=settings.reddit_query,
            limit_per_subreddit=settings.reddit_limit_per_subreddit,
        )
    if settings.macro_enabled:
        macro_df = macro_collector.fetch(series_map=settings.fred_series)
    if settings.desktop_enabled:
        desktop_df = desktop_collector.fetch(targets=settings.desktop_targets)
    if settings.stock_market_enabled:
        stock_market_df = stock_market_collector.fetch(
            symbols=settings.stock_symbols,
            period=settings.stock_market_period,
            interval=settings.stock_market_interval,
        )
    if settings.trading_strategy_enabled:
        trading_strategy_df = trading_strategy_collector.fetch(
            subreddits=settings.trading_strategy_subreddits,
            query=settings.trading_strategy_query,
            limit_per_subreddit=settings.trading_strategy_limit_per_subreddit,
        )
    if settings.trading_mistakes_enabled:
        trading_mistakes_df = trading_mistakes_collector.fetch(
            subreddits=settings.trading_mistakes_subreddits,
            queries=settings.trading_mistakes_queries,
            limit_per_subreddit=settings.trading_mistakes_limit_per_subreddit,
        )

    scored_news_df = sentiment_processor.score_news(news_df)
    export_df = _build_training_export(market_df, scored_news_df)

    result: Dict[str, str] = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "market_rows": str(len(market_df)),
        "news_rows": str(len(news_df)),
        "browser_rows": str(len(browser_df)),
        "reddit_rows": str(len(reddit_df)),
        "macro_rows": str(len(macro_df)),
        "desktop_rows": str(len(desktop_df)),
        "stock_market_rows": str(len(stock_market_df)),
        "trading_strategy_rows": str(len(trading_strategy_df)),
        "trading_mistakes_rows": str(len(trading_mistakes_df)),
        "export_rows": str(len(export_df)),
    }

    if not market_df.empty:
        result["market_file"] = str(raw_store.save(market_df, "market"))
    if not news_df.empty:
        result["news_file"] = str(raw_store.save(news_df, "news"))
    if not browser_df.empty:
        result["browser_file"] = str(raw_store.save(browser_df, "browser"))
    if not reddit_df.empty:
        result["reddit_file"] = str(raw_store.save(reddit_df, "reddit"))
    if not macro_df.empty:
        result["macro_file"] = str(raw_store.save(macro_df, "macro"))
    if not desktop_df.empty:
        result["desktop_file"] = str(raw_store.save(desktop_df, "desktop"))
    if not stock_market_df.empty:
        result["stock_market_file"] = str(raw_store.save(stock_market_df, "stock_market"))
    if not trading_strategy_df.empty:
        result["trading_strategy_file"] = str(raw_store.save(trading_strategy_df, "trading_strategy"))
    if not trading_mistakes_df.empty:
        result["trading_mistakes_file"] = str(raw_store.save(trading_mistakes_df, "trading_mistakes"))
    if not scored_news_df.empty:
        result["news_scored_file"] = str(processed_store.save(scored_news_df, "news_scored"))
    if not export_df.empty:
        result["training_export_file"] = str(export_store.save(export_df, "training_export"))

    return result
