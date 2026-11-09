"""
LocalPilot — Safety helpers

* Telegram-safe formatting: all bot messages use Telegram's HTML parse mode and
  every dynamic value (user text, URLs, email subjects/previews, model answers)
  goes through ``h()`` so Markdown/HTML special characters can never break a message.
* Secret redaction: ``redact()`` masks passwords, tokens, API keys and card numbers.
  It is applied to log output (``RedactingFormatter``) and to every prompt sent to
  the local model (see ``browser_service._chat``).
* Untrusted content wrapping: ``wrap_untrusted()`` fences webpage text so the model
  is told to treat it as data, never as instructions.
"""

import html
import logging
import re
from typing import Any

# Telegram rejects messages longer than 4096 characters after entity parsing.
TELEGRAM_SAFE_TEXT_LIMIT = 3000


# --------------------------------------------------------------------------- #
# Telegram formatting
# --------------------------------------------------------------------------- #

def h(value: Any) -> str:
    """Escapes a dynamic value for Telegram HTML parse mode (&, <, >)."""
    return html.escape("" if value is None else str(value), quote=False)


def truncate(value: Any, limit: int = TELEGRAM_SAFE_TEXT_LIMIT) -> str:
    """Shortens text to ``limit`` characters, appending an ellipsis when cut."""
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


# --------------------------------------------------------------------------- #
# Secret redaction
# --------------------------------------------------------------------------- #

REDACTED = "[REDACTED]"

# Order matters: specific token formats first, generic key=value last.
_TOKEN_PATTERNS = [
    # Telegram bot token, also when embedded in an API URL (".../bot<token>/getMe")
    (re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}"), "[REDACTED_TELEGRAM_TOKEN]"),
    # Google OAuth access / refresh tokens
    (re.compile(r"ya29\.[0-9A-Za-z_\-]+"), "[REDACTED_GOOGLE_TOKEN]"),
    (re.compile(r"\b1//[0-9A-Za-z_\-]{20,}"), "[REDACTED_GOOGLE_TOKEN]"),
    # Common API key formats
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_API_KEY]"),
    # JSON Web Tokens
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "[REDACTED_JWT]"),
    # Authorization headers
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=+/]{8,}"), "Bearer [REDACTED]"),
    # Fernet tokens (vault ciphertext)
    (re.compile(r"\bgAAAAA[A-Za-z0-9_\-=]{20,}"), "[REDACTED_CIPHERTEXT]"),
]

_SECRET_KEYWORDS = (
    r"password|passwd|pwd|passcode|pin|secret|token|api[_\- ]?key|access[_\- ]?token|"
    r"refresh[_\- ]?token|client[_\- ]?secret|cvv|cvc|security[_\- ]?code|otp"
)
# "password: x", "password=x", "token is x", "my password is x", '"password": "x"'
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(\b(?:" + _SECRET_KEYWORDS + r")\b[\"']?\s*(?:[:=]|\bis\b)\s*[\"']?)([^\s\"',;]+)"
)

_CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _redact_cards(text: str) -> str:
    def repl(match: "re.Match[str]") -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            return "[REDACTED_CARD]"
        return match.group(0)

    return _CARD_CANDIDATE.sub(repl, text)


def redact(value: Any) -> str:
    """Masks secrets (tokens, API keys, passwords, card numbers) in arbitrary text."""
    text = "" if value is None else str(value)
    if not text:
        return text
    for pattern, replacement in _TOKEN_PATTERNS:
        text = pattern.sub(replacement, text)
    text = _KEY_VALUE_PATTERN.sub(lambda m: m.group(1) + REDACTED, text)
    text = _redact_cards(text)
    return text


class RedactingFormatter(logging.Formatter):
    """Log formatter that redacts secrets from the final line, including tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


# --------------------------------------------------------------------------- #
# Prompt-injection fencing
# --------------------------------------------------------------------------- #

UNTRUSTED_OPEN = "<<<UNTRUSTED_WEB_CONTENT>>>"
UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_WEB_CONTENT>>>"


def wrap_untrusted(text: Any) -> str:
    """
    Fences webpage-derived text for the model. Delimiter look-alikes inside the
    content are neutralised so a page cannot "close" the fence and inject text
    that appears to come from LocalPilot.
    """
    body = "" if text is None else str(text)
    body = body.replace("<<<", "< < <").replace(">>>", "> > >")
    return f"{UNTRUSTED_OPEN}\n{body}\n{UNTRUSTED_CLOSE}"
