"""Tests for purchase line expense resolver."""

from datetime import date

from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.inventory.entities import InventoryProduct
from vaybooks.bms.domain.purchases.purchase_line_resolver import PurchaseLineResolver
from vaybooks.bms.domain.shared.enums import CatalogItemType, VendorRegistrationType
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile
from vaybooks.bms.domain.vendor_services.entities import VendorService
from vaybooks.bms.domain.vendors.entities import Vendor


def test_product_maps_to_material_expense():
    product = InventoryProduct(sku="SKU1", name="Fabric", category_id="c1", hsn_sac="5208")
    product.apply_active_rates(gst_rate=5.0)
    service = VendorService(
        service_name="Dyeing", expense_account_id="exp-dyeing",
        tax_profile=ItemTaxProfile(hsn_sac="9988", gst_rate=18.0),
    )
    resolver = PurchaseLineResolver(
        get_product=lambda pid: product if pid == product.id else None,
        get_service=lambda sid: service if sid == service.id else None,
        get_expense_account_id_by_name=lambda name: "exp-material" if name == "Material Purchase Expense" else None,
        get_expense_account_name=lambda aid: {"exp-material": "Material Purchase Expense", "exp-dyeing": "Dyeing Expense"}[aid],
    )
    vendor = Vendor(
        vendor_name="V", phone_number="9876543210",
        registration_type=VendorRegistrationType.UNREGISTERED,
        state_code="27",
    )
    lines = resolver.resolve_lines(
        [{"item_type": CatalogItemType.PRODUCT.value, "item_id": product.id, "qty": 2, "rate": 100}],
        vendor=vendor,
        business=BusinessProfile(state_code="27"),
    )
    assert lines[0].expense_account_id == "exp-material"
    assert lines[0].line_total == 200.0


def test_service_maps_to_configured_expense():
    product = InventoryProduct(sku="SKU1", name="Fabric", category_id="c1")
    service = VendorService(
        service_name="Dyeing", expense_account_id="exp-dyeing",
        tax_profile=ItemTaxProfile(gst_rate=18.0),
    )
    resolver = PurchaseLineResolver(
        get_product=lambda pid: product if pid == product.id else None,
        get_service=lambda sid: service if sid == service.id else None,
        get_expense_account_id_by_name=lambda name: "exp-material" if name == "Material Purchase Expense" else None,
        get_expense_account_name=lambda aid: "Dyeing Expense",
    )
    vendor = Vendor(
        vendor_name="V", phone_number="9876543210",
        registration_type=VendorRegistrationType.REGISTERED,
        state_code="27",
    )
    lines = resolver.resolve_lines(
        [{"item_type": CatalogItemType.SERVICE.value, "item_id": service.id, "qty": 1, "rate": 1000}],
        vendor=vendor,
        business=BusinessProfile(state_code="27"),
    )
    assert lines[0].expense_account_id == "exp-dyeing"
    assert lines[0].cgst_amount > 0
    assert lines[0].line_total > 1000


def test_product_uses_active_gst_rate():
    product = InventoryProduct(sku="SKU1", name="Fabric", category_id="c1", hsn_sac="5208")
    product.apply_active_rates(gst_rate=18.0)
    resolver = PurchaseLineResolver(
        get_product=lambda pid: product if pid == product.id else None,
        get_service=lambda sid: None,
        get_expense_account_id_by_name=lambda name: "exp-material" if name == "Material Purchase Expense" else None,
        get_expense_account_name=lambda aid: "Material Purchase Expense",
    )
    vendor = Vendor(
        vendor_name="V", phone_number="9876543210",
        registration_type=VendorRegistrationType.REGISTERED,
        state_code="27",
    )
    lines = resolver.resolve_lines(
        [{"item_type": CatalogItemType.PRODUCT.value, "item_id": product.id, "qty": 1, "rate": 1000}],
        vendor=vendor,
        business=BusinessProfile(state_code="27"),
    )
    assert lines[0].cgst_amount == 90.0
    assert lines[0].line_total == 1180.0
