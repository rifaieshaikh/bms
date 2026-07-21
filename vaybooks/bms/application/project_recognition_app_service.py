from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.projects.entities import ProjectExpense
from vaybooks.bms.domain.projects.recognition import (
    ProjectReconcileException,
    ProjectRecognitionEntry,
    ProjectReconciliation,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectCostCategory,
    ProjectExpenseSource,
    ProjectRecognitionMethod,
    ProjectRecognitionStatus,
    ProjectReconcileStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectRecognitionAppService:
    def __init__(
        self,
        recognition_repo,
        project_repo,
        *,
        accounting_service=None,
        expense_repo=None,
    ):
        self._repo = recognition_repo
        self._project_repo = project_repo
        self._accounting = accounting_service
        self._expense_repo = expense_repo

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _get_entry(self, entry_id: str) -> ProjectRecognitionEntry:
        entry = self._repo.find_entry_by_id(entry_id)
        if not entry:
            raise ValidationError("Recognition entry not found")
        return entry

    def _compute_wip(
        self,
        *,
        method: ProjectRecognitionMethod,
        contract_value: float,
        percent_complete: float,
        total_cost: float,
        billed_to_date: float,
        prior_recognised: float,
        estimated_total_cost: float = 0.0,
    ) -> dict:
        contract = float(contract_value or 0.0)
        billed = float(billed_to_date or 0.0)
        prior = float(prior_recognised or 0.0)
        if method == ProjectRecognitionMethod.PERCENT_COMPLETE:
            recognised_to_date = contract * (float(percent_complete or 0.0) / 100.0)
        elif method == ProjectRecognitionMethod.COST:
            etc = float(estimated_total_cost or 0.0)
            if etc <= 0:
                etc = float(total_cost or 0.0)
            if etc <= 0:
                recognised_to_date = 0.0
            else:
                recognised_to_date = contract * (float(total_cost or 0.0) / etc)
        else:
            recognised_to_date = billed
        recognised_to_date = round(recognised_to_date, 2)
        current = round(recognised_to_date - prior, 2)
        diff = round(recognised_to_date - billed, 2)
        unbilled = max(diff, 0.0)
        deferred = max(-diff, 0.0)
        return {
            "current_recognised": current,
            "wip_adjustment": diff,
            "unbilled_revenue": unbilled,
            "deferred_revenue": deferred,
        }

    def _build_journal_lines(self, entry: ProjectRecognitionEntry) -> List[dict]:
        """Balanced WIP / Revenue lines (AC-010). Reverse when unbilled is cleared."""
        amount = round(float(entry.current_recognised or 0.0), 2)
        reverse = False
        if abs(amount) < 0.01:
            if float(entry.deferred_revenue or 0.0) > 0.01:
                amount = round(float(entry.deferred_revenue), 2)
                reverse = True
            elif float(entry.unbilled_revenue or 0.0) > 0.01:
                amount = round(float(entry.unbilled_revenue), 2)
            else:
                amount = round(abs(float(entry.wip_adjustment or 0.0)), 2)
                reverse = float(entry.wip_adjustment or 0.0) < 0
        elif amount < 0:
            amount = abs(amount)
            reverse = True
        amount = round(amount, 2)
        if amount < 0.01:
            return []
        if reverse:
            return [
                {
                    "account_name": "Revenue",
                    "debit_amount": amount,
                    "credit_amount": 0.0,
                    "description": "Reverse unbilled / deferred recognition",
                },
                {
                    "account_name": "WIP",
                    "debit_amount": 0.0,
                    "credit_amount": amount,
                    "description": "Reverse unbilled / deferred recognition",
                },
            ]
        return [
            {
                "account_name": "WIP",
                "debit_amount": amount,
                "credit_amount": 0.0,
                "description": "Recognise WIP / unbilled revenue",
            },
            {
                "account_name": "Revenue",
                "debit_amount": 0.0,
                "credit_amount": amount,
                "description": "Recognise WIP / unbilled revenue",
            },
        ]

    def _resolve_account(self, preferred_names: List[str], fallback=None):
        if not self._accounting:
            return None
        for name in preferred_names:
            getter = getattr(self._accounting, "get_account_by_name", None)
            if getter:
                acct = getter(name)
                if acct:
                    return acct
        return fallback

    def _post_journal(
        self, entry: ProjectRecognitionEntry
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        lines = self._build_journal_lines(entry)
        stub: Dict[str, Any] = {
            "description": f"Project recognition {entry.id}",
            "project_id": entry.project_id,
            "period_end": str(entry.period_end),
            "lines": [
                {
                    "account_name": ln["account_name"],
                    "debit_amount": ln["debit_amount"],
                    "credit_amount": ln["credit_amount"],
                    "description": ln.get("description", ""),
                }
                for ln in lines
            ],
            "balanced": True,
            "posted_via": "stub",
        }
        if not lines:
            stub["posted_via"] = "noop"
            return "", stub

        if not self._accounting or not hasattr(
            self._accounting, "create_journal_entry"
        ):
            return "", stub

        sales = None
        if hasattr(self._accounting, "get_sales_account"):
            sales = self._accounting.get_sales_account()
        wip_acct = self._resolve_account(
            ["WIP", "Work in Progress", "Unbilled Revenue"],
            fallback=None,
        )
        rev_acct = self._resolve_account(
            ["Revenue", "Sales", "Contract Revenue"],
            fallback=sales,
        )
        if not wip_acct or not rev_acct:
            stub["posted_via"] = "stub_missing_accounts"
            return "", stub

        name_to_acct = {"WIP": wip_acct, "Revenue": rev_acct}
        voucher_lines = []
        for ln in lines:
            acct = name_to_acct[ln["account_name"]]
            voucher_lines.append(
                {
                    "account_id": acct.id,
                    "account_name": getattr(acct, "account_name", ln["account_name"]),
                    "debit_amount": ln["debit_amount"],
                    "credit_amount": ln["credit_amount"],
                    "description": ln.get("description", ""),
                }
            )
        voucher = self._accounting.create_journal_entry(
            description=stub["description"],
            lines=voucher_lines,
            voucher_date=entry.period_end,
        )
        stub["posted_via"] = "accounting"
        stub["voucher_id"] = getattr(voucher, "id", "") or ""
        stub["voucher_number"] = getattr(voucher, "voucher_number", "") or ""
        return stub["voucher_id"] or stub["voucher_number"], stub

    def draft_recognition(
        self,
        project_id: str,
        period_end: date,
        method,
        *,
        percent_complete: float = 0.0,
        total_cost: float = 0.0,
        billed_to_date: float = 0.0,
        prior_recognised: float = 0.0,
        estimated_total_cost: float = 0.0,
        notes: str = "",
        idempotency_key: str = "",
    ) -> ProjectRecognitionEntry:
        project = self._get_project(project_id)
        key = (idempotency_key or "").strip()
        if key:
            existing = self._repo.find_entry_by_idempotency_key(key)
            if existing:
                return existing
        if isinstance(method, str):
            method = ProjectRecognitionMethod(method)
        wip = self._compute_wip(
            method=method,
            contract_value=project.revised_contract_value or project.contract_value,
            percent_complete=percent_complete,
            total_cost=total_cost,
            billed_to_date=billed_to_date,
            prior_recognised=prior_recognised,
            estimated_total_cost=estimated_total_cost,
        )
        entry = ProjectRecognitionEntry(
            project_id=project_id,
            period_end=period_end,
            method=method,
            percent_complete=float(percent_complete or 0.0),
            total_cost=float(total_cost or 0.0),
            billed_to_date=float(billed_to_date or 0.0),
            prior_recognised=float(prior_recognised or 0.0),
            current_recognised=wip["current_recognised"],
            wip_adjustment=wip["wip_adjustment"],
            unbilled_revenue=wip["unbilled_revenue"],
            deferred_revenue=wip["deferred_revenue"],
            notes=(notes or "").strip(),
            idempotency_key=key,
        )
        return self._repo.save_entry(entry)

    def approve(self, entry_id: str) -> ProjectRecognitionEntry:
        entry = self._get_entry(entry_id)
        if entry.status != ProjectRecognitionStatus.DRAFT:
            raise ValidationError("Only draft recognition entries can be approved")
        entry.status = ProjectRecognitionStatus.APPROVED
        entry.updated_at = utc_now()
        return self._repo.save_entry(entry)

    def post(self, entry_id: str, voucher_id: str = "") -> ProjectRecognitionEntry:
        entry = self._get_entry(entry_id)
        if entry.status != ProjectRecognitionStatus.APPROVED:
            raise ValidationError("Only approved recognition entries can be posted")
        posted_voucher, stub = self._post_journal(entry)
        entry.status = ProjectRecognitionStatus.POSTED
        entry.voucher_id = (voucher_id or posted_voucher or "").strip()
        entry.journal_stub = stub
        entry.updated_at = utc_now()
        return self._repo.save_entry(entry)

    def allocate_overhead(self, project_id: str) -> dict:
        """Allocate HO overhead as % of direct project costs (Wave 8)."""
        project = self._get_project(project_id)
        pct = float(project.overhead_allocation_pct or 0.0)
        if pct <= 0:
            return {
                "project_id": project_id,
                "overhead_allocation_pct": pct,
                "base_cost": 0.0,
                "amount": 0.0,
                "expense_id": "",
            }
        base_cost = 0.0
        if self._expense_repo:
            for exp in self._expense_repo.list_by_project(project_id):
                cat = (getattr(exp, "cost_category", "") or "").strip()
                if cat in (
                    ProjectCostCategory.HO_OH.value,
                    ProjectCostCategory.SITE_OH.value,
                ):
                    continue
                base_cost += float(exp.amount or 0.0)
        amount = round(base_cost * pct / 100.0, 2)
        expense_id = ""
        if amount > 0 and self._expense_repo:
            expense = ProjectExpense(
                project_id=project_id,
                expense_date=date.today(),
                expense_name="Overhead allocation",
                expense_source=ProjectExpenseSource.OTHER,
                amount=amount,
                cost_category=ProjectCostCategory.HO_OH.value,
                notes=f"Allocated at {pct}% of direct costs ({base_cost})",
            )
            saved = self._expense_repo.save(expense)
            expense_id = saved.id
        return {
            "project_id": project_id,
            "overhead_allocation_pct": pct,
            "base_cost": round(base_cost, 2),
            "amount": amount,
            "expense_id": expense_id,
        }

    def list_entries(self, project_id: str) -> List[ProjectRecognitionEntry]:
        self._get_project(project_id)
        return self._repo.list_entries_by_project(project_id)

    def create_reconciliation(
        self,
        project_id: str,
        as_of: date,
        *,
        project_subledger: float = 0.0,
        gl_balance: float = 0.0,
        ar_balance: float = 0.0,
        ap_balance: float = 0.0,
        exceptions: Optional[List[dict]] = None,
        notes: str = "",
    ) -> ProjectReconciliation:
        self._get_project(project_id)
        exc_list: List[ProjectReconcileException] = []
        for row in exceptions or []:
            exc_list.append(
                ProjectReconcileException(
                    category=(row.get("category") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    amount=float(row.get("amount") or 0.0),
                    source_ref=(row.get("source_ref") or "").strip(),
                )
            )
        recon = ProjectReconciliation(
            project_id=project_id,
            as_of=as_of,
            project_subledger=float(project_subledger or 0.0),
            gl_balance=float(gl_balance or 0.0),
            ar_balance=float(ar_balance or 0.0),
            ap_balance=float(ap_balance or 0.0),
            exceptions=exc_list,
            notes=(notes or "").strip(),
        )
        return self._repo.save_reconciliation(recon)

    def approve_reconciliation(
        self, recon_id: str, signed_off_by: str = ""
    ) -> ProjectReconciliation:
        recon = self._repo.find_reconciliation_by_id(recon_id)
        if not recon:
            raise ValidationError("Reconciliation not found")
        if recon.status == ProjectReconcileStatus.APPROVED:
            raise ValidationError("Reconciliation is already approved and immutable")
        recon.status = ProjectReconcileStatus.APPROVED
        recon.signed_off_by = (signed_off_by or "").strip()
        recon.signed_off_at = utc_now()
        recon.updated_at = utc_now()
        return self._repo.save_reconciliation(recon)

    def list_reconciliations(self, project_id: str) -> List[ProjectReconciliation]:
        self._get_project(project_id)
        return self._repo.list_reconciliations_by_project(project_id)
