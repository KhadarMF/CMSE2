"""Meta WhatsApp Cloud API helpers for Cadceed-Maal ERP.

Phase 16D adds outgoing WhatsApp notifications and a webhook endpoint.
Secrets must be configured in Render Environment Variables, not committed to Git.
"""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

GRAPH_API_VERSION = os.environ.get("WHATSAPP_GRAPH_API_VERSION", "v25.0")
GRAPH_API_BASE = os.environ.get("WHATSAPP_GRAPH_API_BASE", "https://graph.facebook.com")


def whatsapp_config() -> Dict[str, str]:
    return {
        "access_token": os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip(),
        "phone_number_id": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "1091324590741999").strip(),
        "business_account_id": os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID", "4334785340171192").strip(),
        "verify_token": os.environ.get("WHATSAPP_VERIFY_TOKEN", "cmse_whatsapp_verify_2026").strip(),
        "public_base_url": os.environ.get("PUBLIC_BASE_URL", "https://cmse2.onrender.com").strip().rstrip("/"),
    }


def is_whatsapp_configured() -> Tuple[bool, str]:
    cfg = whatsapp_config()
    missing = [name for name in ("access_token", "phone_number_id") if not cfg.get(name)]
    if missing:
        return False, "Missing WhatsApp environment variables: " + ", ".join(missing)
    return True, "Configured"


def normalize_whatsapp_number(raw: str) -> str:
    """Normalize phone number to international digits without '+'.

    Examples:
    +252 63 8888044 -> 252638888044
    0638888044      -> 252638888044
    638888044       -> 252638888044
    +1 555 123 4567 -> 15551234567  (non-Somali numbers preserved as-is)
    """
    digits = re.sub(r"\D+", "", raw or "")
    if not digits:
        return ""
    # Strip leading 00 international prefix
    if digits.startswith("00"):
        digits = digits[2:]
    # Already a full international number (10+ digits starting with country code)
    if len(digits) >= 10 and not digits.startswith("0") and not digits.startswith("6"):
        return digits
    # Somali local format: leading 0 + 9 digits
    if digits.startswith("0") and len(digits) >= 9:
        digits = "252" + digits[1:]
    # Somali format: 63/61/62/65 + 7 digits (no country code)
    elif len(digits) == 9 and digits[0] in ("6",):
        digits = "252" + digits
    return digits


def _post_json(url: str, payload: Dict[str, Any], token: str, timeout: int = 30) -> Tuple[bool, Dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return True, json.loads(body or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            return False, json.loads(body or "{}")
        except Exception:
            return False, {"error": {"message": body or str(exc), "code": exc.code}}
    except Exception as exc:
        return False, {"error": {"message": str(exc)}}


def send_whatsapp_text(to_phone: str, message: str, preview_url: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """Send a simple WhatsApp text message via Meta Cloud API."""
    cfg = whatsapp_config()
    ok, msg = is_whatsapp_configured()
    if not ok:
        return False, {"error": {"message": msg}}

    to = normalize_whatsapp_number(to_phone)
    if not to:
        return False, {"error": {"message": "Recipient phone number is required."}}
    if not (message or "").strip():
        return False, {"error": {"message": "Message is empty."}}

    url = f"{GRAPH_API_BASE}/{GRAPH_API_VERSION}/{cfg['phone_number_id']}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": bool(preview_url), "body": message[:4096]},
    }
    return _post_json(url, payload, cfg["access_token"])


def send_whatsapp_template(
    to_phone: str,
    template_name: Optional[str] = None,
    language_code: Optional[str] = None,
    components: Optional[list] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Send an approved WhatsApp template message via Meta Cloud API.

    Default template is controlled by Render env vars:
    WHATSAPP_TEMPLATE_NAME=cmse_test
    WHATSAPP_TEMPLATE_LANGUAGE=en

    Optional ``components`` supports templates with body variables and buttons.
    Example: [{"type": "body", "parameters": [{"type": "text", "text": "Customer"}]}]
    """
    cfg = whatsapp_config()
    ok, msg = is_whatsapp_configured()
    if not ok:
        return False, {"error": {"message": msg}}

    to = normalize_whatsapp_number(to_phone)
    if not to:
        return False, {"error": {"message": "Recipient phone number is required."}}

    template_name = (template_name or os.environ.get("WHATSAPP_TEMPLATE_NAME") or "cmse_test").strip()
    language_code = (language_code or os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE") or "en").strip()

    url = f"{GRAPH_API_BASE}/{GRAPH_API_VERSION}/{cfg['phone_number_id']}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        payload["template"]["components"] = components
    return _post_json(url, payload, cfg["access_token"])


def format_money(amount: float) -> str:
    try:
        return f"${float(amount or 0):,.2f}"
    except Exception:
        return "$0.00"


def build_quotation_message(quotation, base_url: Optional[str] = None) -> str:
    """Build a customer-friendly quotation summary for WhatsApp."""
    cfg = whatsapp_config()
    base = (base_url or cfg.get("public_base_url") or "").rstrip("/")
    quotation_link = f"{base}/sales/quotations/{quotation.id}" if base else ""

    lines = [
        "Assalaamu Calaykum,",
        f"Cadceed-Maal Solar Energy waxay kuu diyaarisay quotation: {quotation.ref_no}.",
        "",
        f"Customer: {quotation.customer_name}",
        f"Project Type: {quotation.project_type or '-'}",
        f"Capacity: {quotation.capacity or '-'}",
        f"Total Amount: {format_money(quotation.total_amount)}",
        f"Validity: {quotation.validity_days or 15} days",
    ]
    if quotation_link:
        lines.extend(["", f"View quotation: {quotation_link}"])
    lines.extend([
        "",
        "Mahadsanid,",
        "Cadceed-Maal Solar Energy",
    ])
    return "\n".join(lines)



def extract_whatsapp_message_id(response: Dict[str, Any]) -> str:
    """Return Meta wamid from a send-message API response."""
    try:
        return ((response.get("messages") or [{}])[0] or {}).get("id") or ""
    except Exception:
        return ""


def extract_whatsapp_statuses(payload: Dict[str, Any]) -> list:
    """Extract WhatsApp delivery status updates from Meta webhook payload."""
    results = []
    try:
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                for st in value.get("statuses") or []:
                    conversation = st.get("conversation") or {}
                    pricing = st.get("pricing") or {}
                    error_items = st.get("errors") or []
                    error_text = ""
                    if error_items:
                        first = error_items[0] or {}
                        error_text = first.get("message") or first.get("title") or json.dumps(first)
                    results.append({
                        "message_id": st.get("id") or "",
                        "recipient_id": st.get("recipient_id") or "",
                        "status": st.get("status") or "",
                        "timestamp": st.get("timestamp") or "",
                        "conversation_id": conversation.get("id") or "",
                        "pricing_category": pricing.get("category") or "",
                        "error_message": error_text,
                    })
    except Exception:
        return []
    return results


def parse_incoming_whatsapp(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract useful fields from WhatsApp webhook payload for logging."""
    try:
        entry = (payload.get("entry") or [{}])[0]
        change = (entry.get("changes") or [{}])[0]
        value = change.get("value") or {}
        messages = value.get("messages") or []
        contacts = value.get("contacts") or []
        msg = messages[0] if messages else {}
        contact = contacts[0] if contacts else {}
        text = ((msg.get("text") or {}).get("body")) or ""
        return {
            "from": msg.get("from") or (contact.get("wa_id") if contact else ""),
            "name": ((contact.get("profile") or {}).get("name")) if contact else "",
            "message_id": msg.get("id") or "",
            "type": msg.get("type") or "",
            "text": text,
            "timestamp": msg.get("timestamp") or "",
        }
    except Exception:
        return {}
