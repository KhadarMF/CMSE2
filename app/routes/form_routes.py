from datetime import datetime, date
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.form_layouts import form_sections
from app.models import (
    Project, SiteSurveyForm, SolarPumpSurveyForm, LoadAssessmentForm, DailySiteReport,
    DeliveryNoteForm, TestingForm, CommissioningForm, HandoverForm,
    FORM_APPROVAL_STATUSES, ApprovalHistory, ProjectMilestone, Team,
)
from app.permissions import can_create_form, can_edit_form, can_delete_form, can_access_module
from app.activity import log_activity, log_approval
from app.notifications import notify_approvers, notify_user
from app.milestone_service import mark_milestone_started, invalidate_evidence
from app.team_leader_access import (
    assigned_projects_for_user, is_team_leader, led_teams_for_user,
    team_is_assigned_to_project, team_leader_can_access_daily_report,
)

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
        "title": "Solar Off-Grid Site Survey & Load Assessment", "model": SiteSurveyForm,
        "template": "forms/form_editor.html", "detail_template": "forms/detail.html",
        "fields": [
            ("survey_date", "Survey Date", "date"), ("surveyed_by", "Surveyed By", "text"),
            ("gps_coordinates", "GPS Coordinates (Optional)", "text"),
            ("existing_power_source", "Existing Power Source", "text"), ("power_supply", "Power Supply (Single / Three Phase)", "text"),
            ("monthly_consumption_kwh", "Average Monthly Consumption (kWh)", "text"),
            ("monthly_electricity_bill", "Average Monthly Electricity Bill (USD)", "text"),
            ("ac_loads", "Major Loads (AC / Pump / Motor / Other)", "textarea"),
            ("connected_load_kw", "Connected Load (kW)", "text"), ("estimated_peak_load_kw", "Estimated Peak Load (kW)", "text"),
            ("total_daily_consumption_kwh", "Total Daily Energy (kWh/day)", "text"),
            ("day_consumption_kwh", "Day Consumption (kWh/day)", "text"), ("night_consumption_kwh", "Night Consumption (kWh/night)", "text"),
            ("critical_load_kw", "Critical Load (kW)", "text"), ("critical_energy_kwh", "Critical Energy (kWh/day)", "text"),
            ("available_space", "Solar Installation Area / Available Space", "text"),
            ("roof_type", "Installation Type / Roof Type", "text"), ("roof_condition", "Roof / Installation Condition", "text"),
            ("shading_status", "Shading Condition", "text"), ("earthing_condition", "Earthing Condition", "text"),
            ("inverter_battery_location", "Proposed Inverter & Battery Location", "text"), ("access_road", "Site Access", "text"),
            ("remarks", "Surveyor Remarks / Special Requirements", "textarea"),
        ],
    },
    "solar-pump-survey": {
        "title": "Solar Pumping Site Survey", "model": SolarPumpSurveyForm,
        "template": "forms/form_editor.html", "detail_template": "forms/detail.html",
        "fields": [
            ("survey_date", "Survey Date", "date"), ("surveyed_by", "Surveyed By", "text"), ("gps_coordinates", "GPS Coordinates (Optional)", "text"),
            ("water_source", "Water Source (Borehole / Well / Surface)", "text"), ("total_depth_m", "Borehole / Well Total Depth (m)", "text"),
            ("static_water_level_m", "Static Water Level (m)", "text"), ("dynamic_water_level_m", "Dynamic Water Level (m)", "text"),
            ("required_flow_m3h", "Required Flow Rate (m³/h)", "text"), ("required_water_m3day", "Required Water per Day (m³/day)", "text"),
            ("vertical_delivery_height_m", "Vertical Delivery Height (m)", "text"), ("horizontal_pipe_distance_m", "Horizontal Pipe Distance (m)", "text"),
            ("pipe_diameter", "Pipe Diameter (inch/mm)", "text"), ("existing_pump", "Existing Pump (kW/HP, AC/DC, Phase)", "text"),
            ("tank_details", "Water Tank (Capacity & Height)", "text"), ("solar_area", "Solar Panel Installation Area", "text"),
            ("shading_status", "Shading Condition", "text"), ("access_road", "Site Access / Special Conditions", "text"),
            ("remarks", "Surveyor Remarks", "textarea"),
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
            ("report_date", "Report Date", "date"), ("site_location", "Site Location", "text"),
            ("weather", "Weather", "text"), ("site_supervisor", "Team Leader / Site Supervisor", "text"),
            ("planned_activities", "Planned Activities", "textarea"),
            ("manpower", "Manpower Details", "textarea"),
            ("employees_present", "Employees Present", "number"), ("employees_absent", "Employees Absent", "number"),
            ("normal_hours", "Normal Hours", "number"), ("overtime_hours", "Overtime Hours", "number"),
            ("work_done_today", "Work Completed Today", "textarea"),
            ("completed_quantity", "Completed Quantity", "number"), ("quantity_unit", "Quantity Unit", "text"),
            ("materials_used", "Materials Used", "textarea"), ("tools_equipment_used", "Tools / Equipment Used", "textarea"),
            ("delayed_activities", "Delayed Activities", "textarea"), ("delay_reason", "Delay Reason", "textarea"),
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


class FormValidationError(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message


def parse_date(value, field_name=None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise FormValidationError(field_name, "Enter a valid date.") from exc


def form_reference(form_key, form_id=None):
    prefixes = {
        "site-survey": "SSLA", "solar-pump-survey": "SPS", "load-assessment": "LAF", "daily-site-report": "DSR",
        "delivery-note": "DNF", "testing": "TST", "commissioning": "COM", "handover": "HOF",
    }
    prefix = prefixes.get(form_key, "FRM")
    return f"{prefix}-{int(form_id or 0):05d}" if form_id else f"{prefix}-AUTO"

def get_render_fields(form_key):
    render_fields = []
    for field_name, label, field_type in FORM_CONFIG[form_key]["fields"]:
        render_fields.append((field_name, label, get_field_type(field_name, field_type)))
    return render_fields

def daily_report_self_service_mode():
    return is_team_leader(current_user) and current_user.role not in {
        "Admin", "Management", "Operation Manager"
    }


def get_projects(form_key=None):
    if form_key == "daily-site-report" and daily_report_self_service_mode():
        return assigned_projects_for_user(current_user)
    return Project.query.order_by(Project.project_name.asc()).all()


def get_daily_report_teams():
    if daily_report_self_service_mode():
        return led_teams_for_user(current_user)
    return Team.query.filter_by(status="Active").order_by(Team.team_name.asc()).all()


def get_milestones(form_key=None):
    if form_key != "daily-site-report":
        return []
    query = ProjectMilestone.query
    if daily_report_self_service_mode():
        project_ids = [project.id for project in assigned_projects_for_user(current_user)]
        if not project_ids:
            return []
        query = query.filter(ProjectMilestone.project_id.in_(project_ids))
    return query.order_by(ProjectMilestone.project_id, ProjectMilestone.sequence).all()


def can_create_requested_form(form_key):
    return can_create_form(current_user, form_key) or (
        form_key == "daily-site-report" and is_team_leader(current_user)
    )


def can_access_daily_entry(entry, action="view"):
    if can_access_module(current_user, "daily-site-report", action):
        return True
    if action not in {"view", "create", "edit", "print_export"}:
        return False
    if not team_leader_can_access_daily_report(current_user, entry):
        return False
    if action == "edit":
        return entry.approval_status in {"Draft", "Need Correction", "Rejected"}
    return True


def validate_daily_report_scope(project_id, team_id, report_date, exclude_id=None):
    try:
        project_key = int(project_id)
        team_key = int(team_id)
    except (TypeError, ValueError):
        return "Project and Team are required."
    project = db.session.get(Project, project_key)
    team = db.session.get(Team, team_key)
    if not project or not team:
        return "Project and Team are required."
    if daily_report_self_service_mode():
        led_ids = {item.id for item in led_teams_for_user(current_user)}
        if team.id not in led_ids:
            return "You can only report for a team you lead."
    if not team_is_assigned_to_project(team, project):
        return "The selected team is not assigned to that project."
    if not report_date:
        return "Report Date is required."
    duplicate = DailySiteReport.query.filter_by(
        project_id=project.id, team_id=team.id, report_date=report_date
    )
    if exclude_id:
        duplicate = duplicate.filter(DailySiteReport.id != exclude_id)
    if duplicate.first():
        return "A daily report already exists for this team, project, and date."
    return None

def get_counts():
    return {
        "site_surveys": SiteSurveyForm.query.count(),
        "solar_pump_surveys": SolarPumpSurveyForm.query.count(),
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
            form_data[field_name] = parse_date(value, field_name)
        else:
            form_data[field_name] = value
    return form_data


def lock_form_project(project_id):
    """Serialize duplicate checks, including on SQLite where FOR UPDATE is ignored."""
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        raise ValueError("Select a valid project.")
    result = db.session.execute(
        update(Project).where(Project.id == project_id).values(id=Project.id)
    )
    if result.rowcount != 1:
        raise ValueError("Select a valid project.")
    return project_id

def entry_to_values(entry, form_key):
    values = {}
    for field_name, label, field_type in FORM_CONFIG[form_key]["fields"]:
        value = getattr(entry, field_name, "")
        if field_type == "date" and value:
            value = value.strftime("%Y-%m-%d")
        values[field_name] = value or ""
    return values


def request_to_values(form_key):
    return {
        field_name: request.form.get(field_name, "")
        for field_name, _, _ in FORM_CONFIG[form_key]["fields"]
    }


def required_form_fields(form_key):
    if form_key == "daily-site-report":
        return {"report_date", "work_done_today"}
    return set()


def render_form_editor(form_key, mode, config, values, selected_project="", selected_team="",
                       selected_milestone="", approval_status="Draft", form_ref=None,
                       invalid_fields=None, status_code=200):
    response = render_template(
        "forms/form_editor.html",
        mode=mode,
        form_key=form_key,
        form_title=config["title"],
        fields=get_render_fields(form_key),
        sections=form_sections(form_key, get_render_fields(form_key)),
        projects=get_projects(form_key),
        daily_teams=get_daily_report_teams() if form_key == "daily-site-report" else [],
        milestones=get_milestones(form_key),
        daily_report_mode=form_key == "daily-site-report",
        team_leader_mode=daily_report_self_service_mode() if form_key == "daily-site-report" else False,
        selected_team=selected_team,
        selected_milestone=selected_milestone,
        values=values,
        selected_project=selected_project,
        approval_status=approval_status,
        form_ref=form_ref or form_reference(form_key),
        field_choices=FIELD_CHOICES,
        invalid_fields=invalid_fields or {},
        required_fields=required_form_fields(form_key),
    )
    return response, status_code


def render_post_error(form_key, mode, config, message, field=None, form_ref=None, status_code=400):
    db.session.rollback()
    flash(message, "danger")
    selected_project = request.form.get("project_id", "")
    selected_team = request.form.get("team_id", "") if form_key == "daily-site-report" else ""
    selected_milestone = request.form.get("milestone_id", "") if form_key == "daily-site-report" else ""
    approval_status = request.form.get("approval_status", "Draft")
    invalid_fields = {field: message} if field else {}
    return render_form_editor(
        form_key, mode, config, request_to_values(form_key),
        selected_project=selected_project,
        selected_team=selected_team,
        selected_milestone=selected_milestone,
        approval_status=approval_status,
        form_ref=form_ref,
        invalid_fields=invalid_fields,
        status_code=status_code,
    )

def build_display_rows(entry, form_key):
    display_rows = []
    if form_key == "daily-site-report":
        display_rows.append(("Team", entry.team.team_name if entry.team else ""))
        display_rows.append(("Milestone", entry.milestone.name if entry.milestone else "Not linked"))
    for field_name, label, field_type in FORM_CONFIG[form_key]["fields"]:
        value = getattr(entry, field_name, "")
        display_rows.append((label, value or ""))
    if form_key == "site-survey":
        # The concise editor must not hide measurements recorded by older releases.
        current_fields = {field[0] for field in FORM_CONFIG[form_key]["fields"]}
        legacy_fields = [("site_name", "Site Name"), ("recommendation", "Recommendation")]
        legacy_fields += [(name, label) for name, label, _ in FORM_CONFIG["load-assessment"]["fields"]]
        for name, label in legacy_fields:
            value = getattr(entry, name, None)
            if name not in current_fields and value not in (None, ""):
                display_rows.append((f"Legacy: {label}", value))
    return display_rows

@form_bp.route("/")
@login_required
def forms_home():
    allowed_create_forms = {key: can_create_form(current_user, key) for key in FORM_CONFIG.keys()}
    allowed_view_forms = {key: can_create_form(current_user, key) or can_create_form(current_user, key) for key in FORM_CONFIG.keys()}
    # Correct view permissions are controlled separately.
    from app.permissions import can_view_form
    allowed_view_forms = {key: can_view_form(current_user, key) for key in FORM_CONFIG.keys()}
    if is_team_leader(current_user):
        allowed_create_forms["daily-site-report"] = True
        allowed_view_forms["daily-site-report"] = True
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
    if form_key == "daily-site-report" and daily_report_self_service_mode():
        led_ids = {team.id for team in led_teams_for_user(current_user)}
        query = query.filter(DailySiteReport.team_id.in_(led_ids))
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

    projects = get_projects(form_key)

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
        can_create_this_form=can_create_requested_form(form_key),
        form_reference=form_reference,
    )

@form_bp.route("/<form_key>/new", methods=["GET", "POST"])
@login_required
def create_form(form_key):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    if not can_create_requested_form(form_key):
        flash("You do not have permission to create this form.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    Model = config["model"]

    if request.method == "POST":
        try:
            form_data = build_form_data(form_key)
        except FormValidationError as exc:
            return render_post_error(form_key, "create", config, exc.message, exc.field)
        try:
            form_data["project_id"] = lock_form_project(request.form.get("project_id"))
        except ValueError:
            return render_post_error(form_key, "create", config, "Select a valid project.", "project_id")
        form_data["created_by_id"] = current_user.id
        form_data["approval_status"] = request.form.get("approval_status", "Draft")
        if form_data["approval_status"] not in {"Draft", "Submitted"}:
            return render_post_error(form_key, "create", config, "New forms must be Draft or Submitted for approval.", "approval_status")
        if form_key not in {"daily-site-report", "load-assessment"}:
            existing = Model.query.filter_by(project_id=form_data["project_id"]).first()
            if existing:
                flash(f"This project already has a {config['title']}. Open and edit the existing form instead of creating another one.", "warning")
                return redirect(url_for("forms.view_form", form_key=form_key, form_id=existing.id))
        if form_key == "daily-site-report":
            form_data["team_id"] = request.form.get("team_id") or None
            form_data["milestone_id"] = request.form.get("milestone_id") or None
            if form_data["milestone_id"] and not ProjectMilestone.query.filter_by(id=form_data["milestone_id"], project_id=form_data["project_id"]).first():
                return render_post_error(form_key, "create", config, "Selected milestone does not belong to this project.", "milestone_id")
            if daily_report_self_service_mode():
                form_data["site_supervisor"] = current_user.full_name
            error = validate_daily_report_scope(
                form_data["project_id"], form_data["team_id"], form_data.get("report_date")
            )
            if error:
                field = "team_id" if "Team" in error or "team" in error else "report_date"
                return render_post_error(form_key, "create", config, error, field)
            if not (form_data.get("work_done_today") or "").strip():
                return render_post_error(form_key, "create", config, "Work Completed Today is required.", "work_done_today")
        entry = Model(**form_data)
        db.session.add(entry)
        db.session.flush()
        if form_key == "daily-site-report":
            mark_milestone_started(entry.milestone_id)
        log_activity("Create", config["title"], entry.id, f"Created {config['title']} #{entry.id}")
        if entry.approval_status == "Submitted":
            notify_approvers(form_key,
                subject=f"{config['title']} {form_reference(form_key, entry.id)} submitted",
                message=f"{current_user.full_name} submitted {config['title']} for {entry.project.project_name}. Open Project Forms to review {form_reference(form_key, entry.id)}.",
                record_id=entry.id, exclude_user_id=entry.created_by_id)
        db.session.commit()
        flash(f"{config['title']} saved successfully.", "success")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=entry.id))

    initial_values = {}
    if form_key == "daily-site-report":
        initial_values = {
            "report_date": date.today().isoformat(),
            "site_supervisor": current_user.full_name if daily_report_self_service_mode() else "",
        }

    return render_form_editor(
        form_key,
        "create",
        config,
        initial_values,
        selected_project=request.args.get("project_id", ""),
        selected_team=request.args.get("team_id", ""),
        selected_milestone=request.args.get("milestone_id", ""),
        approval_status="Draft",
        form_ref=form_reference(form_key),
    )

@form_bp.route("/<form_key>/<int:form_id>")
@login_required
def view_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    if form_key == "daily-site-report" and not can_access_daily_entry(entry, "view"):
        flash("You can only view daily reports for a team you lead.", "danger")
        return redirect(url_for("forms.list_forms", form_key=form_key))

    history_modules = [config["title"]]
    if form_key == "site-survey":
        history_modules.extend(["Site Survey & Load Assessment", "Site Survey Form"])
    histories = ApprovalHistory.query.filter(
        ApprovalHistory.module.in_(history_modules), ApprovalHistory.record_id == entry.id
    ).order_by(ApprovalHistory.reviewed_at.desc()).all()

    return render_template(
        "forms/detail.html",
        form_key=form_key,
        form_title=config["title"],
        entry=entry,
        display_rows=build_display_rows(entry, form_key),
        can_edit_this_form=(can_access_daily_entry(entry, "edit") if form_key == "daily-site-report" else can_edit_form(current_user, form_key, entry)),
        can_delete_this_form=can_access_module(current_user, form_key, "delete"),
        can_review_this_form=(
            can_access_module(current_user, form_key, "approve")
            and entry.created_by_id != current_user.id
        ),
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

    allowed_to_edit = can_access_daily_entry(entry, "edit") if form_key == "daily-site-report" else can_edit_form(current_user, form_key, entry)
    if not allowed_to_edit:
        flash("You do not have permission to edit this form.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

    if request.method == "POST":
        try:
            form_data = build_form_data(form_key)
        except FormValidationError as exc:
            return render_post_error(form_key, "edit", config, exc.message, exc.field, form_ref=form_reference(form_key, entry.id))
        try:
            new_project_id = lock_form_project(request.form.get("project_id"))
        except ValueError:
            return render_post_error(form_key, "edit", config, "Select a valid project.", "project_id", form_ref=form_reference(form_key, entry.id))
        if form_key not in {"daily-site-report", "load-assessment"}:
            duplicate = config["model"].query.filter_by(project_id=new_project_id).filter(config["model"].id != entry.id).first()
            if duplicate:
                flash("The selected project already has this form. Edit its existing record.", "danger")
                return redirect(url_for("forms.edit_form", form_key=form_key, form_id=form_id))
        if form_key == "daily-site-report":
            new_team_id = request.form.get("team_id") or None
            new_milestone_id = request.form.get("milestone_id") or None
            if new_milestone_id and not ProjectMilestone.query.filter_by(id=new_milestone_id, project_id=new_project_id).first():
                return render_post_error(form_key, "edit", config, "Selected milestone does not belong to this project.", "milestone_id", form_ref=form_reference(form_key, entry.id))
            if daily_report_self_service_mode():
                form_data["site_supervisor"] = current_user.full_name
            error = validate_daily_report_scope(
                new_project_id, new_team_id, form_data.get("report_date"), exclude_id=entry.id
            )
            if error:
                field = "team_id" if "Team" in error or "team" in error else "report_date"
                return render_post_error(form_key, "edit", config, error, field, form_ref=form_reference(form_key, entry.id))
            if not (form_data.get("work_done_today") or "").strip():
                return render_post_error(form_key, "edit", config, "Work Completed Today is required.", "work_done_today", form_ref=form_reference(form_key, entry.id))
            entry.team_id = new_team_id
            entry.milestone_id = new_milestone_id
            mark_milestone_started(entry.milestone_id)
        invalidate_evidence(entry.project, current_user, form_key=form_key, record_id=entry.id)
        entry.project_id = new_project_id
        for key, value in form_data.items():
            setattr(entry, key, value)
        if entry.approval_status != "Draft":
            log_approval(config["title"], entry.id, entry.approval_status, "Draft", "Content edited; a new review is required.")
            entry.approval_status = "Draft"
        entry.reviewed_by_id = None
        entry.reviewed_at = None
        entry.manager_comments = None
        log_activity("Edit", config["title"], entry.id, "Updated form; saved as Draft.")
        db.session.commit()
        flash("Form updated successfully.", "success")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

    return render_form_editor(
        form_key,
        "edit",
        config,
        entry_to_values(entry, form_key),
        selected_team=str(entry.team_id or "") if form_key == "daily-site-report" else "",
        selected_milestone=str(entry.milestone_id or "") if form_key == "daily-site-report" else "",
        selected_project=str(entry.project_id),
        approval_status=entry.approval_status,
        form_ref=form_reference(form_key, entry.id),
    )


@form_bp.route("/<form_key>/<int:form_id>/submit", methods=["POST"])
@login_required
def submit_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))
    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    allowed_to_submit = can_access_daily_entry(entry, "edit") if form_key == "daily-site-report" else can_edit_form(current_user, form_key, entry)
    if not allowed_to_submit:
        flash("You do not have permission to submit this form.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    if entry.approval_status not in ["Draft", "Need Correction", "Rejected"]:
        flash("Only Draft, Rejected, or Need Correction forms can be submitted.", "warning")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    previous_status = entry.approval_status
    entry.approval_status = "Submitted"
    log_approval(config["title"], entry.id, previous_status, "Submitted", "Submitted for approval")
    log_activity("Submit", config["title"], entry.id, f"Submitted {config['title']} #{entry.id}")
    notify_approvers(form_key,
        subject=f"{config['title']} {form_reference(form_key, entry.id)} submitted",
        message=f"{current_user.full_name} submitted {config['title']} for {entry.project.project_name}. Open Project Forms to review {form_reference(form_key, entry.id)}.",
        record_id=entry.id, exclude_user_id=entry.created_by_id)
    db.session.commit()
    flash("Form submitted for approval.", "success")
    return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

@form_bp.route("/<form_key>/<int:form_id>/review", methods=["GET", "POST"])
@login_required
def review_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))
    if not can_access_module(current_user, form_key, "approve"):
        flash("Only Admin, Management, or Operation Manager can review forms.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    config = FORM_CONFIG[form_key]
    entry = config["model"].query.get_or_404(form_id)
    if entry.created_by_id == current_user.id:
        flash("A report creator cannot approve their own report.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
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
        if previous_status != new_status:
            notify_user(entry.creator,
                subject=f"{config['title']} {form_reference(form_key, entry.id)}: {new_status}",
                message=entry.manager_comments or f"Your form is now {new_status}.",
                module=form_key, record_id=entry.id)
        db.session.commit()
        flash("Form review saved.", "success")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))
    return render_template("forms/review.html", form_key=form_key, form_title=config["title"], entry=entry)

@form_bp.route("/<form_key>/<int:form_id>/delete", methods=["GET", "POST"])
@login_required
def delete_form(form_key, form_id):
    if form_key not in FORM_CONFIG:
        flash("Invalid form type.", "danger")
        return redirect(url_for("forms.forms_home"))

    config = FORM_CONFIG[form_key]
    entry = db.session.get(config["model"], form_id)
    if entry is None:
        flash("That form has already been deleted or no longer exists.", "warning")
        return redirect(url_for("forms.list_forms", form_key=form_key))

    if not can_access_module(current_user, form_key, "delete"):
        flash("Only Admin, Management, or Operation Manager can delete forms.", "danger")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

    if request.method != "POST":
        flash("Use the Delete Form button to confirm deletion.", "warning")
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

    project = entry.project
    record_id = entry.id
    try:
        if project is not None:
            invalidate_evidence(project, current_user, form_key=form_key, record_id=record_id)
            for milestone in list(project.milestones or []):
                for requirement in list(milestone.document_requirements or []):
                    if requirement.form_key == form_key and requirement.form_record_id == record_id:
                        requirement.form_record_id = None
        log_activity("Delete", config["title"], record_id, f"Deleted {config['title']} #{record_id}")
        db.session.delete(entry)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to delete %s form %s: %s", form_key, form_id, exc
        )
        flash(
            "The form could not be deleted because linked workflow history still needs cleanup. "
            "Please try again; if it repeats, contact the system administrator.",
            "danger",
        )
        return redirect(url_for("forms.view_form", form_key=form_key, form_id=form_id))

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
    if form_key == "daily-site-report" and not can_access_daily_entry(entry, "print_export"):
        flash("You can only print daily reports for a team you lead.", "danger")
        return redirect(url_for("forms.list_forms", form_key=form_key))
    return render_template(
        "forms/print.html",
        form_key=form_key,
        form_title=config["title"],
        entry=entry,
        display_rows=build_display_rows(entry, form_key),
    )

