"""Phase 20G: bridge legacy Payments/Accounting schemas to Phase 20D+.

Some long-running installations were created with ``db.create_all()`` while
the application still used the original Phase 19 payment and accounting
models.  Stamping those databases at the Phase 20D baseline correctly told
Alembic not to recreate their business tables, but the baseline could not
change tables which already existed.  The result was a stamped database whose
``payment_request`` table, for example, did not have ``requested_by_id``.

This migration is deliberately additive and data-preserving.  It:

* creates the new accounting tables which are absent on a legacy database and
  copies the old chart of accounts with the same primary keys;
* extends legacy journal tables and redirects journal-line account references
  to the current ``account`` table;
* adds and backfills the current payment-request fields from their legacy
  equivalents; and
* creates payment rows for legacy requests which were already marked Paid.

Legacy-only tables and columns are retained.  They are harmless to SQLAlchemy
and keeping them makes the migration reversible from a business-data point of
view: no historical value is discarded.

Revision ID: b20g0000a001
Revises: b20d0000a001
"""

from alembic import op
import sqlalchemy as sa


revision = "b20g0000a001"
down_revision = "b20d0000a001"
branch_labels = None
depends_on = None


FK_NAMING = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _bind():
    return op.get_bind()


def _inspector():
    return sa.inspect(_bind())


def _tables():
    return set(_inspector().get_table_names())


def _columns(table):
    if table not in _tables():
        return {}
    return {column["name"]: column for column in _inspector().get_columns(table)}


def _has_column(table, column):
    return column in _columns(table)


def _scalar(sql, **params):
    return _bind().execute(sa.text(sql), params).scalar()


def _add_missing_columns(table, definitions):
    """Add all missing definitions in one batch (one SQLite table rebuild)."""
    existing = _columns(table)
    missing = [column for column in definitions if column.name not in existing]
    if not missing:
        return
    with op.batch_alter_table(table, naming_convention=FK_NAMING) as batch:
        for column in missing:
            batch.add_column(column)


def _create_current_account_tables():
    tables = _tables()
    if "account" not in tables:
        op.create_table(
            "account",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("account_type", sa.String(length=30), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["parent_id"], ["account.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )

    # Preserve the former chart of accounts.  IDs are deliberately retained
    # so existing journal_line.account_id values still identify the same row.
    if "accounting_account" in _tables():
        _bind().execute(
            sa.text(
                """
                INSERT INTO account
                    (id, code, name, account_type, parent_id, description,
                     is_active, is_system, created_at)
                SELECT legacy.id, substr(legacy.code, 1, 20), legacy.name,
                       substr(legacy.account_type, 1, 30), legacy.parent_id,
                       legacy.description, legacy.is_active, :is_system,
                       legacy.created_at
                  FROM accounting_account AS legacy
                 WHERE NOT EXISTS (
                       SELECT 1 FROM account AS current_account
                        WHERE current_account.id = legacy.id
                           OR current_account.code = substr(legacy.code, 1, 20)
                 )
                """
            ),
            {"is_system": False},
        )

    # Defensive repair for an old journal row whose account record was
    # already missing.  It is better to expose a clearly-labelled placeholder
    # than to delete the journal line or make the FK upgrade fail.
    if "journal_line" in _tables() and _has_column("journal_line", "account_id"):
        _bind().execute(
            sa.text(
                """
                INSERT INTO account
                    (id, code, name, account_type, is_active, is_system)
                SELECT DISTINCT line.account_id,
                       'LEGACY-' || CAST(line.account_id AS VARCHAR(12)),
                       'Recovered legacy account ' || CAST(line.account_id AS VARCHAR(12)),
                       'Expense', :is_active, :is_system
                  FROM journal_line AS line
                 WHERE line.account_id IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM account
                        WHERE account.id = line.account_id
                 )
                """
            ),
            {"is_active": True, "is_system": False},
        )

    if _bind().dialect.name == "postgresql":
        # Explicit-ID copies do not advance a PostgreSQL sequence.
        _bind().execute(
            sa.text(
                """
                SELECT setval(
                    pg_get_serial_sequence('account', 'id'),
                    GREATEST(COALESCE((SELECT MAX(id) FROM account), 1), 1),
                    true
                )
                """
            )
        )

    if "account_mapping" not in _tables():
        op.create_table(
            "account_mapping",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("mapping_type", sa.String(length=40), nullable=False),
            sa.Column("key", sa.String(length=120), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "mapping_type", "key", name="uq_account_mapping_type_key"
            ),
        )


def _extend_journal_entry():
    if "journal_entry" not in _tables():
        return

    _add_missing_columns(
        "journal_entry",
        [
            sa.Column("reference", sa.String(length=180), nullable=True),
            sa.Column("source_record_id", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=True),
            sa.Column("original_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("posted_by_id", sa.Integer(), nullable=True),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("reversed_by_entry_id", sa.Integer(), nullable=True),
            sa.Column("reverses_entry_id", sa.Integer(), nullable=True),
        ],
    )

    cols = _columns("journal_entry")
    if "source_ref" in cols:
        _bind().execute(
            sa.text(
                "UPDATE journal_entry SET reference = source_ref "
                "WHERE reference IS NULL AND source_ref IS NOT NULL"
            )
        )
    _bind().execute(
        sa.text(
            "UPDATE journal_entry SET currency = 'USD' WHERE currency IS NULL"
        )
    )
    _bind().execute(
        sa.text(
            "UPDATE journal_entry SET exchange_rate = 1 WHERE exchange_rate IS NULL"
        )
    )

    cols = _columns("journal_entry")
    if cols.get("entry_no", {}).get("nullable") is False:
        with op.batch_alter_table(
            "journal_entry", naming_convention=FK_NAMING
        ) as batch:
            batch.alter_column(
                "entry_no",
                existing_type=cols["entry_no"]["type"],
                nullable=True,
            )


def _repair_journal_line():
    if "journal_line" not in _tables():
        return

    inspector = _inspector()
    existing = {column["name"] for column in inspector.get_columns("journal_line")}
    foreign_keys = inspector.get_foreign_keys("journal_line")
    wrong = [
        fk
        for fk in foreign_keys
        if fk.get("constrained_columns") == ["account_id"]
        and fk.get("referred_table") != "account"
    ]
    correct = any(
        fk.get("constrained_columns") == ["account_id"]
        and fk.get("referred_table") == "account"
        for fk in foreign_keys
    )

    if _bind().dialect.name == "sqlite":
        # SQLite cannot ALTER a foreign key.  Batch mode rebuilds the table,
        # while the naming convention gives old unnamed constraints a stable
        # name which Alembic can remove.
        with op.batch_alter_table(
            "journal_line", naming_convention=FK_NAMING, recreate="always"
        ) as batch:
            if "line_order" not in existing:
                batch.add_column(sa.Column("line_order", sa.Integer(), nullable=True))
            for fk in wrong:
                name = fk.get("name") or (
                    "fk_journal_line_account_id_" + fk.get("referred_table", "account")
                )
                batch.drop_constraint(name, type_="foreignkey")
            if not correct:
                batch.create_foreign_key(
                    "fk_journal_line_account_id_account",
                    "account",
                    ["account_id"],
                    ["id"],
                )
    else:
        if "line_order" not in existing:
            op.add_column(
                "journal_line", sa.Column("line_order", sa.Integer(), nullable=True)
            )
        for fk in wrong:
            if fk.get("name"):
                op.drop_constraint(fk["name"], "journal_line", type_="foreignkey")
        if not correct:
            op.create_foreign_key(
                "fk_journal_line_account_id_account",
                "journal_line",
                "account",
                ["account_id"],
                ["id"],
            )

    _bind().execute(
        sa.text("UPDATE journal_line SET line_order = id WHERE line_order IS NULL")
    )


PAYMENT_COLUMNS = [
    sa.Column("requested_by_id", sa.Integer(), nullable=True),
    sa.Column("branch_id", sa.Integer(), nullable=True),
    sa.Column("material_request_id", sa.Integer(), nullable=True),
    sa.Column("payee_name", sa.String(length=180), nullable=True),
    sa.Column("payee_phone", sa.String(length=80), nullable=True),
    sa.Column("category", sa.String(length=100), nullable=True),
    sa.Column("purpose", sa.Text(), nullable=True),
    sa.Column("needed_by_date", sa.Date(), nullable=True),
    sa.Column("manager_approved_by_id", sa.Integer(), nullable=True),
    sa.Column("manager_approved_at", sa.DateTime(), nullable=True),
    sa.Column("manager_comment", sa.Text(), nullable=True),
    sa.Column("finance_approved_by_id", sa.Integer(), nullable=True),
    sa.Column("finance_approved_at", sa.DateTime(), nullable=True),
    sa.Column("finance_comment", sa.Text(), nullable=True),
    sa.Column("rejected_by_id", sa.Integer(), nullable=True),
    sa.Column("rejected_at", sa.DateTime(), nullable=True),
    sa.Column("rejection_reason", sa.Text(), nullable=True),
    sa.Column("rejected_at_stage", sa.String(length=80), nullable=True),
    sa.Column("cancelled_by_id", sa.Integer(), nullable=True),
    sa.Column("cancelled_at", sa.DateTime(), nullable=True),
    sa.Column("attachment_original_name", sa.String(length=255), nullable=True),
    sa.Column("attachment_stored_name", sa.String(length=255), nullable=True),
]


def _extend_payment_request():
    if "payment_request" not in _tables():
        return

    _add_missing_columns("payment_request", PAYMENT_COLUMNS)
    cols = _columns("payment_request")

    if "created_by_id" in cols:
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET requested_by_id = created_by_id "
                "WHERE requested_by_id IS NULL"
            )
        )

    # If a corrupt legacy row has no creator, use the oldest existing user.
    # This keeps the row accessible without inventing or deleting a user.
    fallback_user_id = None
    if "user" in _tables():
        fallback_user_id = _scalar('SELECT MIN(id) FROM "user"')
    if fallback_user_id is not None:
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET requested_by_id = :user_id "
                "WHERE requested_by_id IS NULL"
            ),
            {"user_id": fallback_user_id},
        )
        _bind().execute(
            sa.text(
                'UPDATE payment_request SET branch_id = '
                '(SELECT u.branch_id FROM "user" AS u '
                ' WHERE u.id = payment_request.requested_by_id) '
                'WHERE branch_id IS NULL'
            )
        )

    if "vendor_name" in cols:
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET payee_name = vendor_name "
                "WHERE payee_name IS NULL AND vendor_name IS NOT NULL "
                "AND trim(vendor_name) <> ''"
            )
        )
    _bind().execute(
        sa.text(
            "UPDATE payment_request SET payee_name = 'Unspecified payee' "
            "WHERE payee_name IS NULL OR trim(payee_name) = ''"
        )
    )

    if "description" in cols:
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET purpose = description "
                "WHERE purpose IS NULL AND description IS NOT NULL "
                "AND trim(description) <> ''"
            )
        )
    if "payment_type" in cols:
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET category = payment_type "
                "WHERE category IS NULL AND payment_type IS NOT NULL "
                "AND trim(payment_type) <> ''"
            )
        )
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET purpose = payment_type "
                "WHERE purpose IS NULL AND payment_type IS NOT NULL "
                "AND trim(payment_type) <> ''"
            )
        )
    _bind().execute(
        sa.text(
            "UPDATE payment_request SET category = 'Other' "
            "WHERE category IS NULL OR trim(category) = ''"
        )
    )
    _bind().execute(
        sa.text(
            "UPDATE payment_request SET purpose = 'Legacy payment request' "
            "WHERE purpose IS NULL OR trim(purpose) = ''"
        )
    )

    if "due_date" in cols:
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET needed_by_date = due_date "
                "WHERE needed_by_date IS NULL"
            )
        )
    if "finance_notes" in cols:
        _bind().execute(
            sa.text(
                "UPDATE payment_request SET finance_comment = finance_notes "
                "WHERE finance_comment IS NULL"
            )
        )

    if "payment_attachment" in _tables():
        attachment_cols = _columns("payment_attachment")
        if {"payment_request_id", "original_filename", "stored_filename"}.issubset(
            attachment_cols
        ):
            _bind().execute(
                sa.text(
                    """
                    UPDATE payment_request
                       SET attachment_original_name = (
                               SELECT a.original_filename
                                 FROM payment_attachment AS a
                                WHERE a.payment_request_id = payment_request.id
                                ORDER BY a.id LIMIT 1
                           ),
                           attachment_stored_name = (
                               SELECT a.stored_filename
                                 FROM payment_attachment AS a
                                WHERE a.payment_request_id = payment_request.id
                                ORDER BY a.id LIMIT 1
                           )
                     WHERE attachment_original_name IS NULL
                       AND EXISTS (
                               SELECT 1 FROM payment_attachment AS a
                                WHERE a.payment_request_id = payment_request.id
                           )
                    """
                )
            )

    # Translate legacy workflow labels to the statuses the current UI uses.
    _bind().execute(
        sa.text(
            """
            UPDATE payment_request
               SET status = CASE lower(trim(COALESCE(status, '')))
                   WHEN 'paid' THEN 'Paid'
                   WHEN 'payment completed' THEN 'Paid'
                   WHEN 'partially paid' THEN 'Partially Paid'
                   WHEN 'approved' THEN 'Approved'
                   WHEN 'finance approved' THEN 'Approved'
                   WHEN 'pending finance approval' THEN 'Pending Finance Approval'
                   WHEN 'manager approved' THEN 'Pending Finance Approval'
                   WHEN 'rejected' THEN 'Rejected'
                   WHEN 'cancelled' THEN 'Cancelled'
                   WHEN 'canceled' THEN 'Cancelled'
                   WHEN 'pending manager approval' THEN 'Pending Manager Approval'
                   ELSE 'Pending Manager Approval'
               END
            """
        )
    )

    # The old schema required request_no at INSERT time, but the current code
    # builds its collision-proof number after flush() assigns the primary key.
    cols = _columns("payment_request")
    changes = []
    if cols.get("request_no", {}).get("nullable") is False:
        changes.append(("request_no", cols["request_no"]["type"], True))
    for name in ("requested_by_id", "payee_name", "purpose"):
        if name in cols and cols[name].get("nullable") is True:
            nulls = _scalar(
                f'SELECT COUNT(*) FROM payment_request WHERE "{name}" IS NULL'
            )
            if not nulls:
                changes.append((name, cols[name]["type"], False))
    if changes:
        with op.batch_alter_table(
            "payment_request", naming_convention=FK_NAMING
        ) as batch:
            for name, existing_type, nullable in changes:
                batch.alter_column(
                    name, existing_type=existing_type, nullable=nullable
                )


def _create_and_backfill_payment_rows():
    if "payment_request" not in _tables():
        return

    if "payment_request_payment" not in _tables():
        op.create_table(
            "payment_request_payment",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("payment_request_id", sa.Integer(), nullable=False),
            sa.Column("payment_date", sa.Date(), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("payment_method", sa.String(length=80), nullable=True),
            sa.Column("reference_no", sa.String(length=150), nullable=True),
            sa.Column("payee_phone", sa.String(length=80), nullable=True),
            sa.Column("proof_original_name", sa.String(length=255), nullable=True),
            sa.Column("proof_stored_name", sa.String(length=255), nullable=True),
            sa.Column("paid_by_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["paid_by_id"], ["user.id"]),
            sa.ForeignKeyConstraint(
                ["payment_request_id"], ["payment_request.id"]
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    cols = _columns("payment_request")
    # This INSERT is only needed for the legacy single-payment representation.
    if not {"paid_date", "payment_method", "paid_by_id"}.intersection(cols):
        return

    def expr(column, fallback="NULL"):
        return column if column in cols else fallback

    payment_date = "CURRENT_DATE"
    date_options = [
        column
        for column in ("paid_date", "due_date", "request_date", "created_at")
        if column in cols
    ]
    if date_options:
        payment_date = "COALESCE(" + ", ".join(date_options + ["CURRENT_DATE"]) + ")"

    paid_marker = "status = 'Paid'"
    if "paid_date" in cols:
        paid_marker = "(status = 'Paid' OR paid_date IS NOT NULL)"

    reference_parts = [
        column for column in ("paid_reference_no", "paid_cheque_no") if column in cols
    ]
    reference_expr = (
        "COALESCE(" + ", ".join(reference_parts) + ")"
        if reference_parts
        else "NULL"
    )

    sql = f"""
        INSERT INTO payment_request_payment
            (payment_request_id, payment_date, amount, currency,
             payment_method, reference_no, payee_phone,
             proof_original_name, proof_stored_name, paid_by_id,
             notes, created_at)
        SELECT legacy.id,
               {payment_date},
               legacy.amount,
               COALESCE(legacy.currency, 'USD'),
               COALESCE({expr('payment_method', "'Other'")}, 'Other'),
               {reference_expr},
               legacy.payee_phone,
               legacy.attachment_original_name,
               legacy.attachment_stored_name,
               {expr('paid_by_id')},
               {expr('payment_notes')},
               legacy.created_at
          FROM payment_request AS legacy
         WHERE {paid_marker}
           AND legacy.amount IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM payment_request_payment AS payment
                WHERE payment.payment_request_id = legacy.id
           )
    """
    _bind().execute(sa.text(sql))


def upgrade():
    _create_current_account_tables()
    _extend_journal_entry()
    _repair_journal_line()
    _extend_payment_request()
    _create_and_backfill_payment_rows()


def downgrade():
    # The bridge copies and normalizes business data.  An automatic downgrade
    # would have to discard that data, so recovery must use the backup which
    # the deployment guide requires before running migrations.
    raise RuntimeError(
        "Phase 20G is a data-preserving legacy bridge and cannot be "
        "automatically downgraded. Restore the pre-upgrade backup instead."
    )
