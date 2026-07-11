from datetime import date, datetime
from typing import Any, List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    ProductCategory,
    ProductUnit,
    StockMovement,
)
from vaybooks.bms.domain.inventory.field_definitions import (
    ProductFieldDefinition,
    ProductFieldType,
)
from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType
from vaybooks.bms.domain.shared.item_tax import (
    ItemTaxProfile,
    ProductGstSlab,
    ProductMrpSlab,
)


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _parent_key(parent_id: Optional[str]) -> Optional[str]:
    return parent_id or None


class MongoProductUnitRepository:
    def __init__(self, db: Database):
        self._collection = db.product_units
        self._products = db.inventory_products

    def _to_doc(self, unit: ProductUnit) -> dict:
        return {
            "_id": unit.id,
            "code": unit.code,
            "label": unit.label,
            "is_active": unit.is_active,
            "created_at": unit.created_at,
            "updated_at": unit.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProductUnit:
        return ProductUnit(
            id=doc["_id"],
            code=doc["code"],
            label=doc.get("label") or doc["code"],
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, unit: ProductUnit) -> ProductUnit:
        self._collection.replace_one({"_id": unit.id}, self._to_doc(unit), upsert=True)
        return unit

    def find_by_id(self, unit_id: str) -> Optional[ProductUnit]:
        doc = self._collection.find_one({"_id": unit_id})
        return self._from_doc(doc) if doc else None

    def find_by_code(self, code: str) -> Optional[ProductUnit]:
        doc = self._collection.find_one({"code": code.strip().lower()})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> List[ProductUnit]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query).sort("code", 1)]

    def count_products_using(self, unit_id: str) -> int:
        return self._products.count_documents({"unit_id": unit_id})


class MongoProductCategoryRepository:
    def __init__(self, db: Database):
        self._collection = db.product_categories

    def _to_doc(self, category: ProductCategory) -> dict:
        return {
            "_id": category.id,
            "name": category.name,
            "parent_id": category.parent_id,
            "description": category.description,
            "is_active": category.is_active,
            "created_at": category.created_at,
            "updated_at": category.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProductCategory:
        return ProductCategory(
            id=doc["_id"],
            name=doc["name"],
            parent_id=doc.get("parent_id"),
            description=doc.get("description", ""),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, category: ProductCategory) -> ProductCategory:
        self._collection.replace_one(
            {"_id": category.id}, self._to_doc(category), upsert=True
        )
        return category

    def find_by_id(self, category_id: str) -> Optional[ProductCategory]:
        doc = self._collection.find_one({"_id": category_id})
        return self._from_doc(doc) if doc else None

    def find_by_name(self, name: str) -> Optional[ProductCategory]:
        doc = self._collection.find_one({"name": name.strip()})
        return self._from_doc(doc) if doc else None

    def find_by_parent_and_name(
        self, parent_id: Optional[str], name: str
    ) -> Optional[ProductCategory]:
        doc = self._collection.find_one(
            {"parent_id": _parent_key(parent_id), "name": name.strip()}
        )
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> List[ProductCategory]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query)]

    def list_children(self, parent_id: Optional[str]) -> List[ProductCategory]:
        return [
            self._from_doc(d)
            for d in self._collection.find({"parent_id": _parent_key(parent_id)})
        ]

    def delete(self, category_id: str) -> None:
        self._collection.delete_one({"_id": category_id})


class MongoProductFieldDefinitionRepository:
    def __init__(self, db: Database):
        self._collection = db.product_field_definitions

    def _to_doc(self, definition: ProductFieldDefinition) -> dict:
        field_type = definition.field_type
        return {
            "_id": definition.id,
            "key": definition.key,
            "label": definition.label,
            "field_type": field_type.value if hasattr(field_type, "value") else field_type,
            "options": list(definition.options),
            "required": definition.required,
            "applies_to_category_ids": list(definition.applies_to_category_ids),
            "sort_order": definition.sort_order,
            "is_active": definition.is_active,
            "created_at": definition.created_at,
            "updated_at": definition.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProductFieldDefinition:
        return ProductFieldDefinition(
            id=doc["_id"],
            key=doc["key"],
            label=doc["label"],
            field_type=ProductFieldType(doc.get("field_type", ProductFieldType.TEXT.value)),
            options=list(doc.get("options") or []),
            required=bool(doc.get("required")),
            applies_to_category_ids=list(doc.get("applies_to_category_ids") or []),
            sort_order=int(doc.get("sort_order") or 0),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, definition: ProductFieldDefinition) -> ProductFieldDefinition:
        self._collection.replace_one(
            {"_id": definition.id}, self._to_doc(definition), upsert=True
        )
        return definition

    def find_by_id(self, definition_id: str) -> Optional[ProductFieldDefinition]:
        doc = self._collection.find_one({"_id": definition_id})
        return self._from_doc(doc) if doc else None

    def find_by_key(self, key: str) -> Optional[ProductFieldDefinition]:
        doc = self._collection.find_one({"key": key.strip().lower()})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = False) -> List[ProductFieldDefinition]:
        query = {"is_active": True} if active_only else {}
        docs = self._collection.find(query).sort("sort_order", 1)
        return [self._from_doc(d) for d in docs]

    def delete(self, definition_id: str) -> None:
        self._collection.delete_one({"_id": definition_id})


class MongoInventoryProductRepository:
    def __init__(self, db: Database):
        self._collection = db.inventory_products

    def _migrate_tax_from_legacy(self, doc: dict) -> tuple[str, list, list]:
        legacy = ItemTaxProfile.from_dict(doc.get("tax_profile"))
        hsn = str(doc.get("hsn_sac") or legacy.hsn_sac or "")
        gst_rates = [
            ProductGstSlab.from_dict(row) for row in doc.get("gst_rates") or []
        ]
        mrp_entries = [
            ProductMrpSlab.from_dict(row) for row in doc.get("mrp_entries") or []
        ]
        if not gst_rates and (legacy.gst_rate or legacy.hsn_sac):
            gst_rates = [
                InventoryProduct.default_gst_slab(
                    gst_rate=legacy.gst_rate,
                    effective_from=date.today(),
                )
            ]
        if not mrp_entries and legacy.mrp:
            mrp_entries = [
                InventoryProduct.default_mrp_entry(
                    mrp=legacy.mrp,
                    effective_from=date.today(),
                )
            ]
        if not gst_rates:
            gst_rates = [InventoryProduct.default_gst_slab()]
        if not mrp_entries:
            mrp_entries = [InventoryProduct.default_mrp_entry()]
        return hsn, gst_rates, mrp_entries

    def _migrate_categories(self, doc: dict) -> tuple[list[str], list[str]]:
        category_ids = list(doc.get("category_ids") or [])
        category_names = list(doc.get("category_names") or [])
        legacy_id = doc.get("category_id")
        if not category_ids and legacy_id:
            category_ids = [legacy_id]
            legacy_name = doc.get("category_name") or ""
            category_names = [legacy_name] if legacy_name else []
        return category_ids, category_names

    def _to_doc(self, product: InventoryProduct) -> dict:
        product.sync_legacy_category_fields()
        product._sync_tax_profile()
        return {
            "_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "category_ids": list(product.category_ids),
            "category_names": list(product.category_names),
            "category_id": product.category_id,
            "category_name": product.category_name,
            "unit_id": product.unit_id,
            "unit": product.unit,
            "selling_rate": product.selling_rate,
            "hsn_sac": product.hsn_sac,
            "gst_rates": [s.to_dict() for s in product.gst_rates],
            "mrp_entries": [e.to_dict() for e in product.mrp_entries],
            "tax_profile": product.tax_profile.to_dict(),
            "specifications": dict(product.specifications or {}),
            "custom_fields": dict(product.custom_fields or {}),
            "weighted_avg_cost": product.weighted_avg_cost,
            "last_purchase_rate": product.last_purchase_rate,
            "opening_qty": product.opening_qty,
            "current_qty": product.current_qty,
            "is_active": product.is_active,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }

    def _from_doc(self, doc: dict) -> InventoryProduct:
        hsn_sac, gst_rates, mrp_entries = self._migrate_tax_from_legacy(doc)
        category_ids, category_names = self._migrate_categories(doc)
        product = InventoryProduct(
            id=doc["_id"],
            sku=doc["sku"],
            name=doc["name"],
            category_ids=category_ids,
            category_names=category_names,
            unit_id=str(doc.get("unit_id") or ""),
            unit=doc.get("unit", "pcs"),
            selling_rate=float(doc.get("selling_rate") or 0),
            hsn_sac=hsn_sac,
            gst_rates=gst_rates,
            mrp_entries=mrp_entries,
            specifications=dict(doc.get("specifications") or {}),
            custom_fields=dict(doc.get("custom_fields") or {}),
            weighted_avg_cost=float(doc.get("weighted_avg_cost") or 0),
            last_purchase_rate=float(doc.get("last_purchase_rate") or 0),
            opening_qty=float(doc.get("opening_qty") or 0),
            current_qty=float(doc.get("current_qty") or 0),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )
        product.sync_legacy_category_fields()
        product._sync_tax_profile()
        return product

    def save(self, product: InventoryProduct) -> InventoryProduct:
        self._collection.replace_one(
            {"_id": product.id}, self._to_doc(product), upsert=True
        )
        return product

    def find_by_id(self, product_id: str) -> Optional[InventoryProduct]:
        doc = self._collection.find_one({"_id": product_id})
        return self._from_doc(doc) if doc else None

    def find_by_sku(self, sku: str) -> Optional[InventoryProduct]:
        doc = self._collection.find_one({"sku": sku.strip()})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> List[InventoryProduct]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query)]

    def list_by_category(self, category_id: str) -> List[InventoryProduct]:
        return [
            self._from_doc(d)
            for d in self._collection.find(
                {
                    "$or": [
                        {"category_ids": category_id},
                        {"category_id": category_id},
                    ]
                }
            )
        ]

    def count_by_category(self, category_id: str) -> int:
        return self._collection.count_documents(
            {
                "$or": [
                    {"category_ids": category_id},
                    {"category_id": category_id},
                ]
            }
        )

    def count_by_unit(self, unit_id: str) -> int:
        return self._collection.count_documents({"unit_id": unit_id})

    def search(self, query: str) -> List[InventoryProduct]:
        if not query.strip():
            return self.list_all()
        regex = {"$regex": query.strip(), "$options": "i"}
        docs = self._collection.find(
            {
                "$or": [
                    {"name": regex},
                    {"sku": regex},
                    {"category_name": regex},
                    {"category_names": regex},
                ]
            }
        )
        return [self._from_doc(d) for d in docs]


class MongoStockMovementRepository:
    def __init__(self, db: Database):
        self._collection = db.stock_movements

    def _to_doc(self, movement: StockMovement) -> dict:
        md = movement.movement_date
        if isinstance(md, datetime):
            md = md.date()
        return {
            "_id": movement.id,
            "product_id": movement.product_id,
            "movement_type": _enum_value(movement.movement_type),
            "qty": movement.qty,
            "movement_date": md.isoformat() if isinstance(md, date) else md,
            "reference_type": _enum_value(movement.reference_type),
            "reference_id": movement.reference_id,
            "notes": movement.notes,
            "created_at": movement.created_at,
        }

    def _from_doc(self, doc: dict) -> StockMovement:
        md = doc.get("movement_date")
        if isinstance(md, str):
            md = date.fromisoformat(md)
        return StockMovement(
            id=doc["_id"],
            product_id=doc["product_id"],
            movement_type=StockMovementType(doc["movement_type"]),
            qty=float(doc.get("qty") or 0),
            movement_date=md,
            reference_type=StockReferenceType(doc.get("reference_type", "Manual")),
            reference_id=doc.get("reference_id"),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, movement: StockMovement) -> StockMovement:
        self._collection.replace_one(
            {"_id": movement.id}, self._to_doc(movement), upsert=True
        )
        return movement

    def list_by_product(self, product_id: str) -> List[StockMovement]:
        return [
            self._from_doc(d)
            for d in self._collection.find({"product_id": product_id})
        ]

    def list_all(self) -> List[StockMovement]:
        return [self._from_doc(d) for d in self._collection.find()]

    def list_by_reference(self, reference_id: str) -> List[StockMovement]:
        if not reference_id:
            return []
        return [
            self._from_doc(d)
            for d in self._collection.find({"reference_id": reference_id})
        ]

    def delete(self, movement_id: str) -> None:
        self._collection.delete_one({"_id": movement_id})
