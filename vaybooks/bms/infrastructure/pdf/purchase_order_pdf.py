"""Purchase order PDF (A4) — mirrors sales doc layout lightly."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from vaybooks.bms.domain.shared.document_customization import SalesPrintSettings


def _font_path() -> Path | None:
    candidates = (
        Path(__file__).parent / "fonts" / "DejaVuSans.ttf",
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    return next((path for path in candidates if path.exists()), None)


def _val(source: Any, name: str, default: Any = ""):
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _fmt_date(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return str(value or "—")


def _money(value: float) -> str:
    return f"{float(value or 0):,.2f}"


def generate_purchase_order_pdf(
    order: Any,
    business: Any = None,
    settings: SalesPrintSettings | None = None,
    *,
    vendor: Any = None,
) -> bytes:
    """Render a purchase order PDF. Uses SalesPrintSettings for paper/margins/logo toggles."""
    settings = settings or SalesPrintSettings()
    paper = settings.paper_size.upper()
    fmt = "Letter" if paper == "LETTER" else ("A5" if paper == "A5" else "A4")
    orientation = "L" if settings.orientation.lower() == "landscape" else "P"
    pdf = FPDF(orientation=orientation, unit="mm", format=fmt)
    pdf.set_margins(settings.margin_mm, settings.margin_mm, settings.margin_mm)
    pdf.set_auto_page_break(True, settings.margin_mm)
    font = _font_path()
    if font:
        pdf.add_font("POUnicode", "", str(font))
        pdf.add_font("POUnicode", "B", str(font))
        face = "POUnicode"
    else:
        face = "Helvetica"

    pdf.add_page()
    pdf.set_font(face, "B", 16)
    biz_name = (
        str(_val(business, "trade_name", "") or _val(business, "legal_name", "") or "Purchase Order")
        if business
        else "Purchase Order"
    )
    if settings.show_logo:
        pdf.cell(0, 8, biz_name, ln=1)
        pdf.set_font(face, "", 9)
        addr_parts = [
            _val(business, "address_line1", ""),
            _val(business, "address_line2", ""),
            _val(business, "city", ""),
            _val(business, "state_code", ""),
            _val(business, "pincode", ""),
        ]
        addr = ", ".join(str(p) for p in addr_parts if p)
        if addr:
            pdf.multi_cell(0, 5, addr)
        gstin = _val(business, "gstin", "")
        if gstin:
            pdf.cell(0, 5, f"GSTIN: {gstin}", ln=1)
        pdf.ln(2)

    pdf.set_font(face, "B", 14)
    pdf.cell(0, 8, "PURCHASE ORDER", ln=1)
    pdf.set_font(face, "", 10)
    pdf.cell(95, 6, f"PO No: {_val(order, 'po_number', '')}", ln=0)
    pdf.cell(0, 6, f"Date: {_fmt_date(_val(order, 'order_date'))}", ln=1)
    expected = _val(order, "expected_date")
    if expected:
        pdf.cell(0, 6, f"Expected: {_fmt_date(expected)}", ln=1)
    pdf.cell(0, 6, f"Status: {getattr(order.status, 'value', order.status) or ''}", ln=1)
    pdf.ln(2)

    pdf.set_font(face, "B", 11)
    pdf.cell(0, 6, "Vendor", ln=1)
    pdf.set_font(face, "", 10)
    vendor_name = _val(order, "vendor_name", "") or _val(vendor, "vendor_name", "")
    pdf.cell(0, 5, str(vendor_name or "—"), ln=1)
    if vendor:
        v_addr = ", ".join(
            str(p)
            for p in (
                _val(vendor, "address_line1", ""),
                _val(vendor, "city", ""),
                _val(vendor, "state_code", ""),
                _val(vendor, "pincode", ""),
            )
            if p
        )
        if v_addr:
            pdf.multi_cell(0, 5, v_addr)
        v_gst = _val(vendor, "gstin", "")
        if v_gst:
            pdf.cell(0, 5, f"GSTIN: {v_gst}", ln=1)
    pdf.ln(3)

    # Table header
    col_w = (10, 78, 22, 30, 30)  # #, item, qty, rate, amount — ~170
    pdf.set_font(face, "B", 9)
    headers = ("#", "Item", "Qty", "Rate", "Amount")
    for width, label in zip(col_w, headers):
        pdf.cell(width, 7, label, border=1, align="C" if label != "Item" else "L")
    pdf.ln()

    pdf.set_font(face, "", 9)
    lines = list(_val(order, "lines", []) or [])
    total = 0.0
    for idx, line in enumerate(lines, start=1):
        name = str(_val(line, "product_name", "") or _val(line, "product_id", "") or "—")
        qty = float(_val(line, "qty_ordered", 0) or 0)
        rate = float(_val(line, "rate", 0) or 0)
        amount = float(_val(line, "line_total", qty * rate) or 0)
        total += amount
        # Truncate long names for single-line cells
        if len(name) > 48:
            name = name[:45] + "…"
        pdf.cell(col_w[0], 6, str(idx), border=1, align="C")
        pdf.cell(col_w[1], 6, name, border=1)
        pdf.cell(col_w[2], 6, f"{qty:g}", border=1, align="R")
        pdf.cell(col_w[3], 6, _money(rate), border=1, align="R")
        pdf.cell(col_w[4], 6, _money(amount), border=1, align="R")
        pdf.ln()

    pdf.set_font(face, "B", 10)
    pdf.cell(sum(col_w[:4]), 7, "Total", border=1, align="R")
    pdf.cell(col_w[4], 7, _money(total or float(_val(order, "total_amount", 0) or 0)), border=1, align="R")
    pdf.ln(10)

    notes = str(_val(order, "notes", "") or "")
    if notes and settings.show_notes:
        pdf.set_font(face, "B", 10)
        pdf.cell(0, 6, "Notes", ln=1)
        pdf.set_font(face, "", 9)
        pdf.multi_cell(0, 5, notes)

    if settings.footer_text:
        pdf.ln(6)
        pdf.set_font(face, "", 8)
        pdf.multi_cell(0, 4, settings.footer_text)

    return bytes(pdf.output())
