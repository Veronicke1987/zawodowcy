"""
Iteration 39 backend tests:
1) Registration with country param (from country-select screen) persists country, verified via GET /api/auth/me
2) POST /api/careers/custom creates a career entry visible in GET /api/recommendations "now" list,
   with country field matching user's country, and does NOT create a roadmap/path automatically.
3) Regression smoke: login, account/country PATCH, daily-plan premium gate, weekly plan free (ad-gated/no 403).
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def register_user(session, country=None):
    uid = uuid.uuid4().hex[:8]
    email = f"TEST_iter39_{uid}@test.pl"
    payload = {"name": "Test Iter39", "email": email, "password": "test123"}
    if country:
        payload["country"] = country
    r = session.post(f"{API}/auth/register", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert "access_token" in data
    session.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    return data, email


class TestCountrySelectRegistration:
    def test_register_with_country_de_persists(self, session):
        data, email = register_user(session, country="DE")
        assert data["user"]["country"] == "DE"
        me = session.get(f"{API}/auth/me")
        assert me.status_code == 200
        assert me.json()["country"] == "DE"

    def test_register_with_invalid_country_falls_back_to_pl(self, session):
        data, email = register_user(session, country="ZZ")
        assert data["user"]["country"] == "PL"

    def test_register_without_country_defaults_pl(self, session):
        data, email = register_user(session, country=None)
        assert data["user"]["country"] == "PL"


class TestCustomCareerFlow:
    def test_custom_career_creates_entry_visible_in_recommendations_now(self, session):
        data, email = register_user(session, country="PL")
        title = "Grafik komputerowy"
        r = session.post(f"{API}/careers/custom", json={"title": title, "qualifications": "brak"})
        assert r.status_code == 200, r.text
        career_id = r.json()["career_id"]
        assert career_id

        rec = session.get(f"{API}/recommendations")
        assert rec.status_code == 200
        rec_data = rec.json()
        now_list = rec_data.get("now", [])
        match = next((c for c in now_list if c["id"] == career_id), None)
        assert match is not None, "Custom career not found in recommendations 'now' list"
        assert match["title"] == title
        assert match["country"] == "PL"

    def test_custom_career_does_not_create_roadmap_automatically(self, session):
        data, email = register_user(session, country="PL")
        title = "Elektryk przemysłowy"
        r = session.post(f"{API}/careers/custom", json={"title": title, "qualifications": ""})
        assert r.status_code == 200
        career_id = r.json()["career_id"]

        road = session.get(f"{API}/roadmap", params={"path_id": career_id})
        # Should not have an active roadmap for this career yet (no auto-build)
        assert road.status_code in (200, 404)
        if road.status_code == 200:
            body = road.json()
            # if endpoint returns empty/none doc when no path exists
            assert body is None or body.get("career", {}).get("id") != career_id

    def test_custom_career_empty_title_rejected(self, session):
        data, email = register_user(session, country="PL")
        r = session.post(f"{API}/careers/custom", json={"title": "   ", "qualifications": ""})
        assert r.status_code == 400


class TestRegressionSmoke:
    def test_login_existing_user(self, session):
        r = session.post(f"{API}/auth/login", json={"email": "ania_t1@test.pl", "password": "test123"})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["email"] == "ania_t1@test.pl"

    def test_account_country_patch(self, session):
        data, email = register_user(session, country="PL")
        r = session.patch(f"{API}/account/country", json={"country": "DE"})
        assert r.status_code == 200
        assert r.json()["country"] == "DE"
        me = session.get(f"{API}/auth/me")
        assert me.json()["country"] == "DE"

    def test_daily_plan_requires_premium_for_free_user(self, session):
        data, email = register_user(session, country="PL")
        r = session.post(f"{API}/roadmap/daily-plan/settings", json={"time_mode": "daily", "time_value": 2, "free_days": []})
        assert r.status_code == 403

    def test_weekly_plan_not_403_for_free_user(self, session):
        data, email = register_user(session, country="PL")
        r = session.post(f"{API}/roadmap/study-plan")
        # free users allowed (ad-gated), so should not be 403; 400 acceptable since no path exists yet
        assert r.status_code != 403
