"""
Custom exceptions for Pipedrive integration
"""
from typing import Optional, Any


class PipedriveError(Exception):
    """Base exception for Pipedrive-related errors"""
    pass


class PipedriveConfigError(PipedriveError):
    """Exception raised when there's a configuration issue"""

    def __init__(self, message: str, missing_fields: Optional[list[str]] = None) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields or []

    def __str__(self) -> str:
        base_message = super().__str__()
        if self.missing_fields:
            return f"{base_message}. Missing: {', '.join(self.missing_fields)}"
        return base_message


class PipedriveAPIError(PipedriveError):
    """Exception raised when Pipedrive API returns an error"""

    def __init__(self, message: str, status_code: Optional[int] = None,
                 response_data: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

    def __str__(self) -> str:
        base_message = super().__str__()
        if self.status_code:
            return f"{base_message} (HTTP {self.status_code})"
        return base_message


class PipedriveNetworkError(PipedriveError):
    """Exception raised when there's a network connectivity issue"""

    def __init__(self, message: str, original_error: Optional[Exception] = None, retry_count: int = 0) -> None:
        super().__init__(message)
        self.original_error = original_error
        self.retry_count = retry_count

    def __str__(self) -> str:
        base_message = super().__str__()
        if self.retry_count > 0:
            base_message += f" (after {self.retry_count} retries)"
        if self.original_error:
            base_message += f". Original error: {self.original_error}"
        return base_message


class PipedriveValidationError(PipedriveError):
    """Exception raised when data validation fails"""

    def __init__(self, message: str, field_name: Optional[str] = None, field_value: Optional[Any] = None) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.field_value = field_value

    def __str__(self) -> str:
        base_message = super().__str__()
        if self.field_name:
            base_message += f" (field: {self.field_name}"
            if self.field_value is not None:
                base_message += f", value: {self.field_value}"
            base_message += ")"
        return base_message
