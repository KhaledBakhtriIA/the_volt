"""Tests for notebook-free production job entrypoints."""

from unittest.mock import patch

from orchestration.jobs import run_production


def test_run_production_runs_collection_only(monkeypatch):
    """run_production should run collection by default."""
    monkeypatch.setattr("sys.argv", ["run_production"])

    with patch("orchestration.jobs.run_production.run_once_main") as mock_run_once:
        with patch("orchestration.jobs.run_production.prepare_kaggle_main") as mock_kaggle:
            run_production.main()
            mock_run_once.assert_called_once()
            mock_kaggle.assert_not_called()


def test_run_production_runs_collection_and_kaggle(monkeypatch):
    """run_production should run optional Kaggle export when requested."""
    monkeypatch.setattr("sys.argv", ["run_production", "--prepare-kaggle"])

    with patch("orchestration.jobs.run_production.run_once_main") as mock_run_once:
        with patch("orchestration.jobs.run_production.prepare_kaggle_main") as mock_kaggle:
            run_production.main()
            mock_run_once.assert_called_once()
            mock_kaggle.assert_called_once()
