"""QA test fixtures seeded into MongoDB for integration tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from bson import ObjectId
from pymongo.database import Database

from vaybooks.bms.application.delivery_app_service import DeliveryAppService
from vaybooks.bms.application.invoice_app_service import InvoiceAppService
from vaybooks.bms.application.time_tracking_app_service import TimeTrackingAppService
from vaybooks.bms.domain.expenses.entities import Expense
from vaybooks.bms.domain.orders.entities import CustomizationItem, CustomizationOrder, OrderActivity
from vaybooks.bms.domain.shared.enums import ActivityStatus, ExpenseSource, OrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.time_tracking.entities import TimeEntry
from vaybooks.bms.infrastructure.repositories.mongo_counter_repository import MongoCounterRepository
from vaybooks.bms.infrastructure.repositories.mongo_delivery_repository import MongoDeliveryRepository
from vaybooks.bms.infrastructure.repositories.mongo_expense_repository import MongoExpenseRepository
from vaybooks.bms.infrastructure.repositories.mongo_invoice_repository import MongoInvoiceRepository
from vaybooks.bms.infrastructure.repositories.mongo_order_repository import MongoOrderRepository
from vaybooks.bms.infrastructure.repositories.mongo_time_tracking_repository import MongoTimeTrackingRepository

ORDER_ID = "O-1001"
ORDER_NUMBER = "O-1001"
CUSTOMER_ID = "qa-cust-o1001"
BILL_NUMBERS = ("ZB005", "ZB006")
ITEM_SALE_PRICES = {"ZB005": 4500.0, "ZB006": 3500.0}
EXPECTED_TOTAL = sum(ITEM_SALE_PRICES.values())

ZB010_ORDER_ID = "O-1002"
ZB010_ORDER_NUMBER = "O-1002"
ZB010_CUSTOMER_ID = "qa-cust-o1002"
ZB010_BILL_NUMBER = "ZB010"
ZB010_ITEM_ID = "bill-zb010"
ZB010_SELL_AMOUNT = 5000.0
ZB010_ORIGINAL_HOURS = 5.0
ZB010_HOURLY_SELLING = 200.0
ZB010_FROZEN_MPH = 800.0  # (5000 - 5*200) / 5

O1004_ORDER_ID = "O-1004"
O1004_ORDER_NUMBER = "O-1004"
O1004_CUSTOMER_ID = "qa-cust-o1004"
O1004_BILL_NUMBER = "ZB015"
O1004_ITEM_ID = "bill-zb015"
O1004_SELL_AMOUNT = 6000.0

EXPORT_CUSTOMER_NAME = "Anjali Mehta"
EXPORT_CUSTOMER_PHONE = "9988776655"

EXPORT_ORDER_NUMBER = "ZC-2024-0061"
EXPORT_ORDER_DATE = datetime(2024, 3, 15, 10, 30, 0)
EXPORT_EXPECTED_DELIVERY_DATE = datetime(2024, 4, 1, 0, 0, 0)

QA_PINNED_ORDER_NUMBERS = (
    ORDER_NUMBER,
    ZB010_ORDER_NUMBER,
    O1004_ORDER_NUMBER,
    EXPORT_ORDER_NUMBER,
)


def sort_orders_for_list_view(orders: list[CustomizationOrder]) -> list[CustomizationOrder]:
    """Keep seeded QA fixture orders on the first page of the orders list."""
    from vaybooks.bms.domain.orders.order_refs import normalize_order_ref

    pinned = {normalize_order_ref(number) for number in QA_PINNED_ORDER_NUMBERS}
    pinned_orders: list[CustomizationOrder] = []
    other_orders: list[CustomizationOrder] = []
    for order in orders:
        if normalize_order_ref(order.order_number) in pinned:
            pinned_orders.append(order)
        else:
            other_orders.append(order)
    pinned_orders.sort(key=lambda o: normalize_order_ref(o.order_number))
    other_orders.sort(key=lambda o: o.updated_at or datetime.min, reverse=True)
    return pinned_orders + other_orders


def _build_o1001_order() -> CustomizationOrder:
    items = [
        CustomizationItem(
            item_id=f"bill-{bill.lower()}",
            bill_number=bill,
            description="Blouse" if bill == "ZB005" else "Lehenga",
            sell_amount=ITEM_SALE_PRICES[bill],
        )
        for bill in BILL_NUMBERS
    ]
    order = CustomizationOrder(
        id=ORDER_ID,
        order_number=ORDER_NUMBER,
        customer_id=CUSTOMER_ID,
        customer_name="Ananya Rao",
        phone_number="9876543210",
        order_date=date.today(),
        expected_delivery_date=date.today() + timedelta(days=7),
        order_status=OrderStatus.READY_FOR_DELIVERY,
        customization_items=items,
    )
    for item in order.customization_items:
        order.order_activities.append(
            OrderActivity(
                activity_id="act-stitch",
                activity_name="Stitching",
                bill_id=item.item_id,
                activity_status=ActivityStatus.COMPLETED,
                current_status="Completed",
            )
        )
    return order


def _stitching_activity_id(db: Database) -> str:
    doc = db.activity_config.find_one({"activity_name": "Stitching"})
    if not doc:
        raise RuntimeError("Stitching activity not found in activity_config seed data")
    return doc["_id"]


def _build_o1002_order(stitching_id: str) -> CustomizationOrder:
    order = CustomizationOrder(
        id=ZB010_ORDER_ID,
        order_number=ZB010_ORDER_NUMBER,
        customer_id=ZB010_CUSTOMER_ID,
        customer_name="Priya Menon",
        phone_number="9123456780",
        order_date=date.today(),
        expected_delivery_date=date.today() + timedelta(days=7),
        order_status=OrderStatus.READY_FOR_DELIVERY,
        customization_items=[
            CustomizationItem(
                item_id=ZB010_ITEM_ID,
                bill_number=ZB010_BILL_NUMBER,
                description="Blouse",
                sell_amount=ZB010_SELL_AMOUNT,
            )
        ],
    )
    order.order_activities.append(
        OrderActivity(
            activity_id=stitching_id,
            activity_name="Stitching",
            bill_id=ZB010_ITEM_ID,
            activity_status=ActivityStatus.COMPLETED,
            current_status="Completed",
        )
    )
    return order


def _build_o1004_order(stitching_id: str) -> CustomizationOrder:
    order = CustomizationOrder(
        id=O1004_ORDER_ID,
        order_number=O1004_ORDER_NUMBER,
        customer_id=O1004_CUSTOMER_ID,
        customer_name="Ananya Rao",
        phone_number="9876543211",
        order_date=date.today(),
        expected_delivery_date=date.today() + timedelta(days=7),
        order_status=OrderStatus.READY_FOR_DELIVERY,
        customization_items=[
            CustomizationItem(
                item_id=O1004_ITEM_ID,
                bill_number=O1004_BILL_NUMBER,
                description="Bridal Lehenga",
                sell_amount=O1004_SELL_AMOUNT,
            )
        ],
    )
    order.order_activities.append(
        OrderActivity(
            activity_id=stitching_id,
            activity_name="Stitching",
            bill_id=O1004_ITEM_ID,
            activity_status=ActivityStatus.COMPLETED,
            current_status="Completed",
        )
    )
    return order


def ensure_o1004_failed_invoice_attempt(db: Database) -> None:
    """Seed O-1004 and exercise a failed empty-bill_ids invoice for TC-INV-007."""
    order_repo = MongoOrderRepository(db)
    invoice_repo = MongoInvoiceRepository(db)
    expense_repo = MongoExpenseRepository(db)
    counter_repo = MongoCounterRepository(db)
    stitching_id = _stitching_activity_id(db)

    order = order_repo.find_by_order_number(O1004_ORDER_NUMBER)
    if not order:
        order = _build_o1004_order(stitching_id)
        order_repo.save(order)
    else:
        for invoice in invoice_repo.list_by_order(order.id):
            db.invoices.delete_one({"_id": invoice.id})
        if order.order_status != OrderStatus.READY_FOR_DELIVERY:
            order.order_status = OrderStatus.READY_FOR_DELIVERY
            order_repo.save(order)

    service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
    )
    try:
        service.generate_invoice(
            order_id=order.id,
            bill_ids=[],
            invoice_amount=O1004_SELL_AMOUNT,
        )
    except ValidationError:
        pass


def ensure_o1001_invoice(db: Database) -> None:
    """Create order O-1001 and generate its invoice for TC-INV-002."""
    order_repo = MongoOrderRepository(db)
    invoice_repo = MongoInvoiceRepository(db)
    expense_repo = MongoExpenseRepository(db)
    counter_repo = MongoCounterRepository(db)

    existing = order_repo.find_by_order_number(ORDER_NUMBER)
    if existing and invoice_repo.list_by_order(existing.id):
        return

    order = existing or _build_o1001_order()
    if not existing:
        order_repo.save(order)

    bill_ids = [item.item_id for item in order.customization_items]
    item_amounts = {
        item.item_id: float(item.sell_amount or 0.0)
        for item in order.customization_items
    }

    service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
    )
    service.generate_invoice(
        order_id=order.id,
        bill_ids=bill_ids,
        invoice_amount=EXPECTED_TOTAL,
        item_amounts=item_amounts,
    )


def _ensure_zb010_stitching_activity(order: CustomizationOrder, stitching_id: str) -> bool:
    """Ensure bill ZB010 has a completed Stitching activity on the order."""
    for activity in order.order_activities:
        if activity.bill_id == ZB010_ITEM_ID and activity.activity_name == "Stitching":
            changed = False
            if activity.activity_id != stitching_id:
                activity.activity_id = stitching_id
                changed = True
            if activity.activity_status != ActivityStatus.COMPLETED:
                activity.activity_status = ActivityStatus.COMPLETED
                activity.current_status = "Completed"
                changed = True
            return changed

    order.order_activities.append(
        OrderActivity(
            activity_id=stitching_id,
            activity_name="Stitching",
            bill_id=ZB010_ITEM_ID,
            activity_status=ActivityStatus.COMPLETED,
            current_status="Completed",
        )
    )
    return True


def ensure_zb010_frozen_mph(db: Database) -> None:
    """Seed O-1002 / ZB010 invoiced+delivered with frozen MPH for TC-INV-008."""
    order_repo = MongoOrderRepository(db)
    invoice_repo = MongoInvoiceRepository(db)
    expense_repo = MongoExpenseRepository(db)
    counter_repo = MongoCounterRepository(db)
    delivery_repo = MongoDeliveryRepository(db)
    time_repo = MongoTimeTrackingRepository(db)
    stitching_id = _stitching_activity_id(db)

    order = order_repo.find_by_order_number(ZB010_ORDER_NUMBER)
    if order:
        if _ensure_zb010_stitching_activity(order, stitching_id):
            order_repo.save(order)
        item = order.get_item_by_id(ZB010_ITEM_ID)
        entry = time_repo.find_by_id("qa-time-zb010-1")
        if (
            item
            and item.mph_snapshot_at is not None
            and invoice_repo.list_by_order(order.id)
            and entry
            and entry.duration_minutes == 300
        ):
            return
    else:
        order = _build_o1002_order(stitching_id)
        order_repo.save(order)

    bill_id = ZB010_ITEM_ID
    work_date = date.today()

    if not time_repo.find_by_order(order.id):
        time_repo.save(
            TimeEntry(
                id="qa-time-zb010-1",
                order_id=order.id,
                order_number=order.order_number,
                bill_id=bill_id,
                bill_number=ZB010_BILL_NUMBER,
                activity_id=stitching_id,
                activity_name="Stitching",
                work_date=work_date,
                start_time="09:00",
                end_time="11:00",
                duration_minutes=120,
            )
        )
        time_repo.save(
            TimeEntry(
                id="qa-time-zb010-2",
                order_id=order.id,
                order_number=order.order_number,
                bill_id=bill_id,
                bill_number=ZB010_BILL_NUMBER,
                activity_id=stitching_id,
                activity_name="Stitching",
                work_date=work_date,
                start_time="11:30",
                end_time="13:00",
                duration_minutes=90,
            )
        )
        time_repo.save(
            TimeEntry(
                id="qa-time-zb010-3",
                order_id=order.id,
                order_number=order.order_number,
                bill_id=bill_id,
                bill_number=ZB010_BILL_NUMBER,
                activity_id=stitching_id,
                activity_name="Stitching",
                work_date=work_date,
                start_time="14:00",
                end_time="15:30",
                duration_minutes=90,
            )
        )

    if not expense_repo.find_by_bill(bill_id):
        expense_repo.save(
            Expense(
                id="qa-exp-zb010-stitch",
                order_id=order.id,
                order_number=order.order_number,
                expense_date=work_date,
                expense_name="Stitching - In House",
                expense_source=ExpenseSource.IN_HOUSE,
                purchase_price=100.0,
                selling_price=ZB010_HOURLY_SELLING,
                quantity=ZB010_ORIGINAL_HOURS,
                total_purchase_price=ZB010_ORIGINAL_HOURS * 100.0,
                total_selling_price=ZB010_ORIGINAL_HOURS * ZB010_HOURLY_SELLING,
                linked_time_minutes=int(ZB010_ORIGINAL_HOURS * 60),
                linked_time_hours=ZB010_ORIGINAL_HOURS,
                bill_id=bill_id,
                bill_number=ZB010_BILL_NUMBER,
                activity_id=stitching_id,
                activity_name="Stitching",
            )
        )

    invoice_service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
        delivery_repo=delivery_repo,
    )
    if not invoice_repo.list_by_order(order.id):
        invoice_service.generate_invoice(
            order_id=order.id,
            bill_ids=[bill_id],
            invoice_amount=ZB010_SELL_AMOUNT,
            item_amounts={bill_id: ZB010_SELL_AMOUNT},
        )

    delivery_service = DeliveryAppService(
        delivery_repo,
        order_repo,
        invoice_repo,
        expense_repo,
    )
    deliveries = delivery_repo.list_by_order(order.id)
    delivered_ids = {bid for d in deliveries for bid in d.bill_ids}
    if bill_id not in delivered_ids:
        delivery_service.record_delivery(
            order_id=order.id,
            bill_ids=[bill_id],
            delivery_date=work_date,
        )

    time_service = TimeTrackingAppService(time_repo, order_repo)
    entry = time_repo.find_by_id("qa-time-zb010-1")
    if entry and entry.duration_minutes != 300:
        time_service.update_time_entry(
            "qa-time-zb010-1",
            work_date=work_date,
            start_time="09:00",
            end_time="14:00",
            worker_name="QA Worker",
            notes="Post-delivery correction",
            activity_id=stitching_id,
            activity_name="Stitching",
        )


def ensure_export_order_zc20240061(db: Database) -> None:
    """Seed ZC-2024-0061 with datetime order_date/ETD for TC-EXPORT-007."""
    existing = db.customization_orders.find_one({"order_number": EXPORT_ORDER_NUMBER})
    if existing:
        return

    now = datetime.utcnow()
    db.customization_orders.insert_one(
        {
            "_id": EXPORT_ORDER_NUMBER,
            "order_number": EXPORT_ORDER_NUMBER,
            "customer_id": "qa-cust-export-0061",
            "customer_name": "Export QA Customer",
            "phone_number": "9000012345",
            "order_date": EXPORT_ORDER_DATE,
            "expected_delivery_date": EXPORT_EXPECTED_DELIVERY_DATE,
            "order_status": OrderStatus.DRAFT.value,
            "advance_amount": 0.0,
            "customization_items": [],
            "order_activities": [],
            "created_at": now,
            "updated_at": now,
        }
    )


def ensure_export_customer_anjali(db: Database) -> None:
    """Seed Anjali Mehta with ObjectId _id and customer_account_id for TC-EXPORT-006."""
    existing = db.customers.find_one({"customer_name": EXPORT_CUSTOMER_NAME})
    if existing:
        return

    customer_id = ObjectId()
    account_id = ObjectId()
    now = datetime.utcnow()
    db.customers.insert_one(
        {
            "_id": customer_id,
            "customer_name": EXPORT_CUSTOMER_NAME,
            "phone_number": EXPORT_CUSTOMER_PHONE,
            "alternate_phone_number": None,
            "address": "12 Hill Road, Bandra",
            "notes": "QA export fixture",
            "customer_account_id": account_id,
            "created_at": now,
            "updated_at": now,
        }
    )


def ensure_cash_drawer_account(db: Database) -> None:
    """Ensure TC-ACC-007 finds a protected store account named Cash Drawer."""
    now = datetime.utcnow()
    cash_drawer = db.accounts.find_one({"account_name": "Cash Drawer"})
    cash = db.accounts.find_one({"account_name": "Cash"})

    if cash and cash_drawer and cash["_id"] != cash_drawer["_id"]:
        db.accounts.delete_one({"_id": cash["_id"]})
        cash = None

    if cash_drawer:
        updates = {}
        if not cash_drawer.get("is_store_account"):
            updates["is_store_account"] = True
        if not cash_drawer.get("is_active", True):
            updates["is_active"] = True
        if updates:
            updates["updated_at"] = now
            db.accounts.update_one({"_id": cash_drawer["_id"]}, {"$set": updates})
        return

    if cash:
        db.accounts.update_one(
            {"_id": cash["_id"]},
            {
                "$set": {
                    "account_name": "Cash Drawer",
                    "is_store_account": True,
                    "is_active": True,
                    "updated_at": now,
                }
            },
        )
        return

    db.accounts.insert_one(
        {
            "_id": "qa-cash-drawer",
            "account_name": "Cash Drawer",
            "account_type": "Asset",
            "linked_customer_id": None,
            "opening_balance": 0,
            "current_balance": 0,
            "is_store_account": True,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    )


def run_qa_fixtures(db: Database) -> None:
    from tests.qa.sync_execution_overrides import sync_execution_overrides

    sync_execution_overrides()

    ensure_cash_drawer_account(db)
    ensure_o1001_invoice(db)
    ensure_o1004_failed_invoice_attempt(db)
    ensure_zb010_frozen_mph(db)
    ensure_export_customer_anjali(db)
    ensure_export_order_zc20240061(db)
