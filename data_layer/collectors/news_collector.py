from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

import feedparser
import pandas as pd
import requests
from dateutil import parser as dateutil_parser

DEFAULT_RSS_FEEDS: Dict[str, str] = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "bitcoinmagazine": "https://bitcoinmagazine.com/.rss/full/",
}


class NewsCollector:
    """Collect cryptocurrency news from RSS feeds.
    
    Default feeds include major crypto news sources. Can accept custom feeds.
    All entries are fetched, parsed, and converted to a DataFrame with
    standardized columns including published date and source.
    """
    
    def __init__(
        self,
        tokeninsight_api_key: str = "",
        tokeninsight_enabled: bool = False,
        rss_feeds: Dict[str, str] | None = None,
    ) -> None:
        self.tokeninsight_api_key = tokeninsight_api_key
        self.tokeninsight_enabled = tokeninsight_enabled
        self.rss_feeds = dict(rss_feeds) if rss_feeds else dict(DEFAULT_RSS_FEEDS)

    def _extract_tokeninsight_items(self, payload: dict) -> List[dict]:
        """Extract news items from flexible TokenInsight response shapes."""
        data = payload.get("data")
        if isinstance(data, dict):
            items = data.get("list") or data.get("items") or data.get("news") or []
            return items if isinstance(items, list) else []
        if isinstance(data, list):
            return data
        fallback = payload.get("news")
        return fallback if isinstance(fallback, list) else []

    def _fetch_tokeninsight_news(self, limit: int) -> List[dict]:
        """Fetch crypto news and provider sentiment from TokenInsight."""
        if not self.tokeninsight_enabled or not self.tokeninsight_api_key:
            return []

        try:
            response = requests.get(
                "https://api.tokeninsight.com/api/v1/news",
                headers={
                    "Authorization": f"Bearer {self.tokeninsight_api_key}",
                    "X-API-KEY": self.tokeninsight_api_key,
                },
                params={"limit": limit},
                timeout=20,
            )
        except requests.RequestException:
            return []

        if response.status_code != 200:
            return []

        try:
            payload = response.json()
        except ValueError:
            return []

        if not isinstance(payload, dict):
            return []

        rows: List[dict] = []
        fetched = datetime.now(timezone.utc).isoformat()
        for item in self._extract_tokeninsight_items(payload)[:limit]:
            if not isinstance(item, dict):
                continue

            sentiment = item.get("sentiment")
            sentiment_score = None
            sentiment_label = ""
            if isinstance(sentiment, dict):
                sentiment_score = sentiment.get("score")
                sentiment_label = str(sentiment.get("label") or "")
            elif sentiment is not None:
                sentiment_score = sentiment

            published = (
                item.get("publishedAt")
                or item.get("published_at")
                or item.get("timestamp")
                or item.get("time")
            )

            rows.append(
                {
                    "source": "tokeninsight",
                    "title": item.get("title", ""),
                    "summary": item.get("summary") or item.get("content") or "",
                    "link": item.get("url") or item.get("link") or "",
                    "published": published,
                    "fetched_at_utc": fetched,
                    "provider_sentiment": sentiment_score,
                    "provider_sentiment_label": sentiment_label,
                }
            )

        return rows

    def _parse_published_timestamp(self, value: object) -> pd.Timestamp:
        """Parse mixed timestamp shapes into UTC without pandas inference warnings."""
        if value is None:
            return pd.NaT

        if isinstance(value, (int, float)):
            # Treat large values as milliseconds, otherwise seconds.
            unit = "ms" if abs(value) > 10**11 else "s"
            try:
                return pd.to_datetime(value, unit=unit, utc=True, errors="coerce")
            except (OverflowError, ValueError, TypeError):
                return pd.NaT

        text = str(value).strip()
        if not text:
            return pd.NaT

        try:
            dt = dateutil_parser.parse(text)
        except (TypeError, ValueError, OverflowError):
            return pd.NaT

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        return pd.Timestamp(dt)

    def fetch(self, feeds: Dict[str, str] | None = None, limit_per_feed: int = 50) -> pd.DataFrame:
        """Fetch news articles from RSS feeds.
        
        Args:
            feeds: Custom feed dictionary mapping source name to URL.
                  If None, uses default RSS_FEEDS.
            limit_per_feed: Maximum articles to fetch from each feed. Defaults to 50.
        
        Returns:
            DataFrame with columns: source, title, summary, link, published, fetched_at_utc.
            Sorted by published date (most recent first).
            Returns empty DataFrame if no articles found.
        """
        selected_feeds = feeds or self.rss_feeds
        rows: List[dict] = []

        for source, url in selected_feeds.items():
            parsed = feedparser.parse(url)
            entries = parsed.entries[:limit_per_feed]

            for entry in entries:
                published = entry.get("published") or entry.get("updated")
                rows.append(
                    {
                        "source": source,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "link": entry.get("link", ""),
                        "published": published,
                        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )

        # Optional provider-grade crypto sentiment source.
        rows.extend(self._fetch_tokeninsight_news(limit_per_feed))

        if not rows:
            return pd.DataFrame()

        news = pd.DataFrame(rows)
        news["published"] = news["published"].apply(self._parse_published_timestamp)
        news = news.dropna(subset=["published"]).sort_values("published", ascending=False).reset_index(drop=True)
        return news
