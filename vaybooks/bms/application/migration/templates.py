from __future__ import annotations

from io import StringIO
from typing import List

import pandas as pd

from vaybooks.bms.application.migration.schemas import ImportEntityType, fields_for


_SAMPLE_ROWS = {
    ImportEntityType.CATEGORIES: [
        {"name": "Apparel", "parent_name": "", "description": "Root category", "is_active": "true"},
        {"name": "Sarees", "parent_name": "Apparel", "description": "", "is_active": "true"},
    ],
    ImportEntityType.PRODUCTS: [
        {
            "sku": "SKU-001",
            "name": "Sample Product",
            "category": "Apparel",
            "unit": "pcs",
            "selling_rate": "499",
            "hsn_sac": "6204",
            "gst_rate": "5",
            "mrp": "599",
            "opening_qty": "10",
            "weighted_avg_cost": "300",
            "last_purchase_rate": "290",
        }
    ],
    ImportEntityType.CUSTOMERS: [
        {
            "customer_name": "Sample Customer",
            "phone_number": "9876543210",
            "email": "sample@example.com",
            "city": "Chennai",
            "state_code": "33",
            "opening_balance": "1500",
        }
    ],
    ImportEntityType.VENDORS: [
        {
            "vendor_name": "Sample Vendor",
            "phone_number": "9123456780",
            "email": "vendor@example.com",
            "city": "Chennai",
            "state_code": "33",
            "opening_balance": "2000",
        }
    ],
}


def template_csv(entity_type: ImportEntityType) -> str:
    columns: List[str] = [f.key for f in fields_for(entity_type)]
    samples = _SAMPLE_ROWS.get(entity_type, [])
    rows = []
    for sample in samples:
        rows.append({col: sample.get(col, "") for col in columns})
    if not rows:
        rows.append({col: "" for col in columns})
    df = pd.DataFrame(rows, columns=columns)
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()
