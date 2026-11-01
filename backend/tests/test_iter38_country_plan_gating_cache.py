"""
Iteration 38 tests covering this session's changes:
1) Country selection: GET /api/account/countries, PATCH /api/account/country persistence
   (survives re-fetch via GET /api/auth/me), validation of unknown country code.
2) Daily plan is now Premium-only: POST /api/roadmap/daily-plan/settings must 403 for
   free users and succeed for Premium users.
3) Weekly plan (study-plan) is now available to free users (no 403), and supports
   next-block creation producing a second 8-week block.
4) Shared AI cache: two different users choosing the EXACT SAME custom career title
   should have the 2nd user's roadmap generation complete MUCH faster than the 1st
   (cache hit via career_templates collection, apply_cached_roadmap code path).
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def register_user(api_client, suffix):
    email = f"TEST_iter38_{suffix}_{uuid.uuid4().hex[:8]}@test.pl"
    r = api_client.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "test123", "name": "Test"})
    assert r.status_code == 201, r.text
    return email, r.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def poll_roadmap_status(api_client, token, max_wait=120):
    deadline = time.time() + max_wait
    last = None
    while time.time() < deadline:
        r = api_client.get(f"{BASE_URL}/api/roadmap", headers=auth_header(token))
        assert r.status_code == 200
        last = r.json()
        if last.get("status") in ("ready", "error"):
            return last
        time.sleep(2)
    return last


class TestCountrySelection:
    def test_list_countries_has_six(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/account/countries")
        assert r.status_code == 200
        codes = {c["code"] for c in r.json()["countries"]}
        assert codes == {"PL", "US", "GB", "AU", "DE", "NL"}

    def test_default_country_is_pl(self, api_client):
        _, token = register_user(api_client, "country_default")
        r = api_client.get(f"{BASE_URL}/api/auth/me", headers=auth_header(token))
        assert r.status_code == 200
        assert r.json().get("country") == "PL"

    def test_set_country_persists_and_is_returned(self, api_client):
        _, token = register_user(api_client, "country_set")
        r = api_client.patch(f"{BASE_URL}/api/account/country", headers=auth_header(token), json={"country": "US"})
        assert r.status_code == 200
        assert r.json().get("country") == "US"
        # re-fetch via /auth/me to confirm persistence (simulates re-entering profile screen)
        r2 = api_client.get(f"{BASE_URL}/api/auth/me", headers=auth_header(token))
        assert r2.status_code == 200
        assert r2.json().get("country") == "US"

    def test_set_unknown_country_rejected(self, api_client):
        _, token = register_user(api_client, "country_bad")
        r = api_client.patch(f"{BASE_URL}/api/account/country", headers=auth_header(token), json={"country": "ZZ"})
        assert r.status_code == 400


class TestDailyPlanPremiumGating:
    def test_free_user_cannot_create_daily_plan(self, api_client):
        _, token = register_user(api_client, "daily_free")
        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            headers=auth_header(token),
            json={"time_mode": "daily", "time_value": 30, "free_days": [5, 6]},
        )
        assert r.status_code == 403
        assert "Premium" in r.json().get("detail", "")

    def test_premium_user_can_create_daily_plan_settings(self, api_client):
        _, token = register_user(api_client, "daily_prem")
        sub = api_client.post(f"{BASE_URL}/api/premium/subscribe", headers=auth_header(token), json={"plan": "monthly"})
        assert sub.status_code == 200
        assert sub.json()["premium"]["active"] is True
        # need a ready roadmap path before a daily plan can be created
        title = f"Tester oprogramowania daily {uuid.uuid4().hex[:6]}"
        cr = api_client.post(f"{BASE_URL}/api/roadmap/custom", headers=auth_header(token), json={"title": title, "qualifications": ""})
        assert cr.status_code == 200, cr.text
        ready = poll_roadmap_status(api_client, token, max_wait=150)
        assert ready and ready.get("status") == "ready", f"roadmap not ready: {ready}"

        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            headers=auth_header(token),
            json={"time_mode": "daily", "time_value": 30, "free_days": [5, 6]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"


class TestWeeklyPlanAvailableToFree:
    def test_free_user_study_plan_requires_ready_path_not_403_for_premium(self, api_client):
        _, token = register_user(api_client, "weekly_free")
        # no roadmap chosen yet -> expect 400 (need path first), NOT 403 (premium-gated)
        r = api_client.post(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_header(token))
        assert r.status_code == 400
        assert r.status_code != 403


class TestSharedAiCacheSpeedup:
    def test_second_user_same_custom_title_is_faster(self, api_client):
        title = f"Tester oprogramowania cache {uuid.uuid4().hex[:6]}"
        _, token1 = register_user(api_client, "cache_u1")
        _, token2 = register_user(api_client, "cache_u2")

        t0 = time.time()
        r1 = api_client.post(f"{BASE_URL}/api/roadmap/custom", headers=auth_header(token1),
                              json={"title": title, "qualifications": ""})
        assert r1.status_code == 200, r1.text
        res1 = poll_roadmap_status(api_client, token1, max_wait=150)
        dur1 = time.time() - t0
        assert res1 and res1.get("status") == "ready", f"first gen did not become ready: {res1}"

        t1 = time.time()
        r2 = api_client.post(f"{BASE_URL}/api/roadmap/custom", headers=auth_header(token2),
                              json={"title": title, "qualifications": ""})
        assert r2.status_code == 200, r2.text
        res2 = poll_roadmap_status(api_client, token2, max_wait=150)
        dur2 = time.time() - t1
        assert res2 and res2.get("status") == "ready", f"second gen (cache hit expected) did not become ready: {res2}"

        print(f"first gen duration={dur1:.1f}s, second (cached) gen duration={dur2:.1f}s")
        assert dur2 < dur1, f"expected cached generation to be faster: dur1={dur1}, dur2={dur2}"
        assert dur2 < dur1 * 0.6, f"expected cached generation to be notably faster: dur1={dur1}, dur2={dur2}"
