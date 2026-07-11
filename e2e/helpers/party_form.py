"""Fill customer/vendor dialogs (scoped to stDialog)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Locator, Page

VALID_GSTIN = "27AAAAA0000A1Z5"
VALID_PAN = "AAAAA0000A"
VALID_PIN = "400001"
VALID_IFSC = "HDFC0001234"


@dataclass
class PartyMinimal:
    name: str
    phone: str


@dataclass
class PartyFull(PartyMinimal):
    contact_person: str = "Contact E2E"
    alt_phone: str = ""
    email: str = "e2e@example.com"
    address_line1: str = "12 MG Road"
    address_line2: str = "Floor 2"
    city: str = "Mumbai"
    pincode: str = VALID_PIN
    state_label: str = ""
    country: str = "India"
    notes: str = "E2E notes"


@dataclass
class PartyRegistered(PartyFull):
    gstin: str = VALID_GSTIN
    pan: str = VALID_PAN
    msme: str = "UDYAM-MH-00-0000001"


def dialog(page: Page) -> Locator:
    return page.get_by_test_id("stDialog")


def _fill_text(dialog_el: Locator, label: str, value: str) -> None:
    field = dialog_el.get_by_label(label, exact=False)
    field.click()
    field.fill(value)
    field.press("Tab")
    field.page.wait_for_timeout(250)


def _select_option(page: Page, dialog_el: Locator, label: str, option: str) -> None:
    dialog_el.get_by_label(label, exact=False).click()
    page.wait_for_timeout(400)
    popover = page.locator('[data-baseweb="popover"]')
    option_loc = popover.get_by_text(option, exact=True)
    if option_loc.count() == 0:
        option_loc = page.get_by_role("option", name=option)
    option_loc.first.click()
    page.wait_for_timeout(300)


def _fill_basic(dialog_el: Locator, name_label: str, data: PartyMinimal) -> None:
    _fill_text(dialog_el, f"{name_label} *", data.name)
    _fill_text(dialog_el, "Phone Number *", data.phone)


def _fill_optional_basic(dialog_el: Locator, data: PartyFull) -> None:
    _fill_text(dialog_el, "Contact Person", data.contact_person)
    if data.alt_phone:
        _fill_text(dialog_el, "Alternate Phone", data.alt_phone)
    _fill_text(dialog_el, "Email", data.email)


def _fill_address_tax(
    page: Page,
    dialog_el: Locator,
    data: PartyFull,
    *,
    registration: Optional[str] = None,
    gstin: str = "",
    pan: str = "",
    msme: str = "",
) -> None:
    _fill_text(dialog_el, "Address Line 1", data.address_line1)
    _fill_text(dialog_el, "Address Line 2", data.address_line2)
    _fill_text(dialog_el, "City", data.city)
    _fill_text(dialog_el, "PIN Code", data.pincode)
    if data.state_label:
        _select_option(page, dialog_el, "State", data.state_label)
    _fill_text(dialog_el, "Country", data.country)
    if registration:
        _select_option(page, dialog_el, "Registration Type", registration)
    if gstin:
        _fill_text(dialog_el, "GSTIN", gstin)
    if pan:
        _fill_text(dialog_el, "PAN", pan)
    if msme:
        _fill_text(dialog_el, "MSME (Udyam) Number", msme)


def set_registration_type(page: Page, registration: str) -> None:
    _select_option(page, dialog(page), "Registration Type", registration)


def fill_customer_minimal(page: Page, data: PartyMinimal) -> None:
    _fill_basic(dialog(page), "Customer Name", data)


def fill_customer_full(page: Page, data: PartyFull) -> None:
    d = dialog(page)
    _fill_basic(d, "Customer Name", data)
    _fill_optional_basic(d, data)
    _fill_address_tax(page, d, data, registration="Unregistered")
    _fill_text(d, "Notes", data.notes)


def _select_state_by_name(page: Page, dialog_el: Locator, state_name: str) -> None:
    dialog_el.get_by_label("State", exact=False).click()
    page.wait_for_timeout(400)
    page.keyboard.type(state_name)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(300)


def fill_customer_registered(page: Page, data: PartyRegistered) -> None:
    d = dialog(page)
    _fill_basic(d, "Customer Name", data)
    _fill_optional_basic(d, data)
    _fill_text(d, "Address Line 1", data.address_line1)
    _fill_text(d, "Address Line 2", data.address_line2)
    _fill_text(d, "City", data.city)
    _fill_text(d, "PIN Code", data.pincode)
    _select_state_by_name(page, d, "Maharashtra")
    _fill_text(d, "Country", data.country)
    _select_option(page, d, "Registration Type", "Registered")
    _fill_text(d, "GSTIN", data.gstin)
    _fill_text(d, "PAN", data.pan)
    _fill_text(d, "MSME (Udyam) Number", data.msme)
    _fill_text(d, "Notes", data.notes)


def fill_vendor_registered(page: Page, data: PartyRegistered) -> None:
    d = dialog(page)
    _fill_basic(d, "Vendor Name", data)
    _fill_optional_basic(d, data)
    _fill_text(d, "Address Line 1", data.address_line1)
    _fill_text(d, "Address Line 2", data.address_line2)
    _fill_text(d, "City", data.city)
    _fill_text(d, "PIN Code", data.pincode)
    _select_state_by_name(page, d, "Maharashtra")
    _fill_text(d, "Country", data.country)
    _select_option(page, d, "Registration Type", "Registered")
    _fill_text(d, "GSTIN", data.gstin)
    _fill_text(d, "PAN", data.pan)
    _fill_text(d, "MSME (Udyam) Number", data.msme)
    _fill_text(d, "Notes", data.notes)


def fill_vendor_minimal(page: Page, data: PartyMinimal) -> None:
    _fill_basic(dialog(page), "Vendor Name", data)


def fill_vendor_full(page: Page, data: PartyFull) -> None:
    d = dialog(page)
    _fill_basic(d, "Vendor Name", data)
    _fill_optional_basic(d, data)
    _fill_address_tax(page, d, data, registration="Unregistered")
    _fill_text(d, "Notes", data.notes)


def fill_vendor_banking(
    page: Page,
    *,
    holder: str = "E2E Holder",
    account: str = "123456789012",
    ifsc: str = VALID_IFSC,
    bank_name: str = "HDFC Bank",
) -> None:
    d = dialog(page)
    _fill_text(d, "Account Holder Name", holder)
    _fill_text(d, "Account Number", account)
    _fill_text(d, "IFSC", ifsc)
    _fill_text(d, "Bank Name", bank_name)
