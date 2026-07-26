"""Production E2E: seeded recipe/batch → UI post → margin report."""

from datetime import date, datetime

from playwright.sync_api import Page, expect

from e2e.helpers.seed import _db
from e2e.helpers.unique import unique_suffix
from vaybooks.bms.domain.production.entities import (
    ProductionSettings,
    Recipe,
    RecipeInput,
    RecipeOutput,
)
from vaybooks.bms.domain.production.services import ProductionDomainService
from vaybooks.bms.domain.identity.passwords import hash_password
from vaybooks.bms.domain.shared.enums import ProductionOutputRole
from vaybooks.bms.infrastructure.repositories.production import (
    MongoProductionBatchRepository,
    MongoProductionSettingsRepository,
    MongoRecipeRepository,
)
from vaybooks.bms.ui.auth.persist import COOKIE_NAME, issue_token


def _seed_production_batch():
    db = _db()
    suffix = unique_suffix()
    rm_id = f"e2e-production-rm-{suffix}"
    fg_id = f"e2e-production-fg-{suffix}"
    location_id = f"e2e-production-location-{suffix}"
    now = datetime.utcnow()
    db.users.replace_one(
        {"_id": "e2e-production-admin"},
        {
            "_id": "e2e-production-admin",
            "username": "e2e-production-admin",
            "display_name": "E2E Production Admin",
            "password_hash": hash_password("e2e-production-admin"),
            "role_ids": ["role_owner"],
            "active": True,
            "created_at": now,
            "updated_at": now,
        },
        upsert=True,
    )
    for product_id, sku, name, qty, wac, selling in [
        (rm_id, f"RM-{suffix}", "E2E Production Raw", 100.0, 10.0, 0.0),
        (fg_id, f"FG-{suffix}", "E2E Production Output", 0.0, 0.0, 25.0),
    ]:
        db.inventory_products.replace_one(
            {"_id": product_id},
            {
                "_id": product_id,
                "sku": sku,
                "name": name,
                "unit": "kg",
                "current_qty": qty,
                "weighted_avg_cost": wac,
                "active_selling_rate": selling,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            upsert=True,
        )
    db.warehouses.replace_one(
        {"_id": location_id},
        {
            "_id": location_id,
            "name": f"E2E Production {suffix}",
            "code": f"PR{suffix[-6:]}",
            "location_type": "Warehouse",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        upsert=True,
    )
    db.stock_balances.replace_one(
        {"product_id": rm_id, "location_id": location_id},
        {
            "_id": f"bal-{suffix}",
            "product_id": rm_id,
            "location_id": location_id,
            "qty": 100.0,
            "updated_at": now,
        },
        upsert=True,
    )
    account_ids = {}
    for key, name in [
        ("raw", "E2E Raw Stock"),
        ("wip", "E2E WIP"),
        ("fg", "E2E FG Stock"),
        ("clearing", "E2E Production Clearing"),
    ]:
        account_id = f"e2e-production-{key}-{suffix}"
        account_ids[key] = account_id
        db.accounts.replace_one(
            {"_id": account_id},
            {
                "_id": account_id,
                "account_name": f"{name} {suffix}",
                "account_type": "Asset",
                "current_balance": 0.0,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            upsert=True,
        )
    MongoProductionSettingsRepository(db).save(
        ProductionSettings(
            wip_account_id=account_ids["wip"],
            raw_material_account_id=account_ids["raw"],
            finished_goods_account_id=account_ids["fg"],
            expense_clearing_account_id=account_ids["clearing"],
        )
    )
    recipe_repo = MongoRecipeRepository(db)
    batch_repo = MongoProductionBatchRepository(db)
    recipe = recipe_repo.save(
        Recipe(
            name=f"E2E Recipe {suffix}",
            code=f"E2E-{suffix}",
            base_quantity=10,
            inputs=[RecipeInput(product_id=rm_id, product_name="Raw", qty=10)],
            outputs=[
                RecipeOutput(
                    product_id=fg_id,
                    product_name="Output",
                    expected_qty=8,
                    role=ProductionOutputRole.MAIN,
                    nrv_rate=25,
                )
            ],
        )
    )
    batch = ProductionDomainService(recipe_repo, batch_repo).create_batch(
        batch_number=f"E2E-PB-{suffix}",
        recipe_id=recipe.id,
        batch_date=date.today(),
        location_id=location_id,
        planned_quantity=10,
    )
    return batch


def test_post_batch_and_show_margin(page: Page, streamlit_server: str) -> None:
    batch = _seed_production_batch()
    page.context.add_cookies(
        [
            {
                "name": COOKIE_NAME,
                "value": issue_token("e2e-production-admin"),
                "url": streamlit_server,
            }
        ]
    )
    page.goto(f"{streamlit_server}/production-batch-detail?id={batch.id}")
    if page.get_by_text("Sign in to continue").is_visible():
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Username").fill("e2e-production-admin")
        dialog.get_by_label("Password").fill("e2e-production-admin")
        dialog.get_by_label("Password").press("Enter")
        page.wait_for_timeout(3000)
        if dialog.is_visible():
            alerts = page.locator('[data-testid="stAlert"]').all_inner_texts()
            if alerts:
                raise AssertionError(f"Sign-in failed: {alerts}")
    expect(page.get_by_text(batch.batch_number)).to_be_visible(timeout=15000)
    page.get_by_role("tab", name="Cost sheet").click()
    page.get_by_role("button", name="Post production batch").click()
    page.wait_for_timeout(3000)
    posted = MongoProductionBatchRepository(_db()).find_by_id(batch.id)
    assert posted is not None and posted.status.value == "Posted"
    page.goto(f"{streamlit_server}/production-margins")
    expect(page.get_by_role("heading", name="Production Cost & Margin")).to_be_visible()
    assert posted.batch_margin == 100.0
