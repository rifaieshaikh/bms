"""AR aging helpers: configurable day buckets and FIFO open-balance allocation."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Sequence


DEFAULT_AGING_BUCKET_DAYS: tuple[int, ...] = (30, 60, 90)


def normalize_aging_bucket_days(
    raw: str | Sequence[int] | None,
    *,
    default: Sequence[int] = DEFAULT_AGING_BUCKET_DAYS,
) -> list[int]:
    """Parse ascending positive day cutoffs (e.g. ``\"30, 60, 90\"`` or ``[30, 60, 90]``)."""
    if raw is None or raw == "":
        values = list(default)
    elif isinstance(raw, str):
        values = []
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(int(part))
            except ValueError:
                continue
    else:
        values = [int(v) for v in raw]

    cleaned = sorted({max(0, int(v)) for v in values if int(v) > 0})
    return cleaned or list(default)


def aging_bucket_labels(cutoffs: Sequence[int]) -> list[str]:
    """Labels for ``[30, 60, 90]`` → ``0-30``, ``31-60``, ``61-90``, ``90+``."""
    if not cutoffs:
        cutoffs = list(DEFAULT_AGING_BUCKET_DAYS)
    labels: list[str] = []
    prev = 0
    for cutoff in cutoffs:
        if prev == 0:
            labels.append(f"0-{cutoff}")
        else:
            labels.append(f"{prev + 1}-{cutoff}")
        prev = cutoff
    labels.append(f"{prev}+")
    return labels


def aging_bucket_index(days: int, cutoffs: Sequence[int]) -> int:
    """Return bucket index for ``days`` outstanding (0 = newest / current)."""
    days = max(0, int(days))
    for idx, cutoff in enumerate(cutoffs):
        if days <= cutoff:
            return idx
    return len(cutoffs)


def empty_aging_buckets(cutoffs: Sequence[int]) -> dict[str, float]:
    return {label: 0.0 for label in aging_bucket_labels(cutoffs)}


def allocate_balance_to_aging_buckets(
    ledger_balance: float,
    invoices: Iterable[dict],
    *,
    as_of: date,
    cutoffs: Sequence[int],
) -> tuple[dict[str, float], int]:
    """Age ``ledger_balance`` across open invoices (FIFO payment to oldest).

    Each invoice dict needs ``invoice_date`` and ``outstanding`` (face open amount).
    When ledger exceeds invoice faces, the surplus is placed in the oldest bucket
    (opening / unallocated AR). Returns ``(bucket_amounts, oldest_days)``.
    """
    buckets = empty_aging_buckets(cutoffs)
    labels = aging_bucket_labels(cutoffs)
    balance = round(max(float(ledger_balance or 0), 0.0), 2)
    if balance <= 0:
        return buckets, 0

    faces: list[tuple[date, float]] = []
    for inv in invoices:
        inv_date = inv.get("invoice_date")
        if hasattr(inv_date, "date") and callable(inv_date.date):
            inv_date = inv_date.date()
        if not isinstance(inv_date, date):
            continue
        amount = round(max(float(inv.get("outstanding") or 0), 0.0), 2)
        if amount <= 0:
            continue
        faces.append((inv_date, amount))

    faces.sort(key=lambda item: item[0])
    total_face = round(sum(amount for _, amount in faces), 2)
    # Assume subsequent receipts settled oldest invoices first.
    payment_left = round(max(total_face - balance, 0.0), 2)

    oldest_days = 0
    open_items: list[tuple[date, float]] = []
    for inv_date, face in faces:
        applied = min(face, payment_left)
        payment_left = round(payment_left - applied, 2)
        open_amt = round(face - applied, 2)
        if open_amt > 0:
            open_items.append((inv_date, open_amt))

    allocated = 0.0
    for inv_date, open_amt in open_items:
        days = max(0, (as_of - inv_date).days)
        oldest_days = max(oldest_days, days)
        label = labels[aging_bucket_index(days, cutoffs)]
        buckets[label] = round(buckets[label] + open_amt, 2)
        allocated = round(allocated + open_amt, 2)

    surplus = round(balance - allocated, 2)
    if surplus > 0:
        # Opening balance / AR without matching open invoices → oldest bucket.
        buckets[labels[-1]] = round(buckets[labels[-1]] + surplus, 2)
        if not open_items:
            oldest_days = max(oldest_days, cutoffs[-1] + 1 if cutoffs else 0)

    return buckets, oldest_days
