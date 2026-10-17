"""Use simple workflow milestone weights for project progress.

Existing projects that already had the older six-gate template are brought to
the same workflow used for newly initialized projects. Procurement records are
not deleted; they simply stop driving completion percent.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "b20k0000a004"
down_revision = "b20k0000a003"
branch_labels = None
depends_on = None


MILESTONE_SPECS = (
    ("SURVEY", "Survey & Assessment", 1, 10, 0, 0, 100, False),
    ("QUOTATION", "Quotation Approval", 2, 10, 0, 0, 100, False),
    ("CONTRACT", "Contract Signed", 3, 10, 0, 0, 100, False),
    ("DESIGN", "Design & BOM Approval", 4, 15, 0, 0, 100, False),
    ("MATERIALS", "Materials Ready", 5, 15, 0, 0, 100, False),
    ("INSTALLATION", "Installation", 6, 25, 100, 0, 0, True),
    ("TESTING", "Testing & Commissioning", 7, 10, 0, 0, 100, False),
    ("HANDOVER", "Handover", 8, 5, 0, 0, 100, False),
)


REQUIREMENTS = {
    "QUOTATION": (("Approved quotation", None, "Quotation", True),),
    "CONTRACT": (("Signed contract", None, "Contract", True),),
    "MATERIALS": (("Approved materials readiness document", None, "Materials Ready", True),),
}


def _one(bind, sql, **params):
    return bind.execute(sa.text(sql), params).scalar()


def _execute(bind, sql, **params):
    bind.execute(sa.text(sql), params)


def _ensure_requirement(bind, milestone_id, title, form_key, document_type, critical):
    exists = _one(
        bind,
        """
        SELECT id FROM milestone_document_requirement
        WHERE milestone_id = :milestone_id
          AND COALESCE(form_key, '') = COALESCE(:form_key, '')
          AND COALESCE(document_type, '') = COALESCE(:document_type, '')
        LIMIT 1
        """,
        milestone_id=milestone_id,
        form_key=form_key,
        document_type=document_type,
    )
    if exists:
        return
    _execute(
        bind,
        """
        INSERT INTO milestone_document_requirement
        (milestone_id, title, form_key, document_type, is_required, is_critical, created_at)
        VALUES (:milestone_id, :title, :form_key, :document_type, 1, :critical, :created_at)
        """,
        milestone_id=milestone_id,
        title=title,
        form_key=form_key,
        document_type=document_type,
        critical=critical,
        created_at=datetime.utcnow(),
    )


def upgrade():
    bind = op.get_bind()
    project_ids = bind.execute(sa.text("SELECT id FROM project")).scalars().all()
    now = datetime.utcnow()
    for project_id in project_ids:
        existing_codes = set(
            bind.execute(
                sa.text("SELECT code FROM project_milestone WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).scalars()
        )
        if not existing_codes:
            continue
        if "PROCUREMENT" in existing_codes and "MATERIALS" not in existing_codes:
            _execute(
                bind,
                "UPDATE project_milestone SET code = 'MATERIALS' WHERE project_id = :project_id AND code = 'PROCUREMENT'",
                project_id=project_id,
            )
            existing_codes.discard("PROCUREMENT")
            existing_codes.add("MATERIALS")
        for code, name, sequence, project_weight, physical_weight, procurement_weight, document_weight, requires_daily in MILESTONE_SPECS:
            milestone_id = _one(
                bind,
                "SELECT id FROM project_milestone WHERE project_id = :project_id AND code = :code",
                project_id=project_id,
                code=code,
            )
            if milestone_id:
                _execute(
                    bind,
                    """
                    UPDATE project_milestone
                    SET name = :name,
                        sequence = :sequence,
                        project_weight = :project_weight,
                        physical_weight = :physical_weight,
                        procurement_weight = :procurement_weight,
                        document_weight = :document_weight,
                        requires_daily_report = :requires_daily,
                        updated_at = :updated_at
                    WHERE id = :milestone_id
                    """,
                    name=name,
                    sequence=sequence,
                    project_weight=project_weight,
                    physical_weight=physical_weight,
                    procurement_weight=procurement_weight,
                    document_weight=document_weight,
                    requires_daily=requires_daily,
                    updated_at=now,
                    milestone_id=milestone_id,
                )
            else:
                _execute(
                    bind,
                    """
                    INSERT INTO project_milestone
                    (project_id, code, name, description, sequence, project_weight,
                     physical_weight, procurement_weight, document_weight,
                     requires_daily_report, status, created_at, updated_at)
                    VALUES
                    (:project_id, :code, :name, :description, :sequence, :project_weight,
                     :physical_weight, :procurement_weight, :document_weight,
                     :requires_daily, 'Not Started', :created_at, :updated_at)
                    """,
                    project_id=project_id,
                    code=code,
                    name=name,
                    description=f"Evidence gate for {name.lower()}.",
                    sequence=sequence,
                    project_weight=project_weight,
                    physical_weight=physical_weight,
                    procurement_weight=procurement_weight,
                    document_weight=document_weight,
                    requires_daily=requires_daily,
                    created_at=now,
                    updated_at=now,
                )
                milestone_id = _one(
                    bind,
                    "SELECT id FROM project_milestone WHERE project_id = :project_id AND code = :code",
                    project_id=project_id,
                    code=code,
                )
            for title, form_key, document_type, critical in REQUIREMENTS.get(code, ()):
                _ensure_requirement(bind, milestone_id, title, form_key, document_type, critical)
            if code == "MATERIALS":
                _execute(
                    bind,
                    """
                    UPDATE milestone_document_requirement
                    SET title = 'Approved materials readiness document',
                        form_key = NULL,
                        document_type = 'Materials Ready'
                    WHERE milestone_id = :milestone_id
                      AND (form_key = 'delivery-note' OR document_type = 'Delivery Note')
                    """,
                    milestone_id=milestone_id,
                )


def downgrade():
    # Data migration only. Existing operational evidence is intentionally retained.
    pass

