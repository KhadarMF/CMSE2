from datetime import date
import pytest
from flask import g


def user(name, role='Site Supervisor', active=True):
    from app import db
    from app.models import User
    from werkzeug.security import generate_password_hash
    item = User(full_name=name, email=name.lower()+'@example.invalid', role=role,
                password_hash=generate_password_hash('Synthetic-Password-Only!'), is_active=active)
    db.session.add(item); db.session.flush()
    return item


def login(client, item):
    g.pop('_login_user', None)
    with client.session_transaction() as session:
        session.clear(); session['_user_id'] = str(item.id); session['_fresh'] = True


def permission(item, key, **actions):
    from app import db
    from app.models import UserFormPermission
    db.session.add(UserFormPermission(user_id=item.id, form_key=key, **actions))


def test_private_broadcast_inboxes_and_read_ownership(app, client):
    from app import db
    from app.models import SystemNotification, NotificationLog
    admin, alice, bob = user('Admin', 'Admin'), user('Alice'), user('Bob')
    user('Inactive', active=False)
    db.session.commit(); login(client, admin)
    response = client.post('/notifications/create', data={'title':'Team meeting', 'message':'Synthetic announcement'})
    assert response.status_code == 302
    notes = SystemNotification.query.filter_by(title='Team meeting').all()
    assert {n.target_user_id for n in notes} == {admin.id, alice.id, bob.id}
    assert NotificationLog.query.filter_by(channel='Email').count() == 0
    a = next(n for n in notes if n.target_user_id == alice.id)
    b = next(n for n in notes if n.target_user_id == bob.id)
    login(client, alice)
    assert client.get('/notifications/').status_code == 200  # no module assignment needed
    assert client.get('/notifications/unread-count').json['unread'] == 1
    assert client.post(f'/notifications/{b.id}/read').status_code == 403
    assert client.post(f'/notifications/{a.id}/read').status_code == 302
    assert client.get('/notifications/unread-count').json['unread'] == 0
    login(client, bob)
    assert client.get('/notifications/unread-count').json['unread'] == 1
    # Personal inbox permission never grants notification creation.
    assert client.post('/notifications/create', data={'title':'Denied','message':'Denied'}).status_code == 302
    assert not SystemNotification.query.filter_by(title='Denied').first()


def test_private_contents_counts_and_logs_cannot_be_read_by_other_users(app, client):
    from app import db
    from app.notification_gateway import create_notification_event
    admin, alice, bob = user('Admin','Admin'), user('Alice'), user('Bob')
    permission(alice, 'notification-log', can_view=True, can_edit=True)
    create_notification_event('ALICE PRIVATE', 'Alice message', alice, created_by_id=admin.id)
    note = create_notification_event('BOB PRIVATE', 'Bob message', bob, created_by_id=admin.id, send_email_now=True)
    db.session.commit(); login(client, alice)
    page = client.get('/notifications/?all=1').get_data(as_text=True)
    assert 'ALICE PRIVATE' in page and 'BOB PRIVATE' not in page
    assert 'id="notificationUnreadTotal">1</h3>' in page
    assert 'BOB PRIVATE' not in client.get('/notifications/logs').get_data(as_text=True)
    from app.models import NotificationLog
    log = NotificationLog.query.filter_by(notification_ref=note.ref_no,channel='Email').one()
    assert client.post(f'/notifications/email/send/{log.id}').status_code == 404


@pytest.mark.parametrize('target', ['999999', 'not-an-id', 'inactive'])
def test_invalid_recipient_never_becomes_broadcast(app, client, target):
    from app import db
    from app.models import SystemNotification
    admin, inactive = user('Admin','Admin'), user('Inactive',active=False)
    db.session.commit(); login(client, admin)
    result=client.post('/notifications/create',data={'title':'Private','message':'Private','target_user_id':str(inactive.id) if target=='inactive' else target})
    assert result.status_code == 400
    assert SystemNotification.query.count() == 0


def test_broadcast_email_commits_before_delivery_and_does_not_resend(app, client, monkeypatch):
    from app import db
    from app.models import NotificationLog
    import app.notifications as service
    from sqlalchemy import create_engine, text
    admin, alice = user('Admin','Admin'), user('Alice')
    db.session.commit(); login(client, admin)
    calls=[]
    def smtp_stub(recipient, subject, message):
        # Separate connection proves both inbox and outbox survived the business commit.
        engine=create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        with engine.connect() as connection:
            assert connection.execute(text('select count(*) from system_notification')).scalar() == 2
        engine.dispose(); calls.append(recipient)
    monkeypatch.setattr(service,'send_email',smtp_stub)
    result=client.post('/notifications/create',data={'title':'Broadcast','message':'Synthetic','send_email_now':'on'})
    assert result.status_code == 302
    assert set(calls)=={admin.email,alice.email}
    logs=NotificationLog.query.filter_by(channel='Email').all()
    assert all(log.status=='Sent' for log in logs)
    client.post(f'/notifications/email/send/{logs[0].id}')
    assert len(calls)==2


def test_failed_email_keeps_inbox_and_can_be_retried(app, client, monkeypatch):
    from app import db
    from app.models import SystemNotification, NotificationLog
    import app.notifications as service
    admin, alice=user('Admin','Admin'),user('Alice')
    db.session.commit();login(client,admin)
    def fail(*args): raise RuntimeError('SMTP temporarily unavailable')
    monkeypatch.setattr(service,'send_email',fail)
    client.post('/notifications/create',data={'title':'Urgent','message':'Synthetic','target_user_id':alice.id,'send_email_now':'on'})
    assert SystemNotification.query.filter_by(target_user_id=alice.id,status='Unread').count()==1
    log=NotificationLog.query.filter_by(channel='Email').one()
    assert log.status=='Failed' and 'SMTP temporarily unavailable' in log.error_message
    monkeypatch.setattr(service,'send_email',lambda *args: None)
    client.post(f'/notifications/email/send/{log.id}')
    db.session.refresh(log)
    assert log.status=='Sent'


def test_rollback_does_not_send_or_leave_an_inbox_record(app, client, monkeypatch):
    from app import db
    from app.notification_gateway import create_notification_event
    from app.models import SystemNotification, NotificationLog
    import app.notifications as service
    admin=user('Admin','Admin');db.session.commit();login(client,admin)
    calls=[];monkeypatch.setattr(service,'send_email',lambda *args:calls.append(args))
    @app.route('/test-rollback',methods=['POST'])
    def rollback_route():
        create_notification_event('Rollback','Synthetic',admin,send_email_now=True)
        db.session.rollback()
        return 'Rolled back'
    assert client.post('/test-rollback').status_code==200
    assert not calls
    assert SystemNotification.query.count()==NotificationLog.query.count()==0


@pytest.mark.parametrize('form_key', ['site-survey','solar-pump-survey','load-assessment','daily-site-report','delivery-note','testing','commissioning','handover'])
def test_every_form_notifies_approver_then_creator(app, client, monkeypatch, form_key):
    from app import db
    from app.models import Project, SystemNotification, NotificationLog
    from app.routes.form_routes import FORM_CONFIG
    import app.notifications as service
    monkeypatch.setattr(service,'send_email',lambda *args:None)
    creator, approver, unrelated = user('Creator'), user('Approver','Admin'), user('Unrelated','Management')
    permission(creator, form_key, can_view=True, can_create=True, can_edit=True)
    project=Project(project_name='Audit Project',customer_name='Demo',location='Demo',project_type='Solar Off-Grid',status='Survey',created_by_id=creator.id)
    db.session.add(project);db.session.flush()
    entry=FORM_CONFIG[form_key]['model'](project_id=project.id, created_by_id=creator.id, approval_status='Draft')
    if form_key=='daily-site-report':
        # Admin creator can submit a legacy daily report without a team.
        creator.role='Admin';entry.report_date=date.today();entry.work_done_today='Synthetic'
    db.session.add(entry);db.session.commit()
    login(client,creator)
    response=client.post(f'/forms/{form_key}/{entry.id}/submit')
    assert response.status_code==302
    notes=SystemNotification.query.filter_by(related_module=form_key).all()
    assert len(notes)==1 and notes[0].target_user_id==approver.id
    assert NotificationLog.query.filter_by(channel='Email',status='Sent').count()==1
    # A duplicate submit must not deliver a duplicate alert.
    client.post(f'/forms/{form_key}/{entry.id}/submit')
    assert SystemNotification.query.count()==1
    login(client,approver)
    client.post(f'/forms/{form_key}/{entry.id}/review',data={'approval_status':'Approved','manager_comments':'Checked'})
    assert SystemNotification.query.filter_by(target_user_id=creator.id, related_module=form_key).count()==1
    assert SystemNotification.query.filter_by(target_user_id=unrelated.id).count()==0
    assert NotificationLog.query.filter_by(channel='Email',status='Sent').count()==2


def test_workflow_helpers_share_inbox_and_outbox(app, client, monkeypatch):
    from app import db
    from app.models import Notification, SystemNotification, NotificationLog
    from app.notifications import notify_user
    import app.notifications as service
    admin=user('Admin','Admin');db.session.commit();login(client,admin)
    calls=[];monkeypatch.setattr(service,'send_email',lambda *args:calls.append(args))
    @app.route('/test-workflow',methods=['POST'])
    def workflow():
        notify_user(admin,'Workflow event','Synthetic','Document',7)
        db.session.commit()
        return 'Saved'
    client.post('/test-workflow')
    assert len(calls)==1
    assert SystemNotification.query.filter_by(target_user_id=admin.id).count()==1
    assert Notification.query.one().status=='Sent'
    assert NotificationLog.query.filter_by(channel='Email').one().status=='Sent'


def test_sms_manual_status_matches_log_and_missing_phone_is_reported(app, client):
    from app import db
    from app.models import SMSQueue, NotificationLog
    admin=user('Admin','Admin');db.session.commit();login(client,admin)
    client.post('/notifications/create',data={'title':'SMS','message':'Synthetic','target_user_id':admin.id,'queue_sms':'on'})
    assert 'phone' in NotificationLog.query.filter_by(channel='SMS',status='Failed').one().error_message
    client.post('/notifications/sms-queue/create',data={'phone_number':'+000000000','recipient_name':'Demo','message':'Synthetic'})
    sms=SMSQueue.query.one()
    client.post(f'/notifications/sms-queue/{sms.id}/sent')
    assert NotificationLog.query.filter_by(notification_ref=sms.ref_no).one().status=='Sent'


def test_historical_migration_preserves_and_scopes_notifications(app):
    from app import db
    from app.models import SystemNotification, Notification
    from flask_migrate import downgrade, upgrade
    admin, alice=user('Admin','Admin'),user('Alice')
    user('Inactive',active=False)
    db.session.add(SystemNotification(ref_no='OLD-BROADCAST',title='Old broadcast',status='Read'))
    legacy=Notification(recipient_user_id=alice.id,recipient_email=alice.email,subject='Old workflow',message='Old message',status='Failed')
    db.session.add(legacy);db.session.commit();legacy_id=legacy.id
    downgrade(revision='b20k0000a002');upgrade()
    copies=SystemNotification.query.filter_by(title='Old broadcast',status='Unread').all()
    assert {n.target_user_id for n in copies}=={admin.id,alice.id}
    assert SystemNotification.query.filter_by(ref_no=f'WORKFLOW-{legacy_id}',target_user_id=alice.id).count()==1
    count=SystemNotification.query.count()
    downgrade(revision='b20k0000a002');upgrade()
    assert SystemNotification.query.count()==count


def test_cli_recovers_queued_mail_but_not_sent_or_uncertain_attempts(app, monkeypatch):
    from app import db
    from app.models import NotificationLog
    import app.notifications as service
    calls=[];monkeypatch.setattr(service,'send_email',lambda *args:calls.append(args))
    for status in ['Queued','Sent','Sending','Failed']:
        db.session.add(NotificationLog(channel='Email',status=status,recipient='demo@example.invalid',subject=status,message='Synthetic'))
    db.session.commit()
    result=app.test_cli_runner().invoke(args=['notifications-send'])
    assert result.exit_code==0 and len(calls)==1
    assert calls[0][1]=='Queued'
    result=app.test_cli_runner().invoke(args=['notifications-send','--retry-failed'])
    assert result.exit_code==0 and len(calls)==2
    assert calls[1][1]=='Failed'
