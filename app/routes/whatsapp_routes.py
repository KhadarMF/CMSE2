import hashlib
import hmac
import json
import os
from datetime import datetime
from itsdangerous import URLSafeSerializer, BadSignature
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models import NotificationLog, WhatsAppMessage
from app.whatsapp_service import (
    whatsapp_config,
    is_whatsapp_configured,
    send_whatsapp_text,
    send_whatsapp_template,
    normalize_whatsapp_number,
    parse_incoming_whatsapp,
    extract_whatsapp_message_id,
    extract_whatsapp_statuses,
)

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')


def _json_short(data, limit=4000):
    try:
        return json.dumps(data, ensure_ascii=False)[:limit]
    except Exception:
        return str(data)[:limit]


def _status_time(timestamp):
    try:
        return datetime.utcfromtimestamp(int(timestamp))
    except Exception:
        return datetime.utcnow()


def create_whatsapp_message_log(*, direction='Outbound', recipient_name=None, phone_number=None,
                                template_name=None, message_body=None, variables=None,
                                document_type=None, document_id=None, document_ref=None,
                                response=None, ok=False, sent_by_id=None, status=None, error_message=None):
    """Create a WhatsAppMessage tracking record from a send response."""
    response = response or {}
    meta_message_id = extract_whatsapp_message_id(response)
    final_status = status or ('Sent' if ok else 'Failed')
    log = WhatsAppMessage(
        direction=direction,
        recipient_name=recipient_name,
        phone_number=normalize_whatsapp_number(phone_number or ''),
        template_name=template_name,
        message_body=message_body,
        variables_json=_json_short(variables or {}, 3000),
        document_type=document_type,
        document_id=document_id,
        document_ref=document_ref,
        meta_message_id=meta_message_id,
        status=final_status,
        error_message=error_message or (None if ok else _json_short(response, 1000)),
        provider_response=_json_short(response),
        sent_by_id=sent_by_id,
        sent_at=datetime.utcnow() if ok else None,
        failed_at=datetime.utcnow() if not ok else None,
    )
    db.session.add(log)
    return log


def update_whatsapp_message_status(message_id, status, payload=None, timestamp=None, error_message=None):
    if not message_id:
        return None
    msg = WhatsAppMessage.query.filter_by(meta_message_id=message_id).order_by(WhatsAppMessage.id.desc()).first()
    when = _status_time(timestamp) if timestamp else datetime.utcnow()
    if not msg:
        msg = WhatsAppMessage(
            direction='Status',
            meta_message_id=message_id,
            status=(status or 'Status').title(),
            provider_response=_json_short(payload or {}),
            raw_webhook_payload=_json_short(payload or {}),
        )
        db.session.add(msg)
    else:
        normalized = (status or '').lower()
        if normalized == 'sent':
            msg.status = 'Sent'
            msg.sent_at = msg.sent_at or when
        elif normalized == 'delivered':
            msg.status = 'Delivered'
            msg.delivered_at = when
        elif normalized == 'read':
            msg.status = 'Read'
            msg.read_at = when
        elif normalized == 'failed':
            msg.status = 'Failed'
            msg.failed_at = when
            msg.error_message = error_message or msg.error_message
        else:
            msg.status = (status or 'Status').title()
        msg.raw_webhook_payload = _json_short(payload or {})
        msg.provider_response = msg.provider_response or _json_short(payload or {})
    if error_message:
        msg.error_message = error_message
    return msg



def _quotation_resend_token(quotation):
    signer = URLSafeSerializer(current_app.config.get('SECRET_KEY', 'change-this-secret-key'), salt='quotation-public-link')
    return signer.dumps({'qid': quotation.id, 'ref': quotation.ref_no})


def _quotation_public_url_from_token(token):
    base = (whatsapp_config().get('public_base_url') or 'https://cmse2.onrender.com').rstrip('/')
    return f"{base}/sales/q/{token}"


def _quotation_template_name():
    return (os.environ.get('WHATSAPP_QUOTATION_TEMPLATE_NAME') or 'quotation_ready_v2').strip()


def _send_quotation_template_for_log(item):
    """Rebuild and resend a quotation WhatsApp template from a log record."""
    from app.models import SalesQuotation
    quotation = SalesQuotation.query.get(item.document_id)
    if not quotation:
        return False, {"error": {"message": "Related quotation was not found."}}, {}

    token = _quotation_resend_token(quotation)
    public_url = _quotation_public_url_from_token(token)
    customer_name = (quotation.customer_name or item.recipient_name or 'Customer').strip()
    quotation_ref = (quotation.ref_no or item.document_ref or f'Quotation-{quotation.id}').strip()

    ok, response = send_whatsapp_template(
        item.phone_number,
        template_name=_quotation_template_name(),
        language_code=os.environ.get('WHATSAPP_QUOTATION_TEMPLATE_LANGUAGE', 'en'),
        components=[
            {
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': customer_name},
                    {'type': 'text', 'text': quotation_ref},
                ],
            },
            {
                'type': 'button',
                'sub_type': 'url',
                'index': '0',
                'parameters': [
                    {'type': 'text', 'text': token},
                ],
            },
        ],
    )
    variables = {
        'customer_name': customer_name,
        'quotation_ref': quotation_ref,
        'quotation_token': token,
        'quotation_link': public_url,
        'resend_of': item.id,
    }
    return ok, response, variables



@whatsapp_bp.before_app_request
def ensure_whatsapp_tables():
    try:
        db.create_all()
    except Exception:
        pass

@whatsapp_bp.route('/webhook', methods=['GET'])
def webhook_verify():
    """Meta webhook verification endpoint.

    Configure this in Meta Developer Console:
    Callback URL: https://cmse2.onrender.com/whatsapp/webhook
    Verify Token: value of WHATSAPP_VERIFY_TOKEN
    """
    cfg = whatsapp_config()
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == cfg.get('verify_token'):
        return challenge or '', 200
    return 'Verification token mismatch', 403


@whatsapp_bp.route('/webhook', methods=['POST'])
def webhook_receive():
    # Verify Meta webhook signature (X-Hub-Signature-256)
    cfg = whatsapp_config()
    app_secret = cfg.get('verify_token', '')
    if app_secret:
        sig_header = request.headers.get('X-Hub-Signature-256', '')
        if sig_header:
            expected = 'sha256=' + hmac.new(
                app_secret.encode('utf-8'),
                request.get_data(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(sig_header, expected):
                return jsonify({'status': 'invalid signature'}), 403

    payload = request.get_json(silent=True) or {}
    statuses = extract_whatsapp_statuses(payload)
    info = parse_incoming_whatsapp(payload)
    try:
        for st in statuses:
            update_whatsapp_message_status(
                st.get('message_id'),
                st.get('status'),
                payload=payload,
                timestamp=st.get('timestamp'),
                error_message=st.get('error_message'),
            )
        if info:
            inbound_log = WhatsAppMessage(
                direction='Inbound',
                recipient_name=info.get('name') or info.get('from'),
                phone_number=info.get('from'),
                message_body=info.get('text') or json.dumps(payload)[:3000],
                meta_message_id=info.get('message_id'),
                status='Received',
                provider_response=json.dumps(payload)[:4000],
                raw_webhook_payload=json.dumps(payload)[:4000],
                sent_at=datetime.utcnow(),
            )
            db.session.add(inbound_log)
            db.session.add(NotificationLog(
                notification_ref=info.get('message_id') or None,
                recipient_name=info.get('name') or info.get('from'),
                channel='WhatsApp-Inbound',
                recipient=info.get('from'),
                subject=f"Inbound WhatsApp {info.get('type') or ''}".strip(),
                message=info.get('text') or json.dumps(payload)[:4000],
                related_module='WhatsApp Webhook',
                related_ref=info.get('message_id'),
                status='Received',
                provider_response=json.dumps(payload)[:4000],
                sent_at=datetime.utcnow(),
            ))
            db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({'status': 'ok'}), 200


@whatsapp_bp.route('/test', methods=['GET', 'POST'])
@login_required
def test_send():
    configured, config_message = is_whatsapp_configured()
    if request.method == 'POST':
        phone = request.form.get('phone')
        message = request.form.get('message') or 'Test message from Cadceed-Maal ERP.'
        ok, response = send_whatsapp_template(phone)
        log = NotificationLog(
            recipient_user_id=current_user.id,
            recipient_name=getattr(current_user, 'full_name', None),
            channel='WhatsApp',
            recipient=normalize_whatsapp_number(phone),
            subject='Manual WhatsApp Template Test',
            message='Template: cmse_test',
            related_module='WhatsApp Test',
            status='Sent' if ok else 'Failed',
            provider_response=json.dumps(response)[:4000],
            error_message=None if ok else json.dumps(response)[:1000],
            sent_at=datetime.utcnow() if ok else None,
            created_by_id=current_user.id,
        )
        db.session.add(log)
        create_whatsapp_message_log(
            recipient_name=getattr(current_user, 'full_name', None),
            phone_number=phone,
            template_name='cmse_test',
            message_body='Manual WhatsApp Template Test',
            variables={'test': True},
            document_type='WhatsApp Test',
            response=response,
            ok=ok,
            sent_by_id=current_user.id,
        )
        db.session.commit()
        flash('WhatsApp template test sent. Meta response: ' + json.dumps(response)[:300] if ok else f'WhatsApp failed: {response}', 'success' if ok else 'danger')
        return redirect(url_for('whatsapp.test_send'))
    cfg = whatsapp_config()
    return render_template('whatsapp/test.html', configured=configured, config_message=config_message, cfg=cfg)


@whatsapp_bp.route('/messages')
@login_required
def messages():
    status = request.args.get('status', '').strip()
    phone = request.args.get('phone', '').strip()
    template = request.args.get('template', '').strip()
    document_type = request.args.get('document_type', '').strip()
    q = WhatsAppMessage.query
    if status:
        q = q.filter(WhatsAppMessage.status == status)
    if phone:
        q = q.filter(WhatsAppMessage.phone_number.contains(normalize_whatsapp_number(phone) or phone))
    if template:
        q = q.filter(WhatsAppMessage.template_name.contains(template))
    if document_type:
        q = q.filter(WhatsAppMessage.document_type == document_type)
    items = q.order_by(WhatsAppMessage.created_at.desc()).limit(500).all()
    stats = {
        'total': WhatsAppMessage.query.count(),
        'sent': WhatsAppMessage.query.filter_by(status='Sent').count(),
        'delivered': WhatsAppMessage.query.filter_by(status='Delivered').count(),
        'read': WhatsAppMessage.query.filter_by(status='Read').count(),
        'failed': WhatsAppMessage.query.filter_by(status='Failed').count(),
        'received': WhatsAppMessage.query.filter_by(status='Received').count(),
    }
    statuses = ['Queued', 'Sent', 'Delivered', 'Read', 'Failed', 'Received']
    document_types = ['Sales Quotation', 'Invoice', 'Receipt', 'Delivery Note', 'WhatsApp Test']
    return render_template('whatsapp/messages.html', items=items, stats=stats, statuses=statuses, document_types=document_types, filters=request.args)


@whatsapp_bp.route('/messages/<int:message_id>')
@login_required
def message_detail(message_id):
    item = WhatsAppMessage.query.get_or_404(message_id)
    return render_template('whatsapp/message_detail.html', item=item)


@whatsapp_bp.route('/messages/<int:message_id>/resend', methods=['POST'])
@login_required
def resend_message(message_id):
    item = WhatsAppMessage.query.get_or_404(message_id)
    if item.direction != 'Outbound':
        flash('Only outbound WhatsApp messages can be resent.', 'warning')
        return redirect(url_for('whatsapp.message_detail', message_id=item.id))
    if not item.phone_number:
        flash('Cannot resend because the phone number is missing.', 'danger')
        return redirect(url_for('whatsapp.message_detail', message_id=item.id))

    if item.document_type == 'Sales Quotation' and item.document_id:
        ok, response, variables = _send_quotation_template_for_log(item)
        template_name = _quotation_template_name()
        body = item.message_body or 'Quotation WhatsApp resend'
    else:
        # Fallback: resend the manual test template.
        ok, response = send_whatsapp_template(item.phone_number)
        variables = {'resend_of': item.id, 'fallback': True}
        template_name = item.template_name or 'cmse_test'
        body = item.message_body or 'WhatsApp resend'

    new_log = create_whatsapp_message_log(
        recipient_name=item.recipient_name,
        phone_number=item.phone_number,
        template_name=template_name,
        message_body=body,
        variables=variables,
        document_type=item.document_type,
        document_id=item.document_id,
        document_ref=item.document_ref,
        response=response,
        ok=ok,
        sent_by_id=current_user.id,
    )
    db.session.commit()
    if ok:
        flash(f'WhatsApp message resent successfully. New log #{new_log.id}.', 'success')
        return redirect(url_for('whatsapp.message_detail', message_id=new_log.id))
    flash(f'WhatsApp resend failed: {response}', 'danger')
    return redirect(url_for('whatsapp.message_detail', message_id=item.id))


@whatsapp_bp.route('/health')
@login_required
def health():
    configured, message = is_whatsapp_configured()
    cfg = whatsapp_config()
    return jsonify({
        'configured': configured,
        'message': message,
        'phone_number_id': cfg.get('phone_number_id'),
        'business_account_id': cfg.get('business_account_id'),
        'webhook_url': f"{cfg.get('public_base_url')}/whatsapp/webhook" if cfg.get('public_base_url') else None,
    })
