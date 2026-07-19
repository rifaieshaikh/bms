"""Tests for boutique measurements, draft orders, bill suffixes, attachments, PDFs."""

from datetime import date
from types import SimpleNamespace

import pytest

from vaybooks.bms.domain.attachments.entities import Attachment
from vaybooks.bms.domain.attachments.services import AttachmentDomainService
from vaybooks.bms.domain.measurements.entities import (
    MeasurementRecord,
    MeasurementSpecField,
    MeasurementValue,
)
from vaybooks.bms.domain.measurements.seed_catalog import DEFAULT_MEASUREMENT_SPECS
from vaybooks.bms.domain.measurements.services import MeasurementDomainService
from vaybooks.bms.domain.orders.entities import CustomizationItem, CustomizationOrder
from vaybooks.bms.domain.orders.services import OrderDomainService
from vaybooks.bms.domain.shared.enums import (
    AttachmentCategory,
    FitPreference,
    MeasurementSection,
    OrderStatus,
    PersonType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.infrastructure.pdf.boutique_pdf import (
    generate_advance_receipt_pdf,
    generate_customization_item_pdf,
    generate_measurement_sheet_pdf,
)
from vaybooks.bms.domain.shared.document_customization import (
    DocumentTemplateSettings,
    SalesPrintSettings,
)
from vaybooks.bms.application.measurement_app_service import MeasurementAppService
from tests.conftest import FakeBillRegistryRepository, FakeOrderRepository


def test_seed_catalog_covers_all_person_types():
    covered = set()
    for row in DEFAULT_MEASUREMENT_SPECS:
        covered.update(row["person_types"])
    for person in PersonType:
        assert person.value in covered


def test_draft_order_skips_item_validation():
    domain = OrderDomainService(FakeOrderRepository(), FakeBillRegistryRepository())
    order = CustomizationOrder(
        order_number="CO-0001",
        customer_id="c1",
        customer_name="Test",
        phone_number="9999999999",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_status=OrderStatus.DRAFT,
    )
    domain.validate_order(order)


def test_confirm_requires_items():
    domain = OrderDomainService(FakeOrderRepository(), FakeBillRegistryRepository())
    order = CustomizationOrder(
        order_number="CO-0001",
        customer_id="c1",
        customer_name="Test",
        phone_number="9999999999",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        order_status=OrderStatus.IN_PROGRESS,
    )
    with pytest.raises(ValidationError, match="at least one customization item"):
        domain.validate_order(order)


def test_measurement_bill_suffix_allocation():
    registry = FakeBillRegistryRepository()
    domain = OrderDomainService(FakeOrderRepository(), registry)
    first = domain.next_measurement_bill_number("MS-0025")
    assert first == "MS-0025-01"
    from vaybooks.bms.domain.orders.value_objects import BillRegistryEntry

    registry.register(
        BillRegistryEntry(
            bill_number=first, order_id="o1", bill_id="i1"
        )
    )
    second = domain.next_measurement_bill_number("MS-0025")
    assert second == "MS-0025-02"


def test_measurement_record_requires_wearer_for_child():
    domain = MeasurementDomainService()
    record = MeasurementRecord(
        measurement_number="MS-0001",
        customer_id="c1",
        person_type=PersonType.BOY_CHILD,
        wearer_name="",
        values=[MeasurementValue(field_key="chest", value="24")],
    )
    specs = [
        MeasurementSpecField(
            key="chest",
            label="Chest",
            person_types=[PersonType.BOY_CHILD],
            section=MeasurementSection.TORSO,
            required=True,
        )
    ]
    with pytest.raises(ValidationError, match="Wearer name"):
        domain.validate_record(record, specs)


def test_attachment_image_size_limit():
    class Repo:
        def count_by_item_category(self, item_id, category):
            return 0

    service = AttachmentDomainService(Repo())
    attachment = Attachment(
        order_id="o1",
        item_id="i1",
        category=AttachmentCategory.REFERENCE,
        name="big.png",
        content_type="image/png",
        data=b"x" * (5 * 1024 * 1024 + 1),
    )
    with pytest.raises(ValidationError, match="5 MB"):
        service.validate_upload(attachment)


def test_measurement_pdf_smoke():
    record = MeasurementRecord(
        measurement_number="MS-0001",
        customer_id="c1",
        person_type=PersonType.WOMEN,
        fit_preference=FitPreference.REGULAR,
        values=[
            MeasurementValue(field_key="bust", value="36", unit="inch"),
            MeasurementValue(field_key="waist", value="30", unit="inch"),
        ],
        measured_by="Staff",
    )
    customer = SimpleNamespace(customer_name="Asha", phone_number="9000000000")
    business = SimpleNamespace(business_name="Zahcci Boutique")
    pdf = generate_measurement_sheet_pdf(record, customer, business)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000


def test_item_and_advance_pdf_smoke():
    order = CustomizationOrder(
        order_number="CO-0001",
        customer_id="c1",
        customer_name="Asha",
        phone_number="9000000000",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        advance_amount=500,
    )
    item = CustomizationItem(
        bill_number="MS-0001-01",
        description="Blouse",
        customer_specification="Deep neck",
    )
    customer = SimpleNamespace(customer_name="Asha", phone_number="9000000000")
    business = SimpleNamespace(business_name="Zahcci Boutique")
    item_pdf = generate_customization_item_pdf(
        order, item, customer, business, None, []
    )
    assert item_pdf.startswith(b"%PDF")
    assert len(item_pdf) > 10_000
    voucher = SimpleNamespace(
        voucher_number="VCH-0001",
        voucher_date=date.today(),
        description="Advance for CO-0001",
        lines=[],
    )
    adv_pdf = generate_advance_receipt_pdf(voucher, order, customer, business)
    assert adv_pdf.startswith(b"%PDF")
    assert len(adv_pdf) > 10_000


def test_boutique_pdf_uses_saved_document_print_settings():
    business = SimpleNamespace(
        trade_name="Zahcci",
        document_templates={
            "advance_receipt": DocumentTemplateSettings(
                print_settings=SalesPrintSettings(
                    paper_size="A5",
                    orientation="landscape",
                    template_style="modern",
                    accent_color="#7C3AED",
                )
            )
        },
    )
    order = SimpleNamespace(
        advance_amount=1500,
        order_number="CO-0001",
        customer_name="Asha",
        phone_number="9000000000",
    )
    voucher = SimpleNamespace(
        voucher_number="VCH-0001",
        voucher_date=date.today(),
        description="Advance for CO-0001",
        lines=[],
    )
    customer = SimpleNamespace(customer_name="Asha", phone_number="9000000000")
    pdf = generate_advance_receipt_pdf(voucher, order, customer, business)

    assert b"/MediaBox [0 0 595.28 419.53]" in pdf


def test_measurement_sections_are_configurable_and_ordered():
    class SectionRepo:
        def __init__(self):
            self.rows = {}

        def save(self, section):
            self.rows[section.id] = section
            return section

        def find_by_id(self, section_id):
            return self.rows.get(section_id)

        def find_by_key(self, key):
            return next(
                (row for row in self.rows.values() if row.key == key), None
            )

        def list_all(self, active_only=False):
            rows = list(self.rows.values())
            if active_only:
                rows = [row for row in rows if row.is_active]
            return sorted(rows, key=lambda row: (row.sort_order, row.label))

        def delete(self, section_id):
            self.rows.pop(section_id, None)

    class SpecRepo:
        def list_all(self, active_only=False):
            return []

    class RecordRepo:
        pass

    class CounterRepo:
        pass

    sections = SectionRepo()
    service = MeasurementAppService(
        SpecRepo(), RecordRepo(), CounterRepo(), sections
    )
    later = service.create_section("posture", "Posture", sort_order=200)
    earlier = service.create_section("primary", "Primary", sort_order=100)

    assert [row.key for row in service.list_sections()] == [
        "primary",
        "posture",
    ]

    service.update_section(later.id, label="Body Posture", sort_order=50)
    assert service.list_sections()[0].label == "Body Posture"
    assert service.list_sections(active_only=True)[0].key == "posture"
