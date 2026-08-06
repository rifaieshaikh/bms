from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.sales.discount_entities import (
    DEFAULT_APPLY_TO,
    DiscountRule,
    SCOPE_SEASONAL,
)


def _parse_date(value) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


class MongoDiscountRuleRepository:
    def __init__(self, db: Database):
        self._collection = db.discount_rules

    def _to_doc(self, rule: DiscountRule) -> dict:
        return {
            "_id": rule.id,
            "name": rule.name,
            "scope": rule.scope,
            "discount_type": rule.discount_type,
            "value": float(rule.value or 0),
            "priority": int(rule.priority),
            "is_active": bool(rule.is_active),
            "product_ids": list(rule.product_ids or []),
            "category_ids": list(rule.category_ids or []),
            "customer_ids": list(rule.customer_ids or []),
            "segment_ids": list(rule.segment_ids or []),
            "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
            "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
            "apply_to": list(rule.apply_to or DEFAULT_APPLY_TO),
            "max_discount_amount": (
                float(rule.max_discount_amount)
                if rule.max_discount_amount is not None
                else None
            ),
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
        }

    def _from_doc(self, doc: dict) -> DiscountRule:
        return DiscountRule(
            id=doc["_id"],
            name=doc.get("name", ""),
            scope=doc.get("scope", "global"),
            discount_type=doc.get("discount_type", "percent"),
            value=float(doc.get("value") or 0),
            priority=int(doc.get("priority") if doc.get("priority") is not None else 100),
            is_active=bool(doc.get("is_active", True)),
            product_ids=list(doc.get("product_ids") or []),
            category_ids=list(doc.get("category_ids") or []),
            customer_ids=list(doc.get("customer_ids") or []),
            segment_ids=list(doc.get("segment_ids") or []),
            valid_from=_parse_date(doc.get("valid_from")),
            valid_to=_parse_date(doc.get("valid_to")),
            apply_to=list(doc.get("apply_to") or DEFAULT_APPLY_TO),
            max_discount_amount=(
                float(doc["max_discount_amount"])
                if doc.get("max_discount_amount") is not None
                else None
            ),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, rule: DiscountRule) -> DiscountRule:
        doc = self._to_doc(rule)
        self._collection.replace_one({"_id": rule.id}, doc, upsert=True)
        return rule

    def find_by_id(self, rule_id: str) -> Optional[DiscountRule]:
        if not rule_id:
            return None
        doc = self._collection.find_one({"_id": rule_id})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = False) -> List[DiscountRule]:
        query = {"is_active": True} if active_only else {}
        docs = self._collection.find(query).sort([("priority", 1), ("name", 1)])
        return [self._from_doc(d) for d in docs]

    def list_active_seasonal(
        self, exclude_id: Optional[str] = None
    ) -> List[DiscountRule]:
        query: dict = {"scope": SCOPE_SEASONAL, "is_active": True}
        if exclude_id:
            query["_id"] = {"$ne": exclude_id}
        docs = self._collection.find(query).sort([("priority", 1), ("name", 1)])
        return [self._from_doc(d) for d in docs]

    def delete(self, rule_id: str) -> None:
        self._collection.delete_one({"_id": rule_id})
