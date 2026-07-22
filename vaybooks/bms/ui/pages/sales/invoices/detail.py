"""Store sale detail route (`?id=<voucher_id>`)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.domain.shared.india import state_name_for_code
from vaybooks.bms.ui import navigation
from vaybooks.bms.domain.finance.accounting.sales_parsing import sales_row_from_voucher
from vaybooks.bms.domain.sales.line_items import parse_sales_document_content
from vaybooks.bms.domain.sales.invoice_lock import can_edit_invoice
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import generate_sales_document_pdf
from vaybooks.bms.ui.components.document_detail import (
    document_actions,
    document_header,
    format_document_date,
    line_items_table,
    secondary_sections,
    totals_ladder,
)
from vaybooks.bms.ui.components.sales_invoice_edit_dialog import (
    arm_invoice_edit_dialog,
    open_invoice_edit_dialog_if_armed,
)
from vaybooks.bms.ui.components.sales_invoice_form import (
    line_items_grand_total,
    line_items_tax_total,
    line_items_taxable,
    parse_cash_sales_voucher,
)
from vaybooks.bms.ui.components.voucher_card import voucher_receiving_account


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("sales_detail")
    mark_wired("nav.back")
    accounting = services["accounting"]
    sale_id = navigation.current_detail_id("sales_detail")

    if st.button("← Back to sales", key="sales_detail_back") or consume_action(
        "nav.back"
    ):
        navigation.go_back_to_list("store_sales", "sales_invoices_list")
        return

    if not sale_id:
        st.error("Sale not found.")
        return

    voucher = accounting.get_voucher(sale_id)
    if not voucher or voucher.voucher_type != VoucherType.SALES_INVOICE:
        st.error("Sale not found.")
        return

    discount = accounting.get_discount_account()
    discount_id = discount.id if discount else None
    row = sales_row_from_voucher(voucher, discount_id)
    parsed = parse_cash_sales_voucher(voucher, discount_id)
    tax_summary = parsed.get("tax_summary") or {}
    line_items = parsed.get("line_items") or []

    store_no = row.get("store_invoice_number") or voucher.voucher_number
    ref_so = getattr(voucher, "reference_so_id", None)
    ref_dn = getattr(voucher, "reference_dn_id", None)
    caption_parts = [
        format_document_date(row.get("sale_date")),
        f"Voucher {voucher.voucher_number}",
    ]
    right_facts = [("Sale date", format_document_date(row.get("sale_date")))]
    if ref_so:
        so = services.get("sales")
        if so:
            order = so.get_sales_order(ref_so)
            if order:
                caption_parts.append(f"SO {order.so_number}")
                right_facts.append(("Sales order", order.so_number))
    if ref_dn:
        sales_svc = services.get("sales")
        if sales_svc:
            dn = sales_svc.get_delivery_note(ref_dn)
            if dn:
                caption_parts.append(f"DN {dn.dn_number}")
                right_facts.append(("Delivery note", dn.dn_number))

    customer_name = row.get("party_name") or "Customer"
    customer_gstin = ""
    customer_state = ""
    customer_mobile = ""
    linked_customer_id = None
    customers = services.get("customers")
    customer_account_id = row.get("customer_account_id")
    if customers and customer_account_id:
        account = accounting.get_account(customer_account_id)
        if account and account.linked_customer_id:
            linked_customer_id = account.linked_customer_id
            detail = customers.get_customer_detail(account.linked_customer_id)
            if detail:
                customer_gstin = detail.gstin or ""
                customer_state = detail.state_code or ""
                customer_mobile = detail.phone_number or ""

    receiving = voucher_receiving_account(voucher)
    store_account = None
    if parsed.get("store_id"):
        store_account = accounting.get_account(parsed["store_id"])
    pay_label = (
        store_account.account_name if store_account else (receiving or "—")
    )

    left_facts = [("Customer", customer_name)]
    if customer_mobile:
        left_facts.append(("Mobile", customer_mobile))
    if customer_gstin:
        left_facts.append(("GSTIN", customer_gstin))
    if customer_state:
        left_facts.append(
            ("Place of supply", state_name_for_code(customer_state))
        )
    right_facts.append(("Received in", pay_label))

    document_header(
        number=f"Sale {store_no}",
        status=None,
        caption_parts=caption_parts,
        left_facts=left_facts,
        right_facts=right_facts,
        suffix=f"sale_{voucher.id}",
    )

    taxable = line_items_taxable(line_items, tax_summary)
    total_gst = line_items_tax_total(line_items, tax_summary)
    grand_total = line_items_grand_total(line_items, tax_summary)
    show_gst = bool(tax_summary or total_gst > 0)

    business_service = services.get("business")
    business = business_service.get_profile() if business_service else None
    template = None
    pdf_bytes = None
    document_content = parse_sales_document_content(voucher.description)
    if business:
        template = business.document_templates.get("sales_invoice")
        print_settings = template.print_settings if template else None
        copy_label = None
        if (
            print_settings
            and print_settings.invoice_copy_mode == "select"
            and print_settings.invoice_copy_labels
        ):
            labels = list(print_settings.invoice_copy_labels)
            default_copy = print_settings.default_invoice_copy
            copy_label = st.selectbox(
                "Invoice copy",
                labels,
                index=labels.index(default_copy) if default_copy in labels else 0,
                key=f"invoice_copy_{voucher.id}",
            )
        invoice_document = {
            **row,
            "customer_name": customer_name,
            "items": line_items,
            "document_content": document_content,
        }
        try:
            pdf_bytes = generate_sales_document_pdf(
                "sales_invoice",
                invoice_document,
                business,
                print_settings,
                copy_label=copy_label,
            )
        except Exception as exc:
            st.error(f"Could not generate PDF: {exc}")

    editable = can_edit_invoice(voucher.voucher_date)
    actions = []
    if pdf_bytes is not None:
        combined_copies = bool(
            template
            and template.print_settings.invoice_copy_mode == "combined"
        )
        actions.append(
            {
                "label": (
                    f"Download PDF ({len(template.print_settings.invoice_copy_labels)} copies)"
                    if combined_copies
                    else "Download PDF"
                ),
                "key": "pdf",
                "kind": "download",
                "data": pdf_bytes,
                "file_name": f"{store_no}.pdf",
                "mime": "application/pdf",
            }
        )
    if editable:
        actions.append({"label": "Edit", "key": "edit"})
    if linked_customer_id:
        actions.append({"label": "View customer →", "key": "view_customer"})
    clicked = document_actions(actions, suffix=f"sale_{voucher.id}")
    if not editable:
        st.info("Locked: invoice month has ended")

    if clicked.get("edit") and editable:
        arm_invoice_edit_dialog(voucher.id)
        st.rerun()
    if clicked.get("view_customer") and linked_customer_id:
        navigation.go_to_detail("customer_detail", linked_customer_id)
        return

    inventory = services.get("inventory")
    table_rows = []
    for item in line_items:
        desc = (item.get("description") or "").strip()
        if not desc:
            continue
        sku = ""
        product_id = item.get("product_id")
        if inventory and product_id:
            product = inventory.get_product(str(product_id))
            if product:
                sku = product.sku
        table_rows.append(
            {
                "sku": sku,
                "product": desc,
                "hsn_sac": item.get("hsn_sac") or "",
                "qty": float(item.get("qty") or 1.0),
                "rate": float(item.get("rate") or 0.0),
                "discount": float(item.get("discount") or 0.0),
                "taxable": float(
                    item.get("taxable_amount")
                    or max(
                        round(
                            float(item.get("qty") or 1)
                            * float(item.get("rate") or 0)
                            - float(item.get("discount") or 0),
                            2,
                        ),
                        0,
                    )
                ),
                "gst_rate": float(item.get("gst_rate") or 0),
                "cgst": float(item.get("cgst_amount") or 0),
                "sgst": float(item.get("sgst_amount") or 0),
                "utgst": float(item.get("utgst_amount") or 0),
                "igst": float(item.get("igst_amount") or 0),
                "total": float(
                    item.get("line_total")
                    or round(
                        float(item.get("qty") or 1)
                        * float(item.get("rate") or 0)
                        - float(item.get("discount") or 0),
                        2,
                    )
                ),
            }
        )
    line_items_table(
        table_rows,
        show_gst=show_gst,
        suffix=f"sale_{voucher.id}",
    )

    extra = [
        ("Collected", float(row.get("collected") or 0)),
        ("Balance", float(row.get("outstanding") or 0)),
    ]
    if show_gst:
        totals_ladder(
            {
                "taxable": taxable,
                "cgst": float(tax_summary.get("cgst") or 0),
                "sgst": float(tax_summary.get("sgst") or 0),
                "igst": float(tax_summary.get("igst") or 0),
                "utgst": float(tax_summary.get("utgst") or 0),
                "total_tax": total_gst,
                "grand_total": grand_total,
            },
            show_gst=True,
            grand_total=grand_total,
            extra_rows=extra,
            suffix=f"sale_{voucher.id}",
        )
    else:
        totals_ladder(
            {"grand_total": float(row.get("net") or grand_total)},
            show_gst=False,
            grand_total=float(row.get("net") or grand_total),
            extra_rows=[
                ("Gross", float(row.get("gross") or 0)),
                ("Discount", float(row.get("discount") or 0)),
                *extra,
            ],
            suffix=f"sale_{voucher.id}",
        )

    invoice_discount = float(parsed.get("invoice_discount") or 0.0)
    if invoice_discount > 0:
        st.caption(f"Invoice-level discount: ₹{invoice_discount:,.0f}")

    # Adapt dict document_content into a simple namespace for secondary sections.
    from types import SimpleNamespace

    bank_raw = document_content.get("bank_account")
    bank_obj = None
    if isinstance(bank_raw, dict) and bank_raw:
        bank_obj = SimpleNamespace(
            account_name=bank_raw.get("account_name", ""),
            bank_name=bank_raw.get("bank_name", ""),
            account_number=bank_raw.get("account_number", ""),
            ifsc=bank_raw.get("ifsc", ""),
            branch=bank_raw.get("branch", ""),
            upi_or_note=bank_raw.get("upi_or_note", ""),
        )
    content_obj = SimpleNamespace(
        custom_fields=document_content.get("custom_fields", []),
        bank_account=bank_obj,
        terms_and_conditions=document_content.get("terms_and_conditions", ""),
        policies=document_content.get("policies", []),
    )
    secondary_sections(document_content=content_obj)

    open_invoice_edit_dialog_if_armed(
        services,
        row=row,
        parsed=parsed,
        line_items=line_items,
        customer_account_id=customer_account_id,
        invoice_discount=invoice_discount,
    )
