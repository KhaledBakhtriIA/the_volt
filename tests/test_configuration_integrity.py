from __future__ import annotations

from data_api.collectors.news_collector import NewsCollector
from data_api.config.settings import Settings
from data_api.processors.sentiment import SentimentProcessor


def test_sentiment_processor_eager_initialization() -> None:
    processor = SentimentProcessor()
    assert processor._analyzer is not None


def test_news_collector_uses_injected_rss_feeds() -> None:
    feeds = {"custom": "https://example.com/rss"}
    collector = NewsCollector(rss_feeds=feeds)
    assert collector.rss_feeds == feeds


def test_settings_exposes_rss_feeds_mapping() -> None:
    settings = Settings()
    assert isinstance(settings.rss_feeds, dict)
    assert len(settings.rss_feeds) >= 1
