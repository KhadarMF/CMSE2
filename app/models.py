from datetime import datetime
from flask_login import UserMixin
from app import db

ROLES = [
    "Admin", "Management", "Operation Manager", "Technical Engineer",
    "Site Supervisor", "Warehouse Officer", "Transport Officer",
    "Sales Officer", "Finance Officer",
]

PROJECT_STATUSES = [
    "New", "Survey", "Design", "Approved", "Installation",
    "Testing", "Commissioning", "Handover", "Completed",
]

DOCUMENT_TYPES = [
    "Site Survey Form", "Load Assessment", "Technical Design", "BOQ",
    "Quotation", "Contract", "Delivery Note", "Daily Site Report",
    "Testing Report", "Commissioning Form", "Handover Certificate",
    "Warranty Document",
]

APPROVAL_STATUSES = [
    "Draft", "Submitted", "Under Review", "Approved", "Rejected", "Need Correction",
]

FORM_APPROVAL_STATUSES = [
    "Draft", "Submitted", "Under Review", "Approved", "Rejected", "Need Correction",
]

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)

    branch = db.relationship("Branch", foreign_keys=[branch_id])
    department = db.relationship("Department", foreign_keys=[department_id])

    projects_created = db.relationship("Project", backref="creator", lazy=True)
    documents_uploaded = db.relationship("Document", backref="uploader", lazy=True, foreign_keys="Document.uploaded_by_id")

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False)
    customer_name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    project_type = db.Column(db.String(120), nullable=False)
    capacity = db.Column(db.String(80), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    expected_completion_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(80), default="New")
    assigned_team = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documents = db.relationship("Document", backref="project", lazy=True, cascade="all, delete-orphan")
    site_surveys = db.relationship("SiteSurveyForm", backref="project", lazy=True, cascade="all, delete-orphan")
    load_assessments = db.relationship("LoadAssessmentForm", backref="project", lazy=True, cascade="all, delete-orphan")
    daily_reports = db.relationship("DailySiteReport", backref="project", lazy=True, cascade="all, delete-orphan")
    delivery_notes = db.relationship("DeliveryNoteForm", backref="project", lazy=True, cascade="all, delete-orphan")
    testing_forms = db.relationship("TestingForm", backref="project", lazy=True, cascade="all, delete-orphan")
    commissioning_forms = db.relationship("CommissioningForm", backref="project", lazy=True, cascade="all, delete-orphan")
    handover_forms = db.relationship("HandoverForm", backref="project", lazy=True, cascade="all, delete-orphan")

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    document_title = db.Column(db.String(200), nullable=False)
    document_type = db.Column(db.String(120), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    file_name = db.Column(db.String(255), nullable=False)
    stored_file_name = db.Column(db.String(255), nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])

class SiteSurveyForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])
    site_name = db.Column(db.String(200))
    survey_date = db.Column(db.Date)
    surveyed_by = db.Column(db.String(150))
    gps_coordinates = db.Column(db.String(150))
    roof_type = db.Column(db.String(120))
    roof_condition = db.Column(db.String(120))
    available_space = db.Column(db.String(120))
    shading_status = db.Column(db.String(120))
    existing_power_source = db.Column(db.String(150))
    earthing_condition = db.Column(db.String(150))
    access_road = db.Column(db.String(150))
    # Phase 15K: combined Site Survey & Load Assessment fields
    assessment_date = db.Column(db.Date)
    assessed_by = db.Column(db.String(150))
    daytime_load_kw = db.Column(db.String(80))
    nighttime_load_kw = db.Column(db.String(80))
    total_daily_consumption_kwh = db.Column(db.String(80))
    critical_loads = db.Column(db.Text)
    ac_loads = db.Column(db.Text)
    pump_loads = db.Column(db.Text)
    lighting_loads = db.Column(db.Text)
    backup_hours_required = db.Column(db.String(80))
    recommended_system_size = db.Column(db.String(120))
    recommendation = db.Column(db.Text)
    remarks = db.Column(db.Text)
    creator = db.relationship("User", foreign_keys=[created_by_id])

class LoadAssessmentForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])
    assessment_date = db.Column(db.Date)
    assessed_by = db.Column(db.String(150))
    daytime_load_kw = db.Column(db.String(80))
    nighttime_load_kw = db.Column(db.String(80))
    total_daily_consumption_kwh = db.Column(db.String(80))
    critical_loads = db.Column(db.Text)
    ac_loads = db.Column(db.Text)
    pump_loads = db.Column(db.Text)
    lighting_loads = db.Column(db.Text)
    backup_hours_required = db.Column(db.String(80))
    recommended_system_size = db.Column(db.String(120))
    remarks = db.Column(db.Text)
    creator = db.relationship("User", foreign_keys=[created_by_id])

class DailySiteReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])
    report_date = db.Column(db.Date)
    site_supervisor = db.Column(db.String(150))
    manpower = db.Column(db.Text)
    work_done_today = db.Column(db.Text)
    materials_used = db.Column(db.Text)
    tools_equipment_used = db.Column(db.Text)
    issues_challenges = db.Column(db.Text)
    safety_notes = db.Column(db.Text)
    next_day_plan = db.Column(db.Text)
    progress_percentage = db.Column(db.String(50))
    remarks = db.Column(db.Text)
    creator = db.relationship("User", foreign_keys=[created_by_id])

class DeliveryNoteForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])
    delivery_date = db.Column(db.Date)
    delivered_by = db.Column(db.String(150))
    received_by = db.Column(db.String(150))
    vehicle_plate = db.Column(db.String(80))
    delivery_location = db.Column(db.String(200))
    items_delivered = db.Column(db.Text)
    quantity_summary = db.Column(db.Text)
    condition_of_items = db.Column(db.String(150))
    receiver_comments = db.Column(db.Text)
    remarks = db.Column(db.Text)
    creator = db.relationship("User", foreign_keys=[created_by_id])

class TestingForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])
    testing_date = db.Column(db.Date)
    tested_by = db.Column(db.String(150))
    inverter_status = db.Column(db.String(120))
    pv_voltage = db.Column(db.String(80))
    battery_voltage = db.Column(db.String(80))
    output_voltage = db.Column(db.String(80))
    load_test_result = db.Column(db.String(150))
    protection_test_result = db.Column(db.String(150))
    faults_found = db.Column(db.Text)
    corrective_actions = db.Column(db.Text)
    test_result = db.Column(db.String(80))
    remarks = db.Column(db.Text)
    creator = db.relationship("User", foreign_keys=[created_by_id])

class CommissioningForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])
    commissioning_date = db.Column(db.Date)
    commissioned_by = db.Column(db.String(150))
    system_capacity = db.Column(db.String(100))
    inverter_model = db.Column(db.String(150))
    battery_model = db.Column(db.String(150))
    pv_array_details = db.Column(db.Text)
    battery_settings = db.Column(db.Text)
    inverter_settings = db.Column(db.Text)
    monitoring_setup = db.Column(db.String(150))
    client_training_done = db.Column(db.String(20))
    commissioning_status = db.Column(db.String(80))
    remarks = db.Column(db.Text)
    creator = db.relationship("User", foreign_keys=[created_by_id])

class HandoverForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approval_status = db.Column(db.String(80), default="Draft")
    manager_comments = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])
    handover_date = db.Column(db.Date)
    handed_over_by = db.Column(db.String(150))
    received_by = db.Column(db.String(150))
    documents_handed_over = db.Column(db.Text)
    spare_parts_handed_over = db.Column(db.Text)
    training_provided = db.Column(db.String(20))
    warranty_explained = db.Column(db.String(20))
    client_comments = db.Column(db.Text)
    final_status = db.Column(db.String(80))
    remarks = db.Column(db.Text)
    creator = db.relationship("User", foreign_keys=[created_by_id])


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    module = db.Column(db.String(120), nullable=False)
    record_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", foreign_keys=[user_id])

class ApprovalHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(120), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    previous_status = db.Column(db.String(80), nullable=True)
    new_status = db.Column(db.String(80), nullable=False)
    comments = db.Column(db.Text, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    recipient_email = db.Column(db.String(150), nullable=True)
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    module = db.Column(db.String(120), nullable=True)
    record_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(50), default="Pending")
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    recipient = db.relationship("User", foreign_keys=[recipient_user_id])

class DocumentVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    stored_file_name = db.Column(db.String(255), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    remarks = db.Column(db.Text, nullable=True)
    document = db.relationship("Document", backref=db.backref("versions", lazy=True, cascade="all, delete-orphan"))
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])


class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(120), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_name = db.Column(db.String(150), unique=True, nullable=False)
    location = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Phase 9 Models: Project Tasks and Issue/Risk Tracker
TASK_STATUSES = ["Not Started", "In Progress", "Waiting", "Completed", "Cancelled"]
TASK_PRIORITIES = ["Low", "Normal", "High", "Urgent"]
ISSUE_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]
ISSUE_SEVERITIES = ["Low", "Medium", "High", "Critical"]

class ProjectTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # Legacy field kept for backward compatibility with older tasks.
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    # Phase 14E: actual task performer should be an employee, not necessarily a login user.
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=True)
    supervisor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(80), default="Not Started")
    priority = db.Column(db.String(80), default="Normal")
    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    progress_percent = db.Column(db.Integer, default=0)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = db.relationship("Project", backref=db.backref("tasks", lazy=True, cascade="all, delete-orphan"))
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    assigned_employee = db.relationship("Employee", foreign_keys=[assigned_employee_id])
    supervisor_user = db.relationship("User", foreign_keys=[supervisor_user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    @property
    def is_overdue(self):
        if not self.due_date or self.status in ["Completed", "Cancelled"]:
            return False
        return self.due_date < datetime.utcnow().date()

class ProjectIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    issue_type = db.Column(db.String(120), default="General")
    severity = db.Column(db.String(80), default="Medium")
    status = db.Column(db.String(80), default="Open")
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reported_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reported_at = db.Column(db.DateTime, default=datetime.utcnow)
    target_resolution_date = db.Column(db.Date, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    project = db.relationship("Project", backref=db.backref("issues", lazy=True, cascade="all, delete-orphan"))
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])
    reported_by = db.relationship("User", foreign_keys=[reported_by_id])

    @property
    def is_overdue(self):
        if not self.target_resolution_date or self.status in ["Resolved", "Closed"]:
            return False
        return self.target_resolution_date < datetime.utcnow().date()


# Phase 11 Models: Customers, Employees, Teams and Project Workforce
EMPLOYEE_STATUSES = ["Active", "Inactive", "On Leave"]
EMPLOYEE_TYPES = ["Full-time", "Part-time", "Contract", "Temporary"]
TEAM_STATUSES = ["Active", "Inactive"]
PROJECT_WORK_STATUSES = ["Planned", "Active", "Completed", "Removed"]

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200), unique=True, nullable=False)
    contact_person = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    address = db.Column(db.String(250), nullable=True)
    customer_type = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def projects(self):
        return Project.query.filter(Project.customer_name == self.customer_name).order_by(Project.created_at.desc()).all()

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(80), unique=True, nullable=True)
    full_name = db.Column(db.String(150), nullable=False)
    job_title = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    employee_type = db.Column(db.String(80), default="Full-time")
    status = db.Column(db.String(80), default="Active")
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    branch = db.relationship("Branch", foreign_keys=[branch_id])
    department = db.relationship("Department", foreign_keys=[department_id])
    user_account = db.relationship("User", foreign_keys=[user_id])

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(150), unique=True, nullable=False)
    team_type = db.Column(db.String(120), nullable=True)
    leader_employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    status = db.Column(db.String(80), default="Active")
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    leader = db.relationship("Employee", foreign_keys=[leader_employee_id])
    branch = db.relationship("Branch", foreign_keys=[branch_id])
    department = db.relationship("Department", foreign_keys=[department_id])

class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    member_role = db.Column(db.String(120), nullable=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    team = db.relationship("Team", backref=db.backref("members", lazy=True, cascade="all, delete-orphan"))
    employee = db.relationship("Employee")

class ProjectTeamAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    work_scope = db.Column(db.String(200), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(80), default="Active")
    remarks = db.Column(db.Text, nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", backref=db.backref("team_assignments", lazy=True, cascade="all, delete-orphan"))
    team = db.relationship("Team")

class ProjectEmployeeAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    role_on_project = db.Column(db.String(150), nullable=True)
    work_scope = db.Column(db.String(200), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(80), default="Active")
    remarks = db.Column(db.Text, nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", backref=db.backref("employee_assignments", lazy=True, cascade="all, delete-orphan"))
    employee = db.relationship("Employee")


# Phase 12 Models: Project Payroll / Employee Project Salary Accounting
PAYROLL_PERIOD_STATUSES = ["Open", "Locked", "Paid", "Closed"]
PAYROLL_ENTRY_STATUSES = ["Draft", "Submitted", "Approved", "Partially Paid", "Paid", "Closed"]
PAYMENT_METHODS = ["Cash", "Zaad", "E-Dahab", "Bank Transfer", "Cheque", "Other"]

class PayrollPeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    period_name = db.Column(db.String(120), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), default="Open")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    entries = db.relationship("EmployeeProjectPayroll", backref="period", lazy=True, cascade="all, delete-orphan")
    @property
    def total_due(self): return sum(e.total_due for e in self.entries)
    @property
    def total_paid(self): return sum(e.total_paid for e in self.entries)
    @property
    def total_balance(self): return sum(e.balance for e in self.entries)

class EmployeeProjectPayroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey("payroll_period.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    role_on_project = db.Column(db.String(150), nullable=True)
    work_description = db.Column(db.String(250), nullable=True)
    work_days = db.Column(db.Float, default=0)
    salary_amount = db.Column(db.Float, default=0)
    allowance_amount = db.Column(db.Float, default=0)
    deduction_amount = db.Column(db.Float, default=0)
    previous_balance = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default="Draft")
    manager_notes = db.Column(db.Text, nullable=True)
    finance_notes = db.Column(db.Text, nullable=True)
    entered_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    employee = db.relationship("Employee")
    project = db.relationship("Project", backref=db.backref("payroll_entries", lazy=True, cascade="all, delete-orphan"))
    entered_by = db.relationship("User", foreign_keys=[entered_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    payments = db.relationship("PayrollPayment", backref="payroll_entry", lazy=True, cascade="all, delete-orphan")
    @property
    def current_month_due(self): return float(self.salary_amount or 0) + float(self.allowance_amount or 0) - float(self.deduction_amount or 0)
    @property
    def total_due(self): return float(self.previous_balance or 0) + self.current_month_due
    @property
    def total_paid(self): return sum(float(p.amount or 0) for p in self.payments)
    @property
    def balance(self): return self.total_due - self.total_paid

class PayrollPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payroll_entry_id = db.Column(db.Integer, db.ForeignKey("employee_project_payroll.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(80), default="Cash")
    reference_no = db.Column(db.String(120), nullable=True)
    paid_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_by = db.relationship("User", foreign_keys=[paid_by_id])

# Phase 13 Models: Project-based Payroll with Bulk/Batch Entry
PROJECT_PAYROLL_BATCH_STATUSES = ["Draft", "Submitted", "Approved", "Partially Paid", "Paid", "Closed"]
PROJECT_PAYROLL_ENTRY_STATUSES = ["Pending", "Approved", "Partially Paid", "Paid", "Cancelled"]
PROJECT_PAYMENT_METHODS = ["Cash", "Zaad", "E-Dahab", "Bank Transfer", "Cheque", "Other"]

class ProjectPayrollBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_no = db.Column(db.String(120), unique=True, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    work_date = db.Column(db.Date, nullable=True)
    batch_title = db.Column(db.String(180), nullable=False)
    work_scope = db.Column(db.String(250), nullable=True)
    status = db.Column(db.String(80), default="Draft")
    manager_notes = db.Column(db.Text, nullable=True)
    finance_notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)

    project = db.relationship("Project", backref=db.backref("project_payroll_batches", lazy=True, cascade="all, delete-orphan"))
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])

    @property
    def total_due(self):
        return sum(e.total_due for e in self.entries)

    @property
    def total_paid(self):
        return sum(e.total_paid for e in self.entries)

    @property
    def balance(self):
        return self.total_due - self.total_paid

class ProjectPayrollEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("project_payroll_batch.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    role_on_project = db.Column(db.String(150), nullable=True)
    work_description = db.Column(db.String(250), nullable=True)
    work_days = db.Column(db.Float, default=1)
    project_amount = db.Column(db.Float, default=0)
    allowance_amount = db.Column(db.Float, default=0)
    deduction_amount = db.Column(db.Float, default=0)
    previous_balance = db.Column(db.Float, default=0)
    status = db.Column(db.String(80), default="Pending")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    batch = db.relationship("ProjectPayrollBatch", backref=db.backref("entries", lazy=True, cascade="all, delete-orphan"))
    employee = db.relationship("Employee")

    @property
    def current_due(self):
        return float(self.project_amount or 0) + float(self.allowance_amount or 0) - float(self.deduction_amount or 0)

    @property
    def total_due(self):
        return float(self.previous_balance or 0) + self.current_due

    @property
    def total_paid(self):
        return sum(float(p.amount or 0) for p in self.payments)

    @property
    def balance(self):
        return self.total_due - self.total_paid

class ProjectPayrollPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payroll_entry_id = db.Column(db.Integer, db.ForeignKey("project_payroll_entry.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(80), default="Cash")
    reference_no = db.Column(db.String(120), nullable=True)
    paid_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entry = db.relationship("ProjectPayrollEntry", backref=db.backref("payments", lazy=True, cascade="all, delete-orphan"))
    paid_by = db.relationship("User", foreign_keys=[paid_by_id])



# Phase 13B Model: Project Type master list
class ProjectType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Phase 14A Models: Project Materials, Warehouse Issue and Returns
MATERIAL_DOC_STATUSES = ["Draft", "Submitted", "Approved", "Issued", "Partially Issued", "Returned", "Closed", "Cancelled"]

class MaterialItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(80), unique=True, nullable=True)
    item_name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(120), nullable=True)
    unit_cost = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MaterialRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    request_date = db.Column(db.Date, nullable=True)
    purpose = db.Column(db.String(250), nullable=True)
    status = db.Column(db.String(80), default="Draft")
    requested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    project = db.relationship("Project", backref=db.backref("material_requests", lazy=True, cascade="all, delete-orphan"))
    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    @property
    def total_estimated_cost(self):
        return sum(line.estimated_cost for line in self.lines)

class MaterialRequestLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("material_request.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("material_item.id"), nullable=True)
    item_name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity_requested = db.Column(db.Float, default=0)
    unit = db.Column(db.String(50), nullable=True)
    estimated_unit_cost = db.Column(db.Float, default=0)
    remarks = db.Column(db.Text, nullable=True)
    request = db.relationship("MaterialRequest", backref=db.backref("lines", lazy=True, cascade="all, delete-orphan"))
    item = db.relationship("MaterialItem")
    @property
    def estimated_cost(self):
        return float(self.quantity_requested or 0) * float(self.estimated_unit_cost or 0)

class MaterialIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("material_request.id"), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    issue_date = db.Column(db.Date, nullable=True)
    issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    received_by = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(80), default="Issued")
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    request = db.relationship("MaterialRequest", backref=db.backref("issues", lazy=True))
    project = db.relationship("Project", backref=db.backref("material_issues", lazy=True, cascade="all, delete-orphan"))
    issued_by = db.relationship("User", foreign_keys=[issued_by_id])
    @property
    def total_issue_cost(self):
        return sum(line.total_cost for line in self.lines)

class MaterialIssueLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("material_issue.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("material_item.id"), nullable=True)
    item_name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity_issued = db.Column(db.Float, default=0)
    unit = db.Column(db.String(50), nullable=True)
    unit_cost = db.Column(db.Float, default=0)
    remarks = db.Column(db.Text, nullable=True)
    issue = db.relationship("MaterialIssue", backref=db.backref("lines", lazy=True, cascade="all, delete-orphan"))
    item = db.relationship("MaterialItem")
    @property
    def total_cost(self):
        return float(self.quantity_issued or 0) * float(self.unit_cost or 0)

class MaterialReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    return_date = db.Column(db.Date, nullable=True)
    returned_by = db.Column(db.String(150), nullable=True)
    received_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reason = db.Column(db.String(250), nullable=True)
    status = db.Column(db.String(80), default="Returned")
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    project = db.relationship("Project", backref=db.backref("material_returns", lazy=True, cascade="all, delete-orphan"))
    received_by = db.relationship("User", foreign_keys=[received_by_id])
    @property
    def total_return_cost(self):
        return sum(line.total_cost for line in self.lines)

class MaterialReturnLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey("material_return.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("material_item.id"), nullable=True)
    item_name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity_returned = db.Column(db.Float, default=0)
    unit = db.Column(db.String(50), nullable=True)
    unit_cost = db.Column(db.Float, default=0)
    remarks = db.Column(db.Text, nullable=True)
    material_return = db.relationship("MaterialReturn", backref=db.backref("lines", lazy=True, cascade="all, delete-orphan"))
    item = db.relationship("MaterialItem")
    @property
    def total_cost(self):
        return float(self.quantity_returned or 0) * float(self.unit_cost or 0)


# Phase 14C Model: Company Profile for forms and reports
class CompanyProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False, default="Cadceed-Maal Solar Energy")
    tagline = db.Column(db.String(250), nullable=True, default="Renewable Energy Solutions")
    address = db.Column(db.String(250), nullable=True)
    phone = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    website = db.Column(db.String(150), nullable=True)
    tax_no = db.Column(db.String(120), nullable=True)
    logo_text = db.Column(db.String(50), nullable=True, default="CMSE")
    primary_color = db.Column(db.String(20), nullable=True, default="#f97316")
    secondary_color = db.Column(db.String(20), nullable=True, default="#16a34a")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Phase 15A Models: Sales Inquiry, Quotation, Warranty, After-Sales and Notifications
INQUIRY_STATUSES = ["New", "Contacted", "Site Survey Scheduled", "Quoted", "Won", "Lost", "Converted to Project", "Closed"]
INQUIRY_SOURCES = ["Walk-in", "Phone Call", "WhatsApp", "Website", "Referral", "Field Visit", "Social Media", "Existing Customer", "Other"]
QUOTATION_STATUSES = ["Draft", "Sent", "Under Review", "Approved by Customer", "Rejected", "Expired", "Converted to Project"]
WARRANTY_STATUSES = ["Active", "Expired", "Void", "Closed"]
TICKET_STATUSES = ["Open", "Assigned", "In Progress", "Waiting Parts", "Pending Customer", "Resolved", "Closed", "Not Warranty", "Cancelled"]
TICKET_CATEGORIES = ["Inverter Fault", "Battery Issue", "Solar Panel Issue", "Wiring Problem", "Pump Problem", "AC Load Problem", "Monitoring Issue", "Customer Training", "Maintenance Request", "Product Defect", "Installation Issue", "Other"]
COMPLAINT_SOURCES = ["WhatsApp", "Phone Call", "Office Visit", "Sales Team", "Branch Office", "Website", "Email", "Referral", "Other"]
SERVICE_RESULTS = ["Resolved", "Partially Resolved", "Needs Parts", "Needs Second Visit", "Not Warranty", "Customer Not Available", "Escalated", "Pending Testing"]
CUSTOMER_CONFIRMATIONS = ["Customer Confirmed", "Customer Not Satisfied", "Needs Second Visit", "Customer Not Available", "Pending Confirmation"]
TICKET_PRIORITIES = ["Low", "Medium", "High", "Urgent"]
VISIT_STATUSES = ["Planned", "In Progress", "Completed", "Cancelled", "Rescheduled", "Needs Follow-up"]
NOTIFICATION_STATUSES = ["Unread", "Read", "Archived"]


class QuotationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(180), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    unit_price = db.Column(db.Float, default=0)
    category = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SalesInquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    inquiry_date = db.Column(db.Date, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True)
    customer_name = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(80), nullable=True)
    location = db.Column(db.String(180), nullable=True)
    source = db.Column(db.String(80), default="Walk-in")
    project_type = db.Column(db.String(150), nullable=True)
    requirement_summary = db.Column(db.Text, nullable=True)
    estimated_capacity = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(80), default="New")
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    next_followup_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Customer")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

class SalesQuotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    inquiry_id = db.Column(db.Integer, db.ForeignKey("sales_inquiry.id"), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    quotation_date = db.Column(db.Date, nullable=True)
    customer_name = db.Column(db.String(180), nullable=False)
    project_type = db.Column(db.String(150), nullable=True)
    capacity = db.Column(db.String(80), nullable=True)
    scope_of_work = db.Column(db.Text, nullable=True)
    validity_days = db.Column(db.Integer, default=15)
    status = db.Column(db.String(80), default="Draft")
    prepared_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inquiry = db.relationship("SalesInquiry", backref=db.backref("quotations", lazy=True))
    project = db.relationship("Project")
    prepared_by = db.relationship("User", foreign_keys=[prepared_by_id])
    lines = db.relationship("SalesQuotationLine", backref="quotation", lazy=True, cascade="all, delete-orphan")

    @property
    def total_amount(self):
        return sum(line.total_price for line in self.lines)

class SalesQuotationLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey("sales_quotation.id"), nullable=False)
    item = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(50), nullable=True)
    unit_price = db.Column(db.Float, default=0)

    @property
    def total_price(self):
        return float(self.quantity or 0) * float(self.unit_price or 0)

class WarrantyRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True)
    customer_name = db.Column(db.String(180), nullable=False)
    system_type = db.Column(db.String(150), nullable=True)
    capacity = db.Column(db.String(80), nullable=True)
    installation_date = db.Column(db.Date, nullable=True)
    handover_date = db.Column(db.Date, nullable=True)
    warranty_start = db.Column(db.Date, nullable=True)
    warranty_end = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(80), default="Active")
    registered_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project")
    customer = db.relationship("Customer")
    registered_by = db.relationship("User", foreign_keys=[registered_by_id])

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    ticket_date = db.Column(db.Date, nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    warranty_id = db.Column(db.Integer, db.ForeignKey("warranty_registration.id"), nullable=True)
    customer_name = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(80), nullable=True)
    location = db.Column(db.String(180), nullable=True)
    complaint_source = db.Column(db.String(100), nullable=True)
    preferred_visit_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    issue_category = db.Column(db.String(120), nullable=True)
    issue_description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(80), default="Medium")
    status = db.Column(db.String(80), default="Open")
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=True)
    supervisor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    resolution_summary = db.Column(db.Text, nullable=True)
    root_cause = db.Column(db.Text, nullable=True)
    corrective_action = db.Column(db.Text, nullable=True)
    preventive_action = db.Column(db.Text, nullable=True)
    final_result = db.Column(db.String(120), nullable=True)
    customer_confirmation = db.Column(db.String(120), nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Customer")
    project = db.relationship("Project")
    warranty = db.relationship("WarrantyRegistration")
    assigned_employee = db.relationship("Employee")
    supervisor = db.relationship("User", foreign_keys=[supervisor_user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

class ServiceVisit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey("support_ticket.id"), nullable=False)
    visit_date = db.Column(db.Date, nullable=True)
    technician_employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=True)
    fault_found = db.Column(db.Text, nullable=True)
    root_cause = db.Column(db.Text, nullable=True)
    work_done = db.Column(db.Text, nullable=True)
    parts_used = db.Column(db.Text, nullable=True)
    result = db.Column(db.String(120), nullable=True)
    test_result = db.Column(db.String(120), nullable=True)
    customer_feedback = db.Column(db.Text, nullable=True)
    customer_confirmation = db.Column(db.String(120), nullable=True)
    next_action = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(80), default="Planned")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship("SupportTicket", backref=db.backref("service_visits", lazy=True, cascade="all, delete-orphan"))
    technician = db.relationship("Employee")

class SystemNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    priority = db.Column(db.String(80), default="Medium")
    status = db.Column(db.String(80), default="Unread")
    target_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    related_module = db.Column(db.String(100), nullable=True)
    related_ref = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)

    target_user = db.relationship("User")


# Phase 15E Models: Notification Channels, Logs, SMS Queue, WhatsApp Future Settings, User Form Permissions
NOTIFICATION_CHANNELS = ["In-App", "Email", "SMS", "WhatsApp"]
NOTIFICATION_DELIVERY_STATUSES = ["Pending", "Queued", "Sent", "Failed", "Skipped"]
FORM_PERMISSION_KEYS = [
    # Core / Project
    ("dashboard", "Dashboard", "Core"),
    ("projects", "Projects", "Project Management"),
    ("project-tasks", "Project Tasks", "Project Management"),
    ("issues-risks", "Issues / Risks", "Project Management"),
    ("documents", "Documents", "Project Management"),
    ("project-workforce", "Project Workforce", "Project Management"),

    # Online Forms
    ("forms-home", "Online Forms Home", "Online Forms"),
    ("site-survey", "Site Survey & Load Assessment", "Online Forms"),
    ("load-assessment", "Load Assessment Legacy", "Online Forms"),
    ("daily-site-report", "Daily Site Report", "Online Forms"),
    ("delivery-note", "Delivery Note", "Online Forms"),
    ("testing", "Testing", "Online Forms"),
    ("commissioning", "Commissioning", "Online Forms"),
    ("handover", "Handover", "Online Forms"),

    # Materials
    ("materials", "Materials Dashboard", "Materials"),
    ("material-items", "Material Items", "Materials"),
    ("material-request", "Material Requests", "Materials"),
    ("material-issue", "Material Issue", "Materials"),
    ("material-return", "Material Return", "Materials"),
    ("material-reports", "Material Reports", "Materials"),

    # Sales / CRM
    ("sales-crm", "Sales CRM Dashboard", "Sales CRM"),
    ("customer-inquiry", "Customer Inquiry", "Sales CRM"),
    ("quotation", "Quotations", "Sales CRM"),
    ("quotation-items", "Quotation Item Master / Import", "Sales CRM"),

    # After-Sales / Support
    ("after-sales", "After-Sales Dashboard", "After-Sales & Warranty"),
    ("service-ticket", "Service Tickets / Complaints", "After-Sales & Warranty"),
    ("warranty", "Warranty Records", "After-Sales & Warranty"),

    # Reports
    ("reports", "Reports Center", "Reports"),
    ("project-reports", "Project Reports", "Reports"),
    ("customer-reports", "Customer Reports", "Reports"),
    ("form-reports", "Form PDF Reports", "Reports"),

    # Master Data
    ("customers", "Customers", "Master Data"),
    ("employees", "Employees", "Master Data"),
    ("teams", "Teams", "Master Data"),

    # Notifications / System
    ("notifications", "Notification Center", "System Center"),
    ("notification-log", "Notification Log", "System Center"),
    ("sms-queue", "SMS Queue", "System Center"),
    ("whatsapp-integration", "WhatsApp Future Integration", "System Center"),
    ("production-readiness", "Production Readiness", "System Center"),

    # AI
    ("ai-assistant", "AI Assistant", "AI"),
    ("ai-reports", "AI Reports", "AI"),
    ("ai-logs", "AI Logs", "AI"),
    ("ai-settings", "AI Settings", "AI"),

    # Payroll / Admin
    ("payroll", "Project Payroll", "Payroll"),
    ("users", "Users & Roles", "Admin"),
    ("admin-settings", "Admin Settings", "Admin"),
    ("company-profile", "Company Profile", "Admin"),
    ("branches", "Branches", "Admin"),
    ("departments", "Departments", "Admin"),
    ("activity-log", "Activity Log", "Admin"),
    ("backup", "Backup", "Admin"),
    ("user-form-permissions", "User Form Permissions", "Admin"),
]


class NotificationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_ref = db.Column(db.String(120), nullable=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    recipient_name = db.Column(db.String(180), nullable=True)
    channel = db.Column(db.String(80), default="In-App")
    recipient = db.Column(db.String(180), nullable=True)
    subject = db.Column(db.String(250), nullable=True)
    message = db.Column(db.Text, nullable=True)
    related_module = db.Column(db.String(120), nullable=True)
    related_ref = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(80), default="Pending")
    error_message = db.Column(db.Text, nullable=True)
    provider_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    recipient_user = db.relationship("User", foreign_keys=[recipient_user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

class SMSQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    recipient_name = db.Column(db.String(180), nullable=True)
    phone_number = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_module = db.Column(db.String(120), nullable=True)
    related_ref = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(80), default="Pending")
    provider = db.Column(db.String(120), default="No API - Manual Queue")
    provider_response = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])

class WhatsAppIntegrationSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=True)
    provider = db.Column(db.String(120), default="Future: Meta Cloud API / Twilio")
    business_phone = db.Column(db.String(80), nullable=True)
    phone_number_id = db.Column(db.String(150), nullable=True)
    api_base_url = db.Column(db.String(250), nullable=True)
    template_mode = db.Column(db.String(120), default="Approved Templates Required")
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by = db.relationship("User")

class UserFormPermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    form_key = db.Column(db.String(120), nullable=False)
    form_label = db.Column(db.String(180), nullable=True)
    can_view = db.Column(db.Boolean, default=False)
    can_create = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_approve = db.Column(db.Boolean, default=False)
    can_print_export = db.Column(db.Boolean, default=False)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    __table_args__ = (db.UniqueConstraint('user_id', 'form_key', name='uq_user_form_permission'),)


# Phase 15F Models: AI Assistant & Smart ERP Intelligence
AI_CONTEXT_TYPES = [
    "General ERP Question", "Service Ticket Help", "CRM Follow-up", "Quotation Note",
    "Project Summary", "Weekly Report", "Technical Troubleshooting", "Somali/English Translation",
]
AI_RESPONSE_STATUSES = ["Draft", "Reviewed", "Used", "Archived"]

class AISetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=True)
    provider = db.Column(db.String(120), default="OpenAI-Compatible")
    model_name = db.Column(db.String(120), default="gpt-4o-mini")
    api_base_url = db.Column(db.String(250), default="https://api.openai.com/v1/chat/completions")
    api_key = db.Column(db.Text, nullable=True)  # Prefer environment variable OPENAI_API_KEY in production.
    temperature = db.Column(db.Float, default=0.2)
    max_tokens = db.Column(db.Integer, default=900)
    system_prompt = db.Column(db.Text, default="You are Cadceed-Maal Solar Energy ERP assistant. Give practical, professional, concise answers for solar business operations.")
    allow_data_context = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by = db.relationship("User")

class AIInteractionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(120), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    context_type = db.Column(db.String(120), default="General ERP Question")
    related_module = db.Column(db.String(120), nullable=True)
    related_ref = db.Column(db.String(120), nullable=True)
    prompt = db.Column(db.Text, nullable=False)
    context_data = db.Column(db.Text, nullable=True)
    response = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(80), default="Draft")
    provider = db.Column(db.String(120), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")
