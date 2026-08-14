"""
**File:** ``errors.py``
**Region:** ``src/ds_provider_powerofficego_py_lib/errors.py``

This module defines custom exceptions for the PowerOfficeGo data provider library.
These exceptions are used to handle specific error cases that may arise during
the execution of the library's functions.
"""

from typing import Any

from ds_resource_plugin_py_lib.common.resource.dataset.errors import (
    ReadError,
)


class InvalidIncrementalWatermarkException(ReadError):
    """Raised when an incremental watermark value is not valid for the configured strategy."""

    def __init__(
        self,
        message: str,
        code: str = "DS_POWEROFFICEGO_INCREMENTAL_WATERMARK_INVALID",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code, status_code, details)


class UnsupportedIncrementalKindException(ReadError):
    """Raised when incremental metadata uses an unsupported ``kind``."""

    def __init__(
        self,
        message: str,
        code: str = "DS_POWEROFFICEGO_INCREMENTAL_KIND_UNSUPPORTED",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code, status_code, details)
