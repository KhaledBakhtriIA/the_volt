"""Custom exception hierarchy for The Volt System."""


class VoltBaseError(Exception):
    """Base exception for all Volt system errors. Carries message and optional context dict."""

    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message)
        self.context = context or {}


class VoltSystemException(VoltBaseError):
    """Backward-compatible alias for legacy tests/imports."""


class DataCollectionError(VoltSystemException):
    """Raised when a collector fails to fetch data from an external source."""


class FileStoreError(VoltSystemException):
    """Raised when a file read or write operation fails in FileStore."""


class ValidationError(VoltSystemException):
    """Raised when API input fails boundary validation."""


class ProcessingError(VoltSystemException):
    """Raised when sentiment or technical indicator processing fails."""

