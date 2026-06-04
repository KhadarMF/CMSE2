
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import (
    Project, Employee, ProjectPayrollBatch, ProjectPayrollEntry, ProjectPayrollPayment,
    PROJECT_PAYROLL_BATCH_STATUSES, PROJECT_PAYROLL_ENTRY_STATUSES, PROJECT_PAYMENT_METHODS
)

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")
MANAGER_ROLES = ["Admin", "Management", "Operation Manager"]
FINANCE_ROLES = ["Admin", "Management", "Finance Officer"]

def can_manage_payroll(): return current_user.role in MANAGER_ROLES
def can_pay_payroll(): return current_user.role in FINANCE_ROLES

def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None

def parse_float(value):
    try: return float(value or 0)
    except Exception: return 0

def generate_batch_no(): return "PPB-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")

def employee_previous_balance(employee_id):
    entries = ProjectPayrollEntry.query.filter_by(employee_id=employee_id).all()
    return sum(e.balance for e in entries if e.balance > 0)

def update_entry_status(entry):
    if entry.total_paid <= 0:
        if entry.status not in ["Cancelled"]: entry.status = "Approved"
    elif entry.balance <= 0: entry.status = "Paid"
    else: entry.status = "Partially Paid"

def update_batch_status(batch):
    if not batch.entries: return
    if all(e.status == "Paid" for e in batch.entries): batch.status = "Paid"
    elif any(e.total_paid > 0 for e in batch.entries): batch.status = "Partially Paid"

@payroll_bp.before_app_request
def ensure_phase13_tables():
    try: db.create_all()
    except Exception: pass

@payroll_bp.route("/")
@login_required
def dashboard():
    batches = ProjectPayrollBatch.query.order_by(ProjectPayrollBatch.created_at.desc()).all()
    summary = {"batches": len(batches), "total_due": sum(b.total_due for b in batches), "total_paid": sum(b.total_paid for b in batches), "balance": sum(b.balance for b in batches), "employees": len({e.employee_id for b in batches for e in b.entries}), "projects": len({b.project_id for b in batches})}
    return render_template("payroll/dashboard.html", batches=batches, summary=summary)

@payroll_bp.route("/batches")
@login_required
def batches():
    project_id, status = request.args.get("project_id"), request.args.get("status")
    query = ProjectPayrollBatch.query
    if project_id: query = query.filter_by(project_id=project_id)
    if status: query = query.filter_by(status=status)
    batches = query.order_by(ProjectPayrollBatch.created_at.desc()).all()
    return render_template("payroll/batches.html", batches=batches, projects=Project.query.order_by(Project.project_name.asc()).all(), statuses=PROJECT_PAYROLL_BATCH_STATUSES, filters=request.args)

@payroll_bp.route("/batches/create", methods=["GET", "POST"])
@login_required
def create_batch():
    if not can_manage_payroll():
        flash("Only Admin, Management or Operation Manager can create project payroll batches.", "danger")
        return redirect(url_for("payroll.dashboard"))
    employees = Employee.query.filter_by(status="Active").order_by(Employee.full_name.asc()).all()
    projects = Project.query.order_by(Project.project_name.asc()).all()
    if request.method == "POST":
        selected_employee_ids = request.form.getlist("employee_id")
        if not selected_employee_ids or not any(selected_employee_ids):
            flash("Select at least one employee.", "danger")
            return redirect(url_for("payroll.create_batch"))
        batch = ProjectPayrollBatch(batch_no=generate_batch_no(), project_id=request.form.get("project_id"), work_date=parse_date(request.form.get("work_date")), batch_title=request.form.get("batch_title") or "Project Payroll Batch", work_scope=request.form.get("work_scope"), status=request.form.get("status") or "Submitted", manager_notes=request.form.get("manager_notes"), created_by_id=current_user.id)
        db.session.add(batch); db.session.flush()
        created_count = 0
        for idx, emp_id in enumerate(selected_employee_ids, start=1):
            if not emp_id: continue
            amount = parse_float(request.form.get(f"amount_row_{idx}")); allowance = parse_float(request.form.get(f"allowance_row_{idx}")); deduction = parse_float(request.form.get(f"deduction_row_{idx}"))
            if amount == 0 and allowance == 0 and deduction == 0: continue
            prev = employee_previous_balance(emp_id) if request.form.get("auto_previous_balance") == "on" else parse_float(request.form.get(f"previous_row_{idx}"))
            db.session.add(ProjectPayrollEntry(batch_id=batch.id, employee_id=emp_id, role_on_project=request.form.get(f"role_row_{idx}"), work_description=request.form.get(f"description_row_{idx}"), work_days=0, project_amount=amount, allowance_amount=allowance, deduction_amount=deduction, previous_balance=prev, status="Approved" if batch.status == "Approved" else "Pending", notes=request.form.get(f"notes_row_{idx}")))
            created_count += 1
        if created_count == 0:
            db.session.rollback(); flash("No payroll lines were created because amounts are empty.", "danger"); return redirect(url_for("payroll.create_batch"))
        db.session.commit(); flash(f"Project payroll batch created with {created_count} employee lines.", "success")
        return redirect(url_for("payroll.batch_detail", batch_id=batch.id))
    return render_template("payroll/batch_form.html", employees=employees, projects=projects, statuses=PROJECT_PAYROLL_BATCH_STATUSES)

@payroll_bp.route("/batches/<int:batch_id>")
@login_required
def batch_detail(batch_id):
    batch = ProjectPayrollBatch.query.get_or_404(batch_id)
    return render_template("payroll/batch_detail.html", batch=batch, payment_methods=PROJECT_PAYMENT_METHODS)

@payroll_bp.route("/batches/<int:batch_id>/approve")
@login_required
def approve_batch(batch_id):
    if not can_manage_payroll():
        flash("Only Admin, Management or Operation Manager can approve payroll batches.", "danger")
        return redirect(url_for("payroll.batch_detail", batch_id=batch_id))
    batch = ProjectPayrollBatch.query.get_or_404(batch_id)
    batch.status = "Approved"; batch.approved_by_id = current_user.id; batch.approved_at = datetime.utcnow()
    for entry in batch.entries:
        if entry.status == "Pending": entry.status = "Approved"
    db.session.commit(); flash("Project payroll batch approved.", "success")
    return redirect(url_for("payroll.batch_detail", batch_id=batch.id))

@payroll_bp.route("/entries")
@login_required
def entries():
    employee_id, project_id, status = request.args.get("employee_id"), request.args.get("project_id"), request.args.get("status")
    query = ProjectPayrollEntry.query.join(ProjectPayrollBatch)
    if employee_id: query = query.filter(ProjectPayrollEntry.employee_id == employee_id)
    if project_id: query = query.filter(ProjectPayrollBatch.project_id == project_id)
    if status: query = query.filter(ProjectPayrollEntry.status == status)
    entries = query.order_by(ProjectPayrollBatch.created_at.desc()).all()
    return render_template("payroll/entries.html", entries=entries, employees=Employee.query.order_by(Employee.full_name.asc()).all(), projects=Project.query.order_by(Project.project_name.asc()).all(), statuses=PROJECT_PAYROLL_ENTRY_STATUSES, filters=request.args)

@payroll_bp.route("/entries/<int:entry_id>")
@login_required
def entry_detail(entry_id):
    entry = ProjectPayrollEntry.query.get_or_404(entry_id)
    return render_template("payroll/entry_detail.html", entry=entry, payment_methods=PROJECT_PAYMENT_METHODS)

@payroll_bp.route("/entries/<int:entry_id>/payment", methods=["POST"])
@login_required
def add_payment(entry_id):
    if not can_pay_payroll():
        flash("Only Admin, Management or Finance Officer can record payments.", "danger")
        return redirect(url_for("payroll.entry_detail", entry_id=entry_id))
    entry = ProjectPayrollEntry.query.get_or_404(entry_id); amount = parse_float(request.form.get("amount"))
    if amount <= 0:
        flash("Payment amount must be greater than zero.", "danger"); return redirect(url_for("payroll.entry_detail", entry_id=entry_id))
    db.session.add(ProjectPayrollPayment(payroll_entry_id=entry.id, payment_date=parse_date(request.form.get("payment_date")) or date.today(), amount=amount, payment_method=request.form.get("payment_method") or "Cash", reference_no=request.form.get("reference_no"), paid_by_id=current_user.id, notes=request.form.get("notes")))
    update_entry_status(entry); update_batch_status(entry.batch); db.session.commit(); flash("Payment recorded successfully.", "success")
    return redirect(url_for("payroll.entry_detail", entry_id=entry.id))

@payroll_bp.route("/employees/<int:employee_id>/statement")
@login_required
def employee_statement(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    entries = ProjectPayrollEntry.query.filter_by(employee_id=employee.id).join(ProjectPayrollBatch).order_by(ProjectPayrollBatch.work_date.desc()).all()
    summary = {"projects_count": len({e.batch.project_id for e in entries}), "batches_count": len({e.batch_id for e in entries}), "total_due": sum(e.total_due for e in entries), "total_paid": sum(e.total_paid for e in entries), "balance": sum(e.balance for e in entries)}
    return render_template("payroll/employee_statement.html", employee=employee, entries=entries, summary=summary)

@payroll_bp.route("/projects/<int:project_id>/payroll")
@login_required
def project_payroll(project_id):
    project = Project.query.get_or_404(project_id)
    batches = ProjectPayrollBatch.query.filter_by(project_id=project.id).order_by(ProjectPayrollBatch.created_at.desc()).all()
    entries = [entry for batch in batches for entry in batch.entries]
    summary = {"batches_count": len(batches), "employees_count": len({e.employee_id for e in entries}), "total_due": sum(e.total_due for e in entries), "total_paid": sum(e.total_paid for e in entries), "balance": sum(e.balance for e in entries)}
    return render_template("payroll/project_payroll.html", project=project, batches=batches, entries=entries, summary=summary)
