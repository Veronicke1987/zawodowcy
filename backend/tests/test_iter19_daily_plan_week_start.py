"""
Iteration 19 tests: daily plan "first week starts today, not Monday" fix.
Covers:
- POST /api/roadmap/daily-plan/settings -> week_start = today (not Monday-snapped)
- GET /api/roadmap/daily-plan polling until ready: start_date == today, all dates >= today,
  weekday field matches calendar weekday, 7 consecutive days, free_days respected
- POST /api/roadmap/daily-plan/next-week rolls forward exactly 7 days, gating (403 if too early)
"""
import os
import time
from datetime import date, timedelta

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


def poll_ready(api_client, token, field="status", max_wait=90):
    deadline = time.time() + max_wait
    last = None
    while time.time() < deadline:
        r = api_client.get(f"{BASE_URL}/api/roadmap/daily-plan", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        last = r.json()
        if last.get(field) in ("ready", "error"):
            return last
        time.sleep(3)
    return last


class TestDailyPlanWeekStartsToday:
    def test_new_plan_week_start_is_today_and_dates_valid(self, api_client, seeded_token):
        today = date.today()
        # mark a weekday as free that will appear in this window, to verify free_days respected
        free_weekday = (today.weekday() + 2) % 7
        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            headers={"Authorization": f"Bearer {seeded_token}"},
            json={"time_mode": "daily", "time_value": 30, "free_days": [free_weekday]},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        data = poll_ready(api_client, seeded_token)
        assert data is not None, "daily plan never resolved"
        assert data["status"] == "ready", f"plan failed/timed out: {data}"
        weeks = data["weeks"]
        assert len(weeks) == 1
        week = weeks[0]

        # (a) start_date == today
        assert week["start_date"] == today.isoformat(), f"expected start_date {today}, got {week['start_date']}"

        days = week["days"]
        assert len(days) == 7

        # (d) consecutive days today..today+6, no gaps/dupes
        expected_dates = [(today + timedelta(days=i)).isoformat() for i in range(7)]
        actual_dates = [d["date"] for d in days]
        assert actual_dates == expected_dates, f"expected {expected_dates}, got {actual_dates}"

        for d in days:
            dt = date.fromisoformat(d["date"])
            # (b) no past dates
            assert dt >= today, f"found past date {dt}"
            # (c) weekday field matches calendar weekday
            assert d["weekday"] == dt.weekday(), f"weekday mismatch for {dt}: field={d['weekday']} actual={dt.weekday()}"
            # (e) free_days respected
            if dt.weekday() == free_weekday:
                assert d["free"] is True, f"{dt} should be free (weekday {free_weekday})"
            else:
                assert d["free"] is False

    def test_next_week_blocked_immediately_after_creation(self, api_client, seeded_token):
        # Plan was just (re)created in previous test with week_start = today -> unlock day = today+5
        # Calling next-week immediately should be 403/400 "too early" unless today already >= unlock day
        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/next-week",
            headers={"Authorization": f"Bearer {seeded_token}"},
        )
        # Should not succeed with 200 "pending" since freshly created week is not yet unlockable
        assert r.status_code == 400, f"expected 400 'too early', got {r.status_code}: {r.text}"
        assert "tydzień" in r.json().get("detail", "").lower() or "sobot" in r.json().get("detail", "").lower()

    def test_next_week_rolls_forward_7_days_when_unlocked(self, api_client, seeded_token):
        # Directly manipulate stored start_date in Mongo to simulate an eligible past week,
        # then verify next-week rolls forward exactly 7 days from that start_date.
        import pymongo

        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            pytest.skip("MONGO_URL/DB_NAME not available for direct manipulation")
        client = pymongo.MongoClient(mongo_url)
        db = client[db_name]

        # find seeded user's roadmap with daily_plan
        r = api_client.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {seeded_token}"})
        assert r.status_code == 200
        user_id = r.json()["id"]

        roadmap = db.roadmaps.find_one({"user_id": user_id, "daily_plan.status": "ready"})
        assert roadmap is not None, "expected a ready daily_plan for seeded user"
        path_id = roadmap["path_id"]
        weeks = roadmap["daily_plan"]["weeks"]
        last_week = weeks[-1]
        fake_start = date.today() - timedelta(days=10)  # definitely unlockable (>today-5)
        db.roadmaps.update_one(
            {"user_id": user_id, "path_id": path_id, "daily_plan.weeks.index": last_week["index"]},
            {"$set": {"daily_plan.weeks.$.start_date": fake_start.isoformat()}},
        )

        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/next-week",
            headers={"Authorization": f"Bearer {seeded_token}"},
            params={"path_id": path_id},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        data = poll_ready(api_client, seeded_token, field="next_status")
        assert data["next_status"] == "ready", f"next week failed: {data}"
        new_weeks = data["weeks"]
        new_week = [w for w in new_weeks if w["index"] == last_week["index"] + 1][0]
        expected_next_start = (fake_start + timedelta(days=7)).isoformat()
        assert new_week["start_date"] == expected_next_start, (
            f"expected next week start {expected_next_start}, got {new_week['start_date']}"
        )
        # cleanup: remove the extra week + reset status so other tests/users aren't polluted
        db.roadmaps.update_one(
            {"user_id": user_id, "path_id": path_id},
            {"$pull": {"daily_plan.weeks": {"index": new_week["index"]}},
             "$set": {"daily_plan.next_status": "none"}},
        )
        client.close()
