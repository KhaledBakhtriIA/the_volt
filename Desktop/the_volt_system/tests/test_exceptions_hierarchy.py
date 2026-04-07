from __future__ import annotations

from data_api.exceptions import DataCollectionError, FileStoreError, VoltBaseError


def test_data_collection_error_carries_context() -> None:
    context = {"symbol": "AAPL", "source": "yahoo"}
    exc = DataCollectionError("failed", context=context)
    assert exc.context == context


def test_file_store_error_is_subclass_of_volt_base_error() -> None:
    exc = FileStoreError("file write failed")
    assert isinstance(exc, VoltBaseError)


def test_data_collection_error_preserves_exception_cause_chain() -> None:
    try:
        raise ConnectionError("network")
    except ConnectionError as err:
        try:
            raise DataCollectionError("collector failed", context={"source": "yahoo"}) from err
        except DataCollectionError as wrapped:
            assert wrapped.__cause__ is err
            assert isinstance(wrapped.__cause__, ConnectionError)
