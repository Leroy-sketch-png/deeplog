"""Redaction utilities for handling potentially sensitive log field values.

These helpers are deliberately conservative: they redact anything that
*looks* like a secret or personal identifier, even at the cost of some
false positives, because the source data is confidential security logs.

No function in this module ever writes unredacted values to disk when
called through ``redact_value`` / ``redact_row``.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

# ---------------------------------------------------------------------------
# Column-name based redaction (redact the entire value regardless of content)
# ---------------------------------------------------------------------------

# Column-name "tokens" (as underscore-joined, camelCase-split, whole words)
# that mark a column as always fully redacted, because they are documented
# by the task as likely to carry secrets or personal identifiers.
#
# NOTE: matching is done on WHOLE TOKENS after splitting the column name on
# camelCase/snake_case boundaries (see ``_tokenize_column_name``), never on
# raw substrings. This deliberately avoids false positives such as bare
# "ip" matching inside "Subscript-IP-tion" (i.e. "SubscriptionId").
SENSITIVE_COLUMN_NAME_PATTERNS: List[str] = [
    "token",
    "auth",
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "api_key",
    "email",
    "mail",
    "ip",
    "ip_address",
    "user_id",
    "user",
    "device_id",
    "device",
    "caller",
    "request_id",
    "session_id",
    "trace_id",
    "correlation_id",
    "transaction_id",
    "resource_id",
    "guid",
    "uuid",
    "id",
]

REDACTED = "[REDACTED]"

_CAMEL_SPLIT_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z0-9]+")


def _tokenize_column_name(column_name: str) -> List[str]:
    """Split a column name into lowercase whole-word tokens.

    Handles camelCase, PascalCase, snake_case, and kebab-case boundaries,
    e.g. "CallerIpAddress" -> ["caller", "ip", "address"],
    "SubscriptionId" -> ["subscription", "id"].
    """
    parts = re.split(r"[^A-Za-z0-9]+", column_name)
    tokens: List[str] = []
    for part in parts:
        if not part:
            continue
        tokens.extend(t.lower() for t in _CAMEL_SPLIT_RE.findall(part) if t)
    return tokens


def tokenize_column_name(column_name: str) -> List[str]:
    """Public wrapper around the camelCase/snake_case column tokenizer.

    Exposed for reuse by other modules (e.g. profiling heuristics) that need
    consistent, boundary-safe token matching on column names.
    """
    return _tokenize_column_name(column_name)


def column_is_sensitive_by_name(column_name: str) -> bool:
    """Return True if a column name's whole tokens match a sensitive pattern.

    Multi-word patterns (e.g. "user_id") are matched against adjacent token
    pairs joined by underscore; single-word patterns (e.g. "id", "ip") are
    matched against individual whole tokens only -- never substrings.
    """
    tokens = _tokenize_column_name(column_name)
    if not tokens:
        return False
    joined = "_" + "_".join(tokens) + "_"
    for pattern in SENSITIVE_COLUMN_NAME_PATTERNS:
        if f"_{pattern}_" in joined:
            return True
    return False


# ---------------------------------------------------------------------------
# Value-content based redaction (redact substrings within a value)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# IPv4
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)

# IPv6 (simplified, catches the common colon-hex forms)
_IPV6_RE = re.compile(
    r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{1,4}\b"
)

# GUID/UUID (e.g. subscription/tenant/object identifiers embedded in JSON
# blobs such as Claims/Properties). Dash-separated segments are individually
# short, so this needs its own pattern -- the long-token regex below would
# not otherwise catch them.
_GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}\b"
)

# Bearer / auth header style tokens: "Bearer <token>", "Basic <token>"
_AUTH_HEADER_RE = re.compile(
    r"\b(Bearer|Basic|Token)\s+[A-Za-z0-9\-_.=]+", re.IGNORECASE
)

# Generic looking secret/token values: long runs of base64/hex-ish chars.
# Restricted to values that mix letters+digits (or are long hex/base64-like)
# so that plain camelCase JSON *key names* (e.g. "eventSubmissionTimestamp")
# are not falsely treated as secrets.
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{24,}\b")
_HAS_DIGIT_RE = re.compile(r"\d")
_HAS_LETTER_RE = re.compile(r"[A-Za-z]")


def _looks_like_token(candidate: str) -> bool:
    """Heuristic: treat as a likely token/secret only if it mixes letters and
    digits (typical of API keys, JWtd fragments, hashes, GUIDs-without-dashes),
    not if it is purely alphabetic (typical of camelCase identifiers/keys)."""
    return bool(_HAS_DIGIT_RE.search(candidate)) and bool(_HAS_LETTER_RE.search(candidate))

# key=value style secrets, e.g. password=hunter2, api_key=abcd1234
_KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token|auth)\s*[:=]\s*"
    r"([^\s,;&]+)"
)


def redact_value_content(value: str) -> str:
    """Redact likely secrets/PII substrings *within* a string value.

    This does not redact the whole value -- it targets specific patterns
    (emails, IPs, auth headers, key=value secrets, long opaque tokens).
    """
    if value is None:
        return value

    text = str(value)

    text = _KEY_VALUE_SECRET_RE.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    text = _AUTH_HEADER_RE.sub(f"\\1 {REDACTED}", text)
    text = _EMAIL_RE.sub(REDACTED, text)
    text = _IPV4_RE.sub(REDACTED, text)
    text = _IPV6_RE.sub(REDACTED, text)
    text = _GUID_RE.sub(REDACTED, text)
    # Long opaque tokens (do this last, after more specific patterns already
    # consumed / shortened matches above). Only redact candidates that mix
    # letters and digits, to avoid false positives on long camelCase field
    # names such as "eventSubmissionTimestamp".
    text = _LONG_TOKEN_RE.sub(
        lambda m: REDACTED if _looks_like_token(m.group(0)) else m.group(0), text
    )

    return text


def redact_value(column_name: str, value: str) -> str:
    """Redact a single field value, honoring both column name and content."""
    if value is None:
        return value
    if column_is_sensitive_by_name(column_name):
        return REDACTED
    return redact_value_content(value)


def redact_row(row: Dict[str, str]) -> Dict[str, str]:
    """Return a new dict with every value passed through ``redact_value``."""
    return {col: redact_value(col, val) for col, val in row.items()}


def redact_row_values(header: Iterable[str], row: List[str]) -> List[str]:
    """Redact a positional row (list of values) given its header."""
    return [redact_value(col, val) for col, val in zip(header, row)]
