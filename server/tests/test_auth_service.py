from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
import time

import pytest

from app.auth_service import AuthError, AuthService


def make_auth_service(tmp_path: Path) -> AuthService:
    return AuthService(
        db_path=tmp_path / "chatgrid.db",
        token_hash_secret="test-secret",
        password_min_length=8,
        password_max_length=32,
        username_min_length=2,
        username_max_length=32,
    )


def sign_external_assertion(payload: dict[str, object], secret: str) -> str:
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(
        secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{encoded_payload}.{encoded_signature}"


def test_register_and_resume_session(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        session = service.register("User_One", "password99", email="a@example.com")
        assert session.user.username == "user_one"
        resumed = service.resume(session.token)
        assert resumed.user.id == session.user.id
        assert resumed.user.role == "user"
    finally:
        service.close()


def test_login_external_assertion_creates_user_and_session(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        now = int(time.time())
        assertion = sign_external_assertion(
            {
                "aud": "chatgrid",
                "provider": "blind.software",
                "sub": "member-123",
                "username": "Blind Member",
                "email": "member@example.com",
                "displayName": "Blind Member",
                "role": "editor",
                "nonce": "nonce-1",
                "iat": now,
                "exp": now + 120,
            },
            "external-secret",
        )

        session = service.login_external_assertion(
            assertion, signing_secret="external-secret"
        )

        assert session.user.username == "blind-member"
        assert session.user.email == "member@example.com"
        assert session.user.role == "editor"
        resumed = service.resume(session.token)
        assert resumed.user.id == session.user.id
    finally:
        service.close()


def test_login_external_assertion_rejects_nonce_replay(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        now = int(time.time())
        assertion = sign_external_assertion(
            {
                "aud": "chatgrid",
                "provider": "blind.software",
                "sub": "member-123",
                "username": "Blind Member",
                "nonce": "nonce-1",
                "iat": now,
                "exp": now + 120,
            },
            "external-secret",
        )

        service.login_external_assertion(assertion, signing_secret="external-secret")
        with pytest.raises(AuthError, match="already used"):
            service.login_external_assertion(assertion, signing_secret="external-secret")
    finally:
        service.close()


def test_login_rejects_invalid_password(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        service.register("alpha", "password99")
        with pytest.raises(AuthError):
            service.login("alpha", "wrong-pass")
    finally:
        service.close()


def test_bootstrap_admin_once(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        admin = service.bootstrap_admin("root-admin", "password99", email=None)
        assert admin.role == "admin"
        with pytest.raises(AuthError):
            service.bootstrap_admin("another-admin", "password99")
    finally:
        service.close()


def test_login_missing_user_runs_dummy_verify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = make_auth_service(tmp_path)
    try:
        calls: list[tuple[str, str]] = []

        def fake_verify(password: str, stored: str) -> bool:
            calls.append((password, stored))
            return False

        monkeypatch.setattr(service, "_verify_password", fake_verify)
        with pytest.raises(AuthError):
            service.login("missing_user", "password99")
        assert len(calls) == 1
        assert calls[0][0] == "password99"
    finally:
        service.close()


def test_delete_role_rejects_admin_and_user(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        with pytest.raises(AuthError):
            service.delete_role("admin", "editor")
        with pytest.raises(AuthError):
            service.delete_role("user", "editor")
    finally:
        service.close()


def test_update_role_permissions_rejects_admin(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        with pytest.raises(AuthError):
            service.update_role_permissions("admin", ["chat.send"])
    finally:
        service.close()


def test_delete_user_removes_account(tmp_path: Path) -> None:
    service = make_auth_service(tmp_path)
    try:
        service.register("alpha", "password99")
        deleted = service.delete_user("alpha")
        assert deleted == "alpha"
        with pytest.raises(AuthError):
            service.login("alpha", "password99")
    finally:
        service.close()
