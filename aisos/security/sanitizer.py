"""Input prompt-injection heuristics + output secret redaction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("aisos.security.sanitizer")

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (?:all )?previous (?:instructions|messages|prompts)",
        r"disregard (?:all )?(?:previous|prior) (?:instructions|messages)",
        r"^\s*system\s*:",
        r"###\s*system\b",
        r"<\s*\|?im_start\|?\s*>",
        r"act as (?:dan|admin|root)",
    )
)

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[REDACTED:OPENAI_KEY]"),
    (re.compile(r"\bAZURE[_A-Z0-9]*=[^\s]+", re.IGNORECASE), "[REDACTED:AZURE_VAR]"),
    (
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
        "[REDACTED:GUID]",
    ),
    (
        re.compile(r"\b[A-Za-z0-9]{32,}\b"),
        "[REDACTED:LONG_TOKEN]",
    ),
)


@dataclass
class ScreenResult:
    text: str
    suspicious: bool
    matched: list[str]


def screen_input(text: str) -> ScreenResult:
    """Detect prompt-injection patterns. Returns the original text and a flag."""
    matched = [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]
    if matched:
        logger.warning("prompt_injection_suspected", extra={"matched": matched})
    return ScreenResult(text=text, suspicious=bool(matched), matched=matched)


def redact_output(text: str) -> str:
    """Replace likely secrets with placeholder labels."""
    out = text
    for pattern, label in _SECRET_PATTERNS:
        out = pattern.sub(label, out)
    return out


__all__ = ["ScreenResult", "redact_output", "screen_input"]
