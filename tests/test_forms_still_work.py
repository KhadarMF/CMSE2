"""Phase 20D regression guard.

The V49 -> V50 rewrite removed CSRF because turning it on broke every POST.
This file exists so that can never happen silently again: it drives real
forms end to end with CSRF ON and a real token, the way a browser does.
"""
import re

TOKEN_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


def _token(client, url):
    html = client.get(url).get_data(as_text=True)
    match = TOKEN_RE.search(html)
    assert match, f"no CSRF token rendered on {url}"
    return match.group(1)


def _make_user(app, email="admin@example.com", role="Admin"):
    from app import db
    from app.models import User
    from werkzeug.security import generate_password_hash
    u = User(full_name="Admin User", email=email,
             password_hash=generate_password_hash("Correct-Horse-Battery-1"),
             role=role, is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def test_login_works_with_a_real_csrf_token(csrf_app):
    _make_user(csrf_app)
    client = csrf_app.test_client()
    token = _token(client, "/login")
    resp = client.post("/login", data={
        "email": "admin@example.com",
        "password": "Correct-Horse-Battery-1",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    assert "/login" not in resp.headers.get("Location", "")


def test_creating_an_account_works_with_csrf_on(csrf_app):
    """A real business POST, all the way to the database."""
    from app import db
    from app.models import Account

    _make_user(csrf_app)
    client = csrf_app.test_client()
    client.post("/login", data={
        "email": "admin@example.com",
        "password": "Correct-Horse-Battery-1",
        "csrf_token": _token(client, "/login"),
    })

    url = "/accounting/accounts/create"
    resp = client.post(url, data={
        "code": "5999",
        "name": "Phase 20D Test Expense",
        "account_type": "Expense",
        "description": "created through a real form post",
        "csrf_token": _token(client, url),
    }, follow_redirects=True)

    assert resp.status_code == 200
    with csrf_app.app_context():
        assert Account.query.filter_by(code="5999").first() is not None


def test_every_post_form_in_every_template_carries_a_token():
    """Static sweep: one untokenised form is one broken page in production."""
    import pathlib
    form_open = re.compile(r"<form\b[^>]*>", re.IGNORECASE | re.DOTALL)
    is_post = re.compile(r'method\s*=\s*["\']post["\']', re.IGNORECASE)

    missing = []
    for path in sorted(pathlib.Path("app/templates").rglob("*.html")):
        src = path.read_text(encoding="utf-8")
        for match in form_open.finditer(src):
            if not is_post.search(match.group(0)):
                continue
            if "csrf_token" not in src[match.end():match.end() + 300]:
                missing.append(f"{path}: {match.group(0)[:60]}")

    assert not missing, "POST forms without a CSRF token:\n" + "\n".join(missing)


def test_no_route_still_calls_create_all():
    """Alembic owns the schema now; a stray create_all() reintroduces drift.

    Parsed with ast rather than grepped, so mentions inside comments and
    docstrings (there are several, explaining why it was removed) do not
    trip the check - only a real call does.
    """
    import ast
    import pathlib

    offenders = []
    for path in sorted(pathlib.Path("app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "create_all":
                offenders.append(f"{path}:{node.lineno}")

    assert not offenders, "db.create_all() found in: " + ", ".join(offenders)
