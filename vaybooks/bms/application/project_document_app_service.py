from __future__ import annotations

from typing import List, Optional

from vaybooks.bms.domain.projects.entities import ProjectDocument
from vaybooks.bms.domain.projects.repository import (
    ProjectDocumentRepository,
    ProjectRepository,
)
from vaybooks.bms.domain.shared.enums import ProjectDocumentCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectDocumentAppService:
    def __init__(
        self,
        document_repo: ProjectDocumentRepository,
        project_repo: ProjectRepository,
    ):
        self._document_repo = document_repo
        self._project_repo = project_repo

    def _ensure_project(self, project_id: str) -> None:
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")

    def upload(
        self,
        project_id: str,
        category: str,
        name: str,
        content_type: str,
        data: bytes,
        uploaded_by: str = "",
    ) -> ProjectDocument:
        self._ensure_project(project_id)
        if not (name or "").strip():
            raise ValidationError("Document name is required")
        if not data:
            raise ValidationError("Document data is required")
        document = ProjectDocument(
            project_id=project_id,
            category=ProjectDocumentCategory(category),
            name=(name or "").strip(),
            content_type=content_type or "application/octet-stream",
            data=data,
            size_bytes=len(data),
            uploaded_by=(uploaded_by or "").strip(),
        )
        return self._document_repo.save(document)

    def list_by_project(
        self,
        project_id: str,
        include_deleted: bool = False,
        category: Optional[str] = None,
        include_data: bool = False,
    ) -> List[ProjectDocument]:
        cat = ProjectDocumentCategory(category) if category else None
        documents = self._document_repo.list_by_project(
            project_id,
            include_deleted=include_deleted,
            category=cat,
        )
        if include_data:
            return documents
        return [
            ProjectDocument(
                id=doc.id,
                project_id=doc.project_id,
                category=doc.category,
                name=doc.name,
                content_type=doc.content_type,
                data=b"",
                size_bytes=doc.size_bytes,
                uploaded_by=doc.uploaded_by,
                source_ref_type=doc.source_ref_type,
                source_ref_id=doc.source_ref_id,
                is_deleted=doc.is_deleted,
                deleted_at=doc.deleted_at,
                uploaded_at=doc.uploaded_at,
            )
            for doc in documents
        ]

    def download(self, document_id: str) -> ProjectDocument:
        document = self._document_repo.find_by_id(document_id)
        if not document or document.is_deleted:
            raise ValidationError("Document not found")
        return document

    def soft_delete(self, document_id: str) -> None:
        document = self._document_repo.find_by_id(document_id)
        if not document or document.is_deleted:
            raise ValidationError("Document not found")
        self._document_repo.soft_delete(document_id)

    def register_generated_pdf(
        self,
        project_id: str,
        name: str,
        pdf_bytes: bytes,
        category: str,
        source_ref_type: str = "",
        source_ref_id: str = "",
        uploaded_by: str = "",
    ) -> ProjectDocument:
        """Stub: persist a system-generated PDF linked to a billing/quotation ref."""
        self._ensure_project(project_id)
        document = ProjectDocument(
            project_id=project_id,
            category=ProjectDocumentCategory(category),
            name=(name or "").strip(),
            content_type="application/pdf",
            data=pdf_bytes,
            size_bytes=len(pdf_bytes),
            uploaded_by=(uploaded_by or "").strip(),
            source_ref_type=(source_ref_type or "").strip(),
            source_ref_id=(source_ref_id or "").strip(),
        )
        return self._document_repo.save(document)
