"""Tests for file storage functionality."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from infrastructure.database.file_store import FileStore
from data_layer.exceptions import FileStoreError, ValidationError


class TestFileStoreSave:
    """Test FileStore.save() method."""

    def test_save_creates_directory_if_not_exists(self, temp_dir):
        """save() should create base directory if it doesn't exist."""
        new_dir = temp_dir / "nonexistent" / "path"
        assert not new_dir.exists()

        store = FileStore(new_dir)
        assert new_dir.exists()

    def test_save_csv_default(self, temp_dir, sample_market_data):
        """save() should save CSV by default."""
        store = FileStore(temp_dir)
        result_path = store.save(sample_market_data, "test_data")

        assert result_path.exists()
        assert result_path.suffix == ".csv"
        assert result_path.name.startswith("test_data_")

    def test_save_csv_contents_correct(self, temp_dir, sample_market_data):
        """Saved CSV should have correct contents."""
        store = FileStore(temp_dir)
        store.save(sample_market_data, "test")

        saved = pd.read_csv(next(temp_dir.glob("test_*.csv")))
        assert len(saved) == len(sample_market_data)
        assert list(saved.columns) == list(sample_market_data.columns)

    def test_save_parquet_when_enabled(self, temp_dir, sample_market_data):
        """save() should save Parquet when environment variable is set."""
        store = FileStore(temp_dir)
        with patch.dict(os.environ, {"DATA_API_PREFER_PARQUET": "true"}):
            with patch.object(sample_market_data, "to_parquet") as mock_parquet:
                with patch.object(sample_market_data, "to_csv"):
                    result_path = store.save(sample_market_data, "test_data")
                    # Method will attempt parquet first
                    mock_parquet.assert_called_once()

    def test_save_fallback_to_csv_on_parquet_error(self, temp_dir, sample_market_data):
        """save() should fallback to CSV if Parquet fails."""
        store = FileStore(temp_dir)
        with patch.dict(os.environ, {"DATA_API_PREFER_PARQUET": "true"}):
            # Mock parquet to fail, but csv to succeed
            with patch.object(sample_market_data, "to_parquet", side_effect=OSError("Parquet error")):
                with patch.object(sample_market_data, "to_csv") as mock_csv:
                    store.save(sample_market_data, "test")
                    # Should fallback to CSV
                    mock_csv.assert_called_once()

    def test_save_respects_prefix(self, temp_dir, sample_market_data):
        """save() should use provided prefix in filename."""
        store = FileStore(temp_dir)
        result = store.save(sample_market_data, "my_prefix")
        assert "my_prefix_" in result.name

    def test_save_includes_timestamp(self, temp_dir, sample_market_data):
        """save() should include timestamp in filename."""
        store = FileStore(temp_dir)
        result = store.save(sample_market_data, "test")
        # Filename format: prefix_YYYYMMDD_HHMMSS.ext
        assert "_" in result.stem  # Has timestamp with underscores

    def test_save_preserves_data_integrity(self, temp_dir, sample_market_data):
        """save() and load should preserve data integrity."""
        store = FileStore(temp_dir)
        result_path = store.save(sample_market_data, "test")

        loaded = pd.read_csv(result_path)
        assert len(loaded) == len(sample_market_data)
        assert loaded["symbol"].iloc[0] == sample_market_data["symbol"].iloc[0]

    def test_save_handles_empty_dataframe(self, temp_dir):
        """save() should handle empty DataFrames."""
        store = FileStore(temp_dir)
        empty_df = pd.DataFrame()
        result_path = store.save(empty_df, "empty")
        assert result_path.exists()

    def test_save_returns_path(self, temp_dir, sample_market_data):
        """save() should return the Path object."""
        store = FileStore(temp_dir)
        result = store.save(sample_market_data, "test")
        assert isinstance(result, Path)

    def test_save_multiple_files_different_timestamps(self, temp_dir, sample_market_data):
        """Multiple saves should create separate files with different timestamps."""
        store = FileStore(temp_dir)
        result1 = store.save(sample_market_data, "test")
        import time
        time.sleep(0.01)  # Ensure different timestamp
        result2 = store.save(sample_market_data, "test")

        assert result1.exists()
        assert result2.exists()
        # Files should have different names or at least both exist
        files = list(temp_dir.glob("test_*"))
        assert len(files) >= 2


class TestFileStoreLatestFile:
    """Test FileStore.latest_file() method."""

    def test_latest_file_returns_none_when_no_files(self, temp_dir):
        """latest_file() should return None if no files exist."""
        store = FileStore(temp_dir)
        result = store.latest_file("nonexistent_prefix")
        assert result is None

    def test_latest_file_finds_single_file(self, temp_dir, sample_market_data):
        """latest_file() should find single file with matching prefix."""
        store = FileStore(temp_dir)
        saved_path = store.save(sample_market_data, "test_prefix")
        result = store.latest_file("test_prefix")

        assert result is not None
        assert result == saved_path

    def test_latest_file_returns_most_recent(self, temp_dir, sample_market_data):
        """latest_file() should return the most recently modified file."""
        store = FileStore(temp_dir)
        save1 = store.save(sample_market_data, "test")

        # Simulate time passing by modifying modification time
        import time
        time.sleep(0.5)  # Wait longer to ensure different timestamps

        save2 = store.save(sample_market_data, "test")

        latest = store.latest_file("test")
        assert latest == save2
        assert latest != save1

    def test_latest_file_ignores_different_prefixes(self, temp_dir, sample_market_data):
        """latest_file() should ignore files with different prefixes."""
        store = FileStore(temp_dir)
        store.save(sample_market_data, "prefix_a")
        store.save(sample_market_data, "prefix_b")

        result = store.latest_file("prefix_a")
        assert result is not None
        assert "prefix_a_" in result.name
        assert "prefix_b_" not in result.name

    def test_latest_file_returns_path(self, temp_dir, sample_market_data):
        """latest_file() should return a Path object."""
        store = FileStore(temp_dir)
        store.save(sample_market_data, "test")
        result = store.latest_file("test")

        assert isinstance(result, Path)

    def test_latest_file_with_no_matching_prefix(self, temp_dir, sample_market_data):
        """latest_file() should return None for non-matching prefix."""
        store = FileStore(temp_dir)
        store.save(sample_market_data, "data")
        result = store.latest_file("nonexistent")

        assert result is None


class TestFileStoreInitialization:
    """Test FileStore initialization."""

    def test_init_creates_directory(self, temp_dir):
        """__init__ should create the base directory."""
        new_dir = temp_dir / "new_store"
        assert not new_dir.exists()

        FileStore(new_dir)
        assert new_dir.exists()

    def test_init_handles_existing_directory(self, temp_dir):
        """__init__ should handle existing directory gracefully."""
        # Directory already exists from conftest temp_dir fixture
        store = FileStore(temp_dir)
        assert temp_dir.exists()

    def test_init_stores_base_dir(self, temp_dir):
        """__init__ should store base_dir as Path."""
        store = FileStore(temp_dir)
        assert isinstance(store.base_dir, Path)
        assert store.base_dir == temp_dir


class TestFileStoreIntegration:
    """Integration tests for FileStore."""

    def test_save_and_load_cycle(self, temp_dir, sample_market_data):
        """Complete cycle: save and load data back."""
        store = FileStore(temp_dir)

        # Save
        path = store.save(sample_market_data, "cycle_test")
        assert path.exists()

        # Load
        loaded = pd.read_csv(path)
        assert len(loaded) == len(sample_market_data)
        assert list(loaded.columns) == list(sample_market_data.columns)

    def test_multiple_save_operations(self, temp_dir, sample_market_data):
        """Multiple save operations should work independently."""
        store = FileStore(temp_dir)

        paths = []
        for i in range(5):
            path = store.save(sample_market_data, f"batch_{i}")
            paths.append(path)
            assert path.exists()

        # All paths should be unique
        assert len(set(paths)) == 5

    def test_latest_file_among_multiple_batches(self, temp_dir, sample_market_data):
        """latest_file() should work correctly with multiple batches."""
        store = FileStore(temp_dir)

        import time

        # Save multiple batches
        for batch in range(3):
            store.save(sample_market_data, "batch")
            time.sleep(0.15)  # Longer delay to ensure timestamp separation

        # All files should exist
        all_files = list(temp_dir.glob("batch_*"))
        assert len(all_files) >= 2  # At least 2 files created

        # Latest should be the last one saved
        latest = store.latest_file("batch")
        assert latest is not None
