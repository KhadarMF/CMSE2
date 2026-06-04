from app import create_app, db
from sqlalchemy import text
from app.models import User, Branch, Department, SystemSetting, Customer, Project, ProjectType, CompanyProfile, QuotationItem, AISetting
from werkzeug.security import generate_password_hash

app = create_app()

DEFAULT_BRANCHES = [("Hargeisa HQ", "Hargeisa"), ("Burco Branch", "Burco"), ("Jigjiga Branch", "Jigjiga")]
DEFAULT_DEPARTMENTS = [
    ("Management", "Company management and approvals"),
    ("Operations", "Project operations and coordination"),
    ("Technical", "Engineering and technical works"),
    ("Warehouse", "Stock and delivery management"),
    ("Transport", "Transport and logistics"),
    ("Sales", "Sales and customer follow-up"),
    ("Finance", "Finance and accounts"),
]
DEFAULT_SETTINGS = {
    "MAIL_SERVER": "", "MAIL_PORT": "587", "MAIL_USE_TLS": "true",
    "MAIL_USERNAME": "", "MAIL_PASSWORD": "", "MAIL_DEFAULT_SENDER": "",
}

with app.app_context():
    db.create_all()

    # Phase 14E: migrate project_task assignment columns for existing SQLite/PostgreSQL databases.
    try:
        inspector = db.inspect(db.engine)
        existing_cols = [c["name"] for c in inspector.get_columns("project_task")]
        if "assigned_employee_id" not in existing_cols:
            db.session.execute(text("ALTER TABLE project_task ADD COLUMN assigned_employee_id INTEGER"))
        if "supervisor_user_id" not in existing_cols:
            db.session.execute(text("ALTER TABLE project_task ADD COLUMN supervisor_user_id INTEGER"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Phase 14E task assignment migration skipped or already applied:", e)


    # Phase 15K: migrate combined Site Survey & Load Assessment fields and extended permissions.
    try:
        inspector = db.inspect(db.engine)
        site_cols = [c["name"] for c in inspector.get_columns("site_survey_form")]
        site_additions = {
            "assessment_date": "DATE",
            "assessed_by": "VARCHAR(150)",
            "daytime_load_kw": "VARCHAR(80)",
            "nighttime_load_kw": "VARCHAR(80)",
            "total_daily_consumption_kwh": "VARCHAR(80)",
            "critical_loads": "TEXT",
            "ac_loads": "TEXT",
            "pump_loads": "TEXT",
            "lighting_loads": "TEXT",
            "backup_hours_required": "VARCHAR(80)",
            "recommended_system_size": "VARCHAR(120)",
            "recommendation": "TEXT",
        }
        for col, typ in site_additions.items():
            if col not in site_cols:
                db.session.execute(text(f"ALTER TABLE site_survey_form ADD COLUMN {col} {typ}"))
        perm_cols = [c["name"] for c in inspector.get_columns("user_form_permission")]
        if "can_print_export" not in perm_cols:
            db.session.execute(text("ALTER TABLE user_form_permission ADD COLUMN can_print_export BOOLEAN DEFAULT 0"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Phase 15K combined forms / permissions migration skipped or already applied:", e)



    # Phase 15D: migrate advanced service ticket columns for existing databases.
    try:
        inspector = db.inspect(db.engine)
        support_cols = [c["name"] for c in inspector.get_columns("support_ticket")]
        support_additions = {
            "location": "VARCHAR(180)",
            "complaint_source": "VARCHAR(100)",
            "preferred_visit_date": "DATE",
            "due_date": "DATE",
            "root_cause": "TEXT",
            "corrective_action": "TEXT",
            "preventive_action": "TEXT",
            "final_result": "VARCHAR(120)",
            "customer_confirmation": "VARCHAR(120)",
        }
        for col, typ in support_additions.items():
            if col not in support_cols:
                db.session.execute(text(f"ALTER TABLE support_ticket ADD COLUMN {col} {typ}"))
        visit_cols = [c["name"] for c in inspector.get_columns("service_visit")]
        visit_additions = {
            "fault_found": "TEXT",
            "root_cause": "TEXT",
            "test_result": "VARCHAR(120)",
            "customer_confirmation": "VARCHAR(120)",
            "next_action": "TEXT",
        }
        for col, typ in visit_additions.items():
            if col not in visit_cols:
                db.session.execute(text(f"ALTER TABLE service_visit ADD COLUMN {col} {typ}"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Phase 15D support ticket migration skipped or already applied:", e)

    # Phase 14C: default company profile for forms and reports.
    default_company = CompanyProfile.query.first()
    if not default_company:
        db.session.add(CompanyProfile(
            company_name="Cadceed-Maal Solar Energy",
            tagline="Renewable Energy Solutions",
            address="Green Mall, Second Floor, Road One, Hargeisa, Somaliland",
            phone="+252-2-524868",
            email="info@cadceedmaal.com",
            website="www.cadceedmaal.com",
            logo_text="CMSE",
            primary_color="#f97316",
            secondary_color="#16a34a"
        ))

    admin_email = "admin@cadceedmaal.com"
    existing_admin = User.query.filter_by(email=admin_email).first()
    if not existing_admin:
        admin = User(full_name="System Administrator", email=admin_email, password_hash=generate_password_hash("Admin@12345"), role="Admin", is_active=True)
        db.session.add(admin)
    for name, location in DEFAULT_BRANCHES:
        if not Branch.query.filter_by(branch_name=name).first():
            db.session.add(Branch(branch_name=name, location=location, is_active=True))
    for name, desc in DEFAULT_DEPARTMENTS:
        if not Department.query.filter_by(department_name=name).first():
            db.session.add(Department(department_name=name, description=desc, is_active=True))
    for key, value in DEFAULT_SETTINGS.items():
        if not SystemSetting.query.filter_by(setting_key=key).first():
            db.session.add(SystemSetting(setting_key=key, setting_value=value))


    # Phase 13B: seed common project types.
    default_project_types = [
        "Hybrid Solar System", "Off-grid Solar System", "On-grid Solar System",
        "Solar Pump System", "Solar Street Lighting", "Solar Water Heating",
        "Battery / ESS System", "Maintenance / O&M", "Site Survey", "Other",
    ]
    for type_name in default_project_types:
        if not ProjectType.query.filter_by(type_name=type_name).first():
            db.session.add(ProjectType(type_name=type_name, is_active=True))



    # Phase 15C: seed standard quotation items for dropdown quotation lines.
    default_quotation_items = [
        ("Solar Panel", "High efficiency PV solar module", "pcs", 0, "PV Module"),
        ("Hybrid Inverter", "Hybrid solar inverter", "pcs", 0, "Inverter"),
        ("Lithium Battery", "Lithium battery storage module", "pcs", 0, "Battery"),
        ("Mounting Structure", "Roof/ground mounting structure", "set", 0, "Mounting"),
        ("DC Cable", "PV DC cable", "m", 0, "Cable"),
        ("AC Cable", "AC power cable", "m", 0, "Cable"),
        ("Protection Box", "AC/DC protection and breakers", "set", 0, "Protection"),
        ("Earthing System", "Grounding and lightning protection", "set", 0, "Earthing"),
        ("Installation Labor", "Installation, testing and commissioning service", "job", 0, "Service"),
        ("Transport", "Material transportation to site", "trip", 0, "Logistics"),
    ]
    for item_name, description, unit, unit_price, category in default_quotation_items:
        if not QuotationItem.query.filter_by(item_name=item_name).first():
            db.session.add(QuotationItem(item_name=item_name, description=description, unit=unit, unit_price=unit_price, category=category, is_active=True))



    # Phase 15F: default AI settings. Live AI remains disabled until admin configures API key.
    if not AISetting.query.first():
        db.session.add(AISetting(
            enabled=False,
            provider="OpenAI-Compatible",
            model_name="gpt-4o-mini",
            api_base_url="https://api.openai.com/v1/chat/completions",
            system_prompt="You are Cadceed-Maal Solar Energy ERP assistant. Give practical, professional, concise answers for solar business operations.",
            allow_data_context=True,
            notes="Set OPENAI_API_KEY in Render Environment Variables or enter an API key in AI Settings."
        ))

    # Phase 11: build Customer master list from existing project customer names.
    for project in Project.query.all():
        if project.customer_name and not Customer.query.filter_by(customer_name=project.customer_name).first():
            db.session.add(Customer(customer_name=project.customer_name, customer_type="Project Customer", is_active=True))
    db.session.commit()
    print("Database created or updated.")
    if not existing_admin:
        print("Default admin user created:")
        print("Email: admin@cadceedmaal.com")
        print("Password: Admin@12345")
    else:
        print("Admin user already exists.")
