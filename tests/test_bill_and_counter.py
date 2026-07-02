from tests.conftest import FakeBillRegistryRepository, FakeCounterRepository


def test_bill_number_uniqueness():
    from vaybooks.bms.domain.orders.value_objects import BillRegistryEntry
    from vaybooks.bms.domain.shared.exceptions import BillNumberExistsError

    repo = FakeBillRegistryRepository()
    repo.register(BillRegistryEntry(bill_number="ZB001", order_id="o1", bill_id="b1"))
    try:
        repo.register(BillRegistryEntry(bill_number="ZB001", order_id="o2", bill_id="b2"))
        assert False, "Should have raised"
    except BillNumberExistsError:
        pass


def test_counter_number_generation():
    counter = FakeCounterRepository()
    assert counter.next("order_number") == "CO-0001"
    assert counter.next("order_number") == "CO-0002"
    assert counter.next("invoice_number") == "INV-0001"
