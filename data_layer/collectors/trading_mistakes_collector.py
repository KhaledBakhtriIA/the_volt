"""Trading mistakes and financial errors collector from Reddit."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd

from data_layer.collectors.collector_contract import ensure_collector_contract

logger = logging.getLogger(__name__)


class TradingMistakesCollector:
    """Collect trading mistakes, losses, and financial errors from Reddit communities."""

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
            logger.warning("Reddit credentials missing; trading mistakes collection disabled")
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
        queries: List[str] | None = None,
        limit_per_subreddit: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch trading mistakes and financial error discussions from Reddit.

        Args:
            subreddits: List of subreddit names for trading/investing communities
            queries: Search queries for mistakes/losses (e.g., ["loss", "mistake", "bad trade"])
            limit_per_subreddit: Max posts per subreddit

        Returns:
            DataFrame with columns: timestamp, source, fetched_at_utc, subreddit, post_title, post_text, score, comments, mistake_type, sentiment
        """
        if not subreddits:
            subreddits = ["stocks", "investing", "wallstreetbets", "options", "Forex", "daytraders"]

        if not queries:
            queries = ["loss", "mistake", "bad trade", "liquidated", "margin call", "blew account"]

        reddit = self._build_client()
        if not reddit:
            logger.warning("Trading mistakes collection disabled (no Reddit credentials)")
            return pd.DataFrame()

        all_data = []
        fetched_at_utc = datetime.now(timezone.utc)

        for subreddit_name in subreddits:
            for query in queries:
                try:
                    subreddit = reddit.subreddit(subreddit_name)
                    posts = list(subreddit.search(query, limit=limit_per_subreddit, sort="top", time_filter="month"))

                    for post in posts:
                        try:
                            content = (post.title + " " + post.selftext).lower()

                            # Classify mistake type
                            mistake_type = "unclassified"
                            if any(term in content for term in ["leverage", "margin", "margin call"]):
                                mistake_type = "excessive_leverage"
                            elif any(term in content for term in ["fomo", "panic", "emotional"]):
                                mistake_type = "emotional_trading"
                            elif any(term in content for term in ["stop loss", "no stop loss", "didn't have stop"]):
                                mistake_type = "risk_management_failure"
                            elif any(term in content for term in ["overconcentrated", "all in", "single stock"]):
                                mistake_type = "poor_diversification"
                            elif any(term in content for term in ["options", "calls", "puts", "expired"]):
                                mistake_type = "options_mismanagement"
                            elif any(term in content for term in ["timing", "buy high", "sell low"]):
                                mistake_type = "poor_timing"
                            elif any(term in content for term in ["hold too long", "held", "diamond hands"]):
                                mistake_type = "holding_too_long"
                            elif any(term in content for term in ["fees", "commission", "slippage"]):
                                mistake_type = "high_costs"

                            # Estimate sentiment (negative for losses/mistakes)
                            sentiment = "negative"
                            if any(term in content for term in ["learned", "lesson", "improved", "better"]):
                                sentiment = "reflective"
                            elif any(term in content for term in ["glad", "lucky", "dodged", "avoided"]):
                                sentiment = "cautious"

                            # Calculate loss percentage if mentioned
                            loss_pct = 0.0
                            for word in content.split():
                                if "%" in word:
                                    try:
                                        num = float(word.replace("%", "").replace(",", ""))
                                        if -1000 < num < 0:
                                            loss_pct = num
                                            break
                                    except ValueError:
                                        continue

                            all_data.append({
                                "timestamp": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                                "source": f"reddit_{subreddit_name}_{query}",
                                "fetched_at_utc": fetched_at_utc,
                                "subreddit": subreddit_name,
                                "post_title": post.title[:500],
                                "post_text": post.selftext[:1000],
                                "score": post.score,
                                "num_comments": post.num_comments,
                                "mistake_type": mistake_type,
                                "sentiment": sentiment,
                                "estimated_loss_pct": loss_pct,
                                "upvote_ratio": post.upvote_ratio,
                            })
                        except Exception as exc:
                            logger.debug("Failed to process mistake post: %s", exc)
                            continue

                    logger.debug("Collected %d posts from r/%s with query '%s'", len(posts), subreddit_name, query)

                except Exception as exc:
                    logger.warning("Failed to fetch posts from r/%s with query %s: %s", subreddit_name, query, exc)
                    continue

        if not all_data:
            logger.warning("No trading mistake posts collected")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        return ensure_collector_contract(df, "trading_mistakes", "timestamp")
