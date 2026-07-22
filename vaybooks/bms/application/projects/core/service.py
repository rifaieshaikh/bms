from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.finance.accounting.repository import CounterRepository
from vaybooks.bms.domain.parties.customers.repository import CustomerRepository
from vaybooks.bms.domain.projects.entities import (
    Project,
    ProjectActivity,
    ProjectParty,
    ProjectPhase,
    ProjectTemplate,
    ProjectTemplateActivity,
    ProjectTemplatePhase,
)
from vaybooks.bms.domain.projects.repository import (
    ProjectRepository,
    ProjectTemplateRepository,
)
from vaybooks.bms.domain.projects.services import ProjectDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    PlaceOfSupplyMode,
    ProjectActivityStatus,
    ProjectBillingMode,
    ProjectPartyRole,
    ProjectStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectAppService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        template_repo: ProjectTemplateRepository,
        counter_repo: CounterRepository,
        customer_repo: CustomerRepository,
        activity_config_repo=None,
    ):
        self._project_repo = project_repo
        self._template_repo = template_repo
        self._counter_repo = counter_repo
        self._customer_repo = customer_repo
        self._activity_config_repo = activity_config_repo
        self._domain = ProjectDomainService()

    def _get_project(self, project_id: str) -> Project:
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _get_customer(self, customer_id: str) -> tuple[str, str]:
        customer = self._customer_repo.find_by_id(customer_id)
        if not customer:
            raise ValidationError("Customer not found")
        return customer.id, customer.customer_name

    def _validate_contract_value(self, contract_value: float) -> None:
        if float(contract_value or 0) < 0:
            raise ValidationError("Contract value cannot be negative")

    def _save_validated(self, project: Project) -> Project:
        self._domain.validate_activity_tree(project)
        project.updated_at = utc_now()
        return self._project_repo.save(project)

    def _project_from_template(
        self,
        template: ProjectTemplate,
        *,
        project_number: str,
        name: str,
        customer_id: str,
        customer_name: str,
        contract_value: float,
        site_address: str = "",
        site_state_code: str = "",
        notes: str = "",
        start_date: Optional[date] = None,
        expected_end_date: Optional[date] = None,
    ) -> Project:
        phase_id_map: dict[str, str] = {}
        phases: List[ProjectPhase] = []
        if template.phases_enabled:
            for template_phase in sorted(template.phases, key=lambda p: p.sort_order):
                phase = ProjectPhase(
                    name=template_phase.name,
                    sort_order=template_phase.sort_order,
                )
                phase_id_map[template_phase.id] = phase.id
                phases.append(phase)

        activity_id_map: dict[str, str] = {}
        activities: List[ProjectActivity] = []
        for template_activity in sorted(template.activities, key=lambda a: a.sort_order):
            parent_id = (
                activity_id_map.get(template_activity.parent_activity_id)
                if template_activity.parent_activity_id
                else None
            )
            activity = ProjectActivity(
                name=template_activity.name,
                sort_order=template_activity.sort_order,
                parent_activity_id=parent_id,
                default_hourly_rate=template_activity.default_hourly_rate,
            )
            activity_id_map[template_activity.id] = activity.id
            activities.append(activity)

        return Project(
            project_number=project_number,
            name=(name or "").strip(),
            customer_id=customer_id,
            customer_name=customer_name,
            contract_value=float(contract_value or 0.0),
            template_id=template.id,
            site_address=(site_address or "").strip(),
            site_state_code=(site_state_code or "").strip(),
            notes=(notes or "").strip(),
            start_date=start_date,
            expected_end_date=expected_end_date,
            phases_enabled=template.phases_enabled,
            max_activity_depth=template.max_activity_depth,
            billing_mode=template.billing_mode,
            retention_pct=template.retention_pct,
            place_of_supply_mode=template.place_of_supply_mode,
            default_hourly_rate=template.default_hourly_rate,
            parties=[
                ProjectParty(
                    party_id=customer_id,
                    party_name=customer_name,
                    role=ProjectPartyRole.CUSTOMER,
                    is_primary=True,
                )
            ],
            phases=phases,
            activities=activities,
        )

    def create_project_from_template(
        self,
        template_id: str,
        name: str,
        customer_id: str,
        contract_value: float,
        *,
        site_address: str = "",
        site_state_code: str = "",
        notes: str = "",
        start_date: Optional[date] = None,
        expected_end_date: Optional[date] = None,
    ) -> Project:
        template = self._template_repo.find_by_id(template_id)
        if not template:
            raise ValidationError("Project template not found")
        if not (name or "").strip():
            raise ValidationError("Project name is required")
        self._validate_contract_value(contract_value)
        customer_id, customer_name = self._get_customer(customer_id)
        project = self._project_from_template(
            template,
            project_number=self._counter_repo.next("project_number"),
            name=name,
            customer_id=customer_id,
            customer_name=customer_name,
            contract_value=contract_value,
            site_address=site_address,
            site_state_code=site_state_code,
            notes=notes,
            start_date=start_date,
            expected_end_date=expected_end_date,
        )
        return self._save_validated(project)

    def create_project(
        self,
        name: str,
        customer_id: str,
        contract_value: float,
        *,
        site_address: str = "",
        site_state_code: str = "",
        notes: str = "",
        start_date: Optional[date] = None,
        expected_end_date: Optional[date] = None,
        phases: Optional[List[ProjectPhase]] = None,
        activities: Optional[List[ProjectActivity]] = None,
    ) -> Project:
        if not (name or "").strip():
            raise ValidationError("Project name is required")
        self._validate_contract_value(contract_value)
        customer_id, customer_name = self._get_customer(customer_id)
        project = Project(
            project_number=self._counter_repo.next("project_number"),
            name=(name or "").strip(),
            customer_id=customer_id,
            customer_name=customer_name,
            contract_value=float(contract_value or 0.0),
            site_address=(site_address or "").strip(),
            site_state_code=(site_state_code or "").strip(),
            notes=(notes or "").strip(),
            start_date=start_date,
            expected_end_date=expected_end_date,
            parties=[
                ProjectParty(
                    party_id=customer_id,
                    party_name=customer_name,
                    role=ProjectPartyRole.CUSTOMER,
                    is_primary=True,
                )
            ],
            phases=list(phases or []),
            activities=list(activities or []),
        )
        return self._save_validated(project)

    def get_project(self, project_id: str) -> Optional[Project]:
        return self._project_repo.find_by_id(project_id)

    def list_templates(self) -> List[ProjectTemplate]:
        return self._template_repo.list_all()

    def get_template(self, template_id: str) -> Optional[ProjectTemplate]:
        return self._template_repo.find_by_id(template_id)

    def create_template(
        self,
        name: str,
        *,
        description: str = "",
        phases_enabled: bool = True,
        max_activity_depth: int = 3,
        billing_mode=None,
        retention_pct: float = 0.0,
        place_of_supply_mode=None,
        default_hourly_rate: float = 0.0,
        phase_names: Optional[List[str]] = None,
        activity_names: Optional[List[str]] = None,
    ) -> ProjectTemplate:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Template name is required")
        existing = {
            (t.name or "").strip().lower() for t in self._template_repo.list_all()
        }
        if name.lower() in existing:
            raise ValidationError(f"A template named '{name}' already exists")
        phases: List[ProjectTemplatePhase] = []
        for idx, phase_name in enumerate(phase_names or [], start=1):
            phase_name = (phase_name or "").strip()
            if phase_name:
                phases.append(
                    ProjectTemplatePhase(name=phase_name, sort_order=idx)
                )
        activities: List[ProjectTemplateActivity] = []
        for idx, activity_name in enumerate(activity_names or [], start=1):
            activity_name = (activity_name or "").strip()
            if activity_name:
                activities.append(
                    ProjectTemplateActivity(
                        name=activity_name, sort_order=idx
                    )
                )
        template = ProjectTemplate(
            name=name,
            description=(description or "").strip(),
            phases_enabled=bool(phases_enabled),
            max_activity_depth=int(max_activity_depth or 3),
            billing_mode=billing_mode or ProjectBillingMode.FIXED,
            retention_pct=float(retention_pct or 0.0),
            place_of_supply_mode=place_of_supply_mode
            or PlaceOfSupplyMode.SITE_STATE,
            default_hourly_rate=float(default_hourly_rate or 0.0),
            phases=phases,
            activities=activities,
            is_system=False,
        )
        return self._template_repo.save(template)

    def update_template(
        self,
        template_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        phases_enabled: Optional[bool] = None,
        max_activity_depth: Optional[int] = None,
        billing_mode=None,
        retention_pct: Optional[float] = None,
        place_of_supply_mode=None,
        default_hourly_rate: Optional[float] = None,
        phase_names: Optional[List[str]] = None,
        activity_names: Optional[List[str]] = None,
    ) -> ProjectTemplate:
        template = self._template_repo.find_by_id(template_id)
        if not template:
            raise ValidationError("Template not found")
        if name is not None:
            name = (name or "").strip()
            if not name:
                raise ValidationError("Template name is required")
            for other in self._template_repo.list_all():
                if other.id != template.id and other.name.lower() == name.lower():
                    raise ValidationError(f"A template named '{name}' already exists")
            template.name = name
        if description is not None:
            template.description = (description or "").strip()
        if phases_enabled is not None:
            template.phases_enabled = bool(phases_enabled)
        if max_activity_depth is not None:
            template.max_activity_depth = int(max_activity_depth)
        if billing_mode is not None:
            template.billing_mode = billing_mode
        if retention_pct is not None:
            template.retention_pct = float(retention_pct or 0.0)
        if place_of_supply_mode is not None:
            template.place_of_supply_mode = place_of_supply_mode
        if default_hourly_rate is not None:
            template.default_hourly_rate = float(default_hourly_rate or 0.0)
        if phase_names is not None:
            phases: List[ProjectTemplatePhase] = []
            for idx, phase_name in enumerate(phase_names, start=1):
                phase_name = (phase_name or "").strip()
                if phase_name:
                    phases.append(
                        ProjectTemplatePhase(name=phase_name, sort_order=idx)
                    )
            template.phases = phases
        if activity_names is not None:
            activities: List[ProjectTemplateActivity] = []
            for idx, activity_name in enumerate(activity_names, start=1):
                activity_name = (activity_name or "").strip()
                if activity_name:
                    activities.append(
                        ProjectTemplateActivity(
                            name=activity_name, sort_order=idx
                        )
                    )
            template.activities = activities
        template.updated_at = utc_now()
        return self._template_repo.save(template)

    def delete_template(self, template_id: str) -> None:
        template = self._template_repo.find_by_id(template_id)
        if not template:
            raise ValidationError("Template not found")
        if template.is_system:
            raise ValidationError("System templates cannot be deleted")
        self._template_repo.delete(template_id)

    def list_projects(self, status: Optional[ProjectStatus] = None) -> List[Project]:
        return self._project_repo.list_all(status=status)

    def search_projects(self, query: str = "") -> List[Project]:
        if not (query or "").strip():
            return self._project_repo.list_all()
        return self._project_repo.search(query)

    def update_project_settings(
        self,
        project_id: str,
        *,
        name: Optional[str] = None,
        contract_value: Optional[float] = None,
        site_address: Optional[str] = None,
        site_state_code: Optional[str] = None,
        notes: Optional[str] = None,
        start_date: Optional[date] = None,
        expected_end_date: Optional[date] = None,
        billing_mode=None,
        retention_pct: Optional[float] = None,
        place_of_supply_mode=None,
        default_hourly_rate: Optional[float] = None,
        phases_enabled: Optional[bool] = None,
        max_activity_depth: Optional[int] = None,
        status: Optional[ProjectStatus] = None,
        overhead_allocation_pct: Optional[float] = None,
        currency_code: Optional[str] = None,
        advance_gst_policy: Optional[str] = None,
        original_contract_value: Optional[float] = None,
        revised_contract_value: Optional[float] = None,
        advance_terms: Optional[str] = None,
        dlp_months: Optional[int] = None,
        project_manager: Optional[str] = None,
        consultant_name: Optional[str] = None,
        owner_name: Optional[str] = None,
        hard_budget_check: Optional[bool] = None,
        archetype: Optional[str] = None,
        scale_profile: Optional[str] = None,
    ) -> Project:
        project = self._get_project(project_id)
        if name is not None:
            name = (name or "").strip()
            if not name:
                raise ValidationError("Project name is required")
            project.name = name
        if original_contract_value is not None:
            if project.contract_approved:
                raise ValidationError(
                    "Original contract value cannot change after contract approval"
                )
            self._validate_contract_value(original_contract_value)
            project.original_contract_value = float(original_contract_value)
        if contract_value is not None:
            self._validate_contract_value(contract_value)
            if project.contract_approved:
                project.revised_contract_value = float(contract_value)
                project.contract_value = float(contract_value)
            else:
                project.contract_value = float(contract_value)
        if revised_contract_value is not None:
            self._validate_contract_value(revised_contract_value)
            project.revised_contract_value = float(revised_contract_value)
            if project.contract_approved:
                project.contract_value = float(revised_contract_value)
        if site_address is not None:
            project.site_address = (site_address or "").strip()
        if site_state_code is not None:
            project.site_state_code = (site_state_code or "").strip()
        if notes is not None:
            project.notes = (notes or "").strip()
        if start_date is not None:
            project.start_date = start_date
        if expected_end_date is not None:
            project.expected_end_date = expected_end_date
        if billing_mode is not None:
            project.billing_mode = billing_mode
        if retention_pct is not None:
            project.retention_pct = float(retention_pct or 0.0)
        if place_of_supply_mode is not None:
            project.place_of_supply_mode = place_of_supply_mode
        if default_hourly_rate is not None:
            project.default_hourly_rate = float(default_hourly_rate or 0.0)
        if phases_enabled is not None:
            project.phases_enabled = bool(phases_enabled)
        if max_activity_depth is not None:
            project.max_activity_depth = int(max_activity_depth)
        if status is not None:
            project.status = status
        if overhead_allocation_pct is not None:
            project.overhead_allocation_pct = float(overhead_allocation_pct or 0.0)
        if currency_code is not None:
            code = (currency_code or "").strip().upper()
            project.currency_code = code or "INR"
        if advance_gst_policy is not None:
            project.advance_gst_policy = (advance_gst_policy or "").strip()
        if advance_terms is not None:
            project.advance_terms = (advance_terms or "").strip()
        if dlp_months is not None:
            project.dlp_months = int(dlp_months or 0)
        if project_manager is not None:
            project.project_manager = (project_manager or "").strip()
        if consultant_name is not None:
            project.consultant_name = (consultant_name or "").strip()
        if owner_name is not None:
            project.owner_name = (owner_name or "").strip()
        if hard_budget_check is not None:
            project.hard_budget_check = bool(hard_budget_check)
        if archetype is not None:
            project.archetype = (archetype or "").strip() or "Custom"
        if scale_profile is not None:
            project.scale_profile = (scale_profile or "").strip() or "Small"
        return self._save_validated(project)

    def update_phases(self, project_id: str, phases: List[ProjectPhase]) -> Project:
        project = self._get_project(project_id)
        project.phases = list(phases or [])
        return self._save_validated(project)

    def update_activities(
        self, project_id: str, activities: List[ProjectActivity]
    ) -> Project:
        project = self._get_project(project_id)
        project.activities = list(activities or [])
        return self._save_validated(project)

    def add_activity(
        self,
        project_id: str,
        name: str,
        *,
        parent_activity_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        default_hourly_rate: float = 0,
        planned_hours: float = 0,
        planned_cost: float = 0,
        planned_revenue_amount: float = 0,
        planned_revenue_pct: float = 0,
        status=None,
        planned_start: Optional[date] = None,
        planned_end: Optional[date] = None,
        percent_complete: float = 0,
        weightage: float = 0,
        boq_item_ids: Optional[List[str]] = None,
        predecessor_ids: Optional[List[str]] = None,
    ) -> Project:
        project = self._get_project(project_id)
        if not (name or "").strip():
            raise ValidationError("Activity name is required")
        if parent_activity_id:
            parent = next(
                (a for a in project.activities if a.id == parent_activity_id),
                None,
            )
            if not parent:
                raise ValidationError("Parent activity not found")
            # Parents roll up revenue from children — clear leaf revenue on parent
            parent.planned_revenue_amount = 0.0
            parent.planned_revenue_pct = 0.0
        activity_status = status or ProjectActivityStatus.PENDING
        if isinstance(activity_status, str):
            activity_status = ProjectActivityStatus(activity_status)
        max_sort = max((a.sort_order for a in project.activities), default=0)
        project.activities.append(
            ProjectActivity(
                name=(name or "").strip(),
                sort_order=max_sort + 1,
                parent_activity_id=parent_activity_id,
                phase_id=phase_id,
                status=activity_status,
                default_hourly_rate=float(default_hourly_rate or 0.0),
                planned_hours=float(planned_hours or 0.0),
                planned_cost=float(planned_cost or 0.0),
                planned_revenue_amount=float(planned_revenue_amount or 0.0),
                planned_revenue_pct=float(planned_revenue_pct or 0.0),
                planned_start=planned_start,
                planned_end=planned_end,
                percent_complete=float(percent_complete or 0.0),
                weightage=float(weightage or 0.0),
                boq_item_ids=list(boq_item_ids or []),
                predecessor_ids=list(predecessor_ids or []),
            )
        )
        return self._save_validated(project)

    def update_activity(self, project_id: str, activity_id: str, **fields) -> Project:
        allowed = {
            "name",
            "parent_activity_id",
            "phase_id",
            "status",
            "default_hourly_rate",
            "planned_hours",
            "planned_cost",
            "planned_revenue_amount",
            "planned_revenue_pct",
            "sort_order",
            "planned_start",
            "planned_end",
            "percent_complete",
            "weightage",
            "boq_item_ids",
            "predecessor_ids",
            "amount",
            "current_status",
            "activity_config_id",
            "activity_category",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValidationError(f"Unknown fields: {', '.join(sorted(unknown))}")

        project = self._get_project(project_id)
        activity = next(
            (a for a in project.activities if a.id == activity_id),
            None,
        )
        if not activity:
            raise ValidationError("Activity not found")

        if "name" in fields:
            name = (fields["name"] or "").strip()
            if not name:
                raise ValidationError("Activity name is required")
            activity.name = name

        if "parent_activity_id" in fields:
            parent_id = fields["parent_activity_id"]
            if parent_id:
                if parent_id == activity_id:
                    raise ValidationError("Activity cannot be its own parent")
                parent = next(
                    (a for a in project.activities if a.id == parent_id),
                    None,
                )
                if not parent:
                    raise ValidationError("Parent activity not found")
            activity.parent_activity_id = parent_id

        if "phase_id" in fields:
            phase_id = fields["phase_id"]
            if phase_id and not any(p.id == phase_id for p in project.phases):
                raise ValidationError("Phase not found")
            activity.phase_id = phase_id

        if "status" in fields:
            status = fields["status"]
            if isinstance(status, str):
                status = ProjectActivityStatus(status)
            activity.status = status

        if "amount" in fields:
            activity.amount = float(fields["amount"] or 0.0)
            activity.planned_revenue_amount = activity.amount

        if "current_status" in fields:
            activity.current_status = (fields["current_status"] or "Created").strip()

        if "activity_category" in fields:
            activity.activity_category = (fields["activity_category"] or "").strip()

        if "activity_config_id" in fields:
            activity.activity_config_id = (fields["activity_config_id"] or "").strip()

        for key in (
            "default_hourly_rate",
            "planned_hours",
            "planned_cost",
            "planned_revenue_amount",
            "planned_revenue_pct",
            "percent_complete",
            "weightage",
        ):
            if key in fields:
                setattr(activity, key, float(fields[key] or 0.0))
                if key == "planned_revenue_amount":
                    activity.amount = float(fields[key] or 0.0)

        if "sort_order" in fields:
            activity.sort_order = int(fields["sort_order"] or 0)
        if "planned_start" in fields:
            activity.planned_start = fields["planned_start"]
        if "planned_end" in fields:
            activity.planned_end = fields["planned_end"]
        if "boq_item_ids" in fields:
            activity.boq_item_ids = list(fields["boq_item_ids"] or [])
        if "predecessor_ids" in fields:
            activity.predecessor_ids = list(fields["predecessor_ids"] or [])

        if any(a.parent_activity_id == activity_id for a in project.activities):
            activity.planned_revenue_amount = 0.0
            activity.amount = 0.0

        return self._save_validated(project)

    def add_activities_from_catalog(
        self,
        project_id: str,
        config_ids: List[str],
        *,
        phase_id: Optional[str] = None,
    ) -> Project:
        if not self._activity_config_repo:
            raise ValidationError("Project activity catalog is unavailable")
        project = self._get_project(project_id)
        if phase_id and not any(p.id == phase_id for p in project.phases):
            raise ValidationError("Phase not found")
        existing_config_ids = {
            a.activity_config_id for a in project.activities if a.activity_config_id
        }
        max_sort = max((a.sort_order for a in project.activities), default=0)
        added = 0
        for config_id in config_ids or []:
            if not config_id or config_id in existing_config_ids:
                continue
            config = self._activity_config_repo.find_by_id(config_id)
            if not config or not config.is_active:
                raise ValidationError(f"Activity catalog entry not found: {config_id}")
            max_sort += 1
            amount = float(config.default_amount or 0.0)
            project.activities.append(
                ProjectActivity(
                    name=config.activity_name,
                    sort_order=max_sort,
                    phase_id=phase_id,
                    activity_config_id=config.id,
                    activity_category=config.activity_category.value,
                    current_status="Created",
                    amount=amount,
                    default_hourly_rate=float(config.default_hourly_rate or 0.0),
                    planned_revenue_amount=amount,
                    status=ProjectActivityStatus.PENDING,
                )
            )
            existing_config_ids.add(config.id)
            added += 1
        if not added:
            raise ValidationError(
                "No new activities to add (already on project or empty)"
            )
        return self._save_validated(project)

    def assert_activity_transition(
        self,
        project_id: str,
        activity_id: str,
        new_status: str,
        *,
        block_reason: str = "",
    ) -> None:
        """Validate workflow guards before an activity status change (AC-005)."""
        project = self._get_project(project_id)
        activity = self._get_activity(project, activity_id)
        new_status = (new_status or "").strip()
        if new_status == "Blocked":
            if not (block_reason or "").strip():
                raise ValidationError("Block reason is required")
            return
        if activity.blocked and new_status == "Completed":
            raise ValidationError("Cannot complete a blocked activity")
        current = (activity.current_status or "Created").strip() or "Created"
        # Starting = leaving Created for an active / completed status
        is_start = current in ("Created", "Pending") and new_status not in (
            "Created",
            "Pending",
            "Blocked",
            "",
        )
        if not is_start:
            return
        if not activity.predecessor_ids:
            return
        by_id = {a.id: a for a in project.activities}
        for pred_id in activity.predecessor_ids:
            pred = by_id.get(pred_id)
            if not pred:
                raise ValidationError(f"Predecessor activity not found: {pred_id}")
            completed = (
                pred.status == ProjectActivityStatus.COMPLETED
                or (pred.current_status or "") == "Completed"
                or float(pred.percent_complete or 0) >= 100.0
            )
            if not completed:
                raise ValidationError(
                    f"Predecessor '{pred.name}' must be completed before start"
                )

    def set_activity_workflow_status(
        self, project_id: str, activity_id: str, status_name: str
    ) -> Project:
        project = self._get_project(project_id)
        activity = next((a for a in project.activities if a.id == activity_id), None)
        if not activity:
            raise ValidationError("Activity not found")
        status_name = (status_name or "").strip()
        allowed_statuses: List[str] = ["Created", "Completed"]
        if activity.activity_config_id and self._activity_config_repo:
            config = self._activity_config_repo.find_by_id(activity.activity_config_id)
            if config:
                allowed_statuses = list(config.statuses)
        if status_name not in allowed_statuses:
            raise ValidationError(
                f"Status must be one of: {', '.join(allowed_statuses)}"
            )
        self.assert_activity_transition(project_id, activity_id, status_name)
        # Reload after assert (assert loads its own copy)
        project = self._get_project(project_id)
        activity = self._get_activity(project, activity_id)
        activity.current_status = status_name
        if status_name == "Completed":
            activity.status = ProjectActivityStatus.COMPLETED
            activity.percent_complete = 100.0
        elif status_name == "Created":
            activity.status = ProjectActivityStatus.PENDING
        else:
            activity.status = ProjectActivityStatus.IN_PROGRESS
        return self._save_validated(project)

    def update_activity_amount(
        self, project_id: str, activity_id: str, amount: float
    ) -> Project:
        if float(amount or 0) < 0:
            raise ValidationError("Amount cannot be negative")
        return self.update_activity(
            project_id, activity_id, amount=float(amount or 0.0)
        )

    def assign_activity_phase(
        self, project_id: str, activity_id: str, phase_id: Optional[str]
    ) -> Project:
        return self.update_activity(project_id, activity_id, phase_id=phase_id)

    def delete_activity(
        self,
        project_id: str,
        activity_id: str,
        *,
        time_repo=None,
        expense_repo=None,
    ) -> Project:
        project = self._get_project(project_id)
        activity = next(
            (a for a in project.activities if a.id == activity_id),
            None,
        )
        if not activity:
            raise ValidationError("Activity not found")
        if any(a.parent_activity_id == activity_id for a in project.activities):
            raise ValidationError(
                "Remove child activities before deleting this activity"
            )
        if time_repo and time_repo.list_by_activity(activity_id):
            raise ValidationError("Activity has linked time entries")
        if expense_repo:
            linked = [
                e
                for e in expense_repo.list_by_project(project_id)
                if e.activity_id == activity_id
            ]
            if linked:
                raise ValidationError("Activity has linked expenses")
        project.activities = [a for a in project.activities if a.id != activity_id]
        return self._save_validated(project)

    def add_phase(self, project_id: str, name: str) -> Project:
        project = self._get_project(project_id)
        if not (name or "").strip():
            raise ValidationError("Phase name is required")
        max_sort = max((p.sort_order for p in project.phases), default=0)
        project.phases.append(
            ProjectPhase(name=(name or "").strip(), sort_order=max_sort + 1)
        )
        return self._save_validated(project)

    def update_phase(
        self,
        project_id: str,
        phase_id: str,
        name: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> Project:
        project = self._get_project(project_id)
        phase = next((p for p in project.phases if p.id == phase_id), None)
        if not phase:
            raise ValidationError("Phase not found")
        if name is not None:
            name = (name or "").strip()
            if not name:
                raise ValidationError("Phase name is required")
            phase.name = name
        if sort_order is not None:
            phase.sort_order = int(sort_order)
        return self._save_validated(project)

    def delete_phase(self, project_id: str, phase_id: str) -> Project:
        project = self._get_project(project_id)
        phase = next((p for p in project.phases if p.id == phase_id), None)
        if not phase:
            raise ValidationError("Phase not found")
        for activity in project.activities:
            if activity.phase_id == phase_id:
                activity.phase_id = None
        project.phases = [p for p in project.phases if p.id != phase_id]
        return self._save_validated(project)

    def mark_physically_completed(self, project_id: str, by: str = "") -> Project:
        project = self._get_project(project_id)
        if project.status == ProjectStatus.FINANCIALLY_CLOSED:
            raise ValidationError("Project is financially closed")
        project.status = ProjectStatus.PHYSICALLY_COMPLETED
        project.physically_completed_at = utc_now()
        project.updated_at = utc_now()
        if by:
            project.notes = (project.notes or "").strip()
        return self._project_repo.save(project)

    def mark_dlp(self, project_id: str) -> Project:
        project = self._get_project(project_id)
        if project.status not in (
            ProjectStatus.PHYSICALLY_COMPLETED,
            ProjectStatus.ACTIVE,
        ):
            raise ValidationError(
                "Project must be active or physically completed before entering DLP"
            )
        project.status = ProjectStatus.DLP
        project.updated_at = utc_now()
        return self._project_repo.save(project)

    def get_weighted_progress(self, project_id: str) -> float:
        project = self._get_project(project_id)
        leaf_ids = self._domain.leaf_activity_ids(project)
        weighted = 0.0
        total_weight = 0.0
        for activity in project.activities:
            if activity.id not in leaf_ids:
                continue
            weight = float(activity.weightage or 0.0)
            if weight <= 0:
                weight = 1.0
            total_weight += weight
            weighted += weight * float(activity.percent_complete or 0.0)
        if total_weight <= 0:
            return 0.0
        return round(weighted / total_weight, 2)

    def get_closure_blockers(
        self,
        project_id: str,
        *,
        billing_service=None,
        measurement_service=None,
        expense_repo=None,
    ) -> List[dict]:
        if billing_service and hasattr(billing_service, "get_closure_blockers"):
            return billing_service.get_closure_blockers(
                project_id,
                measurement_service=measurement_service,
                expense_repo=expense_repo,
            )
        return []

    def close_project(
        self,
        project_id: str,
        closed_by: str = "",
        force: bool = False,
        billing_service=None,
        measurement_service=None,
        expense_repo=None,
    ) -> Project:
        project = self._get_project(project_id)
        if project.status == ProjectStatus.FINANCIALLY_CLOSED:
            raise ValidationError("Project is already closed")
        blockers = self.get_closure_blockers(
            project_id,
            billing_service=billing_service,
            measurement_service=measurement_service,
            expense_repo=expense_repo,
        )
        blocking = [b for b in blockers if b.get("severity") == "block"]
        if blocking and not force:
            summary = "; ".join(b.get("message", b.get("type", "blocker")) for b in blocking)
            raise ValidationError(f"Project cannot be closed: {summary}")
        snapshot = None
        if billing_service and not force:
            readiness = billing_service.books_match(project_id)
            if not readiness.get("books_match"):
                raise ValidationError(
                    "Project books do not match; settle outstanding balances or use force=True"
                )
            snapshot = readiness
        if blockers:
            snapshot = snapshot or {}
            snapshot["closure_blockers"] = blockers
        project.status = ProjectStatus.FINANCIALLY_CLOSED
        project.closed_at = utc_now()
        project.closed_by = (closed_by or "").strip()
        project.final_snapshot = snapshot
        project.updated_at = utc_now()
        return self._project_repo.save(project)

    def lock_period(self, project_id: str) -> Project:
        project = self._get_project(project_id)
        project.period_locked = True
        project.updated_at = utc_now()
        return self._project_repo.save(project)

    def unlock_period(self, project_id: str) -> Project:
        project = self._get_project(project_id)
        project.period_locked = False
        project.updated_at = utc_now()
        return self._project_repo.save(project)

    def _get_activity(self, project: Project, activity_id: str):
        activity = next((a for a in project.activities if a.id == activity_id), None)
        if not activity:
            raise ValidationError("Activity not found")
        return activity

    def block_activity(
        self, project_id: str, activity_id: str, reason: str = ""
    ) -> Project:
        self.assert_activity_transition(
            project_id, activity_id, "Blocked", block_reason=reason
        )
        project = self._get_project(project_id)
        activity = self._get_activity(project, activity_id)
        activity.blocked = True
        activity.block_reason = (reason or "").strip()
        activity.current_status = "Blocked"
        return self._save_validated(project)

    def resolve_activity(self, project_id: str, activity_id: str) -> Project:
        project = self._get_project(project_id)
        activity = self._get_activity(project, activity_id)
        activity.blocked = False
        activity.block_reason = ""
        if activity.current_status == "Blocked":
            activity.current_status = "In Progress"
            activity.status = ProjectActivityStatus.IN_PROGRESS
        return self._save_validated(project)

    def submit_activity_completion(
        self, project_id: str, activity_id: str
    ) -> Project:
        project = self._get_project(project_id)
        activity = self._get_activity(project, activity_id)
        if activity.blocked:
            raise ValidationError("Cannot complete a blocked activity")
        activity.completion_submitted = True
        return self._save_validated(project)

    def approve_activity_completion(
        self, project_id: str, activity_id: str
    ) -> Project:
        project = self._get_project(project_id)
        activity = self._get_activity(project, activity_id)
        if activity.blocked:
            raise ValidationError("Cannot complete a blocked activity")
        if not activity.completion_submitted:
            raise ValidationError("Completion has not been submitted")
        activity.completion_submitted = False
        activity.current_status = "Completed"
        activity.status = ProjectActivityStatus.COMPLETED
        activity.percent_complete = 100.0
        return self._save_validated(project)

    def reopen_project(self, project_id: str, reason: str) -> Project:
        project = self._get_project(project_id)
        if not (reason or "").strip():
            raise ValidationError("Reopen reason is required")
        if project.status not in (
            ProjectStatus.PHYSICALLY_COMPLETED,
            ProjectStatus.FINANCIALLY_CLOSED,
            ProjectStatus.DLP,
        ):
            raise ValidationError(
                "Only completed, DLP, or closed projects can be reopened"
            )
        project.status = ProjectStatus.ACTIVE
        project.reopen_reason = reason.strip()
        project.reopened_at = utc_now()
        project.closed_at = None
        project.closed_by = ""
        project.period_locked = False
        project.physically_completed_at = None
        project.updated_at = utc_now()
        return self._project_repo.save(project)
