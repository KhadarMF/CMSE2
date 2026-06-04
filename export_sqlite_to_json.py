import json
from pathlib import Path
from datetime import date, datetime
from app import create_app
from app.models import (
    User, Project, Document, SiteSurveyForm, LoadAssessmentForm, DailySiteReport,
    DeliveryNoteForm, TestingForm, CommissioningForm, HandoverForm,
    AuditLog, ApprovalHistory, Notification, DocumentVersion, Branch, Department, SystemSetting
)

MODELS = [
    User, Branch, Department, SystemSetting, Project, Document, DocumentVersion,
    SiteSurveyForm, LoadAssessmentForm, DailySiteReport, DeliveryNoteForm,
    TestingForm, CommissioningForm, HandoverForm, AuditLog, ApprovalHistory, Notification
]

def serialize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value

app = create_app()

with app.app_context():
    data = {}
    for Model in MODELS:
        rows = []
        for obj in Model.query.all():
            row = {}
            for col in Model.__table__.columns:
                row[col.name] = serialize_value(getattr(obj, col.name))
            rows.append(row)
        data[Model.__tablename__] = rows

    out = Path("exports")
    out.mkdir(exist_ok=True)
    file_path = out / "solar_doc_export.json"
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Exported:", file_path)
