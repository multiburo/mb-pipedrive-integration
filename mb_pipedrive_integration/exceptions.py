"""
Custom exceptions for Pipedrive integration
"""
import re
from typing import Optional, Any

# Matches API token values in query strings (api_token=...), headers (x-api-token: ...)
# and dict reprs ('api_token': '...'), keeping the key and replacing only the value
_API_TOKEN_PATTERN = re.compile(
    r"(api[_-]token['\"]?\s*[:=]\s*['\"]?)[^\s'\"&,;)}#]+", re.IGNORECASE
)
# Dict keys whose whole value is the token, e.g. {"x-api-token": "..."}
_API_TOKEN_KEY = re.compile(r"(x-)?api[_-]token", re.IGNORECASE)


def redact_api_token(value: Any) -> Any:
    """Return value with any API token masked; strings, dicts and lists are handled recursively"""
    if isinstance(value, str):
        return _API_TOKEN_PATTERN.sub(r"\1[REDACTED]", value)
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if isinstance(key, str) and _API_TOKEN_KEY.fullmatch(key)
                else redact_api_token(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_api_token(item) for item in value]
    return value


class PipedriveError(Exception):
    """Base exception for Pipedrive-related errors"""

    def __init__(self, *args: Any) -> None:
        # Redacted here so str(), repr() and args never expose an API token
        super().__init__(*(redact_api_token(arg) for arg in args))


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
        self.response_data = redact_api_token(response_data)

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
            base_message += f". Original error: {redact_api_token(str(self.original_error))}"
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
                base_message += f", value: {redact_api_token(str(self.field_value))}"
            base_message += ")"
        return base_message
