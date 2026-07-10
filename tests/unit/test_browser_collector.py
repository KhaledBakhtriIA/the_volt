"""Tests for BrowserCollector."""

from unittest.mock import patch

import pandas as pd

from data_layer.collectors.browser_collector import BrowserCollector


def test_fetch_returns_empty_for_no_targets() -> None:
    collector = BrowserCollector()
    result = collector.fetch(targets={})
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_fetch_combines_multiple_targets() -> None:
    collector = BrowserCollector()

    target_a = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-01-01T00:00:00Z")],
            "source": ["tradingview"],
            "fetched_at_utc": ["2026-01-01T00:00:01Z"],
            "title": ["A"],
            "value": ["A row"],
            "target_url": ["https://example.com/a"],
        }
    )
    target_b = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-01-02T00:00:00Z")],
            "source": ["investing"],
            "fetched_at_utc": ["2026-01-02T00:00:01Z"],
            "title": ["B"],
            "value": ["B row"],
            "target_url": ["https://example.com/b"],
        }
    )

    with patch.object(collector, "_fetch_target", side_effect=[target_a, target_b]):
        result = collector.fetch(targets={"tradingview": "https://a", "investing": "https://b"})

    assert len(result) == 2
    assert {"timestamp", "source", "fetched_at_utc"}.issubset(result.columns)


def test_fetch_skips_failed_target_and_keeps_success() -> None:
    collector = BrowserCollector()

    good_df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-01-01T00:00:00Z")],
            "source": ["investing"],
            "fetched_at_utc": ["2026-01-01T00:00:01Z"],
            "title": ["ok"],
            "value": ["row"],
            "target_url": ["https://example.com/b"],
        }
    )

    with patch.object(collector, "_fetch_target", side_effect=[pd.DataFrame(), good_df]):
        result = collector.fetch(targets={"tradingview": "https://a", "investing": "https://b"})

    assert len(result) == 1
    assert result.iloc[0]["source"] == "investing"
