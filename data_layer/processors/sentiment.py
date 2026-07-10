from __future__ import annotations

import pandas as pd
from nltk import download
from nltk.sentiment import SentimentIntensityAnalyzer


class SentimentProcessor:
    """Analyze sentiment of news articles using VADER sentiment analysis.
    
    Uses NLTK's VADER (Valence Aware Dictionary and sEntiment Reasoner) to
    compute sentiment scores for text. Loads the VADER lexicon at startup
    to fail fast during service boot instead of first request.
    """
    
    def __init__(self) -> None:
        download("vader_lexicon", quiet=True)
        self._analyzer: SentimentIntensityAnalyzer | None = SentimentIntensityAnalyzer()

    def _get_analyzer(self) -> SentimentIntensityAnalyzer:
        """Get or initialize the VADER sentiment analyzer.
        
        Returns:
            SentimentIntensityAnalyzer instance (cached after first call).
        """
        if self._analyzer is None:
            download("vader_lexicon", quiet=True)
            self._analyzer = SentimentIntensityAnalyzer()
        return self._analyzer

    def score_news(self, news_df: pd.DataFrame) -> pd.DataFrame:
        """Score sentiment of news articles.
        
        Combines title and summary, then analyzes using VADER.
        Adds four sentiment score columns to the DataFrame.
        
        Args:
            news_df: DataFrame with 'title' and 'summary' columns.
        
        Returns:
            DataFrame with added columns:
            - sentiment_neg: Negative score (0-1)
            - sentiment_neu: Neutral score (0-1)
            - sentiment_pos: Positive score (0-1)
            - sentiment_compound: Overall sentiment (-1 to 1)
            - text: Combined title + summary for reference
        """
        if news_df.empty:
            return news_df

        analyzer = self._get_analyzer()
        scored = news_df.copy()
        scored["text"] = (scored["title"].fillna("") + " " + scored["summary"].fillna("")).str.strip()
        sentiment = scored["text"].apply(analyzer.polarity_scores)

        scored["sentiment_neg"] = sentiment.apply(lambda x: x["neg"])
        scored["sentiment_neu"] = sentiment.apply(lambda x: x["neu"])
        scored["sentiment_pos"] = sentiment.apply(lambda x: x["pos"])
        scored["sentiment_compound"] = sentiment.apply(lambda x: x["compound"])
        return scored
