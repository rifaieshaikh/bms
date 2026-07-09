from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    ProductCategory,
    StockMovement,
)
from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


class MongoProductCategoryRepository:
    def __init__(self, db: Database):
        self._collection = db.product_categories

    def _to_doc(self, category: ProductCategory) -> dict:
        return {
            "_id": category.id,
            "name": category.name,
            "description": category.description,
            "is_active": category.is_active,
            "created_at": category.created_at,
            "updated_at": category.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProductCategory:
        return ProductCategory(
            id=doc["_id"],
            name=doc["name"],
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

    def list_all(self, active_only: bool = True) -> List[ProductCategory]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query)]

    def delete(self, category_id: str) -> None:
        self._collection.delete_one({"_id": category_id})


class MongoInventoryProductRepository:
    def __init__(self, db: Database):
        self._collection = db.inventory_products

    def _to_doc(self, product: InventoryProduct) -> dict:
        return {
            "_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "category_id": product.category_id,
            "category_name": product.category_name,
            "unit": product.unit,
            "selling_rate": product.selling_rate,
            "opening_qty": product.opening_qty,
            "current_qty": product.current_qty,
            "is_active": product.is_active,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }

    def _from_doc(self, doc: dict) -> InventoryProduct:
        return InventoryProduct(
            id=doc["_id"],
            sku=doc["sku"],
            name=doc["name"],
            category_id=doc["category_id"],
            category_name=doc.get("category_name", ""),
            unit=doc.get("unit", "pcs"),
            selling_rate=float(doc.get("selling_rate") or 0),
            opening_qty=float(doc.get("opening_qty") or 0),
            current_qty=float(doc.get("current_qty") or 0),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

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
            for d in self._collection.find({"category_id": category_id})
        ]

    def count_by_category(self, category_id: str) -> int:
        return self._collection.count_documents({"category_id": category_id})

    def search(self, query: str) -> List[InventoryProduct]:
        if not query.strip():
            return self.list_all()
        regex = {"$regex": query.strip(), "$options": "i"}
        docs = self._collection.find(
            {"$or": [{"name": regex}, {"sku": regex}, {"category_name": regex}]}
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
