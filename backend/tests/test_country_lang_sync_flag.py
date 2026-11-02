"""
Backend regression tests for the country/language sync-on-login bug fix.
Covers the PATCH /api/account/country and /api/account/language endpoints that
the frontend's one-time PENDING_ACCOUNT_SYNC_KEY flag (auth.tsx login()) calls
right after a successful login to apply a freshly-picked pre-login country/language.

These tests exercise the backend contract only (the flag itself is frontend-local
AsyncStorage logic tested via Playwright separately).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@reset.app"
ADMIN_PASSWORD = "Test@123"


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def admin_token(api_client):
    r = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class TestAccountCountryLanguagePatch:
    """Scenario A/B backend contract: PATCH country/language persists and GET /auth/me reflects it."""

    def test_me_returns_country_and_ui_language(self, api_client, admin_token):
        r = api_client.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "country" in data and "ui_language" in data

    def test_patch_country_then_verify_persistence(self, api_client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        original = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers).json()
        original_country = original["country"]
        new_country = "DE" if original_country != "DE" else "NL"

        patch_resp = api_client.patch(f"{BASE_URL}/api/account/country", json={"country": new_country}, headers=headers)
        assert patch_resp.status_code == 200, patch_resp.text
        assert patch_resp.json()["country"] == new_country

        get_resp = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert get_resp.json()["country"] == new_country

        # restore
        api_client.patch(f"{BASE_URL}/api/account/country", json={"country": original_country}, headers=headers)

    def test_patch_language_then_verify_persistence(self, api_client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        original = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers).json()
        original_lang = original["ui_language"]
        new_lang = "pl" if original_lang != "pl" else "en"

        patch_resp = api_client.patch(f"{BASE_URL}/api/account/language", json={"language": new_lang}, headers=headers)
        assert patch_resp.status_code == 200, patch_resp.text
        assert patch_resp.json()["ui_language"] == new_lang

        get_resp = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert get_resp.json()["ui_language"] == new_lang

        # restore
        api_client.patch(f"{BASE_URL}/api/account/language", json={"language": original_lang}, headers=headers)

    def test_patch_country_invalid_rejected(self, api_client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = api_client.patch(f"{BASE_URL}/api/account/country", json={"country": "ZZZZ"}, headers=headers)
        assert r.status_code == 400

    def test_patch_language_invalid_rejected(self, api_client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = api_client.patch(f"{BASE_URL}/api/account/language", json={"language": "zz"}, headers=headers)
        assert r.status_code == 400

    def test_login_does_not_auto_reset_country_language(self, api_client, admin_token):
        """Backend-only sanity: a plain login call must not itself mutate country/ui_language
        (the sync must be driven by the frontend flag, not by backend login side-effects)."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        before = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers).json()
        r2 = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r2.status_code == 200
        after_user = r2.json()["user"]
        assert after_user["country"] == before["country"]
        assert after_user["ui_language"] == before["ui_language"]
