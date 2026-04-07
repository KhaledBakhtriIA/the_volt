"""Tests for newly added hybrid collectors."""

from unittest.mock import patch

import pandas as pd

from data_api.collectors.desktop_collector import DesktopCollector
from data_api.collectors.macro_collector import MacroCollector
from data_api.collectors.reddit_collector import RedditCollector
from data_api.collectors.vision_extractor import VisionExtractor


def test_reddit_collector_without_credentials_returns_empty() -> None:
    collector = RedditCollector(client_id="", client_secret="")
    result = collector.fetch(subreddits=["bitcoin"], query="market", limit_per_subreddit=3)
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_macro_collector_without_api_key_returns_empty() -> None:
    collector = MacroCollector(fred_api_key="")
    result = collector.fetch(series_map={"fed_funds_rate": "FEDFUNDS"})
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_desktop_collector_without_runtime_returns_empty() -> None:
    collector = DesktopCollector(vision_extractor=VisionExtractor(enabled=False))
    with patch.object(collector, "_capture", return_value=None):
        result = collector.fetch(targets={"terminal": "active_screen"})
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_desktop_collector_with_capture_adds_required_columns(tmp_path) -> None:
    collector = DesktopCollector(vision_extractor=VisionExtractor(enabled=False))
    fake_image = tmp_path / "screen.png"
    fake_image.write_bytes(b"x")

    with patch.object(collector, "_capture", return_value=fake_image):
        result = collector.fetch(targets={"terminal": "active_screen"})

    assert not result.empty
    assert {"timestamp", "source", "fetched_at_utc"}.issubset(result.columns)
