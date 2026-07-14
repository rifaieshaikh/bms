"""Domain service for product selling/MRP/GST rate history."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.inventory.rate_history import (
    ProductRatePeriod,
    apply_immediate_rate_change,
    close_open_period_before,
    create_initial_period,
    period_status,
    resolve_active_period,
    validate_gst_rate_value,
    validate_no_overlaps,
    validate_period_dates,
    validate_product_pricing,
    validate_rate_value,
)
from vaybooks.bms.domain.inventory.rate_history_repository import (
    ProductRateHistoryRepository,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProductRateHistoryService:
    def __init__(
        self,
        selling_repo: ProductRateHistoryRepository,
        mrp_repo: ProductRateHistoryRepository,
        gst_repo: ProductRateHistoryRepository,
    ):
        self._selling_repo = selling_repo
        self._mrp_repo = mrp_repo
        self._gst_repo = gst_repo

    def list_selling_rates(self, product_id: str) -> List[ProductRatePeriod]:
        return self._selling_repo.list_for_product(product_id)

    def list_mrp(self, product_id: str) -> List[ProductRatePeriod]:
        return self._mrp_repo.list_for_product(product_id)

    def list_gst_rates(self, product_id: str) -> List[ProductRatePeriod]:
        return self._gst_repo.list_for_product(product_id)

    def active_selling_rate(
        self, product_id: str, as_of: Optional[date] = None
    ) -> Optional[ProductRatePeriod]:
        return resolve_active_period(self.list_selling_rates(product_id), as_of)

    def active_mrp(
        self, product_id: str, as_of: Optional[date] = None
    ) -> Optional[ProductRatePeriod]:
        return resolve_active_period(self.list_mrp(product_id), as_of)

    def active_gst_rate(
        self, product_id: str, as_of: Optional[date] = None
    ) -> Optional[ProductRatePeriod]:
        return resolve_active_period(self.list_gst_rates(product_id), as_of)

    def hydrate_active_values(self, product_id: str, product) -> None:
        selling = self.active_selling_rate(product_id)
        mrp = self.active_mrp(product_id)
        gst = self.active_gst_rate(product_id)
        product.apply_active_rates(
            selling_rate=selling.value if selling else 0.0,
            mrp=mrp.value if mrp else 0.0,
            gst_rate=gst.value if gst else 0.0,
        )

    def create_initial_rates(
        self,
        product_id: str,
        *,
        selling_rate: float,
        mrp: float,
        gst_rate: float,
        start_date: Optional[date] = None,
    ) -> None:
        validate_product_pricing(selling_rate, mrp)
        validate_gst_rate_value(gst_rate)
        start = start_date or date.today()
        for repo, value in (
            (self._selling_repo, selling_rate),
            (self._mrp_repo, mrp),
            (self._gst_repo, gst_rate),
        ):
            period = create_initial_period(product_id, value, start_date=start)
            repo.save(period)

    def apply_form_changes(
        self,
        product_id: str,
        *,
        selling_rate: float,
        mrp: float,
        gst_rate: float,
        edit_date: Optional[date] = None,
        is_new: bool = False,
        gst_required: bool = False,
    ) -> None:
        edit_date = edit_date or date.today()
        validate_product_pricing(selling_rate, mrp)
        validate_gst_rate_value(gst_rate, required=gst_required)

        if is_new:
            self.create_initial_rates(
                product_id,
                selling_rate=selling_rate,
                mrp=mrp,
                gst_rate=gst_rate,
                start_date=edit_date,
            )
            return

        self._apply_change(
            self._selling_repo,
            self.list_selling_rates(product_id),
            product_id,
            selling_rate,
            edit_date,
        )
        self._apply_change(
            self._mrp_repo,
            self.list_mrp(product_id),
            product_id,
            mrp,
            edit_date,
        )
        self._apply_change(
            self._gst_repo,
            self.list_gst_rates(product_id),
            product_id,
            gst_rate,
            edit_date,
        )

    def _apply_change(
        self,
        repo: ProductRateHistoryRepository,
        periods: List[ProductRatePeriod],
        product_id: str,
        new_value: float,
        edit_date: date,
    ) -> None:
        apply_immediate_rate_change(
            periods,
            product_id,
            new_value,
            edit_date=edit_date,
            repo_save=repo.save,
        )

    def add_scheduled_period(
        self,
        rate_type: str,
        product_id: str,
        *,
        value: float,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> ProductRatePeriod:
        validate_period_dates(start_date, end_date)
        if rate_type == "selling":
            validate_rate_value(value, field_label="Selling price")
            repo = self._selling_repo
            periods = self.list_selling_rates(product_id)
        elif rate_type == "mrp":
            validate_rate_value(value, field_label="MRP")
            repo = self._mrp_repo
            periods = self.list_mrp(product_id)
        elif rate_type == "gst":
            validate_gst_rate_value(value)
            repo = self._gst_repo
            periods = self.list_gst_rates(product_id)
        else:
            raise ValidationError("Unknown rate type")

        period = ProductRatePeriod(
            product_id=product_id,
            value=round(float(value), 2),
            start_date=start_date,
            end_date=end_date,
        )
        validate_no_overlaps(periods + [period])
        close_open_period_before(periods, start_date, repo_save=repo.save)
        return repo.save(period)

    def status_for(self, period: ProductRatePeriod, as_of: Optional[date] = None):
        return period_status(period, as_of or date.today())
