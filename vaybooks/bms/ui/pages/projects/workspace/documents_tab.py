"""Documents tab — upload and manage project files."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectDocumentCategory
from vaybooks.bms.ui.pages.projects.workspace import helpers as H


def render_documents(services: dict, project) -> None:
    doc_svc = services.get("project_documents")
    if doc_svc is None:
        st.warning("Document service is not configured.")
        return

    categories = [c.value for c in ProjectDocumentCategory]
    filter_cat = st.selectbox(
        "Category filter",
        options=["All"] + categories,
        key="prj_doc_filter",
    )
    category_param = None if filter_cat == "All" else filter_cat

    st.subheader("Upload document")
    category = st.selectbox(
        "Category",
        options=categories,
        key="prj_doc_category",
    )
    uploaded = st.file_uploader("File", key="prj_doc_upload")
    if st.button("Upload", key="prj_doc_upload_btn", type="primary"):
        if not uploaded:
            st.error("Choose a file to upload")
        else:
            try:
                data = uploaded.getvalue()
                doc_svc.upload(
                    project.id,
                    category,
                    uploaded.name,
                    uploaded.type or "application/octet-stream",
                    data,
                )
                st.success("Document uploaded")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    try:
        documents = doc_svc.list_by_project(
            project.id,
            category=category_param,
        )
    except Exception as exc:
        st.error(str(exc))
        return

    if not documents:
        H.empty_state("No documents yet.")
        return

    for doc in documents:
        with st.container(border=True):
            cols = st.columns([3, 2, 1, 1])
            cols[0].write(f"**{doc.name}**")
            cols[1].caption(
                f"{doc.category.value} · {doc.size_bytes / 1024:.1f} KB"
                + (f" · ref {doc.source_ref_type}" if doc.source_ref_type else "")
            )
            if doc.source_ref_type:
                cols[1].caption(f"Source: {doc.source_ref_type} ({doc.source_ref_id or '—'})")
            if cols[2].button("Download", key=f"prj_doc_dl_{doc.id}"):
                try:
                    full = doc_svc.download(doc.id)
                    st.download_button(
                        "Save file",
                        data=full.data,
                        file_name=full.name,
                        mime=full.content_type,
                        key=f"prj_doc_save_{doc.id}",
                    )
                except Exception as exc:
                    st.error(str(exc))
            if cols[3].button("Delete", key=f"prj_doc_del_{doc.id}"):
                H.run_action(
                    lambda did=doc.id: doc_svc.soft_delete(did),
                    "Document deleted",
                )
