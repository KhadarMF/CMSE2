"""Company-wide, read-only metrics for Dashboard Command Center V5.

The general dashboard is a portfolio view; the existing Project Command
Center remains the detailed source for one project.  This module aggregates
those project snapshots so every number continues to come from operational
records rather than a second, manually maintained dashboard table.
"""

from datetime import date, datetime

from flask import url_for

from app.models import (
    Branch,
    CommissioningForm,
    DailySiteReport,
    DeliveryNoteForm,
    Document,
    Employee,
    HandoverForm,
    LoadAssessmentForm,
    MaterialRequest,
    PaymentRequest,
    Project,
    ProjectIssue,
    ProjectTask,
    PROJECT_STATUSES,
    SiteSurveyForm,
    Team,
    TestingForm,
    WhatsAppMessage,
)
from app.permissions import can_access_module, has_any_permission
from app.project_command_center import build_project_command_center
from app.team_leader_access import assigned_projects_for_user, is_team_leader


FORM_MODELS = (
    SiteSurveyForm,
    LoadAssessmentForm,
    DailySiteReport,
    DeliveryNoteForm,
    TestingForm,
    CommissioningForm,
    HandoverForm,
)
PENDING_APPROVALS = {"Submitted", "Under Review", "Need Correction"}
OPEN_TASK_STATUSES = {"Not Started", "In Progress", "Waiting"}
OPEN_ISSUE_STATUSES = {"Open", "In Progress"}
OPEN_MATERIAL_STATUSES = {"Draft", "Submitted", "Approved", "Partially Issued"}
OPEN_PAYMENT_STATUSES = {
    "Pending Manager Approval",
    "Pending Finance Approval",
    "Approved",
    "Partially Paid",
}
RISK_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _int_arg(args, name):
    try:
        return int(args.get(name)) if args.get(name) not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _date_arg(args, name, fallback):
    try:
        return datetime.strptime(args.get(name, ""), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback


def _average(values):
    values = list(values)
    return round(sum(values) / len(values)) if values else 0


def _percent(numerator, denominator):
    if not denominator:
        return 0
    return max(0, min(100, round((numerator / denominator) * 100)))


def _project_branch_ids(project, teams_by_name):
    branch_ids = {
        assignment.team.branch_id
        for assignment in project.team_assignments
        if assignment.team and assignment.team.branch_id
    }
    if project.creator and project.creator.branch_id:
        branch_ids.add(project.creator.branch_id)
    legacy_team = teams_by_name.get((project.assigned_team or "").strip().lower())
    if legacy_team and legacy_team.branch_id:
        branch_ids.add(legacy_team.branch_id)
    return branch_ids


def _portfolio_projects(user):
    if is_team_leader(user) and str(user.role or "").strip().lower() == "team leader":
        return assigned_projects_for_user(user), "My assigned projects"
    return Project.query.order_by(Project.project_name.asc()).all(), "All company projects"


def _permission_flags(user):
    role = str(getattr(user, "role", "") or "").strip().lower()
    leader = is_team_leader(user)
    flags = {
        "projects": can_access_module(user, "projects", "view"),
        "documents": can_access_module(user, "documents", "view"),
        "forms": can_access_module(user, "forms-home", "view") or leader,
        "tasks": can_access_module(user, "project-tasks", "view"),
        "issues": can_access_module(user, "issues-risks", "view"),
        "materials": has_any_permission(
            user,
            [
                "materials",
                "material-items",
                "material-request",
                "material-issue",
                "material-return",
                "material-reports",
            ],
        ),
        "payments": can_access_module(user, "payment-requests", "view") or leader,
        "accounting": can_access_module(user, "accounting", "view"),
        "whatsapp": can_access_module(user, "whatsapp-integration", "view") or role == "admin",
    }
    flags["finance"] = (
        role in {"admin", "management", "finance officer"}
        or flags["accounting"]
    )
    return flags


def _scoped_query(model, project_ids):
    if not project_ids:
        return model.query.filter(model.project_id == -1)
    return model.query.filter(model.project_id.in_(project_ids))


def _form_counts(project_ids):
    result = {"total": 0, "pending": 0, "approved": 0, "rejected": 0}
    for model in FORM_MODELS:
        query = _scoped_query(model, project_ids)
        result["total"] += query.count()
        result["pending"] += query.filter(model.approval_status.in_(PENDING_APPROVALS)).count()
        result["approved"] += query.filter_by(approval_status="Approved").count()
        result["rejected"] += query.filter_by(approval_status="Rejected").count()
    return result


def _link_or_dashboard(allowed, endpoint, anchor=None, **values):
    if allowed:
        return url_for(endpoint, **values)
    target = url_for("dashboard.dashboard")
    return f"{target}#{anchor}" if anchor else target


def _build_links(flags):
    return {
        "projects": _link_or_dashboard(flags["projects"], "projects.list_projects", "portfolio"),
        "active_projects": _link_or_dashboard(
            flags["projects"], "projects.list_projects", "portfolio", active="1"
        ),
        "completed_projects": _link_or_dashboard(
            flags["projects"], "projects.list_projects", "portfolio", status="Completed"
        ),
        "documents_pending": _link_or_dashboard(
            flags["documents"], "documents.list_documents", "approvals", status="Submitted"
        ),
        "documents_rejected": _link_or_dashboard(
            flags["documents"], "documents.list_documents", "approvals", status="Rejected"
        ),
        "forms": _link_or_dashboard(flags["forms"], "forms.forms_home", "approvals"),
        "daily_reports": _link_or_dashboard(
            flags["forms"], "forms.list_forms", "operations", form_key="daily-site-report"
        ),
        "tasks": _link_or_dashboard(flags["tasks"], "project_tasks.list_tasks", "attention"),
        "overdue_tasks": _link_or_dashboard(
            flags["tasks"], "project_tasks.list_tasks", "attention", overdue="1"
        ),
        "issues": _link_or_dashboard(flags["issues"], "issues.list_issues", "attention"),
        "critical_issues": _link_or_dashboard(
            flags["issues"], "issues.list_issues", "attention", severity="Critical"
        ),
        "materials": _link_or_dashboard(flags["materials"], "materials.dashboard", "operations"),
        "material_requests": _link_or_dashboard(
            flags["materials"], "materials.requests_list", "operations"
        ),
        "payments": _link_or_dashboard(flags["payments"], "payments.dashboard", "finance"),
        "pending_manager": _link_or_dashboard(
            flags["payments"], "payments.list_requests", "finance",
            status="Pending Manager Approval",
        ),
        "pending_finance": _link_or_dashboard(
            flags["payments"], "payments.list_requests", "finance",
            status="Pending Finance Approval",
        ),
        "whatsapp": _link_or_dashboard(flags["whatsapp"], "whatsapp.conversations"),
    }


def _executive_summary(kpis, finance, operations, approvals, data_quality, flags):
    sentences = [
        f"Portfolio progress is {kpis['overall_progress']}% across "
        f"{kpis['total_projects']} selected project(s)."
    ]
    if kpis["delayed_projects"]:
        sentences.append(
            f"{kpis['delayed_projects']} project(s) need schedule recovery attention."
        )
    else:
        sentences.append("No selected project is currently past its planned completion date.")
    if operations["critical_issues"]:
        sentences.append(
            f"There are {operations['critical_issues']} critical unresolved issue(s)."
        )
    if flags["finance"]:
        sentences.append(
            f"Committed cost is USD {finance['committed_cost']:,.2f}; "
            f"USD {finance['outstanding']:,.2f} remains outstanding."
        )

    actions = []
    if operations["overdue_tasks"]:
        actions.append(
            f"Assign recovery owners and dates to {operations['overdue_tasks']} overdue task(s)."
        )
    if operations["critical_issues"]:
        actions.append("Escalate critical issues before the next site milestone.")
    if operations["missing_daily_reports"]:
        actions.append(
            f"Collect today's report from {operations['missing_daily_reports']} active project(s)."
        )
    if operations["open_material_requests"]:
        actions.append(
            f"Review {operations['open_material_requests']} open material request(s)."
        )
    pending_approval_total = (
        approvals["documents_pending"]
        + approvals["forms_pending"]
        + approvals["payments_pending"]
    )
    if pending_approval_total:
        actions.append(f"Clear {pending_approval_total} pending approval item(s).")
    if data_quality["projects_missing_dates"]:
        actions.append(
            f"Add schedule dates to {data_quality['projects_missing_dates']} project(s) for reliable forecasting."
        )
    if not actions:
        actions.append("Maintain daily reports, task progress, approvals, and risk ownership.")

    return {"summary": " ".join(sentences), "actions": actions[:5]}


def build_dashboard_command_center(user, args):
    as_of = _date_arg(args, "as_of", date.today())
    selected_project_id = _int_arg(args, "project_id")
    selected_branch_id = _int_arg(args, "branch_id")
    selected_status = (args.get("status") or "").strip()
    if selected_status not in PROJECT_STATUSES:
        selected_status = ""

    all_projects, scope_label = _portfolio_projects(user)
    project_options = list(all_projects)
    branches = Branch.query.filter_by(is_active=True).order_by(Branch.branch_name.asc()).all()
    teams_by_name = {
        team.team_name.strip().lower(): team
        for team in Team.query.all()
        if team.team_name
    }

    projects = []
    for project in all_projects:
        if selected_project_id and project.id != selected_project_id:
            continue
        if selected_status and project.status != selected_status:
            continue
        if selected_branch_id and selected_branch_id not in _project_branch_ids(
            project, teams_by_name
        ):
            continue
        projects.append(project)

    flags = _permission_flags(user)
    links = _build_links(flags)
    rows = []
    for project in projects:
        snapshot = build_project_command_center(project, today=as_of)
        financial = snapshot["financials"]
        schedule = snapshot["schedule"]
        financial_progress = _percent(financial["paid_cost"], financial["committed_cost"])
        last_report = snapshot["physical"]["latest_report"]
        rows.append(
            {
                "project": project,
                "overall": snapshot["overall"],
                "physical": snapshot["physical"]["progress"],
                "financial_progress": financial_progress,
                "revenue": financial["revenue"],
                "committed_cost": financial["committed_cost"],
                "paid_cost": financial["paid_cost"],
                "outstanding": financial["outstanding"],
                "profit": financial["profit"],
                "procurement": snapshot["procurement"]["progress"],
                "documents": snapshot["documents"]["progress"],
                "risk": snapshot["risks"]["level"],
                "open_issues": snapshot["risks"]["open_count"],
                "overdue_tasks": snapshot["physical"]["overdue_tasks"],
                "is_delayed": bool(
                    schedule["is_overdue"]
                    or (
                        snapshot["forecast"]["variance"] is not None
                        and snapshot["forecast"]["variance"] < -10
                    )
                ),
                "days_remaining": schedule["days_remaining"],
                "health_score": snapshot["forecast"]["health_score"],
                "last_report_date": last_report.report_date if last_report else None,
                "url": (
                    url_for("projects.detail", project_id=project.id)
                    if flags["projects"]
                    else f"{url_for('dashboard.dashboard')}#portfolio"
                ),
                "snapshot": snapshot,
            }
        )
    rows.sort(
        key=lambda row: (
            RISK_ORDER.get(row["risk"], 9),
            not row["is_delayed"],
            row["project"].project_name.lower(),
        )
    )

    project_ids = [project.id for project in projects]
    active_projects = [project for project in projects if project.status != "Completed"]
    finance = {
        "revenue": sum(row["revenue"] for row in rows),
        "committed_cost": sum(row["committed_cost"] for row in rows),
        "paid_cost": sum(row["paid_cost"] for row in rows),
        "outstanding": sum(row["outstanding"] for row in rows),
        "profit": sum(row["profit"] for row in rows),
    }
    finance["payment_progress"] = _percent(
        finance["paid_cost"], finance["committed_cost"]
    )
    finance["margin"] = (
        round((finance["profit"] / finance["revenue"]) * 100, 1)
        if finance["revenue"]
        else None
    )

    task_query = _scoped_query(ProjectTask, project_ids)
    open_tasks_query = task_query.filter(ProjectTask.status.in_(OPEN_TASK_STATUSES))
    open_tasks = open_tasks_query.all()
    overdue_tasks = [task for task in open_tasks if task.due_date and task.due_date < as_of]
    upcoming_tasks = sorted(
        open_tasks,
        key=lambda task: (task.due_date or date.max, task.created_at or datetime.min),
    )[:8]

    issue_query = _scoped_query(ProjectIssue, project_ids).filter(
        ProjectIssue.status.in_(OPEN_ISSUE_STATUSES)
    )
    open_issues = issue_query.all()
    critical_issues = [issue for issue in open_issues if issue.severity == "Critical"]

    material_query = _scoped_query(MaterialRequest, project_ids)
    open_material_requests = material_query.filter(
        MaterialRequest.status.in_(OPEN_MATERIAL_STATUSES)
    ).count()

    reports_today = (
        _scoped_query(DailySiteReport, project_ids)
        .filter(DailySiteReport.report_date == as_of)
        .with_entities(DailySiteReport.project_id)
        .distinct()
        .count()
    )
    operations = {
        "open_tasks": len(open_tasks),
        "overdue_tasks": len(overdue_tasks),
        "open_issues": len(open_issues),
        "critical_issues": len(critical_issues),
        "open_material_requests": open_material_requests,
        "missing_daily_reports": max(0, len(active_projects) - reports_today),
        "reports_today": reports_today,
        "active_employees": Employee.query.filter_by(status="Active").count(),
        "active_teams": Team.query.filter_by(status="Active").count(),
    }

    document_query = _scoped_query(Document, project_ids)
    documents_pending = document_query.filter(
        Document.approval_status.in_(PENDING_APPROVALS)
    ).count()
    documents_rejected = document_query.filter_by(approval_status="Rejected").count()
    recent_documents = document_query.order_by(Document.upload_date.desc()).limit(8).all()
    forms = _form_counts(project_ids)

    payment_query = _scoped_query(PaymentRequest, project_ids)
    if is_team_leader(user) and not flags["finance"]:
        payment_query = payment_query.filter_by(requested_by_id=user.id)
    payment_records = payment_query.all()
    pending_manager = sum(
        1 for item in payment_records if item.status == "Pending Manager Approval"
    )
    pending_finance = sum(
        1 for item in payment_records if item.status == "Pending Finance Approval"
    )
    approved_unpaid = sum(
        1 for item in payment_records if item.status in {"Approved", "Partially Paid"}
    )
    approvals = {
        "documents_pending": documents_pending,
        "documents_rejected": documents_rejected,
        "forms_total": forms["total"],
        "forms_pending": forms["pending"],
        "forms_approved": forms["approved"],
        "forms_rejected": forms["rejected"],
        "pending_manager": pending_manager,
        "pending_finance": pending_finance,
        "approved_unpaid": approved_unpaid,
        "payments_pending": pending_manager + pending_finance,
    }

    whatsapp = {"unread": 0, "failed": 0, "total": 0}
    if flags["whatsapp"]:
        whatsapp = {
            "unread": WhatsAppMessage.query.filter_by(
                direction="Inbound", status="Received"
            ).count(),
            "failed": WhatsAppMessage.query.filter_by(status="Failed").count(),
            "total": WhatsAppMessage.query.count(),
        }

    kpis = {
        "total_projects": len(projects),
        "active_projects": len(active_projects),
        "completed_projects": sum(1 for project in projects if project.status == "Completed"),
        "delayed_projects": sum(1 for row in rows if row["is_delayed"]),
        "at_risk_projects": sum(1 for row in rows if row["risk"] in {"Critical", "High"}),
        "overall_progress": _average(row["overall"] for row in rows),
        "physical_progress": _average(row["physical"] for row in rows),
        "financial_progress": finance["payment_progress"],
        "procurement_progress": _average(row["procurement"] for row in rows),
        "document_progress": _average(row["documents"] for row in rows),
        "pending_approvals": documents_pending + forms["pending"] + pending_manager + pending_finance,
        "critical_issues": len(critical_issues),
    }

    status_distribution = []
    for status in PROJECT_STATUSES:
        count = sum(1 for project in projects if project.status == status)
        if count:
            status_distribution.append(
                {"status": status, "count": count, "percent": _percent(count, len(projects))}
            )

    data_quality = {
        "projects_missing_dates": sum(
            1
            for project in projects
            if not project.start_date or not project.expected_completion_date
        ),
        "projects_without_reports": sum(
            1 for row in rows if row["last_report_date"] is None
        ),
        "projects_without_revenue": sum(1 for row in rows if not row["revenue"]),
        "projects_without_team": sum(
            1
            for project in projects
            if not project.team_assignments and not project.assigned_team
        ),
    }

    attention = []
    attention_specs = [
        (operations["critical_issues"], "danger", "Critical issues", "Resolve or escalate immediately.", links["critical_issues"]),
        (operations["overdue_tasks"], "danger", "Overdue tasks", "Assign recovery owners and revised dates.", links["overdue_tasks"]),
        (kpis["delayed_projects"], "warning", "Delayed projects", "Review schedule variance in the portfolio.", f"{url_for('dashboard.dashboard')}#portfolio"),
        (operations["missing_daily_reports"], "warning", "Daily reports missing", f"Reports not recorded for {as_of.isoformat()}.", links["daily_reports"]),
        (approvals["payments_pending"], "warning", "Payment approvals", "Manager or Finance action is pending.", links["pending_manager"] if pending_manager else links["pending_finance"]),
        (approvals["documents_pending"] + approvals["forms_pending"], "info", "Document/form approvals", "Review submitted and correction items.", links["documents_pending"] if approvals["documents_pending"] else links["forms"]),
        (operations["open_material_requests"], "info", "Open material requests", "Confirm approval, issue, or procurement status.", links["material_requests"]),
        (whatsapp["failed"], "danger", "Failed WhatsApp messages", "Review delivery errors and retry when appropriate.", links["whatsapp"]),
    ]
    for count, tone, title, detail, target in attention_specs:
        if count:
            attention.append(
                {"count": count, "tone": tone, "title": title, "detail": detail, "url": target}
            )

    executive = _executive_summary(
        kpis, finance, operations, approvals, data_quality, flags
    )

    export_args = {"as_of": as_of.isoformat()}
    if selected_project_id:
        export_args["project_id"] = selected_project_id
    if selected_branch_id:
        export_args["branch_id"] = selected_branch_id
    if selected_status:
        export_args["status"] = selected_status

    return {
        "as_of": as_of,
        "scope_label": scope_label,
        "filters": {
            "project_id": selected_project_id,
            "branch_id": selected_branch_id,
            "status": selected_status,
        },
        "branches": branches,
        "project_options": project_options,
        "projects": projects,
        "portfolio": rows,
        "flags": flags,
        "links": links,
        "export_url": url_for("dashboard.export_csv", **export_args),
        "kpis": kpis,
        "finance": finance,
        "operations": operations,
        "approvals": approvals,
        "whatsapp": whatsapp,
        "status_distribution": status_distribution,
        "data_quality": data_quality,
        "attention": attention,
        "executive": executive,
        "upcoming_tasks": upcoming_tasks,
        "recent_documents": recent_documents,
    }
