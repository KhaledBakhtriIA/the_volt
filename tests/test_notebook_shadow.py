import os
import json
import ast
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import pytest

from src.canonical.feature_engineer import FeatureEngineer as CanonicalFeatureEngineer

# Repo-relative path to the archived research notebook (tests/ -> repo root)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK_PATH = os.path.join(_REPO_ROOT, "research", "notebooks", "AutoData_Analyst_v1_aymen.ipynb")

def extract_notebook_feature_engineer():
    nb_path = NOTEBOOK_PATH
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    cells = [c for c in nb.get('cells', []) if c.get('cell_type') == 'code']
    for cell in cells:
        source = "".join(cell.get('source', []))
        if 'class FeatureEngineer' in source:
            # We found the cell. Execute it in a local dictionary
            env = {
                'np': np,
                'pd': pd,
                'StandardScaler': StandardScaler,
                'HAS_TALIB': False,
                'talib': None
            }
            try:
                exec(source, env)
                if 'FeatureEngineer' in env:
                    return env['FeatureEngineer']
            except Exception as e:
                pass
    raise RuntimeError("FeatureEngineer not found in notebook")


def test_feature_engineer_shadow():
    """
    Shadow test comparing notebook logic vs rewritten .py file logic.
    If the results aren't 100% identical, the extraction failed.
    """
    NotebookFE = extract_notebook_feature_engineer()
    
    nb_fe = NotebookFE()
    py_fe = CanonicalFeatureEngineer()
    
    # Generate some standard dummy data to exercise all branches
    np.random.seed(42)
    N = 100
    prices = np.random.lognormal(0.001, 0.02, N).cumprod() * 100
    high = prices * np.random.uniform(1.0, 1.05, N)
    low = prices * np.random.uniform(0.95, 1.0, N)
    close = prices
    volumes = np.random.lognormal(10, 1, N)
    
    # Run notebook logic
    notebook_features = nb_fe.calculate_all_features(prices, volumes, high, low, close)
    
    # Run canonical logic
    canonical_features = py_fe.calculate_all_features(prices, volumes, high, low, close)
    
    # Assert features are identical
    np.testing.assert_allclose(
        notebook_features, 
        canonical_features, 
        rtol=1e-5, 
        atol=1e-5,
        err_msg="Extraction failed: FeatureEngineer results are not 100% identical between Notebook and .py"
    )
    
    # Assert feature names match exactly
    assert nb_fe.feature_names == py_fe.feature_names, "Extraction failed: Feature names do not match"
