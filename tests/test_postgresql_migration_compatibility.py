"""Database-dialect regressions for production migrations."""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def _load_migration_module():
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "b20i0000a001_phase20i_milestone_engine.py"
    )
    spec = importlib.util.spec_from_file_location("phase20i_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_milestone_requirement_seed_uses_postgresql_boolean_literals():
    migration = _load_migration_module()
    metadata = sa.MetaData()
    requirement = sa.Table(
        "milestone_document_requirement",
        metadata,
        sa.Column("milestone_id", sa.Integer),
        sa.Column("title", sa.String),
        sa.Column("form_key", sa.String),
        sa.Column("document_type", sa.String),
        sa.Column("is_required", sa.Boolean),
        sa.Column("is_critical", sa.Boolean),
    )
    values = migration._requirement_values(
        121, "Approved quotation", None, "Quotation", True
    )

    sql = str(
        requirement.insert()
        .values(**values)
        .compile(dialect=postgresql.dialect())
    ).lower()

    assert "is_required" in sql
    assert "true" in sql
    assert " false" not in sql
    assert ", 1," not in sql

