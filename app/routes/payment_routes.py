import os
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    PaymentRequest, PaymentRequestPayment, Project, MaterialRequest, Branch, Department,
    PAYMENT_REQUEST_STATUSES, PAYMENT_REQUEST_CATEGORIES, PAYMENT_REQUEST_METHODS, PAYMENT_REQUEST_CURRENCIES,
)
from app.notifications import notify_roles, notify_user

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

# Same two-tier approval convention as app/routes/payroll_routes.py:
# MANAGER_ROLES give first-level approval, FINANCE_ROLES give final approval
# and record payments. Kept identical on purpose so an Admin/Management user
# who already understands payroll approval understands this immediately.
MANAGER_ROLES = ["Admin", "Management", "Operation Manager"]
FINANCE_ROLES = ["Admin", "Management", "Finance Officer"]
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png"}

DEAD_STATUSES = ("Rejected", "Cancelled")


def can_manage_payment_requests():
    return current_user.role in MANAGER_ROLES


def can_finance_payment_requests():
    return current_user.role in FINANCE_ROLES


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None


def parse_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0


def parse_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    # Same pattern as app/routes/document_routes.py's save_file(), with
    # microsecond precision on the stored filename prefix rather than
    # second precision — see PHASE18A4 notes for why that distinction
    # matters when two uploads can land in the same second.
    if not file or not file.filename or not allowed_file(file.filename):
        return None, None
    orig = secure_filename(file.filename)
    stored = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{orig}"
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], stored))
    return orig, stored


def update_payment_request_status(pr):
    if pr.status in DEAD_STATUSES:
        return
    if pr.total_paid <= 0:
        return
    if pr.balance <= 0.01:
        pr.status = "Paid"
    else:
        pr.status = "Partially Paid"


@payments_bp.before_app_request
def ensure_payment_tables():
    # Phase 20D: db.create_all() removed - the schema is owned by Alembic
    # (`flask db upgrade`). create_all() only ever created MISSING TABLES;
    # it silently ignored new COLUMNS, which is how the schema drifted.
    return None


@payments_bp.route("/")
@login_required
def dashboard():
    all_requests = PaymentRequest.query.order_by(PaymentRequest.created_at.desc()).all()
    live_requests = [r for r in all_requests if r.status not in DEAD_STATUSES]
    summary = {
        "pending_manager": sum(1 for r in all_requests if r.status == "Pending Manager Approval"),
        "pending_finance": sum(1 for r in all_requests if r.status == "Pending Finance Approval"),
        "approved_unpaid": sum(1 for r in all_requests if r.status == "Approved"),
        "partially_paid": sum(1 for r in all_requests if r.status == "Partially Paid"),
        "paid": sum(1 for r in all_requests if r.status == "Paid"),
        "total_requested": sum(float(r.amount or 0) for r in live_requests),
        "total_paid": sum(r.total_paid for r in all_requests),
        "total_outstanding": sum(r.balance for r in live_requests),
    }
    return render_template(
        "payments/dashboard.html", summary=summary, recent=all_requests[:10],
        can_manage=can_manage_payment_requests(), can_finance=can_finance_payment_requests(),
    )


@payments_bp.route("/requests")
@login_required
def list_requests():
    status, category, project_id = request.args.get("status"), request.args.get("category"), request.args.get("project_id")
    query = PaymentRequest.query
    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.filter_by(category=category)
    if project_id:
        query = query.filter_by(project_id=project_id)
    requests_list = query.order_by(PaymentRequest.created_at.desc()).all()
    return render_template(
        "payments/requests.html", requests=requests_list, statuses=PAYMENT_REQUEST_STATUSES,
        categories=PAYMENT_REQUEST_CATEGORIES,
        projects=Project.query.order_by(Project.project_name.asc()).all(), filters=request.args,
    )


@payments_bp.route("/requests/my")
@login_required
def my_requests():
    requests_list = PaymentRequest.query.filter_by(requested_by_id=current_user.id).order_by(PaymentRequest.created_at.desc()).all()
    return render_template("payments/my_requests.html", requests=requests_list)


@payments_bp.route("/requests/create", methods=["GET", "POST"])
@login_required
def create_request():
    if request.method == "POST":
        amount = parse_float(request.form.get("amount"))
        payee_name = (request.form.get("payee_name") or "").strip()
        purpose = (request.form.get("purpose") or "").strip()
        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(url_for("payments.create_request"))
        if not payee_name or not purpose:
            flash("Payee name and purpose are required.", "danger")
            return redirect(url_for("payments.create_request"))

        pr = PaymentRequest(
            requested_by_id=current_user.id,
            branch_id=parse_int(request.form.get("branch_id")) or current_user.branch_id,
            department_id=parse_int(request.form.get("department_id")) or current_user.department_id,
            project_id=parse_int(request.form.get("project_id")),
            material_request_id=parse_int(request.form.get("material_request_id")),
            payee_name=payee_name,
            payee_phone=request.form.get("payee_phone"),
            category=request.form.get("category") or "Other",
            purpose=purpose,
            amount=amount,
            currency=request.form.get("currency") or "USD",
            needed_by_date=parse_date(request.form.get("needed_by_date")),
            status="Pending Manager Approval",
        )
        file = request.files.get("attachment")
        if file and file.filename:
            orig, stored = save_upload(file)
            if stored:
                pr.attachment_original_name, pr.attachment_stored_name = orig, stored

        db.session.add(pr)
        db.session.flush()  # assigns pr.id, used to build a collision-proof request_no
        pr.request_no = f"PR-{datetime.utcnow().strftime('%Y%m%d')}-{pr.id:05d}"
        db.session.commit()

        notify_roles(
            MANAGER_ROLES, subject=f"Payment Request {pr.request_no} awaiting approval",
            message=f"{current_user.full_name} requested {pr.currency} {pr.amount:,.2f} for {pr.payee_name} — {pr.purpose}",
            module="payment-requests", record_id=pr.id,
        )
        flash(f"Payment request {pr.request_no} submitted for approval.", "success")
        return redirect(url_for("payments.request_detail", request_id=pr.id))

    return render_template(
        "payments/request_form.html",
        categories=PAYMENT_REQUEST_CATEGORIES, currencies=PAYMENT_REQUEST_CURRENCIES,
        projects=Project.query.order_by(Project.project_name.asc()).all(),
        material_requests=MaterialRequest.query.order_by(MaterialRequest.created_at.desc()).limit(100).all(),
        branches=Branch.query.filter_by(is_active=True).order_by(Branch.branch_name.asc()).all(),
        departments=Department.query.filter_by(is_active=True).order_by(Department.department_name.asc()).all(),
        selected_project=request.args.get("project_id", ""),
    )


@payments_bp.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    pr = PaymentRequest.query.get_or_404(request_id)
    return render_template(
        "payments/request_detail.html", pr=pr, payment_methods=PAYMENT_REQUEST_METHODS,
        currencies=PAYMENT_REQUEST_CURRENCIES,
        can_manage=can_manage_payment_requests(), can_finance=can_finance_payment_requests(),
    )


@payments_bp.route("/requests/<int:request_id>/attachment")
@login_required
def download_attachment(request_id):
    pr = PaymentRequest.query.get_or_404(request_id)
    if not pr.attachment_stored_name:
        flash("No attachment on this request.", "warning")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], pr.attachment_stored_name, as_attachment=True, download_name=pr.attachment_original_name or pr.attachment_stored_name)


@payments_bp.route("/requests/<int:request_id>/approve-manager")
@login_required
def approve_manager(request_id):
    pr = PaymentRequest.query.get_or_404(request_id)
    if not can_manage_payment_requests():
        flash("Only Admin, Management or Operation Manager can give first-level approval.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    if pr.status != "Pending Manager Approval":
        flash("This request is not awaiting manager approval.", "warning")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    pr.status = "Pending Finance Approval"
    pr.manager_approved_by_id = current_user.id
    pr.manager_approved_at = datetime.utcnow()
    db.session.commit()
    notify_roles(
        FINANCE_ROLES, subject=f"Payment Request {pr.request_no} needs finance approval",
        message=f"Manager-approved by {current_user.full_name}. {pr.currency} {pr.amount:,.2f} for {pr.payee_name}.",
        module="payment-requests", record_id=pr.id,
    )
    notify_user(
        pr.requested_by, subject=f"Your payment request {pr.request_no} was approved by manager",
        message="Now awaiting finance approval.", module="payment-requests", record_id=pr.id,
    )
    flash("Request approved and sent to Finance.", "success")
    return redirect(url_for("payments.request_detail", request_id=request_id))


@payments_bp.route("/requests/<int:request_id>/approve-finance")
@login_required
def approve_finance(request_id):
    pr = PaymentRequest.query.get_or_404(request_id)
    if not can_finance_payment_requests():
        flash("Only Admin, Management or Finance Officer can give final approval.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    if pr.status != "Pending Finance Approval":
        flash("This request is not awaiting finance approval.", "warning")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    pr.status = "Approved"
    pr.finance_approved_by_id = current_user.id
    pr.finance_approved_at = datetime.utcnow()
    db.session.commit()
    notify_user(
        pr.requested_by, subject=f"Your payment request {pr.request_no} is approved",
        message="Finance approved this request. Payment will follow.", module="payment-requests", record_id=pr.id,
    )
    flash("Request approved by Finance. Ready for payment.", "success")
    return redirect(url_for("payments.request_detail", request_id=request_id))


@payments_bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@login_required
def reject_request(request_id):
    pr = PaymentRequest.query.get_or_404(request_id)
    stage = pr.status
    allowed = (stage == "Pending Manager Approval" and can_manage_payment_requests()) or \
              (stage == "Pending Finance Approval" and can_finance_payment_requests())
    if not allowed:
        flash("You cannot reject this request at its current stage.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("A rejection reason is required.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    pr.status = "Rejected"
    pr.rejected_by_id = current_user.id
    pr.rejected_at = datetime.utcnow()
    pr.rejection_reason = reason
    pr.rejected_at_stage = stage
    db.session.commit()
    notify_user(
        pr.requested_by, subject=f"Your payment request {pr.request_no} was rejected",
        message=f"Reason: {reason}", module="payment-requests", record_id=pr.id,
    )
    flash("Request rejected.", "success")
    return redirect(url_for("payments.request_detail", request_id=request_id))


@payments_bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel_request(request_id):
    pr = PaymentRequest.query.get_or_404(request_id)
    if pr.requested_by_id != current_user.id and current_user.role != "Admin":
        flash("Only the requester or Admin can cancel this request.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    if pr.status != "Pending Manager Approval":
        flash("Only requests still awaiting manager approval can be cancelled directly. Ask an approver to reject it instead.", "warning")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    pr.status = "Cancelled"
    pr.cancelled_by_id = current_user.id
    pr.cancelled_at = datetime.utcnow()
    db.session.commit()
    flash("Request cancelled.", "success")
    return redirect(url_for("payments.request_detail", request_id=request_id))


@payments_bp.route("/requests/<int:request_id>/payment", methods=["POST"])
@login_required
def add_payment(request_id):
    pr = PaymentRequest.query.get_or_404(request_id)
    if not can_finance_payment_requests():
        flash("Only Admin, Management or Finance Officer can record payments.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    if pr.status not in ("Approved", "Partially Paid"):
        flash("This request must be fully approved before recording a payment.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    amount = parse_float(request.form.get("amount"))
    if amount <= 0:
        flash("Payment amount must be greater than zero.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    if amount > pr.balance + 0.01:
        flash(f"Payment amount ({amount:,.2f}) exceeds the remaining balance ({pr.balance:,.2f}).", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))

    payment = PaymentRequestPayment(
        payment_date=parse_date(request.form.get("payment_date")) or date.today(),
        amount=amount,
        currency=pr.currency,
        payment_method=request.form.get("payment_method") or "Cash",
        reference_no=request.form.get("reference_no"),
        payee_phone=request.form.get("payee_phone") or pr.payee_phone,
        paid_by_id=current_user.id,
        notes=request.form.get("notes"),
    )
    file = request.files.get("proof")
    if file and file.filename:
        orig, stored = save_upload(file)
        if stored:
            payment.proof_original_name, payment.proof_stored_name = orig, stored

    # Append to the relationship (not just set payment_request_id) so the
    # in-memory pr.payments collection — already loaded above by the
    # pr.balance check — includes this payment immediately. Setting only
    # the foreign key left that cached collection stale, so total_paid/
    # balance computed a moment later were still pre-payment values and
    # the status never advanced past "Approved". Confirmed by testing.
    pr.payments.append(payment)
    update_payment_request_status(pr)
    db.session.commit()

    # Phase 20B: auto-journal AFTER the payment is committed - the payment
    # is the source of truth, a journal failure must never undo it.
    from app.accounting_service import journal_for_payment_request_payment, try_auto_journal
    journal_entry, journal_error = try_auto_journal(
        journal_for_payment_request_payment, pr, payment, created_by_id=current_user.id
    )
    if journal_error:
        flash(f"Payment recorded, but the accounting journal entry could not be created automatically: {journal_error} You can add it manually in Accounting > Journal.", "warning")

    notify_user(
        pr.requested_by, subject=f"Payment recorded for {pr.request_no}",
        message=f"{payment.currency} {payment.amount:,.2f} paid via {payment.payment_method}. Status: {pr.status}.",
        module="payment-requests", record_id=pr.id,
    )
    flash("Payment recorded.", "success")
    return redirect(url_for("payments.request_detail", request_id=request_id))


@payments_bp.route("/requests/<int:request_id>/payments/<int:payment_id>/proof")
@login_required
def download_payment_proof(request_id, payment_id):
    payment = PaymentRequestPayment.query.get_or_404(payment_id)
    if payment.payment_request_id != request_id:
        flash("Payment does not belong to this request.", "danger")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    if not payment.proof_stored_name:
        flash("No proof file attached to this payment.", "warning")
        return redirect(url_for("payments.request_detail", request_id=request_id))
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], payment.proof_stored_name, as_attachment=True, download_name=payment.proof_original_name or payment.proof_stored_name)


@payments_bp.route("/reports")
@login_required
def payment_reports():
    all_requests = PaymentRequest.query.all()
    by_category = {}
    for r in all_requests:
        c = r.category or "Other"
        row = by_category.setdefault(c, {"count": 0, "amount": 0.0, "paid": 0.0})
        row["count"] += 1
        row["amount"] += float(r.amount or 0)
        row["paid"] += r.total_paid
    by_method = {}
    for r in all_requests:
        for p in r.payments:
            m = p.payment_method or "Other"
            row = by_method.setdefault(m, {"count": 0, "amount": 0.0})
            row["count"] += 1
            row["amount"] += float(p.amount or 0)
    return render_template(
        "payments/reports.html", by_category=by_category, by_method=by_method,
        total_requests=len(all_requests),
    )
