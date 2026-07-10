import xgboost as xgb
import pandas as pd
from typing import Dict, Any, Tuple

def train_xgboost_classifier(
    X_train: pd.DataFrame, 
    y_train: pd.Series, 
    params: Dict[str, Any] = None
) -> xgb.Booster:
    """
    Train a pure XGBoost classifier on the given training data.
    """
    if params is None:
        params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "learning_rate": 0.05,
            "max_depth": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42
        }
        
    dtrain = xgb.DMatrix(X_train, label=y_train)
    model = xgb.train(params, dtrain, num_boost_round=100)
    
    return model

def predict_xgboost_classifier(
    model: xgb.Booster, 
    X_test: pd.DataFrame
) -> pd.Series:
    """
    Generate probability predictions using the trained XGBoost model.
    """
    dtest = xgb.DMatrix(X_test)
    preds = model.predict(dtest)
    
    return pd.Series(preds, index=X_test.index, name="probability_3sigma_breakout")

def xgboost_dispatcher(
    X: pd.DataFrame, 
    y: pd.Series, 
    train_size: float = 0.8,
    params: Dict[str, Any] = None
) -> Tuple[xgb.Booster, pd.Series]:
    """
    Pure dispatcher that splits data, trains the model, and evaluates it on the test set.
    """
    split_idx = int(len(X) * train_size)
    
    X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    
    model = train_xgboost_classifier(X_train, y_train, params)
    predictions = predict_xgboost_classifier(model, X_test)
    
    return model, predictions
