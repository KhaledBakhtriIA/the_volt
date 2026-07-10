"""Trading strategy and discussion collector from Reddit."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd

from data_layer.collectors.collector_contract import ensure_collector_contract

logger = logging.getLogger(__name__)


class TradingStrategyCollector:
    """Collect trading strategies and discussions from Reddit trading communities."""

    def __init__(self, reddit_client_id: str = "", reddit_client_secret: str = "", reddit_user_agent: str = "") -> None:
        self.reddit_client_id = reddit_client_id
        self.reddit_client_secret = reddit_client_secret
        self.reddit_user_agent = reddit_user_agent or "volt-data-api/1.0"

    def _build_client(self):
        """Initialize PRAW Reddit client with credentials."""
        try:
            import praw  # type: ignore
        except Exception:
            return None

        if not self.reddit_client_id or not self.reddit_client_secret:
            logger.warning("Reddit credentials missing; trading strategy collection disabled")
            return None

        try:
            reddit = praw.Reddit(
                client_id=self.reddit_client_id,
                client_secret=self.reddit_client_secret,
                user_agent=self.reddit_user_agent,
            )
            return reddit
        except Exception as exc:
            logger.warning("Failed to initialize Reddit client: %s", exc)
            return None

    def fetch(
        self,
        subreddits: List[str] | None = None,
        query: str = "strategy",
        limit_per_subreddit: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch trading strategy discussions from Reddit.

        Args:
            subreddits: List of subreddit names (e.g., ["stocks", "investing", "daytraders"])
            query: Search query for posts (e.g., "strategy", "trading plan")
            limit_per_subreddit: Max posts per subreddit

        Returns:
            DataFrame with columns: timestamp, source, fetched_at_utc, subreddit, post_title, post_text, score, comments, strategy_type
        """
        if not subreddits:
            subreddits = ["stocks", "investing", "daytraders", "wallstreetbets", "options", "Forex"]

        reddit = self._build_client()
        if not reddit:
            logger.warning("Trading strategy collection disabled (no Reddit credentials)")
            return pd.DataFrame()

        all_data = []
        fetched_at_utc = datetime.now(timezone.utc)

        for subreddit_name in subreddits:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                posts = list(subreddit.search(query, limit=limit_per_subreddit, sort="top", time_filter="week"))

                for post in posts:
                    try:
                        # Detect strategy type from post content
                        content = (post.title + " " + post.selftext).lower()
                        strategy_type = "unknown"
                        if any(term in content for term in ["technical analysis", "rsi", "macd", "bollinger bands"]):
                            strategy_type = "technical_analysis"
                        elif any(term in content for term in ["fundamental", "earnings", "pe ratio", "cash flow"]):
                            strategy_type = "fundamental_analysis"
                        elif any(term in content for term in ["momentum", "trend", "reversal"]):
                            strategy_type = "momentum_trading"
                        elif any(term in content for term in ["dividend", "income", "yield"]):
                            strategy_type = "income_trading"
                        elif any(term in content for term in ["swing", "short term", "day trade"]):
                            strategy_type = "swing_trading"
                        elif any(term in content for term in ["value", "undervalued", "intrinsic"]):
                            strategy_type = "value_investing"

                        all_data.append({
                            "timestamp": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                            "source": f"reddit_{subreddit_name}",
                            "fetched_at_utc": fetched_at_utc,
                            "subreddit": subreddit_name,
                            "post_title": post.title[:500],
                            "post_text": post.selftext[:1000],
                            "score": post.score,
                            "num_comments": post.num_comments,
                            "strategy_type": strategy_type,
                            "upvote_ratio": post.upvote_ratio,
                        })
                    except Exception as exc:
                        logger.debug("Failed to process post: %s", exc)
                        continue

                logger.debug("Collected %d posts from r/%s for query '%s'", len(posts), subreddit_name, query)

            except Exception as exc:
                logger.warning("Failed to fetch posts from r/%s: %s", subreddit_name, exc)
                continue

        if not all_data:
            logger.warning("No trading strategy posts collected")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        return ensure_collector_contract(df, "trading_strategy", "timestamp")
