"""Repository protocol for product rate history collections."""

from __future__ import annotations

from typing import List, Optional, Protocol

from vaybooks.bms.domain.inventory.rate_history import ProductRatePeriod


class ProductRateHistoryRepository(Protocol):
    def save(self, period: ProductRatePeriod) -> ProductRatePeriod: ...

    def find_by_id(self, period_id: str) -> Optional[ProductRatePeriod]: ...

    def list_for_product(self, product_id: str) -> List[ProductRatePeriod]: ...

    def delete(self, period_id: str) -> None: ...
