from __future__ import annotations

from typing import Callable, List, Optional

from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.purchases.line_items import PurchaseBillLine
from vaybooks.bms.domain.shared.enums import CatalogItemType, VendorRegistrationType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.india import (
    MATERIAL_PURCHASE_EXPENSE_NAME,
    compute_purchase_gst,
)
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile
from vaybooks.bms.domain.vendors.entities import Vendor


class PurchaseLineResolver:
    def __init__(
        self,
        *,
        get_product,
        get_service,
        get_expense_account_id_by_name: Callable[[str], Optional[str]],
        get_expense_account_name: Callable[[str], str],
    ):
        self._get_product = get_product
        self._get_service = get_service
        self._get_expense_id = get_expense_account_id_by_name
        self._get_expense_name = get_expense_account_name
        self._cached_material_expense_id: Optional[str] = None

    def _material_expense_account_id(self) -> str:
        if not self._cached_material_expense_id:
            account_id = self._get_expense_id(MATERIAL_PURCHASE_EXPENSE_NAME)
            if not account_id:
                raise ValidationError(
                    f'Expense account "{MATERIAL_PURCHASE_EXPENSE_NAME}" not found'
                )
            self._cached_material_expense_id = account_id
        return self._cached_material_expense_id

    def resolve_lines(
        self,
        raw_lines: List[dict],
        *,
        vendor: Vendor,
        business: Optional[BusinessProfile],
    ) -> List[PurchaseBillLine]:
        vendor_registered = (
            vendor.registration_type == VendorRegistrationType.REGISTERED
        )
        business_state = business.state_code if business else ""
        resolved: List[PurchaseBillLine] = []

        for raw in raw_lines:
            qty = float(raw.get("qty") or 0)
            rate = float(raw.get("rate") or 0)
            if qty <= 0 or rate < 0:
                continue
            item_type = CatalogItemType(
                raw.get("item_type") or CatalogItemType.PRODUCT.value
            )
            item_id = str(raw.get("item_id") or "").strip()
            if not item_id:
                raise ValidationError(
                    "Each line must have a product or service selected"
                )

            tax_profile, item_name, expense_id = self._resolve_item(
                item_type, item_id
            )
            taxable = round(qty * rate, 2)
            gst = compute_purchase_gst(
                taxable,
                tax_profile.gst_rate,
                vendor_registered=vendor_registered,
                business_state_code=business_state,
                vendor_state_code=vendor.state_code,
            )
            expense_name = self._get_expense_name(expense_id)
            resolved.append(
                PurchaseBillLine.from_raw(
                    raw,
                    tax_profile=tax_profile,
                    gst=gst,
                    expense_account_id=expense_id,
                    expense_account_name=expense_name,
                    item_name=item_name,
                )
            )

        if not resolved:
            raise ValidationError(
                "Add at least one line with quantity, rate, and item"
            )
        return resolved

    def _resolve_item(
        self, item_type: CatalogItemType, item_id: str
    ) -> tuple[ItemTaxProfile, str, str]:
        if item_type == CatalogItemType.PRODUCT:
            product = self._get_product(item_id)
            if not product:
                raise ValidationError("Product not found")
            return product.active_tax_profile(), product.name, self._material_expense_account_id()
        service = self._get_service(item_id)
        if not service:
            raise ValidationError("Service not found")
        return service.tax_profile, service.service_name, service.expense_account_id
