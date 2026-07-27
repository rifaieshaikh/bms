from pymongo.database import Database
from pymongo import ReturnDocument


class MongoCounterRepository:
    def __init__(self, db: Database):
        self._collection = db.counters

    def next(self, counter_name: str) -> str:
        result = self._collection.find_one_and_update(
            {"_id": counter_name},
            {"$inc": {"current_value": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if not result:
            raise ValueError(f"Counter {counter_name} not found")
        prefix = result.get("prefix", "")
        value = result["current_value"]
        return f"{prefix}-{value:04d}"

    def peek(self, counter_name: str) -> str:
        result = self._collection.find_one({"_id": counter_name})
        if not result:
            raise ValueError(f"Counter {counter_name} not found")
        prefix = result.get("prefix", "")
        value = int(result.get("current_value", 0)) + 1
        return f"{prefix}-{value:04d}"

    def ensure_and_next(self, counter_name: str) -> int:
        """Upsert a counter and return the next integer sequence (no prefix)."""
        result = self._collection.find_one_and_update(
            {"_id": counter_name},
            {"$inc": {"current_value": 1}, "$setOnInsert": {"prefix": ""}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(result["current_value"])

    def peek_next_value(self, counter_name: str) -> int:
        """Return the next sequence value without incrementing."""
        result = self._collection.find_one({"_id": counter_name})
        if not result:
            return 1
        return int(result.get("current_value", 0)) + 1
