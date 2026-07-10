"""
XGBoost + Optuna Training Pipeline
====================================
Extracted from notebook Phase 4 / Phase 5 (cells 335 & 339).
Provides a self-contained, reusable training pipeline:

1. ``load_data``              — CSV or synthetic patterned data
2. ``clean_realtime_df``      — strips, deduplicates, numeric-ifies scraped data
3. ``preprocess_for_model``   — impute + scale → numpy arrays (fit/transform safe)
4. ``train_xgb_with_optuna``  — XGBoost + Optuna (budget-aware, imbalance-aware)
5. ``get_oof_preds_and_stack``— 5-fold OOF stacking into a meta-XGBoost
6. ``evaluate_and_plot``      — threshold-optimised metrics + ROC/PR plots
7. ``XGBOptunaBundle``        — thin class wrapping steps 1-6 together

All Colab-specific magic (``%pip``, ``from google.colab ...``) has been removed.
Plots are optional (matplotlib); joblib serialisation is optional too.
"""

import gc
import os
import warnings
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    xgb = None  # type: ignore[assignment]
    HAS_XGB = False

try:
    import optuna
    from optuna.samplers import TPESampler
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    optuna = None  # type: ignore[assignment]
    HAS_OPTUNA = False

try:
    import matplotlib.pyplot as plt
    import matplotlib  # noqa: F401
    HAS_MPL = True
except ImportError:
    plt = None  # type: ignore[assignment]
    HAS_MPL = False

try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    joblib = None  # type: ignore[assignment]
    HAS_JOBLIB = False

# ============================================================================
# CONFIG DEFAULTS
# ============================================================================
RANDOM_SEED = 42
N_JOBS = 2
DEFAULT_NUM_ROUND = 2_000
EARLY_STOPPING_ROUNDS = 50
TARGET_COL = "target"


# ============================================================================
# 1. DATA LOADING
# ============================================================================

def _create_synthetic_patterns(X: np.ndarray) -> np.ndarray:
    p1 = (X[:, 0] > 0.4) & (X[:, 1] < -0.3) & (X[:, 2] > 0.2) & (np.sin(X[:, 3] * 2) > 0.6)
    p2 = (X[:, 4] * X[:, 5] > 0.15) | (X[:, 6] ** 2 + X[:, 7] ** 2 > 1.8) | (np.exp(X[:, 8]) > 2.8)
    p3 = (X[:, 9] + X[:, 10] + X[:, 11] > 1.2) & (X[:, 12] < X[:, 13] - 0.4) & (X[:, 14] > 0.7)
    p4 = (np.sin(X[:, 15] * 3) * np.cos(X[:, 16] * 2) > 0.4) | (X[:, 17] > X[:, 18] + 0.6)
    p5 = (X[:, 22] > 0.8) & (X[:, 23] < -0.5) & (X[:, 24] > 0.3)
    p6 = np.sqrt(X[:, 27] ** 2 + X[:, 28] ** 2) > 1.5
    return (p1 | p2 | p3 | p4 | p5 | p6).astype(int)


def generate_synthetic(
    n_samples: int = 15_000, n_features: int = 30, noise: float = 0.01, seed: int = RANDOM_SEED
) -> tuple[pd.DataFrame, pd.Series]:
    np.random.seed(seed)
    X = np.random.randn(n_samples, n_features)
    y = _create_synthetic_patterns(X)
    mask = np.random.random(n_samples) < noise
    y[mask] = 1 - y[mask]
    return (
        pd.DataFrame(X, columns=[f"f{i}" for i in range(n_features)]),
        pd.Series(y, name=TARGET_COL),
    )


def load_data(
    csv_path: Optional[str] = None,
    target_col: str = TARGET_COL,
    sample_rows: Optional[int] = None,
) -> pd.DataFrame:
    """Load data from a CSV file or generate synthetic patterned data."""
    if csv_path is None:
        print("No CSV provided — using synthetic dataset (patterned).")
        X_df, y = generate_synthetic(n_samples=15_000)
        df = X_df.copy()
        df[target_col] = y
    else:
        print(f"Loading CSV: {csv_path}")
        df = pd.read_csv(csv_path, nrows=sample_rows)
        if target_col not in df.columns:
            raise ValueError(
                f"Target column '{target_col}' not in CSV columns: {df.columns.tolist()[:50]}"
            )
    return df


# ============================================================================
# 2. CLEANING (real-time / scraped data)
# ============================================================================

def clean_realtime_df(
    df: pd.DataFrame,
    text_cols: list[str] | None = None,
    date_cols: list[str] | None = None,
    drop_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Clean common issues in web-scraped / real-time data."""
    df = df.copy()
    df = df.drop_duplicates().reset_index(drop=True)

    if drop_cols:
        df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    if text_cols:
        for c in text_cols:
            if c in df.columns:
                df[c] = df[c].astype(str).str.strip().str.lower().replace({"nan": None})

    if date_cols:
        for c in date_cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
                df[c + "_hour"] = df[c].dt.hour.fillna(-1).astype(int)
                df[c + "_dow"] = df[c].dt.dayofweek.fillna(-1).astype(int)

    for c in df.columns:
        if df[c].dtype == object:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="ignore"
            )

    nunique = df.nunique(dropna=False)
    df.drop(columns=nunique[nunique <= 1].index.tolist(), inplace=True)
    return df


# ============================================================================
# 3. PREPROCESSING (impute + scale)
# ============================================================================

def frequency_encode(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            vc = df[c].value_counts(dropna=False).to_dict()
            df[c + "_freq"] = df[c].map(vc).astype(float).fillna(0)
            df.drop(columns=[c], inplace=True)
    return df


def preprocess_for_model(
    df: pd.DataFrame,
    target_col: str = TARGET_COL,
    fit_objects: dict | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Impute + scale to float32 numpy arrays.

    Parameters
    ----------
    df : DataFrame with target column present
    target_col : name of the binary target column
    fit_objects : if provided, *transform* using pre-fitted objects (for val/test)

    Returns
    -------
    (X, y, fit_objects)
    """
    df = df.copy()
    if target_col not in df.columns:
        raise ValueError(f"target column '{target_col}' not present")
    y = df[target_col].astype(int).values
    X_df = df.drop(columns=[target_col])

    obj_cols = [c for c in X_df.columns if X_df[c].dtype == object]
    if obj_cols:
        X_df = frequency_encode(X_df, obj_cols)

    num_cols = X_df.select_dtypes(include=[np.number]).columns.tolist()

    if fit_objects is None:
        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        X_num = imputer.fit_transform(X_df[num_cols])
        X_num = scaler.fit_transform(X_num)
        fit_objects = {"imputer": imputer, "scaler": scaler, "num_cols": num_cols}
    else:
        imputer = fit_objects["imputer"]
        scaler = fit_objects["scaler"]
        num_cols = fit_objects["num_cols"]
        X_num = imputer.transform(X_df[num_cols])
        X_num = scaler.transform(X_num)

    return np.ascontiguousarray(X_num.astype(np.float32)), y, fit_objects


# ============================================================================
# 4. TRAINING: XGBoost + Optuna
# ============================================================================

def _get_tree_method() -> str:
    try:
        if "COLAB_GPU" in os.environ or (
            "CUDA_VISIBLE_DEVICES" in os.environ
            and os.environ["CUDA_VISIBLE_DEVICES"] != ""
        ):
            return "gpu_hist"
    except Exception:
        pass
    return "hist"


def train_xgb_with_optuna(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray | None = None,
    y_val: np.ndarray | None = None,
    n_trials: int = 12,
    num_round: int = DEFAULT_NUM_ROUND,
    early_stopping: int = EARLY_STOPPING_ROUNDS,
    seed: int = RANDOM_SEED,
) -> tuple:
    """Train XGBoost with Optuna hyperparameter search.

    Returns
    -------
    (booster, best_params, study)

    Raises ``ImportError`` if xgboost or optuna are not installed.
    """
    if not HAS_XGB:
        raise ImportError("xgboost is required: pip install xgboost")
    if not HAS_OPTUNA:
        raise ImportError("optuna is required: pip install optuna")

    pos = int(y_train.sum())
    neg = len(y_train) - pos
    scale_pos_weight = max(1.0, neg / max(1.0, pos))
    tree_method = _get_tree_method()

    base_params = {
        "objective": "binary:logistic",
        "eval_metric": ["auc", "aucpr"],
        "tree_method": tree_method,
        "verbosity": 0,
        "nthread": N_JOBS,
        "scale_pos_weight": scale_pos_weight,
    }
    dtrain = xgb.DMatrix(X_train, label=y_train)

    def objective(trial: "optuna.Trial") -> float:
        params = base_params.copy()
        params.update(
            {
                "max_depth": trial.suggest_int("max_depth", 3, 9),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "lambda": trial.suggest_float("lambda", 1e-2, 10.0),
                "alpha": trial.suggest_float("alpha", 1e-2, 10.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 30),
            }
        )
        cv = xgb.cv(
            params,
            dtrain,
            num_boost_round=500,
            nfold=3,
            metrics=("aucpr",),
            early_stopping_rounds=30,
            seed=seed,
            verbose_eval=False,
            as_pandas=True,
        )
        return float(cv["test-aucpr-mean"].max())

    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    print("Optuna best params:", study.best_params)

    best_params = base_params.copy()
    best_params.update(study.best_params)

    evals = [(dtrain, "train")]
    dval = None
    if X_val is not None and y_val is not None:
        dval = xgb.DMatrix(X_val, label=y_val)
        evals.append((dval, "valid"))

    booster = xgb.train(
        params=best_params,
        dtrain=dtrain,
        num_boost_round=num_round,
        evals=evals,
        early_stopping_rounds=early_stopping,
        verbose_eval=25,
    )
    return booster, best_params, study


# ============================================================================
# 5. OOF STACKING
# ============================================================================

def get_oof_preds_and_stack(
    X: np.ndarray,
    y: np.ndarray,
    params: dict,
    n_splits: int = 5,
    rounds: int | None = None,
) -> tuple:
    """5-fold OOF predictions + a simple XGBoost meta-model.

    Returns
    -------
    (oof_preds, stack_booster)
    """
    if not HAS_XGB:
        raise ImportError("xgboost is required")

    kf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_SEED)
    oof_preds = np.zeros(X.shape[0])

    for _, (tr_idx, te_idx) in enumerate(kf.split(X, y)):
        dtr = xgb.DMatrix(X[tr_idx], label=y[tr_idx])
        dte = xgb.DMatrix(X[te_idx], label=y[te_idx])
        model = xgb.train(params, dtr, num_boost_round=rounds or 200, verbose_eval=False)
        oof_preds[te_idx] = model.predict(dte)

    stack_X = oof_preds.reshape(-1, 1)
    dstack = xgb.DMatrix(stack_X, label=y)
    stack_params = {
        "objective": "binary:logistic",
        "tree_method": "hist",
        "learning_rate": 0.05,
        "max_depth": 3,
        "nthread": N_JOBS,
    }
    stack_bst = xgb.train(stack_params, dstack, num_boost_round=100, verbose_eval=False)
    return oof_preds, stack_bst


# ============================================================================
# 6. EVALUATION
# ============================================================================

def evaluate_and_plot(
    booster,
    X_test: np.ndarray,
    y_test: np.ndarray,
    stack_booster=None,
    threshold_search: bool = True,
    plot: bool = True,
) -> dict:
    """Compute threshold-optimised metrics and optionally plot ROC/PR curves."""
    if not HAS_XGB:
        raise ImportError("xgboost is required")

    dtest = xgb.DMatrix(X_test)
    base_pred = booster.predict(dtest)

    if stack_booster is not None:
        meta_pred = stack_booster.predict(xgb.DMatrix(base_pred.reshape(-1, 1)))
        blend = 0.75 * base_pred + 0.25 * meta_pred
    else:
        blend = base_pred

    best_thresh, best_f1 = 0.5, -1.0
    if threshold_search:
        for thr in np.linspace(0.01, 0.99, 99):
            yhat = (blend >= thr).astype(int)
            f1 = f1_score(y_test, yhat, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = float(thr)

    yhat = (blend >= best_thresh).astype(int)
    metrics = {
        "threshold": best_thresh,
        "accuracy": float(accuracy_score(y_test, yhat)),
        "precision": float(precision_score(y_test, yhat, zero_division=0)),
        "recall": float(recall_score(y_test, yhat, zero_division=0)),
        "f1": float(f1_score(y_test, yhat, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, blend)),
        "pr_auc": float(average_precision_score(y_test, blend)),
    }

    print("\n=== EVALUATION SUMMARY ===")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    if plot and HAS_MPL:
        try:
            from sklearn.metrics import PrecisionRecallDisplay, RocCurveDisplay

            _fig, axes = plt.subplots(1, 2, figsize=(10, 4))
            RocCurveDisplay.from_predictions(y_test, blend, name="Model", ax=axes[0])
            axes[0].set_title("ROC curve")
            PrecisionRecallDisplay.from_predictions(y_test, blend, name="Model", ax=axes[1])
            axes[1].set_title("PR curve")
            plt.tight_layout()
            plt.show()
        except Exception as exc:
            print(f"[warn] plotting skipped: {exc}")

    return metrics


# ============================================================================
# 7. CONVENIENCE BUNDLE
# ============================================================================

class XGBOptunaBundle:
    """High-level wrapper: load → clean → preprocess → train → stack → evaluate.

    Usage
    -----
    >>> bundle = XGBOptunaBundle()
    >>> metrics = bundle.run(csv_path="data.csv", target_col="label")
    >>> bundle.save("my_model.joblib")  # requires joblib
    """

    def __init__(
        self,
        n_trials: int = 12,
        test_size: float = 0.15,
        seed: int = RANDOM_SEED,
    ):
        self.n_trials = n_trials
        self.test_size = test_size
        self.seed = seed

        self.booster = None
        self.stack_booster = None
        self.fit_objs: dict | None = None
        self.best_params: dict | None = None
        self.study = None
        self.metrics: dict = {}

    def run(
        self,
        csv_path: str | None = None,
        target_col: str = TARGET_COL,
        text_cols: list[str] | None = None,
        date_cols: list[str] | None = None,
        drop_cols: list[str] | None = None,
    ) -> dict:
        """End-to-end pipeline.  Returns the evaluation metric dict."""
        df = load_data(csv_path=csv_path, target_col=target_col)
        df = clean_realtime_df(df, text_cols=text_cols, date_cols=date_cols, drop_cols=drop_cols)

        train_df, val_df = train_test_split(
            df, test_size=self.test_size, stratify=df[target_col], random_state=self.seed
        )
        X_tr, y_tr, self.fit_objs = preprocess_for_model(train_df, target_col=target_col)
        X_val, y_val, _ = preprocess_for_model(val_df, target_col=target_col, fit_objects=self.fit_objs)
        del df, train_df, val_df
        gc.collect()

        self.booster, self.best_params, self.study = train_xgb_with_optuna(
            X_tr, y_tr, X_val, y_val, n_trials=self.n_trials, seed=self.seed
        )

        _, self.stack_booster = get_oof_preds_and_stack(
            X_tr, y_tr, self.best_params, n_splits=5,
            rounds=self.booster.best_iteration + 10,
        )

        self.metrics = evaluate_and_plot(self.booster, X_val, y_val, self.stack_booster)
        return self.metrics

    def save(self, path: str) -> None:
        """Serialise bundle to disk (requires joblib)."""
        if not HAS_JOBLIB:
            raise ImportError("joblib is required: pip install joblib")
        payload = {
            "booster": self.booster,
            "stack_booster": self.stack_booster,
            "fit_objs": self.fit_objs,
            "best_params": self.best_params,
            "metrics": self.metrics,
        }
        joblib.dump(payload, path)
        print(f"Saved bundle to {path}")

    @classmethod
    def load(cls, path: str) -> "XGBOptunaBundle":
        """Load a previously saved bundle."""
        if not HAS_JOBLIB:
            raise ImportError("joblib is required")
        payload = joblib.load(path)
        inst = cls.__new__(cls)
        inst.__dict__.update(payload)
        return inst
