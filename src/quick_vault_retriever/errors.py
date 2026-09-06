"""Shared controlled failures for command and benchmark execution."""


class RetrievalError(Exception):
    """A controlled retrieval failure with a public result state."""

    def __init__(self, status: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.status = status
        self.exit_code = exit_code
