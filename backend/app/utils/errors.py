"""One error type for all business-rule failures; main.py turns it into a JSON response."""
from typing import Any


class AppError(Exception):
    def __init__(self, status_code: int, message: str, extra: dict[str, Any] | None = None):
        self.status_code = status_code
        self.message = message
        self.extra = extra or {}
        super().__init__(message)
