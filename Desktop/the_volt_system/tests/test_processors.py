"""Tests for data processors (sentiment analysis, etc.)."""

import pandas as pd
import pytest

from data_api.processors.sentiment import SentimentProcessor


class TestSentimentProcessorBasic:
    """Basic tests for SentimentProcessor."""

    def test_processor_initializes(self):
        """SentimentProcessor should initialize without errors."""
        processor = SentimentProcessor()
        assert processor is not None

    def test_score_news_returns_dataframe(self):
        """score_news() should return a DataFrame."""
        processor = SentimentProcessor()
        news_df = pd.DataFrame({
            "title": ["Bitcoin Rises"],
            "summary": ["Bitcoin price increases"],
        })
        result = processor.score_news(news_df)
        assert isinstance(result, pd.DataFrame)

    def test_score_news_handles_empty_df(self):
        """score_news() should handle empty DataFrame."""
        processor = SentimentProcessor()
        empty_df = pd.DataFrame()
        result = processor.score_news(empty_df)
        assert result.empty

    def test_score_news_adds_sentiment_columns(self):
        """score_news() should add sentiment score columns."""
        processor = SentimentProcessor()
        news_df = pd.DataFrame({
            "title": ["Bitcoin Rises"],
            "summary": ["Price increases"],
        })
        result = processor.score_news(news_df)

        required_cols = ["sentiment_neg", "sentiment_neu", "sentiment_pos", "sentiment_compound"]
        for col in required_cols:
            assert col in result.columns

    def test_score_news_preserves_columns(self):
        """score_news() should preserve original data columns."""
        processor = SentimentProcessor()
        news_df = pd.DataFrame({
            "title": ["Article 1"],
            "summary": ["Summary 1"],
            "source": ["coindesk"],
        })
        result = processor.score_news(news_df)
        assert "source" in result.columns
        assert result["source"].iloc[0] == "coindesk"

    def test_score_news_handles_missing_fields(self):
        """score_news() should handle missing title/summary."""
        processor = SentimentProcessor()
        news_df = pd.DataFrame({
            "title": [None, "Article"],
            "summary": ["Summary", None],
        })
        result = processor.score_news(news_df)
        assert len(result) == 2

    def test_score_news_multiple_articles(self):
        """score_news() should handle multiple articles."""
        processor = SentimentProcessor()
        news_df = pd.DataFrame({
            "title": ["Bitcoin Rises", "Bitcoin Falls", "Bitcoin Stable"],
            "summary": ["Good", "Bad", "Neutral"],
        })
        result = processor.score_news(news_df)
        assert len(result) == 3

    def test_get_analyzer_caches_instance(self):
        """_get_analyzer() should cache the analyzer."""
        processor = SentimentProcessor()
        analyzer1 = processor._get_analyzer()
        analyzer2 = processor._get_analyzer()
        assert analyzer1 is analyzer2

    def test_sentiment_scores_are_numeric(self):
        """Sentiment scores should be numeric."""
        processor = SentimentProcessor()
        news_df = pd.DataFrame({
            "title": ["Test Article"],
            "summary": ["Test summary"],
        })
        result = processor.score_news(news_df)

        assert pd.api.types.is_numeric_dtype(result["sentiment_neg"])
        assert pd.api.types.is_numeric_dtype(result["sentiment_compound"])

    def test_df_not_modified_in_place(self):
        """score_news() should not modify input DataFrame in-place."""
        processor = SentimentProcessor()
        news_df = pd.DataFrame({"title": ["Test"], "summary": ["Test"]})
        original_cols = set(news_df.columns)

        processor.score_news(news_df)

        # Original DataFrame should be unchanged
        assert set(news_df.columns) == original_cols
