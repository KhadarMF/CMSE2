from flask import Blueprint, jsonify
from app import db

health_bp = Blueprint("health", __name__)

@health_bp.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        database = "ok"
    except Exception as e:
        database = f"error: {e}"
    return jsonify({"status": "ok" if database == "ok" else "error", "database": database})
