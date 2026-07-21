"""Vertical demo-seed profile definitions (Kerala-focused catalogs)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vaybooks.bms.domain.shared.enums import PartyRegistrationType

KERALA_STATE = "32"

KERALA_FIRST = (
    "Anjali", "Arun", "Deepa", "Fathima", "Gopika", "Hari", "Indu", "Jayan",
    "Kavya", "Lakshmi", "Manu", "Nithin", "Priya", "Ravi", "Sneha", "Suresh",
    "Meera", "Vineeth", "Asha", "Biju", "Chitra", "Divya", "Elias", "Fahad",
    "Geetha", "Hussain", "Isha", "Joseph", "Krishna", "Leena", "Mohan", "Neethu",
)
KERALA_LAST = (
    "Nair", "Menon", "Pillai", "Kurup", "Varma", "Thomas", "Joseph", "Mathew",
    "Kumar", "Das", "Rajan", "Krishnan", "George", "Philip", "Babu", "Varghese",
)
KERALA_CITIES = (
    ("Kochi", "682001"),
    ("Thrissur", "680001"),
    ("Kozhikode", "673001"),
    ("Kollam", "691001"),
    ("Alappuzha", "688001"),
    ("Kannur", "670001"),
    ("Palakkad", "678001"),
    ("Kottayam", "686001"),
    ("Malappuram", "676505"),
    ("Ernakulam", "682011"),
)

# Mix weights: (unregistered, registered, composition) — sum to 1.0
MIX_RETAIL = (0.75, 0.20, 0.05)
MIX_TRADE = (0.40, 0.40, 0.20)
MIX_PHARMA = (0.45, 0.45, 0.10)

DEMO_UNITS = (
    ("pcs", "Pieces"),
    ("m", "Metres"),
    ("kg", "Kilograms"),
    ("roll", "Roll"),
    ("set", "Set"),
    ("l", "Litre"),
    ("box", "Box"),
)


@dataclass(frozen=True)
class ProfileDef:
    key: str
    label: str
    sku_prefix: str
    cust_phone_base: int
    vend_phone_base: int
    party_mix: tuple[float, float, float]
    # Roots: (name, description, child_name_templates)
    category_roots: tuple[tuple[str, str, tuple[str, ...]], ...]
    product_templates: tuple[dict[str, Any], ...]
    business: dict[str, Any] = field(default_factory=dict)


def _biz(
    legal: str,
    trade: str,
    registration: str = "Registered",
    gstin: str = "",
    pan: str = "",
) -> dict[str, Any]:
    return {
        "legal_name": legal,
        "trade_name": trade,
        "registration": registration,
        "state": KERALA_STATE,
        "gstin": gstin,
        "pan": pan,
        "composition_rate": 1.0,
    }


MULTI_BUSINESS = _biz(
    "Seed Multi Vertical Demo",
    "Seed Multi Demo",
    gstin="32BBBBB0000B1Z5",
    pan="BBBBB0000B",
)

PROFILE_ORDER = (
    "boutique",
    "pos",
    "pharma",
    "groceries",
    "footwear",
    "fancy",
    "paint",
    "tiles_granites",
    "hardware",
    "electricals",
)

PROFILES: dict[str, ProfileDef] = {
    "boutique": ProfileDef(
        key="boutique",
        label="Boutique",
        sku_prefix="BOUT",
        cust_phone_base=9000100000,
        vend_phone_base=9100100000,
        party_mix=MIX_RETAIL,
        category_roots=(
            ("Sarees", "Sarees and draped wear", ("Silk Saree", "Cotton Saree", "Kasavu", "Designer Saree", "Party Saree")),
            ("Salwar Kurtis", "Salwar and kurtis", ("Churidar", "Anarkali", "Straight Kurti", "Palazzo Set")),
            ("Lehengas", "Lehenga sets", ("Bridal Lehenga", "Party Lehenga", "Kids Lehenga")),
            ("Kids Wear", "Children apparel", ("Frock", "Boys Kurta", "School Uniform")),
            ("Fabrics", "Dress materials", ("Cotton Fabric", "Silk Fabric", "Blouse Piece", "Dupatta")),
            ("Accessories", "Boutique accessories", ("Bangles", "Clutch", "Hair Clip", "Stole")),
            ("Bridal", "Bridal collection", ("Bridal Set", "Muhurtham Wear", "Reception Wear")),
        ),
        product_templates=(
            {"name": "Kasavu Saree", "unit_code": "pcs", "hsn_sac": "5007", "selling_rate": 3500, "mrp": 3999, "gst_rate": 5, "opening_qty": 12},
            {"name": "Mundum Neriyathum", "unit_code": "set", "hsn_sac": "5007", "selling_rate": 2800, "mrp": 3200, "gst_rate": 5, "opening_qty": 8},
            {"name": "Cotton Churidar Set", "unit_code": "set", "hsn_sac": "6204", "selling_rate": 1499, "mrp": 1799, "gst_rate": 12, "opening_qty": 20},
            {"name": "Silk Anarkali", "unit_code": "pcs", "hsn_sac": "6204", "selling_rate": 2499, "mrp": 2999, "gst_rate": 12, "opening_qty": 15},
            {"name": "Blouse Material", "unit_code": "m", "hsn_sac": "5208", "selling_rate": 350, "mrp": 399, "gst_rate": 5, "opening_qty": 80},
        ),
        business=_biz("Kochi Silk Boutique", "Kochi Silk", gstin="32AAAAA0000A1Z5", pan="AAAAA0000A"),
    ),
    "pos": ProfileDef(
        key="pos",
        label="Interior POS",
        sku_prefix="POS",
        cust_phone_base=9000200000,
        vend_phone_base=9100200000,
        party_mix=MIX_TRADE,
        category_roots=(
            ("Furniture", "Home furniture", ("Sofa", "Dining", "Bedroom", "Office Chair")),
            ("Lighting", "Lights and lamps", ("Ceiling", "Table Lamp", "LED Panel", "Chandelier")),
            ("Curtains", "Soft furnishings", ("Door Curtain", "Window Curtain", "Cushion")),
            ("Wall Decor", "Wall items", ("Mirror", "Painting", "Wall Shelf")),
            ("Flooring", "Floor coverings", ("Carpet", "Mat", "Runner")),
            ("Kitchen Dining", "Kitchen and dining", ("Dinner Set", "Cutlery", "Storage Jar")),
            ("Home Storage", "Storage solutions", ("Wardrobe Organiser", "Shoe Rack", "Basket")),
        ),
        product_templates=(
            {"name": "Teak Sofa 3 Seater", "unit_code": "pcs", "hsn_sac": "9401", "selling_rate": 28999, "mrp": 32999, "gst_rate": 18, "opening_qty": 4},
            {"name": "LED Panel 18W", "unit_code": "pcs", "hsn_sac": "9405", "selling_rate": 899, "mrp": 1099, "gst_rate": 18, "opening_qty": 40},
            {"name": "Cotton Door Curtain", "unit_code": "pcs", "hsn_sac": "6303", "selling_rate": 799, "mrp": 999, "gst_rate": 12, "opening_qty": 30},
            {"name": "Wall Mirror Round", "unit_code": "pcs", "hsn_sac": "7009", "selling_rate": 1499, "mrp": 1799, "gst_rate": 18, "opening_qty": 12},
            {"name": "Jute Floor Mat", "unit_code": "pcs", "hsn_sac": "5702", "selling_rate": 599, "mrp": 749, "gst_rate": 12, "opening_qty": 25},
        ),
        business=_biz("Alappuzha Home Interiors", "Home Interiors", gstin="32CCCCC0000C1Z5", pan="CCCCC0000C"),
    ),
    "pharma": ProfileDef(
        key="pharma",
        label="Pharmacy",
        sku_prefix="PHAR",
        cust_phone_base=9000300000,
        vend_phone_base=9100300000,
        party_mix=MIX_PHARMA,
        category_roots=(
            ("Tablets", "Oral tablets", ("Analgesic", "Antibiotic", "Antacid", "Vitamin")),
            ("Syrups", "Liquid medicines", ("Cough Syrup", "Tonic", "Pediatric")),
            ("OTC", "Over the counter", ("Balm", "Bandage", "Sanitizer")),
            ("Surgical", "Surgical supplies", ("Syringe", "Gloves", "Mask")),
            ("Personal Care", "Wellness", ("Shampoo", "Soap", "Toothpaste")),
            ("Ayurveda", "Ayurvedic", ("Kashayam", "Churnam", "Oil")),
        ),
        product_templates=(
            {"name": "Paracetamol 500mg", "unit_code": "box", "hsn_sac": "3004", "selling_rate": 28, "mrp": 32, "gst_rate": 12, "opening_qty": 200},
            {"name": "Cough Syrup 100ml", "unit_code": "pcs", "hsn_sac": "3004", "selling_rate": 95, "mrp": 110, "gst_rate": 12, "opening_qty": 60},
            {"name": "Surgical Gloves M", "unit_code": "box", "hsn_sac": "4015", "selling_rate": 180, "mrp": 220, "gst_rate": 12, "opening_qty": 40},
            {"name": "Hand Sanitizer 500ml", "unit_code": "pcs", "hsn_sac": "3808", "selling_rate": 120, "mrp": 149, "gst_rate": 18, "opening_qty": 80},
            {"name": "Ayurvedic Hair Oil", "unit_code": "pcs", "hsn_sac": "3305", "selling_rate": 165, "mrp": 199, "gst_rate": 18, "opening_qty": 35},
        ),
        business=_biz("Thrissur Care Pharmacy", "Care Pharmacy", gstin="32DDDDD0000D1Z5", pan="DDDDD0000D"),
    ),
    "groceries": ProfileDef(
        key="groceries",
        label="Groceries",
        sku_prefix="GROC",
        cust_phone_base=9000400000,
        vend_phone_base=9100400000,
        party_mix=MIX_RETAIL,
        category_roots=(
            ("Staples", "Rice and grains", ("Rice", "Wheat", "Dhal", "Atta")),
            ("Spices", "Spices and masala", ("Turmeric", "Chilli", "Coriander", "Garam Masala")),
            ("Oils", "Cooking oils", ("Coconut Oil", "Sunflower", "Mustard")),
            ("Dairy", "Dairy products", ("Milk", "Curd", "Butter", "Ghee")),
            ("Snacks", "Packaged snacks", ("Biscuits", "Chips", "Nuts")),
            ("Household", "Cleaning", ("Detergent", "Soap", "Dishwash")),
        ),
        product_templates=(
            {"name": "Matta Rice 10kg", "unit_code": "pcs", "hsn_sac": "1006", "selling_rate": 520, "mrp": 560, "gst_rate": 5, "opening_qty": 50},
            {"name": "Coconut Oil 1L", "unit_code": "l", "hsn_sac": "1513", "selling_rate": 210, "mrp": 240, "gst_rate": 5, "opening_qty": 70},
            {"name": "Turmeric Powder 200g", "unit_code": "pcs", "hsn_sac": "0910", "selling_rate": 55, "mrp": 65, "gst_rate": 5, "opening_qty": 100},
            {"name": "Banana Chips 400g", "unit_code": "pcs", "hsn_sac": "2008", "selling_rate": 120, "mrp": 140, "gst_rate": 12, "opening_qty": 45},
            {"name": "Washing Powder 1kg", "unit_code": "pcs", "hsn_sac": "3402", "selling_rate": 95, "mrp": 110, "gst_rate": 18, "opening_qty": 60},
        ),
        business=_biz("Kozhikode Fresh Mart", "Fresh Mart", registration="Unregistered"),
    ),
    "footwear": ProfileDef(
        key="footwear",
        label="Footwear",
        sku_prefix="FOOT",
        cust_phone_base=9000500000,
        vend_phone_base=9100500000,
        party_mix=MIX_RETAIL,
        category_roots=(
            ("Men", "Men footwear", ("Formal", "Casual", "Sports", "Sandals")),
            ("Women", "Women footwear", ("Heels", "Flats", "Sandals", "Sports")),
            ("Kids", "Kids footwear", ("School", "Sports", "Sandals")),
            ("Leather Care", "Care products", ("Polish", "Cream", "Brush")),
            ("Accessories", "Socks and extras", ("Socks", "Insoles", "Laces")),
        ),
        product_templates=(
            {"name": "Men Formal Derby", "unit_code": "pcs", "hsn_sac": "6403", "selling_rate": 2499, "mrp": 2999, "gst_rate": 18, "opening_qty": 18},
            {"name": "Women Kolhapuri", "unit_code": "pcs", "hsn_sac": "6403", "selling_rate": 899, "mrp": 1099, "gst_rate": 18, "opening_qty": 25},
            {"name": "Kids School Shoes", "unit_code": "pcs", "hsn_sac": "6404", "selling_rate": 699, "mrp": 849, "gst_rate": 18, "opening_qty": 30},
            {"name": "Sports Runner", "unit_code": "pcs", "hsn_sac": "6404", "selling_rate": 1899, "mrp": 2299, "gst_rate": 18, "opening_qty": 20},
            {"name": "Shoe Polish Black", "unit_code": "pcs", "hsn_sac": "3405", "selling_rate": 65, "mrp": 80, "gst_rate": 18, "opening_qty": 80},
        ),
        business=_biz("Kollam Step Style", "Step Style", gstin="32EEEEE0000E1Z5", pan="EEEEE0000E"),
    ),
    "fancy": ProfileDef(
        key="fancy",
        label="Fancy Store",
        sku_prefix="FANCY",
        cust_phone_base=9000600000,
        vend_phone_base=9100600000,
        party_mix=MIX_RETAIL,
        category_roots=(
            ("Jewellery", "Imitation jewellery", ("Necklace", "Earring", "Bangle", "Ring")),
            ("Gifts", "Gift items", ("Frame", "Mug", "Toy", "Hamper")),
            ("Cosmetics", "Beauty", ("Lipstick", "Compact", "Kajal")),
            ("Party Wear", "Party extras", ("Tiara", "Gloves", "Stole")),
            ("Stationery Fancy", "Fancy stationery", ("Diary", "Pen Set", "Sticker")),
        ),
        product_templates=(
            {"name": "Temple Necklace Set", "unit_code": "set", "hsn_sac": "7117", "selling_rate": 499, "mrp": 699, "gst_rate": 3, "opening_qty": 40},
            {"name": "Gift Photo Frame", "unit_code": "pcs", "hsn_sac": "4414", "selling_rate": 249, "mrp": 299, "gst_rate": 18, "opening_qty": 35},
            {"name": "Matte Lipstick", "unit_code": "pcs", "hsn_sac": "3304", "selling_rate": 199, "mrp": 249, "gst_rate": 18, "opening_qty": 60},
            {"name": "Party Tiara", "unit_code": "pcs", "hsn_sac": "7117", "selling_rate": 149, "mrp": 199, "gst_rate": 3, "opening_qty": 25},
            {"name": "Decor Diary", "unit_code": "pcs", "hsn_sac": "4820", "selling_rate": 120, "mrp": 150, "gst_rate": 18, "opening_qty": 50},
        ),
        business=_biz("Kannur Fancy World", "Fancy World", registration="Unregistered"),
    ),
    "paint": ProfileDef(
        key="paint",
        label="Paint Shop",
        sku_prefix="PAINT",
        cust_phone_base=9000700000,
        vend_phone_base=9100700000,
        party_mix=MIX_TRADE,
        category_roots=(
            ("Emulsions", "Interior emulsions", ("Premium", "Economy", "Anti Fungal")),
            ("Enamels", "Enamel paints", ("Gloss", "Matt", "Metal")),
            ("Primers", "Primers", ("Wall Primer", "Wood Primer", "Metal Primer")),
            ("Tools", "Painting tools", ("Brush", "Roller", "Tray")),
            ("Putty Thinners", "Putty and thinners", ("Wall Putty", "Thinner", "Turpentine")),
        ),
        product_templates=(
            {"name": "Interior Emulsion 20L", "unit_code": "pcs", "hsn_sac": "3209", "selling_rate": 4200, "mrp": 4800, "gst_rate": 18, "opening_qty": 15},
            {"name": "Enamel Gloss 1L", "unit_code": "l", "hsn_sac": "3208", "selling_rate": 380, "mrp": 450, "gst_rate": 18, "opening_qty": 40},
            {"name": "Wall Primer 10L", "unit_code": "pcs", "hsn_sac": "3209", "selling_rate": 1450, "mrp": 1650, "gst_rate": 18, "opening_qty": 20},
            {"name": "Paint Roller Set", "unit_code": "set", "hsn_sac": "9603", "selling_rate": 220, "mrp": 280, "gst_rate": 18, "opening_qty": 50},
            {"name": "Wall Putty 40kg", "unit_code": "pcs", "hsn_sac": "3214", "selling_rate": 680, "mrp": 750, "gst_rate": 18, "opening_qty": 25},
        ),
        business=_biz("Palakkad Colour Hub", "Colour Hub", gstin="32FFFFF0000F1Z5", pan="FFFFF0000F"),
    ),
    "tiles_granites": ProfileDef(
        key="tiles_granites",
        label="Tiles & Granites",
        sku_prefix="TILE",
        cust_phone_base=9000800000,
        vend_phone_base=9100800000,
        party_mix=MIX_TRADE,
        category_roots=(
            ("Floor Tiles", "Floor tiles", ("Vitrified", "Ceramic", "Anti Skid")),
            ("Wall Tiles", "Wall tiles", ("Kitchen", "Bathroom", "Designer")),
            ("Granite", "Granite slabs", ("Black Galaxy", "Absolute Black", "Kashmir White")),
            ("Adhesives", "Tile adhesives", ("Thinset", "Epoxy", "Grout")),
            ("Tools", "Fixing tools", ("Cutter", "Spacer", "Trowel")),
        ),
        product_templates=(
            {"name": "Vitrified Tile 60x60", "unit_code": "box", "hsn_sac": "6907", "selling_rate": 980, "mrp": 1150, "gst_rate": 18, "opening_qty": 40},
            {"name": "Bathroom Wall Tile", "unit_code": "box", "hsn_sac": "6908", "selling_rate": 650, "mrp": 780, "gst_rate": 18, "opening_qty": 35},
            {"name": "Black Galaxy Granite", "unit_code": "pcs", "hsn_sac": "6802", "selling_rate": 180, "mrp": 220, "gst_rate": 18, "opening_qty": 100},
            {"name": "Tile Adhesive 20kg", "unit_code": "pcs", "hsn_sac": "3214", "selling_rate": 420, "mrp": 490, "gst_rate": 18, "opening_qty": 50},
            {"name": "Tile Cutter Manual", "unit_code": "pcs", "hsn_sac": "8205", "selling_rate": 899, "mrp": 1099, "gst_rate": 18, "opening_qty": 12},
        ),
        business=_biz("Kottayam Stone & Tile", "Stone & Tile", gstin="32GGGGG0000G1Z5", pan="GGGGG0000G"),
    ),
    "hardware": ProfileDef(
        key="hardware",
        label="Hardware",
        sku_prefix="HW",
        cust_phone_base=9000900000,
        vend_phone_base=9100900000,
        party_mix=MIX_TRADE,
        category_roots=(
            ("Fasteners", "Nuts and bolts", ("Bolt", "Nut", "Screw", "Washer")),
            ("Tools", "Hand tools", ("Hammer", "Pliers", "Screwdriver", "Spanner")),
            ("Plumbing", "Plumbing fittings", ("PVC Pipe", "Tap", "Valve", "Elbow")),
            ("Locks", "Locks and hinges", ("Door Lock", "Padlock", "Hinge")),
            ("Safety", "Safety gear", ("Gloves", "Goggles", "Helmet")),
        ),
        product_templates=(
            {"name": "SS Screw Pack 100", "unit_code": "box", "hsn_sac": "7318", "selling_rate": 85, "mrp": 110, "gst_rate": 18, "opening_qty": 90},
            {"name": "Claw Hammer", "unit_code": "pcs", "hsn_sac": "8205", "selling_rate": 320, "mrp": 399, "gst_rate": 18, "opening_qty": 25},
            {"name": "PVC Pipe 1 inch 3m", "unit_code": "pcs", "hsn_sac": "3917", "selling_rate": 145, "mrp": 175, "gst_rate": 18, "opening_qty": 60},
            {"name": "Door Lock Mortise", "unit_code": "pcs", "hsn_sac": "8301", "selling_rate": 890, "mrp": 1090, "gst_rate": 18, "opening_qty": 18},
            {"name": "Work Gloves Pair", "unit_code": "pcs", "hsn_sac": "6116", "selling_rate": 75, "mrp": 95, "gst_rate": 12, "opening_qty": 70},
        ),
        business=_biz("Malappuram Hardware Depot", "Hardware Depot", gstin="32HHHHH0000H1Z5", pan="HHHHH0000H"),
    ),
    "electricals": ProfileDef(
        key="electricals",
        label="Electricals",
        sku_prefix="ELEC",
        cust_phone_base=9001000000,
        vend_phone_base=9101000000,
        party_mix=MIX_TRADE,
        category_roots=(
            ("Wires", "Cables and wires", ("1.5 sqmm", "2.5 sqmm", "4 sqmm", "Flexible")),
            ("Switches", "Switches and sockets", ("Modular Switch", "Socket", "Regulator")),
            ("Lights", "Lighting", ("LED Bulb", "Tube", "Downlight")),
            ("Fans", "Fans", ("Ceiling Fan", "Table Fan", "Exhaust")),
            ("Protection", "MCB and boards", ("MCB", "DB", "ELCB")),
            ("Appliances", "Small appliances", ("Iron", "Mixer", "Heater")),
        ),
        product_templates=(
            {"name": "Copper Wire 1.5sqmm 90m", "unit_code": "roll", "hsn_sac": "8544", "selling_rate": 1850, "mrp": 2100, "gst_rate": 18, "opening_qty": 20},
            {"name": "Modular Switch 6A", "unit_code": "pcs", "hsn_sac": "8536", "selling_rate": 95, "mrp": 120, "gst_rate": 18, "opening_qty": 120},
            {"name": "LED Bulb 9W", "unit_code": "pcs", "hsn_sac": "8539", "selling_rate": 89, "mrp": 120, "gst_rate": 18, "opening_qty": 150},
            {"name": "Ceiling Fan 1200mm", "unit_code": "pcs", "hsn_sac": "8414", "selling_rate": 2499, "mrp": 2899, "gst_rate": 18, "opening_qty": 15},
            {"name": "MCB 16A Single Pole", "unit_code": "pcs", "hsn_sac": "8536", "selling_rate": 180, "mrp": 220, "gst_rate": 18, "opening_qty": 45},
        ),
        business=_biz("Ernakulam Power & Lights", "Power & Lights", gstin="32JJJJJ0000J1Z5", pan="JJJJJ0000J"),
    ),
}

_PROFILE_ALIASES = {
    "interior": "pos",
    "tiles": "tiles_granites",
    "tile": "tiles_granites",
    "granite": "tiles_granites",
    "tiles-granites": "tiles_granites",
    "paint_shop": "paint",
    "fancy_store": "fancy",
}


def normalize_profile_key(raw: str) -> str | None:
    key = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not key:
        return None
    key = _PROFILE_ALIASES.get(key, key)
    if key in PROFILES:
        return key
    return None


def profiles_to_run(seed_profile: str) -> list[str]:
    """Parse SEED_PROFILE into ordered unique profile keys.

    Empty / ``none`` / ``off`` / ``false`` disables profile demo seeding.
    """
    raw = (seed_profile or "").strip()
    if not raw or raw.lower() in {"none", "off", "false", "0"}:
        return []
    if raw.lower() == "all":
        return list(PROFILE_ORDER)
    out: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        key = normalize_profile_key(part)
        if key is None:
            continue
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def registration_for_index(
    index: int, count: int, mix: tuple[float, float, float]
) -> PartyRegistrationType:
    if count <= 0:
        return PartyRegistrationType.UNREGISTERED
    u, r, _c = mix
    unreg_end = int(round(count * u))
    reg_end = unreg_end + int(round(count * r))
    if index < unreg_end:
        return PartyRegistrationType.UNREGISTERED
    if index < reg_end:
        return PartyRegistrationType.REGISTERED
    return PartyRegistrationType.COMPOSITION


def expand_category_tree(
    profile: ProfileDef, count: int
) -> list[tuple[str | None, str, str]]:
    """Return (parent_name|None, name, description) rows up to count."""
    rows: list[tuple[str | None, str, str]] = []
    for root, desc, children in profile.category_roots:
        rows.append((None, root, desc))
        for child in children:
            rows.append((root, child, f"{child} under {root}"))
    # Pad with numbered leaf categories under rotating roots
    roots = [r[0] for r in profile.category_roots]
    i = 1
    while len(rows) < count and roots:
        root = roots[(i - 1) % len(roots)]
        rows.append((root, f"{root} Line {i}", f"Seed line {i} for {root}"))
        i += 1
    return rows[:count]


def expand_products(profile: ProfileDef, count: int) -> list[dict[str, Any]]:
    templates = profile.product_templates
    leaf_names = []
    for _root, _desc, children in profile.category_roots:
        leaf_names.extend(children)
    if not leaf_names:
        leaf_names = [r[0] for r in profile.category_roots]
    products: list[dict[str, Any]] = []
    for i in range(count):
        tmpl = templates[i % len(templates)]
        cat = leaf_names[i % len(leaf_names)]
        sku = f"{profile.sku_prefix}-{i + 1:04d}"
        name = tmpl["name"] if i < len(templates) else f"{tmpl['name']} {i + 1}"
        products.append(
            {
                "sku": sku,
                "name": name,
                "category_names": (cat,),
                "unit_code": tmpl["unit_code"],
                "hsn_sac": tmpl["hsn_sac"],
                "selling_rate": float(tmpl["selling_rate"]),
                "mrp": float(tmpl["mrp"]),
                "gst_rate": float(tmpl["gst_rate"]),
                "opening_qty": float(tmpl["opening_qty"]) + (i % 5),
            }
        )
    return products


def _gstin_for(state: str, pan: str, check: str = "1") -> str:
    pan = (pan or "AAAAA0000A")[:10]
    return f"{state}{pan}{check}Z5"


def build_customer_rows(profile: ProfileDef, count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(count):
        first = KERALA_FIRST[i % len(KERALA_FIRST)]
        last = KERALA_LAST[(i // len(KERALA_FIRST)) % len(KERALA_LAST)]
        city, pin = KERALA_CITIES[i % len(KERALA_CITIES)]
        reg = registration_for_index(i, count, profile.party_mix)
        phone = str(profile.cust_phone_base + i + 1)
        row: dict[str, Any] = {
            "customer_name": f"{first} {last}",
            "phone_number": phone,
            "city": city,
            "state_code": KERALA_STATE,
            "pincode": pin,
            "address_line1": f"{(i % 40) + 1} MG Road",
            "registration_type": reg,
        }
        if reg != PartyRegistrationType.UNREGISTERED:
            pan = f"C{profile.key[:4].upper():<4}{i:04d}"[:10].replace(" ", "X")
            # Ensure PAN-like length 10
            pan = (pan + "XXXXXXXXXX")[:10]
            row["pan"] = pan
            row["gstin"] = _gstin_for(KERALA_STATE, pan, "1" if i % 9 else "2")
        rows.append(row)
    return rows


def build_vendor_rows(profile: ProfileDef, count: int) -> list[dict[str, Any]]:
    trade_suffix = (
        "Traders", "Supplies", "Agencies", "Distributors", "Stores", "Mart",
    )
    rows: list[dict[str, Any]] = []
    for i in range(count):
        last = KERALA_LAST[i % len(KERALA_LAST)]
        city, pin = KERALA_CITIES[i % len(KERALA_CITIES)]
        reg = registration_for_index(i, count, profile.party_mix)
        phone = str(profile.vend_phone_base + i + 1)
        row: dict[str, Any] = {
            "vendor_name": f"{city} {last} {trade_suffix[i % len(trade_suffix)]}",
            "phone_number": phone,
            "city": city,
            "state_code": KERALA_STATE,
            "pincode": pin,
            "address_line1": f"{(i % 30) + 1} Market Road",
            "registration_type": reg,
        }
        if reg != PartyRegistrationType.UNREGISTERED:
            pan = f"V{profile.key[:4].upper():<4}{i:04d}"[:10].replace(" ", "X")
            pan = (pan + "XXXXXXXXXX")[:10]
            row["pan"] = pan
            row["gstin"] = _gstin_for(KERALA_STATE, pan, "3")
        rows.append(row)
    return rows


def default_business_for(profile_key: str) -> dict[str, Any]:
    if profile_key == "multi":
        return dict(MULTI_BUSINESS)
    profile = PROFILES.get(profile_key)
    if profile:
        return dict(profile.business)
    return dict(MULTI_BUSINESS)


def resolve_business_settings(
    selected_profiles: list[str],
    blocks: dict[str, dict[str, Any]] | None = None,
    flat_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pick business block for one vs multi profile selection."""
    blocks = blocks or {}
    if len(selected_profiles) == 1:
        key = selected_profiles[0]
        base = default_business_for(key)
        base.update(blocks.get(key) or {})
    else:
        base = default_business_for("multi")
        base.update(blocks.get("multi") or {})
    if flat_overlay:
        # Map AppSettings-style keys / short keys onto block fields
        mapping = {
            "legal_name": ("legal_name", "seed_business_legal_name"),
            "trade_name": ("trade_name", "seed_business_trade_name"),
            "registration": ("registration", "seed_business_registration"),
            "state": ("state", "seed_business_state"),
            "gstin": ("gstin", "seed_business_gstin"),
            "pan": ("pan", "seed_business_pan"),
            "composition_rate": ("composition_rate", "seed_composition_rate"),
        }
        for field_name, aliases in mapping.items():
            for alias in aliases:
                if alias in flat_overlay and flat_overlay[alias] not in (None, ""):
                    base[field_name] = flat_overlay[alias]
                    break
    return base
