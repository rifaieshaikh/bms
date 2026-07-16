"""Print settings — sales document content defaults and PDF designer."""

import base64
from io import BytesIO
from uuid import uuid4

import pandas as pd
import streamlit as st
from PIL import Image, UnidentifiedImageError

from vaybooks.bms.domain.shared.document_customization import (
    DOCUMENT_TYPES,
    BankAccount,
    CustomFieldDefinition,
    DocumentTemplateSettings,
    PolicySection,
)
from vaybooks.bms.ui.components.print_settings import render_print_settings

_LABELS = {
    "estimate": "Estimate",
    "quotation": "Quotation",
    "sales_order": "Sales Order",
    "delivery_note": "Delivery Note",
    "sales_invoice": "Sales Invoice",
}

_BANK_COLUMNS = [
    "id",
    "account_name",
    "bank_name",
    "account_number",
    "ifsc",
    "branch",
    "upi_or_note",
    "qr_code_image",
    "is_active",
]

_FIELD_COLUMNS = [
    "key",
    "label",
    "field_type",
    "required",
    "default_value",
    "print_visible",
    "display_order",
]

_POLICY_COLUMNS = ["title", "content", "print_visible", "display_order"]


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _flag(value, default: bool = True) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return bool(value)


def _order(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _qr_image_data(uploaded) -> str:
    if uploaded.size > 2 * 1024 * 1024:
        raise ValueError("QR image must be 2 MB or smaller.")
    try:
        image = Image.open(BytesIO(uploaded.getvalue()))
        image.verify()
        image = Image.open(BytesIO(uploaded.getvalue())).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Upload a valid PNG or JPEG QR image.") from exc
    output = BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(
        "ascii"
    )


def _bank_accounts_editor(business) -> list[BankAccount]:
    st.markdown(":material/account_balance: **Bank accounts**")
    st.caption("Add rows with the + button below the table.")
    frame = pd.DataFrame(
        [
            {
                "id": item.id,
                "account_name": item.account_name,
                "bank_name": item.bank_name,
                "account_number": item.account_number,
                "ifsc": item.ifsc,
                "branch": item.branch,
                "upi_or_note": item.upi_or_note,
                "qr_code_image": item.qr_code_image or None,
                "is_active": item.is_active,
            }
            for item in business.bank_accounts
        ],
        columns=_BANK_COLUMNS,
    ).astype({"is_active": "bool"})
    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="business_bank_accounts",
        column_config={
            "id": None,
            "account_name": st.column_config.TextColumn(
                "Account name", required=True
            ),
            "bank_name": st.column_config.TextColumn("Bank"),
            "account_number": st.column_config.TextColumn("Account number"),
            "ifsc": st.column_config.TextColumn("IFSC"),
            "branch": st.column_config.TextColumn("Branch"),
            "upi_or_note": st.column_config.TextColumn("UPI / note"),
            "qr_code_image": st.column_config.ImageColumn(
                "QR", help="Upload or change it in the Payment QR code section below."
            ),
            "is_active": st.column_config.CheckboxColumn(
                "Active", default=True
            ),
        },
    )
    new_ids = st.session_state.setdefault("print_settings_new_bank_ids", {})
    existing = {item.id: item for item in business.bank_accounts}
    accounts = [
        BankAccount(
            id=_text(row.get("id"))
            or new_ids.setdefault(str(index), uuid4().hex),
            account_name=_text(row.get("account_name")),
            bank_name=_text(row.get("bank_name")),
            account_number=_text(row.get("account_number")),
            ifsc=_text(row.get("ifsc")).upper(),
            branch=_text(row.get("branch")),
            upi_or_note=_text(row.get("upi_or_note")),
            qr_code_image=(
                existing[_text(row.get("id"))].qr_code_image
                if _text(row.get("id")) in existing
                else ""
            ),
            is_active=_flag(row.get("is_active")),
        )
        for index, row in enumerate(edited.to_dict("records"))
        if _text(row.get("account_name"))
    ]
    with st.container(border=True):
        st.markdown(":material/qr_code_2: **Payment QR code**")
        if not accounts:
            st.info(
                "Add a bank account above (with an account name) to attach "
                "a payment QR image."
            )
            return accounts
        controls_col, preview_col = st.columns([1.6, 1], gap="large")
        with controls_col:
            selected_id = st.selectbox(
                "Bank account",
                [item.id for item in accounts],
                format_func=lambda account_id: next(
                    item.account_name for item in accounts if item.id == account_id
                ),
                key="print_settings_qr_account",
            )
            selected = next(item for item in accounts if item.id == selected_id)
            uploaded = st.file_uploader(
                "Upload QR image (UPI / bank payment QR)",
                type=["png", "jpg", "jpeg"],
                key=f"bank_qr_upload_{selected_id}",
                help=(
                    "PNG or JPEG, up to 2 MB. A square QR image gives the "
                    "best result. Click 'Save document defaults' below to store it."
                ),
            )
            remove = (
                st.checkbox(
                    "Remove saved QR image",
                    key=f"bank_qr_remove_{selected_id}",
                )
                if selected.qr_code_image and uploaded is None
                else False
            )
            if uploaded is not None:
                try:
                    selected.qr_code_image = _qr_image_data(uploaded)
                except ValueError as exc:
                    st.error(str(exc))
            elif remove:
                selected.qr_code_image = ""
        with preview_col:
            if selected.qr_code_image:
                st.image(
                    selected.qr_code_image,
                    caption=f"{selected.account_name} payment QR",
                    width=170,
                )
            else:
                st.caption("No QR image attached to this account yet.")

    for account in accounts:
        upload = st.session_state.get(f"bank_qr_upload_{account.id}")
        remove_saved = st.session_state.get(f"bank_qr_remove_{account.id}", False)
        if upload is not None:
            try:
                account.qr_code_image = _qr_image_data(upload)
            except ValueError:
                pass
        elif remove_saved:
            account.qr_code_image = ""
    return accounts


def _custom_fields_editor(document_type: str, current) -> list[CustomFieldDefinition]:
    st.markdown(":material/list_alt: **Custom fields**")
    frame = pd.DataFrame(
        [
            {
                "key": item.key,
                "label": item.label,
                "field_type": item.field_type,
                "required": item.required,
                "default_value": item.default_value,
                "print_visible": item.print_visible,
                "display_order": item.display_order,
            }
            for item in current.custom_fields
        ],
        columns=_FIELD_COLUMNS,
    ).astype({"required": "bool", "print_visible": "bool", "display_order": "int64"})
    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"custom_fields_{document_type}",
        column_config={
            "key": st.column_config.TextColumn("Key", required=True),
            "label": st.column_config.TextColumn("Label"),
            "field_type": st.column_config.SelectboxColumn(
                "Type",
                options=["text", "multiline", "number", "date", "checkbox"],
                default="text",
            ),
            "required": st.column_config.CheckboxColumn(
                "Required", default=False
            ),
            "default_value": st.column_config.TextColumn("Default value"),
            "print_visible": st.column_config.CheckboxColumn(
                "Print", default=True
            ),
            "display_order": st.column_config.NumberColumn(
                "Order", default=0, step=1
            ),
        },
    )
    return [
        CustomFieldDefinition(
            key=_text(row.get("key")),
            label=_text(row.get("label")),
            field_type=_text(row.get("field_type")) or "text",
            required=_flag(row.get("required"), default=False),
            default_value=_text(row.get("default_value")),
            print_visible=_flag(row.get("print_visible")),
            display_order=_order(row.get("display_order")),
        )
        for row in edited.to_dict("records")
        if _text(row.get("key"))
    ]


def _policies_editor(document_type: str, current) -> list[PolicySection]:
    st.markdown(":material/policy: **Policies**")
    frame = pd.DataFrame(
        [
            {
                "title": item.title,
                "content": item.content,
                "print_visible": item.print_visible,
                "display_order": item.display_order,
            }
            for item in current.policies
        ],
        columns=_POLICY_COLUMNS,
    ).astype({"print_visible": "bool", "display_order": "int64"})
    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"policies_{document_type}",
        column_config={
            "title": st.column_config.TextColumn("Title", required=True),
            "content": st.column_config.TextColumn("Content", width="large"),
            "print_visible": st.column_config.CheckboxColumn(
                "Print", default=True
            ),
            "display_order": st.column_config.NumberColumn(
                "Order", default=0, step=1
            ),
        },
    )
    return [
        PolicySection(
            title=_text(row.get("title")),
            content=_text(row.get("content")),
            print_visible=_flag(row.get("print_visible")),
            display_order=_order(row.get("display_order")),
        )
        for row in edited.to_dict("records")
        if _text(row.get("title"))
    ]


def _render_document_defaults(services: dict, business) -> None:
    st.caption(
        "Bank accounts, custom fields, terms and policies available while "
        "creating each sales document."
    )
    bank_accounts = _bank_accounts_editor(business)
    account_ids = [""] + [item.id for item in bank_accounts if item.is_active]
    account_names = {item.id: item.account_name for item in bank_accounts}
    templates = {}
    tabs = st.tabs([_LABELS[name] for name in DOCUMENT_TYPES])
    for tab, document_type in zip(tabs, DOCUMENT_TYPES):
        current = business.document_templates[document_type]
        with tab:
            default_id = current.default_bank_account_id
            default_index = (
                account_ids.index(default_id) if default_id in account_ids else 0
            )
            default_bank = st.selectbox(
                "Default bank account",
                account_ids,
                index=default_index,
                format_func=lambda item_id: (
                    "None" if not item_id else account_names.get(item_id, item_id)
                ),
                key=f"default_bank_{document_type}",
            )
            terms = st.text_area(
                "Terms & Conditions",
                value=current.terms_and_conditions,
                key=f"terms_{document_type}",
            )
            custom_fields = _custom_fields_editor(document_type, current)
            policies = _policies_editor(document_type, current)
            templates[document_type] = DocumentTemplateSettings(
                print_settings=current.print_settings,
                custom_fields=custom_fields,
                default_bank_account_id=default_bank,
                terms_and_conditions=terms,
                policies=policies,
            )
    if st.button(
        "Save document defaults",
        type="primary",
        icon=":material/save:",
        key="save_document_defaults",
    ):
        try:
            services["business"].update_document_settings(
                bank_accounts=bank_accounts,
                document_templates=templates,
            )
            st.success("Document defaults saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render(services: dict):
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page("print_settings")
    st.title("Print Settings")
    business = services["business"].get_profile()
    designer_tab, defaults_tab = st.tabs(
        [
            ":material/palette: Print designer",
            ":material/tune: Content defaults",
        ]
    )
    with designer_tab:
        render_print_settings(services, business)
    with defaults_tab:
        _render_document_defaults(services, business)
