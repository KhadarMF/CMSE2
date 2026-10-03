from werkzeug.security import check_password_hash, generate_password_hash


def _login(client, user):
    from flask import g

    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    g.pop("_login_user", None)


def test_admin_password_change_form_avoids_browser_account_autofill(app, client):
    from app import db
    from app.models import User

    admin = User(
        full_name="Password Admin",
        email="password-admin@example.invalid",
        password_hash=generate_password_hash("Correct-Horse-Battery-1"),
        role="Admin",
        is_active=True,
    )
    target = User(
        full_name="Target User",
        email="target-user@example.invalid",
        password_hash=generate_password_hash("old-password"),
        role="Sales Officer",
        is_active=True,
    )
    db.session.add_all([admin, target])
    db.session.commit()

    _login(client, admin)
    response = client.get(f"/users/{target.id}/change-password")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="new_user_password"' in html
    assert 'name="confirm_user_password"' in html
    assert 'autocomplete="new-password"' in html
    assert 'data-lpignore="true"' in html

    changed = client.post(
        f"/users/{target.id}/change-password",
        data={
            "new_user_password": "New-Correct-Horse-1",
            "confirm_user_password": "New-Correct-Horse-1",
        },
        follow_redirects=True,
    )
    assert changed.status_code == 200
    db.session.refresh(target)
    assert check_password_hash(target.password_hash, "New-Correct-Horse-1")

