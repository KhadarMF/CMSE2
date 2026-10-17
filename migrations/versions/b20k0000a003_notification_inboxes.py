"""Give historical broadcasts and workflow notifications private inbox copies.

No email is sent by this migration. Original audit records are retained.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b20k0000a003'
down_revision = 'b20k0000a002'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()
    users = sa.Table('user', meta, autoload_with=bind)
    notes = sa.Table('system_notification', meta, autoload_with=bind)
    legacy = sa.Table('notification', meta, autoload_with=bind)
    active_ids = set(bind.execute(sa.select(users.c.id).where(users.c.is_active == True)).scalars())
    existing_refs = set(bind.execute(sa.select(notes.c.ref_no)).scalars())
    broadcasts = bind.execute(sa.select(notes).where(notes.c.target_user_id.is_(None))).mappings().all()
    for source in broadcasts:
        for user_id in sorted(active_ids):
            ref = f"BROADCAST-{source['id']}-{user_id}"
            if ref in existing_refs:
                continue
            values = {key: source[key] for key in ('title', 'message', 'category', 'priority', 'related_module', 'related_ref', 'created_at')}
            # A shared Read status cannot tell us which person actually read it.
            bind.execute(notes.insert().values(**values, ref_no=ref, target_user_id=user_id,
                                                status='Unread', read_at=None))
            existing_refs.add(ref)
    for source in bind.execute(sa.select(legacy)).mappings().all():
        ref = f"WORKFLOW-{source['id']}"
        if source['recipient_user_id'] not in active_ids or ref in existing_refs:
            continue
        bind.execute(notes.insert().values(ref_no=ref, target_user_id=source['recipient_user_id'],
            title=(source['subject'] or 'Workflow notification')[:180], message=source['message'],
            category='Workflow', priority='Medium', status='Unread', read_at=None,
            related_module=source['module'], related_ref=str(source['record_id']) if source['record_id'] is not None else None,
            created_at=source['created_at']))
        existing_refs.add(ref)
    indexes = {i['name'] for i in sa.inspect(bind).get_indexes('system_notification')}
    if 'ix_notification_inbox' not in indexes:
        op.create_index('ix_notification_inbox', 'system_notification', ['target_user_id', 'status', 'id'])


def downgrade():
    op.drop_index('ix_notification_inbox', table_name='system_notification')
    # Keep private copies and read history; deleting them would lose user data.
