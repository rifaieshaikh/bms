from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.customer_app_service import CustomerAppService
from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.application.migration.mapping import (
    apply_mapping_to_rows,
    apply_saved_profile,
    missing_required,
    suggest_mapping,
)
from vaybooks.bms.application.migration.parser import load_upload, source_columns
from vaybooks.bms.application.migration.results import (
    ImportPreview,
    ImportResult,
    RowIssue,
    issues_to_csv,
)
from vaybooks.bms.application.migration.schemas import (
    DuplicatePolicy,
    ImportEntityType,
    NOT_MAPPED,
    fields_for,
)
from vaybooks.bms.application.migration.templates import template_csv
from vaybooks.bms.application.migration.validators import (
    resolve_category_id,
    validate_mapped_rows,
)
from vaybooks.bms.application.vendor_app_service import VendorAppService
from vaybooks.bms.domain.customers.entities import CustomerInput
from vaybooks.bms.domain.inventory.category_tree import build_category_path
from vaybooks.bms.domain.inventory.entities import InventoryProduct
from vaybooks.bms.domain.migration.entities import ImportMappingProfile
from vaybooks.bms.domain.migration.repository import ImportMappingProfileRepository
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.vendors.entities import VendorInput


class MigrationAppService:
    def __init__(
        self,
        profile_repo: ImportMappingProfileRepository,
        customer_service: CustomerAppService,
        vendor_service: VendorAppService,
        inventory_service: InventoryAppService,
        accounting_service: AccountingAppService,
    ):
        self._profiles = profile_repo
        self._customers = customer_service
        self._vendors = vendor_service
        self._inventory = inventory_service
        self._accounting = accounting_service

    # --- templates / parsing / mapping ---------------------------------

    def get_template(self, entity_type: ImportEntityType) -> str:
        return template_csv(entity_type)

    def parse_upload(self, file_bytes: bytes, filename: str = "") -> pd.DataFrame:
        return load_upload(file_bytes, filename)

    def source_columns(self, df: pd.DataFrame) -> List[str]:
        return source_columns(df)

    def suggest_mapping(
        self, entity_type: ImportEntityType, source_cols: List[str]
    ) -> Dict[str, str]:
        return suggest_mapping(entity_type, source_cols)

    def missing_required(
        self, entity_type: ImportEntityType, mapping: Dict[str, str]
    ) -> List[str]:
        return missing_required(entity_type, mapping)

    def apply_profile_to_mapping(
        self,
        entity_type: ImportEntityType,
        source_cols: List[str],
        profile_mapping: Dict[str, str],
        base_mapping: Optional[Dict[str, str]] = None,
    ) -> Tuple[Dict[str, str], List[str]]:
        base = base_mapping or suggest_mapping(entity_type, source_cols)
        return apply_saved_profile(base, source_cols, profile_mapping)

    # --- mapping profiles ----------------------------------------------

    def list_mapping_profiles(
        self, entity_type: ImportEntityType
    ) -> List[ImportMappingProfile]:
        return self._profiles.list_by_entity(entity_type.value)

    def get_mapping_profile(self, profile_id: str) -> Optional[ImportMappingProfile]:
        return self._profiles.find_by_id(profile_id)

    def save_mapping_profile(
        self,
        entity_type: ImportEntityType,
        name: str,
        mapping: Dict[str, str],
    ) -> ImportMappingProfile:
        name = (name or "").strip()
        if not name:
            raise ValueError("Mapping profile name is required")
        cleaned = {
            k: (v or NOT_MAPPED)
            for k, v in mapping.items()
            if k in {f.key for f in fields_for(entity_type)}
        }
        existing = self._profiles.find_by_entity_and_name(entity_type.value, name)
        if existing:
            existing.update_mapping(cleaned)
            return self._profiles.save(existing)
        profile = ImportMappingProfile(
            name=name,
            entity_type=entity_type.value,
            mapping=cleaned,
        )
        return self._profiles.save(profile)

    def delete_mapping_profile(self, profile_id: str) -> None:
        self._profiles.delete(profile_id)

    # --- preview / import ----------------------------------------------

    def preview_import(
        self,
        entity_type: ImportEntityType,
        df: pd.DataFrame,
        mapping: Dict[str, str],
    ) -> ImportPreview:
        missing = missing_required(entity_type, mapping)
        if missing:
            return ImportPreview(
                entity_type=entity_type.value,
                total_rows=len(df),
                valid_rows=0,
                issues=[
                    RowIssue(
                        row=0,
                        message=f"Required fields not mapped: {', '.join(missing)}",
                    )
                ],
                can_import=False,
            )
        rows = apply_mapping_to_rows(entity_type, df, mapping)
        preview = validate_mapped_rows(entity_type, rows)
        # Allow import of valid rows even when some rows have errors
        preview.can_import = preview.valid_rows > 0
        return preview

    def run_import(
        self,
        entity_type: ImportEntityType,
        df: pd.DataFrame,
        mapping: Dict[str, str],
        duplicate_policy: DuplicatePolicy = DuplicatePolicy.SKIP,
    ) -> ImportResult:
        missing = missing_required(entity_type, mapping)
        if missing:
            return ImportResult(
                entity_type=entity_type.value,
                failed=len(df),
                issues=[
                    RowIssue(
                        row=0,
                        message=f"Required fields not mapped: {', '.join(missing)}",
                    )
                ],
            )
        rows = apply_mapping_to_rows(entity_type, df, mapping)
        if entity_type == ImportEntityType.CATEGORIES:
            return self._import_categories(rows, duplicate_policy)
        if entity_type == ImportEntityType.PRODUCTS:
            return self._import_products(rows, duplicate_policy)
        if entity_type == ImportEntityType.CUSTOMERS:
            return self._import_customers(rows, duplicate_policy)
        if entity_type == ImportEntityType.VENDORS:
            return self._import_vendors(rows, duplicate_policy)
        raise ValueError(f"Unsupported entity type: {entity_type}")

    def issues_csv(self, result: ImportResult) -> str:
        return issues_to_csv(result.issues)

    # --- category import -----------------------------------------------

    def _import_categories(
        self, rows: List[Dict[str, Any]], policy: DuplicatePolicy
    ) -> ImportResult:
        result = ImportResult(entity_type=ImportEntityType.CATEGORIES.value)
        # Multi-pass: parents before children
        pending = list(rows)
        max_passes = max(len(pending), 1) + 2
        try:
            for _ in range(max_passes):
                if not pending:
                    break
                next_pending: List[Dict[str, Any]] = []
                progress = False
                for row in pending:
                    status = self._import_one_category(row, policy, result)
                    if status == "deferred":
                        next_pending.append(row)
                    else:
                        progress = True
                if not progress and next_pending:
                    for row in next_pending:
                        parent = (row.get("parent_name") or "").strip()
                        result.failed += 1
                        result.issues.append(
                            RowIssue(
                                row=int(row.get("_row") or 0),
                                message=f"Parent category '{parent}' not found",
                            )
                        )
                    break
                pending = next_pending
        except _AbortImport:
            pass
        return result

    def _import_one_category(
        self,
        row: Dict[str, Any],
        policy: DuplicatePolicy,
        result: ImportResult,
    ) -> str:
        row_num = int(row.get("_row") or 0)
        name = (row.get("name") or "").strip()
        if not name:
            result.failed += 1
            result.issues.append(RowIssue(row=row_num, message="Name is required"))
            return "done"
        parent_name = (row.get("parent_name") or "").strip()
        parent_id = None
        if parent_name:
            parent = self._find_category_by_name(parent_name)
            if not parent:
                return "deferred"
            parent_id = parent.id
        existing = self._inventory._category_repo.find_by_parent_and_name(parent_id, name)
        description = (row.get("description") or "") or ""
        is_active = row.get("is_active")
        if is_active is None:
            is_active = True
        try:
            if existing:
                if policy == DuplicatePolicy.SKIP:
                    result.skipped += 1
                    return "done"
                if policy == DuplicatePolicy.FAIL:
                    result.failed += 1
                    result.issues.append(
                        RowIssue(row=row_num, message=f"Duplicate category '{name}'")
                    )
                    raise _AbortImport()
                self._inventory.update_category(
                    existing.id,
                    name=name,
                    description=str(description),
                    is_active=bool(is_active),
                    parent_id=parent_id,
                )
                result.updated += 1
                return "done"
            self._inventory.create_category(
                name=name, description=str(description), parent_id=parent_id
            )
            if not is_active:
                created = self._inventory._category_repo.find_by_parent_and_name(
                    parent_id, name
                )
                if created:
                    self._inventory.update_category(
                        created.id,
                        name=created.name,
                        description=created.description,
                        is_active=False,
                        parent_id=created.parent_id,
                    )
            result.created += 1
            return "done"
        except _AbortImport:
            raise
        except Exception as exc:
            result.failed += 1
            result.issues.append(RowIssue(row=row_num, message=str(exc)))
            return "done"

    def _find_category_by_name(self, name: str):
        text = name.strip()
        categories = self._inventory.list_categories(active_only=False)
        by_id = {c.id: c for c in categories}
        # Exact path match
        for cat in categories:
            path = build_category_path(cat.id, by_id)
            if path.lower() == text.lower() or cat.name.lower() == text.lower():
                # Prefer unique name match
                pass
        matches = [c for c in categories if c.name.lower() == text.lower()]
        if len(matches) == 1:
            return matches[0]
        path_matches = [
            c for c in categories if build_category_path(c.id, by_id).lower() == text.lower()
        ]
        if len(path_matches) == 1:
            return path_matches[0]
        if ">" in text:
            normalized = " > ".join(p.strip() for p in text.split(">") if p.strip())
            path_matches = [
                c
                for c in categories
                if build_category_path(c.id, by_id).lower() == normalized.lower()
            ]
            if len(path_matches) == 1:
                return path_matches[0]
        return matches[0] if len(matches) == 1 else None

    # --- product import ------------------------------------------------

    def _category_lookups(self) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        categories = self._inventory.list_categories(active_only=False)
        by_id = {c.id: c for c in categories}
        by_path: Dict[str, str] = {}
        by_name: Dict[str, List[str]] = {}
        for cat in categories:
            path = build_category_path(cat.id, by_id)
            by_path[path.lower()] = cat.id
            by_name.setdefault(cat.name.lower(), []).append(cat.id)
        return by_path, by_name

    def _import_products(
        self, rows: List[Dict[str, Any]], policy: DuplicatePolicy
    ) -> ImportResult:
        result = ImportResult(entity_type=ImportEntityType.PRODUCTS.value)
        by_path, by_name = self._category_lookups()
        try:
            for row in rows:
                self._import_one_product(row, policy, result, by_path, by_name)
        except _AbortImport:
            pass
        return result

    def _import_one_product(
        self,
        row: Dict[str, Any],
        policy: DuplicatePolicy,
        result: ImportResult,
        by_path: Dict[str, str],
        by_name: Dict[str, List[str]],
    ) -> None:
        row_num = int(row.get("_row") or 0)
        sku = (row.get("sku") or "").strip()
        name = (row.get("name") or "").strip()
        if not sku or not name:
            result.failed += 1
            result.issues.append(RowIssue(row=row_num, message="SKU and name are required"))
            return
        category_value = (row.get("category") or "").strip()
        category_id, cat_err = resolve_category_id(category_value, by_path, by_name)
        if cat_err:
            result.failed += 1
            result.issues.append(RowIssue(row=row_num, message=cat_err))
            return
        category_ids = [category_id] if category_id else []
        unit = (row.get("unit") or "pcs").strip() or "pcs"
        selling_rate = float(row.get("selling_rate") or 0)
        opening_qty = float(row.get("opening_qty") or 0)
        hsn_sac = (row.get("hsn_sac") or "") or ""
        gst_rate = row.get("gst_rate")
        mrp = row.get("mrp")
        gst_rates = None
        mrp_entries = None
        if gst_rate is not None:
            gst_rates = [
                InventoryProduct.default_gst_slab(gst_rate=float(gst_rate))
            ]
        if mrp is not None:
            mrp_entries = [
                InventoryProduct.default_mrp_entry(mrp=float(mrp))
            ]
        existing = self._inventory.find_product_by_sku(sku)
        try:
            if existing:
                if policy == DuplicatePolicy.SKIP:
                    result.skipped += 1
                    return
                if policy == DuplicatePolicy.FAIL:
                    result.failed += 1
                    result.issues.append(
                        RowIssue(row=row_num, message=f"Duplicate SKU '{sku}'")
                    )
                    raise _AbortImport()
                self._inventory.update_product(
                    existing.id,
                    sku=sku,
                    name=name,
                    category_ids=category_ids or existing.category_ids,
                    unit_id=existing.unit_id or unit,
                    selling_rate=selling_rate,
                    is_active=True,
                    hsn_sac=hsn_sac or existing.hsn_sac,
                    gst_rates=gst_rates,
                    mrp_entries=mrp_entries,
                )
                self._apply_product_costs(existing.id, row)
                result.updated += 1
                return
            product = self._inventory.create_product(
                sku=sku,
                name=name,
                category_ids=category_ids,
                unit=unit,
                selling_rate=selling_rate,
                opening_qty=opening_qty,
                hsn_sac=hsn_sac,
                gst_rates=gst_rates,
                mrp_entries=mrp_entries,
            )
            self._apply_product_costs(product.id, row)
            result.created += 1
        except _AbortImport:
            raise
        except Exception as exc:
            result.failed += 1
            result.issues.append(RowIssue(row=row_num, message=str(exc)))

    def _apply_product_costs(self, product_id: str, row: Dict[str, Any]) -> None:
        wac = row.get("weighted_avg_cost")
        lpr = row.get("last_purchase_rate")
        if wac is None and lpr is None:
            return
        self._inventory.set_product_cost_fields(
            product_id,
            weighted_avg_cost=float(wac) if wac is not None else None,
            last_purchase_rate=float(lpr) if lpr is not None else None,
        )

    # --- customer / vendor import --------------------------------------

    def _import_customers(
        self, rows: List[Dict[str, Any]], policy: DuplicatePolicy
    ) -> ImportResult:
        result = ImportResult(entity_type=ImportEntityType.CUSTOMERS.value)
        try:
            for row in rows:
                self._import_one_customer(row, policy, result)
        except _AbortImport:
            pass
        return result

    def _import_one_customer(
        self,
        row: Dict[str, Any],
        policy: DuplicatePolicy,
        result: ImportResult,
    ) -> None:
        row_num = int(row.get("_row") or 0)
        try:
            payload = self._party_input_from_row(row, party="customer")
            customer_input = CustomerInput(**payload)
            existing = self._customers.lookup_customer_by_phone(customer_input.phone_number)
            if not existing and customer_input.gstin:
                existing = self._customers._customer_repo.find_by_gstin(customer_input.gstin)
            if existing:
                if policy == DuplicatePolicy.SKIP:
                    result.skipped += 1
                    return
                if policy == DuplicatePolicy.FAIL:
                    result.failed += 1
                    result.issues.append(
                        RowIssue(
                            row=row_num,
                            message=f"Duplicate customer '{customer_input.customer_name}'",
                        )
                    )
                    raise _AbortImport()
                customer = self._customers.update_customer(existing.id, customer_input)
                self._apply_party_opening_balance(
                    customer.id, row.get("opening_balance"), party="customer"
                )
                result.updated += 1
                return
            customer = self._customers.create_customer(customer_input)
            self._apply_party_opening_balance(
                customer.id, row.get("opening_balance"), party="customer"
            )
            result.created += 1
        except _AbortImport:
            raise
        except Exception as exc:
            result.failed += 1
            result.issues.append(RowIssue(row=row_num, message=str(exc)))

    def _import_vendors(
        self, rows: List[Dict[str, Any]], policy: DuplicatePolicy
    ) -> ImportResult:
        result = ImportResult(entity_type=ImportEntityType.VENDORS.value)
        try:
            for row in rows:
                self._import_one_vendor(row, policy, result)
        except _AbortImport:
            pass
        return result

    def _import_one_vendor(
        self,
        row: Dict[str, Any],
        policy: DuplicatePolicy,
        result: ImportResult,
    ) -> None:
        row_num = int(row.get("_row") or 0)
        try:
            payload = self._party_input_from_row(row, party="vendor")
            vendor_input = VendorInput(**payload)
            existing = self._vendors._vendor_repo.find_by_phone(vendor_input.phone_number)
            if not existing and vendor_input.gstin:
                existing = self._vendors._vendor_repo.find_by_gstin(vendor_input.gstin)
            if existing:
                if policy == DuplicatePolicy.SKIP:
                    result.skipped += 1
                    return
                if policy == DuplicatePolicy.FAIL:
                    result.failed += 1
                    result.issues.append(
                        RowIssue(
                            row=row_num,
                            message=f"Duplicate vendor '{vendor_input.vendor_name}'",
                        )
                    )
                    raise _AbortImport()
                vendor = self._vendors.update_vendor(existing.id, vendor_input)
                self._apply_party_opening_balance(
                    vendor.id, row.get("opening_balance"), party="vendor"
                )
                result.updated += 1
                return
            vendor = self._vendors.create_vendor(vendor_input)
            self._apply_party_opening_balance(
                vendor.id, row.get("opening_balance"), party="vendor"
            )
            result.created += 1
        except _AbortImport:
            raise
        except Exception as exc:
            result.failed += 1
            result.issues.append(RowIssue(row=row_num, message=str(exc)))

    def _party_input_from_row(self, row: Dict[str, Any], party: str) -> Dict[str, Any]:
        reg = row.get("registration_type") or PartyRegistrationType.UNREGISTERED.value
        try:
            registration_type = PartyRegistrationType(reg)
        except ValueError:
            registration_type = PartyRegistrationType.UNREGISTERED
        common = {
            "phone_number": (row.get("phone_number") or "").strip(),
            "alternate_phone_number": (row.get("alternate_phone_number") or None) or None,
            "email": (row.get("email") or "") or "",
            "contact_person": (row.get("contact_person") or "") or "",
            "address_line1": (row.get("address_line1") or "") or "",
            "address_line2": (row.get("address_line2") or "") or "",
            "city": (row.get("city") or "") or "",
            "state_code": (row.get("state_code") or "") or "",
            "pincode": (row.get("pincode") or "") or "",
            "country": (row.get("country") or "India") or "India",
            "gstin": (row.get("gstin") or "") or "",
            "pan": (row.get("pan") or "") or "",
            "registration_type": registration_type,
            "msme_number": (row.get("msme_number") or "") or "",
            "notes": (row.get("notes") or "") or "",
        }
        if party == "customer":
            return {
                "customer_name": (row.get("customer_name") or "").strip(),
                **common,
            }
        return {
            "vendor_name": (row.get("vendor_name") or "").strip(),
            **common,
            "bank_account_holder": (row.get("bank_account_holder") or "") or "",
            "bank_account_number": (row.get("bank_account_number") or "") or "",
            "bank_ifsc": (row.get("bank_ifsc") or "") or "",
            "bank_name": (row.get("bank_name") or "") or "",
        }

    def _apply_party_opening_balance(
        self, party_id: str, amount: Any, party: str
    ) -> None:
        if amount is None:
            return
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return
        if abs(value) < 0.0001:
            return
        if party == "customer":
            account = self._accounting._account_repo.find_customer_account(party_id)
        else:
            account = self._accounting._account_repo.find_vendor_account(party_id)
        if not account:
            return
        self._accounting.set_opening_balance(account.id, value)


class _AbortImport(Exception):
    """Stop FAIL-policy import after first duplicate."""
