import json
from pathlib import Path
from datetime import datetime, date
from app import create_app, db
from app.models import (
    User, Project, Document, SiteSurveyForm, LoadAssessmentForm, DailySiteReport,
    DeliveryNoteForm, TestingForm, CommissioningForm, HandoverForm,
    AuditLog, ApprovalHistory, Notification, DocumentVersion, Branch, Department, SystemSetting
)

MODELS = [
    Branch, Department, SystemSetting, User, Project, Document, DocumentVersion,
    SiteSurveyForm, LoadAssessmentForm, DailySiteReport, DeliveryNoteForm,
    TestingForm, CommissioningForm, HandoverForm, AuditLog, ApprovalHistory, Notification
]

MODEL_MAP = {Model.__tablename__: Model for Model in MODELS}


def convert_value(column, value):
    if value is None:
        return None

    col_type = str(column.type).lower()

    if "datetime" in col_type:
        return datetime.fromisoformat(value)

    if "date" in col_type:
        return date.fromisoformat(value)

    return value


app = create_app()

with app.app_context():
    file_path = Path("exports") / "solar_doc_export.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Export file not found: {file_path}")

    data = json.loads(file_path.read_text(encoding="utf-8"))

    for table_name, rows in data.items():
        Model = MODEL_MAP.get(table_name)

        if not Model:
            print(f"Skipped unknown table: {table_name}")
            continue

        print(f"Importing {table_name}: {len(rows)} rows")

        for row in rows:
            clean_row = {}

            for col in Model.__table__.columns:
                if col.name in row:
                    clean_row[col.name] = convert_value(col, row[col.name])

            pk_cols = list(Model.__table__.primary_key.columns)

            if pk_cols:
                pk_name = pk_cols[0].name
                pk_value = clean_row.get(pk_name)

                existing = None
                if pk_value is not None:
                    existing = db.session.get(Model, pk_value)

                if existing:
                    for key, value in clean_row.items():
                        setattr(existing, key, value)
                else:
                    obj = Model(**clean_row)
                    db.session.add(obj)
            else:
                obj = Model(**clean_row)
                db.session.add(obj)

        db.session.commit()

    print("Import completed successfully.")