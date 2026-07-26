"""Projects schedulers: schedule slip, DPRs, approvals, WIP, AR, quality, DLP."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from vaybooks.bms.application.schedulers.jobs._base import (
    BaseJob,
    Deps,
    Outcome,
    aging_bucket,
    business_date,
    cap,
    day_bucket,
    fmt_money,
    money,
    today_bounds,
    week_bucket,
)
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.domain.schedulers.entities import DOMAIN_PROJECTS
from vaybooks.bms.domain.schedulers.schedule import FREQ_WEEKDAYS, FREQ_WEEKLY
from vaybooks.bms.infrastructure.db.bson_utils import as_date

ACTIVE_PROJECT_STATUSES = ("Planned", "Active", "On Hold")
OPEN_ACTIVITY_STATUSES = ("Pending", "In Progress")
DLP_STATUSES = ("Physically Completed", "DLP")


def _status(value: Any) -> str:
    return getattr(value, "value", value) or ""


def _project(deps: Deps, project_id: str):
    repo = deps.repo("projects")
    if repo is None:
        return None
    try:
        return repo.find_by_id(project_id)
    except Exception:
        return None


def _project_recipient(deps: Deps, ctx: JobContext, project) -> str:
    """Project membership role, then project manager, then configured fallback."""
    if project is None:
        return ctx.config.fallback_user_id
    manager = getattr(project, "project_manager_id", "") or getattr(
        project, "manager_user_id", ""
    )
    if manager:
        return str(manager)
    memberships = deps.repo("project_memberships")
    if memberships is not None:
        try:
            members = memberships.list_by_project(getattr(project, "id", ""))
        except Exception:
            members = []
        for member in members or []:
            user_id = getattr(member, "user_id", "")
            if user_id:
                return str(user_id)
    return ctx.config.fallback_user_id


class ActivityEndSlipJob(BaseJob):
    job_id = "projects.activity_end_slip"
    domain = DOMAIN_PROJECTS
    title = "Activity planned-end slip"

    def identify(self, ctx: JobContext) -> List[str]:
        start, _ = today_bounds(ctx)
        boundary = start - timedelta(days=max(0, int(ctx.config.grace_days)))
        statuses = list(ACTIVE_PROJECT_STATUSES)
        if not ctx.option("include_on_hold", True):
            statuses = [s for s in statuses if s != "On Hold"]
        return self.deps.queries.project_activity_refs_overdue(
            statuses, OPEN_ACTIVITY_STATUSES, boundary, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        project_id, _, activity_id = candidate_id.partition("|")
        project = _project(self.deps, project_id)
        if project is None or _status(project.status) not in ACTIVE_PROJECT_STATUSES:
            return None
        activity = next(
            (
                a
                for a in (getattr(project, "activities", []) or [])
                if str(getattr(a, "id", "")) == activity_id
            ),
            None,
        )
        if activity is None or _status(activity.status) not in OPEN_ACTIVITY_STATUSES:
            return None
        planned_end = as_date(getattr(activity, "planned_end", None))
        if planned_end is None or planned_end >= business_date(ctx):
            return None
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Project activity has slipped",
            message=(
                f"{getattr(activity, 'name', activity_id)} on "
                f"{getattr(project, 'name', project_id)} was due "
                f"{planned_end.isoformat()}"
            ),
            ref_type="project_activity",
            ref_id=candidate_id,
        )


class ProjectEndOverdueJob(BaseJob):
    job_id = "projects.project_end_overdue"
    domain = DOMAIN_PROJECTS
    title = "Project expected end overdue"

    def identify(self, ctx: JobContext) -> List[str]:
        start, _ = today_bounds(ctx)
        return self.deps.queries.project_ids_end_overdue(
            ACTIVE_PROJECT_STATUSES, start, limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        project = _project(self.deps, candidate_id)
        if project is None or _status(project.status) not in ACTIVE_PROJECT_STATUSES:
            return None
        expected = as_date(getattr(project, "expected_end_date", None))
        if expected is None or expected >= business_date(ctx):
            return None
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Project is past its expected end",
            message=(
                f"{getattr(project, 'name', candidate_id)} was due "
                f"{expected.isoformat()}"
            ),
            ref_type="project",
            ref_id=candidate_id,
        )


class MissingDprJob(BaseJob):
    job_id = "projects.missing_dpr"
    domain = DOMAIN_PROJECTS
    title = "Missing daily progress report"

    def _target_day(self, ctx: JobContext) -> Optional[date]:
        lag = max(1, int(ctx.option("lag_business_days", 1) or 1))
        day = business_date(ctx)
        skip_weekends = bool(ctx.option("skip_weekends", True))
        steps = 0
        while steps < lag:
            day -= timedelta(days=1)
            if skip_weekends and day.weekday() >= 5:
                continue
            steps += 1
        if skip_weekends and day.weekday() >= 5:
            return None
        return day

    def identify(self, ctx: JobContext) -> List[str]:
        target = self._target_day(ctx)
        if target is None:
            return []
        active = self.deps.queries.project_ids_active(("Active",), limit=cap(ctx))
        if not active:
            return []
        filed = set(
            self.deps.queries.project_ids_with_dpr_on(
                active, target, ("Submitted", "Approved")
            )
        )
        self._target = target
        return [f"{pid}|{target.isoformat()}" for pid in active if pid not in filed]

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        project_id, _, day = candidate_id.partition("|")
        project = _project(self.deps, project_id)
        if project is None or _status(project.status) != "Active":
            return None
        created = as_date(getattr(project, "created_at", None))
        if created is not None and created.isoformat() >= day:
            return None
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Daily progress report is missing",
            message=f"No submitted DPR for {getattr(project, 'name', project_id)} on {day}",
            ref_type="project_dpr_missing",
            ref_id=candidate_id,
        )


class QuotationExpiringJob(BaseJob):
    job_id = "projects.quotation_expiring"
    domain = DOMAIN_PROJECTS
    title = "Project quotation expiry"

    def identify(self, ctx: JobContext) -> List[str]:
        offsets = [int(o) for o in (ctx.config.reminder_offsets_days or [7, 3, 0])]
        _, end = today_bounds(ctx)
        horizon = end + timedelta(days=max(offsets or [0]))
        return self.deps.queries.project_document_ids_date_before(
            "project_quotations",
            ("Approved", "Sent"),
            "valid_until",
            horizon,
            limit=cap(ctx),
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("project_quotations")
        quotation = repo.find_by_id(candidate_id) if repo else None
        if quotation is None or _status(quotation.status) not in ("Approved", "Sent"):
            return None
        valid_until = as_date(getattr(quotation, "valid_until", None))
        if valid_until is None:
            return None
        days_left = (valid_until - business_date(ctx)).days
        offsets = sorted(
            (int(o) for o in (ctx.config.reminder_offsets_days or [7, 3, 0])),
            reverse=True,
        )
        matched = next((o for o in offsets if days_left <= o), None)
        if matched is None:
            return None
        project = _project(self.deps, getattr(quotation, "project_id", "") or "")
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        state = "has expired" if days_left < 0 else f"expires in {days_left} day(s)"
        return Outcome(
            recipient_id=recipient,
            title=f"Project quotation {state}",
            message=(
                f"{getattr(quotation, 'quotation_number', candidate_id)} valid until "
                f"{valid_until.isoformat()}"
            ),
            ref_type="project_quotation",
            ref_id=f"{candidate_id}:{valid_until.isoformat()}:{matched}",
        )


class MaterialNeedByJob(BaseJob):
    job_id = "projects.material_need_by"
    domain = DOMAIN_PROJECTS
    title = "Material request need-by"

    def identify(self, ctx: JobContext) -> List[str]:
        _, end = today_bounds(ctx)
        horizon = end + timedelta(days=max(0, int(ctx.config.warning_days or 3)))
        return self.deps.queries.project_document_ids_date_before(
            "project_material_requests",
            ("Submitted", "Approved"),
            "need_by",
            horizon,
            limit=cap(ctx),
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        repo = self.deps.repo("project_procurement")
        request = None
        if repo is not None:
            for method in ("find_material_request", "get_material_request", "find_by_id"):
                fn = getattr(repo, method, None)
                if callable(fn):
                    try:
                        request = fn(candidate_id)
                        break
                    except Exception:
                        continue
        if request is None or _status(getattr(request, "status", "")) not in (
            "Submitted",
            "Approved",
        ):
            return None
        need_by = as_date(getattr(request, "need_by", None))
        if need_by is None:
            return None
        project = _project(self.deps, getattr(request, "project_id", "") or "")
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        overdue = need_by < business_date(ctx)
        return Outcome(
            recipient_id=recipient,
            title="Material request " + ("is overdue" if overdue else "is due soon"),
            message=(
                f"{getattr(request, 'request_number', candidate_id)} needed by "
                f"{need_by.isoformat()}"
            ),
            ref_type="project_material_request",
            ref_id=f"{candidate_id}:{need_by.isoformat()}",
        )


# Approval sources: collection -> (label, pending statuses)
_APPROVAL_SOURCES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "project_quotations": ("Quotation", ("Pending Approval",)),
    "project_ra_bills": ("RA bill", ("Submitted",)),
    "project_budget_headers": ("Budget", ("Submitted",)),
    "project_material_requests": ("Material request", ("Submitted",)),
    "project_dprs": ("Daily progress report", ("Submitted",)),
    "project_measurements": ("Measurement", ("Submitted", "Engineer Verified")),
    "project_variations": ("Variation", ("Submitted", "Internally Approved")),
}


class PendingApprovalsJob(BaseJob):
    job_id = "projects.pending_approvals"
    domain = DOMAIN_PROJECTS
    title = "Project approvals aging"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = ctx.now - timedelta(days=max(1, int(ctx.config.threshold_days or 2)))
        limit = cap(ctx)
        out: List[str] = []
        for collection, (_, statuses) in _APPROVAL_SOURCES.items():
            try:
                ids = self.deps.queries.project_document_ids_by_status(
                    collection, statuses, "updated_at", boundary, limit=limit
                )
            except Exception:
                ids = []
            out.extend(f"{collection}|{i}" for i in ids)
            if len(out) >= limit:
                break
        return out[:limit]

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        collection, _, document_id = candidate_id.partition("|")
        label, _statuses = _APPROVAL_SOURCES.get(collection, ("Document", ()))
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title=f"{label} awaits approval",
            message=f"{label} {document_id} has been pending for review",
            ref_type=collection,
            ref_id=document_id,
        )


class UnbilledWorkJob(BaseJob):
    job_id = "projects.unbilled_work"
    domain = DOMAIN_PROJECTS
    title = "Unbilled WIP"

    def identify(self, ctx: JobContext) -> List[str]:
        return self.deps.queries.project_ids_active(
            ("Active", "Physically Completed"), limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        reports = self.deps.service("reports_projects")
        if reports is None:
            return None
        try:
            payload = reports.wip_unbilled(candidate_id) or {}
        except Exception:
            return None
        unbilled = money(payload.get("unbilled_cost") or payload.get("unbilled") or 0)
        if unbilled <= 0:
            return None
        project = _project(self.deps, candidate_id)
        contract = money(getattr(project, "contract_value", 0)) if project else 0.0
        floor = float(ctx.option("absolute_floor", 50000) or 0)
        percent = float(ctx.option("contract_percent", 10) or 0) / 100.0
        threshold = max(floor, contract * percent)
        if unbilled < threshold:
            return None
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Unbilled work in progress",
            message=(
                f"{getattr(project, 'name', candidate_id)} has "
                f"{fmt_money(unbilled)} of unbilled cost"
            ),
            ref_type="project_wip",
            ref_id=f"{candidate_id}:{week_bucket(business_date(ctx))}",
            metadata={"unbilled": unbilled},
        )


class ArRetentionJob(BaseJob):
    job_id = "projects.ar_retention"
    domain = DOMAIN_PROJECTS
    title = "Project AR and retention"

    def identify(self, ctx: JobContext) -> List[str]:
        return self.deps.queries.project_ids_active(
            ("Active", "Physically Completed", "DLP"), limit=cap(ctx)
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        reports = self.deps.service("reports_projects")
        if reports is None:
            return None
        try:
            payload = reports.customer_outstanding(candidate_id) or {}
        except Exception:
            return None
        outstanding = max(0.0, money(payload.get("outstanding") or payload.get("total") or 0))
        if outstanding <= float(ctx.config.minimum_amount or 1.0):
            return None
        project = _project(self.deps, candidate_id)
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Project receivable is outstanding",
            message=(
                f"{getattr(project, 'name', candidate_id)} has "
                f"{fmt_money(outstanding)} outstanding"
            ),
            ref_type="project_ar",
            ref_id=f"{candidate_id}:{week_bucket(business_date(ctx))}",
            metadata={"outstanding": outstanding},
        )


class OpenQualityJob(BaseJob):
    job_id = "projects.open_quality"
    domain = DOMAIN_PROJECTS
    title = "Open snags and quality issues"

    def identify(self, ctx: JobContext) -> List[str]:
        boundary = ctx.now - timedelta(days=max(1, int(ctx.config.threshold_days or 7)))
        return self.deps.queries.project_document_ids_by_status(
            "project_quality_issues",
            ("Open", "In Progress"),
            "raised_date",
            boundary,
            limit=cap(ctx),
        )

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        recipient = ctx.config.fallback_user_id
        if not recipient:
            return None
        return Outcome(
            recipient_id=recipient,
            title="Quality issue is still open",
            message=f"Issue {candidate_id} has been open beyond the threshold",
            ref_type="project_quality_issue",
            ref_id=candidate_id,
        )


class DlpWarrantyJob(BaseJob):
    job_id = "projects.dlp_warranty"
    domain = DOMAIN_PROJECTS
    title = "Defect liability window"

    def identify(self, ctx: JobContext) -> List[str]:
        return self.deps.queries.project_ids_dlp_candidates(DLP_STATUSES, limit=cap(ctx))

    def describe(self, ctx: JobContext, candidate_id: str) -> Optional[Outcome]:
        project = _project(self.deps, candidate_id)
        if project is None or _status(project.status) not in DLP_STATUSES:
            return None
        months = int(getattr(project, "dlp_months", 0) or 0)
        if months <= 0:
            return None
        completed = as_date(getattr(project, "physically_completed_at", None))
        dlp_end = as_date(getattr(project, "dlp_end_date", None))
        if dlp_end is None and completed is not None:
            dlp_end = completed + timedelta(days=30 * months)
        recipient = _project_recipient(self.deps, ctx, project)
        if not recipient:
            return None
        today = business_date(ctx)
        if _status(project.status) == "Physically Completed":
            kind, headline = "entry", "Project is ready to enter DLP"
        elif dlp_end is not None and dlp_end < today:
            kind, headline = "closure", "DLP has ended; closure review needed"
        elif (
            dlp_end is not None
            and (dlp_end - today).days <= max(1, int(ctx.config.warning_days or 30))
        ):
            kind, headline = "warning", "DLP ends soon"
        else:
            return None
        return Outcome(
            recipient_id=recipient,
            title=headline,
            message=(
                f"{getattr(project, 'name', candidate_id)} — DLP end "
                f"{dlp_end.isoformat() if dlp_end else 'unknown'}"
            ),
            ref_type="project_dlp",
            ref_id=f"{candidate_id}:{kind}:{day_bucket(dlp_end)}",
        )


def project_jobs(deps: Deps) -> List[Tuple[Any, JobDefinition]]:
    return [
        (
            ActivityEndSlipJob(deps),
            JobDefinition(
                job_id=ActivityEndSlipJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=ActivityEndSlipJob.title,
                description="Flag project activities past their planned end date.",
                grace_days=0,
                create_activity=False,
                options={"include_on_hold": True},
                rule_fields=["grace_days", "include_on_hold"],
            ),
        ),
        (
            ProjectEndOverdueJob(deps),
            JobDefinition(
                job_id=ProjectEndOverdueJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=ProjectEndOverdueJob.title,
                description="Notify project managers about overdue projects.",
                create_activity=False,
            ),
        ),
        (
            MissingDprJob(deps),
            JobDefinition(
                job_id=MissingDprJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=MissingDprJob.title,
                description="Chase site engineers for unfiled daily progress reports.",
                frequency=FREQ_WEEKDAYS,
                time_of_day="09:00",
                create_activity=False,
                options={"lag_business_days": 1, "skip_weekends": True},
                rule_fields=["lag_business_days", "skip_weekends"],
            ),
        ),
        (
            QuotationExpiringJob(deps),
            JobDefinition(
                job_id=QuotationExpiringJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=QuotationExpiringJob.title,
                description="Warn commercial approvers about expiring project quotations.",
                reminder_offsets_days=[7, 3, 0],
                create_activity=False,
                rule_fields=["reminder_offsets_days"],
            ),
        ),
        (
            MaterialNeedByJob(deps),
            JobDefinition(
                job_id=MaterialNeedByJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=MaterialNeedByJob.title,
                description="Alert procurement about approaching material need-by dates.",
                warning_days=3,
                create_activity=False,
                rule_fields=["warning_days"],
            ),
        ),
        (
            PendingApprovalsJob(deps),
            JobDefinition(
                job_id=PendingApprovalsJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=PendingApprovalsJob.title,
                description="Escalate project documents waiting on approval.",
                frequency=FREQ_WEEKDAYS,
                threshold_days=2,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            UnbilledWorkJob(deps),
            JobDefinition(
                job_id=UnbilledWorkJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=UnbilledWorkJob.title,
                description="Surface projects carrying significant unbilled cost.",
                frequency=FREQ_WEEKLY,
                create_activity=False,
                options={"absolute_floor": 50000, "contract_percent": 10},
                rule_fields=["absolute_floor", "contract_percent"],
            ),
        ),
        (
            ArRetentionJob(deps),
            JobDefinition(
                job_id=ArRetentionJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=ArRetentionJob.title,
                description="Chase project receivables and held retention.",
                minimum_amount=1.0,
                create_activity=False,
                options={"retention_hold_days": 30},
                rule_fields=["minimum_amount", "retention_hold_days"],
            ),
        ),
        (
            OpenQualityJob(deps),
            JobDefinition(
                job_id=OpenQualityJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=OpenQualityJob.title,
                description="Chase snags that stay open past the threshold.",
                threshold_days=7,
                create_activity=False,
                rule_fields=["threshold_days"],
            ),
        ),
        (
            DlpWarrantyJob(deps),
            JobDefinition(
                job_id=DlpWarrantyJob.job_id,
                domain=DOMAIN_PROJECTS,
                title=DlpWarrantyJob.title,
                description="Track DLP entry, the warning window, and closure review.",
                frequency=FREQ_WEEKLY,
                warning_days=30,
                create_activity=False,
                rule_fields=["warning_days"],
            ),
        ),
    ]
