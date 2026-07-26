"""CRM WhatsApp click-to-chat payment reminder helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional

from vaybooks.bms.domain.crm.entities import CrmActivity, CrmAuditEntry
from vaybooks.bms.domain.crm.enums import ActivityOrigin, ActivityStatus, NotificationKind
from vaybooks.bms.domain.crm.services import (
    activity_type_key,
    build_whatsapp_click_to_chat_url,
    format_invoice_refs,
    normalize_phone_for_whatsapp,
    render_payment_reminder_message,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


@dataclass
class PaymentReminderPreview:
    customer_id: str
    customer_name: str
    phone: str
    outstanding_amount: float
    message: str
    whatsapp_url: str
    invoice_count: int = 0
    invoice_refs: str = ""
    oldest_due_date: str = ""
    open_invoices: List[dict] = field(default_factory=list)


class CrmPaymentReminderService:
    def __init__(
        self,
        settings_repo,
        activity_repo=None,
        notification_service=None,
        audit_repo=None,
        customer_service=None,
        accounting_service=None,
    ):
        self._settings = settings_repo
        self._activities = activity_repo
        self._notifications = notification_service
        self._audit = audit_repo
        self._customers = customer_service
        self._accounting = accounting_service

    def resolve_outstanding(self, customer_id: str) -> float:
        if not self._accounting:
            return 0.0
        balances = getattr(self._accounting, "customer_balances_by_customer", None)
        if callable(balances):
            try:
                # Positive asset balance is customer receivable; advances are
                # negative and should not produce payment reminders.
                return max(float((balances() or {}).get(customer_id, 0) or 0), 0.0)
            except Exception:
                pass
        # Best-effort: accounting services vary; try common helpers
        for attr in ("get_customer_balance", "customer_outstanding", "get_party_balance"):
            fn = getattr(self._accounting, attr, None)
            if callable(fn):
                try:
                    return float(fn(customer_id) or 0)
                except TypeError:
                    try:
                        return float(fn(customer_id, party="customer") or 0)
                    except Exception:
                        continue
                except Exception:
                    continue
        return 0.0

    def open_invoices(self, customer_id: str) -> List[dict]:
        """Best-effort open sales invoices for a customer, oldest first.

        Returns dicts with ``voucher_id``, ``reference``, ``invoice_date`` and
        ``outstanding``. An empty list means invoice details could not be
        resolved (the aggregate AR balance is still used for the amount).
        """
        if not self._accounting:
            return []
        get_account = getattr(self._accounting, "get_customer_account", None)
        list_by_type = getattr(self._accounting, "list_vouchers_by_type", None)
        if not (callable(get_account) and callable(list_by_type)):
            return []
        try:
            from vaybooks.bms.domain.finance.accounting.sales_parsing import (
                sales_row_from_voucher,
            )
            from vaybooks.bms.domain.shared.enums import VoucherType

            account = get_account(customer_id)
            if not account:
                return []
            discount_id = None
            get_discount = getattr(self._accounting, "get_discount_account", None)
            if callable(get_discount):
                discount = get_discount()
                discount_id = discount.id if discount else None
            vouchers = list_by_type(VoucherType.SALES_INVOICE) or []
        except Exception:
            return []
        invoices: List[dict] = []
        for voucher in vouchers:
            try:
                row = sales_row_from_voucher(voucher, discount_id)
            except Exception:
                continue
            if row.get("customer_account_id") != account.id:
                continue
            outstanding = float(row.get("outstanding") or 0)
            if outstanding <= 0:
                continue
            reference = str(
                row.get("store_invoice_number")
                or getattr(voucher, "voucher_number", "")
                or ""
            ).strip()
            invoices.append(
                {
                    "voucher_id": row.get("id"),
                    "reference": reference or str(row.get("id") or "")[:8],
                    "invoice_date": row.get("sale_date"),
                    "outstanding": outstanding,
                }
            )
        invoices.sort(key=lambda inv: inv.get("invoice_date") or date.min)
        return invoices

    def preview(
        self,
        customer_id: str,
        *,
        phone: str = "",
        outstanding_amount: Optional[float] = None,
        message_override: str = "",
        business_name: str = "",
    ) -> PaymentReminderPreview:
        if not self._customers:
            raise ValidationError("Customer service not configured")
        customer = self._customers.get_customer_detail(customer_id)
        if not customer:
            raise ValidationError("Customer not found")
        mobile = phone or customer.phone_number or ""
        # Validate / normalize for WhatsApp
        normalize_phone_for_whatsapp(mobile)
        amount = (
            float(outstanding_amount)
            if outstanding_amount is not None
            else self.resolve_outstanding(customer_id)
        )
        invoices = self.open_invoices(customer_id)
        invoice_refs = format_invoice_refs(invoices)
        oldest_due = ""
        if invoices:
            first = invoices[0].get("invoice_date")
            if first:
                oldest_due = (
                    first.strftime("%d-%b-%Y")
                    if hasattr(first, "strftime")
                    else str(first)
                )
        settings = self._settings.get()
        biz = business_name or settings.business_display_name or "our business"
        message = (message_override or "").strip() or render_payment_reminder_message(
            settings.payment_reminder_template,
            customer_name=customer.customer_name,
            business_name=biz,
            outstanding_amount=amount,
            invoice_refs=invoice_refs,
            invoice_count=len(invoices),
            oldest_due_date=oldest_due,
        )
        url = build_whatsapp_click_to_chat_url(mobile, message)
        return PaymentReminderPreview(
            customer_id=customer.id,
            customer_name=customer.customer_name,
            phone=mobile,
            outstanding_amount=amount,
            message=message,
            whatsapp_url=url,
            invoice_count=len(invoices),
            invoice_refs=invoice_refs,
            oldest_due_date=oldest_due,
            open_invoices=invoices,
        )

    def record_opened(
        self,
        preview: PaymentReminderPreview,
        *,
        actor_id: str = "",
        actor_name: str = "",
        assigned_user_id: str = "",
        assigned_user_name: str = "",
        lead_id: str = "",
        branch: str = "",
    ) -> CrmActivity | None:
        """Audit that a WhatsApp reminder was prepared/opened (not delivered)."""
        if self._audit:
            self._audit.save(
                CrmAuditEntry(
                    entity_type="crm_payment_reminder",
                    entity_id=preview.customer_id,
                    action="whatsapp_reminder_opened",
                    actor_id=actor_id,
                    actor_name=actor_name,
                    after={
                        "phone": preview.phone,
                        "outstanding_amount": preview.outstanding_amount,
                        "whatsapp_url": preview.whatsapp_url,
                    },
                    branch=branch,
                )
            )
        if not self._activities:
            return None
        activity = CrmActivity(
            activity_type="WhatsApp Message",
            activity_type_key=activity_type_key("WhatsApp Message"),
            origin=ActivityOrigin.MANUAL.value,
            status=ActivityStatus.COMPLETED.value,
            customer_id=preview.customer_id,
            lead_id=lead_id,
            party_name=preview.customer_name,
            assigned_user_id=assigned_user_id or actor_id,
            assigned_user_name=assigned_user_name or actor_name,
            activity_at=utc_now(),
            completed_at=utc_now(),
            outcome="Completed",
            notes="WhatsApp payment reminder opened/prepared (not delivery-confirmed).",
            branch=branch,
        )
        activity.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
        return self._activities.save(activity)

    def schedule_reminder_tasks(
        self,
        *,
        customer_id: str,
        customer_name: str,
        outstanding_amount: float,
        recipient_id: str,
        phone: str = "",
        base_date: Optional[datetime] = None,
        actor_id: str = "",
        actor_name: str = "",
        branch: str = "",
    ) -> List[CrmActivity]:
        """Create deduplicated scheduled reminder tasks from settings offsets."""
        if not self._activities or not recipient_id:
            return []
        settings = self._settings.get()
        offsets = list(settings.payment_reminder_due_offsets_days or [0])
        base = base_date or utc_now()
        created: List[CrmActivity] = []
        for offset in offsets:
            due = base + timedelta(days=int(offset))
            source_txn_id = f"{customer_id}:{due.date().isoformat()}"
            key = activity_type_key("Payment Reminder")
            existing = self._activities.find_by_source(
                "crm", "payment_reminder", source_txn_id, key
            )
            if existing:
                created.append(existing)
                continue
            activity = CrmActivity(
                activity_type="Payment Reminder",
                activity_type_key=key,
                origin=ActivityOrigin.AUTOMATIC.value,
                status=ActivityStatus.SCHEDULED.value,
                customer_id=customer_id,
                party_name=customer_name,
                assigned_user_id=recipient_id,
                scheduled_at=due,
                notes=(
                    f"Review and send WhatsApp payment reminder. "
                    f"Outstanding Rs.{outstanding_amount:,.2f}. Phone: {phone}"
                ),
                source_module="crm",
                source_txn_type="payment_reminder",
                source_txn_id=source_txn_id,
                branch=branch,
            )
            activity.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
            saved = self._activities.save(activity)
            created.append(saved)
            if self._notifications:
                self._notifications.create(
                    recipient_id=recipient_id,
                    kind=NotificationKind.PAYMENT_REMINDER_DUE,
                    title="Payment reminder due",
                    message=f"{customer_name}: Rs.{outstanding_amount:,.2f}",
                    ref_type="crm_activity",
                    ref_id=saved.id,
                    branch=branch,
                )
        return created

    def generate_scheduled_reminders(
        self,
        *,
        default_recipient_id: str = "",
        as_of: Optional[datetime] = None,
        branch: str = "",
        actor_id: str = "system",
        actor_name: str = "System",
    ) -> List[CrmActivity]:
        """Generate review tasks; this never sends a WhatsApp message."""
        if not self._customers or not self._accounting:
            return []
        now = as_of or utc_now()
        balances_loader = getattr(
            self._accounting, "customer_balances_by_customer", None
        )
        if not callable(balances_loader):
            return []
        balances = balances_loader() or {}
        created: List[CrmActivity] = []
        for customer in self._customers.list_all_customers():
            outstanding = max(float(balances.get(customer.id, 0) or 0), 0.0)
            if outstanding <= 0:
                continue
            recipient_id = (
                getattr(customer, "assigned_user_id", "") or default_recipient_id
            )
            if not recipient_id:
                continue
            created.extend(
                self.schedule_reminder_tasks(
                    customer_id=customer.id,
                    customer_name=customer.customer_name,
                    outstanding_amount=outstanding,
                    recipient_id=recipient_id,
                    phone=customer.phone_number or "",
                    base_date=now,
                    actor_id=actor_id,
                    actor_name=actor_name,
                    branch=branch,
                )
            )
        return created
