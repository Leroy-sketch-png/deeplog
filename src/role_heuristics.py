"""Name-based heuristic role tagging for CSV columns.

IMPORTANT: these are candidate/heuristic tags only, based on column-name
tokens. They must never be reported as confirmed semantic conclusions
(e.g. "this IS the session identifier") -- only as candidates to be
corroborated with actual value statistics (cardinality, non-null %, etc.)
gathered during profiling.
"""

from __future__ import annotations

from typing import Dict, List

from .redact import tokenize_column_name

TIMESTAMP_TOKENS = {"time", "timestamp", "date", "generated"}

IDENTIFIER_TOKENS = {
    "id", "guid", "uuid", "correlation", "session", "request", "trace",
    "transaction", "process", "host", "user", "device", "caller",
    "subscription",
}

EVENT_TYPE_TOKENS = {
    "operation", "action", "event", "name", "type", "category", "provider",
}

MESSAGE_TOKENS = {
    "message", "description", "msg", "detail", "details", "properties",
    "body", "claims", "authorization",
}

SEVERITY_STATUS_TOKENS = {
    "level", "severity", "status", "result", "outcome", "disposition",
    "label", "risk", "score",
}


def _tokens_intersect(name: str, keyword_set: set) -> bool:
    tokens = set(tokenize_column_name(name))
    return bool(tokens & keyword_set)


def classify_column_name(name: str) -> Dict[str, bool]:
    """Return heuristic candidate-role flags for a single column name."""
    return {
        "timestamp_candidate": _tokens_intersect(name, TIMESTAMP_TOKENS),
        "identifier_candidate": _tokens_intersect(name, IDENTIFIER_TOKENS),
        "event_type_candidate": _tokens_intersect(name, EVENT_TYPE_TOKENS),
        "message_or_blob_candidate": _tokens_intersect(name, MESSAGE_TOKENS),
        "severity_status_candidate": _tokens_intersect(name, SEVERITY_STATUS_TOKENS),
    }


def classify_all_columns(column_names: List[str]) -> Dict[str, Dict[str, bool]]:
    return {name: classify_column_name(name) for name in column_names}
