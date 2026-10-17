"""Regression tests for document downloads and missing Render uploads."""
from pathlib import Path


def _login(client, user):
    from flask import g

    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    g.pop("_login_user", None)


def _document_with_version(app, *, stored_file_name="version-one.pdf"):
    from app import db
    from app.models import Document, DocumentVersion, Project, User

    user = User(
        full_name="Document Admin",
        email="document-admin@example.invalid",
        password_hash="unused",
        role="Admin",
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    project = Project(
        project_name="Storage Test Project",
        customer_name="Storage Customer",
        location="Test Site",
        project_type="Solar",
        created_by_id=user.id,
    )
    db.session.add(project)
    db.session.flush()
    document = Document(
        project_id=project.id,
        document_title="Site evidence",
        document_type="Technical Design",
        uploaded_by_id=user.id,
        file_name="evidence.pdf",
        stored_file_name=stored_file_name,
        approval_status="Draft",
    )
    db.session.add(document)
    db.session.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_name="evidence.pdf",
        stored_file_name=stored_file_name,
        uploaded_by_id=user.id,
        remarks="Initial upload",
    )
    db.session.add(version)
    db.session.commit()
    return user, document, version


def test_document_version_download_returns_existing_file(app, client):
    user, document, version = _document_with_version(app)
    upload_path = Path(app.config["UPLOAD_FOLDER"])
    upload_path.mkdir(parents=True, exist_ok=True)
    (upload_path / version.stored_file_name).write_bytes(b"stored evidence")
    _login(client, user)

    response = client.get(f"/documents/version/{version.id}/download")

    assert response.status_code == 200
    assert response.data == b"stored evidence"
    assert "attachment" in response.headers["Content-Disposition"]
    assert "evidence.pdf" in response.headers["Content-Disposition"]


def test_missing_document_version_redirects_with_recovery_action(app, client):
    user, document, version = _document_with_version(app, stored_file_name="lost-after-deploy.pdf")
    _login(client, user)

    response = client.get(
        f"/documents/version/{version.id}/download",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert response.request.path == f"/documents/{document.id}"
    assert b"uploaded file is missing from server storage" in response.data
    assert b"File missing" in response.data
    assert b"Upload replacement" in response.data

