import os
from pathlib import Path
from flask import Flask, request, redirect, url_for, flash, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv

db = SQLAlchemy()
migrate = Migrate()
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
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(override=False)
    app = Flask(__name__)

    # Phase 20D: no more silent fallback secret. validate_secret_key() raises
    # in production if SECRET_KEY is missing, still the placeholder, or too
    # short - a forgeable session cookie means anyone can become Admin, and a
    # crash on boot is far cheaper than discovering that later.
    from app.security import validate_secret_key, init_csrf, is_production
    secret_key = os.environ.get("SECRET_KEY", "")
    validate_secret_key(secret_key)
    app.config["SECRET_KEY"] = secret_key or "dev-only-insecure-key"
    # Phase 17B.1E Security Hardening: use a new session cookie name to invalidate
    # any browser cookies created by the unsafe 17B.1C/17B.1D builds.
    app.config["SESSION_COOKIE_NAME"] = os.environ.get("SESSION_COOKIE_NAME", "cmse_erp_session_v17b1e")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Phase 20D: default to Secure cookies in production instead of opt-in.
    # Render always serves HTTPS, so the old opt-in only ever meant "someone
    # forgot to set the variable and the cookie went out in the clear".
    cookie_secure_env = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower()
    if cookie_secure_env in ("1", "true", "yes"):
        app.config["SESSION_COOKIE_SECURE"] = True
    elif cookie_secure_env in ("0", "false", "no"):
        app.config["SESSION_COOKIE_SECURE"] = False
    else:
        app.config["SESSION_COOKIE_SECURE"] = is_production()
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
    migrate.init_app(app, db, compare_type=True)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None
        return user if user and user.is_active else None

    # Phase 17B.2G Admin Account Recovery: disabled unless
    # ADMIN_RECOVERY_PASSWORD is set in environment variables.
    # It only resets/creates the admin login and does not touch business data.
    try:
        with app.app_context():
            from app.admin_recovery import run_admin_recovery_if_requested
            run_admin_recovery_if_requested(app)
    except Exception:
        app.logger.exception("Admin recovery bootstrap failed")

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
    from app.routes.payment_routes import payments_bp
    from app.routes.accounting_routes import accounting_bp
    from app.routes.milestone_routes import milestone_bp

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
    app.register_blueprint(payments_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(milestone_bp)

    # Phase 20D: global CSRF protection. Must run after the blueprints are
    # registered because it exempts the WhatsApp webhook by function object.
    init_csrf(app)

    # Phase 17B.1E Security Hardening: strict login gate.
    # This is a second safety net in addition to @login_required and the
    # permission enforcer. Internal ERP pages must never be reachable unless
    # the user is authenticated. Public endpoints are intentionally limited.
    PUBLIC_ENDPOINTS = {
        "auth.home", "auth.login", "auth.logout",
        "health.health",
        "whatsapp.webhook_verify", "whatsapp.webhook_receive",
        "sales.public_quotation_short", "sales.public_quotation_short_pdf",
        "sales.public_quotation",
    }

    @app.before_request
    def enforce_authentication_gate():
        endpoint = request.endpoint or ""
        if endpoint == "static" or endpoint.startswith("static"):
            return None
        if endpoint in PUBLIC_ENDPOINTS:
            return None
        try:
            from flask_login import current_user
            if not current_user.is_authenticated:
                flash("Please login to continue.", "warning")
                return redirect(url_for("auth.login", next=request.full_path if request.query_string else request.path))
        except Exception:
            return redirect(url_for("auth.login"))
        return None

    # Phase 18A.4: while a restore is running, the whole app is put into
    # maintenance mode for everyone except the Restore Center itself (so the
    # admin who started it can watch progress and check the log). The lock
    # file this checks is created and removed by app.backup_service.
    # NOTE: this only works within a single filesystem/process. It does not
    # coordinate a restore across multiple horizontally-scaled instances.
    @app.before_request
    def enforce_maintenance_mode():
        endpoint = request.endpoint or ""
        if endpoint == "static" or endpoint.startswith("static"):
            return None
        if endpoint in ("auth.login", "auth.logout", "health.health"):
            return None
        if endpoint.startswith("admin.restore"):
            return None
        try:
            from app.backup_service import is_restore_in_progress, get_restore_lock_info
            if is_restore_in_progress():
                return render_template("system/maintenance.html", info=get_restore_lock_info() or {}), 503
        except Exception:
            return None
        return None

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

    # Phase 20D: the schema is now owned by Alembic (`flask db upgrade`).
    # The old ensure_*_tables() helpers called db.create_all() on the fly,
    # which silently did nothing whenever a model gained a COLUMN rather
    # than a whole table - that is how schema drift got in. This warns
    # loudly instead of guessing.
    try:
        with app.app_context():
            from app.db_utils import warn_if_migrations_pending
            warn_if_migrations_pending(app)
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
            from app.team_leader_access import is_team_leader
            return {"can_access_module": can_access_module, "has_any_permission": has_any_permission, "allowed_form_keys": allowed_form_keys, "allowed_permission_keys": allowed_permission_keys, "is_team_leader": is_team_leader}
        except Exception:
            return {"can_access_module": lambda user, key, action="view": False, "has_any_permission": lambda user, keys, action="view": False, "allowed_form_keys": lambda user, action="view": [], "allowed_permission_keys": lambda user: [], "is_team_leader": lambda user: False}

    @app.context_processor
    def inject_notification_badge():
        try:
            from flask_login import current_user
            from app.models import SystemNotification, WhatsAppMessage
            if current_user.is_authenticated:
                count = SystemNotification.query.filter(SystemNotification.status == "Unread").filter((SystemNotification.target_user_id == current_user.id) | (SystemNotification.target_user_id == None)).count()
                whatsapp_unread = WhatsAppMessage.query.filter_by(direction="Inbound", status="Received").count()
                return {"unread_notification_count": count, "whatsapp_unread_count": whatsapp_unread}
        except Exception:
            pass
        return {"unread_notification_count": 0, "whatsapp_unread_count": 0}

    return app
