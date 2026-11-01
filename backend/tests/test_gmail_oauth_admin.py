"""
Tests for Gmail OAuth admin-connect feature:
- GET /api/admin/google/status (admin-only)
- GET /api/admin/google/connect (admin-only)
- POST /api/admin/google/disconnect (admin-only)
- GET /api/auth/google/callback (public)
- Regression: /api/auth/forgot-password still gracefully 503s
- Non-admin 403 checks
"""
import os
import uuid
import urllib.parse
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": "ADMIN", "password": "Test@123"})
    assert r.status_code == 200, r.text
    return r.json()["token"] if "token" in r.json() else r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def regular_user_headers():
    email = f"TEST_gmail_{uuid.uuid4().hex[:8]}@test.pl"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "test1234", "name": "Test Gmail"})
    assert r.status_code in (200, 201), r.text
    token = r.json().get("token") or r.json().get("access_token")
    if not token:
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "test1234"})
        token = r2.json().get("token") or r2.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


class TestGmailAdminStatus:
    def test_status_returns_configured_true(self, admin_headers):
        r = requests.get(f"{API}/admin/google/status", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["configured"] is True
        assert data["connected"] is False
        assert data["sender"] == "support.zawodowcy@gmail.com"
        assert data["connected_at"] is None

    def test_status_non_admin_403(self, regular_user_headers):
        r = requests.get(f"{API}/admin/google/status", headers=regular_user_headers)
        assert r.status_code == 403

    def test_status_no_auth_401_or_403(self):
        r = requests.get(f"{API}/admin/google/status")
        assert r.status_code in (401, 403)


class TestGmailAdminConnect:
    def test_connect_returns_valid_google_oauth_url(self, admin_headers):
        r = requests.get(f"{API}/admin/google/connect", headers=admin_headers)
        assert r.status_code == 200, r.text
        url = r.json()["url"]
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        assert "client_id" in qs
        assert qs["client_id"][0].endswith(".apps.googleusercontent.com")
        assert qs["redirect_uri"][0].endswith("/api/auth/google/callback")
        assert qs["scope"][0] == "https://www.googleapis.com/auth/gmail.send" or "gmail.send" in qs["scope"][0]
        assert qs["access_type"][0] == "offline"
        assert qs["prompt"][0] == "consent"
        assert "state" in qs and len(qs["state"][0]) > 10

    def test_connect_non_admin_403(self, regular_user_headers):
        r = requests.get(f"{API}/admin/google/connect", headers=regular_user_headers)
        assert r.status_code == 403


class TestGmailAdminDisconnect:
    def test_disconnect_ok_even_if_nothing_connected(self, admin_headers):
        r = requests.post(f"{API}/admin/google/disconnect", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}


class TestGoogleOAuthCallbackPublic:
    def test_error_param_returns_400_html(self):
        r = requests.get(f"{API}/auth/google/callback", params={"error": "access_denied"})
        assert r.status_code == 400
        assert "text/html" in r.headers.get("content-type", "")
        assert "Google zwrócił błąd" in r.text or "błąd" in r.text

    def test_bogus_state_returns_400_html(self):
        r = requests.get(f"{API}/auth/google/callback", params={"code": "fake", "state": "doesnotexist"})
        assert r.status_code == 400
        assert "text/html" in r.headers.get("content-type", "")

    def test_no_params_returns_400_html(self):
        r = requests.get(f"{API}/auth/google/callback")
        assert r.status_code == 400
        assert "text/html" in r.headers.get("content-type", "")


class TestForgotPasswordRegression:
    def test_forgot_password_still_graceful_503(self):
        email = f"TEST_fp_{uuid.uuid4().hex[:8]}@test.pl"
        requests.post(f"{API}/auth/register", json={"email": email, "password": "test1234", "name": "Test FP"})
        r = requests.post(f"{API}/auth/forgot-password", json={"email": email})
        # Pre-existing expected behavior: Gmail not connected + no EMERGENT_EMAIL_KEY -> 503
        if r.status_code == 503:
            assert r.json()["detail"] == "Wysyłka e-maili jest chwilowo niedostępna. Spróbuj ponownie za chwilę."
        else:
            # If EMERGENT_EMAIL_KEY happens to be configured, should be 200
            assert r.status_code == 200, r.text
