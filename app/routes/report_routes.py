from collections import defaultdict
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required
from weasyprint import HTML

from app.models import Project, ProjectPayrollEntry, MaterialIssue, MaterialReturn, ProjectPayrollBatch, ProjectPayrollBatch
from app.routes.form_routes import FORM_CONFIG, build_display_rows

report_bp = Blueprint("reports", __name__, url_prefix="/reports")

FORM_REQUIREMENTS = [
    ("Site Survey", "site_surveys"),
    ("Load Assessment", "load_assessments"),
    ("Daily Site Report", "daily_reports"),
    ("Delivery Note", "delivery_notes"),
    ("Testing Form", "testing_forms"),
    ("Commissioning Form", "commissioning_forms"),
    ("Handover Form", "handover_forms"),
]

def safe_len(value):
    return len(value) if value is not None else 0

def status_count(records, attr_name="approval_status"):
    result = defaultdict(int)
    for record in records:
        result[getattr(record, attr_name, "Unknown") or "Unknown"] += 1
    return dict(result)

def project_checklist(project):
    items = []
    for label, rel in FORM_REQUIREMENTS:
        records = getattr(project, rel)
        count = safe_len(records)
        approved = len([r for r in records if getattr(r, "approval_status", "") == "Approved"])
        status = "Missing" if count == 0 else ("Approved" if approved > 0 else "Pending / Not Approved")
        items.append({"label": label, "count": count, "approved_count": approved, "status": status})

    dc = safe_len(project.documents)
    ad = len([d for d in project.documents if d.approval_status == "Approved"])
    items.append({
        "label": "Uploaded Documents",
        "count": dc,
        "approved_count": ad,
        "status": "Missing" if dc == 0 else ("Approved" if ad == dc else "Pending / Not Approved"),
    })

    ready = all(i["status"] == "Approved" for i in items)
    return items, ready

def project_report_data(project):
    checklist, ready = project_checklist(project)

    forms_summary = []
    total_forms = 0
    approved_forms = 0
    for label, rel in FORM_REQUIREMENTS:
        records = list(getattr(project, rel))
        counts = status_count(records)
        total_forms += len(records)
        approved_forms += counts.get("Approved", 0)
        forms_summary.append({
            "label": label,
            "total": len(records),
            "approved": counts.get("Approved", 0),
            "submitted": counts.get("Submitted", 0),
            "under_review": counts.get("Under Review", 0),
            "rejected": counts.get("Rejected", 0),
            "need_correction": counts.get("Need Correction", 0),
            "draft": counts.get("Draft", 0),
        })

    documents = sorted(project.documents, key=lambda d: d.upload_date or datetime.min, reverse=True)
    tasks = sorted(getattr(project, "tasks", []), key=lambda t: t.due_date or datetime.max.date())
    issues = sorted(getattr(project, "issues", []), key=lambda i: i.reported_at or datetime.min, reverse=True)

    open_tasks = [t for t in tasks if t.status not in ["Completed", "Cancelled"]]
    overdue_tasks = [t for t in tasks if t.is_overdue]
    open_issues = [i for i in issues if i.status not in ["Resolved", "Closed"]]
    critical_issues = [i for i in issues if i.severity == "Critical" and i.status not in ["Resolved", "Closed"]]

    payroll_entries = ProjectPayrollEntry.query.join(ProjectPayrollBatch).filter(ProjectPayrollBatch.project_id == project.id).all()

    material_issues = MaterialIssue.query.filter_by(project_id=project.id).all()
    material_returns = MaterialReturn.query.filter_by(project_id=project.id).all()

    summary = {
        "payroll_total_due": sum(e.total_due for e in payroll_entries),
        "payroll_total_paid": sum(e.total_paid for e in payroll_entries),
        "payroll_balance": sum(e.balance for e in payroll_entries),
        "payroll_employees": len({e.employee_id for e in payroll_entries}),
        "material_issue_cost": sum(i.total_issue_cost for i in material_issues),
        "material_return_cost": sum(r.total_return_cost for r in material_returns),
        "net_material_cost": sum(i.total_issue_cost for i in material_issues) - sum(r.total_return_cost for r in material_returns),
        "total_documents": len(documents),
        "approved_documents": len([d for d in documents if d.approval_status == "Approved"]),
        "total_forms": total_forms,
        "approved_forms": approved_forms,
        "total_tasks": len(tasks),
        "open_tasks": len(open_tasks),
        "overdue_tasks": len(overdue_tasks),
        "total_issues": len(issues),
        "open_issues": len(open_issues),
        "critical_issues": len(critical_issues),
    }

    return {
        "project": project,
        "checklist": checklist,
        "ready": ready,
        "forms_summary": forms_summary,
        "documents": documents,
        "tasks": tasks,
        "issues": issues,
        "summary": summary,
        "report_ref": f"PFR-{project.id:04d}-{datetime.utcnow().strftime('%Y%m%d')}",
        "payroll_entries": payroll_entries,
        "team_assignments": [a for a in getattr(project, "team_assignments", []) if a.status != "Removed"],
        "employee_assignments": [a for a in getattr(project, "employee_assignments", []) if a.status != "Removed"],
        "generated_at": datetime.utcnow(),
    }

def customer_report_data(customer_name):
    projects = Project.query.filter(Project.customer_name == customer_name).order_by(Project.created_at.desc()).all()
    totals = {
        "projects": len(projects),
        "completed": 0,
        "active": 0,
        "documents": 0,
        "approved_documents": 0,
        "forms": 0,
        "approved_forms": 0,
        "tasks": 0,
        "open_tasks": 0,
        "issues": 0,
        "open_issues": 0,
        "payroll_due": 0,
        "payroll_paid": 0,
        "payroll_balance": 0,
        "total_capacity_text": "",
    }

    project_rows = []
    for project in projects:
        data = project_report_data(project)
        summary = data["summary"]

        if project.status == "Completed":
            totals["completed"] += 1
        else:
            totals["active"] += 1

        totals["documents"] += summary["total_documents"]
        totals["approved_documents"] += summary["approved_documents"]
        totals["forms"] += summary["total_forms"]
        totals["approved_forms"] += summary["approved_forms"]
        totals["tasks"] += summary["total_tasks"]
        totals["open_tasks"] += summary["open_tasks"]
        totals["issues"] += summary["total_issues"]
        totals["open_issues"] += summary["open_issues"]
        totals["payroll_due"] += summary.get("payroll_total_due", 0)
        totals["payroll_paid"] += summary.get("payroll_total_paid", 0)
        totals["payroll_balance"] += summary.get("payroll_balance", 0)

        project_rows.append({
            "project": project,
            "ready": data["ready"],
            "summary": summary,
        })

    return {
        "customer_name": customer_name,
        "projects": projects,
        "project_rows": project_rows,
        "totals": totals,
        "generated_at": datetime.utcnow(),
    }

def build_customer_summary(projects):
    grouped = {}
    for project in projects:
        name = project.customer_name or "Unknown Customer"
        if name not in grouped:
            grouped[name] = {
                "customer_name": name,
                "project_count": 0,
                "completed_count": 0,
                "active_count": 0,
                "documents": 0,
                "forms": 0,
                "open_tasks": 0,
                "open_issues": 0,
                "payroll_due": 0,
                "payroll_paid": 0,
                "payroll_balance": 0,
                "locations": set(),
            }

        row = grouped[name]
        row["project_count"] += 1
        row["completed_count"] += 1 if project.status == "Completed" else 0
        row["active_count"] += 0 if project.status == "Completed" else 1
        row["documents"] += len(project.documents)
        row["forms"] += sum(len(getattr(project, rel)) for _, rel in FORM_REQUIREMENTS)
        row["open_tasks"] += len([t for t in getattr(project, "tasks", []) if t.status not in ["Completed", "Cancelled"]])
        row["open_issues"] += len([i for i in getattr(project, "issues", []) if i.status not in ["Resolved", "Closed"]])
        payroll_entries = ProjectPayrollEntry.query.join(ProjectPayrollBatch).filter(ProjectPayrollBatch.project_id == project.id).all()
        row["payroll_due"] += sum(e.total_due for e in payroll_entries)
        row["payroll_paid"] += sum(e.total_paid for e in payroll_entries)
        row["payroll_balance"] += sum(e.balance for e in payroll_entries)
        if project.location:
            row["locations"].add(project.location)

    rows = []
    for row in grouped.values():
        row["locations"] = ", ".join(sorted(row["locations"]))
        rows.append(row)
    return sorted(rows, key=lambda r: r["customer_name"].lower())

def pdf_response(html, filename):
    pdf = HTML(string=html, base_url=request.host_url).write_pdf()
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    return response

@report_bp.route("/")
@login_required
def reports_home():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    summary = []
    for p in projects:
        data = project_report_data(p)
        summary.append({"project": p, "ready": data["ready"], "items": data["checklist"], "summary": data["summary"]})
    return render_template("reports/home.html", summary=summary)

@report_bp.route("/project/<int:project_id>")
@login_required
def project_report(project_id):
    project = Project.query.get_or_404(project_id)
    items, ready = project_checklist(project)
    return render_template("reports/project_report.html", project=project, items=items, ready=ready)

@report_bp.route("/project/<int:project_id>/pdf")
@login_required
def project_report_pdf(project_id):
    project = Project.query.get_or_404(project_id)
    items, ready = project_checklist(project)
    html = render_template("reports/project_report_pdf.html", project=project, items=items, ready=ready)
    return pdf_response(html, f"project_{project.id}_completion_report.pdf")

@report_bp.route("/project/<int:project_id>/full")
@login_required
def project_full_report(project_id):
    project = Project.query.get_or_404(project_id)
    data = project_report_data(project)
    return render_template("reports/project_full_report.html", **data)

@report_bp.route("/project/<int:project_id>/full/pdf")
@login_required
def project_full_report_pdf(project_id):
    project = Project.query.get_or_404(project_id)
    data = project_report_data(project)
    html = render_template("reports/project_full_report_pdf.html", **data)
    return pdf_response(html, f"project_{project.id}_full_report.pdf")

@report_bp.route("/customers")
@login_required
def customer_reports():
    q = (request.args.get("q") or "").strip()
    query = Project.query
    if q:
        query = query.filter(Project.customer_name.ilike(f"%{q}%"))
    projects = query.order_by(Project.customer_name.asc(), Project.created_at.desc()).all()
    customers = build_customer_summary(projects)
    return render_template("reports/customer_reports.html", customers=customers, q=q)

@report_bp.route("/customers/<path:customer_name>")
@login_required
def customer_report_detail(customer_name):
    data = customer_report_data(customer_name)
    if not data["projects"]:
        flash("Customer report not found.", "warning")
        return redirect(url_for("reports.customer_reports"))
    return render_template("reports/customer_report_detail.html", **data)

@report_bp.route("/customers/<path:customer_name>/pdf")
@login_required
def customer_report_pdf(customer_name):
    data = customer_report_data(customer_name)
    if not data["projects"]:
        flash("Customer report not found.", "warning")
        return redirect(url_for("reports.customer_reports"))
    html = render_template("reports/customer_report_pdf.html", **data)
    safe_name = "".join(c for c in customer_name if c.isalnum() or c in ("-", "_")).strip() or "customer"
    return pdf_response(html, f"customer_{safe_name}_report.pdf")

@report_bp.route("/form/<form_key>/<int:form_id>/pdf")
@login_required
def form_pdf(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("reports.reports_home"))
    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    rows = build_display_rows(entry, form_key)
    html = render_template("reports/form_pdf.html", form_title=config["title"], entry=entry, display_rows=rows)
    return pdf_response(html, f"{form_key}_{form_id}.pdf")