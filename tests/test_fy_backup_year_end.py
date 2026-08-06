"""Tests for backup modes/retention and FY year-end migrate."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.finance.fy_year_end.service import (
    FyYearEndService,
    previous_fy_label,
)
from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.finance.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.finance.fy_close import (
    FY_MODE_BALANCES_ONLY,
    FY_MODE_FULL_PENDING,
    FY_STATUS_SUCCESS,
    FyCloseRecord,
)
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.infrastructure.backup.service import (
    BackupService,
    normalize_backup_mode,
    normalize_retention,
)
from tests.conftest import FakeAccountRepository, FakeCounterRepository, FakeVoucherRepository
from tests.test_sales_workflow import FakeBusinessService


class _FakeCollection:
    def __init__(self):
        self._docs = []

    def find(self, *args, **kwargs):
        return list(self._docs)

    def find_one(self, query=None, *args, **kwargs):
        query = query or {}
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def insert_one(self, doc):
        self._docs.append(doc)

    def delete_many(self, query):
        if not query:
            n = len(self._docs)
            self._docs.clear()
            return type("R", (), {"deleted_count": n})()
        return type("R", (), {"deleted_count": 0})()

    def replace_one(self, filt, doc, upsert=False):
        for i, existing in enumerate(self._docs):
            if existing.get("_id") == filt.get("_id"):
                self._docs[i] = doc
                return
        if upsert:
            self._docs.append(doc)

    def update_one(self, filt, update, upsert=False):
        doc = self.find_one(filt)
        if doc is None and upsert:
            doc = dict(filt)
            self._docs.append(doc)
        if doc is not None and "$set" in update:
            doc.update(update["$set"])

    def create_index(self, *args, **kwargs):
        return "idx"


class _FakeDB:
    def __init__(self):
        self._cols = {}

    def list_collection_names(self):
        return list(self._cols.keys())

    def __getitem__(self, name):
        if name not in self._cols:
            self._cols[name] = _FakeCollection()
        return self._cols[name]


class FakeFyCloseRepo:
    def __init__(self):
        self._store = {}

    def save(self, record: FyCloseRecord) -> FyCloseRecord:
        existing = self.find_by_pair(record.from_fy, record.to_fy)
        if existing:
            record.id = existing.id
        self._store[(record.from_fy, record.to_fy)] = record
        return record

    def find_by_pair(self, from_fy: str, to_fy: str):
        return self._store.get((from_fy, to_fy))

    def find_success_by_pair(self, from_fy: str, to_fy: str):
        row = self.find_by_pair(from_fy, to_fy)
        if row and row.status == FY_STATUS_SUCCESS:
            return row
        return None

    def last_success(self):
        rows = [r for r in self._store.values() if r.status == FY_STATUS_SUCCESS]
        return rows[-1] if rows else None

    def is_fy_closed(self, fy: str) -> bool:
        return any(
            r.from_fy == fy and r.status == FY_STATUS_SUCCESS
            for r in self._store.values()
        )


def test_normalize_backup_helpers():
    assert normalize_backup_mode("balances") == "balances"
    assert normalize_backup_mode("COMPLETE") == "complete"
    assert normalize_retention("keep_all") == "keep_all"
    assert normalize_retention(None) == "keep_one"


def test_backup_balances_exports_only_party_collections(monkeypatch):
    db = _FakeDB()
    db["customers"]._docs.append({"_id": "c1", "name": "A"})
    db["accounts"]._docs.append(
        {
            "_id": "a1",
            "account_name": "Cust",
            "current_balance": 10,
            "linked_customer_id": "c1",
        }
    )
    db["vouchers"]._docs.append({"_id": "v1"})
    db["system.indexes"]._docs.append({"_id": "sys"})

    from vaybooks.bms.infrastructure.config.settings import AppSettings

    monkeypatch.setattr(
        "vaybooks.bms.infrastructure.backup.service.get_settings",
        lambda: AppSettings(db_name="test"),
    )
    monkeypatch.setattr(
        "vaybooks.bms.infrastructure.backup.service.get_config_path",
        lambda: None,
    )

    service = BackupService(db)
    names = service.list_exportable_collections("balances")
    assert "customers" in names
    assert "accounts" in names
    assert "vouchers" not in names

    complete = service.list_exportable_collections("complete")
    assert "vouchers" in complete
    assert "system.indexes" not in complete

    zip_bytes = service.create_backup_zip("balances")
    assert zip_bytes[:2] == b"PK"


def test_apply_retention_keep_one(tmp_path, monkeypatch):
    db = _FakeDB()
    service = BackupService(db)
    monkeypatch.setenv("VAYBOOKS_DATA_DIR", str(tmp_path))
    backups = tmp_path / "data" / "backups"
    backups.mkdir(parents=True)
    older = backups / "backup_old.zip"
    newer = backups / "backup_new.zip"
    protected = backups / "pre_fy_close_2025-26.zip"
    upgrade = backups / "pre_upgrade_1.0.0.zip"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    protected.write_bytes(b"fy")
    upgrade.write_bytes(b"up")
    import os
    import time

    os.utime(older, (time.time() - 100, time.time() - 100))
    os.utime(newer, None)

    removed = service.apply_retention("keep_one", keep_path=newer)
    assert removed == 1
    assert newer.exists()
    assert not older.exists()
    assert protected.exists()
    assert upgrade.exists()
    assert service.apply_retention("keep_all") == 0


def test_previous_fy_label():
    assert previous_fy_label("2026-27") == "2025-26"


def test_fy_balances_only_sets_opening_and_locks():
    accounts = FakeAccountRepository()
    vouchers = FakeVoucherRepository()
    counters = FakeCounterRepository()
    cash = Account(
        account_name="Cash Drawer",
        account_type=AccountType.ASSET,
        opening_balance=0,
        current_balance=500,
        is_store_account=True,
    )
    accounts.save(cash)
    business = FakeBusinessService(
        BusinessProfile(fy_start_month=4, legal_name="Test")
    )
    accounting = AccountingAppService(accounts, vouchers, counters)
    accounting.set_business_service(business)
    fy_repo = FakeFyCloseRepo()
    accounting.set_fy_close_repo(fy_repo)
    fy = FyYearEndService(accounting, business, fy_repo)

    # Pretend we are in 2026-27 and prior is unclosed
    preview = fy.preview(FY_MODE_BALANCES_ONLY)
    assert preview["mode"] == FY_MODE_BALANCES_ONLY
    assert preview["account_count"] >= 1

    record = fy.migrate(FY_MODE_BALANCES_ONLY, backup_first=False)
    assert record.status == FY_STATUS_SUCCESS
    updated = accounts.find_by_id(cash.id)
    assert updated.opening_balance == 500

    with pytest.raises(ValueError, match="already been closed"):
        fy.migrate(FY_MODE_BALANCES_ONLY, backup_first=False)

    # Soft-lock: posting into closed from_fy should fail
    from_fy = record.from_fy
    accounting.set_fy_lock_bypass(False)
    with pytest.raises(ValueError, match="closed"):
        accounting.create_fy_system_journal(
            description="Should fail",
            lines=[
                {
                    "account_id": cash.id,
                    "account_name": cash.account_name,
                    "debit_amount": 1,
                    "credit_amount": 0,
                },
                {
                    "account_id": cash.id,
                    "account_name": cash.account_name,
                    "debit_amount": 0,
                    "credit_amount": 1,
                },
            ],
            voucher_date=date(2025, 6, 1),
            financial_year=from_fy,
        )


def test_fy_full_pending_net_zero_on_customer():
    accounts = FakeAccountRepository()
    vouchers = FakeVoucherRepository()
    counters = FakeCounterRepository()
    customer = Account(
        account_name="Customer - A",
        account_type=AccountType.ASSET,
        linked_customer_id="cust1",
        opening_balance=0,
        current_balance=100,
    )
    sales = Account(
        account_name="Sales",
        account_type=AccountType.REVENUE,
        current_balance=-100,
    )
    accounts.save(customer)
    accounts.save(sales)
    business = FakeBusinessService(BusinessProfile(fy_start_month=4))
    accounting = AccountingAppService(accounts, vouchers, counters)
    accounting.set_business_service(business)
    fy_repo = FakeFyCloseRepo()
    accounting.set_fy_close_repo(fy_repo)

    # Seed an open sales invoice
    inv = Voucher(
        voucher_number="INV-1",
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=datetime(2025, 8, 15),
        description="Open invoice",
        financial_year="2025-26",
        lines=[
            VoucherLine(
                account_id=customer.id,
                account_name=customer.account_name,
                debit_amount=100,
                credit_amount=0,
            ),
            VoucherLine(
                account_id=sales.id,
                account_name=sales.account_name,
                debit_amount=0,
                credit_amount=100,
                description="Sales invoice",
            ),
        ],
    )
    vouchers.save(inv)

    fy = FyYearEndService(accounting, business, fy_repo)
    before = customer.current_balance
    record = fy.migrate(FY_MODE_FULL_PENDING, backup_first=False)
    assert record.status == FY_STATUS_SUCCESS
    assert abs(accounts.find_by_id(customer.id).current_balance - before) < 0.01
    assert record.totals.get("receivable_count", 0) >= 1

    open_after = accounting.list_open_sales_invoices_for_customer(customer.id)
    old_still_open = [
        r
        for r in open_after
        if r.get("id") == inv.id and float(r.get("outstanding") or 0) > 0.01
    ]
    assert old_still_open == []
    assert any(r.get("id") != inv.id for r in open_after)


def test_fy_failed_close_can_retry():
    from vaybooks.bms.domain.finance.fy_close import FY_STATUS_FAILED

    accounts = FakeAccountRepository()
    vouchers = FakeVoucherRepository()
    counters = FakeCounterRepository()
    cash = Account(
        account_name="Cash Drawer",
        account_type=AccountType.ASSET,
        current_balance=10,
        is_store_account=True,
    )
    accounts.save(cash)
    business = FakeBusinessService(BusinessProfile(fy_start_month=4))
    accounting = AccountingAppService(accounts, vouchers, counters)
    accounting.set_business_service(business)
    fy_repo = FakeFyCloseRepo()
    accounting.set_fy_close_repo(fy_repo)
    fy = FyYearEndService(accounting, business, fy_repo)

    current = fy.current_fy()
    prior = previous_fy_label(current)
    fy_repo.save(
        FyCloseRecord(
            from_fy=prior,
            to_fy=current,
            mode=FY_MODE_BALANCES_ONLY,
            status=FY_STATUS_FAILED,
            error="boom",
        )
    )
    vouchers.save(
        Voucher(
            voucher_number="V1",
            voucher_type=VoucherType.JOURNAL,
            voucher_date=datetime(2025, 5, 1),
            description="prior",
            financial_year=prior,
            lines=[
                VoucherLine(
                    account_id=cash.id,
                    account_name=cash.account_name,
                    debit_amount=1,
                    credit_amount=0,
                ),
                VoucherLine(
                    account_id=cash.id,
                    account_name=cash.account_name,
                    debit_amount=0,
                    credit_amount=1,
                ),
            ],
        )
    )
    pending = fy.detect_pending_close()
    assert pending is not None
    record = fy.migrate(FY_MODE_BALANCES_ONLY, backup_first=False)
    assert record.status == FY_STATUS_SUCCESS
    assert fy_repo.find_by_pair(prior, current).status == FY_STATUS_SUCCESS
