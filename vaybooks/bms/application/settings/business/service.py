import base64
import binascii
import re
from typing import Optional

from vaybooks.bms.domain.business.entities import BUSINESS_PROFILE_ID, BusinessProfile
from vaybooks.bms.domain.business.repository import BusinessProfileRepository
from vaybooks.bms.domain.shared.document_customization import (
    DOCUMENT_TYPES,
    BankAccount,
    DocumentTemplateSettings,
)
from vaybooks.bms.domain.shared.enums import VendorRegistrationType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.india import (
    normalize_indian_phone,
    validate_gstin,
    validate_pan,
    validate_pincode,
    validate_state_code,
)


class BusinessAppService:
    def __init__(self, repo: BusinessProfileRepository):
        self._repo = repo

    def get_profile(self) -> BusinessProfile:
        profile = self._repo.get()
        if profile:
            return profile
        return BusinessProfile(id=BUSINESS_PROFILE_ID)

    def update_profile(
        self,
        *,
        legal_name: str = "",
        trade_name: str = "",
        address_line1: str = "",
        address_line2: str = "",
        city: str = "",
        state_code: str = "",
        pincode: str = "",
        country: str = "India",
        phone: str = "",
        email: str = "",
        gstin: str = "",
        pan: str = "",
        registration_type: VendorRegistrationType = VendorRegistrationType.UNREGISTERED,
        composition_tax_rate: float = 1.0,
    ) -> BusinessProfile:
        legal_name = legal_name.strip()
        trade_name = trade_name.strip()
        state_code = validate_state_code(state_code) if state_code else ""
        pin = validate_pan(pan) if (pan or "").strip() else ""
        gst = (gstin or "").strip().upper()
        if registration_type in {
            VendorRegistrationType.REGISTERED,
            VendorRegistrationType.COMPOSITION,
        }:
            if not gst:
                raise ValidationError(
                    "GSTIN is required for registered and composition businesses"
                )
            if not state_code:
                raise ValidationError(
                    "State is required for registered and composition businesses"
                )
            gst = validate_gstin(gst, state_code=state_code, pan=pin or None)
        elif gst:
            gst = validate_gstin(gst, state_code=state_code or None, pan=pin or None)
        phone_norm = ""
        if (phone or "").strip():
            phone_norm = normalize_indian_phone(phone)
        pincode_norm = validate_pincode(pincode) if (pincode or "").strip() else ""
        composition_rate = round(float(composition_tax_rate or 0), 2)
        if composition_rate < 0 or composition_rate > 100:
            raise ValidationError("Composition GST rate must be between 0 and 100")

        profile = self.get_profile()
        profile.update(
            legal_name=legal_name,
            trade_name=trade_name,
            address_line1=address_line1.strip(),
            address_line2=address_line2.strip(),
            city=city.strip(),
            state_code=state_code,
            pincode=pincode_norm,
            country=(country or "India").strip() or "India",
            phone=phone_norm,
            email=email.strip(),
            gstin=gst,
            pan=pin,
            registration_type=registration_type,
            composition_tax_rate=composition_rate,
        )
        return self._repo.save(profile)

    def update_document_settings(
        self,
        *,
        bank_accounts: list[BankAccount],
        document_templates: dict[str, DocumentTemplateSettings],
    ) -> BusinessProfile:
        account_ids = [item.id for item in bank_accounts]
        if len(account_ids) != len(set(account_ids)):
            raise ValidationError("Bank account IDs must be unique")
        for account in bank_accounts:
            if not account.account_name.strip():
                raise ValidationError("Bank account name is required")
            if account.qr_code_image:
                try:
                    header, encoded = account.qr_code_image.split(",", 1)
                    image_bytes = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise ValidationError("Bank QR code must be a valid image") from exc
                if header != "data:image/png;base64":
                    raise ValidationError("Bank QR code must be a PNG image")
                if len(image_bytes) > 2 * 1024 * 1024:
                    raise ValidationError("Bank QR code must be 2 MB or smaller")

        normalized: dict[str, DocumentTemplateSettings] = {}
        for document_type in DOCUMENT_TYPES:
            template = document_templates.get(document_type, DocumentTemplateSettings())
            keys = [field.key.strip() for field in template.custom_fields]
            if any(not key for key in keys):
                raise ValidationError("Custom field key is required")
            if len(keys) != len(set(keys)):
                raise ValidationError(
                    f"Custom field keys must be unique for {document_type}"
                )
            allowed_types = {"text", "multiline", "number", "date", "checkbox"}
            if any(field.field_type not in allowed_types for field in template.custom_fields):
                raise ValidationError("Unsupported custom field type")
            if (
                template.default_bank_account_id
                and template.default_bank_account_id not in account_ids
            ):
                raise ValidationError("Default bank account does not exist")
            printing = template.print_settings
            if printing.paper_size not in {"A4", "A5", "Letter", "80mm", "58mm"}:
                raise ValidationError("Unsupported print paper size")
            if printing.orientation not in {"portrait", "landscape"}:
                raise ValidationError("Unsupported print orientation")
            if printing.template_style not in {"classic", "modern", "compact"}:
                raise ValidationError("Unsupported print design")
            if printing.font_size not in {"small", "normal", "large"}:
                raise ValidationError("Unsupported print text size")
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", printing.accent_color or ""):
                raise ValidationError("Print accent color must be a hex color")
            if printing.invoice_copy_mode not in {"select", "combined"}:
                raise ValidationError("Unsupported invoice copy behavior")
            copy_labels = [
                label.strip()
                for label in printing.invoice_copy_labels
                if label.strip()
            ]
            if len(copy_labels) != len(set(copy_labels)):
                raise ValidationError("Invoice copy labels must be unique")
            if document_type == "sales_invoice" and not copy_labels:
                raise ValidationError("Configure at least one invoice copy")
            if (
                document_type == "sales_invoice"
                and printing.default_invoice_copy not in copy_labels
            ):
                raise ValidationError(
                    "Default invoice copy must be one of the configured copies"
                )
            normalized[document_type] = template

        profile = self.get_profile()
        profile.bank_accounts = list(bank_accounts)
        profile.document_templates = normalized
        profile.update()
        return self._repo.save(profile)
