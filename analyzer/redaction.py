"""
Privacy redaction helpers for values extracted from Copilot Chat logs.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "<email>"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer <token>"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;\]}]+"), r"\1=<redacted>"),
    (re.compile(r"\b(?:ghp|pat|sk)-?[A-Za-z0-9_]{16,}\b"), "<secret>"),
    (re.compile(r"(?i)file:///[A-Za-z]:/[^\s\"'<>|,}]+"), "file:///<local-path>"),
    (re.compile(r"(?i)\b[A-Za-z]:\\Users\\[^\\\s\"'|]+\\[^\r\n\"'|]*"), r"<user-path>"),
    (re.compile(r"(?i)\b[A-Za-z]:\\[^\r\n\"'|]*"), r"<local-path>"),
    (re.compile(r"\\\\[^\s\"'|]+\\[^\r\n\"'|]*"), r"<network-path>"),
    (re.compile(r"(?i)(?:/Users|/home)/[^\s\"'|]+(?:/[^\s\"'|]+)*"), "<user-path>"),
)


def redact_text(value: str) -> str:
    """Redact common personal data, local paths, and secret-like strings."""
    redacted = value
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_value(value: Any) -> Any:
    """Recursively redact strings inside mappings and sequences."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_value(item) for item in value]
    return value
