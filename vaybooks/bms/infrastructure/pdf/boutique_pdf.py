"""Modern boutique documents: measurement sheet, item work order, receipt."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fpdf import FPDF

from vaybooks.bms.domain.shared.document_customization import SalesPrintSettings
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import _amount_in_words

INK = (30, 41, 59)
MUTED = (100, 116, 139)
SURFACE = (248, 250, 252)
LINE = (226, 232, 240)
WHITE = (255, 255, 255)
SUCCESS = (22, 101, 52)


def _font_path() -> Path | None:
    candidates = (
        Path(__file__).parent / "fonts" / "DejaVuSans.ttf",
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    return next((path for path in candidates if path.exists()), None)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    raw = (hex_color or "#1F4E78").lstrip("#")
    try:
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return (31, 78, 120)


def _settings_for(
    business: Any,
    document_type: str,
    settings: Optional[SalesPrintSettings],
) -> SalesPrintSettings:
    if settings:
        return settings
    templates = getattr(business, "document_templates", {}) or {}
    template = templates.get(document_type)
    return getattr(template, "print_settings", None) or SalesPrintSettings()


def _paper(settings: SalesPrintSettings):
    value = settings.paper_size.upper()
    if value == "LETTER":
        return "Letter"
    if value == "A5":
        return "A5"
    return "A4"


def _configure_pdf(settings: SalesPrintSettings) -> FPDF:
    orientation = "P" if settings.orientation.lower().startswith("p") else "L"
    pdf = FPDF(orientation=orientation, format=_paper(settings))
    pdf.set_auto_page_break(auto=True, margin=max(settings.margin_mm, 12))
    pdf.set_margins(settings.margin_mm, settings.margin_mm, settings.margin_mm)
    font = _font_path()
    if font:
        pdf.add_font("Body", "", str(font))
        pdf.set_font("Body", size=9)
        pdf.font_family = "Body"
    else:
        pdf.set_font("Helvetica", size=9)
        pdf.font_family = "Helvetica"
    pdf.add_page()
    return pdf


def _business_name(business: Any) -> str:
    return (
        getattr(business, "trade_name", "")
        or getattr(business, "legal_name", "")
        or getattr(business, "business_name", "")
        or getattr(business, "name", "")
        or "Boutique"
    )


def _business_line(business: Any) -> str:
    parts = [
        getattr(business, "address_line1", ""),
        getattr(business, "city", ""),
        getattr(business, "phone", ""),
        getattr(business, "email", ""),
    ]
    return "  |  ".join(str(part) for part in parts if part)


def _header(
    pdf: FPDF,
    business: Any,
    title: str,
    document_number: str,
    settings: SalesPrintSettings,
) -> None:
    """Header mirroring the sales document layout so all PDFs look alike."""
    accent = _rgb(settings.accent_color)
    name = _business_name(business)
    initials = "".join(word[0].upper() for word in name.split()[:2] if word) or "B"

    if settings.template_style == "modern":
        x, y, width = pdf.l_margin, pdf.get_y(), pdf.epw
        pdf.set_fill_color(*accent)
        pdf.rect(x, y, width, 24, style="F")
        pdf.set_text_color(*WHITE)
        pdf.set_font(pdf.font_family, size=15)
        pdf.set_xy(x + 2, y + 2)
        brand_width = width * 0.62
        if settings.show_logo:
            pdf.cell(12, 9, initials, border=1, align="C")
            brand_width -= 12
        pdf.cell(brand_width, 9, name[:45])
        pdf.set_font(pdf.font_family, size=12)
        pdf.cell(width * 0.34, 9, title, align="R")
        pdf.set_xy(x + 2, y + 12)
        pdf.set_font(pdf.font_family, size=7.5)
        pdf.cell(width - 4, 5, _business_line(business)[:110])
        gstin = getattr(business, "gstin", "")
        if gstin:
            pdf.set_xy(x + 2, y + 17)
            pdf.cell(width - 4, 5, f"GSTIN: {gstin}")
        pdf.set_y(y + 27)
        pdf.set_text_color(*INK)
    else:
        pdf.set_font(pdf.font_family, size=13)
        heading = f"[{initials}]  {name}" if settings.show_logo else name
        pdf.cell(0, 7, heading, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(pdf.font_family, size=7.5)
        pdf.set_text_color(*MUTED)
        line = _business_line(business)
        if line:
            pdf.multi_cell(0, 4, line, align="C", new_x="LMARGIN", new_y="NEXT")
        gstin = getattr(business, "gstin", "")
        if gstin:
            pdf.cell(0, 4, f"GSTIN: {gstin}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*accent)
        pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
        pdf.ln(3)
        pdf.set_text_color(*INK)
        pdf.set_font(pdf.font_family, size=11)
        pdf.cell(0, 6, title, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(pdf.font_family, size=8)
    pdf.set_text_color(*INK)
    pdf.cell(0, 5, f"No: {document_number}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _section(pdf: FPDF, title: str, settings: SalesPrintSettings) -> None:
    if pdf.get_y() > pdf.h - 30:
        pdf.add_page()
    accent = _rgb(settings.accent_color)
    pdf.ln(3)
    pdf.set_fill_color(*accent)
    pdf.rect(pdf.l_margin, pdf.get_y() + 1, 2, 5, style="F")
    pdf.set_x(pdf.l_margin + 5)
    pdf.set_text_color(*INK)
    pdf.set_font(pdf.font_family, size=10)
    pdf.cell(0, 7, title.upper(), new_x="LMARGIN", new_y="NEXT")


def _info_grid(pdf: FPDF, rows: list[tuple[str, str]], columns: int = 3) -> None:
    rows = [(label, str(value or "—")) for label, value in rows]
    gap = 3
    card_w = (pdf.epw - gap * (columns - 1)) / columns
    for start in range(0, len(rows), columns):
        batch = rows[start : start + columns]
        y = pdf.get_y()
        for index, (label, value) in enumerate(batch):
            x = pdf.l_margin + index * (card_w + gap)
            pdf.set_fill_color(*SURFACE)
            pdf.set_draw_color(*LINE)
            pdf.rect(x, y, card_w, 15, style="DF")
            pdf.set_xy(x + 4, y + 3)
            pdf.set_text_color(*MUTED)
            pdf.set_font(pdf.font_family, size=6.5)
            pdf.cell(card_w - 8, 3, label.upper())
            pdf.set_xy(x + 4, y + 7)
            pdf.set_text_color(*INK)
            pdf.set_font(pdf.font_family, size=9)
            pdf.cell(card_w - 8, 5, value[:35])
        pdf.set_y(y + 18)


def _note_card(
    pdf: FPDF, title: str, content: str, settings: SalesPrintSettings
) -> None:
    if not content:
        return
    accent = _rgb(settings.accent_color)
    pdf.set_fill_color(*SURFACE)
    pdf.set_draw_color(*LINE)
    y = pdf.get_y()
    pdf.rect(pdf.l_margin, y, pdf.epw, 20, style="DF")
    pdf.set_xy(pdf.l_margin + 5, y + 3)
    pdf.set_text_color(*accent)
    pdf.set_font(pdf.font_family, size=7)
    pdf.cell(0, 4, title.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin + 5)
    pdf.set_text_color(*INK)
    pdf.set_font(pdf.font_family, size=8.5)
    pdf.multi_cell(pdf.epw - 10, 4, content[:450])
    pdf.set_y(max(pdf.get_y() + 3, y + 23))


def _table(
    pdf: FPDF,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float],
    settings: SalesPrintSettings,
) -> None:
    accent = _rgb(settings.accent_color)

    def header_row() -> None:
        pdf.set_fill_color(*accent)
        pdf.set_text_color(*WHITE)
        pdf.set_font(pdf.font_family, size=7)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, header.upper(), fill=True)
        pdf.ln(7)

    header_row()
    for index, row in enumerate(rows):
        if pdf.get_y() > pdf.h - 22:
            pdf.add_page()
            header_row()
        pdf.set_fill_color(*(SURFACE if index % 2 == 0 else WHITE))
        pdf.set_text_color(*INK)
        pdf.set_font(pdf.font_family, size=8)
        for value, width in zip(row, widths):
            pdf.cell(width, 6.5, str(value)[:48], fill=True)
        pdf.ln(6.5)
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + sum(widths), pdf.get_y())


def _footer(
    pdf: FPDF,
    settings: SalesPrintSettings,
    left_label: str,
    business: Any = None,
) -> None:
    """Footer mirroring the sales document layout so all PDFs look alike."""
    pdf.ln(6)
    if settings.footer_text:
        pdf.set_text_color(*MUTED)
        pdf.set_font(pdf.font_family, size=7)
        pdf.multi_cell(0, 4, settings.footer_text, align="C")
    if settings.show_signature:
        pdf.ln(8)
        y = pdf.get_y()
        pdf.set_text_color(*INK)
        pdf.set_font(pdf.font_family, size=8)
        pdf.multi_cell(
            0,
            5,
            f"For {_business_name(business)}\nAuthorised Signatory",
            align="R",
        )
        pdf.set_draw_color(*LINE)
        pdf.line(pdf.l_margin, y + 8, pdf.l_margin + 55, y + 8)
        pdf.set_xy(pdf.l_margin, y + 9)
        pdf.set_text_color(*MUTED)
        pdf.set_font(pdf.font_family, size=7)
        pdf.cell(55, 4, left_label, align="C")
        pdf.set_y(max(pdf.get_y(), y + 14))


def generate_measurement_sheet_pdf(
    record: Any,
    customer: Any,
    business: Any,
    settings: Optional[SalesPrintSettings] = None,
) -> bytes:
    settings = _settings_for(business, "measurement_sheet", settings)
    pdf = _configure_pdf(settings)
    _header(
        pdf, business, "Measurement Sheet", record.measurement_number, settings
    )
    person_type = getattr(record.person_type, "value", record.person_type)
    fit = getattr(record.fit_preference, "value", record.fit_preference)
    _info_grid(
        pdf,
        [
            ("Customer", getattr(customer, "customer_name", "")),
            ("Mobile", getattr(customer, "phone_number", "")),
            ("Person type", person_type),
            ("Wearer", record.wearer_name),
            ("Age", record.wearer_age),
            ("Fit preference", fit),
            ("Height", getattr(record, "wearer_height", "")),
            ("Weight", getattr(record, "wearer_weight", "")),
            ("Measured on", record.measured_at),
            ("Measured by", record.measured_by),
        ],
    )
    _section(pdf, "Body & Garment Measurements", settings)
    name_w = pdf.epw * 0.58
    value_w = pdf.epw * 0.25
    unit_w = pdf.epw - name_w - value_w
    _table(
        pdf,
        ["Measurement", "Value", "Unit"],
        [
            [
                value.field_key.replace("_", " ").title(),
                str(value.value),
                value.unit,
            ]
            for value in record.values
        ],
        [name_w, value_w, unit_w],
        settings,
    )
    if settings.show_notes:
        _section(pdf, "Notes", settings)
        _note_card(
            pdf,
            "Tailor notes",
            record.notes or record.print_notes or "No additional notes.",
            settings,
        )
    _footer(pdf, settings, "CUSTOMER CONFIRMATION", business)
    return bytes(pdf.output())


def generate_customization_item_pdf(
    order: Any,
    item: Any,
    customer: Any,
    business: Any,
    measurement: Any = None,
    attachments: Optional[list] = None,
    settings: Optional[SalesPrintSettings] = None,
) -> bytes:
    settings = _settings_for(business, "customization_item", settings)
    pdf = _configure_pdf(settings)
    _header(pdf, business, "Customization Item with Notes", item.bill_number, settings)
    _info_grid(
        pdf,
        [
            ("Order", order.order_number),
            ("Measurement bill number", item.bill_number),
            ("Delivery date", item.expected_delivery_date or order.expected_delivery_date),
            ("Customer", getattr(customer, "customer_name", order.customer_name)),
            ("Mobile", getattr(customer, "phone_number", order.phone_number)),
            (
                "Measurement",
                getattr(measurement, "measurement_number", "")
                or getattr(item, "measurement_number", ""),
            ),
        ],
    )
    _section(pdf, "Item Brief", settings)
    _note_card(pdf, "Garment / work", item.description, settings)
    _note_card(
        pdf,
        "Customer specification",
        item.customer_specification or "No special specification.",
        settings,
    )
    if settings.show_notes:
        order_notes = (getattr(order, "notes", None) or "").strip()
        measurement_notes = ""
        if measurement:
            measurement_notes = (
                getattr(measurement, "notes", None)
                or getattr(measurement, "print_notes", None)
                or ""
            ).strip()
        notes_body = order_notes or measurement_notes or "No additional notes."
        _section(pdf, "Notes", settings)
        _note_card(pdf, "Order / tailor notes", notes_body, settings)
        if order_notes and measurement_notes and order_notes != measurement_notes:
            _note_card(pdf, "Measurement notes", measurement_notes, settings)
    if settings.show_linked_measurements and measurement:
        _section(pdf, f"Measurements · {measurement.measurement_number}", settings)
        name_w = pdf.epw * 0.55
        value_w = pdf.epw * 0.28
        _table(
            pdf,
            ["Measurement", "Value", "Unit"],
            [
                [
                    value.field_key.replace("_", " ").title(),
                    str(value.value),
                    value.unit,
                ]
                for value in measurement.values
            ],
            [name_w, value_w, pdf.epw - name_w - value_w],
            settings,
        )
    activities = [
        activity
        for activity in getattr(order, "order_activities", [])
        if activity.bill_id == item.item_id
    ]
    if settings.show_activities and activities:
        _section(pdf, "Production Checklist", settings)
        _table(
            pdf,
            ["Done", "Activity", "Current status"],
            [
                ["[ ]", activity.activity_name, activity.current_status]
                for activity in activities
            ],
            [pdf.epw * 0.12, pdf.epw * 0.5, pdf.epw * 0.38],
            settings,
        )
    attachments = attachments or []
    images = [
        attachment
        for attachment in attachments
        if getattr(getattr(attachment, "category", ""), "value", getattr(attachment, "category", ""))
        != "file_out"
        and getattr(attachment, "data", None)
    ]
    files = [
        attachment
        for attachment in attachments
        if getattr(getattr(attachment, "category", ""), "value", getattr(attachment, "category", ""))
        == "file_out"
    ]
    if settings.show_media and images:
        _section(pdf, "Visual References", settings)
        thumb_w, thumb_h, gap = 52, 42, 5
        per_row = max(1, int((pdf.epw + gap) // (thumb_w + gap)))
        for start in range(0, len(images), per_row):
            if pdf.get_y() + thumb_h + 10 > pdf.h - 15:
                pdf.add_page()
            y = pdf.get_y()
            for index, attachment in enumerate(images[start : start + per_row]):
                x = pdf.l_margin + index * (thumb_w + gap)
                pdf.set_draw_color(*LINE)
                pdf.rect(x, y, thumb_w, thumb_h)
                try:
                    pdf.image(
                        BytesIO(attachment.data),
                        x=x + 1,
                        y=y + 1,
                        w=thumb_w - 2,
                        h=thumb_h - 7,
                        keep_aspect_ratio=True,
                    )
                except Exception:
                    pass
                pdf.set_xy(x + 2, y + thumb_h - 5)
                pdf.set_text_color(*MUTED)
                pdf.set_font(pdf.font_family, size=6)
                pdf.cell(thumb_w - 4, 4, attachment.name[:28], align="C")
            pdf.set_y(y + thumb_h + 5)
    if settings.show_media and files:
        _section(pdf, "Production Files", settings)
        _table(
            pdf,
            ["File name", "Type", "Size"],
            [
                [
                    attachment.name,
                    attachment.content_type,
                    f"{attachment.size_bytes / 1024:.0f} KB",
                ]
                for attachment in files
            ],
            [pdf.epw * 0.55, pdf.epw * 0.27, pdf.epw * 0.18],
            settings,
        )
    _footer(pdf, settings, "CUSTOMER APPROVAL", business)
    return bytes(pdf.output())


def generate_advance_receipt_pdf(
    voucher: Any,
    order: Any,
    customer: Any,
    business: Any,
    settings: Optional[SalesPrintSettings] = None,
) -> bytes:
    settings = _settings_for(business, "advance_receipt", settings)
    pdf = _configure_pdf(settings)
    _header(pdf, business, "Advance Receipt", voucher.voucher_number, settings)
    amount = float(order.advance_amount or 0)
    receiving_account = ""
    for line in getattr(voucher, "lines", []) or []:
        if getattr(line, "debit", 0):
            amount = float(line.debit)
            receiving_account = getattr(line, "account_name", "")
            break
    _info_grid(
        pdf,
        [
            ("Receipt number", voucher.voucher_number),
            ("Receipt date", getattr(voucher, "voucher_date", "")),
            ("Order", order.order_number),
            ("Received from", getattr(customer, "customer_name", order.customer_name)),
            ("Mobile", getattr(customer, "phone_number", order.phone_number)),
            ("Received in", receiving_account),
        ],
    )
    _section(pdf, "Amount Received", settings)
    accent = _rgb(settings.accent_color)
    y = pdf.get_y()
    pdf.set_fill_color(*accent)
    pdf.rect(pdf.l_margin, y, pdf.epw, 31, style="F")
    pdf.set_xy(pdf.l_margin + 7, y + 5)
    pdf.set_text_color(219, 234, 254)
    pdf.set_font(pdf.font_family, size=7)
    pdf.cell(0, 5, "ADVANCE AMOUNT")
    pdf.set_xy(pdf.l_margin + 7, y + 11)
    pdf.set_text_color(*WHITE)
    pdf.set_font(pdf.font_family, size=22)
    pdf.cell(0, 11, f"Rs. {amount:,.2f}")
    pdf.set_xy(pdf.l_margin + 7, y + 23)
    pdf.set_font(pdf.font_family, size=7.5)
    pdf.cell(0, 5, _amount_in_words(amount))
    pdf.set_y(y + 36)
    _note_card(
        pdf,
        "Towards",
        getattr(voucher, "description", "") or f"Advance for {order.order_number}",
        settings,
    )
    _note_card(
        pdf,
        "Acknowledgement",
        "Received as advance against the customization order. "
        "This receipt is not a final tax invoice.",
        settings,
    )
    _footer(pdf, settings, "CUSTOMER / PAYER", business)
    return bytes(pdf.output())


def generate_customization_invoice_pdf(
    invoice: Any,
    order: Any,
    customer: Any,
    business: Any,
    settings: Optional[SalesPrintSettings] = None,
) -> bytes:
    """Tax invoice PDF for system-generated customization invoices."""
    settings = _settings_for(business, "customization_invoice", settings)
    pdf = _configure_pdf(settings)
    _header(pdf, business, "Tax Invoice", invoice.invoice_number, settings)

    pos_label = ""
    if getattr(invoice, "place_of_supply_state", ""):
        from vaybooks.bms.domain.shared.india import state_name_for_code

        pos_label = state_name_for_code(invoice.place_of_supply_state)

    _info_grid(
        pdf,
        [
            ("Invoice date", getattr(invoice, "invoice_date", "")),
            ("Order", getattr(order, "order_number", "")),
            ("Supply type", getattr(invoice, "supply_type", "") or "—"),
            ("Place of supply", pos_label or "—"),
            ("Customer", getattr(customer, "customer_name", getattr(order, "customer_name", ""))),
            ("Mobile", getattr(customer, "phone_number", getattr(order, "phone_number", ""))),
            ("Customer GSTIN", getattr(customer, "gstin", "") or "—"),
        ],
        columns=2,
    )
    if customer and getattr(customer, "formatted_address", ""):
        _section(pdf, "Billing Address", settings)
        _note_card(pdf, "Bill to", customer.formatted_address, settings)

    _section(pdf, "Line Items", settings)
    rows = []
    for bill_id in getattr(invoice, "bill_ids", []) or []:
        item = order.get_item_by_id(bill_id) if hasattr(order, "get_item_by_id") else None
        label = getattr(item, "bill_number", bill_id) if item else bill_id
        desc = getattr(item, "description", "") if item else ""
        gross = float((getattr(invoice, "item_amounts", {}) or {}).get(bill_id, 0) or 0)
        disc = float((getattr(invoice, "item_discounts", {}) or {}).get(bill_id, 0) or 0)
        net = round(gross - disc, 2)
        sac = getattr(invoice, "hsn_sac", "") or ""
        rate = float(getattr(invoice, "gst_rate", 0) or 0)
        rows.append(
            [
                label,
                desc[:30] or "—",
                sac,
                f"{rate:g}%",
                f"{net:,.2f}",
            ]
        )
    if not rows:
        rows.append(["—", "Customization services", "", "", f"{invoice.net_amount:,.2f}"])

    name_w = pdf.epw * 0.14
    desc_w = pdf.epw * 0.28
    sac_w = pdf.epw * 0.12
    rate_w = pdf.epw * 0.12
    amt_w = pdf.epw - name_w - desc_w - sac_w - rate_w
    _table(
        pdf,
        ["Bill", "Description", "SAC", "GST %", "Taxable"],
        rows,
        [name_w, desc_w, sac_w, rate_w, amt_w],
        settings,
    )

    taxable = float(getattr(invoice, "taxable_amount", 0) or invoice.net_amount)
    cgst = float(getattr(invoice, "cgst_amount", 0) or 0)
    sgst = float(getattr(invoice, "sgst_amount", 0) or 0)
    utgst = float(getattr(invoice, "utgst_amount", 0) or 0)
    igst = float(getattr(invoice, "igst_amount", 0) or 0)
    grand = float(getattr(invoice, "grand_total", taxable))

    _section(pdf, "Tax Summary", settings)
    summary_rows = [("Taxable value", f"Rs. {taxable:,.2f}")]
    if cgst:
        summary_rows.append(("CGST", f"Rs. {cgst:,.2f}"))
    if sgst:
        summary_rows.append(("SGST", f"Rs. {sgst:,.2f}"))
    if utgst:
        summary_rows.append(("UTGST", f"Rs. {utgst:,.2f}"))
    if igst:
        summary_rows.append(("IGST", f"Rs. {igst:,.2f}"))
    summary_rows.append(("Grand total", f"Rs. {grand:,.2f}"))
    for label, value in summary_rows:
        pdf.set_font(pdf.font_family, size=9)
        pdf.cell(pdf.epw * 0.55, 6, label)
        pdf.cell(pdf.epw * 0.45, 6, value, align="R", new_x="LMARGIN", new_y="NEXT")

    if settings.show_amount_in_words:
        pdf.ln(2)
        pdf.set_text_color(*MUTED)
        pdf.set_font(pdf.font_family, size=8)
        pdf.multi_cell(0, 4, _amount_in_words(grand))

    _footer(pdf, settings, "RECIPIENT", business)
    return bytes(pdf.output())
