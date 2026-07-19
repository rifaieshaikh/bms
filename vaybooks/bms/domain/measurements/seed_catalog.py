"""Seed catalog for measurement specs across person types."""

from __future__ import annotations

from typing import List

from vaybooks.bms.domain.shared.enums import (
    MeasurementFieldType,
    MeasurementSection,
    PersonType,
)

ALL = list(PersonType)
MEN = [PersonType.MEN]
WOMEN = [PersonType.WOMEN]
BOY = [PersonType.BOY_CHILD]
GIRL = [PersonType.GIRL_CHILD]
INFANT = [PersonType.INFANT]
ADULTS = [PersonType.MEN, PersonType.WOMEN]
KIDS = [PersonType.BOY_CHILD, PersonType.GIRL_CHILD]
KIDS_INFANT = KIDS + INFANT
MEN_BOY = [PersonType.MEN, PersonType.BOY_CHILD]
WOMEN_GIRL = [PersonType.WOMEN, PersonType.GIRL_CHILD]


def _field(
    key: str,
    label: str,
    person_types: List[PersonType],
    section: MeasurementSection,
    *,
    is_core: bool = True,
    required: bool = False,
    unit: str = "inch",
    value_type: MeasurementFieldType = MeasurementFieldType.NUMBER,
    options: List[str] | None = None,
    sort_order: int = 0,
) -> dict:
    return {
        "key": key,
        "label": label,
        "person_types": [p.value for p in person_types],
        "section": section.value,
        "value_type": value_type.value,
        "unit": unit,
        "required": required,
        "sort_order": sort_order,
        "is_core": is_core,
        # Seeded fields are active by default so the measurement form shows
        # the full person-type catalog. Spec admin can deactivate Extended ones.
        "is_active": True,
        "help_text": "",
        "options": list(options or []),
    }


# Sort order blocks: Meta 0-99, Head 100, Torso 200, Arms 300, Lower 400, Lengths 500
DEFAULT_MEASUREMENT_SPECS: List[dict] = [
    # --- Meta ---
    _field("height", "Height", ALL, MeasurementSection.META, required=True, sort_order=10),
    _field(
        "infant_size_band",
        "Age / size band",
        INFANT,
        MeasurementSection.META,
        required=True,
        unit="none",
        value_type=MeasurementFieldType.SELECT,
        options=["NB", "3M", "6M", "12M", "18M", "24M"],
        sort_order=5,
    ),
    _field(
        "weight",
        "Weight",
        INFANT,
        MeasurementSection.META,
        unit="kg",
        sort_order=15,
    ),
    # --- Head / neck ---
    _field("head_round", "Head round", KIDS_INFANT, MeasurementSection.HEAD, sort_order=100),
    _field(
        "head_round",
        "Head round",
        ADULTS,
        MeasurementSection.HEAD,
        is_core=False,
        sort_order=100,
    ),
    _field("neck", "Neck / collar", MEN_BOY + WOMEN, MeasurementSection.HEAD, required=True, sort_order=110),
    _field("neck_width", "Neck width", ALL, MeasurementSection.HEAD, is_core=False, sort_order=120),
    _field(
        "front_neck_depth",
        "Front neck depth",
        WOMEN_GIRL,
        MeasurementSection.HEAD,
        required=True,
        sort_order=130,
    ),
    _field(
        "back_neck_depth",
        "Back neck depth",
        WOMEN_GIRL,
        MeasurementSection.HEAD,
        required=True,
        sort_order=140,
    ),
    _field("hat_height", "Hat height", INFANT, MeasurementSection.HEAD, is_core=False, sort_order=150),
    # --- Shoulders / torso ---
    _field("shoulder", "Shoulder (across)", ALL, MeasurementSection.TORSO, required=True, sort_order=200),
    _field("across_front", "Front cross", ADULTS, MeasurementSection.TORSO, is_core=False, sort_order=210),
    _field("across_back", "Back cross", ADULTS, MeasurementSection.TORSO, is_core=False, sort_order=220),
    _field("armhole", "Armhole", ALL, MeasurementSection.TORSO, required=True, sort_order=230),
    _field(
        "armhole_depth",
        "Armhole depth",
        INFANT,
        MeasurementSection.TORSO,
        required=True,
        sort_order=235,
    ),
    _field(
        "armhole_depth",
        "Armhole depth",
        ADULTS + KIDS,
        MeasurementSection.TORSO,
        is_core=False,
        sort_order=235,
    ),
    _field(
        "upper_chest",
        "Upper chest",
        MEN_BOY,
        MeasurementSection.TORSO,
        required=True,
        sort_order=240,
    ),
    _field(
        "upper_bust",
        "Upper bust",
        WOMEN_GIRL,
        MeasurementSection.TORSO,
        required=True,
        sort_order=240,
    ),
    _field("chest", "Chest", MEN_BOY + INFANT, MeasurementSection.TORSO, required=True, sort_order=250),
    _field("bust", "Bust", WOMEN_GIRL, MeasurementSection.TORSO, required=True, sort_order=250),
    _field(
        "under_bust",
        "Under bust",
        WOMEN,
        MeasurementSection.TORSO,
        required=True,
        sort_order=260,
    ),
    _field(
        "under_bust",
        "Under bust",
        GIRL,
        MeasurementSection.TORSO,
        is_core=False,
        sort_order=260,
    ),
    _field(
        "bust_point",
        "Bust point / apex",
        WOMEN,
        MeasurementSection.TORSO,
        required=True,
        sort_order=270,
    ),
    _field(
        "bust_point",
        "Bust point / apex",
        GIRL,
        MeasurementSection.TORSO,
        is_core=False,
        sort_order=270,
    ),
    _field(
        "bust_point_to_bust_point",
        "Bust point distance",
        WOMEN,
        MeasurementSection.TORSO,
        is_core=False,
        sort_order=275,
    ),
    _field("stomach", "Stomach / midriff", MEN + WOMEN, MeasurementSection.TORSO, sort_order=280),
    _field("stomach", "Stomach", BOY, MeasurementSection.TORSO, is_core=False, sort_order=280),
    _field("waist", "Waist", ALL, MeasurementSection.TORSO, required=True, sort_order=290),
    _field(
        "low_waist",
        "Low waist",
        WOMEN_GIRL,
        MeasurementSection.TORSO,
        required=True,
        sort_order=295,
    ),
    _field("hip", "Hip / seat", ALL, MeasurementSection.TORSO, required=True, sort_order=300),
    _field("high_hip", "High hip", WOMEN, MeasurementSection.TORSO, is_core=False, sort_order=305),
    # --- Arms ---
    _field(
        "sleeve_length",
        "Sleeve length",
        ALL,
        MeasurementSection.ARMS,
        required=True,
        sort_order=310,
    ),
    _field(
        "sleeve_round",
        "Sleeve round / cuff",
        ADULTS + KIDS,
        MeasurementSection.ARMS,
        required=True,
        sort_order=320,
    ),
    _field("bicep", "Bicep / upper arm", ADULTS + KIDS, MeasurementSection.ARMS, required=True, sort_order=330),
    _field("bicep", "Upper arm", INFANT, MeasurementSection.ARMS, is_core=False, sort_order=330),
    _field("elbow", "Elbow", ADULTS + KIDS, MeasurementSection.ARMS, is_core=False, sort_order=340),
    _field("wrist", "Wrist", ALL, MeasurementSection.ARMS, sort_order=350),
    # --- Lower ---
    _field(
        "front_rise",
        "Front rise",
        MEN_BOY + WOMEN,
        MeasurementSection.LOWER,
        required=True,
        sort_order=400,
    ),
    _field("back_rise", "Back rise", MEN_BOY, MeasurementSection.LOWER, required=True, sort_order=410),
    _field(
        "full_crotch",
        "Full crotch",
        MEN_BOY + INFANT + WOMEN,
        MeasurementSection.LOWER,
        sort_order=420,
    ),
    _field("inseam", "Inseam", MEN_BOY + WOMEN + INFANT, MeasurementSection.LOWER, required=True, sort_order=430),
    _field(
        "trouser_length",
        "Trouser / outseam length",
        MEN_BOY,
        MeasurementSection.LOWER,
        required=True,
        sort_order=440,
    ),
    _field("thigh", "Thigh", ADULTS + KIDS, MeasurementSection.LOWER, required=True, sort_order=450),
    _field("mid_thigh", "Mid thigh", ADULTS, MeasurementSection.LOWER, is_core=False, sort_order=455),
    _field("knee", "Knee", ADULTS + KIDS, MeasurementSection.LOWER, required=True, sort_order=460),
    _field("calf", "Calf", ADULTS + KIDS, MeasurementSection.LOWER, is_core=False, sort_order=470),
    _field(
        "ankle",
        "Ankle / bottom hem",
        ADULTS + KIDS + INFANT,
        MeasurementSection.LOWER,
        required=True,
        sort_order=480,
    ),
    _field(
        "waist_to_ankle",
        "Waist to ankle",
        KIDS_INFANT,
        MeasurementSection.LOWER,
        required=True,
        sort_order=490,
    ),
    # --- Garment lengths ---
    _field("shirt_length", "Shirt length", MEN_BOY, MeasurementSection.LENGTHS, required=True, sort_order=500),
    _field(
        "kurta_length",
        "Kurta / sherwani length",
        MEN_BOY,
        MeasurementSection.LENGTHS,
        required=True,
        sort_order=510,
    ),
    _field(
        "sherwani_length",
        "Sherwani length",
        MEN,
        MeasurementSection.LENGTHS,
        is_core=False,
        sort_order=515,
    ),
    _field("blazer_length", "Blazer / coat length", MEN, MeasurementSection.LENGTHS, is_core=False, sort_order=520),
    _field(
        "waistcoat_length",
        "Waistcoat / bundi length",
        MEN,
        MeasurementSection.LENGTHS,
        is_core=False,
        sort_order=525,
    ),
    _field(
        "blouse_length",
        "Blouse length",
        WOMEN_GIRL,
        MeasurementSection.LENGTHS,
        required=True,
        sort_order=530,
    ),
    _field(
        "top_length",
        "Top / kurti length",
        WOMEN_GIRL,
        MeasurementSection.LENGTHS,
        required=True,
        sort_order=540,
    ),
    _field(
        "lehenga_length",
        "Lehenga / frock / bottom length",
        WOMEN_GIRL,
        MeasurementSection.LENGTHS,
        required=True,
        sort_order=550,
    ),
    _field(
        "waist_to_floor",
        "Waist to floor",
        WOMEN,
        MeasurementSection.LENGTHS,
        is_core=False,
        sort_order=555,
    ),
    _field("salwar_length", "Salwar length", WOMEN_GIRL, MeasurementSection.LENGTHS, is_core=False, sort_order=560),
    _field(
        "churidar_length",
        "Churidar length",
        ADULTS + KIDS,
        MeasurementSection.LENGTHS,
        is_core=False,
        sort_order=570,
    ),
    _field(
        "pajama_length",
        "Pajama length",
        MEN_BOY,
        MeasurementSection.LENGTHS,
        is_core=False,
        sort_order=580,
    ),
    _field(
        "bottom_length",
        "Bottom / pant length",
        ALL,
        MeasurementSection.LENGTHS,
        is_core=False,
        sort_order=590,
    ),
    _field("shorts_length", "Shorts length", MEN_BOY, MeasurementSection.LENGTHS, is_core=False, sort_order=600),
    _field(
        "romper_length",
        "Frock / romper / set length",
        INFANT,
        MeasurementSection.LENGTHS,
        required=True,
        sort_order=610,
    ),
    _field(
        "shoe_size",
        "Shoe size",
        MEN,
        MeasurementSection.LENGTHS,
        is_core=False,
        unit="none",
        value_type=MeasurementFieldType.TEXT,
        sort_order=620,
    ),
]


def dedupe_seed_specs(rows: List[dict] | None = None) -> List[dict]:
    """Collapse duplicate keys with overlapping person types into one row each.

    Seed data may intentionally list the same key once for Core and once for
    Extended person-type groups. Mongo uniqueness is (key, person_type set),
    so we keep one document per (key, frozenset(person_types), is_core).
    """
    seen = set()
    result = []
    for row in rows or DEFAULT_MEASUREMENT_SPECS:
        identity = (
            row["key"],
            tuple(sorted(row["person_types"])),
            row.get("is_core", True),
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    return result
