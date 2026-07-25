from datetime import date, datetime
from typing import Any, List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    Location,
    ProductCategory,
    ProductUnit,
    StockBalance,
    StockMovement,
    StockTransfer,
    StockTransferLine,
    Warehouse,
)
from vaybooks.bms.domain.inventory.field_definitions import (
    ProductFieldDefinition,
    ProductFieldType,
)
from vaybooks.bms.domain.shared.enums import (
    LocationType,
    StockMovementType,
    StockReferenceType,
    StockTransferStatus,
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

    def search(
        self, query: str, *, active_only: bool = True, limit: int = 25
    ) -> List[ProductUnit]:
        limit = max(1, min(int(limit or 25), 50))
        filters: dict = {}
        if active_only:
            filters["is_active"] = True
        text = (query or "").strip()
        if text:
            regex = {"$regex": text, "$options": "i"}
            filters["$or"] = [{"code": regex}, {"label": regex}]
        cursor = self._collection.find(filters).sort("code", 1).limit(limit)
        return [self._from_doc(d) for d in cursor]

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

    def find_by_ids(self, category_ids: List[str]) -> List[ProductCategory]:
        ids = [cid for cid in category_ids if cid]
        if not ids:
            return []
        docs = self._collection.find({"_id": {"$in": ids}})
        by_id = {d["_id"]: self._from_doc(d) for d in docs}
        return [by_id[cid] for cid in ids if cid in by_id]

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

    def search(
        self, query: str, *, active_only: bool = True, limit: int = 25
    ) -> List[ProductCategory]:
        limit = max(1, min(int(limit or 25), 50))
        filters: dict = {}
        if active_only:
            filters["is_active"] = True
        text = (query or "").strip()
        if text:
            filters["name"] = {"$regex": text, "$options": "i"}
        cursor = self._collection.find(filters).sort("name", 1).limit(limit)
        return [self._from_doc(d) for d in cursor]

    def list_children(self, parent_id: Optional[str]) -> List[ProductCategory]:
        return [
            self._from_doc(d)
            for d in self._collection.find({"parent_id": _parent_key(parent_id)})
        ]

    def delete(self, category_id: str) -> None:
        self._collection.delete_one({"_id": category_id})


class MongoLocationRepository:
    def __init__(self, db: Database):
        self._collection = db.warehouses

    def _to_doc(self, location: Location) -> dict:
        loc_type = location.location_type
        return {
            "_id": location.id,
            "code": location.code,
            "name": location.name,
            "location_type": _enum_value(loc_type),
            "address": location.address,
            "is_active": location.is_active,
            "created_at": location.created_at,
            "updated_at": location.updated_at,
        }

    def _from_doc(self, doc: dict) -> Location:
        raw_type = doc.get("location_type") or LocationType.WAREHOUSE.value
        try:
            location_type = LocationType(raw_type)
        except ValueError:
            location_type = LocationType.WAREHOUSE
        return Location(
            id=doc["_id"],
            code=doc["code"],
            name=doc["name"],
            location_type=location_type,
            address=doc.get("address", ""),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, location: Location) -> Location:
        self._collection.replace_one(
            {"_id": location.id}, self._to_doc(location), upsert=True
        )
        return location

    def find_by_id(self, location_id: str) -> Optional[Location]:
        doc = self._collection.find_one({"_id": location_id})
        return self._from_doc(doc) if doc else None

    def find_by_code(self, code: str) -> Optional[Location]:
        doc = self._collection.find_one({"code": (code or "").strip().upper()})
        return self._from_doc(doc) if doc else None

    def list_all(
        self,
        active_only: bool = True,
        location_type: Optional[LocationType] = None,
    ) -> List[Location]:
        query: dict = {}
        if active_only:
            query["is_active"] = True
        if location_type is not None:
            query["location_type"] = _enum_value(location_type)
        return [
            self._from_doc(d)
            for d in self._collection.find(query).sort("code", 1)
        ]

    def search(
        self,
        query: str,
        *,
        active_only: bool = True,
        limit: int = 25,
        location_type: Optional[LocationType] = None,
    ) -> List[Location]:
        limit = max(1, min(int(limit or 25), 50))
        filters: dict = {}
        if active_only:
            filters["is_active"] = True
        if location_type is not None:
            filters["location_type"] = _enum_value(location_type)
        text = (query or "").strip()
        if text:
            regex = {"$regex": text, "$options": "i"}
            filters["$or"] = [{"code": regex}, {"name": regex}, {"address": regex}]
        cursor = self._collection.find(filters).sort("code", 1).limit(limit)
        return [self._from_doc(d) for d in cursor]

    def delete(self, location_id: str) -> None:
        self._collection.delete_one({"_id": location_id})


# Back-compat alias
MongoWarehouseRepository = MongoLocationRepository


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
            "hsn_sac": product.hsn_sac,
            "specifications": dict(product.specifications or {}),
            "custom_fields": dict(product.custom_fields or {}),
            "weighted_avg_cost": product.weighted_avg_cost,
            "last_purchase_rate": product.last_purchase_rate,
            "opening_qty": product.opening_qty,
            "current_qty": product.current_qty,
            "track_batch": product.track_batch,
            "track_serial": product.track_serial,
            "is_active": product.is_active,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }

    def _from_doc(self, doc: dict) -> InventoryProduct:
        category_ids, category_names = self._migrate_categories(doc)
        product = InventoryProduct(
            id=doc["_id"],
            sku=doc["sku"],
            name=doc["name"],
            category_ids=category_ids,
            category_names=category_names,
            unit_id=str(doc.get("unit_id") or ""),
            unit=doc.get("unit", "pcs"),
            hsn_sac=str(doc.get("hsn_sac") or ""),
            specifications=dict(doc.get("specifications") or {}),
            custom_fields=dict(doc.get("custom_fields") or {}),
            weighted_avg_cost=float(doc.get("weighted_avg_cost") or 0),
            last_purchase_rate=float(doc.get("last_purchase_rate") or 0),
            opening_qty=float(doc.get("opening_qty") or 0),
            current_qty=float(doc.get("current_qty") or 0),
            track_batch=bool(doc.get("track_batch")),
            track_serial=bool(doc.get("track_serial")),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )
        product.sync_legacy_category_fields()
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
        location_id = movement.location_id
        return {
            "_id": movement.id,
            "product_id": movement.product_id,
            "movement_type": _enum_value(movement.movement_type),
            "qty": movement.qty,
            "movement_date": md.isoformat() if isinstance(md, date) else md,
            "reference_type": _enum_value(movement.reference_type),
            "reference_id": movement.reference_id,
            "location_id": location_id,
            "warehouse_id": location_id,
            "notes": movement.notes,
            "created_at": movement.created_at,
        }

    def _from_doc(self, doc: dict) -> StockMovement:
        md = doc.get("movement_date")
        if isinstance(md, str):
            md = date.fromisoformat(md)
        location_id = doc.get("location_id") or doc.get("warehouse_id")
        return StockMovement(
            id=doc["_id"],
            product_id=doc["product_id"],
            movement_type=StockMovementType(doc["movement_type"]),
            qty=float(doc.get("qty") or 0),
            movement_date=md,
            reference_type=StockReferenceType(doc.get("reference_type", "Manual")),
            reference_id=doc.get("reference_id"),
            location_id=location_id,
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

    def list_by_location(self, location_id: str) -> List[StockMovement]:
        if not location_id:
            return []
        return [
            self._from_doc(d)
            for d in self._collection.find(
                {
                    "$or": [
                        {"location_id": location_id},
                        {"warehouse_id": location_id},
                    ]
                }
            )
        ]

    def delete(self, movement_id: str) -> None:
        self._collection.delete_one({"_id": movement_id})


class MongoStockBalanceRepository:
    def __init__(self, db: Database):
        self._collection = db.stock_balances

    def _to_doc(self, balance: StockBalance) -> dict:
        return {
            "_id": balance.id,
            "product_id": balance.product_id,
            "location_id": balance.location_id,
            "qty": balance.qty,
            "updated_at": balance.updated_at,
        }

    def _from_doc(self, doc: dict) -> StockBalance:
        return StockBalance(
            id=doc["_id"],
            product_id=doc["product_id"],
            location_id=doc["location_id"],
            qty=float(doc.get("qty") or 0),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, balance: StockBalance) -> StockBalance:
        self._collection.replace_one(
            {"_id": balance.id}, self._to_doc(balance), upsert=True
        )
        return balance

    def get(self, product_id: str, location_id: str) -> Optional[StockBalance]:
        doc = self._collection.find_one(
            {"product_id": product_id, "location_id": location_id}
        )
        return self._from_doc(doc) if doc else None

    def list_by_product(self, product_id: str) -> List[StockBalance]:
        return [
            self._from_doc(d)
            for d in self._collection.find({"product_id": product_id})
        ]

    def list_by_location(self, location_id: str) -> List[StockBalance]:
        return [
            self._from_doc(d)
            for d in self._collection.find({"location_id": location_id})
        ]

    def list_all(self) -> List[StockBalance]:
        return [self._from_doc(d) for d in self._collection.find()]

    def delete(self, balance_id: str) -> None:
        self._collection.delete_one({"_id": balance_id})


class MongoStockTransferRepository:
    def __init__(self, db: Database):
        self._collection = db.stock_transfers

    def _line_to_doc(self, line: StockTransferLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty": line.qty,
        }

    def _line_from_doc(self, doc: dict) -> StockTransferLine:
        return StockTransferLine(
            id=doc.get("id", ""),
            product_id=doc.get("product_id", ""),
            product_name=doc.get("product_name", ""),
            qty=float(doc.get("qty") or 0),
        )

    def _to_doc(self, transfer: StockTransfer) -> dict:
        td = transfer.transfer_date
        return {
            "_id": transfer.id,
            "transfer_number": transfer.transfer_number,
            "from_location_id": transfer.from_location_id,
            "from_location_name": transfer.from_location_name,
            "to_location_id": transfer.to_location_id,
            "to_location_name": transfer.to_location_name,
            "transfer_date": td.isoformat() if isinstance(td, date) else td,
            "status": _enum_value(transfer.status),
            "lines": [self._line_to_doc(line) for line in transfer.lines],
            "notes": transfer.notes,
            "created_at": transfer.created_at,
            "updated_at": transfer.updated_at,
        }

    def _from_doc(self, doc: dict) -> StockTransfer:
        td = doc.get("transfer_date")
        if isinstance(td, str):
            td = date.fromisoformat(td)
        return StockTransfer(
            id=doc["_id"],
            transfer_number=doc["transfer_number"],
            from_location_id=doc.get("from_location_id", ""),
            from_location_name=doc.get("from_location_name", ""),
            to_location_id=doc.get("to_location_id", ""),
            to_location_name=doc.get("to_location_name", ""),
            transfer_date=td,
            status=StockTransferStatus(
                doc.get("status", StockTransferStatus.DRAFT.value)
            ),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, transfer: StockTransfer) -> StockTransfer:
        self._collection.replace_one(
            {"_id": transfer.id}, self._to_doc(transfer), upsert=True
        )
        return transfer

    def find_by_id(self, transfer_id: str) -> Optional[StockTransfer]:
        doc = self._collection.find_one({"_id": transfer_id})
        return self._from_doc(doc) if doc else None

    def find_by_number(self, transfer_number: str) -> Optional[StockTransfer]:
        doc = self._collection.find_one({"transfer_number": transfer_number})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[StockTransfer]:
        return [self._from_doc(d) for d in self._collection.find()]

    def delete(self, transfer_id: str) -> None:
        self._collection.delete_one({"_id": transfer_id})
