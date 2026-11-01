"""Tests for premium subscribe/cancel flow, optional cancellation reason,
admin cancellations listing, and admin stats counter."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def test_user(session):
    email = f"TEST_cancel_{int(time.time())}_{uuid.uuid4().hex[:8]}@test.pl"
    password = "testpass123"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    token = r.json().get("token") or r.json().get("access_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return {"email": email, "password": password}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": "ADMIN", "password": "Test@123"})
    assert r.status_code == 200, r.text
    token = r.json().get("token") or r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


class TestPremiumCancelOptionalReason:
    def test_scenario_a_no_reason(self, session, test_user):
        r = session.post(f"{API}/premium/subscribe", json={"plan": "monthly"})
        assert r.status_code == 200
        r2 = session.post(f"{API}/premium/cancel", json={})
        assert r2.status_code == 200, r2.text
        assert r2.json().get("ok") is True
        # verify premium now inactive
        info = session.get(f"{API}/premium")
        assert info.status_code == 200
        assert info.json()["is_premium"] is False

    def test_scenario_b_predefined_reason(self, session, test_user):
        r = session.post(f"{API}/premium/subscribe", json={"plan": "yearly"})
        assert r.status_code == 200
        r2 = session.post(f"{API}/premium/cancel", json={"reason": "too_expensive"})
        assert r2.status_code == 200, r2.text
        assert r2.json().get("ok") is True
        info = session.get(f"{API}/premium")
        assert info.json()["is_premium"] is False

    def test_scenario_c_other_with_detail(self, session, test_user):
        r = session.post(f"{API}/premium/subscribe", json={"plan": "monthly"})
        assert r.status_code == 200
        r2 = session.post(f"{API}/premium/cancel", json={"reason": "other", "detail": "TEST_detail_text"})
        assert r2.status_code == 200, r2.text
        assert r2.json().get("ok") is True
        info = session.get(f"{API}/premium")
        assert info.json()["is_premium"] is False

    def test_admin_cancellations_list_grouped_by_reason(self, test_user):
        # Uses its own admin login (not the module-scoped admin_session fixture) so this
        # assertion runs in the SAME worker/scope as the scenario tests above and can see
        # this test_user's cancellations (xdist --dist loadscope pins fixtures per class).
        admin = requests.Session()
        admin.headers.update({"Content-Type": "application/json"})
        login = admin.post(f"{API}/auth/login", json={"email": "ADMIN", "password": "Test@123"})
        assert login.status_code == 200, login.text
        token = login.json().get("token") or login.json().get("access_token")
        admin.headers.update({"Authorization": f"Bearer {token}"})

        r = admin.get(f"{API}/admin/cancellations")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total" in data and "by_reason" in data and "recent" in data
        assert isinstance(data["recent"], list)
        docs = data["recent"]
        emails = [(d.get("email") or "").lower() for d in docs]
        assert test_user["email"].lower() in emails
        reasons_for_user = [d["reason"] for d in docs if (d.get("email") or "").lower() == test_user["email"].lower()]
        assert "not_specified" in reasons_for_user
        assert "too_expensive" in reasons_for_user
        assert "other" in reasons_for_user
        other_doc = [d for d in docs if (d.get("email") or "").lower() == test_user["email"].lower() and d["reason"] == "other"][0]
        assert other_doc.get("detail") == "TEST_detail_text"
        assert data["by_reason"].get("not_specified", 0) >= 1
        assert data["by_reason"].get("too_expensive", 0) >= 1
        assert data["by_reason"].get("other", 0) >= 1
        for d in docs:
            assert "_id" not in d


class TestAdminCancellationsVisibility:
    def test_admin_stats_cancellations_counter(self, admin_session):
        r = admin_session.get(f"{API}/admin/stats")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "cancellations" in data
        assert isinstance(data["cancellations"], int)
        assert data["cancellations"] >= 3

    def test_non_admin_cannot_access_cancellations(self, session):
        r = session.get(f"{API}/admin/cancellations")
        assert r.status_code in (401, 403)
