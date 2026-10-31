"""
Phase 1 Daily Study Plan tests:
- POST /api/roadmap/daily-plan/settings validation (bad time_mode, all-7-days-free)
- GET /api/roadmap/daily-plan (status none for fresh user, ready plan structure for seeded user)
- PATCH /api/roadmap/daily-plan/items/{item_id} toggle + 404 for unknown id + persistence via GET
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
SEEDED_USER = {"email": "ania_t1@test.pl", "password": "test123"}


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def seeded_token(api_client):
    r = api_client.post(f"{BASE_URL}/api/auth/login", json=SEEDED_USER)
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def fresh_user_token(api_client):
    email = f"TEST_dp_{int(time.time()*1000)}@test.pl"
    r = api_client.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "test123", "name": "TestDP"})
    assert r.status_code in (200, 201)
    return r.json()["access_token"]


class TestDailyPlanSettingsValidation:
    def test_invalid_time_mode_rejected(self, api_client, seeded_token):
        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            headers={"Authorization": f"Bearer {seeded_token}"},
            json={"time_mode": "monthly", "time_value": 30, "free_days": [5, 6]},
        )
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_all_seven_days_free_rejected(self, api_client, seeded_token):
        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            headers={"Authorization": f"Bearer {seeded_token}"},
            json={"time_mode": "daily", "time_value": 30, "free_days": [0, 1, 2, 3, 4, 5, 6]},
        )
        assert r.status_code == 400
        assert "dzień nauki" in r.json()["detail"]

    def test_settings_rejected_without_ready_roadmap(self, api_client, fresh_user_token):
        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            headers={"Authorization": f"Bearer {fresh_user_token}"},
            json={"time_mode": "daily", "time_value": 30, "free_days": [5, 6]},
        )
        assert r.status_code == 400


class TestDailyPlanGet:
    def test_fresh_user_no_roadmap_returns_none(self, api_client, fresh_user_token):
        r = api_client.get(f"{BASE_URL}/api/roadmap/daily-plan", headers={"Authorization": f"Bearer {fresh_user_token}"})
        assert r.status_code == 200
        assert r.json() == {"status": "none"}

    def test_seeded_user_ready_plan_structure(self, api_client, seeded_token):
        r = api_client.get(f"{BASE_URL}/api/roadmap/daily-plan", headers={"Authorization": f"Bearer {seeded_token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("ready", "pending", "error")
        if data["status"] == "ready":
            assert "settings" in data and "free_days" in data["settings"]
            assert len(data["weeks"]) >= 1
            week = data["weeks"][-1]
            assert len(week["days"]) == 7
            for day in week["days"]:
                assert set(day.keys()) >= {"date", "weekday", "free", "items"}
                if day["free"]:
                    assert day["items"] == []
            assert "is_premium" in data
            assert "career" in data


class TestDailyPlanItemToggle:
    def test_toggle_unknown_item_404(self, api_client, seeded_token):
        r = api_client.patch(
            f"{BASE_URL}/api/roadmap/daily-plan/items/doesnotexist123",
            headers={"Authorization": f"Bearer {seeded_token}"},
            json={"done": True},
        )
        assert r.status_code == 404

    def test_toggle_existing_item_persists(self, api_client, seeded_token):
        plan = api_client.get(f"{BASE_URL}/api/roadmap/daily-plan", headers={"Authorization": f"Bearer {seeded_token}"}).json()
        if plan.get("status") != "ready":
            pytest.skip("seeded user has no ready daily plan right now")
        item_id = None
        for week in plan["weeks"]:
            for day in week["days"]:
                if day["items"]:
                    item_id = day["items"][0]["id"]
                    break
            if item_id:
                break
        assert item_id, "expected at least one item in seeded user's plan"

        toggle = api_client.patch(
            f"{BASE_URL}/api/roadmap/daily-plan/items/{item_id}",
            headers={"Authorization": f"Bearer {seeded_token}"},
            json={"done": True},
        )
        assert toggle.status_code == 200
        assert toggle.json()["done"] is True

        verify = api_client.get(f"{BASE_URL}/api/roadmap/daily-plan", headers={"Authorization": f"Bearer {seeded_token}"}).json()
        found = False
        for week in verify["weeks"]:
            for day in week["days"]:
                for it in day["items"]:
                    if it["id"] == item_id:
                        assert it["done"] is True
                        found = True
        assert found
