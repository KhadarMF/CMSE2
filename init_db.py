from app import create_app, db
import os
import secrets
from pathlib import Path
from flask_migrate import upgrade
from app.models import User, Branch, Department, SystemSetting, Customer, Project, ProjectType, CompanyProfile, QuotationItem, AISetting
from werkzeug.security import generate_password_hash

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

def initialize_database(application):
    """Migrate and seed defaults without replacing existing accounts or data."""
    with application.app_context():
        upgrade(directory=str(Path(__file__).resolve().parent / "migrations"))
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

        admin_email = os.environ.get("INITIAL_ADMIN_EMAIL", "admin@cadceedmaal.com").strip().lower()
        existing_admin = User.query.filter(db.func.lower(User.role) == "admin").first()
        admin_password = None
        if not existing_admin:
            if User.query.filter_by(email=admin_email).first():
                raise RuntimeError("Bootstrap email already belongs to a user. Use admin recovery instead.")
            admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD") or secrets.token_urlsafe(18)
            if len(admin_password) < 12:
                raise ValueError("INITIAL_ADMIN_PASSWORD must be at least 12 characters.")
            admin = User(full_name="System Administrator", email=admin_email, password_hash=generate_password_hash(admin_password), role="Admin", is_active=True)
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
        print("Database migrations and default data are ready.")
        if not existing_admin:
            print("Default admin user created:")
            print(f"Email: {admin_email}")
            print(f"Temporary password: {admin_password}")
            print("Save this password now; it is only displayed when the administrator is created.")
        else:
            print("Admin user already exists.")


if __name__ == "__main__":
    from app.local_setup import prepare_local_environment
    prepare_local_environment()
    initialize_database(create_app())
