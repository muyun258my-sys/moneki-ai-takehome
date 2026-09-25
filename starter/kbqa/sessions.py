"""对话历史。"""

from __future__ import annotations

import threading
from typing import Optional

MAX_TURNS = 6
MAX_SESSIONS = 500


class SessionStore:
    """最近几轮对话，够解追问就行。"""

    def __init__(self, max_sessions: int = MAX_SESSIONS, max_turns: int = MAX_TURNS) -> None:
        self._sessions: dict[str, list[dict]] = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.max_turns = max_turns

    def history(self, session_id: Optional[str]) -> list[dict]:
        key = session_id or ""
        with self._lock:
            return list(self._sessions.get(key, []))

    def append(self, session_id: Optional[str], turn: dict) -> None:
        key = session_id or ""
        with self._lock:
            turns = self._sessions.setdefault(key, [])
            turns.append(turn)
            del turns[: max(0, len(turns) - self.max_turns)]
            while len(self._sessions) > self.max_sessions:
                self._sessions.pop(next(iter(self._sessions)))

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
