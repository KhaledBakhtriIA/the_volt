from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data_layer.exceptions import FileStoreError
from infrastructure.database.file_store import FileStore


def test_save_none_raises_file_store_error_when_reject_empty_enabled(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(FileStoreError):
        store.save(None, "dataset", reject_empty=True)


def test_save_empty_dataframe_raises_file_store_error_when_reject_empty_enabled(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    empty_df = pd.DataFrame()
    with pytest.raises(FileStoreError):
        store.save(empty_df, "dataset", reject_empty=True)


def test_save_valid_dataframe_writes_file_and_returns_path(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = store.save(df, "dataset")
    assert isinstance(out, Path)
    assert out.exists()
