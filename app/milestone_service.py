"""Evidence-based milestone scoring, completion gates, and audit workflow."""

from datetime import date, datetime, timedelta
import json
import re

from app import db
from app.models import (
    CommissioningForm, DailySiteReport, DeliveryNoteForm, Document,
    HandoverForm, LoadAssessmentForm, MilestoneAuditLog,
    MilestoneDocumentRequirement, ProjectIssue, ProjectMilestone,
    SiteSurveyForm, TestingForm,
)


COMPLETED_MILESTONE_STATUSES = {"Completed", "Completed with Exception"}
APPROVED_RECORD_STATUSES = {"Approved", "Closed", "Completed"}
MATERIAL_COMPLETE_STATUSES = {"Issued", "Closed"}
MATERIAL_SCORES = {
    "Draft": 0, "Submitted": 20, "Approved": 50,
    "Partially Issued": 80, "Issued": 100, "Closed": 100,
    "Returned": 75, "Cancelled": 0,
}
DOCUMENT_SCORES = {
    "Draft": 20, "Submitted": 50, "Under Review": 65,
    "Need Correction": 35, "Approved": 100, "Closed": 100,
    "Completed": 100, "Rejected": 0,
}
FORM_MODELS = {
    "site-survey": SiteSurveyForm,
    "load-assessment": LoadAssessmentForm,
    "daily-site-report": DailySiteReport,
    "delivery-note": DeliveryNoteForm,
    "testing": TestingForm,
    "commissioning": CommissioningForm,
    "handover": HandoverForm,
}
FORM_RELATIONSHIPS = {
    "site-survey": "site_surveys",
    "load-assessment": "load_assessments",
    "daily-site-report": "daily_reports",
    "delivery-note": "delivery_notes",
    "testing": "testing_forms",
    "commissioning": "commissioning_forms",
    "handover": "handover_forms",
}


DEFAULT_MILESTONES = (
    {
        "code": "SURVEY", "name": "Survey & Assessment", "project_weight": 10,
        "physical_weight": 20, "procurement_weight": 0, "document_weight": 80,
        "requirements": (("Approved site survey & load assessment", "site-survey", None, True),),
    },
    {
        "code": "DESIGN", "name": "Design & Approval", "project_weight": 15,
        "physical_weight": 10, "procurement_weight": 10, "document_weight": 80,
        "requirements": (
            ("Approved technical design", None, "Technical Design", True),
            ("Approved bill of quantities", None, "BOQ", True),
        ),
    },
    {
        "code": "PROCUREMENT", "name": "Procurement", "project_weight": 20,
        "physical_weight": 0, "procurement_weight": 80, "document_weight": 20,
        "requirements": (("Approved delivery note", "delivery-note", None, True),),
    },
    {
        "code": "INSTALLATION", "name": "Installation", "project_weight": 35,
        "physical_weight": 75, "procurement_weight": 20, "document_weight": 5,
        "requires_daily_report": True,
        "requirements": (("Approved installation daily report", "daily-site-report", None, True),),
    },
    {
        "code": "TESTING", "name": "Testing & Commissioning", "project_weight": 15,
        "physical_weight": 60, "procurement_weight": 10, "document_weight": 30,
        "requires_daily_report": True,
        "requirements": (
            ("Approved testing form", "testing", None, True),
            ("Approved commissioning form", "commissioning", None, True),
        ),
    },
    {
        "code": "HANDOVER", "name": "Handover", "project_weight": 5,
        "physical_weight": 20, "procurement_weight": 0, "document_weight": 80,
        "requirements": (
            ("Approved handover form", "handover", None, True),
            ("Approved warranty document", None, "Warranty Document", True),
        ),
    },
)


def _clamp(value):
    return max(0, min(100, int(round(value or 0))))


def mark_milestone_started(milestone_id):
    """Move a gate into active work when an operational record is attached."""
    if not milestone_id:
        return None
    milestone = db.session.get(ProjectMilestone, int(milestone_id))
    if milestone and milestone.status == "Not Started":
        milestone.status = "In Progress"
        milestone.updated_at = datetime.utcnow()
    return milestone


def _number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _record_sort_key(record):
    return (
        getattr(record, "report_date", None) or date.min,
        getattr(record, "created_at", None) or getattr(record, "upload_date", None) or datetime.min,
        getattr(record, "id", 0) or 0,
    )


def ensure_default_milestones(project, actor_id=None):
    """Add the standard six-gate template. Caller owns the transaction."""
    if project.milestones:
        return sorted(project.milestones, key=lambda item: (item.sequence, item.id or 0))

    total_days = None
    if project.start_date and project.expected_completion_date and project.expected_completion_date >= project.start_date:
        total_days = max((project.expected_completion_date - project.start_date).days, 1)
    cumulative_weight = 0
    created = []
    for sequence, spec in enumerate(DEFAULT_MILESTONES, start=1):
        planned_start = planned_end = None
        if total_days is not None:
            planned_start = project.start_date + timedelta(days=round(total_days * cumulative_weight / 100))
            cumulative_weight += spec["project_weight"]
            planned_end = project.start_date + timedelta(days=round(total_days * cumulative_weight / 100))
        else:
            cumulative_weight += spec["project_weight"]
        milestone = ProjectMilestone(
            project=project,
            code=spec["code"],
            name=spec["name"],
            description=f"Evidence gate for {spec['name'].lower()}.",
            sequence=sequence,
            project_weight=spec["project_weight"],
            physical_weight=spec["physical_weight"],
            procurement_weight=spec["procurement_weight"],
            document_weight=spec["document_weight"],
            planned_start=planned_start,
            planned_end=planned_end,
            requires_daily_report=spec.get("requires_daily_report", False),
            status="Not Started",
        )
        db.session.add(milestone)
        db.session.flush()
        for title, form_key, document_type, critical in spec.get("requirements", ()):
            db.session.add(MilestoneDocumentRequirement(
                milestone_id=milestone.id,
                title=title,
                form_key=form_key,
                document_type=document_type,
                is_required=True,
                is_critical=critical,
            ))
        if actor_id:
            db.session.add(MilestoneAuditLog(
                milestone_id=milestone.id,
                action="Initialize",
                from_status=None,
                to_status="Not Started",
                user_id=actor_id,
                notes="Created from the standard six-milestone template.",
            ))
        created.append(milestone)
    return created


def _resolve_requirement(milestone, requirement):
    record = None
    source = "Not linked"
    if requirement.document_id:
        candidate = requirement.document
        if candidate and candidate.project_id == milestone.project_id:
            record, source = candidate, f"Document #{candidate.id}"
    elif requirement.form_key in FORM_RELATIONSHIPS:
        records = list(getattr(milestone.project, FORM_RELATIONSHIPS[requirement.form_key], []))
        if requirement.form_key == "daily-site-report":
            records = [item for item in records if item.milestone_id in (None, milestone.id)]
        if requirement.form_record_id:
            records = [item for item in records if item.id == requirement.form_record_id]
        if records:
            record = max(records, key=_record_sort_key)
            source = f"{requirement.form_key} #{record.id}"
    elif requirement.document_type:
        records = [
            item for item in milestone.project.documents
            if item.document_type == requirement.document_type
            and item.milestone_id in (None, milestone.id)
        ]
        if records:
            record = max(records, key=_record_sort_key)
            source = f"Document #{record.id}"

    status = getattr(record, "approval_status", None) if record else "Missing"
    return {
        "requirement": requirement,
        "record": record,
        "source": source,
        "status": status or "Draft",
        "progress": DOCUMENT_SCORES.get(status, 0),
        "approved": status in APPROVED_RECORD_STATUSES,
    }


def _component(name, weight, progress, source, records=0):
    return {
        "name": name,
        "weight": int(weight or 0),
        "applicable": int(weight or 0) > 0,
        "progress": None if int(weight or 0) <= 0 else _clamp(progress),
        "source": source,
        "records": records,
    }


def build_milestone_snapshot(milestone):
    tasks = [item for item in milestone.tasks if item.status != "Cancelled"]
    required_tasks = [item for item in tasks if item.milestone_required or item.milestone_critical]
    scored_tasks = required_tasks or tasks
    task_progress = (
        sum(_clamp(item.progress_percent) for item in scored_tasks) / len(scored_tasks)
        if scored_tasks else 0
    )
    approved_reports = [
        item for item in milestone.daily_reports
        if item.approval_status in APPROVED_RECORD_STATUSES
    ]
    latest_report = max(approved_reports, key=_record_sort_key) if approved_reports else None
    report_progress = _number(latest_report.progress_percentage) if latest_report else None
    if latest_report and tasks:
        physical_progress = (task_progress * 0.70) + (_clamp(report_progress) * 0.30)
        physical_source = "Linked tasks 70% + latest approved daily report 30%"
    elif tasks:
        physical_progress = task_progress
        physical_source = "Average progress of linked tasks"
    elif latest_report:
        physical_progress = _clamp(report_progress)
        physical_source = "Latest approved linked daily report"
    else:
        physical_progress = 0
        physical_source = "No linked task or approved daily evidence"

    material_requests = [item for item in milestone.material_requests if item.status != "Cancelled"]
    required_materials = [
        item for item in material_requests
        if item.milestone_required or item.milestone_critical
    ]
    scored_materials = required_materials or material_requests
    procurement_progress = (
        sum(MATERIAL_SCORES.get(item.status, 0) for item in scored_materials) / len(scored_materials)
        if scored_materials else 0
    )

    requirement_rows = [_resolve_requirement(milestone, item) for item in milestone.document_requirements]
    required_documents = [
        item for item in requirement_rows
        if item["requirement"].is_required or item["requirement"].is_critical
    ]
    scored_documents = required_documents or requirement_rows
    document_progress = (
        sum(item["progress"] for item in scored_documents) / len(scored_documents)
        if scored_documents else 0
    )

    components = {
        "physical": _component(
            "Physical", milestone.physical_weight, physical_progress,
            physical_source, len(tasks),
        ),
        "procurement": _component(
            "Procurement", milestone.procurement_weight, procurement_progress,
            "Status of material requests linked to this milestone", len(material_requests),
        ),
        "documents": _component(
            "Documents", milestone.document_weight, document_progress,
            "Approval status of required forms and documents", len(requirement_rows),
        ),
    }
    applicable_weight = sum(item["weight"] for item in components.values() if item["applicable"])
    raw_progress = _clamp(
        sum(item["progress"] * item["weight"] for item in components.values() if item["applicable"])
        / applicable_weight
    ) if applicable_weight else 0

    open_critical_issues = [
        item for item in milestone.project.issues
        if item.severity == "Critical"
        and item.status not in {"Resolved", "Closed"}
        and item.milestone_id in (None, milestone.id)
    ]
    project_weight_total = sum(int(item.project_weight or 0) for item in milestone.project.milestones)

    gates = []
    def gate(code, label, passed, detail):
        gates.append({"code": code, "label": label, "passed": bool(passed), "detail": detail})

    gate(
        "dimension_weights", "Applicable dimension weights total 100%",
        applicable_weight == 100,
        f"Configured total: {applicable_weight}% (0% means N/A).",
    )
    gate(
        "project_weights", "Project milestone weights total 100%",
        project_weight_total == 100,
        f"Configured total: {project_weight_total}%.",
    )
    if milestone.physical_weight:
        gate("task_plan", "Physical work plan exists", bool(tasks), f"{len(tasks)} linked task(s).")
        incomplete_tasks = [item for item in required_tasks if item.status != "Completed" or _clamp(item.progress_percent) < 100]
        gate(
            "required_tasks", "All required tasks are completed",
            bool(required_tasks) and not incomplete_tasks,
            f"{len(required_tasks) - len(incomplete_tasks)}/{len(required_tasks)} required task(s) complete.",
        )
    if milestone.requires_daily_report:
        gate(
            "daily_report", "Approved daily site evidence exists",
            latest_report is not None,
            f"Latest approved report: #{latest_report.id}." if latest_report else "No approved report linked to this milestone.",
        )
    if milestone.procurement_weight:
        gate("material_plan", "Procurement records exist", bool(material_requests), f"{len(material_requests)} linked request(s).")
        incomplete_materials = [item for item in required_materials if item.status not in MATERIAL_COMPLETE_STATUSES]
        gate(
            "required_materials", "All required materials are issued/closed",
            bool(required_materials) and not incomplete_materials,
            f"{len(required_materials) - len(incomplete_materials)}/{len(required_materials)} required request(s) fulfilled.",
        )
    if milestone.document_weight:
        gate("document_plan", "Document requirements are configured", bool(requirement_rows), f"{len(requirement_rows)} requirement(s).")
        missing_documents = [item for item in required_documents if not item["approved"]]
        gate(
            "required_documents", "All required documents/forms are approved",
            bool(required_documents) and not missing_documents,
            f"{len(required_documents) - len(missing_documents)}/{len(required_documents)} required record(s) approved.",
        )
    gate(
        "critical_issues", "No open critical issue blocks the gate",
        not open_critical_issues,
        f"{len(open_critical_issues)} open critical issue(s).",
    )
    gate("score", "Calculated milestone progress is 100%", raw_progress == 100, f"Current calculated score: {raw_progress}%.")

    blockers = [item for item in gates if not item["passed"]]
    effective_progress = 100 if milestone.status in COMPLETED_MILESTONE_STATUSES else raw_progress
    return {
        "model": milestone,
        "name": milestone.name,
        "status": milestone.status,
        "raw_progress": raw_progress,
        "progress": effective_progress,
        "components": components,
        "requirements": requirement_rows,
        "latest_report": latest_report,
        "gates": gates,
        "blockers": blockers,
        "ready": not blockers,
        "exception": milestone.status == "Completed with Exception",
        "task_count": len(tasks),
        "material_count": len(material_requests),
    }


def build_project_milestone_portfolio(project):
    milestones = sorted(project.milestones, key=lambda item: (item.sequence, item.id or 0))
    if not milestones:
        return {"configured": False, "milestones": [], "overall": 0, "dimensions": {}}
    snapshots = [build_milestone_snapshot(item) for item in milestones]
    project_weight = sum(max(0, int(item["model"].project_weight or 0)) for item in snapshots)
    overall = _clamp(
        sum(item["progress"] * max(0, int(item["model"].project_weight or 0)) for item in snapshots)
        / project_weight
    ) if project_weight else 0

    dimensions = {}
    for key in ("physical", "procurement", "documents"):
        applicable = [item for item in snapshots if item["components"][key]["applicable"]]
        weight = sum(max(0, int(item["model"].project_weight or 0)) for item in applicable)
        progress = _clamp(
            sum(item["components"][key]["progress"] * max(0, int(item["model"].project_weight or 0)) for item in applicable)
            / weight
        ) if weight else None
        dimensions[key] = {"applicable": bool(applicable), "progress": progress}

    current_assigned = False
    for item in snapshots:
        if item["status"] in COMPLETED_MILESTONE_STATUSES:
            item["state"] = "complete"
        elif not current_assigned:
            item["state"] = "current"
            current_assigned = True
        else:
            item["state"] = "upcoming"
    return {
        "configured": True,
        "milestones": snapshots,
        "overall": overall,
        "dimensions": dimensions,
        "project_weight_total": project_weight,
        "all_completed": all(item["status"] in COMPLETED_MILESTONE_STATUSES for item in snapshots),
        "exceptions": sum(1 for item in snapshots if item["exception"]),
    }


def _serializable_gate_snapshot(snapshot, action, reason=None):
    payload = {
        "captured_at": datetime.utcnow().isoformat(),
        "action": action,
        "score": snapshot["raw_progress"],
        "ready": snapshot["ready"],
        "gates": [
            {"code": item["code"], "label": item["label"], "passed": item["passed"], "detail": item["detail"]}
            for item in snapshot["gates"]
        ],
    }
    if reason:
        payload["reason"] = reason
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _audit(milestone, user, action, previous, target, notes=None):
    db.session.add(MilestoneAuditLog(
        milestone_id=milestone.id,
        action=action,
        from_status=previous,
        to_status=target,
        user_id=user.id,
        notes=notes,
    ))


def submit_milestone(milestone, user):
    snapshot = build_milestone_snapshot(milestone)
    previous = milestone.status
    milestone.submitted_by_id = user.id
    milestone.submitted_at = datetime.utcnow()
    milestone.gate_snapshot = _serializable_gate_snapshot(snapshot, "submit")
    if not snapshot["ready"]:
        milestone.status = "Blocked"
        notes = "; ".join(item["label"] for item in snapshot["blockers"])
        _audit(milestone, user, "Submit blocked", previous, milestone.status, notes)
        return False, snapshot
    milestone.status = "Ready for Approval"
    _audit(milestone, user, "Submit", previous, milestone.status, "All automatic completion gates passed.")
    return True, snapshot


def approve_milestone(milestone, user):
    snapshot = build_milestone_snapshot(milestone)
    if milestone.status != "Ready for Approval":
        return False, snapshot, "Milestone must be submitted before approval."
    if milestone.submitted_by_id == user.id:
        return False, snapshot, "The submitter cannot approve the same milestone."
    if not snapshot["ready"]:
        previous = milestone.status
        milestone.status = "Blocked"
        _audit(milestone, user, "Approval blocked", previous, milestone.status, "Records changed after submission; gates no longer pass.")
        return False, snapshot, "Records changed and one or more completion gates no longer pass."
    previous = milestone.status
    milestone.status = "Completed"
    milestone.approved_by_id = user.id
    milestone.approved_at = datetime.utcnow()
    milestone.gate_snapshot = _serializable_gate_snapshot(snapshot, "approve")
    _audit(milestone, user, "Approve", previous, milestone.status, "Completion approved after gate revalidation.")
    _sync_project_status(milestone.project)
    return True, snapshot, "Milestone approved and completed."


def override_milestone(milestone, user, reason):
    reason = (reason or "").strip()
    snapshot = build_milestone_snapshot(milestone)
    if len(reason) < 15:
        return False, snapshot, "Override reason must be at least 15 characters."
    previous = milestone.status
    milestone.status = "Completed with Exception"
    milestone.override_by_id = user.id
    milestone.override_at = datetime.utcnow()
    milestone.override_reason = reason
    milestone.gate_snapshot = _serializable_gate_snapshot(snapshot, "override", reason)
    _audit(milestone, user, "Emergency override", previous, milestone.status, reason)
    _sync_project_status(milestone.project)
    return True, snapshot, "Milestone completed with an audited exception."


def reopen_milestone(milestone, user, reason):
    reason = (reason or "").strip()
    if len(reason) < 10:
        return False, "Reopen reason must be at least 10 characters."
    previous = milestone.status
    milestone.status = "In Progress"
    milestone.approved_by_id = None
    milestone.approved_at = None
    _audit(milestone, user, "Reopen", previous, milestone.status, reason)
    if milestone.project.status == "Completed":
        milestone.project.status = "Handover"
    return True, "Milestone reopened."


def project_completion_ready(project):
    portfolio = build_project_milestone_portfolio(project)
    return bool(
        portfolio["configured"]
        and portfolio["project_weight_total"] == 100
        and portfolio["all_completed"]
    )


def _sync_project_status(project):
    if project_completion_ready(project):
        project.status = "Completed"
