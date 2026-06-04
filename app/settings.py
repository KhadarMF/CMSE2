from flask import current_app
from app.models import SystemSetting

def get_setting(key, default=""):
    item = SystemSetting.query.filter_by(setting_key=key).first()
    if item and item.setting_value is not None:
        return item.setting_value
    return default

def set_setting(key, value):
    item = SystemSetting.query.filter_by(setting_key=key).first()
    if not item:
        item = SystemSetting(setting_key=key)
    item.setting_value = value
    return item

def get_email_config():
    def fallback(key, default=""):
        val = get_setting(key, "")
        return val if val != "" else current_app.config.get(key, default)
    return {
        "MAIL_SERVER": fallback("MAIL_SERVER", ""),
        "MAIL_PORT": int(fallback("MAIL_PORT", "587") or 587),
        "MAIL_USE_TLS": str(fallback("MAIL_USE_TLS", "true")).lower() == "true",
        "MAIL_USERNAME": fallback("MAIL_USERNAME", ""),
        "MAIL_PASSWORD": fallback("MAIL_PASSWORD", ""),
        "MAIL_DEFAULT_SENDER": fallback("MAIL_DEFAULT_SENDER", fallback("MAIL_USERNAME", "")),
    }
