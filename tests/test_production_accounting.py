from datetime import date
from types import SimpleNamespace

import pytest

from vaybooks.bms.application.production.service import ProductionAppService
from vaybooks.bms.domain.production.entities import (
    BatchCost,
    ProductionSettings,
    Recipe,
    RecipeInput,
    RecipeOutput,
)
from vaybooks.bms.domain.shared.enums import (
    AccountType,
    ProductionBatchStatus,
    ProductionCostAllocationMethod,
    ProductionOutputRole,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class MemoryRepo:
    def __init__(self):
        self.values = {}

    def save(self, value):
        self.values[value.id] = value
        return value

    def find_by_id(self, value_id):
        return self.values.get(value_id)

    def list_all(self, active_only=True):
        values = list(self.values.values())
        return [value for value in values if not active_only or getattr(value, "is_active", True)]

    def delete(self, value_id):
        self.values.pop(value_id, None)

    def find_by_code(self, code):
        return next((item for item in self.values.values() if item.code == code), None)


class BatchRepo(MemoryRepo):
    def find_by_number(self, number):
        return next(
            (item for item in self.values.values() if item.batch_number == number),
            None,
        )

    def list_all(self, status=None):
        values = list(self.values.values())
        return [item for item in values if status is None or item.status == status]


class SettingsRepo:
    def __init__(self):
        self.value = ProductionSettings(
            wip_account_id="wip",
            raw_material_account_id="raw",
            finished_goods_account_id="fg",
            expense_clearing_account_id="clearing",
        )

    def get(self):
        return self.value

    def save(self, value):
        self.value = value
        return value


class InventoryStub:
    def __init__(self):
        self.products = {
            "rm": SimpleNamespace(
                id="rm", name="Raw", unit="kg", weighted_avg_cost=10, selling_rate=0
            ),
            "fg": SimpleNamespace(
                id="fg", name="Finished", unit="kg", weighted_avg_cost=0, selling_rate=30
            ),
            "by": SimpleNamespace(
                id="by", name="By-product", unit="kg", weighted_avg_cost=0, selling_rate=5
            ),
        }
        self.stock = {("rm", "loc"): 100.0, ("fg", "loc"): 0.0, ("by", "loc"): 0.0}
        self.movement_counter = 0

    def get_product(self, product_id):
        return self.products.get(product_id)

    def get_stock_balance(self, product_id, location_id):
        return self.stock.get((product_id, location_id), 0)

    def _apply(self, batch_id, lines, direction):
        result = []
        for line in lines:
            key = (line["product_id"], line["location_id"])
            self.stock[key] = self.stock.get(key, 0) + direction * line["qty"]
            self.movement_counter += 1
            result.append(SimpleNamespace(id=f"m{self.movement_counter}"))
        return result

    def apply_production_issue(self, batch_id, lines, movement_date):
        return self._apply(batch_id, lines, -1)

    def apply_production_receive(self, batch_id, lines, movement_date):
        return self._apply(batch_id, lines, 1)

    def apply_landed_cost(self, lines):
        for line in lines:
            self.products[line["product_id"]].weighted_avg_cost = line["unit_cost"]

    def reverse_movements_by_reference(self, batch_id):
        pass


class AccountingStub:
    def __init__(self):
        self.accounts = {
            key: SimpleNamespace(id=key, account_name=key, account_type=AccountType.ASSET)
            for key in ("wip", "raw", "fg", "clearing")
        }
        self.vouchers = []

    def get_account(self, account_id):
        return self.accounts.get(account_id)

    def create_journal_entry(self, description, lines, voucher_date, **kwargs):
        assert sum(line.get("debit_amount", 0) for line in lines) == pytest.approx(
            sum(line.get("credit_amount", 0) for line in lines)
        )
        voucher = SimpleNamespace(id=f"v{len(self.vouchers) + 1}", lines=lines)
        self.vouchers.append(voucher)
        return voucher

    def list_vouchers(self):
        return []


@pytest.fixture
def production():
    recipes = MemoryRepo()
    batches = BatchRepo()
    inventory = InventoryStub()
    accounting = AccountingStub()
    service = ProductionAppService(
        recipes, batches, SettingsRepo(), inventory, accounting
    )
    recipe = Recipe(
        name="Generic process",
        code="PROC-1",
        base_quantity=100,
        allocation_method=ProductionCostAllocationMethod.NRV,
        inputs=[RecipeInput(product_id="rm", product_name="Raw", qty=100)],
        outputs=[
            RecipeOutput(
                product_id="fg",
                product_name="Finished",
                expected_qty=60,
                role=ProductionOutputRole.MAIN,
                nrv_rate=30,
            ),
            RecipeOutput(
                product_id="by",
                product_name="By-product",
                expected_qty=20,
                role=ProductionOutputRole.BY_PRODUCT,
                nrv_rate=5,
            ),
        ],
    )
    service.save_recipe(recipe)
    return service, inventory, accounting, recipe


def test_nrv_cost_allocation_and_margin(production):
    service, _inventory, _accounting, recipe = production
    batch = service.create_batch(
        batch_number="PB-001",
        recipe_id=recipe.id,
        batch_date=date.today(),
        location_id="loc",
        planned_quantity=50,
    )
    service.add_cost(batch.id, BatchCost(cost_type="Power", amount=100))
    batch = service.get_batch(batch.id)

    assert batch.material_cost == 500
    assert batch.expense_cost == 100
    assert batch.total_cost == 600
    assert sum(line.allocated_cost for line in batch.outputs) == pytest.approx(600)
    assert batch.expected_sales_value == 950
    assert batch.batch_margin == 350


def test_post_batch_updates_stock_wac_and_balanced_journals(production):
    service, inventory, accounting, recipe = production
    batch = service.create_batch(
        batch_number="PB-002",
        recipe_id=recipe.id,
        batch_date=date.today(),
        location_id="loc",
        planned_quantity=50,
    )
    service.add_cost(batch.id, BatchCost(cost_type="Labour", amount=50))
    posted = service.post_batch(batch.id, posted_by="tester")

    assert posted.status == ProductionBatchStatus.POSTED
    assert inventory.stock[("rm", "loc")] == 50
    assert inventory.stock[("fg", "loc")] == 30
    assert inventory.stock[("by", "loc")] == 10
    assert len(posted.posting.movement_ids) == 3
    assert len(accounting.vouchers) == 3
    assert inventory.products["fg"].weighted_avg_cost > 0


def test_percentage_allocation_requires_one_hundred_percent(production):
    service, _inventory, _accounting, _recipe = production
    invalid = Recipe(
        name="Bad split",
        allocation_method=ProductionCostAllocationMethod.PERCENTAGE,
        inputs=[RecipeInput(product_id="rm", qty=1)],
        outputs=[
            RecipeOutput(
                product_id="fg",
                expected_qty=1,
                role=ProductionOutputRole.MAIN,
                allocation_pct=90,
            )
        ],
    )
    with pytest.raises(ValidationError, match="total 100"):
        service.save_recipe(invalid)
