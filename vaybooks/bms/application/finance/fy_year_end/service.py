"""Financial year end close and carry-forward."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.finance.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.finance.accounting.settlement import (
    ALLOC_INVOICE_TAG,
    PAYMENT_TOLERANCE,
    append_meta,
)
from vaybooks.bms.domain.finance.fy_close import (
    FY_CARRY_FORWARD_TAG,
    FY_CLEARING_ACCOUNT_NAME,
    FY_MODE_BALANCES_ONLY,
    FY_MODE_FULL_PENDING,
    FY_MODES,
    FY_OPENING_TAG,
    FY_STATUS_FAILED,
    FY_STATUS_SUCCESS,
    FyCloseRecord,
)
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.domain.shared.financial_year import resolve_financial_year
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.repositories.finance.mongo_fy_close_repository import (
    MongoFyCloseRepository,
)

logger = logging.getLogger("vaybooks.bms.fy")


def fy_start_date(fy_label: str, start_month: int = 4) -> date:
    """Return the calendar start date for an FY label like ``2026-27``."""
    start_year = int(str(fy_label).split("-")[0])
    month = int(start_month or 4)
    if month < 1 or month > 12:
        month = 4
    return date(start_year, month, 1)


def previous_fy_label(fy_label: str) -> str:
    start_year = int(str(fy_label).split("-")[0])
    prev = start_year - 1
    return f"{prev}-{str(start_year)[-2:]}"


class FyYearEndService:
    def __init__(
        self,
        accounting,
        business_service,
        fy_close_repo: MongoFyCloseRepository,
        *,
        inventory_service=None,
    ):
        self._accounting = accounting
        self._business = business_service
        self._repo = fy_close_repo
        self._inventory = inventory_service

    def _fy_start_month(self) -> int:
        profile = self._business.get_profile()
        try:
            month = int(getattr(profile, "fy_start_month", 4) or 4)
        except (TypeError, ValueError):
            month = 4
        return month if 1 <= month <= 12 else 4

    def current_fy(self, on: Optional[date] = None) -> str:
        return resolve_financial_year(on or date.today(), self._fy_start_month())

    def last_close(self) -> Optional[FyCloseRecord]:
        return self._repo.last_success()

    def is_fy_closed(self, fy: str) -> bool:
        return self._repo.is_fy_closed(fy)

    def detect_pending_close(self) -> Optional[Dict[str, str]]:
        """If current FY has no successful close from previous FY and prior has activity."""
        current = self.current_fy()
        prior = previous_fy_label(current)
        if self._is_pair_successfully_closed(prior, current):
            return None
        if not self._prior_fy_has_activity(prior):
            return None
        return {"from_fy": prior, "to_fy": current}

    def _is_pair_successfully_closed(self, from_fy: str, to_fy: str) -> bool:
        finder = getattr(self._repo, "find_success_by_pair", None)
        if callable(finder):
            return finder(from_fy, to_fy) is not None
        existing = self._repo.find_by_pair(from_fy, to_fy)
        return bool(existing and existing.status == FY_STATUS_SUCCESS)

    def _prior_fy_has_activity(self, prior_fy: str) -> bool:
        try:
            vouchers = self._accounting.list_vouchers()
        except Exception:
            vouchers = []
        for voucher in vouchers or []:
            fy = (getattr(voucher, "financial_year", None) or "").strip()
            if fy == prior_fy:
                return True
            v_date = getattr(voucher, "voucher_date", None)
            if v_date is not None:
                try:
                    if self._accounting.resolve_voucher_financial_year(
                        v_date.date() if hasattr(v_date, "date") else v_date
                    ) == prior_fy:
                        return True
                except Exception:
                    continue
        return False

    def preview(self, mode: str = FY_MODE_BALANCES_ONLY) -> Dict[str, Any]:
        mode = self._normalize_mode(mode)
        pending = self.detect_pending_close()
        if not pending:
            current = self.current_fy()
            pending = {
                "from_fy": previous_fy_label(current),
                "to_fy": current,
            }
        accounts = self._accounting.list_accounts(active_only=False)
        snapshots = []
        total_abs = 0.0
        for acc in accounts:
            bal = round(float(getattr(acc, "current_balance", 0) or 0), 2)
            if abs(bal) < PAYMENT_TOLERANCE:
                continue
            snapshots.append(
                {
                    "account_id": acc.id,
                    "account_name": acc.account_name,
                    "account_type": getattr(acc.account_type, "value", acc.account_type),
                    "balance": bal,
                    "linked_customer_id": getattr(acc, "linked_customer_id", None),
                    "linked_vendor_id": getattr(acc, "linked_vendor_id", None),
                }
            )
            total_abs += abs(bal)

        receivables: List[Dict[str, Any]] = []
        payables: List[Dict[str, Any]] = []
        if mode == FY_MODE_FULL_PENDING:
            receivables = self._collect_open_receivables()
            payables = self._collect_vendor_payables()

        return {
            "from_fy": pending["from_fy"],
            "to_fy": pending["to_fy"],
            "mode": mode,
            "account_count": len(snapshots),
            "balance_abs_total": round(total_abs, 2),
            "accounts": snapshots,
            "pending_receivables": receivables,
            "pending_payables": payables,
            "receivable_count": len(receivables),
            "payable_count": len(payables),
            "receivable_total": round(
                sum(float(r.get("outstanding") or 0) for r in receivables), 2
            ),
            "payable_total": round(
                sum(float(p.get("payable") or 0) for p in payables), 2
            ),
            "already_closed": self._is_pair_successfully_closed(
                pending["from_fy"], pending["to_fy"]
            ),
        }

    def migrate(
        self,
        mode: str = FY_MODE_BALANCES_ONLY,
        *,
        backup_first: bool = True,
    ) -> FyCloseRecord:
        mode = self._normalize_mode(mode)
        preview = self.preview(mode)
        from_fy = preview["from_fy"]
        to_fy = preview["to_fy"]
        existing = self._repo.find_by_pair(from_fy, to_fy)
        if existing and existing.status == FY_STATUS_SUCCESS:
            raise ValueError(
                f"Financial year {from_fy} has already been closed into {to_fy}"
            )

        backup_path = ""
        if backup_first and is_desktop():
            try:
                from vaybooks.bms.infrastructure.backup.service import BackupService
                from vaybooks.bms.infrastructure.db.connection import get_database

                path = BackupService(get_database()).save_backup_to_disk(
                    label=f"pre_fy_close_{from_fy}",
                    mode="complete",
                )
                backup_path = str(path) if path else ""
            except Exception:
                logger.exception("Pre-FY-close backup failed; continuing migrate")

        created_ids: List[str] = []
        opening_backup: List[Dict[str, Any]] = []
        bypass = getattr(self._accounting, "set_fy_lock_bypass", None)
        if callable(bypass):
            bypass(True)
        try:
            if mode == FY_MODE_FULL_PENDING:
                created_ids.extend(
                    self._carry_open_receivables(preview["pending_receivables"], to_fy)
                )
                created_ids.extend(
                    self._carry_vendor_payables(preview["pending_payables"], to_fy)
                )

            # Reconcile before mutating opening_balance so failure is clean.
            self._reconcile_after_migrate(preview["accounts"])
            opening_backup = self._snapshot_opening_balances(preview["accounts"])

            record = FyCloseRecord(
                from_fy=from_fy,
                to_fy=to_fy,
                mode=mode,
                status=FY_STATUS_SUCCESS,
                backup_path=backup_path,
                totals={
                    "account_count": preview["account_count"],
                    "balance_abs_total": preview["balance_abs_total"],
                    "receivable_count": preview["receivable_count"],
                    "payable_count": preview["payable_count"],
                    "receivable_total": preview["receivable_total"],
                    "payable_total": preview["payable_total"],
                    "carry_voucher_ids": created_ids,
                },
                account_snapshots=preview["accounts"],
                pending_receivables=preview["pending_receivables"],
                pending_payables=preview["pending_payables"],
            )
            if existing and existing.status != FY_STATUS_SUCCESS:
                record.id = existing.id
            return self._repo.save(record)
        except Exception as exc:
            logger.exception("FY migrate failed")
            for voucher_id in reversed(created_ids):
                try:
                    self._accounting._domain.reverse_and_delete_voucher(voucher_id)
                except Exception:
                    logger.exception("Rollback voucher %s failed", voucher_id)
            if opening_backup:
                self._restore_opening_balances(opening_backup)
            failed = FyCloseRecord(
                from_fy=from_fy,
                to_fy=to_fy,
                mode=mode,
                status=FY_STATUS_FAILED,
                backup_path=backup_path,
                error=str(exc),
                totals={"carry_voucher_ids": created_ids},
            )
            if existing:
                failed.id = existing.id
            try:
                self._repo.save(failed)
            except Exception:
                pass
            raise
        finally:
            if callable(bypass):
                bypass(False)

    def _normalize_mode(self, mode: str) -> str:
        value = (mode or FY_MODE_BALANCES_ONLY).strip().lower()
        if value not in FY_MODES:
            raise ValueError(
                f"Invalid FY migrate mode '{mode}'. Use balances_only or full_pending."
            )
        return value

    def _snapshot_opening_balances(
        self, snapshots: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Set account.opening_balance to closing balance; return prior values for rollback."""
        prior: List[Dict[str, Any]] = []
        for row in snapshots:
            account = self._accounting._account_repo.find_by_id(row["account_id"])
            if not account:
                continue
            prior.append(
                {
                    "account_id": account.id,
                    "opening_balance": float(getattr(account, "opening_balance", 0) or 0),
                }
            )
            bal = round(float(row.get("balance") or 0), 2)
            account.opening_balance = bal
            account.updated_at = datetime.utcnow()
            self._accounting._account_repo.save(account)
        return prior

    def _restore_opening_balances(self, prior: List[Dict[str, Any]]) -> None:
        for row in prior:
            account = self._accounting._account_repo.find_by_id(row["account_id"])
            if not account:
                continue
            account.opening_balance = round(float(row.get("opening_balance") or 0), 2)
            account.updated_at = datetime.utcnow()
            self._accounting._account_repo.save(account)

    def _collect_open_receivables(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for acc in self._accounting.list_accounts(active_only=False):
            if not getattr(acc, "linked_customer_id", None):
                continue
            open_invoices = self._accounting.list_open_sales_invoices_for_customer(
                acc.id
            )
            for inv in open_invoices:
                outstanding = round(float(inv.get("outstanding") or 0), 2)
                if outstanding <= PAYMENT_TOLERANCE:
                    continue
                sale_date = inv.get("sale_date")
                if isinstance(sale_date, datetime):
                    sale_date = sale_date.date()
                rows.append(
                    {
                        "invoice_id": inv.get("id"),
                        "voucher_number": inv.get("voucher_number") or "",
                        "customer_account_id": acc.id,
                        "customer_account_name": acc.account_name,
                        "customer_id": acc.linked_customer_id,
                        "sale_date": sale_date.isoformat()
                        if isinstance(sale_date, date)
                        else str(sale_date or ""),
                        "outstanding": outstanding,
                    }
                )
        return rows

    def _collect_vendor_payables(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for acc in self._accounting.list_accounts(active_only=False):
            if not getattr(acc, "linked_vendor_id", None):
                continue
            bal = round(float(getattr(acc, "current_balance", 0) or 0), 2)
            payable = abs(bal) if bal < -PAYMENT_TOLERANCE else 0.0
            if payable <= PAYMENT_TOLERANCE:
                continue
            rows.append(
                {
                    "vendor_account_id": acc.id,
                    "vendor_account_name": acc.account_name,
                    "vendor_id": acc.linked_vendor_id,
                    "payable": payable,
                }
            )
        return rows

    def _ensure_clearing_account(self) -> Account:
        for acc in self._accounting.list_accounts(active_only=False):
            if acc.account_name.strip().lower() == FY_CLEARING_ACCOUNT_NAME.lower():
                return acc
        return self._accounting.create_account(
            FY_CLEARING_ACCOUNT_NAME,
            AccountType.EQUITY.value,
            opening_balance=0,
        )

    def _carry_open_receivables(
        self, receivables: List[Dict[str, Any]], to_fy: str
    ) -> List[str]:
        """Settle old open invoices and reopen as carry-forward (net-zero balances)."""
        clearing = self._ensure_clearing_account()
        created: List[str] = []
        for row in receivables:
            outstanding = round(float(row.get("outstanding") or 0), 2)
            if outstanding <= PAYMENT_TOLERANCE:
                continue
            customer_id = row["customer_account_id"]
            customer_name = row["customer_account_name"]
            invoice_id = row.get("invoice_id") or ""
            raw_date = row.get("sale_date") or ""
            try:
                voucher_date = (
                    date.fromisoformat(raw_date)
                    if isinstance(raw_date, str) and raw_date
                    else date.today()
                )
            except ValueError:
                voucher_date = date.today()

            # 1) Close old outstanding against clearing (allocate to invoice).
            close_desc = append_meta(
                f"FY close settle invoice {row.get('voucher_number') or invoice_id}",
                FY_CARRY_FORWARD_TAG,
                {
                    "phase": "settle",
                    "to_fy": to_fy,
                    "carried_from_voucher_id": invoice_id,
                    "amount": outstanding,
                },
            )
            close_desc = append_meta(
                close_desc,
                ALLOC_INVOICE_TAG,
                {
                    "allocations": [{"invoice_id": invoice_id, "amount": outstanding}],
                    "unallocated": 0,
                },
            )
            close_voucher = self._accounting.create_fy_system_journal(
                description=close_desc,
                lines=[
                    {
                        "account_id": clearing.id,
                        "account_name": clearing.account_name,
                        "debit_amount": outstanding,
                        "credit_amount": 0,
                        "description": "FY settle AR",
                    },
                    {
                        "account_id": customer_id,
                        "account_name": customer_name,
                        "debit_amount": 0,
                        "credit_amount": outstanding,
                        "description": "FY settle AR",
                    },
                ],
                voucher_date=voucher_date,
                financial_year=to_fy,
            )
            created.append(close_voucher.id)

            # 2) Reopen as carry-forward invoice dated the same day.
            open_desc = append_meta(
                f"FY opening receivable from {row.get('voucher_number') or invoice_id}",
                FY_CARRY_FORWARD_TAG,
                {
                    "phase": "open",
                    "to_fy": to_fy,
                    "carried_from_voucher_id": invoice_id,
                    "amount": outstanding,
                },
            )
            open_desc = append_meta(
                open_desc,
                FY_OPENING_TAG,
                {"to_fy": to_fy, "kind": "receivable"},
            )
            open_voucher = self._accounting.create_fy_carry_sales_invoice(
                customer_account_id=customer_id,
                customer_account_name=customer_name,
                clearing_account_id=clearing.id,
                clearing_account_name=clearing.account_name,
                amount=outstanding,
                voucher_date=voucher_date,
                description=open_desc,
                financial_year=to_fy,
                carried_from_voucher_id=invoice_id,
            )
            created.append(open_voucher.id)
        return created

    def _carry_vendor_payables(
        self, payables: List[Dict[str, Any]], to_fy: str
    ) -> List[str]:
        clearing = self._ensure_clearing_account()
        created: List[str] = []
        start = fy_start_date(to_fy, self._fy_start_month())
        # Use day before new FY start as the "same prior FY" payable date anchor
        # when we only have balance-level payables (no open bill list).
        prior_date = start.fromordinal(start.toordinal() - 1)
        for row in payables:
            payable = round(float(row.get("payable") or 0), 2)
            if payable <= PAYMENT_TOLERANCE:
                continue
            vendor_id = row["vendor_account_id"]
            vendor_name = row["vendor_account_name"]

            # Settle: Dr Vendor / Cr Clearing (reduces liability magnitude when
            # vendor balance is credit/negative under debit-positive convention).
            # Vendor LIABILITY: credit increases payable; debit decreases.
            # current_balance for vendor payable is negative (credit).
            # To clear: Debit vendor (reduces credit balance toward 0).
            settle_desc = append_meta(
                f"FY close settle vendor payable {vendor_name}",
                FY_CARRY_FORWARD_TAG,
                {
                    "phase": "settle_payable",
                    "to_fy": to_fy,
                    "amount": payable,
                    "vendor_account_id": vendor_id,
                },
            )
            settle = self._accounting.create_fy_system_journal(
                description=settle_desc,
                lines=[
                    {
                        "account_id": vendor_id,
                        "account_name": vendor_name,
                        "debit_amount": payable,
                        "credit_amount": 0,
                        "description": "FY settle AP",
                    },
                    {
                        "account_id": clearing.id,
                        "account_name": clearing.account_name,
                        "debit_amount": 0,
                        "credit_amount": payable,
                        "description": "FY settle AP",
                    },
                ],
                voucher_date=prior_date,
                financial_year=to_fy,
            )
            created.append(settle.id)

            open_desc = append_meta(
                f"FY opening payable {vendor_name}",
                FY_CARRY_FORWARD_TAG,
                {
                    "phase": "open_payable",
                    "to_fy": to_fy,
                    "amount": payable,
                    "vendor_account_id": vendor_id,
                },
            )
            open_desc = append_meta(
                open_desc,
                FY_OPENING_TAG,
                {"to_fy": to_fy, "kind": "payable"},
            )
            reopen = self._accounting.create_fy_system_journal(
                description=open_desc,
                lines=[
                    {
                        "account_id": clearing.id,
                        "account_name": clearing.account_name,
                        "debit_amount": payable,
                        "credit_amount": 0,
                        "description": "FY open AP",
                    },
                    {
                        "account_id": vendor_id,
                        "account_name": vendor_name,
                        "debit_amount": 0,
                        "credit_amount": payable,
                        "description": "FY open AP",
                    },
                ],
                voucher_date=prior_date,
                financial_year=to_fy,
            )
            created.append(reopen.id)
        return created

    def _reconcile_after_migrate(self, before: List[Dict[str, Any]]) -> None:
        by_id = {row["account_id"]: round(float(row["balance"]), 2) for row in before}
        for account_id, expected in by_id.items():
            account = self._accounting._account_repo.find_by_id(account_id)
            if not account:
                continue
            actual = round(float(account.current_balance or 0), 2)
            if abs(actual - expected) > PAYMENT_TOLERANCE:
                raise ValueError(
                    f"Balance mismatch after FY migrate for {account.account_name}: "
                    f"expected {expected}, got {actual}"
                )
