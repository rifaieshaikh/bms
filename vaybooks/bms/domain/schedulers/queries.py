"""Read-only, projection-first queries used by scheduler identify phases.

Jobs must never hydrate whole collections during identify. Every method here
returns identifiers (or tiny tuples) so the write path can reload only the
records in the current batch.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Protocol, Sequence, Tuple


class SchedulerQueries(Protocol):
    # --- CRM ---
    def crm_activity_ids_scheduled_between(
        self, start: datetime, end: datetime, *, limit: int
    ) -> List[str]: ...

    def crm_activity_ids_overdue(self, before: datetime, *, limit: int) -> List[str]: ...

    def crm_activity_ids_by_type_scheduled_between(
        self, type_keys: Sequence[str], start: datetime, end: datetime, *, limit: int
    ) -> List[str]: ...

    def crm_activity_ids_promise_due(
        self, boundary: datetime, *, limit: int
    ) -> List[str]: ...

    def crm_lead_ids_follow_up_due(
        self, before: datetime, *, limit: int
    ) -> List[str]: ...

    def crm_lead_ids_high_priority_idle(
        self, priorities: Sequence[str], before: datetime, *, limit: int
    ) -> List[str]: ...

    def crm_lead_ids_unassigned(self, before: datetime, *, limit: int) -> List[str]: ...

    def crm_enquiry_ids_stale(
        self, before: datetime, *, limit: int
    ) -> List[str]: ...

    def crm_customer_ids_without_activity_since(
        self, since: datetime, *, limit: int
    ) -> List[str]: ...

    def crm_customer_ids_without_visit_since(
        self, type_keys: Sequence[str], since: datetime, *, limit: int
    ) -> List[str]: ...

    def receivable_customer_ids(
        self, minimum: float, *, limit: int
    ) -> List[str]: ...

    def crm_customer_ids_with_recent_collection(
        self, type_keys: Sequence[str], since: datetime
    ) -> List[str]: ...

    # --- Sales ---
    def sales_document_ids_expiring(
        self,
        collection: str,
        statuses: Sequence[str],
        on_or_before: date,
        *,
        limit: int,
    ) -> List[str]: ...

    def sales_order_ids_overdue(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]: ...

    def sales_order_ids_without_progress(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]: ...

    def sales_document_ids_by_status_before(
        self,
        collection: str,
        statuses: Sequence[str],
        date_field: str,
        before: date,
        *,
        limit: int,
    ) -> List[str]: ...

    # --- Purchases ---
    def purchase_order_ids_overdue(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]: ...

    def purchase_order_ids_without_receipt(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]: ...

    def vendor_ids_with_open_bills(self, minimum: float, *, limit: int) -> List[str]: ...

    # --- Inventory ---
    def product_ids_low_stock(
        self, threshold: float, *, limit: int
    ) -> List[str]: ...

    def product_ids_negative_stock(self, *, limit: int) -> List[str]: ...

    def stock_balance_keys_negative(self, *, limit: int) -> List[str]: ...

    def product_ids_inactive_with_stock(
        self, minimum_qty: float, *, limit: int
    ) -> List[str]: ...

    def stock_transfer_ids_stale(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]: ...

    # --- Production ---
    def production_batch_ids_by_status_before(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]: ...

    def production_batch_ids_by_status(
        self, statuses: Sequence[str], *, limit: int
    ) -> List[str]: ...

    def production_batch_ids_margin_below(
        self, maximum: float, *, limit: int
    ) -> List[str]: ...

    # --- Boutique ---
    def boutique_order_ids_by_etd(
        self,
        exclude_statuses: Sequence[str],
        start: datetime,
        end: datetime,
        *,
        limit: int,
    ) -> List[str]: ...

    def boutique_order_ids_etd_before(
        self, exclude_statuses: Sequence[str], before: datetime, *, limit: int
    ) -> List[str]: ...

    def boutique_item_refs_due(
        self, exclude_statuses: Sequence[str], on_or_before: datetime, *, limit: int
    ) -> List[str]: ...

    def boutique_activity_bottlenecks(
        self, exclude_statuses: Sequence[str], statuses: Sequence[str]
    ) -> Dict[str, Tuple[int, int]]: ...

    def boutique_activity_refs_overdue(
        self,
        exclude_statuses: Sequence[str],
        statuses: Sequence[str],
        before: datetime,
        *,
        limit: int,
    ) -> List[str]: ...

    def boutique_order_ids_pending_invoice(
        self, exclude_statuses: Sequence[str], *, limit: int
    ) -> List[str]: ...

    def boutique_order_ids_pending_delivery(
        self, exclude_statuses: Sequence[str], *, limit: int
    ) -> List[str]: ...

    def boutique_invoice_ids_with_outstanding(
        self, before: datetime, *, limit: int
    ) -> List[str]: ...

    # --- Projects ---
    def project_activity_refs_overdue(
        self,
        project_statuses: Sequence[str],
        activity_statuses: Sequence[str],
        before: datetime,
        *,
        limit: int,
    ) -> List[str]: ...

    def project_ids_end_overdue(
        self, statuses: Sequence[str], before: datetime, *, limit: int
    ) -> List[str]: ...

    def project_ids_active(
        self, statuses: Sequence[str], *, limit: int
    ) -> List[str]: ...

    def project_ids_with_dpr_on(
        self, project_ids: Sequence[str], day: date, statuses: Sequence[str]
    ) -> List[str]: ...

    def project_document_ids_by_status(
        self,
        collection: str,
        statuses: Sequence[str],
        date_field: str,
        before: datetime,
        *,
        limit: int,
    ) -> List[str]: ...

    def project_document_ids_date_before(
        self,
        collection: str,
        statuses: Sequence[str],
        date_field: str,
        boundary: datetime,
        *,
        limit: int,
    ) -> List[str]: ...

    def project_ids_dlp_candidates(
        self, statuses: Sequence[str], *, limit: int
    ) -> List[str]: ...
