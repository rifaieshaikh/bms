from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from vaybooks.bms.domain.projects.entities import Project, ProjectActivity, ProjectExpense
from vaybooks.bms.domain.projects.services import ProjectDomainService


@dataclass
class ActivityProfitRow:
    activity_id: str
    activity_name: str
    parent_activity_id: Optional[str]
    person_hours: float = 0.0
    labour_cost: float = 0.0
    other_cost: float = 0.0
    total_cost: float = 0.0
    planned_revenue: float = 0.0
    billed_revenue: float = 0.0
    budget_margin: Optional[float] = None
    budget_mph: Optional[float] = None
    billed_margin: Optional[float] = None
    billed_mph: Optional[float] = None


@dataclass
class ProjectProfitability:
    project_id: str
    person_hours: float = 0.0
    labour_cost: float = 0.0
    other_cost: float = 0.0
    total_cost: float = 0.0
    planned_revenue: float = 0.0
    billed_revenue: float = 0.0
    budget_margin: Optional[float] = None
    budget_mph: Optional[float] = None
    billed_margin: Optional[float] = None
    billed_mph: Optional[float] = None
    unallocated_cost: float = 0.0
    activity_rows: List[ActivityProfitRow] = field(default_factory=list)


class ProjectProfitabilityCalculator:
    def __init__(self, domain: Optional[ProjectDomainService] = None):
        self._domain = domain or ProjectDomainService()

    def calculate(
        self,
        project: Project,
        time_entries: list,
        expenses: List[ProjectExpense],
        billed_by_activity: Optional[Dict[str, float]] = None,
    ) -> ProjectProfitability:
        billed_by_activity = billed_by_activity or {}
        revenue_map = self._domain.roll_up_planned_revenue(project)
        total_planned = sum(revenue_map.values()) if revenue_map else 0.0
        # Avoid double-count: only sum leaf revenues for project total
        leaf_ids = self._domain.leaf_activity_ids(project)
        total_planned = sum(
            revenue_map.get(aid, 0.0) for aid in leaf_ids
        )

        labour_by_activity: Dict[str, float] = {}
        hours_by_activity: Dict[str, float] = {}
        for entry in time_entries:
            labour_by_activity[entry.activity_id] = (
                labour_by_activity.get(entry.activity_id, 0.0) + entry.labour_cost
            )
            hours_by_activity[entry.activity_id] = (
                hours_by_activity.get(entry.activity_id, 0.0)
                + entry.duration_minutes / 60.0
            )

        other_by_activity: Dict[str, float] = {}
        unallocated = 0.0
        for exp in expenses:
            if exp.activity_id:
                other_by_activity[exp.activity_id] = (
                    other_by_activity.get(exp.activity_id, 0.0) + exp.amount
                )
            else:
                unallocated += exp.amount

        activity_rows: List[ActivityProfitRow] = []
        for activity in project.activities:
            labour = labour_by_activity.get(activity.id, 0.0)
            hours = hours_by_activity.get(activity.id, 0.0)
            other = other_by_activity.get(activity.id, 0.0)
            total = labour + other
            planned_rev = revenue_map.get(activity.id, 0.0)
            billed_rev = billed_by_activity.get(activity.id, 0.0)
            row = ActivityProfitRow(
                activity_id=activity.id,
                activity_name=activity.name,
                parent_activity_id=activity.parent_activity_id,
                person_hours=round(hours, 2),
                labour_cost=round(labour, 2),
                other_cost=round(other, 2),
                total_cost=round(total, 2),
                planned_revenue=round(planned_rev, 2),
                billed_revenue=round(billed_rev, 2),
            )
            if planned_rev > 0 or total > 0:
                row.budget_margin = round(planned_rev - total, 2)
                row.budget_mph = (
                    round(row.budget_margin / hours, 2) if hours > 0 else None
                )
            if billed_rev > 0 or total > 0:
                row.billed_margin = round(billed_rev - total, 2)
                row.billed_mph = (
                    round(row.billed_margin / hours, 2) if hours > 0 else None
                )
            activity_rows.append(row)

        total_labour = sum(labour_by_activity.values())
        total_hours = sum(hours_by_activity.values())
        total_other = sum(other_by_activity.values()) + unallocated
        total_cost = total_labour + total_other
        total_billed = sum(billed_by_activity.values())

        result = ProjectProfitability(
            project_id=project.id,
            person_hours=round(total_hours, 2),
            labour_cost=round(total_labour, 2),
            other_cost=round(total_other, 2),
            total_cost=round(total_cost, 2),
            planned_revenue=round(total_planned, 2),
            billed_revenue=round(total_billed, 2),
            unallocated_cost=round(unallocated, 2),
            activity_rows=activity_rows,
        )
        if total_planned > 0 or total_cost > 0:
            result.budget_margin = round(total_planned - total_cost, 2)
            result.budget_mph = (
                round(result.budget_margin / total_hours, 2)
                if total_hours > 0
                else None
            )
        if total_billed > 0 or total_cost > 0:
            result.billed_margin = round(total_billed - total_cost, 2)
            result.billed_mph = (
                round(result.billed_margin / total_hours, 2)
                if total_hours > 0
                else None
            )
        return result
