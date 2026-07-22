"""Enquiry and site assessment application service."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.projects.enquiry import ProjectEnquiry, ProjectSiteAssessment
from vaybooks.bms.domain.projects.entities import Project
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectEnquiryStatus, ProjectStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectEnquiryAppService:
    def __init__(
        self,
        enquiry_repo,
        project_repo,
        counter_repo,
        customer_repo=None,
    ):
        self._enquiry_repo = enquiry_repo
        self._project_repo = project_repo
        self._counter_repo = counter_repo
        self._customer_repo = customer_repo

    def _get(self, enquiry_id: str) -> ProjectEnquiry:
        enquiry = self._enquiry_repo.find_by_id(enquiry_id)
        if not enquiry:
            raise ValidationError("Enquiry not found")
        return enquiry

    def create_enquiry(
        self,
        customer_id: str,
        *,
        site_address: str = "",
        site_state_code: str = "",
        requirement: str = "",
        source: str = "",
        expected_start: Optional[date] = None,
        expected_end: Optional[date] = None,
        internal_notes: str = "",
        customer_notes: str = "",
    ) -> ProjectEnquiry:
        customer_name = ""
        if self._customer_repo:
            customer = self._customer_repo.find_by_id(customer_id)
            if not customer:
                raise ValidationError("Customer not found")
            customer_name = getattr(customer, "customer_name", "") or ""
        enquiry = ProjectEnquiry(
            enquiry_number=self._counter_repo.next("enquiry_number"),
            customer_id=customer_id,
            customer_name=customer_name,
            site_address=(site_address or "").strip(),
            site_state_code=(site_state_code or "").strip(),
            requirement=(requirement or "").strip(),
            source=(source or "").strip(),
            expected_start=expected_start,
            expected_end=expected_end,
            internal_notes=(internal_notes or "").strip(),
            customer_notes=(customer_notes or "").strip(),
        )
        return self._enquiry_repo.save(enquiry)

    def list_enquiries(
        self, status: Optional[ProjectEnquiryStatus] = None
    ) -> List[ProjectEnquiry]:
        return self._enquiry_repo.list_all(status=status)

    def get_enquiry(self, enquiry_id: str) -> ProjectEnquiry:
        return self._get(enquiry_id)

    def update_status(self, enquiry_id: str, status) -> ProjectEnquiry:
        enquiry = self._get(enquiry_id)
        if isinstance(status, str):
            status = ProjectEnquiryStatus(status)
        enquiry.status = status
        enquiry.updated_at = utc_now()
        return self._enquiry_repo.save(enquiry)

    def start_estimation(self, enquiry_id: str) -> Project:
        enquiry = self._get(enquiry_id)
        if enquiry.project_id:
            project = self._project_repo.find_by_id(enquiry.project_id)
            if project:
                if enquiry.status == ProjectEnquiryStatus.DRAFT:
                    enquiry.status = ProjectEnquiryStatus.ESTIMATING
                    enquiry.updated_at = utc_now()
                    self._enquiry_repo.save(enquiry)
                return project
        project = Project(
            project_number=self._counter_repo.next("project_number"),
            name=f"Enquiry {enquiry.enquiry_number}",
            customer_id=enquiry.customer_id,
            customer_name=enquiry.customer_name,
            site_address=enquiry.site_address,
            site_state_code=enquiry.site_state_code,
            notes=enquiry.requirement,
            status=ProjectStatus.DRAFT,
            enquiry_id=enquiry.id,
            start_date=enquiry.expected_start,
            expected_end_date=enquiry.expected_end,
        )
        project = self._project_repo.save(project)
        enquiry.project_id = project.id
        enquiry.status = ProjectEnquiryStatus.ESTIMATING
        enquiry.updated_at = utc_now()
        self._enquiry_repo.save(enquiry)
        return project

    def add_assessment(
        self,
        enquiry_id: str,
        *,
        visit_date: date,
        conditions: str = "",
        measurements_notes: str = "",
        access_notes: str = "",
        utilities_notes: str = "",
        risks: str = "",
        assumptions: str = "",
        recommended_scope: str = "",
        submit: bool = False,
    ) -> ProjectSiteAssessment:
        self._get(enquiry_id)
        assessment = ProjectSiteAssessment(
            enquiry_id=enquiry_id,
            visit_date=visit_date,
            conditions=(conditions or "").strip(),
            measurements_notes=(measurements_notes or "").strip(),
            access_notes=(access_notes or "").strip(),
            utilities_notes=(utilities_notes or "").strip(),
            risks=(risks or "").strip(),
            assumptions=(assumptions or "").strip(),
            recommended_scope=(recommended_scope or "").strip(),
            submitted_at=utc_now() if submit else None,
        )
        return self._enquiry_repo.save_assessment(assessment)

    def list_assessments(self, enquiry_id: str) -> List[ProjectSiteAssessment]:
        self._get(enquiry_id)
        return self._enquiry_repo.list_assessments(enquiry_id)

    def mark_won(self, enquiry_id: str) -> ProjectEnquiry:
        enquiry = self._get(enquiry_id)
        enquiry.status = ProjectEnquiryStatus.WON
        enquiry.updated_at = utc_now()
        return self._enquiry_repo.save(enquiry)

    def mark_won_for_project(self, project_id: str) -> Optional[ProjectEnquiry]:
        enquiry = self._enquiry_repo.find_by_project_id(project_id)
        if not enquiry:
            project = self._project_repo.find_by_id(project_id)
            if project and getattr(project, "enquiry_id", ""):
                enquiry = self._enquiry_repo.find_by_id(project.enquiry_id)
        if not enquiry:
            return None
        return self.mark_won(enquiry.id)

    def find_by_project(self, project_id: str) -> Optional[ProjectEnquiry]:
        return self._enquiry_repo.find_by_project_id(project_id)
