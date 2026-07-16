from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


DOCUMENT_TYPES = (
    "estimate",
    "quotation",
    "sales_order",
    "delivery_note",
    "sales_invoice",
)


@dataclass
class CustomFieldDefinition:
    key: str
    label: str
    field_type: str = "text"
    required: bool = False
    default_value: Any = ""
    print_visible: bool = True
    display_order: int = 0


@dataclass
class CustomFieldValue:
    key: str
    label: str
    field_type: str = "text"
    value: Any = ""
    print_visible: bool = True


@dataclass
class BankAccount:
    account_name: str
    bank_name: str = ""
    account_number: str = ""
    ifsc: str = ""
    branch: str = ""
    upi_or_note: str = ""
    qr_code_image: str = ""
    is_active: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class PolicySection:
    title: str
    content: str = ""
    print_visible: bool = True
    display_order: int = 0


@dataclass
class SalesPrintSettings:
    paper_size: str = "A4"
    orientation: str = "portrait"
    margin_mm: float = 10.0
    template_style: str = "classic"
    accent_color: str = "#1F4E78"
    font_size: str = "normal"
    show_logo: bool = True
    show_gst_columns: bool = True
    show_hsn_column: bool = True
    show_discount_column: bool = True
    show_amount_in_words: bool = True
    show_bank_details: bool = True
    show_bank_qr: bool = True
    show_terms: bool = True
    show_custom_fields: bool = True
    footer_text: str = ""
    show_signature: bool = True
    invoice_copy_mode: str = "select"
    invoice_copy_labels: list[str] = field(
        default_factory=lambda: [
            "Original for Recipient",
            "Duplicate for Transporter",
            "Triplicate for Supplier",
        ]
    )
    default_invoice_copy: str = "Original for Recipient"


@dataclass
class DocumentTemplateSettings:
    print_settings: SalesPrintSettings = field(default_factory=SalesPrintSettings)
    custom_fields: list[CustomFieldDefinition] = field(default_factory=list)
    default_bank_account_id: str = ""
    terms_and_conditions: str = ""
    policies: list[PolicySection] = field(default_factory=list)


@dataclass
class DocumentContentSnapshot:
    custom_fields: list[CustomFieldValue] = field(default_factory=list)
    bank_account: BankAccount | None = None
    terms_and_conditions: str = ""
    policies: list[PolicySection] = field(default_factory=list)


def default_document_templates() -> dict[str, DocumentTemplateSettings]:
    defaults = {
        "estimate": SalesPrintSettings(
            template_style="modern",
            accent_color="#2563EB",
            show_gst_columns=True,
            show_discount_column=False,
            footer_text="This estimate is subject to confirmation.",
        ),
        "quotation": SalesPrintSettings(
            template_style="modern",
            accent_color="#0F766E",
            show_gst_columns=True,
            show_discount_column=False,
            footer_text="Thank you for the opportunity to quote.",
        ),
        "sales_order": SalesPrintSettings(
            template_style="classic",
            accent_color="#7C3AED",
            show_gst_columns=True,
            show_discount_column=False,
        ),
        "delivery_note": SalesPrintSettings(
            template_style="compact",
            accent_color="#475569",
            show_gst_columns=False,
            show_discount_column=False,
            show_amount_in_words=False,
            show_bank_details=False,
            show_bank_qr=False,
            show_terms=False,
        ),
        "sales_invoice": SalesPrintSettings(
            template_style="classic",
            accent_color="#1F4E78",
            show_gst_columns=True,
            show_discount_column=True,
        ),
    }
    return {
        name: DocumentTemplateSettings(print_settings=defaults[name])
        for name in DOCUMENT_TYPES
    }


def dataclass_to_dict(value) -> dict:
    return asdict(value)


def print_settings_from_dict(raw: dict | None) -> SalesPrintSettings:
    raw = raw or {}
    copy_labels = [
        str(item).strip()
        for item in raw.get("invoice_copy_labels", [])
        if str(item).strip()
    ]
    if not copy_labels:
        copy_labels = [
            "Original for Recipient",
            "Duplicate for Transporter",
            "Triplicate for Supplier",
        ]
    return SalesPrintSettings(
        paper_size=str(raw.get("paper_size") or "A4"),
        orientation=str(raw.get("orientation") or "portrait"),
        margin_mm=float(raw.get("margin_mm") or 10),
        template_style=str(raw.get("template_style") or "classic"),
        accent_color=str(raw.get("accent_color") or "#1F4E78"),
        font_size=str(raw.get("font_size") or "normal"),
        show_logo=bool(raw.get("show_logo", True)),
        show_gst_columns=bool(raw.get("show_gst_columns", True)),
        show_hsn_column=bool(raw.get("show_hsn_column", True)),
        show_discount_column=bool(raw.get("show_discount_column", True)),
        show_amount_in_words=bool(raw.get("show_amount_in_words", True)),
        show_bank_details=bool(raw.get("show_bank_details", True)),
        show_bank_qr=bool(
            raw.get("show_bank_qr", raw.get("show_bank_details", True))
        ),
        show_terms=bool(raw.get("show_terms", True)),
        show_custom_fields=bool(raw.get("show_custom_fields", True)),
        footer_text=str(raw.get("footer_text") or ""),
        show_signature=bool(raw.get("show_signature", True)),
        invoice_copy_mode=str(raw.get("invoice_copy_mode") or "select"),
        invoice_copy_labels=copy_labels,
        default_invoice_copy=str(
            raw.get("default_invoice_copy") or copy_labels[0]
        ),
    )


def custom_field_definition_from_dict(raw: dict) -> CustomFieldDefinition:
    return CustomFieldDefinition(
        key=str(raw.get("key") or ""),
        label=str(raw.get("label") or ""),
        field_type=str(raw.get("field_type") or "text"),
        required=bool(raw.get("required", False)),
        default_value=raw.get("default_value", ""),
        print_visible=bool(raw.get("print_visible", True)),
        display_order=int(raw.get("display_order") or 0),
    )


def custom_field_value_from_dict(raw: dict) -> CustomFieldValue:
    return CustomFieldValue(
        key=str(raw.get("key") or ""),
        label=str(raw.get("label") or ""),
        field_type=str(raw.get("field_type") or "text"),
        value=raw.get("value", ""),
        print_visible=bool(raw.get("print_visible", True)),
    )


def bank_account_from_dict(raw: dict | None) -> BankAccount | None:
    if not raw:
        return None
    return BankAccount(
        id=str(raw.get("id") or uuid4().hex),
        account_name=str(raw.get("account_name") or ""),
        bank_name=str(raw.get("bank_name") or ""),
        account_number=str(raw.get("account_number") or ""),
        ifsc=str(raw.get("ifsc") or ""),
        branch=str(raw.get("branch") or ""),
        upi_or_note=str(raw.get("upi_or_note") or ""),
        qr_code_image=str(raw.get("qr_code_image") or ""),
        is_active=bool(raw.get("is_active", True)),
    )


def policy_from_dict(raw: dict) -> PolicySection:
    return PolicySection(
        title=str(raw.get("title") or ""),
        content=str(raw.get("content") or ""),
        print_visible=bool(raw.get("print_visible", True)),
        display_order=int(raw.get("display_order") or 0),
    )


def template_from_dict(raw: dict | None) -> DocumentTemplateSettings:
    raw = raw or {}
    return DocumentTemplateSettings(
        print_settings=print_settings_from_dict(raw.get("print_settings")),
        custom_fields=[
            custom_field_definition_from_dict(item)
            for item in raw.get("custom_fields", [])
        ],
        default_bank_account_id=str(raw.get("default_bank_account_id") or ""),
        terms_and_conditions=str(raw.get("terms_and_conditions") or ""),
        policies=[policy_from_dict(item) for item in raw.get("policies", [])],
    )


def snapshot_from_dict(raw: dict | None) -> DocumentContentSnapshot:
    raw = raw or {}
    return DocumentContentSnapshot(
        custom_fields=[
            custom_field_value_from_dict(item) for item in raw.get("custom_fields", [])
        ],
        bank_account=bank_account_from_dict(raw.get("bank_account")),
        terms_and_conditions=str(raw.get("terms_and_conditions") or ""),
        policies=[policy_from_dict(item) for item in raw.get("policies", [])],
    )
