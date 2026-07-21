"""Pending-approval notification stub for projects (Wave 8)."""

from __future__ import annotations

from typing import List

from vaybooks.bms.domain.projects.offline import ProjectNotification
from vaybooks.bms.domain.shared.enums import (
    ProjectQuotationStatus,
    ProjectRABillStatus,
)


class ProjectNotificationAppService:
    def __init__(
        self,
        *,
        quotation_repo=None,
        ra_repo=None,
        project_repo=None,
    ):
        self._quotation_repo = quotation_repo
        self._ra_repo = ra_repo
        self._project_repo = project_repo

    def list_pending_approvals(self, user_id: str) -> List[ProjectNotification]:
        """Aggregate pending quotations and RA bills awaiting approval."""
        user_id = (user_id or "").strip()
        items: List[ProjectNotification] = []

        if self._quotation_repo and hasattr(self._quotation_repo, "list_all"):
            for quote in self._quotation_repo.list_all():
                status = getattr(quote, "status", None)
                if status == ProjectQuotationStatus.PENDING_APPROVAL or (
                    getattr(status, "value", status) == "Pending Approval"
                ):
                    items.append(
                        ProjectNotification(
                            user_id=user_id,
                            kind="quotation_approval",
                            title=f"Quotation {quote.quotation_number} pending approval",
                            project_id=quote.project_id,
                            ref_id=quote.id,
                            ref_type="quotation",
                        )
                    )

        if self._ra_repo and self._project_repo:
            projects = self._project_repo.list_all()
            for project in projects:
                for ra in self._ra_repo.list_by_project(project.id):
                    status = getattr(ra, "status", None)
                    if status == ProjectRABillStatus.SUBMITTED or (
                        getattr(status, "value", status) == "Submitted"
                    ):
                        ra_number = getattr(ra, "ra_number", None) or getattr(
                            ra, "bill_number", ra.id
                        )
                        items.append(
                            ProjectNotification(
                                user_id=user_id,
                                kind="ra_approval",
                                title=f"RA {ra_number} pending approval",
                                project_id=project.id,
                                ref_id=ra.id,
                                ref_type="ra_bill",
                            )
                        )

        return items
