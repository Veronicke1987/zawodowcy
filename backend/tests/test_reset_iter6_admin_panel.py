# Iteration 6 - admin panel: stats, user search, premium toggle, grant by email (granted/pending), auto-apply on register, 403 for non-admin
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
ANIA = "ania_t1@test.pl"


def login(ident, pw):
    r = requests.post(f"{API}/auth/login", json={"email": ident, "password": pw})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s, r.json()["user"]


@pytest.fixture(scope="module")
def admin():
    s, u = login("ADMIN", "Test@123")
    assert u["role"] == "admin"
    return s


@pytest.fixture(scope="module")
def ania():
    s, u = login(ANIA, "test123")
    return s, u


@pytest.fixture(scope="module")
def ania_initial(admin):
    users = admin.get(f"{API}/admin/users", params={"q": ANIA}).json()["users"]
    row = [x for x in users if x["email"] == ANIA][0]
    yield row
    # restore ania premium to original state
    admin.post(f"{API}/admin/users/{row['id']}/premium", json={"active": row["is_premium"]})


# Admin role via ADMIN_EMAILS env (code-level check, owner email is never registered)
def test_admin_emails_env_contains_owner():
    import sys
    sys.path.insert(0, "/app/backend")
    from dotenv import dotenv_values
    v = dotenv_values("/app/backend/.env").get("ADMIN_EMAILS", "")
    assert "weronisia1987s@gmail.com" in [e.strip().lower() for e in v.split(",")]


# Non-admin forbidden
class TestForbidden:
    @pytest.mark.parametrize("method,path,body", [
        ("get", "/admin/stats", None), ("get", "/admin/users", None),
        ("post", "/admin/premium/grant", {"email": "x@y.pl"}),
        ("post", "/admin/users/000000000000000000000000/premium", {"active": True}),
        ("delete", "/admin/premium/grant/x@y.pl", None),
    ])
    def test_non_admin_403(self, ania, method, path, body):
        s, _ = ania
        r = getattr(s, method)(f"{API}{path}", json=body) if body else getattr(s, method)(f"{API}{path}")
        assert r.status_code == 403
        assert "Brak uprawnień" in r.json()["detail"]

    def test_unauth_401(self):
        assert requests.get(f"{API}/admin/stats").status_code in (401, 403)


# Admin stats + users
class TestAdminRead:
    def test_stats(self, admin):
        d = admin.get(f"{API}/admin/stats").json()
        for k in ("users", "premium", "gifted", "pending_grants", "paths"):
            assert isinstance(d[k], int)
        assert d["users"] >= 2

    def test_users_search(self, admin):
        d = admin.get(f"{API}/admin/users", params={"q": "ania_t1"}).json()
        assert any(u["email"] == ANIA for u in d["users"])
        assert all("password_hash" not in u and "_id" not in u for u in d["users"])
        assert isinstance(d["pending"], list)

    def test_users_search_regex_safe(self, admin):
        r = admin.get(f"{API}/admin/users", params={"q": "(.*"})
        assert r.status_code == 200


# Premium toggle per user
class TestToggle:
    def test_toggle_on_off(self, admin, ania, ania_initial):
        s, _ = ania
        uid = ania_initial["id"]
        r = admin.post(f"{API}/admin/users/{uid}/premium", json={"active": True})
        assert r.status_code == 200 and r.json()["is_premium"] is True
        assert s.get(f"{API}/auth/me").json()["is_premium"] is True
        row = [x for x in admin.get(f"{API}/admin/users", params={"q": ANIA}).json()["users"] if x["email"] == ANIA][0]
        assert row["premium_plan"] == "gift"
        r = admin.post(f"{API}/admin/users/{uid}/premium", json={"active": False})
        assert r.json()["is_premium"] is False
        assert s.get(f"{API}/auth/me").json()["is_premium"] is False

    def test_toggle_invalid_id_404(self, admin):
        assert admin.post(f"{API}/admin/users/bad/premium", json={"active": True}).status_code == 404
        assert admin.post(f"{API}/admin/users/000000000000000000000000/premium", json={"active": True}).status_code == 404


# Grant by email
class TestGrant:
    def test_grant_existing(self, admin, ania, ania_initial):
        r = admin.post(f"{API}/admin/premium/grant", json={"email": "  ANIA_T1@test.pl "})
        assert r.status_code == 200 and r.json()["status"] == "granted"
        assert "Nadano Premium" in r.json()["message"]
        assert ania[0].get(f"{API}/auth/me").json()["is_premium"] is True

    def test_grant_invalid_email(self, admin):
        assert admin.post(f"{API}/admin/premium/grant", json={"email": "abcdef"}).status_code == 400

    def test_grant_pending_then_register(self, admin):
        email = f"test_gift_{uuid.uuid4().hex[:8]}@test.pl"
        r = admin.post(f"{API}/admin/premium/grant", json={"email": email.upper()})
        assert r.json()["status"] == "pending" and "automatycznie" in r.json()["message"]
        pend = admin.get(f"{API}/admin/users").json()["pending"]
        assert email in [p["email"] for p in pend]
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "TEST_Gift"})
        assert r.status_code == 201
        assert r.json()["user"]["is_premium"] is True and r.json()["user"]["role"] == "user"
        pend = admin.get(f"{API}/admin/users").json()["pending"]
        assert email not in [p["email"] for p in pend]

    def test_grant_pending_remove(self, admin):
        email = f"test_rm_{uuid.uuid4().hex[:8]}@test.pl"
        admin.post(f"{API}/admin/premium/grant", json={"email": email})
        r = admin.delete(f"{API}/admin/premium/grant/{email}")
        assert r.status_code == 200
        assert email not in [p["email"] for p in admin.get(f"{API}/admin/users").json()["pending"]]
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "test123"})
        assert r.json()["user"]["is_premium"] is False
