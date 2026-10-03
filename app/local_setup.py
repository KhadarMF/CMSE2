"""Local development environment setup shared by entry points."""
import os
from pathlib import Path
import re
import secrets

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _set_env_value(content, key, value):
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    replacement = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(replacement, content, count=1)
    return content.rstrip() + f"\n{replacement}\n"


def prepare_local_environment():
    """Create/repair only the local, git-ignored environment file."""
    process_env = (os.environ.get("FLASK_ENV") or "").strip().lower()
    if process_env == "production" or os.environ.get("RENDER"):
        return

    env_path = PROJECT_ROOT / ".env"
    env_example_path = PROJECT_ROOT / ".env.example"
    created = not env_path.exists()
    content = (
        env_example_path.read_text(encoding="utf-8")
        if created and env_example_path.exists()
        else env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    )

    match = re.search(r"^SECRET_KEY=(.*)$", content, re.MULTILINE)
    current_secret = match.group(1).strip() if match else ""
    unsafe = {
        "", "secret", "dev", "development", "change-this-secret-key",
        "change-this-to-a-long-random-secret-key",
    }
    changed = created
    if current_secret.lower() in unsafe or len(current_secret) < 32:
        content = _set_env_value(content, "SECRET_KEY", secrets.token_hex(32))
        changed = True
    # `run.py` is the local launcher. Keep local HTTP login cookies usable even
    # when `.env` was previously copied verbatim from the production example.
    if not re.search(r"^FLASK_ENV=development$", content, re.MULTILINE):
        content = _set_env_value(content, "FLASK_ENV", "development")
        changed = True
    if not re.search(r"^SESSION_COOKIE_SECURE=0$", content, re.MULTILINE):
        content = _set_env_value(content, "SESSION_COOKIE_SECURE", "0")
        changed = True

    if changed:
        env_path.write_text(content, encoding="utf-8")
        print("LOCAL SETUP: .env is ready with a private generated SECRET_KEY.")

