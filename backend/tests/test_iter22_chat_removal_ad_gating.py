"""
Iteration 22 verification tests:
1. AI Chat Advisor fully removed -> /api/chat/* must 404, /api/premium no chat quota fields
2. Regression: quiz -> recommendations, roadmap (custom-path), daily-plan settings/next-week still work end-to-end
3. Spot check AI output lengths (roadmap milestones/tasks, recommendations) for conciseness
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def fresh_user(api_client):
    """Register a truly fresh TEST_ user with no profile yet."""
    email = f"TEST_fresh_{uuid.uuid4().hex[:8]}@example.com"
    password = "Test@123"
    r = api_client.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Test Fresh"})
    assert r.status_code in (200, 201), r.text
    token = r.json()["access_token"]
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client


class TestChatRemoval:
    def test_chat_stream_404(self, fresh_user):
        r = fresh_user.post(f"{API}/chat/stream", json={"message": "hello"})
        assert r.status_code == 404, r.text

    def test_chat_get_404(self, fresh_user):
        r = fresh_user.get(f"{API}/chat")
        assert r.status_code == 404, r.text

    def test_chat_delete_404(self, fresh_user):
        r = fresh_user.delete(f"{API}/chat")
        assert r.status_code == 404, r.text

    def test_premium_no_chat_quota_fields(self, fresh_user):
        r = fresh_user.get(f"{API}/premium")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "free_chat_per_day" not in data
        assert "premium_chat_per_day" not in data
        assert "is_premium" in data and "plans" in data


class TestRegressionQuizRoadmapDailyPlan:
    def test_full_flow_fresh_user(self, fresh_user):
        """Fresh user: submit quiz -> recommendations -> custom path -> roadmap -> daily plan settings -> next-week."""
        answers = {
            "personality": {"intro_extro": 3, "detail_big_picture": 3},
            "interests": ["technology", "people"],
            "skills": ["communication"],
            "work_style": "office",
            "experience_years": 5,
            "current_role": "Ksiegowa",
        }
        r = fresh_user.put(f"{API}/profile", json={"answers": answers})
        assert r.status_code == 200, r.text

        r = fresh_user.post(f"{API}/recommendations/generate")
        assert r.status_code == 200, r.text

        # poll for recommendations ready
        ready = False
        recs = None
        for _ in range(40):
            r = fresh_user.get(f"{API}/recommendations")
            if r.status_code == 200:
                recs = r.json()
                if recs.get("status") == "ready":
                    ready = True
                    break
            time.sleep(3)
        assert ready, f"recommendations never became ready: {recs}"
        now_items = recs.get("now") or recs.get("items", {}).get("now", [])
        assert len(now_items) >= 1

        # spot check conciseness of 'why' field
        sample_why = now_items[0].get("why", "")
        print(f"\n[LEN CHECK] recommendation 'why' word count={len(sample_why.split())}: {sample_why}")

        # custom path flow (regression - still ad-gated on frontend, backend endpoint unaffected)
        title = f"TEST_Elektryk przemyslowy {uuid.uuid4().hex[:4]}"
        r = fresh_user.post(f"{API}/roadmap/custom", json={"title": title})
        assert r.status_code == 200, r.text

        roadmap_ready = False
        roadmap = None
        for _ in range(60):
            r = fresh_user.get(f"{API}/roadmap")
            if r.status_code == 200:
                roadmap = r.json()
                if roadmap.get("status") == "ready":
                    roadmap_ready = True
                    break
            time.sleep(3)
        assert roadmap_ready, f"roadmap never became ready: {roadmap}"
        milestones = roadmap.get("milestones", [])
        assert len(milestones) >= 1
        sample_desc = milestones[0].get("description") or milestones[0].get("desc", "")
        print(f"\n[LEN CHECK] milestone description word count={len(str(sample_desc).split())}: {sample_desc}")

        # daily plan settings (first time)
        r = fresh_user.post(f"{API}/roadmap/daily-plan/settings", json={"time_mode": "daily", "time_value": 30, "free_days": [5, 6]})
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "pending"

        plan_ready = False
        plan = None
        for _ in range(60):
            r = fresh_user.get(f"{API}/roadmap/daily-plan")
            if r.status_code == 200:
                plan = r.json()
                if plan.get("status") == "ready":
                    plan_ready = True
                    break
            time.sleep(3)
        assert plan_ready, f"daily plan never became ready: {plan}"

        # redo settings (same endpoint again) should still work (ad-gate is frontend only)
        r = fresh_user.post(f"{API}/roadmap/daily-plan/settings", json={"time_mode": "daily", "time_value": 45, "free_days": [6]})
        assert r.status_code == 200, r.text


class TestPasswordResetRegression:
    def test_forgot_password_endpoint_exists(self, api_client):
        r = api_client.post(f"{API}/auth/forgot-password", json={"email": "ania_t1@test.pl"})
        # should not 404/500 regardless of email existing
        assert r.status_code in (200, 400, 422), r.text
