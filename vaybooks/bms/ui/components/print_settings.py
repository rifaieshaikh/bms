"""Visual print settings editor with live PDF preview."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.document_customization import (
    DEFAULT_ACCENT_COLOR,
    DOCUMENT_TYPES,
    DocumentContentSnapshot,
    SalesPrintSettings,
    default_document_templates,
)
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import (
    generate_sales_document_pdf,
)


_LABELS = {
    "estimate": "Estimate",
    "quotation": "Quotation",
    "sales_order": "Sales Order",
    "delivery_note": "Delivery Note",
    "sales_invoice": "Sales Invoice",
    "measurement_sheet": "Measurement Sheet",
    "customization_item": "Customization Item",
    "advance_receipt": "Advance Receipt",
}

_ACCENTS = {name: DEFAULT_ACCENT_COLOR for name in _LABELS}

_STYLE_LABELS = {
    "classic": ":material/table_rows: Classic",
    "modern": ":material/gradient: Modern",
    "compact": ":material/density_small: Compact",
}

_FONT_LABELS = {
    "small": "Small",
    "normal": "Normal",
    "large": "Large",
}


def _sample_document(document_type: str, business) -> dict:
    if document_type in (
        "measurement_sheet",
        "customization_item",
        "advance_receipt",
    ):
        return {
            "document_type": document_type,
            "order_number": "CO-0001",
            "bill_number": "MS-0001-01",
            "measurement_number": "MS-0001",
            "voucher_number": "VCH-0001",
            "customer_name": "Sample Customer",
            "phone_number": "9876543210",
            "description": "Sample boutique document",
            "lines": [],
        }
    number_fields = {
        "estimate": ("estimate_number", "EST-2026-001"),
        "quotation": ("quotation_number", "QUO-2026-001"),
        "sales_order": ("so_number", "SO-2026-001"),
        "delivery_note": ("dn_number", "DN-2026-001"),
        "sales_invoice": ("store_invoice_number", "INV-2026-001"),
    }
    date_fields = {
        "estimate": "estimate_date",
        "quotation": "quotation_date",
        "sales_order": "order_date",
        "delivery_note": "delivery_date",
        "sales_invoice": "sale_date",
    }
    number_key, number = number_fields[document_type]
    account = next(
        (item for item in business.bank_accounts if item.is_active), None
    )
    lines = [
        {
            "item_name": "Premium Cotton Kurta",
            "hsn_sac": "6205",
            "qty": 2,
            "rate": 1250.0,
            "discount": 100.0,
            "taxable_amount": 2400.0,
            "gst_rate": 5.0,
            "cgst_amount": 60.0,
            "sgst_amount": 60.0,
            "igst_amount": 0.0,
            "line_total": 2520.0,
        },
        {
            "item_name": "Handloom Dupatta",
            "hsn_sac": "6214",
            "qty": 1,
            "rate": 850.0,
            "discount": 0.0,
            "taxable_amount": 850.0,
            "gst_rate": 5.0,
            "cgst_amount": 21.25,
            "sgst_amount": 21.25,
            "igst_amount": 0.0,
            "line_total": 892.5,
        },
        {
            "item_name": "Tailoring Service",
            "hsn_sac": "9988",
            "qty": 1,
            "rate": 500.0,
            "discount": 0.0,
            "taxable_amount": 500.0,
            "gst_rate": 18.0,
            "cgst_amount": 45.0,
            "sgst_amount": 45.0,
            "igst_amount": 0.0,
            "line_total": 590.0,
        },
    ]
    return {
        number_key: number,
        date_fields[document_type]: date.today(),
        "customer_name": "Aarav Retail Private Limited",
        "items": lines,
        "total_amount": 4002.5,
        "document_content": DocumentContentSnapshot(
            bank_account=account,
            terms_and_conditions=(
                "Payment is due within 15 days. Goods once sold will not be "
                "returned without prior approval."
            ),
        ),
    }


def _invoice_copy_controls(
    current: SalesPrintSettings, document_type: str
) -> tuple[str, list[str], str]:
    if document_type != "sales_invoice":
        return (
            current.invoice_copy_mode,
            list(current.invoice_copy_labels),
            current.default_invoice_copy,
        )
    with st.container(border=True):
        st.markdown(":material/content_copy: **Invoice copies**")
        mode = st.segmented_control(
            "Copy behavior",
            ["select", "combined"],
            default="combined" if current.invoice_copy_mode == "combined" else "select",
            format_func=lambda value: (
                "Choose at print time" if value == "select" else "All copies in one PDF"
            ),
            key="print_copy_mode_sales_invoice",
            width="stretch",
        ) or "select"
        rows = [{"Copy label": label} for label in current.invoice_copy_labels]
        edited = st.data_editor(
            rows,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key="print_copy_labels_sales_invoice",
            column_config={
                "Copy label": st.column_config.TextColumn(
                    "Copy label", required=True, width="large"
                )
            },
        )
        labels = [
            str(row.get("Copy label") or "").strip()
            for row in edited
            if str(row.get("Copy label") or "").strip()
        ] or ["Original for Recipient"]
        default = st.selectbox(
            "Default copy",
            labels,
            index=(
                labels.index(current.default_invoice_copy)
                if current.default_invoice_copy in labels
                else 0
            ),
            key="print_default_copy_sales_invoice",
            disabled=mode == "combined",
        )
    return mode, labels, default


def _layout_controls(
    document_type: str, current: SalesPrintSettings
) -> dict:
    style_options = list(_STYLE_LABELS)
    current_style = (
        current.template_style
        if current.template_style in style_options
        else style_options[0]
    )
    with st.container(border=True):
        st.markdown(":material/palette: **Design**")
        style = st.segmented_control(
            "Template",
            style_options,
            default=current_style,
            format_func=_STYLE_LABELS.get,
            key=f"print_style_{document_type}",
            width="stretch",
        ) or current_style
        paper_options = ["A4", "A5", "Letter", "80mm", "58mm"]
        paper = st.pills(
            "Paper size",
            paper_options,
            default=(
                current.paper_size
                if current.paper_size in paper_options
                else "A4"
            ),
            key=f"print_paper_{document_type}",
        ) or "A4"
        thermal = paper in {"80mm", "58mm"}
        orientation = st.segmented_control(
            "Orientation",
            ["portrait", "landscape"],
            default="portrait" if current.orientation == "portrait" else "landscape",
            format_func=str.title,
            key=f"print_orientation_{document_type}",
            disabled=thermal,
            width="stretch",
        ) or "portrait"
        font_size = st.segmented_control(
            "Text size",
            list(_FONT_LABELS),
            default=(
                current.font_size
                if current.font_size in _FONT_LABELS
                else "normal"
            ),
            format_func=_FONT_LABELS.get,
            key=f"print_font_{document_type}",
            width="stretch",
        ) or "normal"
        accent_col, margin_col = st.columns([1, 2], vertical_alignment="bottom")
        accent = accent_col.color_picker(
            "Accent",
            value=current.accent_color or _ACCENTS[document_type],
            key=f"print_accent_{document_type}",
        )
        margin = margin_col.slider(
            "Margin (mm)",
            min_value=2.0,
            max_value=30.0,
            value=float(current.margin_mm),
            step=1.0,
            key=f"print_margin_{document_type}",
        )
    return {
        "template_style": style,
        "paper_size": paper,
        "orientation": "portrait" if thermal else orientation,
        "font_size": font_size,
        "accent_color": accent,
        "margin_mm": margin,
    }


def _content_controls(document_type: str, current: SalesPrintSettings) -> dict:
    toggles = [
        ("show_logo", "Business logo / mark", current.show_logo),
        ("show_signature", "Signature", current.show_signature),
        ("show_gst_columns", "GST columns", current.show_gst_columns),
        ("show_hsn_column", "HSN/SAC", current.show_hsn_column),
        ("show_discount_column", "Discount", current.show_discount_column),
        ("show_amount_in_words", "Amount in words", current.show_amount_in_words),
        ("show_bank_details", "Bank details", current.show_bank_details),
        ("show_bank_qr", "Payment QR", current.show_bank_qr),
        ("show_terms", "Terms and policies", current.show_terms),
        ("show_custom_fields", "Custom fields", current.show_custom_fields),
    ]
    values: dict = {}
    with st.container(border=True):
        st.markdown(":material/visibility: **Visible content**")
        columns = st.columns(2)
        for position, (field, label, value) in enumerate(toggles):
            values[field] = columns[position % 2].toggle(
                label, value=value, key=f"print_{field}_{document_type}"
            )
        values["footer_text"] = st.text_area(
            "Footer text",
            value=current.footer_text,
            key=f"print_footer_{document_type}",
            height=68,
            placeholder="e.g. Thank you for your business!",
        )
    return values


def _settings_controls(
    document_type: str, current: SalesPrintSettings
) -> SalesPrintSettings:
    layout = _layout_controls(document_type, current)
    content = _content_controls(document_type, current)
    copy_mode, copy_labels, default_copy = _invoice_copy_controls(
        current, document_type
    )
    return SalesPrintSettings(
        **layout,
        **content,
        invoice_copy_mode=copy_mode,
        invoice_copy_labels=copy_labels,
        default_invoice_copy=default_copy,
    )


def _reset_widget_state(document_type: str) -> None:
    suffix = f"_{document_type}"
    for key in list(st.session_state):
        if key.startswith("print_") and key.endswith(suffix):
            del st.session_state[key]


def render_print_settings(services: dict, business) -> None:
    saved_label = st.session_state.pop("print_settings_saved", "")
    if saved_label:
        st.toast(f"{saved_label} print design saved.", icon=":material/check_circle:")
    st.caption(
        "Design each sales document and inspect the actual generated PDF "
        "before saving. Each document keeps its own design."
    )
    document_type = st.segmented_control(
        "Document",
        DOCUMENT_TYPES,
        default=DOCUMENT_TYPES[0],
        format_func=_LABELS.get,
        key="print_settings_document",
        label_visibility="collapsed",
        width="stretch",
    ) or DOCUMENT_TYPES[0]

    controls, preview = st.columns([0.85, 1.35], gap="large")
    with controls:
        if st.session_state.pop(f"print_use_defaults__{document_type}", False):
            current = default_document_templates()[document_type].print_settings
        else:
            current = business.document_templates[document_type].print_settings
        settings = _settings_controls(document_type, current)
        save_col, reset_col = st.columns([2, 1])
        if save_col.button(
            f"Save {_LABELS[document_type]} design",
            type="primary",
            key=f"save_print_settings_{document_type}",
            width="stretch",
            icon=":material/save:",
        ):
            templates = dict(business.document_templates)
            templates[document_type] = replace(
                templates[document_type], print_settings=settings
            )
            services["business"].update_document_settings(
                bank_accounts=list(business.bank_accounts),
                document_templates=templates,
            )
            st.session_state["print_settings_saved"] = _LABELS[document_type]
            st.rerun()
        if reset_col.button(
            "Reset",
            key=f"reset_print_settings_{document_type}",
            width="stretch",
            icon=":material/restart_alt:",
            help="Restore the default design for this document (not saved yet).",
        ):
            _reset_widget_state(document_type)
            st.session_state[f"print_use_defaults__{document_type}"] = True
            st.rerun()

    with preview:
        try:
            if document_type in (
                "measurement_sheet",
                "customization_item",
                "advance_receipt",
            ):
                from datetime import date
                from types import SimpleNamespace

                from vaybooks.bms.domain.shared.enums import (
                    FitPreference,
                    PersonType,
                )
                from vaybooks.bms.infrastructure.pdf.boutique_pdf import (
                    generate_advance_receipt_pdf,
                    generate_customization_item_pdf,
                    generate_measurement_sheet_pdf,
                )

                customer = SimpleNamespace(
                    customer_name="Sample Customer", phone_number="9876543210"
                )
                if document_type == "measurement_sheet":
                    record = SimpleNamespace(
                        measurement_number="MS-0001",
                        person_type=PersonType.WOMEN,
                        wearer_name="",
                        wearer_age="",
                        fit_preference=FitPreference.REGULAR,
                        measured_at=date.today(),
                        measured_by="Staff",
                        notes="Sample",
                        print_notes="",
                        values=[
                            SimpleNamespace(
                                field_key="bust", value="36", unit="inch"
                            ),
                            SimpleNamespace(
                                field_key="waist", value="30", unit="inch"
                            ),
                        ],
                    )
                    pdf_bytes = generate_measurement_sheet_pdf(
                        record, customer, business, settings
                    )
                elif document_type == "customization_item":
                    order = SimpleNamespace(
                        order_number="CO-0001",
                        customer_name="Sample Customer",
                        phone_number="9876543210",
                        expected_delivery_date=date.today(),
                        order_activities=[],
                    )
                    item = SimpleNamespace(
                        bill_number="MS-0001-01",
                        description="Blouse",
                        expected_delivery_date=date.today(),
                        customer_specification="Deep neck",
                        item_id="item1",
                    )
                    pdf_bytes = generate_customization_item_pdf(
                        order, item, customer, business, None, [], settings
                    )
                else:
                    order = SimpleNamespace(
                        order_number="CO-0001",
                        customer_name="Sample Customer",
                        phone_number="9876543210",
                        advance_amount=1000.0,
                    )
                    voucher = SimpleNamespace(
                        voucher_number="VCH-0001",
                        voucher_date=date.today(),
                        description="Advance for CO-0001",
                        lines=[],
                    )
                    pdf_bytes = generate_advance_receipt_pdf(
                        voucher, order, customer, business, settings
                    )
            else:
                pdf_bytes = generate_sales_document_pdf(
                    document_type,
                    _sample_document(document_type, business),
                    business,
                    settings,
                )
            st.pdf(pdf_bytes, height=760, key=f"pdf_preview_{document_type}")
            st.download_button(
                "Download preview",
                data=pdf_bytes,
                file_name=f"{document_type}-preview.pdf",
                mime="application/pdf",
                key=f"download_{document_type}_preview",
                icon=":material/download:",
            )
        except Exception as exc:
            st.error(f"Preview could not be generated: {exc}")
