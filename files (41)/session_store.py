"""
services/session_store.py
──────────────────────────
Lightweight in-memory store that replaces Streamlit's session_state.
Keyed by browser session-id (stored in a cookie / passed as header).

For production replace with Redis or a DB-backed store.
"""

from __future__ import annotations
import threading
from typing import Any

_store: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def get(session_id: str, key: str, default: Any = None) -> Any:
    with _lock:
        return _store.get(session_id, {}).get(key, default)


def set(session_id: str, key: str, value: Any) -> None:
    with _lock:
        if session_id not in _store:
            _store[session_id] = {}
        _store[session_id][key] = value


def delete(session_id: str, key: str) -> None:
    with _lock:
        _store.get(session_id, {}).pop(key, None)


def clear_session(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)
