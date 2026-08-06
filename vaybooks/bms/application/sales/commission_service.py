"""Application service for rule-based commission accrual and payout."""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional, Sequence

from vaybooks.bms.application.sales.commission_engine import (
    CommissionEngine,
    InvoiceCommissionContext,
    InvoiceLineContext,
    PartyCommissionSource,
    build_parties_from_tags,
)
from vaybooks.bms.domain.sales.commission_accrual import (
    STATUS_ACCRUED,
    STATUS_REVERSED,
    CommissionAccrualCandidate,
    CommissionAccrualEntry,
    candidate_to_entry,
)
from vaybooks.bms.domain.sales.commission_rules import (
    BASIS_COLLECTION,
    BASIS_SALES,
    PARTY_AGENT,
    PARTY_SALES_REP,
    empty_commission_profile,
)
from vaybooks.bms.domain.shared.date_utils import utc_now

logger = logging.getLogger(__name__)


def parse_commission_tags(description: str) -> dict:
    """Extract commission_agent_ids / sales_rep_ids from invoice note JSON."""
    import json

    if not description or "\n" not in description:
        return {"commission_agent_ids": [], "sales_rep_ids": []}
    try:
        data = json.loads(description.split("\n", 1)[1].strip())
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"commission_agent_ids": [], "sales_rep_ids": []}
    tags = data.get("commission_tags")
    if isinstance(tags, dict):
        return {
            "commission_agent_ids": [
                str(i).strip()
                for i in (tags.get("commission_agent_ids") or [])
                if str(i).strip()
            ],
            "sales_rep_ids": [
                str(i).strip()
                for i in (tags.get("sales_rep_ids") or [])
                if str(i).strip()
            ],
        }
    # Legacy single agent in commission blob
    commission = data.get("commission")
    if isinstance(commission, dict):
        agent_id = str(commission.get("agent_id") or "").strip()
        if agent_id:
            return {"commission_agent_ids": [agent_id], "sales_rep_ids": []}
    return {"commission_agent_ids": [], "sales_rep_ids": []}


class CommissionAppService:
    def __init__(
        self,
        accrual_repo,
        accounting,
        agent_service=None,
        worker_service=None,
        inventory=None,
    ):
        self._accrual_repo = accrual_repo
        self._accounting = accounting
        self._agent_service = agent_service
        self._worker_service = worker_service
        self._inventory = inventory
        self._engine = CommissionEngine(
            threshold_base_lookup=self._threshold_base_lookup
        )

    def _threshold_base_lookup(
        self, party_type: str, party_id: str, period_key: str, basis: str
    ) -> float:
        if hasattr(self._accrual_repo, "sum_base_for_party_period"):
            return float(
                self._accrual_repo.sum_base_for_party_period(
                    party_type, party_id, period_key=period_key, basis=basis
                )
                or 0
            )
        entries = self._accrual_repo.list_by_party(
            party_type, party_id, period_key=period_key, basis=basis
        )
        return round(
            sum(
                float(e.base_amount)
                for e in entries
                if e.status in (STATUS_ACCRUED, "paid") and not e.reversal_of_id
            ),
            2,
        )

    def _category_ids_for_product(self, product_id: str) -> List[str]:
        if not product_id or not self._inventory:
            return []
        try:
            product = self._inventory.get_product(product_id)
        except Exception:
            return []
        if not product:
            return []
        ids = list(getattr(product, "category_ids", None) or [])
        single = getattr(product, "category_id", "") or ""
        if single and single not in ids:
            ids.append(single)
        return [str(i).strip() for i in ids if str(i).strip()]

    def build_invoice_context(
        self,
        *,
        invoice_id: str,
        customer_id: str,
        invoice_date: date,
        sales_lines: Sequence[dict],
        commission_agent_ids: Sequence[str],
        sales_rep_ids: Sequence[str],
        is_fully_paid: bool = False,
        amount_collected_on_invoice: float = 0.0,
    ) -> InvoiceCommissionContext:
        lines: List[InvoiceLineContext] = []
        taxable_total = 0.0
        for raw in sales_lines or []:
            product_id = str(raw.get("product_id") or "").strip()
            taxable = round(float(raw.get("taxable_amount") or 0), 2)
            taxable_total = round(taxable_total + taxable, 2)
            lines.append(
                InvoiceLineContext(
                    product_id=product_id,
                    taxable_amount=taxable,
                    category_ids=self._category_ids_for_product(product_id),
                    qty=float(raw.get("qty") or 0),
                )
            )
        return InvoiceCommissionContext(
            invoice_id=str(invoice_id),
            customer_id=str(customer_id or ""),
            invoice_date=invoice_date,
            lines=lines,
            taxable_total=taxable_total,
            is_fully_paid=bool(is_fully_paid),
            amount_collected_on_invoice=round(float(amount_collected_on_invoice or 0), 2),
            commission_agent_ids=[
                str(i).strip() for i in commission_agent_ids if str(i).strip()
            ],
            sales_rep_ids=[str(i).strip() for i in sales_rep_ids if str(i).strip()],
        )

    def _load_parties(
        self, agent_ids: Sequence[str], sales_rep_ids: Sequence[str]
    ) -> List[PartyCommissionSource]:
        agent_profiles: Dict[str, object] = {}
        if self._agent_service:
            for agent_id in agent_ids or []:
                agent = None
                if hasattr(self._agent_service, "get_agent"):
                    agent = self._agent_service.get_agent(agent_id)
                elif hasattr(self._agent_service, "get_agent_detail"):
                    agent = self._agent_service.get_agent_detail(agent_id)
                if not agent:
                    continue
                profile = getattr(agent, "commission_profile", None) or empty_commission_profile()
                agent_profiles[str(agent_id)] = profile
        sales_rep_profiles: Dict[str, object] = {}
        if self._worker_service:
            for rep_id in sales_rep_ids or []:
                worker = None
                if hasattr(self._worker_service, "get_worker"):
                    worker = self._worker_service.get_worker(rep_id)
                elif hasattr(self._worker_service, "get"):
                    worker = self._worker_service.get(rep_id)
                if not worker or not getattr(worker, "commission_enabled", False):
                    continue
                profile = getattr(worker, "commission_profile", None) or empty_commission_profile()
                sales_rep_profiles[str(rep_id)] = profile
        return build_parties_from_tags(
            agent_ids=agent_ids,
            sales_rep_ids=sales_rep_ids,
            agent_profiles=agent_profiles,
            sales_rep_profiles=sales_rep_profiles,
        )

    def preview_sales_commission(
        self, ctx: InvoiceCommissionContext
    ) -> List[CommissionAccrualCandidate]:
        parties = self._load_parties(ctx.commission_agent_ids, ctx.sales_rep_ids)
        return self._engine.accrue_on_invoice(ctx, parties)

    def preview_collection_commission(
        self,
        ctx: InvoiceCommissionContext,
        *,
        payment_amount: float,
        payment_date: date,
        receipt_id: str = "",
    ) -> List[CommissionAccrualCandidate]:
        parties = self._load_parties(ctx.commission_agent_ids, ctx.sales_rep_ids)
        return self._engine.accrue_on_collection(
            ctx,
            parties,
            payment_amount=payment_amount,
            payment_date=payment_date,
            receipt_id=receipt_id,
        )

    def accrue_on_invoice(
        self,
        ctx: InvoiceCommissionContext,
        *,
        location_id: str = "",
        location_name: str = "",
    ) -> List[CommissionAccrualEntry]:
        candidates = self.preview_sales_commission(ctx)
        return self._persist_and_post(
            candidates,
            description_prefix=f"Sales commission accrual for invoice {ctx.invoice_id}",
            location_id=location_id,
            location_name=location_name,
            event_date=ctx.invoice_date,
        )

    def accrue_on_collection(
        self,
        ctx: InvoiceCommissionContext,
        *,
        payment_amount: float,
        payment_date: date,
        receipt_id: str = "",
        location_id: str = "",
        location_name: str = "",
    ) -> List[CommissionAccrualEntry]:
        candidates = self.preview_collection_commission(
            ctx,
            payment_amount=payment_amount,
            payment_date=payment_date,
            receipt_id=receipt_id,
        )
        return self._persist_and_post(
            candidates,
            description_prefix=(
                f"Collection commission accrual for invoice {ctx.invoice_id}"
            ),
            location_id=location_id,
            location_name=location_name,
            event_date=payment_date,
        )

    def reverse_for_return(
        self,
        *,
        source_invoice_id: str,
        return_ratio: float,
        event_date: Optional[date] = None,
        location_id: str = "",
        location_name: str = "",
    ) -> List[CommissionAccrualEntry]:
        existing = self._accrual_repo.list_by_invoice(
            source_invoice_id, status=STATUS_ACCRUED
        )
        candidates = self._engine.reverse_for_return(
            existing, return_ratio=return_ratio
        )
        # Mark originals reversed proportionally by creating reversal entries
        # and flipping remaining source amount via status when fully reversed.
        saved: List[CommissionAccrualEntry] = []
        ratio = min(max(float(return_ratio or 0), 0.0), 1.0)
        for candidate, source in zip(candidates, existing):
            entry = candidate_to_entry(candidate)
            entry.amount = abs(float(candidate.amount))
            entry.status = STATUS_REVERSED
            entry.reversal_of_id = source.id
            entry.event_date = event_date or source.event_date
            entry = self._accrual_repo.save(entry)
            if ratio >= 0.999:
                source.mark_reversed()
                self._accrual_repo.save(source)
            saved.append(entry)
            self._post_gl_for_entry(
                entry,
                reverse=True,
                description=(
                    f"Commission reversal for invoice {source_invoice_id}"
                ),
                location_id=location_id,
                location_name=location_name,
            )
        return saved

    def _persist_and_post(
        self,
        candidates: Sequence[CommissionAccrualCandidate],
        *,
        description_prefix: str,
        location_id: str,
        location_name: str,
        event_date: date,
    ) -> List[CommissionAccrualEntry]:
        saved: List[CommissionAccrualEntry] = []
        for candidate in candidates:
            if float(candidate.amount) <= 0:
                continue
            entry = candidate_to_entry(candidate)
            entry.event_date = candidate.event_date or event_date
            entry = self._accrual_repo.save(entry)
            self._post_gl_for_entry(
                entry,
                reverse=False,
                description=description_prefix,
                location_id=location_id,
                location_name=location_name,
            )
            saved.append(entry)
        return saved

    def _payable_account(self, party_type: str, party_id: str):
        if party_type == PARTY_AGENT:
            return self._accounting.get_agent_account(party_id)
        # Sales rep → worker salary/commission liability account
        if hasattr(self._accounting, "get_worker_account"):
            return self._accounting.get_worker_account(party_id)
        find = getattr(self._accounting, "_account_repo", None)
        if find and hasattr(find, "find_worker_account"):
            return find.find_worker_account(party_id)
        return None

    def _expense_account(self):
        ensure = getattr(self._accounting, "ensure_commission_expense_account", None)
        if callable(ensure):
            return ensure()
        domain = getattr(self._accounting, "_domain", None)
        if domain and hasattr(domain, "ensure_commission_expense_account"):
            return domain.ensure_commission_expense_account()
        # Fallback: try by name
        get = getattr(self._accounting, "get_account_by_name", None)
        if callable(get):
            return get("Commission Expense")
        return None

    def _post_gl_for_entry(
        self,
        entry: CommissionAccrualEntry,
        *,
        reverse: bool,
        description: str,
        location_id: str,
        location_name: str,
    ) -> None:
        amount = round(float(entry.amount or 0), 2)
        if amount <= 0:
            return
        payable = self._payable_account(entry.party_type, entry.party_id)
        expense = self._expense_account()
        if not payable or not expense:
            logger.warning(
                "Skipping commission GL: payable=%s expense=%s party=%s/%s",
                bool(payable),
                bool(expense),
                entry.party_type,
                entry.party_id,
            )
            return
        if reverse:
            lines = [
                {
                    "account_id": payable.id,
                    "account_name": payable.account_name,
                    "debit_amount": amount,
                    "credit_amount": 0,
                    "description": "Commission payable reversed",
                },
                {
                    "account_id": expense.id,
                    "account_name": expense.account_name,
                    "debit_amount": 0,
                    "credit_amount": amount,
                    "description": "Commission expense reversed",
                },
            ]
        else:
            lines = [
                {
                    "account_id": expense.id,
                    "account_name": expense.account_name,
                    "debit_amount": amount,
                    "credit_amount": 0,
                    "description": "Commission expense",
                },
                {
                    "account_id": payable.id,
                    "account_name": payable.account_name,
                    "debit_amount": 0,
                    "credit_amount": amount,
                    "description": "Commission payable",
                },
            ]
        try:
            voucher = self._accounting.create_journal_entry(
                description=description,
                lines=lines,
                voucher_date=entry.event_date or date.today(),
                location_id=location_id,
                location_name=location_name,
            )
            entry.gl_voucher_id = voucher.id
            entry.updated_at = utc_now()
            self._accrual_repo.save(entry)
        except Exception:
            logger.exception(
                "Failed to post commission GL for accrual %s", entry.id
            )

    def mark_paid(
        self, entry_ids: Sequence[str], paid_voucher_id: str
    ) -> int:
        return int(
            self._accrual_repo.mark_paid(list(entry_ids), paid_voucher_id) or 0
        )

    def list_unpaid_for_party(
        self,
        party_type: str,
        party_id: str,
        *,
        period_key: Optional[str] = None,
    ) -> List[CommissionAccrualEntry]:
        return self._accrual_repo.list_unpaid(
            party_type, party_id, period_key=period_key
        )

    def metrics_for_party(self, party_type: str, party_id: str) -> dict:
        entries = self._accrual_repo.list_by_party(party_type, party_id)
        accrued = 0.0
        reversed_amt = 0.0
        paid = 0.0
        for e in entries:
            if e.reversal_of_id or e.status == STATUS_REVERSED:
                reversed_amt = round(reversed_amt + float(e.amount), 2)
            elif e.status == "paid":
                paid = round(paid + float(e.amount), 2)
                accrued = round(accrued + float(e.amount), 2)
            elif e.status == STATUS_ACCRUED:
                accrued = round(accrued + float(e.amount), 2)
        net = round(accrued - reversed_amt, 2)
        outstanding = round(max(net - paid, 0.0), 2)
        return {
            "commission_accrued": accrued,
            "commission_reversed": reversed_amt,
            "commission_net": net,
            "commission_paid": paid,
            "commission_outstanding": outstanding,
            "commission_unpaid": outstanding,
        }

    def accrue_from_invoice_voucher(
        self,
        voucher,
        *,
        sales_lines: Optional[list] = None,
        commission_agent_ids: Optional[list] = None,
        sales_rep_ids: Optional[list] = None,
        amount_received: float = 0.0,
        location_id: str = "",
        location_name: str = "",
    ) -> List[CommissionAccrualEntry]:
        """Convenience: accrue sales (and cash-on-invoice collection) for a voucher."""
        from vaybooks.bms.domain.sales.line_items import parse_sales_line_items_note

        tags = parse_commission_tags(getattr(voucher, "description", "") or "")
        agent_ids = list(commission_agent_ids or tags["commission_agent_ids"])
        rep_ids = list(sales_rep_ids or tags["sales_rep_ids"])
        if not agent_ids and not rep_ids:
            return []
        if sales_lines is None:
            sales_lines, _, _ = parse_sales_line_items_note(
                getattr(voucher, "description", "") or ""
            )
        customer_id = ""
        for line in getattr(voucher, "lines", []) or []:
            # customer line is usually the AR debit
            account = None
            if hasattr(self._accounting, "get_account"):
                account = self._accounting.get_account(line.account_id)
            if account and getattr(account, "linked_customer_id", None):
                customer_id = account.linked_customer_id
                break
        v_date = voucher.voucher_date
        if hasattr(v_date, "date"):
            v_date = v_date.date()
        amount_received = round(float(amount_received or 0), 2)
        taxable = round(
            sum(float(r.get("taxable_amount") or 0) for r in (sales_lines or [])), 2
        )
        grand = round(
            sum(float(r.get("line_total") or 0) for r in (sales_lines or [])), 2
        )
        is_fully_paid = amount_received + 0.01 >= grand if grand > 0 else False
        ctx = self.build_invoice_context(
            invoice_id=voucher.id,
            customer_id=customer_id,
            invoice_date=v_date or date.today(),
            sales_lines=sales_lines or [],
            commission_agent_ids=agent_ids,
            sales_rep_ids=rep_ids,
            is_fully_paid=is_fully_paid,
            amount_collected_on_invoice=amount_received,
        )
        saved = self.accrue_on_invoice(
            ctx, location_id=location_id, location_name=location_name
        )
        if amount_received > 0:
            # Cash portion triggers collection rules immediately.
            saved.extend(
                self.accrue_on_collection(
                    ctx,
                    payment_amount=min(amount_received, taxable or amount_received),
                    payment_date=v_date or date.today(),
                    receipt_id=voucher.id,
                    location_id=location_id,
                    location_name=location_name,
                )
            )
        return saved

    def accrue_from_receipt_allocations(
        self,
        receipt_voucher,
        allocations: Sequence[dict],
        *,
        get_invoice,
        location_id: str = "",
        location_name: str = "",
        override_agent_ids: Optional[list] = None,
        override_sales_rep_ids: Optional[list] = None,
    ) -> List[CommissionAccrualEntry]:
        """Accrue collection commission for each invoice allocation on a receipt."""
        from vaybooks.bms.domain.sales.line_items import parse_sales_line_items_note

        saved: List[CommissionAccrualEntry] = []
        r_date = receipt_voucher.voucher_date
        if hasattr(r_date, "date"):
            r_date = r_date.date()
        for alloc in allocations or []:
            invoice_id = str(alloc.get("invoice_id") or "").strip()
            amount = round(float(alloc.get("amount") or 0), 2)
            if not invoice_id or amount <= 0:
                continue
            invoice = get_invoice(invoice_id)
            if not invoice:
                continue
            tags = parse_commission_tags(getattr(invoice, "description", "") or "")
            agent_ids = list(override_agent_ids or tags["commission_agent_ids"])
            rep_ids = list(override_sales_rep_ids or tags["sales_rep_ids"])
            if not agent_ids and not rep_ids:
                continue
            sales_lines, _, _ = parse_sales_line_items_note(
                getattr(invoice, "description", "") or ""
            )
            customer_id = ""
            for line in getattr(invoice, "lines", []) or []:
                account = None
                if hasattr(self._accounting, "get_account"):
                    account = self._accounting.get_account(line.account_id)
                if account and getattr(account, "linked_customer_id", None):
                    customer_id = account.linked_customer_id
                    break
            inv_date = invoice.voucher_date
            if hasattr(inv_date, "date"):
                inv_date = inv_date.date()
            ctx = self.build_invoice_context(
                invoice_id=invoice.id,
                customer_id=customer_id,
                invoice_date=inv_date or date.today(),
                sales_lines=sales_lines,
                commission_agent_ids=agent_ids,
                sales_rep_ids=rep_ids,
                is_fully_paid=False,
                amount_collected_on_invoice=amount,
            )
            saved.extend(
                self.accrue_on_collection(
                    ctx,
                    payment_amount=amount,
                    payment_date=r_date or date.today(),
                    receipt_id=receipt_voucher.id,
                    location_id=location_id,
                    location_name=location_name,
                )
            )
        return saved
