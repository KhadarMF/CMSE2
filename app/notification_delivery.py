"""Durable email outbox. Delivery happens only after the business transaction commits."""
from datetime import datetime
import click
from flask import g, has_request_context, current_app
from sqlalchemy import event
from sqlalchemy.orm import Session
from app import db
from app.models import NotificationLog, Notification


def queue_email(log):
    db.session.flush()
    db.session.info.setdefault('notification_email_ids', set()).add(log.id)


@event.listens_for(Session, 'after_commit')
def _committed(session):
    ids = session.info.pop('notification_email_ids', set())
    if ids and has_request_context():
        g.setdefault('committed_notification_email_ids', set()).update(ids)


@event.listens_for(Session, 'after_rollback')
def _rolled_back(session):
    session.info.pop('notification_email_ids', None)


def deliver_email(log_id, retry_failed=False):
    """Claim once across workers; uncertain Sending attempts require operator review."""
    states = ['Queued', 'Pending'] + (['Failed'] if retry_failed else [])
    changed = NotificationLog.query.filter(
        NotificationLog.id == log_id, NotificationLog.channel == 'Email',
        NotificationLog.status.in_(states),
    ).update({'status': 'Sending', 'error_message': None}, synchronize_session=False)
    db.session.commit()
    if not changed:
        return None
    log = db.session.get(NotificationLog, log_id)
    try:
        from app.notifications import send_email
        send_email(log.recipient, log.subject or 'ERP Notification', log.message or '')
        log.status, log.sent_at, log.error_message = 'Sent', datetime.utcnow(), None
    except Exception as exc:
        log.status, log.error_message = 'Failed', str(exc)[:2000]
    if (log.notification_ref or '').startswith('WORKFLOW-'):
        legacy = db.session.get(Notification, int(log.notification_ref.split('-')[1]))
        if legacy:
            legacy.status, legacy.sent_at, legacy.error_message = log.status, log.sent_at, log.error_message
    db.session.commit()
    return log.status


def register_notification_delivery(app):
    @app.after_request
    def deliver_committed_notifications(response):
        ids = g.pop('committed_notification_email_ids', set())
        for log_id in sorted(ids):
            try:
                deliver_email(log_id)
            except Exception:
                db.session.rollback()
                current_app.logger.exception('Email outbox delivery interrupted for log %s', log_id)
        return response

    @app.cli.command('notifications-send')
    @click.option('--retry-failed', is_flag=True, help='Also retry known failed attempts.')
    @click.option('--limit', default=100, type=click.IntRange(1, 1000))
    def notifications_send(retry_failed, limit):
        """Recover committed queued email after interruption. Sent mail is never resent."""
        states = ['Queued', 'Pending'] + (['Failed'] if retry_failed else [])
        ids = [row.id for row in NotificationLog.query.filter(
            NotificationLog.channel == 'Email', NotificationLog.status.in_(states)
        ).order_by(NotificationLog.id).limit(limit).all()]
        counts = {'Sent': 0, 'Failed': 0, 'Skipped': 0}
        for log_id in ids:
            result = deliver_email(log_id, retry_failed)
            counts[result or 'Skipped'] += 1
        click.echo(str(counts))
