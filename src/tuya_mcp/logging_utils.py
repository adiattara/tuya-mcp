"""Logging setup that guarantees secrets never reach the output."""

from __future__ import annotations

import logging
import sys

REDACTED = "***"


class SecretRedactor(logging.Filter):
    """Replace every registered secret in log records, whatever the level."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: set[str] = set()

    def add(self, secret: str) -> None:
        if secret:
            self._secrets.add(secret)

    def redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            record.msg = self.redact(record.getMessage())
            record.args = None
        return True


redactor = SecretRedactor()


def configure_logging(level: str) -> None:
    """Log to stderr (stdout carries the MCP stdio protocol)."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(redactor)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
