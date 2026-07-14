from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class ImportEntityType(str, Enum):
    CATEGORIES = "categories"
    PRODUCTS = "products"
    CUSTOMERS = "customers"
    VENDORS = "vendors"


class DuplicatePolicy(str, Enum):
    SKIP = "skip"
    UPDATE = "update"
    FAIL = "fail"


class FieldType(str, Enum):
    STRING = "string"
    FLOAT = "float"
    BOOL = "bool"
    STATE_CODE = "state_code"
    REGISTRATION_TYPE = "registration_type"


@dataclass(frozen=True)
class TargetField:
    key: str
    label: str
    required: bool = False
    field_type: FieldType = FieldType.STRING
    aliases: tuple[str, ...] = ()


NOT_MAPPED = ""

CATEGORY_FIELDS: List[TargetField] = [
    TargetField("name", "Name", required=True, aliases=("category", "category name", "category_name")),
    TargetField("parent_name", "Parent Name", aliases=("parent", "parent category", "parent_category")),
    TargetField("description", "Description", aliases=("desc", "details")),
    TargetField("is_active", "Is Active", field_type=FieldType.BOOL, aliases=("active", "status")),
]

PRODUCT_FIELDS: List[TargetField] = [
    TargetField("sku", "SKU", required=True, aliases=("item code", "item_code", "product code", "code")),
    TargetField("name", "Name", required=True, aliases=("product", "product name", "item name", "item")),
    TargetField("category", "Category", aliases=("category name", "category_name", "group")),
    TargetField("unit", "Unit", aliases=("uom", "unit of measure")),
    TargetField("selling_rate", "Selling Rate", field_type=FieldType.FLOAT, aliases=("rate", "price", "selling price", "mrp rate")),
    TargetField("hsn_sac", "HSN/SAC", aliases=("hsn", "sac", "hsn code")),
    TargetField("gst_rate", "GST Rate", field_type=FieldType.FLOAT, aliases=("gst", "gst%", "tax rate")),
    TargetField("mrp", "MRP", field_type=FieldType.FLOAT, aliases=("max retail price",)),
    TargetField("opening_qty", "Opening Qty", field_type=FieldType.FLOAT, aliases=("opening stock", "op qty", "opening quantity", "stock")),
    TargetField(
        "weighted_avg_cost",
        "Weighted Avg Cost",
        field_type=FieldType.FLOAT,
        aliases=("wac", "avg cost", "average cost", "cost"),
    ),
    TargetField(
        "last_purchase_rate",
        "Last Purchase Rate",
        field_type=FieldType.FLOAT,
        aliases=("purchase rate", "last rate", "buy rate"),
    ),
]

_PARTY_COMMON: List[TargetField] = [
    TargetField("phone_number", "Phone", required=True, aliases=("phone", "mobile", "mobile number", "contact number")),
    TargetField("alternate_phone_number", "Alternate Phone", aliases=("alt phone", "alternate mobile")),
    TargetField("email", "Email", aliases=("email id", "e-mail")),
    TargetField("contact_person", "Contact Person", aliases=("contact", "contact name")),
    TargetField("address_line1", "Address Line 1", aliases=("address", "address1", "street")),
    TargetField("address_line2", "Address Line 2", aliases=("address2",)),
    TargetField("city", "City", aliases=("town",)),
    TargetField("state_code", "State Code", field_type=FieldType.STATE_CODE, aliases=("state", "state name")),
    TargetField("pincode", "Pincode", aliases=("pin", "zip", "postal code")),
    TargetField("country", "Country"),
    TargetField("gstin", "GSTIN", aliases=("gst", "gst no", "gst number")),
    TargetField("pan", "PAN", aliases=("pan number", "pan no")),
    TargetField(
        "registration_type",
        "Registration Type",
        field_type=FieldType.REGISTRATION_TYPE,
        aliases=("gst type", "reg type"),
    ),
    TargetField("msme_number", "MSME Number", aliases=("msme", "udyam")),
    TargetField("notes", "Notes", aliases=("remark", "remarks")),
    TargetField(
        "opening_balance",
        "Opening Balance",
        field_type=FieldType.FLOAT,
        aliases=("op bal", "op. balance", "opening bal", "balance", "receivable", "payable"),
    ),
]

CUSTOMER_FIELDS: List[TargetField] = [
    TargetField(
        "customer_name",
        "Customer Name",
        required=True,
        aliases=("name", "party name", "party", "customer", "account name"),
    ),
    *_PARTY_COMMON,
]

VENDOR_FIELDS: List[TargetField] = [
    TargetField(
        "vendor_name",
        "Vendor Name",
        required=True,
        aliases=("name", "party name", "party", "vendor", "supplier", "account name"),
    ),
    *_PARTY_COMMON,
    TargetField("bank_account_holder", "Bank Account Holder", aliases=("account holder", "beneficiary")),
    TargetField("bank_account_number", "Bank Account Number", aliases=("account number", "bank account", "a/c no")),
    TargetField("bank_ifsc", "Bank IFSC", aliases=("ifsc", "ifsc code")),
    TargetField("bank_name", "Bank Name", aliases=("bank",)),
]

ENTITY_FIELDS: Dict[ImportEntityType, List[TargetField]] = {
    ImportEntityType.CATEGORIES: CATEGORY_FIELDS,
    ImportEntityType.PRODUCTS: PRODUCT_FIELDS,
    ImportEntityType.CUSTOMERS: CUSTOMER_FIELDS,
    ImportEntityType.VENDORS: VENDOR_FIELDS,
}

ENTITY_TITLES: Dict[ImportEntityType, str] = {
    ImportEntityType.CATEGORIES: "Categories",
    ImportEntityType.PRODUCTS: "Products",
    ImportEntityType.CUSTOMERS: "Customers",
    ImportEntityType.VENDORS: "Vendors",
}


def fields_for(entity_type: ImportEntityType) -> List[TargetField]:
    return ENTITY_FIELDS[entity_type]


def required_keys(entity_type: ImportEntityType) -> List[str]:
    return [f.key for f in fields_for(entity_type) if f.required]


def field_by_key(entity_type: ImportEntityType, key: str) -> Optional[TargetField]:
    for field in fields_for(entity_type):
        if field.key == key:
            return field
    return None
