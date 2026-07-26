"""CRM report engine covering all 34 named reports."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional

from vaybooks.bms.domain.crm.enums import (
    CRM_REPORT_DEFINITIONS,
    ActivityStatus,
    EnquiryStatus,
    LeadStatus,
)
from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class CrmReportFilters:
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    branch: str = ""
    assigned_user_id: str = ""
    customer_id: str = ""
    area: str = ""
    activity_type: str = ""
    inactivity_days: int = 30
    high_value_threshold: float = 50000.0


@dataclass
class CrmReportResult:
    report_id: str
    title: str
    category: str
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    empty: bool = True


class CrmReportService:
    """Generic report runner with one method per named report (1–34)."""

    def __init__(
        self,
        lead_repo,
        enquiry_repo=None,
        activity_repo=None,
        customer_service=None,
        settings_repo=None,
        sales_service=None,
        accounting_service=None,
    ):
        self._leads = lead_repo
        self._enquiries = enquiry_repo
        self._activities = activity_repo
        self._customers = customer_service
        self._settings = settings_repo
        self._sales = sales_service
        self._accounting = accounting_service
        self._registry: Dict[str, Callable[[CrmReportFilters], CrmReportResult]] = {
            rid: getattr(self, f"report_{rid}")
            for rid, _title, _cat in CRM_REPORT_DEFINITIONS
            if hasattr(self, f"report_{rid}")
        }

    def list_reports(self) -> List[Dict[str, str]]:
        return [
            {"id": rid, "title": title, "category": cat}
            for rid, title, cat in CRM_REPORT_DEFINITIONS
        ]

    def run_report(
        self, report_id: str, filters: Optional[CrmReportFilters] = None
    ) -> CrmReportResult:
        filters = filters or CrmReportFilters()
        meta = {rid: (title, cat) for rid, title, cat in CRM_REPORT_DEFINITIONS}
        if report_id not in meta:
            raise ValueError(f"Unknown CRM report: {report_id}")
        fn = self._registry.get(report_id)
        if not fn:
            title, cat = meta[report_id]
            return CrmReportResult(
                report_id=report_id, title=title, category=cat, empty=True
            )
        result = fn(filters)
        result.empty = len(result.rows) == 0
        return result

    def run_all(
        self, filters: Optional[CrmReportFilters] = None
    ) -> List[CrmReportResult]:
        return [self.run_report(rid, filters) for rid, _, _ in CRM_REPORT_DEFINITIONS]

    # --- helpers ---

    def _meta(self, report_id: str) -> tuple[str, str]:
        for rid, title, cat in CRM_REPORT_DEFINITIONS:
            if rid == report_id:
                return title, cat
        return report_id, ""

    @staticmethod
    def _as_datetime(value, *, end: bool = False) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.max if end else time.min)
        return None

    def _result(
        self, report_id: str, columns: List[str], rows: List[Dict[str, Any]], **summary
    ) -> CrmReportResult:
        title, cat = self._meta(report_id)
        return CrmReportResult(
            report_id=report_id,
            title=title,
            category=cat,
            columns=columns,
            rows=rows,
            summary=summary,
            empty=not rows,
        )

    def _leads_filtered(self, f: CrmReportFilters) -> list:
        leads = self._leads.list(
            assigned_user_id=f.assigned_user_id or None,
            branch=f.branch or None,
            limit=5000,
        )
        if f.area:
            leads = [l for l in leads if (l.area or "").lower() == f.area.lower()]
        if f.date_from:
            start = self._as_datetime(f.date_from)
            leads = [l for l in leads if l.created_at and start and l.created_at >= start]
        if f.date_to:
            end = self._as_datetime(f.date_to, end=True)
            leads = [l for l in leads if l.created_at and end and l.created_at <= end]
        return leads

    def _activities_filtered(self, f: CrmReportFilters) -> list:
        if not self._activities:
            return []
        acts = self._activities.list(
            assigned_user_id=f.assigned_user_id or None,
            customer_id=f.customer_id or None,
            activity_type=f.activity_type or None,
            branch=f.branch or None,
            limit=5000,
        )
        if f.date_from:
            start = self._as_datetime(f.date_from)
            acts = [
                a
                for a in acts
                if (a.activity_at or a.scheduled_at or a.created_at)
                and start
                and (a.activity_at or a.scheduled_at or a.created_at) >= start
            ]
        if f.date_to:
            end = self._as_datetime(f.date_to, end=True)
            acts = [
                a
                for a in acts
                if (a.activity_at or a.scheduled_at or a.created_at)
                and end
                and (a.activity_at or a.scheduled_at or a.created_at) <= end
            ]
        return acts

    def _enquiries_filtered(self, f: CrmReportFilters) -> list:
        if not self._enquiries:
            return []
        enquiries = self._enquiries.list(
            assigned_user_id=f.assigned_user_id or None,
            customer_id=f.customer_id or None,
            branch=f.branch or None,
            limit=5000,
        )
        if f.date_from:
            start = self._as_datetime(f.date_from)
            enquiries = [
                enquiry
                for enquiry in enquiries
                if enquiry.enquiry_date and start and enquiry.enquiry_date >= start
            ]
        if f.date_to:
            end = self._as_datetime(f.date_to, end=True)
            enquiries = [
                enquiry
                for enquiry in enquiries
                if enquiry.enquiry_date and end and enquiry.enquiry_date <= end
            ]
        return enquiries

    def _customer_list(self, f: Optional[CrmReportFilters] = None) -> list:
        if not self._customers:
            return []
        customers = list(self._customers.list_all_customers())
        if f is None:
            return customers
        if f.customer_id:
            customers = [customer for customer in customers if customer.id == f.customer_id]
        if f.assigned_user_id:
            customers = [
                customer
                for customer in customers
                if getattr(customer, "assigned_user_id", "") == f.assigned_user_id
            ]
        if f.area:
            needle = f.area.strip().casefold()
            customers = [
                customer
                for customer in customers
                if needle
                in (
                    getattr(customer, "area", "")
                    or getattr(customer, "city", "")
                    or ""
                ).casefold()
            ]
        return customers

    def _customer_map(self, f: Optional[CrmReportFilters] = None) -> Dict[str, Any]:
        return {c.id: c for c in self._customer_list(f)}

    def _balances(self) -> Dict[str, float]:
        if not self._accounting:
            return {}
        loader = getattr(self._accounting, "customer_balances_by_customer", None)
        if not callable(loader):
            return {}
        try:
            return {str(k): float(v or 0) for k, v in (loader() or {}).items()}
        except Exception:
            return {}

    def _sales_orders(self, f: CrmReportFilters) -> list:
        if not self._sales:
            return []
        loader = getattr(self._sales, "list_sales_orders", None)
        if not callable(loader):
            return []
        try:
            orders = list(loader() or [])
        except Exception:
            return []
        if f.customer_id:
            orders = [o for o in orders if o.customer_id == f.customer_id]
        if f.assigned_user_id or f.area:
            allowed = set(self._customer_map(f))
            orders = [order for order in orders if order.customer_id in allowed]
        if f.date_from:
            start_dt = self._as_datetime(f.date_from)
            start = start_dt.date() if start_dt else date.min
            orders = [o for o in orders if o.order_date and o.order_date >= start]
        if f.date_to:
            end_dt = self._as_datetime(f.date_to, end=True)
            end = end_dt.date() if end_dt else date.max
            orders = [o for o in orders if o.order_date and o.order_date <= end]
        if f.branch:
            orders = [
                o
                for o in orders
                if (getattr(o, "branch", "") or getattr(o, "location_name", ""))
                == f.branch
            ]
        return orders

    @staticmethod
    def _amount_from_activity(activity) -> float:
        marker = "Amount:"
        notes = activity.notes or ""
        if marker not in notes:
            return 0.0
        try:
            return float(notes.split(marker, 1)[1].split(";", 1)[0].strip())
        except (TypeError, ValueError):
            return 0.0

    # --- engagement ---

    def report_customers_with_orders(self, f: CrmReportFilters) -> CrmReportResult:
        customers = self._customer_map(f)
        grouped: Dict[str, Dict[str, Any]] = {}
        for order in self._sales_orders(f):
            customer = customers.get(order.customer_id)
            row = grouped.setdefault(
                order.customer_id,
                {
                    "customer_id": order.customer_id,
                    "customer_name": order.customer_name
                    or getattr(customer, "customer_name", ""),
                    "order_count": 0,
                    "quantity": 0.0,
                    "sales_value": 0.0,
                    "last_order_date": None,
                    "assigned_user": getattr(customer, "assigned_user_name", ""),
                },
            )
            row["order_count"] += 1
            row["quantity"] += sum(float(line.qty_ordered or 0) for line in order.lines)
            row["sales_value"] += float(order.total_amount or 0)
            if not row["last_order_date"] or order.order_date > row["last_order_date"]:
                row["last_order_date"] = order.order_date
        rows = list(grouped.values())
        return self._result(
            "customers_with_orders",
            [
                "customer_id",
                "customer_name",
                "order_count",
                "quantity",
                "sales_value",
                "last_order_date",
                "assigned_user",
            ],
            rows,
            count=len(rows),
        )

    def report_customers_with_payments(self, f: CrmReportFilters) -> CrmReportResult:
        acts = [
            a
            for a in self._activities_filtered(f)
            if a.activity_type == "Payment Received" and a.customer_id
        ]
        by_cust: Dict[str, Dict[str, Any]] = {}
        balances = self._balances()
        for a in acts:
            row = by_cust.setdefault(
                a.customer_id,
                {
                    "customer_id": a.customer_id,
                    "customer_name": a.party_name,
                    "payment_count": 0,
                    "amount_received": 0.0,
                    "last_payment_at": None,
                    "outstanding_balance": balances.get(a.customer_id, 0.0),
                },
            )
            row["payment_count"] += 1
            row["amount_received"] += self._amount_from_activity(a)
            if a.activity_at and (
                not row["last_payment_at"] or a.activity_at > row["last_payment_at"]
            ):
                row["last_payment_at"] = a.activity_at
        rows = list(by_cust.values())
        return self._result(
            "customers_with_payments",
            [
                "customer_id",
                "customer_name",
                "amount_received",
                "payment_count",
                "last_payment_at",
                "outstanding_balance",
            ],
            rows,
            count=len(rows),
        )

    def report_customers_without_activity(self, f: CrmReportFilters) -> CrmReportResult:
        cutoff = utc_now() - timedelta(days=f.inactivity_days or 30)
        acts = (
            self._activities_filtered(
                CrmReportFilters(
                    branch=f.branch,
                    assigned_user_id=f.assigned_user_id,
                    customer_id=f.customer_id,
                )
            )
            if self._activities
            else []
        )
        recent = {
            a.customer_id
            for a in acts
            if a.customer_id and a.activity_at and a.activity_at >= cutoff
        }
        rows = []
        for c in self._customer_list(f):
            if f.assigned_user_id and getattr(c, "assigned_user_id", "") != f.assigned_user_id:
                continue
            if c.id not in recent:
                rows.append(
                    {
                        "customer_id": c.id,
                        "customer_name": c.customer_name,
                        "assigned_user": getattr(c, "assigned_user_name", ""),
                    }
                )
        return self._result(
            "customers_without_activity",
            ["customer_id", "customer_name", "assigned_user"],
            rows,
            inactivity_days=f.inactivity_days,
        )

    def report_customers_called(self, f: CrmReportFilters) -> CrmReportResult:
        rows = [
            {
                "customer_id": a.customer_id,
                "customer_name": a.party_name,
                "outcome": a.outcome,
                "representative": a.assigned_user_name,
                "call_at": a.activity_at,
                "next_follow_up_at": a.next_follow_up_at,
            }
            for a in self._activities_filtered(f)
            if a.activity_type == "Called" and a.customer_id
        ]
        return self._result(
            "customers_called",
            [
                "customer_id",
                "customer_name",
                "outcome",
                "representative",
                "call_at",
                "next_follow_up_at",
            ],
            rows,
        )

    def report_customers_visited(self, f: CrmReportFilters) -> CrmReportResult:
        rows = [
            {
                "customer_id": a.customer_id,
                "customer_name": a.party_name,
                "location": a.location,
                "outcome": a.outcome,
                "representative": a.assigned_user_name,
                "visit_at": a.activity_at,
                "next_action": a.next_action,
            }
            for a in self._activities_filtered(f)
            if "visit" in (a.activity_type or "").lower() and a.customer_id
        ]
        return self._result(
            "customers_visited",
            [
                "customer_id",
                "customer_name",
                "location",
                "outcome",
                "representative",
                "visit_at",
                "next_action",
            ],
            rows,
        )

    def report_customers_not_ordered_recently(self, f: CrmReportFilters) -> CrmReportResult:
        cutoff = utc_now() - timedelta(days=f.inactivity_days or 30)
        base_filters = CrmReportFilters(
            branch=f.branch, customer_id=f.customer_id
        )
        customers = self._customer_map(f)
        last_order: Dict[str, Any] = {}
        for order in self._sales_orders(base_filters):
            previous = last_order.get(order.customer_id)
            if previous is None or order.order_date > previous.order_date:
                last_order[order.customer_id] = order
        rows = [
            {
                "customer_id": cid,
                "customer_name": getattr(customers.get(cid), "customer_name", ""),
                "last_order_date": order.order_date,
                "days_since": (utc_now().date() - order.order_date).days,
                "assigned_user": getattr(
                    customers.get(cid), "assigned_user_name", ""
                ),
            }
            for cid, order in last_order.items()
            if order.order_date < cutoff.date()
        ]
        return self._result(
            "customers_not_ordered_recently",
            [
                "customer_id",
                "customer_name",
                "last_order_date",
                "days_since",
                "assigned_user",
            ],
            rows,
        )

    def report_customers_never_contacted(self, f: CrmReportFilters) -> CrmReportResult:
        acts = (
            self._activities_filtered(
                CrmReportFilters(
                    branch=f.branch,
                    assigned_user_id=f.assigned_user_id,
                    customer_id=f.customer_id,
                )
            )
            if self._activities
            else []
        )
        contacted = {
            a.customer_id
            for a in acts
            if a.customer_id and a.origin != "Automatic"
        }
        # Also treat manual activity types
        manual_types = {
            "Called",
            "Sales Representative Visit",
            "Meeting",
            "WhatsApp Message",
            "Email",
            "General Follow-up",
            "Contacted for Order",
            "Contacted for Credit",
        }
        contacted |= {
            a.customer_id
            for a in acts
            if a.customer_id and a.activity_type in manual_types
        }
        rows = [
            {
                "customer_id": c.id,
                "customer_name": c.customer_name,
                "assigned_user": getattr(c, "assigned_user_name", ""),
            }
            for c in self._customer_list(f)
            if c.id not in contacted
        ]
        return self._result(
            "customers_never_contacted",
            ["customer_id", "customer_name", "assigned_user"],
            rows,
        )

    def report_customers_requiring_follow_up(self, f: CrmReportFilters) -> CrmReportResult:
        now = utc_now()
        rows = [
            {
                "customer_id": a.customer_id,
                "party_name": a.party_name,
                "activity_type": a.activity_type,
                "scheduled_at": a.scheduled_at,
                "assigned_user": a.assigned_user_name,
                "overdue": bool(a.scheduled_at and a.scheduled_at < now),
            }
            for a in self._activities_filtered(f)
            if a.status in {ActivityStatus.SCHEDULED.value, ActivityStatus.IN_PROGRESS.value}
            and a.scheduled_at
            and a.customer_id
        ]
        return self._result(
            "customers_requiring_follow_up",
            [
                "customer_id",
                "party_name",
                "activity_type",
                "scheduled_at",
                "assigned_user",
                "overdue",
            ],
            rows,
        )

    # --- conversion ---

    def report_lead_conversion_funnel(self, f: CrmReportFilters) -> CrmReportResult:
        leads = self._leads_filtered(f)
        counts = Counter(l.status for l in leads)
        order = [
            LeadStatus.NEW.value,
            LeadStatus.CONTACTED.value,
            LeadStatus.QUALIFIED.value,
            LeadStatus.INTERESTED.value,
            LeadStatus.CONVERTED.value,
            LeadStatus.LOST.value,
        ]
        rows = [{"status": s, "count": counts.get(s, 0)} for s in order]
        return self._result(
            "lead_conversion_funnel", ["status", "count"], rows, total=len(leads)
        )

    def report_lead_conversion_by_source(self, f: CrmReportFilters) -> CrmReportResult:
        leads = self._leads_filtered(f)
        by_source: Dict[str, Dict[str, Any]] = {}
        for lead in leads:
            src = lead.source or "Unknown"
            row = by_source.setdefault(
                src, {"source": src, "leads": 0, "converted": 0, "estimated_value": 0.0}
            )
            row["leads"] += 1
            if lead.status == LeadStatus.CONVERTED.value:
                row["converted"] += 1
                row["estimated_value"] += float(lead.estimated_value or 0)
        rows = []
        for row in by_source.values():
            row["conversion_pct"] = (
                round(100.0 * row["converted"] / row["leads"], 1) if row["leads"] else 0
            )
            rows.append(row)
        return self._result(
            "lead_conversion_by_source",
            ["source", "leads", "converted", "conversion_pct", "estimated_value"],
            rows,
        )

    def report_lead_conversion_by_sales_representative(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        leads = self._leads_filtered(f)
        by_rep: Dict[str, Dict[str, Any]] = {}
        for lead in leads:
            key = lead.assigned_user_id or "unassigned"
            row = by_rep.setdefault(
                key,
                {
                    "assigned_user_id": lead.assigned_user_id,
                    "assigned_user_name": lead.assigned_user_name or "Unassigned",
                    "assigned": 0,
                    "converted": 0,
                    "lost": 0,
                    "estimated_value": 0.0,
                },
            )
            row["assigned"] += 1
            if lead.status == LeadStatus.CONVERTED.value:
                row["converted"] += 1
                row["estimated_value"] += float(lead.estimated_value or 0)
            if lead.status == LeadStatus.LOST.value:
                row["lost"] += 1
        rows = []
        for row in by_rep.values():
            row["conversion_pct"] = (
                round(100.0 * row["converted"] / row["assigned"], 1)
                if row["assigned"]
                else 0
            )
            rows.append(row)
        return self._result(
            "lead_conversion_by_sales_representative",
            [
                "assigned_user_id",
                "assigned_user_name",
                "assigned",
                "converted",
                "lost",
                "conversion_pct",
                "estimated_value",
            ],
            rows,
        )

    def report_enquiry_conversion_report(self, f: CrmReportFilters) -> CrmReportResult:
        enquiries = self._enquiries_filtered(f)
        created = len(enquiries)
        quoted = sum(1 for e in enquiries if e.quotation_id)
        won = sum(1 for e in enquiries if e.status == EnquiryStatus.WON.value)
        ordered = sum(1 for e in enquiries if e.sales_order_id)
        rows = [
            {
                "enquiries_created": created,
                "quotations": quoted,
                "won": won,
                "orders": ordered,
                "conversion_pct": round(100.0 * won / created, 1) if created else 0,
            }
        ]
        return self._result(
            "enquiry_conversion_report",
            ["enquiries_created", "quotations", "won", "orders", "conversion_pct"],
            rows,
        )

    def report_lost_leads_and_enquiries(self, f: CrmReportFilters) -> CrmReportResult:
        rows = []
        for lead in self._leads_filtered(f):
            if lead.status == LeadStatus.LOST.value:
                rows.append(
                    {
                        "record_type": "lead",
                        "id": lead.id,
                        "name": lead.name,
                        "reason": lead.lost_reason,
                        "source": lead.source,
                        "assigned_user": lead.assigned_user_name,
                        "estimated_value": lead.estimated_value,
                    }
                )
        for enq in self._enquiries_filtered(f):
            if enq.status == EnquiryStatus.LOST.value:
                rows.append(
                    {
                        "record_type": "enquiry",
                        "id": enq.id,
                        "name": enq.party_name,
                        "reason": enq.lost_reason,
                        "source": enq.source,
                        "assigned_user": enq.assigned_user_name,
                        "estimated_value": enq.estimated_value,
                    }
                )
        return self._result(
            "lost_leads_and_enquiries",
            [
                "record_type",
                "id",
                "name",
                "reason",
                "source",
                "assigned_user",
                "estimated_value",
            ],
            rows,
        )

    def report_order_generated_after_follow_up(self, f: CrmReportFilters) -> CrmReportResult:
        acts = self._activities_filtered(f)
        followups = [
            a
            for a in acts
            if a.activity_type
            in {"Called", "Sales Representative Visit", "Contacted for Order", "General Follow-up"}
            and a.customer_id
        ]
        orders = [a for a in acts if a.activity_type == "Order Placed" and a.customer_id]
        rows = []
        for order in orders:
            prior = [
                fu
                for fu in followups
                if fu.customer_id == order.customer_id
                and fu.activity_at
                and order.activity_at
                and fu.activity_at < order.activity_at
            ]
            if prior:
                latest = max(prior, key=lambda x: x.activity_at or utc_now())
                rows.append(
                    {
                        "customer_id": order.customer_id,
                        "order_activity_id": order.id,
                        "follow_up_type": latest.activity_type,
                        "follow_up_at": latest.activity_at,
                        "order_at": order.activity_at,
                    }
                )
        return self._result(
            "order_generated_after_follow_up",
            [
                "customer_id",
                "order_activity_id",
                "follow_up_type",
                "follow_up_at",
                "order_at",
            ],
            rows,
        )

    def report_dormant_customer_reactivation(self, f: CrmReportFilters) -> CrmReportResult:
        gap_days = f.inactivity_days or 30
        orders_by_customer: Dict[str, list] = defaultdict(list)
        for order in self._sales_orders(
            CrmReportFilters(
                branch=f.branch,
                customer_id=f.customer_id,
                assigned_user_id=f.assigned_user_id,
                area=f.area,
            )
        ):
            orders_by_customer[order.customer_id].append(order)
        activities = self._activities_filtered(f)
        rows = []
        for customer_id, orders in orders_by_customer.items():
            orders.sort(key=lambda order: order.order_date)
            for previous, resumed in zip(orders, orders[1:]):
                gap = (resumed.order_date - previous.order_date).days
                if gap < gap_days:
                    continue
                resumed_at = datetime.combine(resumed.order_date, datetime.min.time())
                prior = [
                    activity
                    for activity in activities
                    if activity.customer_id == customer_id
                    and activity.origin != "Automatic"
                    and activity.activity_at
                    and activity.activity_at <= resumed_at
                ]
                preceding = max(
                    prior, key=lambda activity: activity.activity_at, default=None
                )
                rows.append(
                    {
                        "customer_id": customer_id,
                        "previous_order_date": previous.order_date,
                        "reactivated_order_date": resumed.order_date,
                        "inactive_days": gap,
                        "preceding_activity": getattr(
                            preceding, "activity_type", ""
                        ),
                        "preceding_activity_at": getattr(
                            preceding, "activity_at", None
                        ),
                    }
                )
        return self._result(
            "dormant_customer_reactivation",
            [
                "customer_id",
                "previous_order_date",
                "reactivated_order_date",
                "inactive_days",
                "preceding_activity",
                "preceding_activity_at",
            ],
            rows,
        )

    def report_customers_with_declining_order_frequency(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        window_days = f.inactivity_days or 30
        today = utc_now().date()
        current_start = today - timedelta(days=window_days)
        previous_start = current_start - timedelta(days=window_days)
        counts: Dict[str, Counter] = defaultdict(Counter)
        for order in self._sales_orders(
            CrmReportFilters(
                branch=f.branch,
                customer_id=f.customer_id,
                assigned_user_id=f.assigned_user_id,
                area=f.area,
            )
        ):
            if current_start <= order.order_date <= today:
                counts[order.customer_id]["current"] += 1
            elif previous_start <= order.order_date < current_start:
                counts[order.customer_id]["previous"] += 1
        rows = [
            {
                "customer_id": customer_id,
                "previous_period_orders": values["previous"],
                "current_period_orders": values["current"],
                "decline": values["previous"] - values["current"],
            }
            for customer_id, values in counts.items()
            if values["previous"] > values["current"]
        ]
        return self._result(
            "customers_with_declining_order_frequency",
            [
                "customer_id",
                "previous_period_orders",
                "current_period_orders",
                "decline",
            ],
            rows,
        )

    # --- collection ---

    def report_customers_contacted_for_credit(self, f: CrmReportFilters) -> CrmReportResult:
        rows = [
            {
                "customer_id": a.customer_id,
                "customer_name": a.party_name,
                "representative": a.assigned_user_name,
                "outcome": a.outcome,
                "promised_amount": a.promised_amount,
                "promised_date": a.promised_date,
                "next_follow_up_at": a.next_follow_up_at,
            }
            for a in self._activities_filtered(f)
            if a.activity_type == "Contacted for Credit"
        ]
        return self._result(
            "customers_contacted_for_credit",
            [
                "customer_id",
                "customer_name",
                "representative",
                "outcome",
                "promised_amount",
                "promised_date",
                "next_follow_up_at",
            ],
            rows,
        )

    def report_payment_promise_report(self, f: CrmReportFilters) -> CrmReportResult:
        activities = self._activities_filtered(f)
        payments = [
            activity
            for activity in activities
            if activity.activity_type == "Payment Received"
        ]
        rows = []
        for activity in activities:
            if activity.outcome != "Payment Promised" and not activity.promised_amount:
                continue
            actual = sum(
                self._amount_from_activity(payment)
                for payment in payments
                if payment.customer_id == activity.customer_id
                and payment.activity_at
                and activity.activity_at
                and payment.activity_at >= activity.activity_at
            )
            promised = float(activity.promised_amount or 0)
            pending = max(promised - actual, 0.0)
            rows.append(
                {
                    "customer_id": activity.customer_id,
                    "customer_name": activity.party_name,
                    "promised_amount": promised,
                    "promised_date": activity.promised_date,
                    "actual_payment": actual,
                    "pending_amount": pending,
                    "promise_status": (
                        "Fulfilled"
                        if promised and pending <= 0
                        else "Partially Paid"
                        if actual
                        else "Overdue"
                        if activity.promised_date
                        and activity.promised_date < utc_now()
                        else "Pending"
                    ),
                    "representative": activity.assigned_user_name,
                }
            )
        return self._result(
            "payment_promise_report",
            [
                "customer_id",
                "customer_name",
                "promised_amount",
                "promised_date",
                "actual_payment",
                "pending_amount",
                "promise_status",
                "representative",
            ],
            rows,
        )

    def report_payments_received_after_follow_up(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        acts = self._activities_filtered(f)
        credits = [
            a
            for a in acts
            if a.activity_type == "Contacted for Credit" and a.customer_id
        ]
        payments = [
            a for a in acts if a.activity_type == "Payment Received" and a.customer_id
        ]
        rows = []
        for pay in payments:
            prior = [
                c
                for c in credits
                if c.customer_id == pay.customer_id
                and c.activity_at
                and pay.activity_at
                and c.activity_at < pay.activity_at
            ]
            if prior:
                latest = max(prior, key=lambda x: x.activity_at or utc_now())
                rows.append(
                    {
                        "customer_id": pay.customer_id,
                        "follow_up_at": latest.activity_at,
                        "payment_at": pay.activity_at,
                        "payment_activity_id": pay.id,
                    }
                )
        return self._result(
            "payments_received_after_follow_up",
            ["customer_id", "follow_up_at", "payment_at", "payment_activity_id"],
            rows,
        )

    def report_overdue_collection_follow_ups(self, f: CrmReportFilters) -> CrmReportResult:
        now = utc_now()
        balances = self._balances()
        rows = [
            {
                "customer_id": a.customer_id,
                "party_name": a.party_name,
                "scheduled_at": a.scheduled_at,
                "days_overdue": (now - a.scheduled_at).days if a.scheduled_at else 0,
                "assigned_user": a.assigned_user_name,
                "priority": a.priority,
                "outstanding_balance": balances.get(a.customer_id, 0.0),
            }
            for a in self._activities_filtered(f)
            if a.activity_type in {"Contacted for Credit", "Payment Reminder", "General Follow-up"}
            and a.status in {ActivityStatus.SCHEDULED.value, ActivityStatus.IN_PROGRESS.value}
            and a.scheduled_at
            and a.scheduled_at < now
        ]
        return self._result(
            "overdue_collection_follow_ups",
            [
                "customer_id",
                "party_name",
                "scheduled_at",
                "days_overdue",
                "assigned_user",
                "priority",
                "outstanding_balance",
            ],
            rows,
        )

    # --- rep ---

    def report_sales_representative_activity_summary(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        acts = self._activities_filtered(f)
        by_rep: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "assigned_user_id": "",
                "assigned_user_name": "",
                "calls": 0,
                "visits": 0,
                "completed": 0,
                "missed": 0,
                "follow_ups": 0,
                "leads": 0,
                "enquiries": 0,
                "conversions": 0,
                "orders": 0,
                "collections": 0.0,
            }
        )
        for a in acts:
            key = a.assigned_user_id or "unassigned"
            row = by_rep[key]
            row["assigned_user_id"] = a.assigned_user_id
            row["assigned_user_name"] = a.assigned_user_name or "Unassigned"
            if a.activity_type == "Called":
                row["calls"] += 1
            if "visit" in (a.activity_type or "").lower():
                row["visits"] += 1
            if a.status == ActivityStatus.COMPLETED.value:
                row["completed"] += 1
            if a.status == ActivityStatus.MISSED.value:
                row["missed"] += 1
            if "follow" in (a.activity_type or "").lower():
                row["follow_ups"] += 1
            if a.activity_type == "Order Placed":
                row["orders"] += 1
            if a.activity_type == "Payment Received":
                row["collections"] += self._amount_from_activity(a)
        for lead in self._leads_filtered(f):
            key = lead.assigned_user_id or "unassigned"
            row = by_rep[key]
            row["assigned_user_id"] = lead.assigned_user_id
            row["assigned_user_name"] = lead.assigned_user_name or "Unassigned"
            row["leads"] += 1
            if lead.status == LeadStatus.CONVERTED.value:
                row["conversions"] += 1
        for enquiry in self._enquiries_filtered(f):
            key = enquiry.assigned_user_id or "unassigned"
            row = by_rep[key]
            row["assigned_user_id"] = enquiry.assigned_user_id
            row["assigned_user_name"] = enquiry.assigned_user_name or "Unassigned"
            row["enquiries"] += 1
        rows = list(by_rep.values())
        return self._result(
            "sales_representative_activity_summary",
            [
                "assigned_user_id",
                "assigned_user_name",
                "calls",
                "visits",
                "completed",
                "missed",
                "follow_ups",
                "leads",
                "enquiries",
                "conversions",
                "orders",
                "collections",
            ],
            rows,
        )

    def report_scheduled_vs_completed_activities(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        acts = self._activities_filtered(f)
        by_rep: Dict[str, Counter] = defaultdict(Counter)
        names: Dict[str, str] = {}
        for a in acts:
            key = a.assigned_user_id or "unassigned"
            names[key] = a.assigned_user_name or "Unassigned"
            by_rep[key][a.status] += 1
        rows = [
            {
                "assigned_user_id": key,
                "assigned_user_name": names[key],
                "scheduled": counts.get(ActivityStatus.SCHEDULED.value, 0),
                "completed": counts.get(ActivityStatus.COMPLETED.value, 0),
                "cancelled": counts.get(ActivityStatus.CANCELLED.value, 0),
                "missed": counts.get(ActivityStatus.MISSED.value, 0),
                "overdue": sum(
                    1
                    for activity in acts
                    if (activity.assigned_user_id or "unassigned") == key
                    and activity.status
                    in {
                        ActivityStatus.SCHEDULED.value,
                        ActivityStatus.IN_PROGRESS.value,
                    }
                    and activity.scheduled_at
                    and activity.scheduled_at < utc_now()
                ),
            }
            for key, counts in by_rep.items()
        ]
        return self._result(
            "scheduled_vs_completed_activities",
            [
                "assigned_user_id",
                "assigned_user_name",
                "scheduled",
                "completed",
                "cancelled",
                "missed",
                "overdue",
            ],
            rows,
        )

    def report_sales_representative_visit_productivity(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        acts = self._activities_filtered(f)
        visits = [a for a in acts if "visit" in (a.activity_type or "").lower()]
        by_rep: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "assigned_user_id": "",
                "assigned_user_name": "",
                "visits": 0,
                "productive": 0,
                "orders_generated": 0,
                "payments_collected": 0.0,
            }
        )
        for a in visits:
            key = a.assigned_user_id or "unassigned"
            row = by_rep[key]
            row["assigned_user_id"] = a.assigned_user_id
            row["assigned_user_name"] = a.assigned_user_name or "Unassigned"
            row["visits"] += 1
            if a.outcome in {"Interested", "Order Expected", "Payment Promised", "Completed"}:
                row["productive"] += 1
            subsequent = [
                candidate
                for candidate in acts
                if candidate.customer_id
                and candidate.customer_id == a.customer_id
                and candidate.activity_at
                and a.activity_at
                and candidate.activity_at >= a.activity_at
            ]
            row["orders_generated"] += sum(
                1 for candidate in subsequent if candidate.activity_type == "Order Placed"
            )
            row["payments_collected"] += sum(
                self._amount_from_activity(candidate)
                for candidate in subsequent
                if candidate.activity_type == "Payment Received"
            )
        rows = list(by_rep.values())
        for row in rows:
            row["visit_to_order_pct"] = (
                round(100.0 * row.get("orders_generated", 0) / row["visits"], 1)
                if row["visits"]
                else 0.0
            )
        return self._result(
            "sales_representative_visit_productivity",
            [
                "assigned_user_id",
                "assigned_user_name",
                "visits",
                "productive",
                "orders_generated",
                "payments_collected",
                "visit_to_order_pct",
            ],
            rows,
        )

    def report_follow_up_effectiveness(self, f: CrmReportFilters) -> CrmReportResult:
        acts = self._activities_filtered(f)
        by_type: Dict[str, Counter] = defaultdict(Counter)
        for a in acts:
            if a.outcome:
                by_type[a.activity_type][a.outcome] += 1
        rows = []
        for activity_type, outcomes in by_type.items():
            for outcome, count in outcomes.items():
                rows.append(
                    {
                        "activity_type": activity_type,
                        "outcome": outcome,
                        "count": count,
                    }
                )
        return self._result(
            "follow_up_effectiveness",
            ["activity_type", "outcome", "count"],
            rows,
        )

    # --- management ---

    def report_high_value_leads_without_follow_up(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        now = utc_now()
        rows = [
            {
                "lead_id": l.id,
                "name": l.name,
                "estimated_value": l.estimated_value,
                "next_follow_up_at": l.next_follow_up_at,
                "assigned_user": l.assigned_user_name,
            }
            for l in self._leads_filtered(f)
            if float(l.estimated_value or 0) >= f.high_value_threshold
            and l.status not in {LeadStatus.CONVERTED.value, LeadStatus.LOST.value}
            and (not l.next_follow_up_at or l.next_follow_up_at < now)
        ]
        return self._result(
            "high_value_leads_without_follow_up",
            ["lead_id", "name", "estimated_value", "next_follow_up_at", "assigned_user"],
            rows,
        )

    def report_high_value_customers_not_contacted_recently(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        order_totals: Dict[str, float] = defaultdict(float)
        for order in self._sales_orders(
            CrmReportFilters(
                branch=f.branch,
                customer_id=f.customer_id,
                assigned_user_id=f.assigned_user_id,
                area=f.area,
            )
        ):
            order_totals[order.customer_id] += float(order.total_amount or 0)
        inactive = {
            row["customer_id"]: row
            for row in self.report_customers_without_activity(f).rows
        }
        rows = []
        for customer_id, total in order_totals.items():
            if total < f.high_value_threshold or customer_id not in inactive:
                continue
            row = dict(inactive[customer_id])
            row["sales_value"] = total
            rows.append(row)
        return self._result(
            "high_value_customers_not_contacted_recently",
            ["customer_id", "customer_name", "assigned_user", "sales_value"],
            rows,
        )

    def report_customers_with_outstanding_balance_and_no_collection_activity(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        cutoff = utc_now() - timedelta(days=f.inactivity_days or 30)
        credit_customers = {
            a.customer_id
            for a in self._activities_filtered(f)
            if a.activity_type in {"Contacted for Credit", "Payment Reminder"}
            and a.customer_id
            and (a.activity_at or a.scheduled_at or a.created_at) >= cutoff
        }
        balances = self._balances()
        rows = [
            {
                "customer_id": c.id,
                "customer_name": c.customer_name,
                "assigned_user": getattr(c, "assigned_user_name", ""),
                "outstanding_balance": balances.get(c.id, 0.0),
            }
            for c in self._customer_list(f)
            if balances.get(c.id, 0.0) > 0 and c.id not in credit_customers
        ]
        return self._result(
            "customers_with_outstanding_balance_and_no_collection_activity",
            [
                "customer_id",
                "customer_name",
                "assigned_user",
                "outstanding_balance",
            ],
            rows,
        )

    def report_customers_with_frequent_enquiries_but_no_orders(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        enquiries = self._enquiries_filtered(f)
        by_cust: Dict[str, int] = Counter(
            e.customer_id for e in enquiries if e.customer_id
        )
        ordered = {
            order.customer_id
            for order in self._sales_orders(
                CrmReportFilters(
                    branch=f.branch,
                    customer_id=f.customer_id,
                    assigned_user_id=f.assigned_user_id,
                    area=f.area,
                )
            )
        }
        rows = [
            {"customer_id": cid, "enquiry_count": count}
            for cid, count in by_cust.items()
            if count >= 2 and cid not in ordered
        ]
        return self._result(
            "customers_with_frequent_enquiries_but_no_orders",
            ["customer_id", "enquiry_count"],
            rows,
        )

    def report_top_areas_by_leads_orders_and_collections(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        leads = self._leads_filtered(f)
        by_area: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "area": "",
                "leads": 0,
                "orders": 0,
                "sales_value": 0.0,
                "collections": 0.0,
            }
        )
        area_by_customer: Dict[str, str] = {}
        for lead in leads:
            area = lead.area or lead.city or "Unknown"
            row = by_area[area]
            row["area"] = area
            row["leads"] += 1
            if lead.customer_id:
                area_by_customer[lead.customer_id] = area
        for order in self._sales_orders(f):
            area = area_by_customer.get(order.customer_id, "Unknown")
            row = by_area[area]
            row["area"] = area
            row["orders"] += 1
            row["sales_value"] += float(order.total_amount or 0)
        for activity in self._activities_filtered(f):
            if activity.activity_type != "Payment Received" or not activity.customer_id:
                continue
            area = area_by_customer.get(activity.customer_id, "Unknown")
            row = by_area[area]
            row["area"] = area
            row["collections"] += self._amount_from_activity(activity)
        rows = sorted(by_area.values(), key=lambda r: r["leads"], reverse=True)
        return self._result(
            "top_areas_by_leads_orders_and_collections",
            ["area", "leads", "orders", "sales_value", "collections"],
            rows,
        )

    def report_upcoming_expected_orders(self, f: CrmReportFilters) -> CrmReportResult:
        rows = [
            {
                "enquiry_id": e.id,
                "party_name": e.party_name,
                "expected_decision_at": e.expected_decision_at,
                "estimated_value": e.estimated_value,
                "assigned_user": e.assigned_user_name,
            }
            for e in self._enquiries_filtered(f)
            if e.expected_decision_at
            and e.status
            not in {
                EnquiryStatus.WON.value,
                EnquiryStatus.LOST.value,
                EnquiryStatus.CLOSED.value,
            }
        ]
        return self._result(
            "upcoming_expected_orders",
            [
                "enquiry_id",
                "party_name",
                "expected_decision_at",
                "estimated_value",
                "assigned_user",
            ],
            rows,
        )

    def report_upcoming_payment_promises(self, f: CrmReportFilters) -> CrmReportResult:
        now = utc_now()
        rows = [
            {
                "customer_id": a.customer_id,
                "party_name": a.party_name,
                "promised_amount": a.promised_amount,
                "promised_date": a.promised_date,
                "assigned_user": a.assigned_user_name,
            }
            for a in self._activities_filtered(f)
            if a.promised_date and a.promised_date >= now
        ]
        return self._result(
            "upcoming_payment_promises",
            [
                "customer_id",
                "party_name",
                "promised_amount",
                "promised_date",
                "assigned_user",
            ],
            rows,
        )

    def report_overdue_activities_by_priority(self, f: CrmReportFilters) -> CrmReportResult:
        now = utc_now()
        rows = [
            {
                "activity_id": a.id,
                "activity_type": a.activity_type,
                "priority": a.priority,
                "scheduled_at": a.scheduled_at,
                "assigned_user": a.assigned_user_name,
                "party_name": a.party_name,
            }
            for a in self._activities_filtered(f)
            if a.status in {ActivityStatus.SCHEDULED.value, ActivityStatus.IN_PROGRESS.value}
            and a.scheduled_at
            and a.scheduled_at < now
        ]
        rows.sort(key=lambda r: (r["priority"] != "Urgent", r["priority"] != "High"))
        return self._result(
            "overdue_activities_by_priority",
            [
                "activity_id",
                "activity_type",
                "priority",
                "scheduled_at",
                "assigned_user",
                "party_name",
            ],
            rows,
        )

    def report_unassigned_leads_and_enquiries(self, f: CrmReportFilters) -> CrmReportResult:
        rows = [
            {
                "record_type": "lead",
                "id": l.id,
                "name": l.name,
                "status": l.status,
            }
            for l in self._leads.list(assigned_user_id="", branch=f.branch or None, limit=2000)
        ]
        if self._enquiries:
            for e in self._enquiries.list(assigned_user_id="", branch=f.branch or None, limit=2000):
                rows.append(
                    {
                        "record_type": "enquiry",
                        "id": e.id,
                        "name": e.party_name,
                        "status": e.status,
                    }
                )
        return self._result(
            "unassigned_leads_and_enquiries",
            ["record_type", "id", "name", "status"],
            rows,
        )

    def report_duplicate_or_potentially_duplicate_leads(
        self, f: CrmReportFilters
    ) -> CrmReportResult:
        leads = self._leads_filtered(f)
        by_phone: Dict[str, list] = defaultdict(list)
        by_email: Dict[str, list] = defaultdict(list)
        by_gstin: Dict[str, list] = defaultdict(list)
        for lead in leads:
            if lead.phone_normalized:
                by_phone[lead.phone_normalized].append(lead)
            if lead.email_normalized:
                by_email[lead.email_normalized].append(lead)
            if lead.gstin_normalized:
                by_gstin[lead.gstin_normalized].append(lead)
        rows = []
        seen = set()
        for group in list(by_phone.values()) + list(by_email.values()) + list(by_gstin.values()):
            if len(group) < 2:
                continue
            ids = tuple(sorted(l.id for l in group))
            if ids in seen:
                continue
            seen.add(ids)
            rows.append(
                {
                    "lead_ids": ",".join(ids),
                    "names": ", ".join(l.name for l in group),
                    "count": len(group),
                    "match_on": "phone/email/gstin",
                }
            )
        return self._result(
            "duplicate_or_potentially_duplicate_leads",
            ["lead_ids", "names", "count", "match_on"],
            rows,
        )
