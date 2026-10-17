"""Production-dialect regression for the simple progress data migration."""
from pathlib import Path


def test_requirement_insert_uses_boolean_literal():
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "b20k0000a004_simple_progress_formula.py"
    ).read_text(encoding="utf-8")

    normalized = " ".join(migration.split())
    assert (
        "VALUES (:milestone_id, :title, :form_key, :document_type, "
        "TRUE, :critical, :created_at)"
    ) in normalized
    assert (
        "VALUES (:milestone_id, :title, :form_key, :document_type, "
        "1, :critical, :created_at)"
    ) not in normalized
