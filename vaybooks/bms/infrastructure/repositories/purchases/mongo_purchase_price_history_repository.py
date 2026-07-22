from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.purchases.line_items import PurchasePriceHistory
from vaybooks.bms.domain.shared.enums import CatalogItemType


class MongoPurchasePriceHistoryRepository:
    def __init__(self, db: Database):
        self._collection = db.purchase_price_history

    def _to_doc(self, row: PurchasePriceHistory) -> dict:
        pd = row.purchase_date
        if isinstance(pd, datetime):
            pd = pd.date()
        return {
            "_id": row.id,
            "item_type": row.item_type.value,
            "item_id": row.item_id,
            "vendor_id": row.vendor_id,
            "purchase_date": pd.isoformat() if isinstance(pd, date) else pd,
            "qty": row.qty,
            "rate": row.rate,
            "taxable_amount": row.taxable_amount,
            "line_total": row.line_total,
            "cgst_amount": row.cgst_amount,
            "sgst_amount": row.sgst_amount,
            "igst_amount": row.igst_amount,
            "utgst_amount": row.utgst_amount,
            "vendor_bill_number": row.vendor_bill_number,
            "voucher_id": row.voucher_id,
            "created_at": row.created_at,
        }

    def _item_type(self, value) -> CatalogItemType:
        try:
            return CatalogItemType(value)
        except ValueError:
            return CatalogItemType.PRODUCT

    def _from_doc(self, doc: dict) -> PurchasePriceHistory:
        pd = doc.get("purchase_date")
        if isinstance(pd, str):
            pd = date.fromisoformat(pd)
        return PurchasePriceHistory(
            id=doc["_id"],
            item_type=self._item_type(doc.get("item_type")),
            item_id=doc["item_id"],
            vendor_id=doc["vendor_id"],
            purchase_date=pd,
            qty=float(doc.get("qty") or 0),
            rate=float(doc.get("rate") or 0),
            taxable_amount=float(doc.get("taxable_amount") or 0),
            line_total=float(doc.get("line_total") or 0),
            cgst_amount=float(doc.get("cgst_amount") or 0),
            sgst_amount=float(doc.get("sgst_amount") or 0),
            igst_amount=float(doc.get("igst_amount") or 0),
            utgst_amount=float(doc.get("utgst_amount") or 0),
            vendor_bill_number=doc.get("vendor_bill_number", ""),
            voucher_id=doc.get("voucher_id"),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, row: PurchasePriceHistory) -> PurchasePriceHistory:
        self._collection.replace_one(
            {"_id": row.id}, self._to_doc(row), upsert=True
        )
        return row

    def save_many(self, rows: List[PurchasePriceHistory]) -> None:
        for row in rows:
            self.save(row)

    def list_for_item(
        self,
        item_type: CatalogItemType,
        item_id: str,
        vendor_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[PurchasePriceHistory]:
        query = {"item_type": item_type.value, "item_id": item_id}
        if vendor_id:
            query["vendor_id"] = vendor_id
        docs = (
            self._collection.find(query)
            .sort([("purchase_date", -1), ("created_at", -1)])
            .limit(limit)
        )
        return [self._from_doc(d) for d in docs]

    def latest_rate(
        self,
        item_type: CatalogItemType,
        item_id: str,
        vendor_id: str,
    ) -> Optional[float]:
        rows = self.list_for_item(item_type, item_id, vendor_id=vendor_id, limit=1)
        return rows[0].rate if rows else None
