"""Read-only project portfolio metrics used by the Project Command Center.

The command center deliberately derives its numbers from existing operational
records.  It adds no parallel source of truth and therefore needs no schema
migration.
"""
from datetime import date, datetime, timedelta
import re

from app.models import PROJECT_STATUSES, SalesQuotation


APPROVED_QUOTATION_STATUSES = {"Approved by Customer", "Converted to Project"}
APPROVED_STATUSES = {"Approved", "Closed", "Completed"}
INACTIVE_STATUSES = {"Cancelled", "Rejected"}
MATERIAL_STATUS_SCORES = {
    "Draft": 10,
    "Submitted": 30,
    "Approved": 55,
    "Partially Issued": 75,
    "Issued": 90,
    "Returned": 90,
    "Closed": 100,
}
FORM_GROUPS = (
    ("Site survey", "site_surveys", "site-survey"),
    ("Load assessment", "load_assessments", "load-assessment"),
    ("Daily site report", "daily_reports", "daily-site-report"),
    ("Delivery note", "delivery_notes", "delivery-note"),
    ("Testing", "testing_forms", "testing"),
    ("Commissioning", "commissioning_forms", "commissioning"),
    ("Handover", "handover_forms", "handover"),
)


def _clamp(value, low=0, high=100):
    return max(low, min(high, int(round(value or 0))))


def _number(value):
    """Extract a tolerant percentage-like number from legacy text fields."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _as_float(value):
    return float(value or 0)


def _latest_daily_report(project):
    approved_reports = [
        report for report in project.daily_reports
        if report.approval_status in APPROVED_STATUSES
    ]
    if not approved_reports:
        return None
    return max(
        approved_reports,
        key=lambda item: (item.report_date or date.min, item.created_at or datetime.min),
    )


def _milestones(project):
    try:
        current_index = PROJECT_STATUSES.index(project.status)
    except ValueError:
        current_index = 0

    last_index = max(len(PROJECT_STATUSES) - 1, 1)
    progress = _clamp((current_index / last_index) * 100)
    if project.status == "Completed":
        progress = 100

    rows = []
    for index, name in enumerate(PROJECT_STATUSES):
        if index < current_index or project.status == "Completed":
            state = "complete"
        elif index == current_index:
            state = "current"
        else:
            state = "upcoming"
        rows.append({"name": name, "state": state})
    return rows, progress


def _physical_progress(project, milestone_progress):
    tasks = [task for task in project.tasks if task.status != "Cancelled"]
    task_progress = None
    if tasks:
        task_progress = sum(_clamp(task.progress_percent) for task in tasks) / len(tasks)

    latest_report = _latest_daily_report(project)
    reported_progress = _number(latest_report.progress_percentage) if latest_report else None
    if reported_progress is not None and task_progress is not None:
        progress = (reported_progress * 0.6) + (task_progress * 0.4)
        source = "Latest site report + task completion"
    elif reported_progress is not None:
        progress = reported_progress
        source = "Latest approved site report"
    elif task_progress is not None:
        progress = task_progress
        source = "Average task completion"
    else:
        progress = milestone_progress
        source = "Project phase estimate; add tasks or a daily report for accuracy"

    completed = sum(1 for task in tasks if task.status == "Completed")
    overdue = sum(1 for task in tasks if task.is_overdue)
    active = sum(1 for task in tasks if task.status in {"In Progress", "Waiting"})
    return {
        "progress": _clamp(progress),
        "source": source,
        "latest_report": latest_report,
        "task_count": len(tasks),
        "completed_tasks": completed,
        "active_tasks": active,
        "overdue_tasks": overdue,
    }


def _schedule(project, today):
    start = project.start_date
    end = project.expected_completion_date
    if not start or not end or end <= start:
        return {
            "start": start,
            "end": end,
            "elapsed_percent": None,
            "days_remaining": None,
            "is_overdue": bool(end and end < today and project.status != "Completed"),
        }
    total_days = max((end - start).days, 1)
    elapsed_percent = _clamp(((today - start).days / total_days) * 100)
    return {
        "start": start,
        "end": end,
        "elapsed_percent": elapsed_percent,
        "days_remaining": (end - today).days,
        "is_overdue": end < today and project.status != "Completed",
    }


def _gantt(project, today):
    tasks = [task for task in project.tasks if task.status != "Cancelled"]
    dated_starts = [task.start_date for task in tasks if task.start_date]
    dated_ends = [task.due_date for task in tasks if task.due_date]
    start = project.start_date or (min(dated_starts) if dated_starts else today)
    end = project.expected_completion_date or (max(dated_ends) if dated_ends else start + timedelta(days=30))
    if end <= start:
        end = start + timedelta(days=30)
    span = max((end - start).days, 1)

    rows = []
    for task in sorted(tasks, key=lambda item: (item.start_date or start, item.due_date or end, item.id or 0)):
        task_start = task.start_date or start
        task_end = task.due_date or min(task_start + timedelta(days=7), end)
        if task_end < task_start:
            task_end = task_start
        left = _clamp(((task_start - start).days / span) * 100)
        right = _clamp(((task_end - start).days / span) * 100)
        width = max(2, right - left)
        if left + width > 100:
            width = max(2, 100 - left)
        rows.append({
            "task": task,
            "start": task_start,
            "end": task_end,
            "left": left,
            "width": width,
            "progress": _clamp(task.progress_percent),
        })

    today_marker = None
    if start <= today <= end:
        today_marker = _clamp(((today - start).days / span) * 100)
    return {"start": start, "end": end, "today_marker": today_marker, "rows": rows}


def _documents(project):
    form_rows = []
    form_records = []
    slot_scores = []
    for label, relationship, form_key in FORM_GROUPS:
        records = list(getattr(project, relationship))
        form_records.extend(records)
        approved = sum(1 for item in records if item.approval_status in APPROVED_STATUSES)
        if approved:
            state, score = "Approved", 100
        elif records:
            state, score = records[-1].approval_status or "In progress", 50
        else:
            state, score = "Missing", 0
        slot_scores.append(score)
        form_rows.append({
            "label": label,
            "form_key": form_key,
            "count": len(records),
            "approved": approved,
            "state": state,
        })

    uploaded = list(project.documents)
    all_records = form_records + uploaded
    approved_total = sum(1 for item in all_records if item.approval_status in APPROVED_STATUSES)
    attention_total = sum(
        1 for item in all_records if item.approval_status in {"Rejected", "Need Correction"}
    )
    form_progress = sum(slot_scores) / len(slot_scores)
    upload_progress = (
        (sum(1 for item in uploaded if item.approval_status in APPROVED_STATUSES) / len(uploaded)) * 100
        if uploaded else None
    )
    progress = form_progress if upload_progress is None else (form_progress * 0.7) + (upload_progress * 0.3)
    return {
        "progress": _clamp(progress),
        "form_rows": form_rows,
        "records": all_records,
        "total": len(all_records),
        "approved": approved_total,
        "attention": attention_total,
        "uploaded": len(uploaded),
        "recent_documents": sorted(uploaded, key=lambda item: item.upload_date or datetime.min, reverse=True)[:5],
    }


def _procurement(project):
    requests = [item for item in project.material_requests if item.status != "Cancelled"]
    progress = (
        sum(MATERIAL_STATUS_SCORES.get(item.status, 0) for item in requests) / len(requests)
        if requests else 0
    )
    requested_value = sum(_as_float(item.total_estimated_cost) for item in requests)
    issued_value = sum(_as_float(item.total_issue_cost) for item in project.material_issues)
    returned_value = sum(_as_float(item.total_return_cost) for item in project.material_returns)
    return {
        "progress": _clamp(progress),
        "requests": sorted(requests, key=lambda item: (item.request_date or date.min, item.created_at or date.min), reverse=True),
        "request_count": len(requests),
        "approved_count": sum(1 for item in requests if item.status in {"Approved", "Issued", "Partially Issued", "Closed"}),
        "issued_count": len(project.material_issues),
        "requested_value": requested_value,
        "issued_value": issued_value,
        "returned_value": returned_value,
        "net_material_cost": max(0, issued_value - returned_value),
    }


def _financials(project, procurement):
    quotations = SalesQuotation.query.filter_by(project_id=project.id).all()
    revenue = sum(
        _as_float(quotation.total_amount)
        for quotation in quotations
        if quotation.status in APPROVED_QUOTATION_STATUSES
    )

    active_requests = [item for item in project.payment_requests if item.status not in INACTIVE_STATUSES]
    usd_requests = [item for item in active_requests if (item.currency or "USD") == "USD"]
    slsh_requests = [item for item in active_requests if item.currency == "SLSH"]
    # Material payments are represented by net issued inventory below.  Excluding
    # linked/category material requests here prevents the same cost being counted twice.
    other_usd_requests = [
        item for item in usd_requests
        if not item.material_request_id and item.category != "Materials & Supplies"
    ]
    committed_payments = sum(_as_float(item.amount) for item in other_usd_requests)
    paid_payments = sum(_as_float(item.total_paid) for item in other_usd_requests)

    payroll_due = sum(_as_float(item.total_due) for item in project.payroll_entries)
    payroll_paid = sum(_as_float(item.total_paid) for item in project.payroll_entries)
    payroll_due += sum(_as_float(item.total_due) for item in project.project_payroll_batches)
    payroll_paid += sum(_as_float(item.total_paid) for item in project.project_payroll_batches)

    committed_cost = committed_payments + payroll_due + procurement["net_material_cost"]
    paid_cost = paid_payments + payroll_paid
    profit = revenue - committed_cost
    margin = (profit / revenue * 100) if revenue else None
    return {
        "revenue": revenue,
        "committed_cost": committed_cost,
        "paid_cost": paid_cost,
        "outstanding": max(0, committed_cost - paid_cost),
        "profit": profit,
        "margin": round(margin, 1) if margin is not None else None,
        "cost_percent": _clamp((committed_cost / revenue * 100) if revenue else 0),
        "payment_request_count": len(active_requests),
        "slsh_committed": sum(_as_float(item.amount) for item in slsh_requests),
        "slsh_paid": sum(_as_float(item.total_paid) for item in slsh_requests),
        "has_revenue": bool(revenue),
    }


def _risks(project, schedule, physical, procurement, documents):
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    open_issues = [item for item in project.issues if item.status not in {"Resolved", "Closed"}]
    open_issues.sort(key=lambda item: (severity_order.get(item.severity, 9), not item.is_overdue, item.target_resolution_date or date.max))
    critical = sum(1 for item in open_issues if item.severity == "Critical")
    high = sum(1 for item in open_issues if item.severity == "High")
    overdue = sum(1 for item in open_issues if item.is_overdue)

    if critical or (schedule["is_overdue"] and physical["progress"] < 90):
        level = "Critical"
    elif high or overdue or physical["overdue_tasks"]:
        level = "High"
    elif open_issues or procurement["progress"] < 40 or documents["attention"]:
        level = "Medium"
    else:
        level = "Low"
    return {
        "level": project.ai_risk_level or level,
        "open": open_issues,
        "open_count": len(open_issues),
        "critical_count": critical,
        "high_count": high,
        "overdue_count": overdue,
    }


def _forecast(project, overall, schedule, physical, procurement, documents, risks, financials):
    if schedule["elapsed_percent"] is None:
        schedule_message = "Add valid project start and completion dates to enable schedule forecasting."
        variance = None
    else:
        variance = overall - schedule["elapsed_percent"]
        if variance < -10:
            schedule_message = f"Delivery is trending {abs(variance)} points behind elapsed time."
        elif variance > 10:
            schedule_message = f"Delivery is trending {variance} points ahead of elapsed time."
        else:
            schedule_message = "Delivery is broadly aligned with elapsed project time."

    actions = []
    if physical["overdue_tasks"]:
        actions.append(f"Recover {physical['overdue_tasks']} overdue task(s) and confirm new owners/dates.")
    if risks["critical_count"] or risks["high_count"]:
        actions.append("Resolve critical/high risks before the next site milestone.")
    if procurement["progress"] < physical["progress"] - 10:
        actions.append("Procurement is trailing site progress; expedite outstanding material requests.")
    if documents["attention"]:
        actions.append(f"Correct or resubmit {documents['attention']} rejected document/form record(s).")
    if documents["progress"] < physical["progress"] - 15:
        actions.append("Bring approvals and site documentation up to date with physical work.")
    if financials["has_revenue"] and financials["margin"] is not None and financials["margin"] < 10:
        actions.append("Review committed costs; forecast margin is below 10%.")
    if not actions:
        actions.append("Maintain weekly updates to tasks, approvals, procurement, and risk owners.")

    summary = project.ai_project_summary or (
        f"Project is {overall}% complete with {physical['progress']}% physical progress. "
        f"There are {risks['open_count']} open issue(s), {physical['overdue_tasks']} overdue task(s), "
        f"and document readiness is {documents['progress']}%."
    )
    return {
        "summary": summary,
        "schedule_message": project.ai_delay_prediction or schedule_message,
        "variance": variance,
        "health_score": _clamp(
            _number(project.ai_health_score)
            if _number(project.ai_health_score) is not None
            else 100 - (risks["critical_count"] * 20) - (risks["high_count"] * 10) - (physical["overdue_tasks"] * 5)
        ),
        "actions": actions,
        "saved_actions": project.ai_recommended_actions,
        "last_analysis": project.ai_last_analysis,
    }


def build_project_command_center(project, today=None):
    """Return a template-friendly, read-only snapshot for one project."""
    today = today or date.today()
    milestones, milestone_progress = _milestones(project)
    physical = _physical_progress(project, milestone_progress)
    schedule = _schedule(project, today)
    documents = _documents(project)
    procurement = _procurement(project)
    financials = _financials(project, procurement)
    risks = _risks(project, schedule, physical, procurement, documents)
    overall = _clamp(
        (milestone_progress * 0.25)
        + (physical["progress"] * 0.35)
        + (procurement["progress"] * 0.20)
        + (documents["progress"] * 0.20)
    )
    forecast = _forecast(
        project, overall, schedule, physical, procurement, documents, risks, financials
    )
    return {
        "today": today,
        "overall": overall,
        "milestone_progress": milestone_progress,
        "milestones": milestones,
        "physical": physical,
        "schedule": schedule,
        "gantt": _gantt(project, today),
        "procurement": procurement,
        "documents": documents,
        "financials": financials,
        "risks": risks,
        "forecast": forecast,
    }
