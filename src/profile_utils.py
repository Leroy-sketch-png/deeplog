"""Reusable streaming statistics accumulators for Phase B dataset profiling.

Design goals:
  * Bounded memory regardless of input size (all per-column value sets and
    counters are capped; the caps are recorded so callers can report them).
  * Single-pass streaming: every accumulator supports ``update(value)`` and
    can be queried for a summary at any time.
  * No dependency beyond the standard library.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration constants (documented caps / thresholds)
# ---------------------------------------------------------------------------

CARDINALITY_CAP = 2000          # max distinct values tracked per column
TOP_VALUES_REPORTED = 20        # top-N values reported for low-cardinality cols
MAX_DUPLICATE_ROW_HASHES = 3_000_000  # cap for full-row duplicate detection

PLACEHOLDER_TOKENS = {"null", "none", "unknown", "n/a", "-", ""}


def normalize_placeholder(value: str) -> str:
    return value.strip().lower()


# ---------------------------------------------------------------------------
# Timestamp parsing helper
# ---------------------------------------------------------------------------

_TRAILING_Z_RE = re.compile(r"Z$")


def try_parse_timestamp(value: str) -> Optional[datetime]:
    """Best-effort ISO-8601-ish timestamp parser using only the stdlib.

    Returns None if parsing fails. Does not raise.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    # Normalize a trailing 'Z' (Zulu/UTC) to +00:00 for datetime.fromisoformat,
    # which (on Python < 3.11) does not accept 'Z' directly.
    normalized = _TRAILING_Z_RE.sub("+00:00", text)
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    # Common alternative formats seen in logs.
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def try_parse_number(value: str) -> Optional[float]:
    """Best-effort numeric parser. Returns None (not 0) on failure."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Per-column accumulator
# ---------------------------------------------------------------------------

@dataclass
class ColumnStats:
    name: str
    # If True, this column's name matched a sensitive-field pattern (see
    # ``src.redact.column_is_sensitive_by_name``). Cardinality is then
    # tracked via a one-way hash of the value instead of the raw value, so
    # no secret/PII ever ends up in an in-memory dict or output artifact.
    is_sensitive: bool = False

    total_count: int = 0
    null_or_blank_count: int = 0
    placeholder_counts: Dict[str, int] = field(default_factory=dict)

    # Bounded cardinality tracking (raw values, as observed).
    value_counts: Dict[str, int] = field(default_factory=dict)
    cardinality_capped: bool = False

    # Bounded cardinality tracking of normalized (strip+lower) values, used
    # to detect inconsistent capitalization/whitespace.
    normalized_value_counts: Dict[str, int] = field(default_factory=dict)

    # String length running stats (Welford-style running sum/sumsq).
    len_count: int = 0
    len_sum: int = 0
    len_sumsq: int = 0
    len_min: Optional[int] = None
    len_max: Optional[int] = None

    # Numeric running stats.
    numeric_success_count: int = 0
    numeric_fail_count: int = 0
    numeric_min: Optional[float] = None
    numeric_max: Optional[float] = None

    # Timestamp running stats (only meaningful for candidate timestamp cols).
    timestamp_success_count: int = 0
    timestamp_fail_count: int = 0
    timestamp_min: Optional[datetime] = None
    timestamp_max: Optional[datetime] = None
    timestamp_out_of_order_count: int = 0
    timestamp_duplicate_count: int = 0
    _last_timestamp: Optional[datetime] = field(default=None, repr=False)
    _last_timestamp_seen: bool = field(default=False, repr=False)

    def update(self, raw_value: Optional[str], is_timestamp_candidate: bool) -> None:
        self.total_count += 1
        value = "" if raw_value is None else raw_value

        stripped = value.strip()
        norm = normalize_placeholder(value)
        if norm in PLACEHOLDER_TOKENS:
            self.null_or_blank_count += 1
            self.placeholder_counts[norm] = self.placeholder_counts.get(norm, 0) + 1

        # Length stats (based on raw, un-stripped value length).
        length = len(value)
        self.len_count += 1
        self.len_sum += length
        self.len_sumsq += length * length
        self.len_min = length if self.len_min is None else min(self.len_min, length)
        self.len_max = length if self.len_max is None else max(self.len_max, length)

        # Bounded cardinality tracking. For sensitive columns, track a
        # one-way hash of the value instead of the raw value -- this keeps
        # cardinality/rows-per-identifier estimation possible (needed for
        # sequence-key suitability assessment) without ever retaining or
        # exporting the actual identifier value.
        cardinality_key = value
        if self.is_sensitive and value != "":
            import hashlib
            cardinality_key = "h_" + hashlib.sha256(
                value.encode("utf-8", errors="replace")
            ).hexdigest()[:16]

        if not self.cardinality_capped:
            if cardinality_key in self.value_counts:
                self.value_counts[cardinality_key] += 1
            elif len(self.value_counts) < CARDINALITY_CAP:
                self.value_counts[cardinality_key] = 1
            else:
                self.cardinality_capped = True

        if not self.is_sensitive and not self.cardinality_capped:
            if norm in self.normalized_value_counts:
                self.normalized_value_counts[norm] += 1
            elif len(self.normalized_value_counts) < CARDINALITY_CAP:
                self.normalized_value_counts[norm] = 1

        # Numeric attempt (skip placeholders/blank to avoid noise).
        if stripped and norm not in PLACEHOLDER_TOKENS:
            num = try_parse_number(stripped)
            if num is not None:
                self.numeric_success_count += 1
                self.numeric_min = num if self.numeric_min is None else min(self.numeric_min, num)
                self.numeric_max = num if self.numeric_max is None else max(self.numeric_max, num)
            else:
                self.numeric_fail_count += 1

        # Timestamp attempt, only for candidate timestamp columns.
        if is_timestamp_candidate and stripped and norm not in PLACEHOLDER_TOKENS:
            ts = try_parse_timestamp(stripped)
            if ts is not None:
                self.timestamp_success_count += 1
                self.timestamp_min = ts if self.timestamp_min is None else min(self.timestamp_min, ts)
                self.timestamp_max = ts if self.timestamp_max is None else max(self.timestamp_max, ts)
                if self._last_timestamp_seen:
                    if ts < self._last_timestamp:
                        self.timestamp_out_of_order_count += 1
                    elif ts == self._last_timestamp:
                        self.timestamp_duplicate_count += 1
                self._last_timestamp = ts
                self._last_timestamp_seen = True
            else:
                self.timestamp_fail_count += 1

    # -- derived summaries -------------------------------------------------

    def length_mean_std(self) -> Tuple[Optional[float], Optional[float]]:
        if self.len_count == 0:
            return None, None
        mean = self.len_sum / self.len_count
        variance = max(0.0, (self.len_sumsq / self.len_count) - (mean * mean))
        return mean, math.sqrt(variance)

    def top_values(self, n: int = TOP_VALUES_REPORTED) -> List[Tuple[str, int]]:
        """Return top-N (value, count) pairs.

        For sensitive columns, ``value`` here is already a one-way hash
        (never the raw value) because ``value_counts`` keys were hashed at
        update-time. Callers should still run non-sensitive values through
        content-redaction defensively before persisting to disk.
        """
        return sorted(self.value_counts.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def approx_cardinality_label(self) -> str:
        distinct = len(self.value_counts)
        if self.cardinality_capped:
            return f">= {CARDINALITY_CAP} (capped, approximate)"
        return str(distinct)

    def inconsistent_casing_detected(self) -> bool:
        if self.is_sensitive or self.cardinality_capped:
            return False  # not meaningful/safe to compute
        return len(self.value_counts) > len(self.normalized_value_counts)


# ---------------------------------------------------------------------------
# Bounded full-row duplicate tracker
# ---------------------------------------------------------------------------

class DuplicateRowTracker:
    """Tracks approximate/exact duplicate full rows via bounded hash set."""

    def __init__(self, cap: int = MAX_DUPLICATE_ROW_HASHES):
        self.cap = cap
        self._seen: set = set()
        self.capped = False
        self.duplicate_count = 0
        self.rows_considered = 0

    def observe(self, row_key: str) -> None:
        self.rows_considered += 1
        if self.capped:
            return
        import hashlib

        digest = hashlib.blake2b(row_key.encode("utf-8", errors="replace"), digest_size=16).digest()
        if digest in self._seen:
            self.duplicate_count += 1
        else:
            if len(self._seen) >= self.cap:
                self.capped = True
                return
            self._seen.add(digest)

    def summary(self) -> Dict[str, object]:
        return {
            "rows_considered": self.rows_considered,
            "duplicate_count": self.duplicate_count,
            "capped": self.capped,
            "cap": self.cap,
            "note": (
                "Approximate: hash-set capped before full file was scanned."
                if self.capped
                else "Exact over rows successfully parsed."
            ),
        }
