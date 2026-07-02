from typing import List, Optional

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.vendor_services.entities import VendorService
from vaybooks.bms.domain.vendor_services.repository import VendorServiceRepository


class VendorServiceAppService:
    def __init__(self, service_repo: VendorServiceRepository):
        self._repo = service_repo

    def list_services(self, active_only: bool = True) -> List[VendorService]:
        return self._repo.list_all(active_only=active_only)

    def get_service(self, service_id: str) -> Optional[VendorService]:
        return self._repo.find_by_id(service_id)

    def create_service(
        self, service_name: str, expense_account_id: str
    ) -> VendorService:
        if not service_name.strip():
            raise ValidationError("Service name is required")
        if not expense_account_id:
            raise ValidationError("An expense account is required")
        service = VendorService(
            service_name=service_name.strip(),
            expense_account_id=expense_account_id,
        )
        return self._repo.save(service)

    def update_service(
        self,
        service_id: str,
        service_name: str,
        expense_account_id: str,
        is_active: bool = True,
    ) -> VendorService:
        service = self._repo.find_by_id(service_id)
        if not service:
            raise ValueError("Service not found")
        if not service_name.strip():
            raise ValidationError("Service name is required")
        if not expense_account_id:
            raise ValidationError("An expense account is required")
        service.service_name = service_name.strip()
        service.expense_account_id = expense_account_id
        service.is_active = is_active
        return self._repo.save(service)

    def deactivate_service(self, service_id: str) -> VendorService:
        service = self._repo.find_by_id(service_id)
        if not service:
            raise ValueError("Service not found")
        service.is_active = False
        return self._repo.save(service)
