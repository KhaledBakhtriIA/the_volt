"""Canonical production-grade control-plane components for Volt."""

# --- Original control-plane modules ---
from .orchestrator import AnalysisOrchestrator
from .realtime_extractor import RealTimeDataExtractor
from .supervisor import PipelineSupervisor
from .meta_controller import MetaControllerV2
from .feature_store_engine import FeatureStoreEngine, FeatureStoreConfig, QualityReport, DataQualityError

# --- Extracted from notebook Phase 8 ---
from .feature_engineer import FeatureEngineer
from .predictive_models import (
    PredictiveModel,
    MomentumModel,
    MeanReversionModel,
    VolatilityModel,
    SentimentModel,
    MacroModel,
    RiskModel,
    ExecutionModel,
    MODEL_REGISTRY,
)
from .meta_controller_v1 import MetaController
from .xgb_optuna_pipeline import (
    XGBOptunaBundle,
    load_data,
    clean_realtime_df,
    preprocess_for_model,
    train_xgb_with_optuna,
    get_oof_preds_and_stack,
    evaluate_and_plot,
)

# --- Extracted from notebook Phase 1 ---
from .phase1_analytics import (
    create_sample_sales_data,
    clean_data,
    calculate_key_metrics,
    create_visualizations,
    ai_insights,
    advanced_sales_forecast,
    ai_customer_segmentation,
    ml_anomaly_detection,
    generate_report,
    export_for_powerbi,
)

__all__ = [
    # Control-plane
    "AnalysisOrchestrator",
    "RealTimeDataExtractor",
    "PipelineSupervisor",
    "MetaControllerV2",
    "FeatureStoreEngine",
    "FeatureStoreConfig",
    "QualityReport",
    "DataQualityError",
    # Feature engineering
    "FeatureEngineer",
    # Predictive models
    "PredictiveModel",
    "MomentumModel",
    "MeanReversionModel",
    "VolatilityModel",
    "SentimentModel",
    "MacroModel",
    "RiskModel",
    "ExecutionModel",
    "MODEL_REGISTRY",
    # Meta-controllers
    "MetaController",
    # Training pipeline
    "XGBOptunaBundle",
    "load_data",
    "clean_realtime_df",
    "preprocess_for_model",
    "train_xgb_with_optuna",
    "get_oof_preds_and_stack",
    "evaluate_and_plot",
    # Phase 1 analytics
    "create_sample_sales_data",
    "clean_data",
    "calculate_key_metrics",
    "create_visualizations",
    "ai_insights",
    "advanced_sales_forecast",
    "ai_customer_segmentation",
    "ml_anomaly_detection",
    "generate_report",
    "export_for_powerbi",
]
from .learning_loop import NeuroplasticityLoop

__all__.append('NeuroplasticityLoop')
