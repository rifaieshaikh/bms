from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.enquiry import ProjectEnquiry, ProjectSiteAssessment
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectEnquiryStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectEnquiryRepository:
    def __init__(self, db: Database):
        self._enquiries = db.project_enquiries
        self._assessments = db.project_site_assessments

    def _enquiry_to_doc(self, enquiry: ProjectEnquiry) -> dict:
        return {
            "_id": enquiry.id,
            "enquiry_number": enquiry.enquiry_number,
            "customer_id": enquiry.customer_id,
            "customer_name": enquiry.customer_name,
            "site_address": enquiry.site_address,
            "site_state_code": enquiry.site_state_code,
            "requirement": enquiry.requirement,
            "source": enquiry.source,
            "expected_start": to_bson_value(enquiry.expected_start),
            "expected_end": to_bson_value(enquiry.expected_end),
            "status": enquiry.status.value,
            "project_id": enquiry.project_id,
            "internal_notes": enquiry.internal_notes,
            "customer_notes": enquiry.customer_notes,
            "confirmation_date": to_bson_value(enquiry.confirmation_date),
            "confirmation_note": enquiry.confirmation_note,
            "created_at": enquiry.created_at,
            "updated_at": enquiry.updated_at,
        }

    def _enquiry_from_doc(self, doc: dict) -> ProjectEnquiry:
        return ProjectEnquiry(
            id=doc["_id"],
            enquiry_number=doc.get("enquiry_number", ""),
            customer_id=doc.get("customer_id", ""),
            customer_name=doc.get("customer_name", ""),
            site_address=doc.get("site_address", ""),
            site_state_code=doc.get("site_state_code", ""),
            requirement=doc.get("requirement", ""),
            source=doc.get("source", ""),
            expected_start=from_bson_date(doc.get("expected_start")),
            expected_end=from_bson_date(doc.get("expected_end")),
            status=ProjectEnquiryStatus(
                doc.get("status", ProjectEnquiryStatus.DRAFT.value)
            ),
            project_id=doc.get("project_id"),
            internal_notes=doc.get("internal_notes", ""),
            customer_notes=doc.get("customer_notes", ""),
            confirmation_date=from_bson_date(doc.get("confirmation_date")),
            confirmation_note=doc.get("confirmation_note", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _assessment_to_doc(self, assessment: ProjectSiteAssessment) -> dict:
        return {
            "_id": assessment.id,
            "enquiry_id": assessment.enquiry_id,
            "visit_date": to_bson_value(assessment.visit_date),
            "conditions": assessment.conditions,
            "measurements_notes": assessment.measurements_notes,
            "access_notes": assessment.access_notes,
            "utilities_notes": assessment.utilities_notes,
            "risks": assessment.risks,
            "assumptions": assessment.assumptions,
            "recommended_scope": assessment.recommended_scope,
            "attachment_ids": list(assessment.attachment_ids or []),
            "submitted_at": assessment.submitted_at,
            "created_at": assessment.created_at,
            "updated_at": assessment.updated_at,
        }

    def _assessment_from_doc(self, doc: dict) -> ProjectSiteAssessment:
        return ProjectSiteAssessment(
            id=doc["_id"],
            enquiry_id=doc["enquiry_id"],
            visit_date=from_bson_date(doc["visit_date"]),
            conditions=doc.get("conditions", ""),
            measurements_notes=doc.get("measurements_notes", ""),
            access_notes=doc.get("access_notes", ""),
            utilities_notes=doc.get("utilities_notes", ""),
            risks=doc.get("risks", ""),
            assumptions=doc.get("assumptions", ""),
            recommended_scope=doc.get("recommended_scope", ""),
            attachment_ids=list(doc.get("attachment_ids") or []),
            submitted_at=doc.get("submitted_at"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, enquiry: ProjectEnquiry) -> ProjectEnquiry:
        return self.save_enquiry(enquiry)

    def find_by_id(self, enquiry_id: str) -> Optional[ProjectEnquiry]:
        return self.find_enquiry_by_id(enquiry_id)

    def list_all(
        self, status: Optional[ProjectEnquiryStatus] = None
    ) -> List[ProjectEnquiry]:
        return self.list_enquiries(status=status)

    def find_by_project_id(self, project_id: str) -> Optional[ProjectEnquiry]:
        doc = self._enquiries.find_one({"project_id": project_id})
        return self._enquiry_from_doc(doc) if doc else None

    def list_assessments(self, enquiry_id: str) -> List[ProjectSiteAssessment]:
        return self.list_assessments_by_enquiry(enquiry_id)

    def save_enquiry(self, enquiry: ProjectEnquiry) -> ProjectEnquiry:
        enquiry.updated_at = utc_now()
        self._enquiries.replace_one(
            {"_id": enquiry.id}, self._enquiry_to_doc(enquiry), upsert=True
        )
        return enquiry

    def find_enquiry_by_id(self, enquiry_id: str) -> Optional[ProjectEnquiry]:
        doc = self._enquiries.find_one({"_id": enquiry_id})
        return self._enquiry_from_doc(doc) if doc else None

    def list_enquiries(
        self, status: Optional[ProjectEnquiryStatus] = None
    ) -> List[ProjectEnquiry]:
        query: dict = {}
        if status is not None:
            query["status"] = status.value if isinstance(status, ProjectEnquiryStatus) else status
        docs = self._enquiries.find(query).sort("created_at", -1)
        return [self._enquiry_from_doc(d) for d in docs]

    def save_assessment(self, assessment: ProjectSiteAssessment) -> ProjectSiteAssessment:
        assessment.updated_at = utc_now()
        self._assessments.replace_one(
            {"_id": assessment.id}, self._assessment_to_doc(assessment), upsert=True
        )
        return assessment

    def find_assessment_by_id(
        self, assessment_id: str
    ) -> Optional[ProjectSiteAssessment]:
        doc = self._assessments.find_one({"_id": assessment_id})
        return self._assessment_from_doc(doc) if doc else None

    def list_assessments_by_enquiry(
        self, enquiry_id: str
    ) -> List[ProjectSiteAssessment]:
        docs = self._assessments.find({"enquiry_id": enquiry_id}).sort("visit_date", -1)
        return [self._assessment_from_doc(d) for d in docs]
