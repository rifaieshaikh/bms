"""Unify document print design: one accent color and template style for all.

Saved templates that still carry an old per-document default (accent + style)
are moved to the unified default. Customized values are left untouched.
"""

from __future__ import annotations

from pymongo.database import Database

UNIFIED_STYLE = "classic"
UNIFIED_ACCENT = "#1F4E78"

# (template_style, accent_color) defaults that shipped before unification.
OLD_DEFAULTS = {
    "estimate": ("modern", "#2563EB"),
    "quotation": ("modern", "#0F766E"),
    "sales_order": ("classic", "#7C3AED"),
    "delivery_note": ("compact", "#475569"),
    "sales_invoice": ("classic", "#1F4E78"),
    "measurement_sheet": ("classic", "#0F766E"),
    "customization_item": ("classic", "#7C3AED"),
    "advance_receipt": ("compact", "#1F4E78"),
}


def up(db: Database) -> None:
    for profile in db.business_profile.find({}, {"document_templates": 1}):
        templates = profile.get("document_templates") or {}
        updates: dict[str, str] = {}
        for name, template in templates.items():
            print_settings = (template or {}).get("print_settings") or {}
            old_style, old_accent = OLD_DEFAULTS.get(name, (None, None))
            style = print_settings.get("template_style")
            accent = (print_settings.get("accent_color") or "").upper()
            if style == old_style and accent == (old_accent or "").upper():
                prefix = f"document_templates.{name}.print_settings"
                updates[f"{prefix}.template_style"] = UNIFIED_STYLE
                updates[f"{prefix}.accent_color"] = UNIFIED_ACCENT
        if updates:
            db.business_profile.update_one(
                {"_id": profile["_id"]}, {"$set": updates}
            )
