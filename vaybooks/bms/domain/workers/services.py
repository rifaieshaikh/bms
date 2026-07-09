from vaybooks.bms.domain.workers.entities import Worker


class WorkerDomainService:
    @staticmethod
    def build_salary_account_name(worker: Worker) -> str:
        return f"Salary - {worker.worker_name.strip()}"
