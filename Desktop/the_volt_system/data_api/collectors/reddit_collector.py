from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd

from data_api.collectors.collector_contract import ensure_collector_contract

logger = logging.getLogger(__name__)


class RedditCollector:
    """Collect structured Reddit submissions using PRAW."""

    def __init__(self, client_id: str = "", client_secret: str = "", user_agent: str = "volt-data-api/1.0") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent

    def _build_client(self):
        try:
            import praw  # type: ignore
        except Exception:
            logger.warning("PRAW is not installed; skipping Reddit collection")
            return None

        if not self.client_id or not self.client_secret:
            logger.warning("Reddit credentials missing; skipping Reddit collection")
            return None

        return praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
            check_for_async=False,
        )

    def fetch(
        self,
        subreddits: List[str],
        query: str = "market",
        limit_per_subreddit: int = 50,
        sort: str = "new",
    ) -> pd.DataFrame:
        """Fetch Reddit submissions from one or more subreddits."""
        if not subreddits:
            return pd.DataFrame(columns=["timestamp", "source", "fetched_at_utc"])

        client = self._build_client()
        if client is None:
            return pd.DataFrame(columns=["timestamp", "source", "fetched_at_utc"])

        rows: List[dict] = []
        for subreddit_name in subreddits:
            try:
                subreddit = client.subreddit(subreddit_name)
                if sort == "hot":
                    submissions = subreddit.hot(limit=limit_per_subreddit)
                elif sort == "top":
                    submissions = subreddit.top(limit=limit_per_subreddit, time_filter="day")
                else:
                    submissions = subreddit.search(query, limit=limit_per_subreddit, sort="new")

                for post in submissions:
                    rows.append(
                        {
                            "timestamp": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                            "source": "reddit",
                            "subreddit": subreddit_name,
                            "title": getattr(post, "title", "") or "",
                            "text": getattr(post, "selftext", "") or "",
                            "score": int(getattr(post, "score", 0) or 0),
                            "num_comments": int(getattr(post, "num_comments", 0) or 0),
                            "url": getattr(post, "url", "") or "",
                            "author": str(getattr(post, "author", "") or ""),
                            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            except Exception as exc:
                logger.warning("Reddit fetch failed for subreddit '%s': %s", subreddit_name, exc)

        if not rows:
            return pd.DataFrame(columns=["timestamp", "source", "fetched_at_utc"])

        result = pd.DataFrame(rows)
        result = ensure_collector_contract(result, source="reddit", timestamp_col="timestamp")
        return result.sort_values(["subreddit", "timestamp"], ascending=[True, False]).reset_index(drop=True)
