from __future__ import annotations

from typing import List, Optional

from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.sales.line_items import SalesInvoiceLine
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.india import compute_sales_gst
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile


def business_is_registered(business: Optional[BusinessProfile]) -> bool:
    if not business:
        return False
    if business.registration_type == PartyRegistrationType.REGISTERED:
        return True
    return bool((business.gstin or "").strip())


class SalesLineResolver:
    def __init__(self, *, get_product):
        self._get_product = get_product

    def resolve_lines(
        self,
        raw_lines: List[dict],
        *,
        customer: Customer,
        business: Optional[BusinessProfile],
    ) -> List[SalesInvoiceLine]:
        business_registered = business_is_registered(business)
        business_state = business.state_code if business else ""
        customer_state = customer.state_code if customer else ""
        resolved: List[SalesInvoiceLine] = []

        for raw in raw_lines:
            qty = float(raw.get("qty") or 0)
            rate = float(raw.get("rate") or 0)
            if qty <= 0:
                continue
            product_id = str(raw.get("product_id") or "").strip()
            if not product_id:
                desc = (raw.get("description") or "").strip()
                if not desc:
                    continue
                line_gross = round(qty * rate, 2)
                line_discount = round(min(float(raw.get("discount") or 0), line_gross), 2)
                taxable = round(max(line_gross - line_discount, 0.0), 2)
                gst = compute_sales_gst(
                    taxable,
                    0.0,
                    business_registered=business_registered,
                    business_state_code=business_state,
                    customer_state_code=customer_state,
                )
                resolved.append(
                    SalesInvoiceLine.from_raw(
                        raw,
                        tax_profile=ItemTaxProfile(),
                        gst=gst,
                        item_name=desc,
                    )
                )
                continue

            product = self._get_product(product_id)
            if not product:
                raise ValidationError("Product not found")
            tax_profile = product.active_tax_profile()
            if rate == 0:
                rate = float(getattr(product, "selling_rate", 0) or 0)
            line_gross = round(qty * rate, 2)
            line_discount = round(min(float(raw.get("discount") or 0), line_gross), 2)
            taxable = round(max(line_gross - line_discount, 0.0), 2)
            gst = compute_sales_gst(
                taxable,
                tax_profile.gst_rate,
                business_registered=business_registered,
                business_state_code=business_state,
                customer_state_code=customer_state,
            )
            resolved.append(
                SalesInvoiceLine.from_raw(
                    raw,
                    tax_profile=tax_profile,
                    gst=gst,
                    item_name=product.name,
                    gst_rate=tax_profile.gst_rate,
                )
            )

        if not resolved:
            raise ValidationError("Add at least one line with quantity and rate")
        return resolved
