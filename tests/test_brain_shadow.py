import numpy as np
import pandas as pd
import pytest

# Import the newly extracted Brain module logic
from src.brain.features import calculate_std, calculate_atr, add_3sigma_target
from src.brain.models import xgboost_dispatcher

def test_shadow_feature_extraction():
    """
    Shadow test to verify that the extracted src/brain/ logic perfectly matches
    the raw notebook logic byte-for-byte on identically shaped data.
    """
    # 1. Create a deterministic synthetic OHLCV dataset
    np.random.seed(42)
    size = 100
    df = pd.DataFrame({
        'open': np.random.uniform(100, 110, size),
        'high': np.random.uniform(110, 120, size),
        'low': np.random.uniform(90, 100, size),
        'close': np.random.uniform(95, 115, size),
        'volume': np.random.uniform(1000, 5000, size)
    })
    
    # Ensure high is highest and low is lowest
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)

    # 2. Notebook Reference Logic (Raw inline as requested by user)
    def nb_calculate_std(d, window=20, column="close"):
        return d[column].rolling(window=window).std()

    def nb_calculate_atr(d, window=14):
        high = d['high']
        low = d['low']
        prev_close = d['close'].shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()

    def nb_add_3sigma_target(d, std_window=20, horizon=4):
        out = d.copy()
        out['std_20'] = nb_calculate_std(out, window=std_window)
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

    # 3. Execute Notebook Reference Path
    nb_atr = nb_calculate_atr(df)
    nb_std = nb_calculate_std(df)
    nb_target_df = nb_add_3sigma_target(df)

    # 4. Execute Extracted Brain Path
    brain_atr = calculate_atr(df)
    brain_std = calculate_std(df)
    brain_target_df = add_3sigma_target(df)

    # 5. Shadow Verifications (Byte-for-byte strict equality)
    pd.testing.assert_series_equal(nb_atr, brain_atr, check_exact=True, obj="ATR")
    pd.testing.assert_series_equal(nb_std, brain_std, check_exact=True, obj="STD")
    pd.testing.assert_frame_equal(nb_target_df, brain_target_df, check_exact=True, obj="Target DF")

def test_shadow_model_extraction():
    """
    Verify the pure XGBoost dispatcher executes deterministically on the new target.
    """
    np.random.seed(42)
    # Generate dummy features and binary target
    X = pd.DataFrame(np.random.randn(100, 5), columns=[f'feat_{i}' for i in range(5)])
    y = pd.Series(np.random.randint(0, 2, 100), name='target_3sigma_breakout')
    
    # Run brain model dispatcher
    model, preds = xgboost_dispatcher(X, y)
    
    # Simple assertions to ensure the dispatcher contract hasn't broken
    assert model is not None, "Model failed to train"
    assert len(preds) == 20, "Predictions should match the 20% test size (20/100)"
    assert preds.name == "probability_3sigma_breakout", "Probability name mismatch"
    assert preds.min() >= 0.0 and preds.max() <= 1.0, "Predictions must be strict probabilities"
