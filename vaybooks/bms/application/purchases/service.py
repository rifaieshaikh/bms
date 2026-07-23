from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.domain.finance.accounting.entities import Voucher
from vaybooks.bms.domain.finance.accounting.purchase_parsing import (
    purchase_row_from_voucher,
    vendor_payment_row_from_voucher,
)
from vaybooks.bms.domain.purchases.line_items import PurchasePriceHistory
from vaybooks.bms.domain.purchases.purchase_line_resolver import PurchaseLineResolver
from vaybooks.bms.domain.purchases.entities import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseReturn,
)
from vaybooks.bms.domain.purchases.repository import (
    GoodsReceiptRepository,
    PurchaseOrderRepository,
    PurchaseReturnRepository,
)
from vaybooks.bms.domain.purchases.services import PurchaseDomainService
from vaybooks.bms.domain.shared.enums import (
    CatalogItemType,
    GoodsReceiptStatus,
    PurchaseOrderStatus,
    StockReferenceType,
    VoucherType,
)
from vaybooks.bms.infrastructure.repositories.finance.mongo_counter_repository import (
    MongoCounterRepository,
)


class PurchaseAppService:
    def __init__(
        self,
        po_repo: PurchaseOrderRepository,
        grn_repo: GoodsReceiptRepository,
        return_repo: PurchaseReturnRepository,
        counter_repo: MongoCounterRepository,
        accounting: AccountingAppService,
        inventory: InventoryAppService,
        vendor_service=None,
        vendor_services_config=None,
        business_service=None,
        price_history_repo=None,
    ):
        self._po_repo = po_repo
        self._grn_repo = grn_repo
        self._return_repo = return_repo
        self._counter_repo = counter_repo
        self._accounting = accounting
        self._inventory = inventory
        self._vendor_service = vendor_service
        self._vendor_services_config = vendor_services_config
        self._business_service = business_service
        self._price_history_repo = price_history_repo
        self._domain = PurchaseDomainService(po_repo, grn_repo, return_repo)

    def _line_resolver(self) -> PurchaseLineResolver:
        return PurchaseLineResolver(
            get_product=self._inventory.get_product,
            get_service=(
                self._vendor_services_config.get_service
                if self._vendor_services_config
                else lambda _id: None
            ),
            get_expense_account_id_by_name=lambda name: (
                acct.id if (acct := self._accounting.get_account_by_name(name)) else None
            ),
            get_expense_account_name=lambda account_id: (
                (acct.account_name if (acct := self._accounting.get_account(account_id)) else "")
            ),
        )

    def resolve_purchase_lines(self, raw_lines: list[dict], vendor_id: str):
        if not self._vendor_service:
            raise ValueError("Vendor service not configured")
        vendor = self._vendor_service.get_vendor_detail(vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        business = (
            self._business_service.get_profile()
            if self._business_service
            else None
        )
        return self._line_resolver().resolve_lines(
            raw_lines, vendor=vendor, business=business
        )

    def get_latest_purchase_rate(
        self,
        item_type: CatalogItemType,
        item_id: str,
        vendor_id: str,
        *,
        product=None,
    ) -> Optional[float]:
        """Return vendor's latest ex-GST purchase rate, else product last_purchase_rate.

        Pass ``product`` when already hydrated to avoid a second get_product round-trip.
        """
        if self._price_history_repo and vendor_id and item_id:
            latest = self._price_history_repo.latest_rate(item_type, item_id, vendor_id)
            if latest is not None and float(latest) > 0:
                return round(float(latest), 2)
        if item_type == CatalogItemType.PRODUCT and item_id:
            resolved = product
            if resolved is None and self._inventory:
                resolved = self._inventory.get_product(item_id)
            if resolved:
                last = float(getattr(resolved, "last_purchase_rate", 0) or 0)
                if last > 0:
                    return round(last, 2)
                selling = float(
                    getattr(resolved, "active_selling_rate", 0)
                    or getattr(resolved, "selling_rate", 0)
                    or 0
                )
                if selling > 0:
                    return round(selling, 2)
        return None

    def list_purchase_price_history(
        self,
        item_type: CatalogItemType,
        item_id: str,
        vendor_id: Optional[str] = None,
    ):
        if not self._price_history_repo:
            return []
        return self._price_history_repo.list_for_item(
            item_type, item_id, vendor_id=vendor_id
        )

    def _record_price_history(
        self,
        lines,
        *,
        vendor_id: str,
        purchase_date: date,
        voucher_id: str,
        vendor_bill_number: str,
    ) -> None:
        if not self._price_history_repo:
            return
        rows = []
        for line in lines:
            rate = round(float(getattr(line, "rate", 0) or 0), 2)
            if rate <= 0 or not getattr(line, "item_id", None):
                continue
            rows.append(
                PurchasePriceHistory(
                    item_type=line.item_type,
                    item_id=line.item_id,
                    vendor_id=vendor_id,
                    purchase_date=purchase_date,
                    qty=line.qty,
                    rate=rate,
                    taxable_amount=line.taxable_amount,
                    line_total=line.line_total,
                    cgst_amount=line.cgst_amount,
                    sgst_amount=line.sgst_amount,
                    igst_amount=line.igst_amount,
                    utgst_amount=line.utgst_amount,
                    voucher_id=voucher_id,
                    vendor_bill_number=vendor_bill_number,
                )
            )
        if not rows:
            return
        self._price_history_repo.save_many(rows)
        # Newest rate becomes the product's active purchase price (ex-GST).
        for line in rows:
            if line.item_type != CatalogItemType.PRODUCT:
                continue
            try:
                self._inventory.set_product_cost_fields(
                    line.item_id, last_purchase_rate=line.rate
                )
            except Exception:
                continue

    def create_purchase_bill_from_lines(
        self,
        vendor_id: str,
        raw_lines: list[dict],
        vendor_bill_number: str,
        amount_paid: float = 0.0,
        paying_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
        reference_service_id: Optional[str] = None,
        reference_po_id: Optional[str] = None,
        reference_grn_id: Optional[str] = None,
        apply_stock: bool = False,
    ) -> Voucher:
        resolved = self.resolve_purchase_lines(raw_lines, vendor_id)
        vendor_account = self._accounting.get_vendor_account(vendor_id)
        if not vendor_account:
            raise ValueError("Vendor account not found")
        expense_lines = [line.to_expense_line_dict() for line in resolved]
        voucher = self.create_purchase_bill(
            vendor_account_id=vendor_account.id,
            expense_lines=expense_lines,
            vendor_bill_number=vendor_bill_number,
            amount_paid=amount_paid,
            paying_account_id=paying_account_id,
            voucher_date=voucher_date,
            reference_order_id=reference_order_id,
            reference_service_id=reference_service_id,
            reference_po_id=reference_po_id,
            reference_grn_id=reference_grn_id,
            apply_stock=apply_stock,
            vendor_id=vendor_id,
            resolved_lines=resolved,
        )
        return voucher

    def list_purchase_orders(self) -> List[PurchaseOrder]:
        return self._po_repo.list_all()

    def get_purchase_order(self, order_id: str) -> Optional[PurchaseOrder]:
        return self._po_repo.find_by_id(order_id)

    def list_recent_purchase_orders_by_vendor(
        self, vendor_id: str, limit: int = 5
    ) -> List[PurchaseOrder]:
        fn = getattr(self._po_repo, "list_recent_by_vendor", None)
        if callable(fn):
            return list(fn(vendor_id, limit) or [])
        orders = [
            po for po in self._po_repo.list_all() if po.vendor_id == vendor_id
        ]
        orders.sort(
            key=lambda po: (po.created_at or datetime.min, po.order_date or date.min),
            reverse=True,
        )
        return orders[:limit]

    def get_vendor_summary(self, vendor_id: str) -> dict:
        """PO counts and total billed for one vendor."""
        summary_fn = getattr(self._po_repo, "get_vendor_summary", None)
        if callable(summary_fn):
            summary = dict(summary_fn(vendor_id) or {})
        else:
            closed = {
                PurchaseOrderStatus.RECEIVED,
                PurchaseOrderStatus.CLOSED,
                PurchaseOrderStatus.CANCELLED,
            }
            orders = [
                po for po in self._po_repo.list_all() if po.vendor_id == vendor_id
            ]
            summary = {
                "po_count": len(orders),
                "open_count": sum(1 for po in orders if po.status not in closed),
            }

        total_billed = 0.0
        vendor_account = None
        try:
            vendor_account = self._accounting.get_vendor_account(vendor_id)
        except Exception:
            vendor_account = None
        if vendor_account:
            try:
                for voucher in self._accounting.list_vouchers_by_type(
                    VoucherType.PURCHASE_BILL
                ):
                    row = purchase_row_from_voucher(voucher)
                    if row.get("vendor_account_id") == vendor_account.id:
                        total_billed += float(row.get("total") or 0)
            except Exception:
                pass
        summary["total_billed"] = round(total_billed, 2)
        return summary

    def related_document_counts(
        self, vendor_id: str, *, vendor_account_id: str = ""
    ) -> dict:
        """Counts for Related Transactions — one service entry point."""
        counts: dict = {}

        def _repo_count(repo) -> int | None:
            if repo is None:
                return None
            fn = getattr(repo, "count_by_vendor", None)
            if not callable(fn):
                return None
            try:
                return int(fn(vendor_id) or 0)
            except Exception:
                return None

        for key, repo in (
            ("purchase_orders", self._po_repo),
            ("goods_receipts", self._grn_repo),
            ("purchase_returns", self._return_repo),
        ):
            value = _repo_count(repo)
            if value is not None:
                counts[key] = value
            else:
                try:
                    items = repo.list_all() if repo else []
                    counts[key] = sum(
                        1 for item in items if getattr(item, "vendor_id", None) == vendor_id
                    )
                except Exception:
                    pass

        if vendor_account_id:
            try:
                counts["purchase_bills"] = self._accounting.count_vouchers_for_account(
                    VoucherType.PURCHASE_BILL, vendor_account_id
                )
            except Exception:
                pass
        return counts

    def create_purchase_order(
        self,
        vendor_id: str,
        order_date: date,
        lines: list[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT,
        project_id: str = "",
    ) -> PurchaseOrder:
        vendor_name = self._vendor_name(vendor_id)
        po_number = self._counter_repo.next("po_number")
        return self._domain.create_purchase_order(
            po_number=po_number,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            order_date=order_date,
            lines=lines,
            expected_date=expected_date,
            notes=notes,
            status=PurchaseOrderStatus.SENT,
            project_id=project_id,
        )

    def update_purchase_order(
        self,
        order_id: str,
        vendor_id: str,
        order_date: date,
        lines: list[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: Optional[PurchaseOrderStatus] = None,
    ) -> PurchaseOrder:
        return self._domain.update_purchase_order(
            order_id,
            vendor_id,
            self._vendor_name(vendor_id),
            order_date,
            lines,
            expected_date,
            notes,
            status,
        )

    def cancel_purchase_order(self, order_id: str) -> PurchaseOrder:
        return self._domain.cancel_purchase_order(order_id)

    def close_purchase_order(self, order_id: str) -> PurchaseOrder:
        return self._domain.close_purchase_order(order_id)

    def list_goods_receipts(self) -> List[GoodsReceipt]:
        return self._grn_repo.list_all()

    def get_goods_receipt(self, grn_id: str) -> Optional[GoodsReceipt]:
        return self._grn_repo.find_by_id(grn_id)

    def create_goods_receipt(
        self,
        vendor_id: str,
        receipt_date: date,
        lines: list[dict],
        purchase_order_id: Optional[str] = None,
        freight: float = 0.0,
        duty: float = 0.0,
        other: float = 0.0,
        notes: str = "",
        confirm: bool = True,
        allow_over_receive: bool = False,
    ) -> GoodsReceipt:
        po_number = ""
        if purchase_order_id:
            po = self._po_repo.find_by_id(purchase_order_id)
            po_number = po.po_number if po else ""
        grn_number = self._counter_repo.next("grn_number")
        grn = self._domain.create_grn(
            grn_number=grn_number,
            vendor_id=vendor_id,
            vendor_name=self._vendor_name(vendor_id),
            receipt_date=receipt_date,
            lines=lines,
            purchase_order_id=purchase_order_id,
            po_number=po_number,
            freight=freight,
            duty=duty,
            other=other,
            notes=notes,
            allow_over_receive=allow_over_receive,
        )
        if confirm:
            return self.confirm_goods_receipt(grn.id)
        return grn

    def confirm_goods_receipt(self, grn_id: str) -> GoodsReceipt:
        grn = self._grn_repo.find_by_id(grn_id)
        if not grn:
            raise ValueError("Goods receipt not found")
        if grn.status == GoodsReceiptStatus.RECEIVED:
            return grn
        stock_lines = self._domain.grn_to_stock_lines(grn)
        landed_lines = self._domain.grn_to_landed_cost_lines(grn)
        self._inventory.apply_purchase_receive(
            stock_lines,
            grn.id,
            StockReferenceType.GRN,
            grn.receipt_date,
        )
        self._inventory.apply_landed_cost(landed_lines)
        return self._domain.confirm_grn_received(grn_id)

    def list_purchase_returns(self) -> List[PurchaseReturn]:
        return self._return_repo.list_all()

    def get_purchase_return(self, return_id: str) -> Optional[PurchaseReturn]:
        return self._return_repo.find_by_id(return_id)

    def create_purchase_bill(
        self,
        vendor_account_id: str,
        expense_lines: list[dict],
        vendor_bill_number: str,
        amount_paid: float = 0.0,
        paying_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_order_id: Optional[str] = None,
        reference_service_id: Optional[str] = None,
        reference_po_id: Optional[str] = None,
        reference_grn_id: Optional[str] = None,
        apply_stock: bool = False,
        vendor_id: Optional[str] = None,
        resolved_lines=None,
    ) -> Voucher:
        voucher = self._accounting.create_purchase_bill(
            vendor_account_id=vendor_account_id,
            expense_lines=expense_lines,
            vendor_bill_number=vendor_bill_number,
            amount_paid=amount_paid,
            paying_account_id=paying_account_id,
            voucher_date=voucher_date,
            reference_order_id=reference_order_id,
            reference_service_id=reference_service_id,
            reference_po_id=reference_po_id,
            reference_grn_id=reference_grn_id,
        )
        if vendor_id and resolved_lines:
            self._record_price_history(
                resolved_lines,
                vendor_id=vendor_id,
                purchase_date=voucher_date or date.today(),
                voucher_id=voucher.id,
                vendor_bill_number=vendor_bill_number,
            )
        if apply_stock and not reference_grn_id:
            stock_lines = [
                {
                    "product_id": line.get("product_id"),
                    "qty": line.get("qty"),
                    "description": "Purchase bill",
                }
                for line in expense_lines
                if line.get("product_id") and float(line.get("qty") or 0) > 0
            ]
            if stock_lines:
                self._inventory.apply_purchase_receive(
                    stock_lines,
                    voucher.id,
                    StockReferenceType.PURCHASE,
                    voucher_date or date.today(),
                )
                landed = [
                    {
                        "product_id": line.get("product_id"),
                        "qty": float(line.get("qty") or 0),
                        "unit_cost": round(
                            float(
                                line.get("taxable_amount")
                                or line.get("amount")
                                or 0
                            )
                            / max(float(line.get("qty") or 0), 1),
                            4,
                        ),
                    }
                    for line in expense_lines
                    if line.get("product_id") and float(line.get("qty") or 0) > 0
                ]
                self._inventory.apply_landed_cost(landed)
        if reference_grn_id:
            grn = self._grn_repo.find_by_id(reference_grn_id)
            if grn:
                grn.voucher_id = voucher.id
                self._grn_repo.save(grn)
        return voucher

    def update_purchase_bill(
        self,
        voucher_id: str,
        vendor_account_id: str,
        expense_lines: list[dict],
        vendor_bill_number: str,
        amount_paid: float = 0.0,
        paying_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_service_id: Optional[str] = None,
        apply_stock: bool = False,
    ) -> Voucher:
        # apply_stock is accepted for API compatibility with create, but bill edit
        # is metadata + GST only — no stock / landed re-application on update.
        _ = apply_stock
        voucher = self._accounting.update_purchase_bill(
            voucher_id,
            vendor_account_id,
            expense_lines,
            vendor_bill_number,
            amount_paid,
            paying_account_id,
            voucher_date,
            reference_service_id,
        )
        return voucher

    def update_purchase_bill_from_lines(
        self,
        voucher_id: str,
        vendor_id: str,
        raw_lines: list[dict],
        vendor_bill_number: str,
        amount_paid: float = 0.0,
        paying_account_id: Optional[str] = None,
        voucher_date: Optional[date] = None,
        reference_service_id: Optional[str] = None,
        prior_landed_by_key: Optional[dict[tuple[str, str], float]] = None,
    ) -> Voucher:
        """Re-resolve lines and update bill metadata/GST; preserve landed_cost_alloc."""
        resolved = self.resolve_purchase_lines(raw_lines, vendor_id)
        prior = prior_landed_by_key or {}
        if not prior:
            old_row = self.get_purchase_bill(voucher_id) or {}
            for item in old_row.get("line_items") or []:
                key = (
                    str(item.get("item_type") or CatalogItemType.PRODUCT.value),
                    str(item.get("item_id") or item.get("product_id") or ""),
                )
                if key[1]:
                    prior[key] = float(item.get("landed_cost_alloc") or 0)
        for line in resolved:
            key = (line.item_type.value, line.item_id)
            if key in prior:
                line.landed_cost_alloc = prior[key]
            else:
                # Prefer explicit raw seed if present
                for raw in raw_lines:
                    raw_key = (
                        str(raw.get("item_type") or CatalogItemType.PRODUCT.value),
                        str(raw.get("item_id") or raw.get("product_id") or ""),
                    )
                    if raw_key == key and raw.get("landed_cost_alloc") is not None:
                        line.landed_cost_alloc = float(raw.get("landed_cost_alloc") or 0)
                        break
        vendor_account = self._accounting.get_vendor_account(vendor_id)
        if not vendor_account:
            raise ValueError("Vendor account not found")
        expense_lines = [line.to_expense_line_dict() for line in resolved]
        voucher = self.update_purchase_bill(
            voucher_id=voucher_id,
            vendor_account_id=vendor_account.id,
            expense_lines=expense_lines,
            vendor_bill_number=vendor_bill_number,
            amount_paid=amount_paid,
            paying_account_id=paying_account_id,
            voucher_date=voucher_date,
            reference_service_id=reference_service_id,
            apply_stock=False,
        )
        self._record_price_history(
            resolved,
            vendor_id=vendor_id,
            purchase_date=voucher_date or date.today(),
            voucher_id=voucher.id,
            vendor_bill_number=vendor_bill_number,
        )
        return voucher

    def delete_purchase_bill(self, voucher_id: str) -> None:
        old = self._accounting.get_voucher(voucher_id)
        if old and not old.reference_grn_id:
            self._inventory.reverse_movements_by_reference(voucher_id)
        self._accounting.delete_purchase_bill(voucher_id)

    def create_purchase_return(
        self,
        vendor_id: str,
        return_date: date,
        lines: list[dict],
        source_bill_id: Optional[str] = None,
        source_grn_id: Optional[str] = None,
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        notes: str = "",
    ) -> PurchaseReturn:
        vendor_account = self._accounting.get_vendor_account(vendor_id)
        if not vendor_account:
            raise ValueError("Vendor account not found")
        return_number = self._counter_repo.next("purchase_return_number")
        purchase_return = self._domain.create_purchase_return(
            return_number=return_number,
            vendor_id=vendor_id,
            vendor_name=self._vendor_name(vendor_id),
            return_date=return_date,
            lines=lines,
            source_bill_id=source_bill_id,
            source_grn_id=source_grn_id,
            notes=notes,
        )
        expense_lines = []
        stock_lines = []
        for line in purchase_return.lines:
            amount = line.line_total
            expense_lines.append(
                {
                    "expense_account_id": line.expense_account_id,
                    "amount": amount,
                }
            )
            stock_lines.append(
                {
                    "product_id": line.product_id,
                    "qty": line.qty,
                    "description": line.product_name or "Return",
                }
            )
        description = f"Purchase return {return_number}"
        if notes.strip():
            description = f"{description} — {notes.strip()}"
        voucher = self._accounting.create_purchase_return_voucher(
            vendor_account_id=vendor_account.id,
            expense_lines=expense_lines,
            description=description,
            amount_refunded=amount_refunded,
            refund_account_id=refund_account_id,
            voucher_date=return_date,
            reference_grn_id=source_grn_id,
        )
        purchase_return.voucher_id = voucher.id
        self._return_repo.save(purchase_return)
        self._inventory.apply_purchase_return(
            purchase_return.id, stock_lines, return_date
        )
        return purchase_return

    def list_purchase_bills(self) -> list[dict]:
        account_vendor: dict[str, str] = {}

        def _vendor_id_for(account_id: str | None) -> str:
            if not account_id:
                return ""
            if account_id in account_vendor:
                return account_vendor[account_id]
            try:
                account = self._accounting.get_account(account_id)
            except Exception:
                account = None
            vendor_id = (
                (getattr(account, "linked_vendor_id", None) or "") if account else ""
            )
            account_vendor[account_id] = vendor_id
            return vendor_id

        rows = []
        for voucher in self._accounting.list_vouchers_by_type(VoucherType.PURCHASE_BILL):
            row = purchase_row_from_voucher(voucher)
            row["vendor_id"] = _vendor_id_for(row.get("vendor_account_id"))
            rows.append(row)
        for voucher in self._accounting.list_vouchers_by_type(VoucherType.VENDOR_PAYMENT):
            row = vendor_payment_row_from_voucher(voucher)
            row["vendor_id"] = _vendor_id_for(row.get("vendor_account_id"))
            rows.append(row)
        rows.sort(key=lambda r: (r.get("bill_date") or date.min, r.get("voucher_number") or ""), reverse=True)
        return rows

    def get_purchase_bill(self, voucher_id: str) -> Optional[dict]:
        voucher = self._accounting.get_voucher(voucher_id)
        if not voucher:
            return None
        if voucher.voucher_type == VoucherType.PURCHASE_BILL:
            return purchase_row_from_voucher(voucher)
        if voucher.voucher_type == VoucherType.VENDOR_PAYMENT:
            return vendor_payment_row_from_voucher(voucher)
        return None

    def merge_vendor_payment_into_purchase(
        self,
        vendor_account_id: str,
        expense_account_id: str,
        paying_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        service_id: Optional[str] = None,
        reference_order_id: Optional[str] = None,
        vendor_bill_number: str = "",
    ) -> Voucher:
        """Adapter: legacy vendor payment → PURCHASE_BILL."""
        bill_number = vendor_bill_number or description.strip()[:40] or "Vendor payment"
        return self.create_purchase_bill(
            vendor_account_id=vendor_account_id,
            expense_lines=[
                {
                    "expense_account_id": expense_account_id,
                    "amount": amount,
                }
            ],
            vendor_bill_number=bill_number,
            amount_paid=amount,
            paying_account_id=paying_account_id,
            voucher_date=voucher_date,
            reference_order_id=reference_order_id,
            reference_service_id=service_id,
        )

    def _vendor_name(self, vendor_id: str) -> str:
        if not self._vendor_service or not vendor_id:
            return ""
        vendor = self._vendor_service.get_vendor_detail(vendor_id)
        return vendor.vendor_name if vendor else ""
