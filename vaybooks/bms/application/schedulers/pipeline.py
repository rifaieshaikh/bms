"""Batched identify/process pipeline shared by every scheduler job."""

from __future__ import annotations

import logging
import time as time_module
from typing import Callable, Iterable, List, Optional, Sequence

from vaybooks.bms.application.schedulers.protocol import JobContext, JobResult, SchedulerJob
from vaybooks.bms.domain.schedulers.entities import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    SchedulerRunLog,
)
from vaybooks.bms.domain.schedulers.time import utc_now

logger = logging.getLogger("vaybooks.bms.schedulers")

MAX_LOGGED_DETAILS = 20


def chunks(items: Sequence[str], size: int) -> Iterable[List[str]]:
    step = max(1, int(size))
    for start in range(0, len(items), step):
        yield list(items[start : start + step])


def run_job(
    job: SchedulerJob,
    ctx: JobContext,
    log: SchedulerRunLog,
    *,
    heartbeat: Optional[Callable[[], None]] = None,
    sleep: Callable[[float], None] = time_module.sleep,
) -> SchedulerRunLog:
    """Execute one job end to end and populate its run log.

    Identify never writes. Batches are processed sequentially with a pause in
    between so a large wave stays gentle on the database.
    """
    config = ctx.config
    log.batch_size = config.batch_size
    try:
        identified = list(job.identify(ctx) or [])
    except Exception as exc:  # a broken identify must not kill the wave
        logger.exception("Scheduler job %s failed during identify", config.job_id)
        log.status = STATUS_FAILED
        log.error_summary = f"identify failed: {exc}"[:2000]
        log.finished_at = utc_now()
        return log

    log.identified_count = len(identified)
    cap = max(1, int(config.max_ids_per_run))
    if len(identified) > cap:
        log.details.append(
            f"Capped at {cap} of {len(identified)} candidates; remainder stays due."
        )
        identified = identified[:cap]

    if ctx.dry_run:
        log.status = STATUS_DRY_RUN
        log.batch_count = len(list(chunks(identified, config.batch_size)))
        log.finished_at = utc_now()
        return log

    aggregate = JobResult()
    batch_index = 0
    for batch in chunks(identified, config.batch_size):
        batch_index += 1
        try:
            result = job.process_batch(ctx, batch)
            aggregate.merge(result or JobResult())
        except Exception as exc:
            logger.exception(
                "Scheduler job %s failed on batch %s", config.job_id, batch_index
            )
            aggregate.errors += 1
            aggregate.messages.append(f"batch {batch_index}: {exc}")
        if heartbeat:
            try:
                heartbeat()
            except Exception:
                logger.debug("Lease heartbeat failed for %s", config.job_id)
        pause = max(0, int(config.batch_pause_ms)) / 1000.0
        if pause:
            sleep(pause)

    log.batch_count = batch_index
    log.processed_count = aggregate.processed
    log.created_count = aggregate.created
    log.skipped_count = aggregate.skipped
    log.error_count = aggregate.errors
    log.details.extend([str(m)[:500] for m in aggregate.messages[:MAX_LOGGED_DETAILS]])
    if aggregate.errors:
        log.status = STATUS_COMPLETED_WITH_ERRORS
        log.error_summary = "; ".join(str(m) for m in aggregate.messages[:5])[:2000]
    else:
        log.status = STATUS_COMPLETED
    log.finished_at = utc_now()
    return log
