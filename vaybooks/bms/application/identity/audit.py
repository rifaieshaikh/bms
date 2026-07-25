"""Access audit application service with optional async persistence."""

from __future__ import annotations

import atexit
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from vaybooks.bms.domain.identity.audit import AccessAuditEntry

logger = logging.getLogger(__name__)

# Returns (actor_id, actor_name) for the current session; injected by the UI.
ActorResolver = Callable[[], Tuple[str, str]]


class _AsyncAuditWriter:
    """Daemon worker that drains a queue of AccessAuditEntry saves."""

    def __init__(self, save_fn: Callable[[AccessAuditEntry], AccessAuditEntry]):
        self._save = save_fn
        self._q: queue.Queue[Optional[AccessAuditEntry]] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="access-audit-writer",
            daemon=True,
        )
        self._thread.start()
        atexit.register(self.shutdown)

    def enqueue(self, entry: AccessAuditEntry) -> None:
        self._q.put(entry)

    def flush(self, timeout: float = 5.0) -> None:
        """Block until the queue is drained (or timeout)."""
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            if self._q.unfinished_tasks == 0:
                return
            time.sleep(0.02)
        logger.warning(
            "Access audit flush timed out with %s pending writes",
            self._q.unfinished_tasks,
        )

    def shutdown(self) -> None:
        if self._stop.is_set():
            return
        self.flush(timeout=3.0)
        self._stop.set()
        self._q.put(None)
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                entry = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if entry is None:
                self._q.task_done()
                break
            try:
                self._save(entry)
            except Exception:
                logger.exception(
                    "Failed to persist access audit entry action=%s id=%s",
                    getattr(entry, "action", ""),
                    getattr(entry, "id", ""),
                )
            finally:
                self._q.task_done()


class AccessAuditAppService:
    def __init__(
        self,
        audit_repo,
        actor_resolver: Optional[ActorResolver] = None,
        *,
        async_write: bool = False,
    ):
        self._repo = audit_repo
        self._actor_resolver = actor_resolver
        self._async_write = bool(async_write)
        self._writer: Optional[_AsyncAuditWriter] = None
        if self._async_write:
            self._writer = _AsyncAuditWriter(self._repo.save)

    def record(
        self,
        action: str,
        *,
        target_type: str = "",
        target_id: str = "",
        target_label: str = "",
        detail: Optional[dict] = None,
        actor_id: str = "",
        actor_name: str = "",
    ) -> AccessAuditEntry:
        if not actor_id and not actor_name and self._actor_resolver:
            try:
                actor_id, actor_name = self._actor_resolver()
            except Exception:
                actor_id, actor_name = "", ""
        entry = AccessAuditEntry(
            action=action,
            actor_id=actor_id,
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            detail=dict(detail or {}),
        )
        if self._writer is not None:
            self._writer.enqueue(entry)
            return entry
        try:
            return self._repo.save(entry)
        except Exception:
            logger.exception(
                "Failed to persist access audit entry action=%s id=%s",
                entry.action,
                entry.id,
            )
            return entry

    def flush(self, timeout: float = 5.0) -> None:
        if self._writer is not None:
            self._writer.flush(timeout)

    def list_entries(
        self,
        *,
        actor_id: str = "",
        action: str = "",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[AccessAuditEntry]:
        # Ensure recent async writes are visible before reading.
        self.flush(timeout=2.0)
        return self._repo.list_entries(
            actor_id=actor_id, action=action, start=start, end=end, limit=limit
        )

    def list_by_actor(self, actor_id: str, limit: int = 200) -> List[AccessAuditEntry]:
        return self.list_entries(actor_id=actor_id, limit=limit)

    def count_entries(self) -> int:
        self.flush(timeout=2.0)
        count_fn = getattr(self._repo, "count", None)
        if callable(count_fn):
            return int(count_fn())
        return len(self._repo.list_entries(limit=10_000))
