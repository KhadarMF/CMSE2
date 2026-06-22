import os
from pathlib import Path
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

def normalize_database_url(url):
    if not url:
        return "sqlite:///solar_documents.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url

def create_app():
    # Load local environment variables reliably from the project root.
    # This is important when the app is started from VS Code/Visual Studio,
    # because the current working directory can sometimes differ from the
    # folder that contains .env.
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env", override=True)
    load_dotenv(override=False)
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(os.environ.get("DATABASE_URL", "sqlite:///solar_documents.db"))
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    upload_folder = os.environ.get("UPLOAD_FOLDER", "")
    if upload_folder:
        if not os.path.isabs(upload_folder):
            upload_folder = os.path.join(Path(app.root_path).parent, upload_folder)
        app.config["UPLOAD_FOLDER"] = upload_folder
    else:
        app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")

    max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "20"))
    app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024

    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"])

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth_routes import auth_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.project_routes import project_bp
    from app.routes.document_routes import document_bp
    from app.routes.user_routes import user_bp
    from app.routes.form_routes import form_bp
    from app.routes.report_routes import report_bp
    from app.routes.activity_routes import activity_bp
    from app.routes.task_routes import task_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.health_routes import health_bp
    from app.routes.project_task_routes import project_task_bp
    from app.routes.issue_routes import issue_bp
    from app.routes.master_routes import master_bp
    from app.routes.payroll_routes import payroll_bp
    from app.routes.materials_routes import materials_bp
    from app.routes.sales_routes import sales_bp
    from app.routes.support_routes import support_bp
    from app.routes.notifications_routes import notifications_bp
    from app.routes.production_routes import production_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.whatsapp_routes import whatsapp_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(form_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(project_task_bp)
    app.register_blueprint(issue_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(whatsapp_bp)

    from app.permission_enforcer import register_permission_enforcer
    register_permission_enforcer(app)

    # Keep PostgreSQL ID sequences aligned after imports/restores.
    # This fixes duplicate primary key errors when saving projects/forms/tickets.
    try:
        with app.app_context():
            from app.db_utils import sync_postgres_sequences
            sync_postgres_sequences()
    except Exception:
        pass

    @app.context_processor
    def inject_company_profile():
        try:
            from app.models import CompanyProfile
            company = CompanyProfile.query.first()
            if company:
                return {"company_profile": company}
        except Exception:
            pass
        class DefaultCompany:
            company_name = "Cadceed-Maal Solar Energy"
            tagline = "Renewable Energy Solutions"
            address = "Green Mall, Second Floor, Road One, Hargeisa, Somaliland"
            phone = "+252-2-524868"
            email = "info@cadceedmaal.com"
            website = "www.cadceedmaal.com"
            tax_no = ""
            logo_text = "CMSE"
            primary_color = "#f97316"
            secondary_color = "#16a34a"
        return {"company_profile": DefaultCompany()}


    @app.context_processor
    def inject_permission_helpers():
        try:
            from app.permissions import can_access_module, has_any_permission, allowed_form_keys, allowed_permission_keys
            return {"can_access_module": can_access_module, "has_any_permission": has_any_permission, "allowed_form_keys": allowed_form_keys, "allowed_permission_keys": allowed_permission_keys}
        except Exception:
            return {"can_access_module": lambda user, key, action="view": False, "has_any_permission": lambda user, keys, action="view": False, "allowed_form_keys": lambda user, action="view": [], "allowed_permission_keys": lambda user: []}

    @app.context_processor
    def inject_notification_badge():
        try:
            from flask_login import current_user
            from app.models import SystemNotification
            if current_user.is_authenticated:
                count = SystemNotification.query.filter(SystemNotification.status == "Unread").filter((SystemNotification.target_user_id == current_user.id) | (SystemNotification.target_user_id == None)).count()
                return {"unread_notification_count": count}
        except Exception:
            pass
        return {"unread_notification_count": 0}

    return app
