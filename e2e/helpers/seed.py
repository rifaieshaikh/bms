"""Seed deterministic records for Playwright E2E tests."""

from __future__ import annotations

import os

from vaybooks.bms.domain.customers.entities import CustomerInput
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.vendors.entities import VendorInput
from vaybooks.bms.infrastructure.db.connection import get_database_from_uri
from vaybooks.bms.infrastructure.db.indexes import ensure_indexes


def _db():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        try:
            import streamlit as st

            uri = st.secrets.get("MONGODB_URI")
        except Exception:
            uri = None
    if not uri:
        raise RuntimeError("MONGODB_URI required for E2E seed")
    name = os.environ.get("MONGODB_DATABASE", "zahcci_e2e")
    return get_database_from_uri(uri, name)


def seed_database() -> None:
    from vaybooks.bms.application.customer_app_service import CustomerAppService
    from vaybooks.bms.application.vendor_app_service import VendorAppService
    from vaybooks.bms.infrastructure.repositories.mongo_accounting_repository import (
        MongoAccountRepository,
    )
    from vaybooks.bms.infrastructure.repositories.mongo_customer_repository import (
        MongoCustomerRepository,
    )
    from vaybooks.bms.infrastructure.repositories.mongo_vendor_repository import (
        MongoVendorRepository,
    )

    db = _db()
    ensure_indexes(db)

    for coll in ("customers", "vendors", "accounts"):
        db[coll].delete_many({})

    customer_repo = MongoCustomerRepository(db)
    vendor_repo = MongoVendorRepository(db)
    account_repo = MongoAccountRepository(db)
    customers = CustomerAppService(customer_repo, account_repo)
    vendors = VendorAppService(vendor_repo, account_repo)

    customers.create_customer(
        CustomerInput(customer_name="Alpha E2E", phone_number="9000000101")
    )
    customers.create_customer(
        CustomerInput(customer_name="Beta E2E", phone_number="9000000102")
    )
    customers.create_customer(
        CustomerInput(
            customer_name="Gamma GST E2E",
            phone_number="9000000103",
            registration_type=PartyRegistrationType.REGISTERED,
            gstin="27AAAAA0000A1Z5",
            pan="AAAAA0000A",
            state_code="27",
        )
    )
    vendors.create_vendor(
        VendorInput(vendor_name="Alpha Vendor E2E", phone_number="9100000101")
    )
    vendors.create_vendor(
        VendorInput(vendor_name="Beta Vendor E2E", phone_number="9100000102")
    )
