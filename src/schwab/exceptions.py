from __future__ import annotations


class SchwabError(Exception):
    pass


class SchwabAuthError(SchwabError):
    pass


class SchwabAPIError(SchwabError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
