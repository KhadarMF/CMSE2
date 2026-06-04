from flask import Blueprint, render_template
from flask_login import login_required
from app import db
from app.models import User, Project, Customer

production_bp = Blueprint('production', __name__, url_prefix='/production')

@production_bp.route('/')
@login_required
def readiness():
    checks=[]
    try:
        db.session.execute(db.text('SELECT 1'))
        db_ok=True
    except Exception:
        db_ok=False
    checks.append(('Database connection', 'OK' if db_ok else 'Error'))
    checks.append(('Users', User.query.count()))
    checks.append(('Projects', Project.query.count()))
    checks.append(('Customers', Customer.query.count()))
    return render_template('production/readiness.html', checks=checks)