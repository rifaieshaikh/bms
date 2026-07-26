"""Daemon background execution with process locks and Mongo leases."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Dict

logger = logging.getLogger("vaybooks.bms.schedulers")

# Lease lifetime; refreshed after every batch so long waves keep their claim.
LEASE_TTL_SECONDS = 300


class ProcessLocks:
    """In-process guard so one Streamlit process never double-starts a key."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._active: Dict[str, bool] = {}

    def try_acquire(self, key: str) -> bool:
        with self._guard:
            if self._active.get(key):
                return False
            self._active[key] = True
            return True

    def release(self, key: str) -> None:
        with self._guard:
            self._active.pop(key, None)

    def is_active(self, key: str) -> bool:
        with self._guard:
            return bool(self._active.get(key))

    def active_keys(self) -> list[str]:
        with self._guard:
            return [k for k, v in self._active.items() if v]


def start_background(target: Callable[[], None], *, name: str) -> threading.Thread:
    """Run work on a daemon thread so the Streamlit script never blocks."""

    def _wrapped() -> None:
        try:
            target()
        except Exception:
            logger.exception("Scheduler worker %s crashed", name)

    thread = threading.Thread(target=_wrapped, name=name, daemon=True)
    thread.start()
    return thread
