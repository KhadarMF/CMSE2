"""Connect existing pumping projects to the new survey evidence type.

Only the unlinked default requirement is changed. Historical forms and
explicit document/form links are preserved.
"""
from alembic import op
import sqlalchemy as sa

revision = "b20k0000a002"
down_revision = "b20k0000a001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        UPDATE milestone_document_requirement
        SET form_key = 'solar-pump-survey', title = 'Approved Solar Pumping Site Survey'
        WHERE form_key = 'site-survey'
          AND title = 'Approved site survey & load assessment'
          AND form_record_id IS NULL AND document_id IS NULL
          AND milestone_id IN (
              SELECT m.id FROM project_milestone m JOIN project p ON p.id = m.project_id
              WHERE m.code = 'SURVEY' AND LOWER(p.project_type) LIKE '%pump%'
                AND m.status NOT IN ('Completed', 'Completed with Exception')
          )
    """))


def downgrade():
    # Preserve evidence configuration; reverting a data repair would overwrite
    # choices made by managers after upgrade.
    pass
