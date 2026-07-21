"""Project enquiry and site assessment (commercial spine)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectEnquiryStatus


@dataclass
class ProjectSiteAssessment:
    enquiry_id: str
    visit_date: date
    conditions: str = ""
    measurements_notes: str = ""
    access_notes: str = ""
    utilities_notes: str = ""
    risks: str = ""
    assumptions: str = ""
    recommended_scope: str = ""
    attachment_ids: List[str] = field(default_factory=list)
    submitted_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectEnquiry:
    enquiry_number: str
    customer_id: str
    customer_name: str
    site_address: str = ""
    site_state_code: str = ""
    requirement: str = ""
    source: str = ""
    expected_start: Optional[date] = None
    expected_end: Optional[date] = None
    status: ProjectEnquiryStatus = ProjectEnquiryStatus.DRAFT
    project_id: Optional[str] = None
    internal_notes: str = ""
    customer_notes: str = ""
    confirmation_date: Optional[date] = None
    confirmation_note: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
