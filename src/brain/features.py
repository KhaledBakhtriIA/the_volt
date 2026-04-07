import numpy as np
import pandas as pd

def calculate_std(df: pd.DataFrame, window: int = 20, column: str = "close") -> pd.Series:
    """
    Calculate rolling Standard Deviation of the price.
    """
    return df[column].rolling(window=window).std()

def calculate_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Calculate the Average True Range (ATR).
    """
    high = df['high']
    low = df['low']
    prev_close = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=window).mean()
    return atr

def add_3sigma_target(df: pd.DataFrame, std_window: int = 20, horizon: int = 4) -> pd.DataFrame:
    """
    Creates a binary target: 1 if a 3-sigma move occurs within the next `horizon` bars, else 0.
    """
    out = df.copy()
    
    out['std_20'] = calculate_std(out, window=std_window)
    
    out['future_max_high'] = out['high'].shift(-1).rolling(window=horizon).max().shift(-(horizon-1))
    out['future_min_low']  = out['low'].shift(-1).rolling(window=horizon).min().shift(-(horizon-1))
    
    upper_bound = out['close'] + (3 * out['std_20'])
    lower_bound = out['close'] - (3 * out['std_20'])
    
    out['target_3sigma_breakout'] = (
        (out['future_max_high'] >= upper_bound) | 
        (out['future_min_low'] <= lower_bound)
    ).astype(int)
    
    out.loc[out.index[-horizon:], 'target_3sigma_breakout'] = np.nan
    
    return out
