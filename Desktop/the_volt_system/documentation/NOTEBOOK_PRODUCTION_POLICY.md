# Notebook Production Policy

Date: 2026-03-28

## Purpose

Define safe boundaries between exploratory notebooks and production execution.

## Policy

1. Production data runs must use Python module entrypoints, not notebook execution.
2. Supported production entrypoints:
- `python -m data_api.jobs.run_once`
- `python -m data_api.jobs.run_production`
- `python -m data_api.jobs.run_production --prepare-kaggle`
3. Notebooks are allowed for research, visualization, and ad-hoc validation only.
4. Notebook outputs are not considered a deployment artifact.
5. Any production logic developed in notebook cells must be migrated into versioned modules under `data_api/` or `src/`.

## Verification

- `tests/test_run_production.py` verifies production entrypoints without notebook dependency.
- CI/runtime checks should execute module entrypoints, not `.ipynb` files.
