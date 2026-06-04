from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import (
    Project, SiteSurveyForm, LoadAssessmentForm, DailySiteReport,
    DeliveryNoteForm, TestingForm, CommissioningForm, HandoverForm, FORM_APPROVAL_STATUSES, ApprovalHistory
)
from app.permissions import can_create_form, can_edit_form, can_delete_form, can_review_document
from app.activity import log_activity, log_approval
from app.notifications import notify_roles, notify_user

form_bp = Blueprint("forms", __name__, url_prefix="/forms")

FIELD_CHOICES = {
    "roof_type": [("Concrete Roof","Concrete Roof (Saqaf shub/concrete ah)"),("Metal Sheet Roof","Metal Sheet Roof (Jiingad/saqaf bir ah)"),("Tile Roof","Tile Roof (Saqaf tiles ah)"),("Flat Roof","Flat Roof (Saqaf siman)"),("Ground Mount","Ground Mount (Dhul lagu rakibayo)"),("Other","Other (Mid kale)")],
    "roof_condition": [("Excellent","Excellent (Aad u fiican)"),("Good","Good (Fiican)"),("Fair","Fair (Dhexdhexaad)"),("Weak","Weak (Daciif ah)"),("Needs Repair","Needs Repair (Dayactir ayuu u baahan yahay)"),("Not Suitable","Not Suitable (Kuma habboona rakibid)")],
    "shading_status": [("No Shading","No Shading (Wax hadh ah ma jiro)"),("Partial Shading","Partial Shading (Hadh qayb ah - Geedo/Dhismayaal)"),("Heavy Shading","Heavy Shading (Hadh badan - Aan ku habboonayn)")],
    "existing_power_source": [("No Grid","No Grid (Koronto grid ah ma jirto)"),("Grid Available","Grid Available (Grid waa jiraa)"),("Grid Unstable","Grid Unstable (Grid-ku wuu liitaa)"),("Generator Available","Generator Available (Generator waa jiraa)"),("Existing Solar System","Existing Solar System (Solar hore ayaa jira)")],
    "earthing_condition": [("Good","Good (Fiican)"),("Needs Improvement","Needs Improvement (Hagaajin ayuu u baahan yahay)"),("Not Available","Not Available (Ma jiro)"),("Not Checked","Not Checked (Lama hubin)")],
    "access_road": [("Easy Access","Easy Access (Si fudud ayaa loo geli karaa)"),("Moderate Access","Moderate Access (Dhexdhexaad)"),("Difficult Access","Difficult Access (Way adag tahay)"),("Crane/Scaffold Required","Crane/Scaffold Required (Qalab kor u qaadis ayaa loo baahan yahay)")],
    "condition_of_items": [("Good","Good (Fiican)"),("Minor Damage","Minor Damage (Dhaawac yar)"),("Damaged","Damaged (Waxyeello leh)"),("Missing Items","Missing Items (Alaab ayaa maqan)")],
    "inverter_status": [("Good","Good (Fiican)"),("Configured","Configured (Waa la habeeyey)"),("Needs Configuration","Needs Configuration (Settings ayaa loo baahan yahay)"),("Fault Showing","Fault Showing (Cilad ayaa muuqata)"),("Not Installed","Not Installed (Lama rakibin)")],
    "load_test_result": [("Pass","Pass (Wuu gudbay)"),("Pass with Comments","Pass with Comments (Wuu gudbay faallo ayaa jirta)"),("Fail","Fail (Wuu dhacay)"),("Not Tested","Not Tested (Lama tijaabin)")],
    "protection_test_result": [("Pass","Pass (Wuu gudbay)"),("Pass with Comments","Pass with Comments (Wuu gudbay faallo ayaa jirta)"),("Fail","Fail (Wuu dhacay)"),("Not Tested","Not Tested (Lama tijaabin)")],
    "test_result": [("Pass","Pass (Wuu gudbay)"),("Pass with Comments","Pass with Comments (Wuu gudbay faallo ayaa jirta)"),("Fail","Fail (Wuu dhacay)"),("Not Tested","Not Tested (Lama tijaabin)")],
    "monitoring_setup": [("Completed","Completed (Waa la dhammeeyey)"),("Pending","Pending (Weli wuu dhiman yahay)"),("Not Applicable","Not Applicable (Ma khusayso)")],
    "client_training_done": [("Yes","Yes (Haa)"),("No","No (Maya)"),("Partially","Partially (Qayb ahaan)"),("Pending","Pending (Weli)")],
    "commissioning_status": [("Fully Operational","Fully Operational (Nidaamku si buuxda ayuu u shaqaynayaa)"),("Operational with Issues","Operational with Issues (Wuu shaqaynayaa laakiin cilad yar ayaa jirta)"),("Pending - Testing Required","Pending - Testing Required (Wuxuu sugayaa in la tijaabiyo)"),("Failed - Needs Troubleshooting","Failed - Needs Troubleshooting (Wuu guuldaystay - Dayactir ayuu u baahan yahay)")],
    "training_provided": [("Yes","Yes (Haa)"),("No","No (Maya)"),("Partially","Partially (Qayb ahaan)"),("Pending","Pending (Weli)")],
    "warranty_explained": [("Yes","Yes (Haa)"),("No","No (Maya)"),("Partially","Partially (Qayb ahaan)")],
    "final_status": [("Ready for Handover","Ready for Handover (Handover diyaar ayuu u yahay)"),("Handover with Pending Items","Handover with Pending Items (Waxyaabo yar ayaa dhiman)"),("Not Ready","Not Ready (Weli diyaar ma aha)")],
}

def get_field_type(field_name, default_type):
    return f"select:{field_name}" if field_name in FIELD_CHOICES else default_type


FORM_CONFIG = {
    "site-survey": {
        "title": "Site Survey & Load Assessment Form", "model": SiteSurveyForm,
        "template": "forms/site_survey.html",
        "detail_template": "forms/detail.html",
        "fields": [
            ("site_name", "Site Name", "text"), ("survey_date", "Survey Date", "date"),
            ("surveyed_by", "Surveyed By", "text"), ("gps_coordinates", "GPS Coordinates", "text"),
            ("roof_type", "Roof Type", "text"), ("roof_condition", "Roof Condition", "text"),
            ("available_space", "Available Space", "text"), ("shading_status", "Shading Status", "text"),
            ("existing_power_source", "Existing Power Source", "text"),
            ("earthing_condition", "Earthing Condition", "text"), ("access_road", "Access Road", "text"),
            ("assessment_date", "Load Assessment Date", "date"), ("assessed_by", "Assessed By", "text"),
            ("daytime_load_kw", "Daytime Load kW", "text"), ("nighttime_load_kw", "Nighttime Load kW", "text"),
            ("total_daily_consumption_kwh", "Total Daily Consumption kWh", "text"),
            ("critical_loads", "Critical Loads", "textarea"), ("ac_loads", "AC Loads", "textarea"),
            ("pump_loads", "Pump Loads", "textarea"), ("lighting_loads", "Lighting Loads", "textarea"),
            ("backup_hours_required", "Backup Hours Required", "text"),
            ("recommended_system_size", "Recommended System Size", "text"),
            ("recommendation", "Technical Recommendation", "textarea"),
            ("remarks", "Remarks", "textarea"),
        ],
    },
    "load-assessment": {
        "title": "Load Assessment Form", "model": LoadAssessmentForm,
        "template": "forms/load_assessment.html", "detail_template": "forms/detail.html",
        "fields": [
            ("assessment_date", "Assessment Date", "date"), ("assessed_by", "Assessed By", "text"),
            ("daytime_load_kw", "Daytime Load kW", "text"), ("nighttime_load_kw", "Nighttime Load kW", "text"),
            ("total_daily_consumption_kwh", "Total Daily Consumption kWh", "text"),
            ("critical_loads", "Critical Loads", "textarea"), ("ac_loads", "AC Loads", "textarea"),
            ("pump_loads", "Pump Loads", "textarea"), ("lighting_loads", "Lighting Loads", "textarea"),
            ("backup_hours_required", "Backup Hours Required", "text"),
            ("recommended_system_size", "Recommended System Size", "text"), ("remarks", "Remarks", "textarea"),
        ],
    },
    "daily-site-report": {
        "title": "Daily Site Report", "model": DailySiteReport,
        "template": "forms/daily_site_report.html", "detail_template": "forms/detail.html",
        "fields": [
            ("report_date", "Report Date", "date"), ("site_supervisor", "Site Supervisor", "text"),
            ("manpower", "Manpower", "textarea"), ("work_done_today", "Work Done Today", "textarea"),
            ("materials_used", "Materials Used", "textarea"), ("tools_equipment_used", "Tools / Equipment Used", "textarea"),
            ("issues_challenges", "Issues / Challenges", "textarea"), ("safety_notes", "Safety Notes", "textarea"),
            ("next_day_plan", "Next Day Plan", "textarea"), ("progress_percentage", "Progress Percentage", "text"),
            ("remarks", "Remarks", "textarea"),
        ],
    },
    "delivery-note": {
        "title": "Delivery Note", "model": DeliveryNoteForm,
        "template": "forms/delivery_note.html", "detail_template": "forms/detail.html",
        "fields": [
            ("delivery_date", "Delivery Date", "date"), ("delivered_by", "Delivered By", "text"),
            ("received_by", "Received By", "text"), ("vehicle_plate", "Vehicle Plate", "text"),
            ("delivery_location", "Delivery Location", "text"), ("items_delivered", "Items Delivered", "textarea"),
            ("quantity_summary", "Quantity Summary", "textarea"), ("condition_of_items", "Condition of Items", "text"),
            ("receiver_comments", "Receiver Comments", "textarea"), ("remarks", "Remarks", "textarea"),
        ],
    },
    "testing": {
        "title": "Testing Form", "model": TestingForm,
        "template": "forms/testing.html", "detail_template": "forms/detail.html",
        "fields": [
            ("testing_date", "Testing Date", "date"), ("tested_by", "Tested By", "text"),
            ("inverter_status", "Inverter Status", "text"), ("pv_voltage", "PV Voltage", "text"),
            ("battery_voltage", "Battery Voltage", "text"), ("output_voltage", "Output Voltage", "text"),
            ("load_test_result", "Load Test Result", "text"), ("protection_test_result", "Protection Test Result", "text"),
            ("faults_found", "Faults Found", "textarea"), ("corrective_actions", "Corrective Actions", "textarea"),
            ("test_result", "Test Result", "text"), ("remarks", "Remarks", "textarea"),
        ],
    },
    "commissioning": {
        "title": "Commissioning Form", "model": CommissioningForm,
        "template": "forms/commissioning.html", "detail_template": "forms/detail.html",
        "fields": [
            ("commissioning_date", "Commissioning Date", "date"), ("commissioned_by", "Commissioned By", "text"),
            ("system_capacity", "System Capacity", "text"), ("inverter_model", "Inverter Model", "text"),
            ("battery_model", "Battery Model", "text"), ("pv_array_details", "PV Array Details", "textarea"),
            ("battery_settings", "Battery Settings", "textarea"), ("inverter_settings", "Inverter Settings", "textarea"),
            ("monitoring_setup", "Monitoring Setup", "text"), ("client_training_done", "Client Training Done?", "text"),
            ("commissioning_status", "Commissioning Status", "text"), ("remarks", "Remarks", "textarea"),
        ],
    },
    "handover": {
        "title": "Handover Form", "model": HandoverForm,
        "template": "forms/handover.html", "detail_template": "forms/detail.html",
        "fields": [
            ("handover_date", "Handover Date", "date"), ("handed_over_by", "Handed Over By", "text"),
            ("received_by", "Received By", "text"), ("documents_handed_over", "Documents Handed Over", "textarea"),
            ("spare_parts_handed_over", "Spare Parts Handed Over", "textarea"),
            ("training_provided", "Training Provided?", "text"), ("warranty_explained", "Warranty Explained?", "text"),
            ("client_comments", "Client Comments", "textarea"), ("final_status", "Final Status", "text"),
            ("remarks", "Remarks", "textarea"),
        ],
    },
}

DATE_FIELDS = {
    "survey_date", "assessment_date", "report_date", "delivery_date",
    "testing_date", "commissioning_date", "handover_date",
}

def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def form_reference(form_key, form_id=None):
    prefixes = {
        "site-survey": "SSLA", "load-assessment": "LAF", "daily-site-report": "DSR",
        "delivery-note": "DNF", "testing": "TST", "commissioning": "COM", "handover": "HOF",
    }
    prefix = prefixes.get(form_key, "FRM")
    return f"{prefix}-{int(form_id or 0):05d}" if form_id else f"{prefix}-AUTO"

def get_render_fields(form_key):
    render_fields = []
    for field_name, label, field_type in FORM_CONFIG[form_key]["fields"]:
        render_fields.append((field_name, label, get_field_type(field_name, field_type)))
    return render_fields

def get_projects():
    return Project.query.order_by(Project.project_name.asc()).all()

def get_counts():
    return {
        "site_surveys": SiteSurveyForm.query.count(),
        "load_assessments": LoadAssessmentForm.query.count(),
        "daily_reports": DailySiteReport.query.count(),
        "delivery_notes": DeliveryNoteForm.query.count(),
        "testing_forms": TestingForm.query.count(),
        "commissioning_forms": CommissioningForm.query.count(),
        "handover_forms": HandoverForm.query.count(),
    }

def build_form_data(form_key):
    form_data = {}
    for field_name, label, field_type in FORM_CONFIG[form_key]["fields"]:
        value = request.form.get(field_name)
        if field_name in DATE_FIELDS:
            form_data[field_name] = parse_date(value)
        else:
            form_data[field_name] = value
    return form_data

def entry_to_values(entry, form_key):
    values = {}
    for field_name, label, field_type in FORM_CONFIG[form_key]["fields"]:
        value = getattr(entry, field_name, "")
        if field_type == "date" and value:
            value = value.strftime("%Y-%m-%d")
        values[field_name] = value or ""
    return values

def build_display_rows(entry, form_key):
    display_rows = []
    for field_name, label, field_type in FORM_CONFIG[form_key]["fields"]:
        value = getattr(entry, field_name, "")
        display_rows.append((label, value or ""))
    return display_rows

@form_bp.route("/")
@login_required
def forms_home():
    allowed_create_forms = {key: can_create_form(current_user, key) for key in FORM_CONFIG.keys()}
    allowed_view_forms = {key: can_create_form(current_user, key) or can_create_form(current_user, key) for key in FORM_CONFIG.keys()}
    # Correct view permissions are controlled separately.
    from app.permissions import can_view_form
    allowed_view_forms = {key: can_view_form(current_user, key) for key in FORM_CONFIG.keys()}
    return render_template("forms/home.html", counts=get_counts(), allowed_forms=allowed_create_forms, allowed_view_forms=allowed_view_forms)

@form_bp.route("/<form_key>")
@login_required
def list_forms(form_key):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    Model = config["model"]
    project_id = request.args.get("project_id", "")
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    query = Model.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    if status:
        query = query.filter_by(approval_status=status)

    entries = query.order_by(Model.created_at.desc()).all()

    if search:
        search_lower = search.lower()
        filtered_entries = []
        for entry in entries:
            text_values = [entry.project.project_name, entry.project.customer_name, entry.creator.full_name, entry.remarks or "", entry.approval_status or ""]
            if any(search_lower in str(value).lower() for value in text_values):
                filtered_entries.append(entry)
        entries = filtered_entries

    projects = get_projects()

    return render_template(
        "forms/list.html",
        form_key=form_key,
        form_title=config["title"],
        entries=entries,
        projects=projects,
        selected_project=project_id,
        selected_status=status,
        statuses=FORM_APPROVAL_STATUSES,
        search=search,
        can_create_this_form=can_create_form(current_user, form_key),
        form_reference=form_reference,
    )

@form_bp.route("/<form_key>/new", methods=["GET", "POST"])
@login_required
def create_form(form_key):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    if not can_create_form(current_user, form_key):
        flash("You do not have permission to create this form.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    Model = config["model"]

    if request.method == "POST":
        form_data = build_form_data(form_key)
        form_data["project_id"] = request.form.get("project_id")
        form_data["created_by_id"] = current_user.id
        form_data["approval_status"] = request.form.get("approval_status", "Draft")
        entry = Model(**form_data)
        db.session.add(entry)
        db.session.flush()
        log_activity("Create", config["title"], entry.id, f"Created {config['title']} #{entry.id}")
        db.session.commit()
        flash(f"{config['title']} saved successfully.", "success")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=entry.id))

    return render_template(
        "forms/form_editor.html",
        mode="create",
        form_key=form_key,
        form_title=config["title"],
        fields=get_render_fields(form_key),
        projects=get_projects(),
        values={},
        selected_project="",
        approval_status="Draft",
        form_ref=form_reference(form_key),
        field_choices=FIELD_CHOICES,
    )

@form_bp.route("/<form_key>/<int:form_id>")
@login_required
def view_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)

    histories = ApprovalHistory.query.filter_by(
        module=config["title"],
        record_id=entry.id
    ).order_by(ApprovalHistory.reviewed_at.desc()).all()

    return render_template(
        "forms/detail.html",
        form_key=form_key,
        form_title=config["title"],
        entry=entry,
        display_rows=build_display_rows(entry, form_key),
        can_edit_this_form=can_edit_form(current_user, form_key, entry),
        can_delete_this_form=can_delete_form(current_user),
        can_review_this_form=can_review_document(current_user),
        histories=histories,
        form_ref=form_reference(form_key, entry.id),
        field_choices=FIELD_CHOICES,
    )

@form_bp.route("/<form_key>/<int:form_id>/edit", methods=["GET", "POST"])
@login_required
def edit_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)

    if not can_edit_form(current_user, form_key, entry):
        flash("You do not have permission to edit this form.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

    if request.method == "POST":
        form_data = build_form_data(form_key)
        entry.project_id = request.form.get("project_id")
        for key, value in form_data.items():
            setattr(entry, key, value)
        if entry.approval_status in ["Rejected", "Need Correction"]:
            entry.approval_status = "Draft"
        db.session.commit()
        flash("Form updated successfully.", "success")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

    return render_template(
        "forms/form_editor.html",
        mode="edit",
        form_key=form_key,
        form_title=config["title"],
        fields=get_render_fields(form_key),
        projects=get_projects(),
        values=entry_to_values(entry, form_key),
        selected_project=str(entry.project_id),
        approval_status=entry.approval_status,
        form_ref=form_reference(form_key, entry.id),
        field_choices=FIELD_CHOICES,
    )


@form_bp.route("/<form_key>/<int:form_id>/submit", methods=["POST"])
@login_required
def submit_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))
    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    if not can_edit_form(current_user, form_key, entry):
        flash("You do not have permission to submit this form.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    if entry.approval_status not in ["Draft", "Need Correction", "Rejected"]:
        flash("Only Draft, Rejected, or Need Correction forms can be submitted.", "warning")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    previous_status = entry.approval_status
    entry.approval_status = "Submitted"
    log_approval(config["title"], entry.id, previous_status, "Submitted", "Submitted for approval")
    log_activity("Submit", config["title"], entry.id, f"Submitted {config['title']} #{entry.id}")
    db.session.commit()
    flash("Form submitted for approval.", "success")
    return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

@form_bp.route("/<form_key>/<int:form_id>/review", methods=["GET", "POST"])
@login_required
def review_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))
    if not can_review_document(current_user):
        flash("Only Admin, Management, or Operation Manager can review forms.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    if request.method == "POST":
        new_status = request.form.get("approval_status")
        if new_status not in ["Under Review", "Approved", "Rejected", "Need Correction"]:
            flash("Invalid review status.", "danger")
            return redirect(request.url)
        previous_status = entry.approval_status
        entry.approval_status = new_status
        entry.manager_comments = request.form.get("manager_comments")
        entry.reviewed_by_id = current_user.id
        entry.reviewed_at = datetime.utcnow()
        log_approval(config["title"], entry.id, previous_status, new_status, entry.manager_comments)
        log_activity("Review", config["title"], entry.id, f"Changed status from {previous_status} to {new_status}")
        db.session.commit()
        flash("Form review saved.", "success")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    return render_template("forms/review.html", form_key=form_key, form_title=config["title"], entry=entry)

@form_bp.route("/<form_key>/<int:form_id>/delete", methods=["POST"])
@login_required
def delete_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    if not can_delete_form(current_user):
        flash("Only Admin, Management, or Operation Manager can delete forms.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    log_activity("Delete", config["title"], entry.id, f"Deleted {config['title']} #{entry.id}")
    db.session.delete(entry)
    db.session.commit()
    flash("Form deleted successfully.", "success")
    return redirect(url_for("forms.list_forms", form_key=form_key))

@form_bp.route("/<form_key>/<int:form_id>/print")
@login_required
def print_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    return render_template(
        "forms/print.html",
        form_key=form_key,
        form_title=config["title"],
        entry=entry,
        display_rows=build_display_rows(entry, form_key),
    )
