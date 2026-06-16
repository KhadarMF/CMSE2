import hashlib
import hmac
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import NotificationLog
from app.whatsapp_service import (
    whatsapp_config,
    is_whatsapp_configured,
    send_whatsapp_text,
    send_whatsapp_template,
    normalize_whatsapp_number,
    parse_incoming_whatsapp,
)

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')


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
    info = parse_incoming_whatsapp(payload)
    try:
        if info:
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
        db.session.add(log); db.session.commit()
        flash('WhatsApp template test sent. Meta response: ' + json.dumps(response)[:300] if ok else f'WhatsApp failed: {response}', 'success' if ok else 'danger')
        return redirect(url_for('whatsapp.test_send'))
    cfg = whatsapp_config()
    return render_template('whatsapp/test.html', configured=configured, config_message=config_message, cfg=cfg)


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
