from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

from fpdf import FPDF

from vaybooks.bms.domain.shared.document_customization import (
    DocumentContentSnapshot,
    SalesPrintSettings,
    snapshot_from_dict,
)


DOCUMENT_TITLES = {
    "estimate": "ESTIMATE",
    "quotation": "QUOTATION",
    "sales_order": "SALES ORDER",
    "delivery_note": "DELIVERY NOTE",
    "sales_invoice": "TAX INVOICE",
}


def _font_path() -> Path | None:
    candidates = (
        Path(__file__).parent / "fonts" / "DejaVuSans.ttf",
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    return next((path for path in candidates if path.exists()), None)


def _paper(settings: SalesPrintSettings, height: float | None = None):
    size = settings.paper_size.upper()
    if size == "80MM":
        return (80, height or 400)
    if size == "58MM":
        return (58, height or 400)
    if size == "LETTER":
        return "Letter"
    if size == "A5":
        return "A5"
    return "A4"


def _value(source: Any, name: str, default=""):
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _document_meta(document_type: str, document: Any) -> tuple[str, Any, str]:
    fields = {
        "estimate": ("estimate_number", "estimate_date"),
        "quotation": ("quotation_number", "quotation_date"),
        "sales_order": ("so_number", "order_date"),
        "delivery_note": ("dn_number", "delivery_date"),
        "sales_invoice": ("store_invoice_number", "sale_date"),
    }
    number_field, date_field = fields[document_type]
    return str(_value(document, number_field, "")), _value(document, date_field), date_field


def _line_rows(document_type: str, document: Any) -> list[dict]:
    raw_lines = _value(document, "lines", None)
    if raw_lines is None:
        raw_lines = _value(document, "items", [])
    rows = []
    for line in raw_lines or []:
        qty = (
            _value(line, "qty", None)
            or _value(line, "qty_ordered", None)
            or _value(line, "qty_delivered", 0)
        )
        name = (
            _value(line, "product_name", "")
            or _value(line, "item_name", "")
            or _value(line, "description", "")
        )
        rate = float(_value(line, "rate", 0) or 0)
        total = _value(line, "line_total", None)
        if total is None:
            total = round(float(qty or 0) * rate, 2)
        rows.append(
            {
                "name": str(name),
                "hsn_sac": str(_value(line, "hsn_sac", "") or ""),
                "qty": float(qty or 0),
                "rate": rate,
                "discount": float(_value(line, "discount", 0) or 0),
                "taxable": float(
                    _value(line, "taxable_amount", float(qty or 0) * rate) or 0
                ),
                "gst_rate": float(_value(line, "gst_rate", 0) or 0),
                "cgst": float(_value(line, "cgst_amount", 0) or 0),
                "sgst": float(_value(line, "sgst_amount", 0) or 0),
                "utgst": float(_value(line, "utgst_amount", 0) or 0),
                "igst": float(_value(line, "igst_amount", 0) or 0),
                "total": float(total or 0),
            }
        )
    return rows


def _document_content(document: Any) -> DocumentContentSnapshot:
    content = _value(document, "document_content", None)
    if isinstance(content, DocumentContentSnapshot):
        return content
    return snapshot_from_dict(content if isinstance(content, dict) else {})


def _configure_pdf(
    settings: SalesPrintSettings, *, height: float | None = None
) -> FPDF:
    orientation = "L" if settings.orientation.lower() == "landscape" else "P"
    pdf = FPDF(orientation=orientation, unit="mm", format=_paper(settings, height))
    pdf.set_margins(settings.margin_mm, settings.margin_mm, settings.margin_mm)
    pdf.set_auto_page_break(True, settings.margin_mm)
    font = _font_path()
    if font:
        pdf.add_font("DocumentUnicode", "", str(font))
        pdf.add_font("DocumentUnicode", "B", str(font))
        pdf._document_font = "DocumentUnicode"
    else:
        pdf._document_font = "Helvetica"
    return pdf


def _set_font(
    pdf: FPDF,
    settings: SalesPrintSettings,
    style: str = "",
    size: float = 9,
) -> None:
    scale = {"small": 0.86, "normal": 1.0, "large": 1.14}.get(
        settings.font_size, 1.0
    )
    pdf.set_font(pdf._document_font, style=style, size=max(size * scale, 6))


def _accent(settings: SalesPrintSettings) -> tuple[int, int, int]:
    value = (settings.accent_color or "#1F4E78").strip().lstrip("#")
    if len(value) != 6:
        return 31, 78, 120
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return 31, 78, 120


def _business_name(business: Any) -> str:
    return str(
        _value(business, "trade_name", "")
        or _value(business, "legal_name", "")
        or "Your Business"
    )


def _business_address(business: Any) -> str:
    return ", ".join(
        str(part)
        for part in (
            _value(business, "address_line1", ""),
            _value(business, "address_line2", ""),
            _value(business, "city", ""),
            _value(business, "state_code", ""),
            _value(business, "pincode", ""),
        )
        if part
    )


_ONES = (
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_TENS = (
    "",
    "",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
)


def _under_thousand(number: int) -> str:
    parts: list[str] = []
    if number >= 100:
        parts.append(f"{_ONES[number // 100]} Hundred")
        number %= 100
    if number >= 20:
        parts.append(_TENS[number // 10])
        number %= 10
    if number:
        parts.append(_ONES[number])
    return " ".join(parts)


def _amount_in_words(amount: float) -> str:
    rupees = int(round(float(amount or 0)))
    if rupees == 0:
        return "Zero Rupees Only"
    groups = (
        (10_000_000, "Crore"),
        (100_000, "Lakh"),
        (1_000, "Thousand"),
    )
    parts: list[str] = []
    remainder = rupees
    for divisor, label in groups:
        value, remainder = divmod(remainder, divisor)
        if value:
            parts.append(f"{_under_thousand(value)} {label}")
    if remainder:
        parts.append(_under_thousand(remainder))
    return f"{' '.join(parts)} Rupees Only"


def _render_header(
    pdf: FPDF,
    document_type: str,
    document: Any,
    business: Any,
    settings: SalesPrintSettings,
    copy_label: str,
) -> None:
    number, document_date, _ = _document_meta(document_type, document)
    title = DOCUMENT_TITLES[document_type]
    narrow = settings.paper_size.upper() in {"80MM", "58MM"}
    style = "thermal" if narrow else settings.template_style
    red, green, blue = _accent(settings)
    name = _business_name(business)
    initials = "".join(
        word[0].upper() for word in name.split()[:2] if word
    ) or "B"

    if style == "modern":
        pdf.set_fill_color(red, green, blue)
        pdf.rect(pdf.l_margin, pdf.get_y(), pdf.epw, 24, style="F")
        pdf.set_text_color(255, 255, 255)
        _set_font(pdf, settings, "B", 15)
        brand_width = pdf.epw * 0.62
        if settings.show_logo:
            pdf.cell(12, 9, initials, border=1, align="C")
            brand_width -= 12
        pdf.cell(
            brand_width,
            9,
            name[:45],
            new_x="RIGHT",
            new_y="TOP",
        )
        _set_font(pdf, settings, "B", 12)
        pdf.cell(
            pdf.epw * 0.38,
            9,
            title,
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        _set_font(pdf, settings, "", 7.5)
        pdf.cell(pdf.epw, 5, _business_address(business)[:110], new_x="LMARGIN", new_y="NEXT")
        gstin = _value(business, "gstin", "")
        pdf.cell(
            pdf.epw,
            5,
            f"GSTIN: {gstin}" if gstin else "",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)
    else:
        _set_font(pdf, settings, "B", 13 if not narrow else 10)
        heading = f"[{initials}]  {name}" if settings.show_logo else name
        pdf.cell(0, 7, heading, align="C", new_x="LMARGIN", new_y="NEXT")
        _set_font(pdf, settings, "", 7.5)
        address = _business_address(business)
        if address:
            pdf.multi_cell(0, 4, address, align="C", new_x="LMARGIN", new_y="NEXT")
        gstin = _value(business, "gstin", "")
        if gstin:
            pdf.cell(
                0,
                4,
                f"GSTIN: {gstin}",
                align="C",
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.set_draw_color(red, green, blue)
        pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
        pdf.ln(3)
        _set_font(pdf, settings, "B", 11 if not narrow else 9)
        pdf.cell(0, 6, title, align="C", new_x="LMARGIN", new_y="NEXT")

    if copy_label and document_type == "sales_invoice":
        _set_font(pdf, settings, "B", 7)
        pdf.set_text_color(red, green, blue)
        pdf.cell(0, 4, copy_label, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    customer = _value(document, "customer_name", "") or _value(
        document, "party_name", ""
    )
    _set_font(pdf, settings, "", 8)
    if narrow:
        pdf.cell(0, 4, f"No: {number}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 4, f"Date: {document_date}", new_x="LMARGIN", new_y="NEXT")
        if customer:
            pdf.multi_cell(0, 4, f"Customer: {customer}")
    else:
        top = pdf.get_y()
        pdf.cell(pdf.epw * 0.55, 5, f"Bill to: {customer or '-'}")
        pdf.set_xy(pdf.l_margin + pdf.epw * 0.58, top)
        pdf.cell(
            pdf.epw * 0.42,
            5,
            f"No: {number}",
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.cell(
            0,
            5,
            f"Date: {document_date}",
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.ln(2)


def _table_columns(
    rows: list[dict], settings: SalesPrintSettings
) -> list[tuple[str, str, float, str]]:
    columns: list[tuple[str, str, float, str]] = [
        ("index", "#", 0.05, "C"),
        ("name", "Item", 0.31, "L"),
    ]
    if settings.show_hsn_column:
        columns.append(("hsn_sac", "HSN", 0.09, "C"))
    columns.extend(
        [
            ("qty", "Qty", 0.07, "R"),
            ("rate", "Rate", 0.10, "R"),
        ]
    )
    if settings.show_discount_column and any(row["discount"] for row in rows):
        columns.append(("discount", "Disc.", 0.08, "R"))
    if settings.show_gst_columns:
        columns.extend(
            [
                ("taxable", "Taxable", 0.11, "R"),
                ("gst_rate", "GST %", 0.07, "R"),
            ]
        )
        if any(row["igst"] for row in rows):
            columns.append(("igst", "IGST", 0.09, "R"))
        else:
            columns.append(("cgst", "CGST", 0.08, "R"))
            if any(row["utgst"] for row in rows):
                columns.append(("utgst", "UTGST", 0.08, "R"))
            else:
                columns.append(("sgst", "SGST", 0.08, "R"))
    columns.append(("total", "Amount", 0.12, "R"))
    return columns


def _display_cell(key: str, value: Any) -> str:
    if key == "index":
        return str(value)
    if key == "name" or key == "hsn_sac":
        return str(value or "")
    if key == "qty":
        return f"{float(value or 0):g}"
    if key == "gst_rate":
        return f"{float(value or 0):g}%"
    return f"{float(value or 0):,.2f}"


def _render_lines(
    pdf: FPDF,
    document_type: str,
    document: Any,
    settings: SalesPrintSettings,
) -> list[dict]:
    rows = _line_rows(document_type, document)
    narrow = settings.paper_size.upper() in {"80MM", "58MM"}
    if narrow:
        for index, row in enumerate(rows, 1):
            _set_font(pdf, settings, "B", 7.5)
            pdf.multi_cell(0, 4, f"{index}. {row['name']}")
            _set_font(pdf, settings, "", 7.5)
            tax = row["cgst"] + row["sgst"] + row["utgst"] + row["igst"]
            detail = (
                f"{row['qty']:g} x {row['rate']:,.2f}"
                + (f"  GST {tax:,.2f}" if settings.show_gst_columns and tax else "")
                + f"   {row['total']:,.2f}"
            )
            pdf.cell(0, 4, detail, align="R", new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(210, 210, 210)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        return rows

    columns = _table_columns(rows, settings)
    total_weight = sum(item[2] for item in columns)
    widths = [pdf.epw * item[2] / total_weight for item in columns]
    red, green, blue = _accent(settings)
    modern = settings.template_style == "modern"
    compact = settings.template_style == "compact"
    pdf.set_fill_color(red, green, blue)
    pdf.set_text_color(255, 255, 255)
    _set_font(pdf, settings, "B", 6.5 if len(columns) > 8 else 7.5)
    for width, (_, label, _, _) in zip(widths, columns):
        pdf.cell(
            width,
            5 if compact else 6,
            label,
            border=0 if modern else 1,
            align="C",
            fill=True,
        )
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    _set_font(pdf, settings, "", 6.5 if len(columns) > 8 else 7.5)
    for index, row in enumerate(rows, 1):
        source = {"index": index, **row}
        if modern and index % 2 == 0:
            pdf.set_fill_color(242, 246, 250)
        for width, (key, _, _, align) in zip(widths, columns):
            text = _display_cell(key, source.get(key))
            max_chars = max(int(width / 1.8), 3)
            pdf.cell(
                width,
                4.5 if compact else 5.5,
                text[:max_chars],
                border=0 if modern else 1,
                align=align,
                fill=modern and index % 2 == 0,
            )
        pdf.ln()
    return rows


def _document_total(document: Any, rows: list[dict]) -> float:
    total = _value(document, "total_amount", None)
    if total is None:
        total = _value(document, "net", None)
    if total is None:
        total = sum(row["total"] for row in rows)
    return round(float(total or 0), 2)


def _render_totals(
    pdf: FPDF,
    document: Any,
    rows: list[dict],
    settings: SalesPrintSettings,
) -> float:
    total = _document_total(document, rows)
    narrow = settings.paper_size.upper() in {"80MM", "58MM"}
    taxable = sum(row["taxable"] for row in rows)
    cgst = sum(row["cgst"] for row in rows)
    sgst = sum(row["sgst"] for row in rows)
    utgst = sum(row["utgst"] for row in rows)
    igst = sum(row["igst"] for row in rows)
    pdf.ln(2)
    if settings.show_gst_columns and any((cgst, sgst, utgst, igst)):
        _set_font(pdf, settings, "", 7 if narrow else 8)
        parts = [f"Taxable: Rs. {taxable:,.2f}"]
        if igst:
            parts.append(f"IGST: Rs. {igst:,.2f}")
        else:
            if cgst:
                parts.append(f"CGST: Rs. {cgst:,.2f}")
            if sgst:
                parts.append(f"SGST: Rs. {sgst:,.2f}")
            if utgst:
                parts.append(f"UTGST: Rs. {utgst:,.2f}")
        pdf.multi_cell(0, 4, "  |  ".join(parts), align="R")
    red, green, blue = _accent(settings)
    pdf.set_text_color(red, green, blue)
    _set_font(pdf, settings, "B", 10 if not narrow else 9)
    pdf.cell(
        0,
        6,
        f"Grand Total: Rs. {total:,.2f}",
        align="R",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(0, 0, 0)
    if settings.show_amount_in_words and not narrow:
        _set_font(pdf, settings, "", 7.5)
        pdf.multi_cell(0, 4, f"Amount in words: {_amount_in_words(total)}")
    return total


def _render_content(
    pdf: FPDF,
    document: Any,
    business: Any,
    settings: SalesPrintSettings,
) -> None:
    narrow = settings.paper_size.upper() in {"80MM", "58MM"}
    content = _document_content(document)
    visible_fields = [
        field
        for field in content.custom_fields
        if field.print_visible and field.value not in ("", None)
    ]
    if settings.show_custom_fields and visible_fields:
        pdf.ln(2)
        _set_font(pdf, settings, "B", 8)
        pdf.cell(0, 5, "Additional details", new_x="LMARGIN", new_y="NEXT")
        _set_font(pdf, settings, "", 7.5)
        for field in visible_fields:
            pdf.multi_cell(0, 4, f"{field.label}: {field.value}")
    account = content.bank_account
    if settings.show_bank_details and account:
        pdf.ln(2)
        _set_font(pdf, settings, "B", 8)
        pdf.cell(0, 5, "Payment details", new_x="LMARGIN", new_y="NEXT")
        _set_font(pdf, settings, "", 7.5)
        bank_line = " | ".join(
            part
            for part in (
                account.account_name,
                account.bank_name,
                account.account_number,
                f"IFSC {account.ifsc}" if account.ifsc else "",
                account.upi_or_note,
            )
            if part
        )
        pdf.multi_cell(0, 4, bank_line)
    if settings.show_bank_qr and account and account.qr_code_image:
        try:
            encoded = account.qr_code_image.split(",", 1)[1]
            qr_image = BytesIO(base64.b64decode(encoded, validate=True))
            qr_size = 20 if narrow else 25
            if pdf.get_y() + qr_size + 8 > pdf.h - pdf.b_margin:
                pdf.add_page()
            pdf.ln(2)
            _set_font(pdf, settings, "", 7)
            pdf.cell(0, 4, "Scan to pay", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.image(
                qr_image,
                x=(pdf.w - qr_size) / 2,
                y=pdf.get_y(),
                w=qr_size,
                h=qr_size,
            )
            pdf.set_y(pdf.get_y() + qr_size + 2)
        except (ValueError, IndexError):
            pass
    if settings.show_terms and content.terms_and_conditions:
        pdf.ln(2)
        _set_font(pdf, settings, "B", 8)
        pdf.cell(0, 5, "Terms & Conditions", new_x="LMARGIN", new_y="NEXT")
        _set_font(pdf, settings, "", 7 if narrow else 7.5)
        pdf.multi_cell(0, 4, content.terms_and_conditions)
    if settings.show_terms:
        for policy in sorted(content.policies, key=lambda item: item.display_order):
            if policy.print_visible and policy.content:
                _set_font(pdf, settings, "B", 8)
                pdf.cell(0, 5, policy.title, new_x="LMARGIN", new_y="NEXT")
                _set_font(pdf, settings, "", 7 if narrow else 7.5)
                pdf.multi_cell(0, 4, policy.content)
    if settings.footer_text:
        pdf.ln(2)
        _set_font(pdf, settings, "", 7)
        pdf.multi_cell(0, 4, settings.footer_text, align="C")
    if settings.show_signature and not narrow:
        pdf.ln(8)
        _set_font(pdf, settings, "", 8)
        pdf.multi_cell(
            0,
            5,
            f"For {_business_name(business)}\nAuthorised Signatory",
            align="R",
        )


def _render(
    pdf: FPDF,
    document_type: str,
    document: Any,
    business: Any,
    settings: SalesPrintSettings,
    copy_label: str = "",
) -> None:
    _render_header(
        pdf, document_type, document, business, settings, copy_label
    )
    rows = _render_lines(pdf, document_type, document, settings)
    _render_totals(pdf, document, rows, settings)
    _render_content(pdf, document, business, settings)


def _copy_labels(
    document_type: str,
    settings: SalesPrintSettings,
    requested: str | None,
) -> list[str]:
    if document_type != "sales_invoice":
        return [""]
    configured = [
        item.strip() for item in settings.invoice_copy_labels if item.strip()
    ] or ["Original for Recipient"]
    if settings.invoice_copy_mode == "combined":
        return configured
    selected = requested or settings.default_invoice_copy
    return [selected if selected in configured else configured[0]]


def generate_sales_document_pdf(
    document_type: str,
    document: Any,
    business: Any,
    settings: SalesPrintSettings | None = None,
    *,
    copy_label: str | None = None,
) -> bytes:
    if document_type not in DOCUMENT_TITLES:
        raise ValueError(f"Unsupported document type: {document_type}")
    settings = settings or SalesPrintSettings()
    labels = _copy_labels(document_type, settings, copy_label)
    narrow = settings.paper_size.upper() in {"80MM", "58MM"}
    height = None
    if narrow:
        scratch = _configure_pdf(settings, height=1000)
        scratch.add_page()
        _render(
            scratch,
            document_type,
            document,
            business,
            settings,
            labels[0],
        )
        height = max(scratch.get_y() + settings.margin_mm, 80)
    pdf = _configure_pdf(settings, height=height)
    for label in labels:
        pdf.add_page()
        _render(pdf, document_type, document, business, settings, label)
    return bytes(pdf.output())
