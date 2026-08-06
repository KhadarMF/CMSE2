"""Phase 20I: evidence-based project milestone engine.

Revision ID: b20i0000a001
Revises: b20h0000a003
"""

from alembic import op
import sqlalchemy as sa


revision = "b20i0000a001"
down_revision = "b20h0000a003"
branch_labels = None
depends_on = None


DEFAULT_MILESTONES = (
    ("SURVEY", "Survey & Assessment", 10, 20, 0, 80, False, (("Approved site survey & load assessment", "site-survey", None, True),)),
    ("DESIGN", "Design & Approval", 15, 10, 10, 80, False, (("Approved technical design", None, "Technical Design", True), ("Approved bill of quantities", None, "BOQ", True))),
    ("PROCUREMENT", "Procurement", 20, 0, 80, 20, False, (("Approved delivery note", "delivery-note", None, True),)),
    ("INSTALLATION", "Installation", 35, 75, 20, 5, True, (("Approved installation daily report", "daily-site-report", None, True),)),
    ("TESTING", "Testing & Commissioning", 15, 60, 10, 30, True, (("Approved testing form", "testing", None, True), ("Approved commissioning form", "commissioning", None, True))),
    ("HANDOVER", "Handover", 5, 20, 0, 80, False, (("Approved handover form", "handover", None, True), ("Approved warranty document", None, "Warranty Document", True))),
)


def _seed_existing_projects():
    """Make the engine immediately available to projects that predate 20I."""
    bind = op.get_bind()
    project_rows = bind.execute(sa.text("SELECT id, status FROM project")).mappings().all()
    metadata = sa.MetaData()
    milestone_table = sa.Table("project_milestone", metadata, autoload_with=bind)
    requirement_table = sa.Table("milestone_document_requirement", metadata, autoload_with=bind)
    for project in project_rows:
        existing_count = bind.execute(
            sa.select(sa.func.count()).select_from(milestone_table).where(
                milestone_table.c.project_id == project["id"]
            )
        ).scalar_one()
        if existing_count:
            continue
        legacy_completed = project["status"] == "Completed"
        for sequence, spec in enumerate(DEFAULT_MILESTONES, start=1):
            code, name, project_weight, physical, procurement, documents, requires_daily, requirements = spec
            result = bind.execute(milestone_table.insert().values(
                project_id=project["id"], code=code, name=name,
                description=f"Evidence gate for {name.lower()}.", sequence=sequence,
                project_weight=project_weight, physical_weight=physical,
                procurement_weight=procurement, document_weight=documents,
                requires_daily_report=requires_daily,
                status="Completed with Exception" if legacy_completed else "Not Started",
                override_reason="Legacy project was already completed before milestone governance." if legacy_completed else None,
                gate_snapshot='{"action":"legacy-migration","reason":"Project already completed before Phase 20I"}' if legacy_completed else None,
            ))
            milestone_id = result.inserted_primary_key[0]
            for title, form_key, document_type, critical in requirements:
                bind.execute(requirement_table.insert().values(
                    milestone_id=milestone_id, title=title, form_key=form_key,
                    document_type=document_type, is_required=True, is_critical=critical,
                ))


def upgrade():
    # Some repair tests and manually repaired legacy databases can move the
    # Alembic stamp backwards while retaining newer business tables. Treat an
    # already-complete 20I schema as installed instead of recreating it.
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "project_milestone" in tables:
        required_tables = {"project_milestone", "milestone_document_requirement", "milestone_audit_log"}
        required_columns = {
            "project_task": {"milestone_id", "milestone_required", "milestone_critical"},
            "material_request": {"milestone_id", "milestone_required", "milestone_critical"},
            "document": {"milestone_id"},
            "daily_site_report": {"milestone_id"},
            "project_issue": {"milestone_id"},
        }
        schema_complete = required_tables.issubset(tables) and all(
            names.issubset({column["name"] for column in inspector.get_columns(table_name)})
            for table_name, names in required_columns.items()
        )
        if schema_complete:
            _seed_existing_projects()
            return
        raise RuntimeError(
            "Partial Phase 20I milestone schema detected. Restore the pre-upgrade backup "
            "or complete the missing tables/columns before retrying."
        )

    op.create_table(
        "project_milestone",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("project_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("physical_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("procurement_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("responsible_team_id", sa.Integer(), nullable=True),
        sa.Column("responsible_user_id", sa.Integer(), nullable=True),
        sa.Column("requires_daily_report", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="Not Started"),
        sa.Column("submitted_by_id", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("override_by_id", sa.Integer(), nullable=True),
        sa.Column("override_at", sa.DateTime(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("gate_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["responsible_team_id"], ["team.id"]),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["submitted_by_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["approved_by_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["override_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "code", name="uq_project_milestone_project_code"),
    )
    op.create_index("ix_project_milestone_project_sequence", "project_milestone", ["project_id", "sequence"])

    op.create_table(
        "milestone_document_requirement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("milestone_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("form_key", sa.String(length=80), nullable=True),
        sa.Column("form_record_id", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(length=120), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_critical", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.ForeignKeyConstraint(["milestone_id"], ["project_milestone.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "milestone_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("milestone_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("from_status", sa.String(length=80), nullable=True),
        sa.Column("to_status", sa.String(length=80), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["milestone_id"], ["project_milestone.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("project_task") as batch:
        batch.add_column(sa.Column("milestone_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("milestone_required", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("milestone_critical", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key("fk_project_task_milestone_id_project_milestone", "project_milestone", ["milestone_id"], ["id"])

    with op.batch_alter_table("material_request") as batch:
        batch.add_column(sa.Column("milestone_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("milestone_required", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("milestone_critical", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key("fk_material_request_milestone_id_project_milestone", "project_milestone", ["milestone_id"], ["id"])

    for table_name in ("document", "daily_site_report", "project_issue"):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(sa.Column("milestone_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f"fk_{table_name}_milestone_id_project_milestone",
                "project_milestone", ["milestone_id"], ["id"],
            )

    _seed_existing_projects()


def downgrade():
    for table_name in ("project_issue", "daily_site_report", "document"):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_constraint(f"fk_{table_name}_milestone_id_project_milestone", type_="foreignkey")
            batch.drop_column("milestone_id")

    with op.batch_alter_table("material_request") as batch:
        batch.drop_constraint("fk_material_request_milestone_id_project_milestone", type_="foreignkey")
        batch.drop_column("milestone_critical")
        batch.drop_column("milestone_required")
        batch.drop_column("milestone_id")

    with op.batch_alter_table("project_task") as batch:
        batch.drop_constraint("fk_project_task_milestone_id_project_milestone", type_="foreignkey")
        batch.drop_column("milestone_critical")
        batch.drop_column("milestone_required")
        batch.drop_column("milestone_id")

    op.drop_table("milestone_audit_log")
    op.drop_table("milestone_document_requirement")
    op.drop_index("ix_project_milestone_project_sequence", table_name="project_milestone")
    op.drop_table("project_milestone")
