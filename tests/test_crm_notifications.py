from datetime import datetime, timedelta

from vaybooks.bms.application.crm.notifications import CrmNotificationAppService
from vaybooks.bms.application.crm.payment_reminder import CrmPaymentReminderService
from vaybooks.bms.domain.crm.access import CrmAccessPolicy
from vaybooks.bms.domain.crm.entities import (
    CrmActivity,
    CrmNotificationPreferences,
)
from vaybooks.bms.domain.identity.entities import User
from tests.test_crm_foundation import (
    FakeActivityRepo,
    FakeCustomer,
    FakeCustomerService,
    FakeNotificationRepo,
    FakeSettingsRepo,
)


class FakePreferenceRepo:
    def __init__(self):
        self.values = {}

    def find_by_user_id(self, user_id):
        return self.values.get(user_id)

    def save(self, prefs):
        self.values[prefs.user_id] = prefs
        return prefs


class FakeAccounting:
    def __init__(self, balances):
        self.balances = balances

    def customer_balances_by_customer(self):
        return dict(self.balances)


def test_app_wide_permission_keys_drive_crm_access_policy():
    user = User(username="manager")
    policy = CrmAccessPolicy(
        user,
        {
            "crm.records.view_team",
            "crm.leads.assign",
            "crm.settings.view",
        },
    )
    assert policy.is_manager()
    assert policy.can_assign()
    assert not policy.is_admin()


def test_due_notification_generation_is_deduplicated():
    activities = FakeActivityRepo()
    activity = CrmActivity(
        activity_type="Called",
        assigned_user_id="rep-1",
        party_name="Acme",
        scheduled_at=datetime.utcnow() - timedelta(days=1),
        status="Scheduled",
    )
    activities.save(activity)
    repo = FakeNotificationRepo()
    service = CrmNotificationAppService(
        repo,
        preferences_repo=FakePreferenceRepo(),
        activity_repo=activities,
    )

    first = service.generate_due_notifications()
    second = service.generate_due_notifications()
    assert len(first) == 1
    assert len(second) == 1
    assert len(repo._store) == 1
    assert next(iter(repo._store.values())).kind == "overdue_follow_up"


def test_scheduled_payment_reminder_generator_never_duplicates_tasks():
    customers = FakeCustomerService()
    customer = FakeCustomer(
        customer_name="Acme",
        phone_number="9876543210",
        assigned_user_id="rep-1",
    )
    customers._by_id[customer.id] = customer
    activities = FakeActivityRepo()
    service = CrmPaymentReminderService(
        FakeSettingsRepo(),
        activity_repo=activities,
        customer_service=customers,
        accounting_service=FakeAccounting({customer.id: 2000}),
    )
    now = datetime.utcnow()

    first = service.generate_scheduled_reminders(as_of=now)
    second = service.generate_scheduled_reminders(as_of=now)
    assert first
    assert len(activities._store) == len(first)
    assert [task.id for task in second] == [task.id for task in first]
    assert all(task.status == "Scheduled" for task in first)
