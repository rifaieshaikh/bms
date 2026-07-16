"""Sales document print formats, styles, and invoice copy behavior."""

import base64
from datetime import date
from io import BytesIO

import pytest
from PIL import Image

from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.shared.document_customization import (
    BankAccount,
    DocumentContentSnapshot,
    SalesPrintSettings,
    bank_account_from_dict,
    print_settings_from_dict,
)
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import (
    generate_sales_document_pdf,
)


DOCUMENT_TYPES = (
    "estimate",
    "quotation",
    "sales_order",
    "delivery_note",
    "sales_invoice",
)


def _document(document_type: str) -> dict:
    numbers = {
        "estimate": ("estimate_number", "EST-1"),
        "quotation": ("quotation_number", "QUO-1"),
        "sales_order": ("so_number", "SO-1"),
        "delivery_note": ("dn_number", "DN-1"),
        "sales_invoice": ("store_invoice_number", "INV-1"),
    }
    dates = {
        "estimate": "estimate_date",
        "quotation": "quotation_date",
        "sales_order": "order_date",
        "delivery_note": "delivery_date",
        "sales_invoice": "sale_date",
    }
    number_key, number = numbers[document_type]
    return {
        number_key: number,
        dates[document_type]: date(2026, 7, 15),
        "customer_name": "Test Customer",
        "items": [
            {
                "item_name": "Kurta",
                "hsn_sac": "6205",
                "qty": 2,
                "rate": 100,
                "discount": 10,
                "taxable_amount": 190,
                "gst_rate": 5,
                "cgst_amount": 4.75,
                "sgst_amount": 4.75,
                "line_total": 199.5,
            }
        ],
        "total_amount": 199.5,
    }


@pytest.mark.parametrize("document_type", DOCUMENT_TYPES)
@pytest.mark.parametrize("paper", ["A4", "A5", "Letter", "80mm", "58mm"])
def test_every_sales_document_supports_every_paper_format(document_type, paper):
    pdf = generate_sales_document_pdf(
        document_type,
        _document(document_type),
        BusinessProfile(legal_name="Test Business"),
        SalesPrintSettings(paper_size=paper),
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


@pytest.mark.parametrize("style", ["classic", "modern", "compact"])
def test_invoice_supports_multiple_designs(style):
    pdf = generate_sales_document_pdf(
        "sales_invoice",
        _document("sales_invoice"),
        BusinessProfile(legal_name="Test Business"),
        SalesPrintSettings(template_style=style),
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_combined_invoice_generates_each_configured_copy_as_a_page():
    settings = SalesPrintSettings(
        invoice_copy_mode="combined",
        invoice_copy_labels=["Original", "Duplicate", "Office Copy"],
        default_invoice_copy="Original",
    )
    pdf = generate_sales_document_pdf(
        "sales_invoice",
        _document("sales_invoice"),
        BusinessProfile(legal_name="Test Business"),
        settings,
    )
    assert pdf.count(b"/Type /Page") == 4  # Three pages plus the /Pages node.


def test_select_invoice_mode_generates_only_requested_copy():
    settings = SalesPrintSettings(
        invoice_copy_mode="select",
        invoice_copy_labels=["Original", "Duplicate"],
        default_invoice_copy="Original",
    )
    pdf = generate_sales_document_pdf(
        "sales_invoice",
        _document("sales_invoice"),
        BusinessProfile(legal_name="Test Business"),
        settings,
        copy_label="Duplicate",
    )
    assert pdf.count(b"/Type /Page") == 2  # One page plus the /Pages node.


def test_old_print_settings_receive_new_defaults():
    settings = print_settings_from_dict({"paper_size": "Letter"})
    assert settings.paper_size == "Letter"
    assert settings.template_style == "classic"
    assert settings.show_bank_qr is True
    assert settings.invoice_copy_mode == "select"
    assert settings.default_invoice_copy == "Original for Recipient"
    assert (
        print_settings_from_dict({"show_bank_details": False}).show_bank_qr
        is False
    )


def test_bank_qr_image_round_trips_and_renders_in_pdf():
    image = Image.new("RGB", (21, 21), "white")
    for position in range(0, 21, 2):
        image.putpixel((position, position), (0, 0, 0))
    output = BytesIO()
    image.save(output, format="PNG")
    qr_data = "data:image/png;base64," + base64.b64encode(
        output.getvalue()
    ).decode("ascii")
    account = bank_account_from_dict(
        {
            "account_name": "Primary account",
            "bank_name": "Test Bank",
            "qr_code_image": qr_data,
        }
    )

    assert account is not None
    assert account.qr_code_image == qr_data
    document = _document("sales_invoice")
    document["document_content"] = DocumentContentSnapshot(bank_account=account)
    pdf = generate_sales_document_pdf(
        "sales_invoice",
        document,
        BusinessProfile(legal_name="Test Business"),
        SalesPrintSettings(show_bank_details=True),
    )
    assert pdf.startswith(b"%PDF")
    assert b"/Subtype /Image" in pdf

    qr_only_pdf = generate_sales_document_pdf(
        "sales_invoice",
        document,
        BusinessProfile(legal_name="Test Business"),
        SalesPrintSettings(show_bank_details=False, show_bank_qr=True),
    )
    assert b"/Subtype /Image" in qr_only_pdf

    details_only_pdf = generate_sales_document_pdf(
        "sales_invoice",
        document,
        BusinessProfile(legal_name="Test Business"),
        SalesPrintSettings(show_bank_details=True, show_bank_qr=False),
    )
    assert b"/Subtype /Image" not in details_only_pdf
