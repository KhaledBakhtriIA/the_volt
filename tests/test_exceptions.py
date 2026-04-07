"""Tests for custom exception classes."""

import pytest

from data_api.exceptions import (
    DataCollectionError,
    FileStoreError,
    ProcessingError,
    ValidationError,
    VoltSystemException,
)


class TestExceptionHierarchy:
    """Test that exception hierarchy is correct."""

    def test_data_collection_error_is_volt_exception(self):
        """DataCollectionError should inherit from VoltSystemException."""
        exc = DataCollectionError("Test error")
        assert isinstance(exc, VoltSystemException)
        assert isinstance(exc, Exception)

    def test_file_store_error_is_volt_exception(self):
        """FileStoreError should inherit from VoltSystemException."""
        exc = FileStoreError("Test error")
        assert isinstance(exc, VoltSystemException)

    def test_validation_error_is_volt_exception(self):
        """ValidationError should inherit from VoltSystemException."""
        exc = ValidationError("Test error")
        assert isinstance(exc, VoltSystemException)

    def test_processing_error_is_volt_exception(self):
        """ProcessingError should inherit from VoltSystemException."""
        exc = ProcessingError("Test error")
        assert isinstance(exc, VoltSystemException)


class TestExceptionMessages:
    """Test that exceptions preserve messages correctly."""

    def test_data_collection_error_message(self):
        """DataCollectionError should preserve error message."""
        msg = "Failed to fetch data from Yahoo Finance"
        exc = DataCollectionError(msg)
        assert str(exc) == msg

    def test_file_store_error_message(self):
        """FileStoreError should preserve error message."""
        msg = "Failed to write CSV file: Permission denied"
        exc = FileStoreError(msg)
        assert str(exc) == msg

    def test_validation_error_message(self):
        """ValidationError should preserve error message."""
        msg = "Invalid symbols list: must be non-empty"
        exc = ValidationError(msg)
        assert str(exc) == msg

    def test_processing_error_message(self):
        """ProcessingError should preserve error message."""
        msg = "Failed to calculate technical indicators"
        exc = ProcessingError(msg)
        assert str(exc) == msg


class TestExceptionRaising:
    """Test that exceptions can be raised and caught correctly."""

    def test_catch_specific_data_collection_error(self):
        """Should be able to catch DataCollectionError specifically."""
        with pytest.raises(DataCollectionError):
            raise DataCollectionError("Network timeout")

    def test_catch_specific_file_store_error(self):
        """Should be able to catch FileStoreError specifically."""
        with pytest.raises(FileStoreError):
            raise FileStoreError("Disk full")

    def test_catch_specific_validation_error(self):
        """Should be able to catch ValidationError specifically."""
        with pytest.raises(ValidationError):
            raise ValidationError("Empty input")

    def test_catch_specific_processing_error(self):
        """Should be able to catch ProcessingError specifically."""
        with pytest.raises(ProcessingError):
            raise ProcessingError("Analysis failed")

    def test_catch_all_volt_exceptions(self):
        """Should be able to catch all as VoltSystemException."""
        for exc_class in [
            DataCollectionError,
            FileStoreError,
            ValidationError,
            ProcessingError,
        ]:
            with pytest.raises(VoltSystemException):
                raise exc_class("Test error")

    def test_catch_with_parent_exception(self):
        """Child exception can be caught by parent."""
        with pytest.raises(VoltSystemException) as exc_info:
            raise DataCollectionError("Network error")

        assert isinstance(exc_info.value, DataCollectionError)
