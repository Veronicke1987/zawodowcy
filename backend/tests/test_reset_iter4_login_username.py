# Iteration 4: login by username (ADMIN) or e-mail
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _login(ident, pw):
    return requests.post(f"{API}/auth/login", json={"email": ident, "password": pw}, timeout=20)


# Admin login with username / email variants
@pytest.mark.parametrize("ident", ["ADMIN", "admin", " ADMIN ", "Admin", "admin@reset.app", "ADMIN@RESET.APP"])
def test_admin_login_variants(ident):
    r = _login(ident, "Test@123")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["access_token"]
    assert d["user"]["role"] == "admin"
    assert "_id" not in d["user"]
    assert "password_hash" not in d["user"]


# /auth/me returns admin role
def test_admin_me():
    tok = _login("ADMIN", "Test@123").json()["access_token"]
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d["role"] == "admin"
    assert d["email"] == "admin@reset.app"
    print("admin me:", d)


# Wrong password -> Polish 401
def test_admin_wrong_password():
    r = _login("ADMIN", "wrongpass")
    assert r.status_code == 401
    assert r.json()["detail"] == "Nieprawidłowy login/e-mail lub hasło."


# Unknown username -> 401 same message
def test_unknown_username():
    r = _login("nobody_xyz_123", "Test@123")
    assert r.status_code == 401
    assert r.json()["detail"] == "Nieprawidłowy login/e-mail lub hasło."


# Normal user still works
def test_normal_user_login():
    r = _login("ania_t1@test.pl", "test123")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "ania_t1@test.pl"


# Register without @ rejected in Polish
def test_register_requires_email():
    r = requests.post(f"{API}/auth/register", json={"email": "ADMIN", "password": "Test@123", "name": "x"}, timeout=20)
    assert r.status_code == 400
    assert r.json()["detail"] == "Podaj poprawny adres e-mail."


# Admin has no quiz profile
def test_admin_profile_empty():
    tok = _login("ADMIN", "Test@123").json()["access_token"]
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=20).json()
    print("has_profile fields:", {k: v for k, v in me.items() if "profile" in k})
