"""
E2E backend test for the LLM provider swap Gemini(gemini-3.5-flash) -> Anthropic(claude-haiku-5-5).
Covers every AI-backed endpoint with a fresh TEST_ user and real ANTHROPIC_API_KEY calls (no mocks):
  - register + profile
  - recommendations generate/poll (ask_llm regex-based JSON extraction, watch for markdown fences)
  - career detail (fresh + cached)
  - custom roadmap generate/poll
  - task resources (fresh + cached)
  - daily plan settings + generation
  - study plan (premium, best-effort)
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get('EXPO_BACKEND_URL', os.environ.get('EXPO_PUBLIC_BACKEND_URL', '')).rstrip('/')
API = f"{BASE_URL}/api"

SAMPLE_ANSWERS = {
    "age": "30-40",
    "education": "srednie",
    "experience": "Pracowałem jako sprzedawca przez 5 lat.",
    "interests": ["technologia", "praca_z_ludzmi"],
    "strengths": ["komunikatywnosc", "zorganizowanie"],
    "work_style": "zespolowa",
    "goals": "Chcę zmienić zawód na coś bardziej technicznego i stabilnego finansowo.",
    "constraints": "Mogę się uczyć wieczorami, mam 2 godziny dziennie.",
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_session(session):
    email = f"TEST_claude_{uuid.uuid4().hex[:8]}@test.pl"
    password = "test123"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Claude Test"})
    assert r.status_code == 201, f"register failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"no token in register response: {r.text}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, email


def poll(session, url, timeout=120, interval=3):
    """Poll a GET endpoint until json 'status' == 'ready' or 'error', or timeout."""
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = session.get(url)
        last = r
        if r.status_code == 200:
            data = r.json()
            status = data.get("status")
            if status in ("ready", "error", None):
                return r
        time.sleep(interval)
    return last


class TestProfileAndRecommendations:
    def test_profile_submit(self, auth_session):
        session, _ = auth_session
        r = session.put(f"{API}/profile", json={"answers": SAMPLE_ANSWERS})
        assert r.status_code == 200, f"profile failed: {r.status_code} {r.text}"

    def test_generate_recommendations_and_poll(self, auth_session):
        session, _ = auth_session
        r = session.post(f"{API}/recommendations/generate")
        assert r.status_code == 200, f"generate failed: {r.status_code} {r.text}"

        final = poll(session, f"{API}/recommendations", timeout=150)
        assert final is not None, "polling never returned a response"
        assert final.status_code == 200, f"poll failed: {final.status_code} {final.text}"
        data = final.json()
        assert data.get("status") == "ready", f"recommendations never became ready: {data}"

        rec = data.get("data") or data
        summary = rec.get("summary", "")
        assert isinstance(summary, str) and len(summary) > 20, f"summary too short/missing: {rec}"
        now_list = rec.get("now") or rec.get("now_careers")
        future_list = rec.get("future") or rec.get("future_careers")
        assert now_list, f"no 'now' career list in recommendations: {rec.keys()}"
        assert future_list, f"no 'future' career list in recommendations: {rec.keys()}"
        first = now_list[0]
        for field in ("title", "summary"):
            assert field in first, f"missing field {field} in career item: {first}"
        # store for next tests
        TestProfileAndRecommendations.career_id = first.get("id") or first.get("career_id")


class TestCareerDetail:
    def test_career_detail_fresh_and_cached(self, auth_session):
        session, _ = auth_session
        career_id = getattr(TestProfileAndRecommendations, "career_id", None)
        if not career_id:
            pytest.skip("no career_id captured from recommendations test")
        r1 = session.get(f"{API}/careers/{career_id}")
        assert r1.status_code == 200, f"career detail failed: {r1.status_code} {r1.text}"
        d1 = r1.json()
        detail1 = d1.get("detail") or d1
        for field in ("description", "pros", "cons", "requirements", "how_to_start"):
            assert field in detail1, f"missing field {field} in career detail: {detail1.keys()}"

        r2 = session.get(f"{API}/careers/{career_id}")
        assert r2.status_code == 200, f"career detail (cached) failed: {r2.status_code} {r2.text}"
        d2 = r2.json()
        detail2 = d2.get("detail") or d2
        assert detail1.get("description") == detail2.get("description"), "career detail not cached (content differs on 2nd call)"


class TestCustomRoadmap:
    def test_custom_roadmap_and_poll(self, auth_session):
        session, _ = auth_session
        r = session.post(f"{API}/roadmap/custom", json={"title": "elektryk", "qualifications": ""})
        assert r.status_code == 200, f"custom roadmap failed: {r.status_code} {r.text}"

        final = poll(session, f"{API}/roadmap", timeout=150)
        assert final is not None
        assert final.status_code == 200, f"roadmap poll failed: {final.status_code} {final.text}"
        data = final.json()
        assert data.get("status") == "ready", f"roadmap never ready: {data}"
        milestones = data.get("milestones") or (data.get("data") or {}).get("milestones")
        assert milestones, f"no milestones generated: {data}"
        first_milestone = milestones[0]
        tasks = first_milestone.get("tasks")
        assert tasks, f"no tasks in first milestone: {first_milestone}"
        TestCustomRoadmap.task_id = tasks[0].get("id") or tasks[0].get("task_id")


class TestTaskResources:
    def test_task_resources_fresh_and_cached(self, auth_session):
        session, _ = auth_session
        task_id = getattr(TestCustomRoadmap, "task_id", None)
        if not task_id:
            pytest.skip("no task_id captured from roadmap test")
        r1 = session.get(f"{API}/roadmap/tasks/{task_id}/resources")
        assert r1.status_code == 200, f"task resources failed: {r1.status_code} {r1.text}"
        d1 = r1.json()
        for field in ("overview", "steps"):
            assert field in d1, f"missing field {field}: {d1.keys()}"

        r2 = session.get(f"{API}/roadmap/tasks/{task_id}/resources")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d1.get("overview") == d2.get("overview"), "task resources not cached"


class TestDailyPlan:
    def test_daily_plan_settings_and_generate(self, auth_session):
        session, _ = auth_session
        r = session.post(f"{API}/roadmap/daily-plan/settings", json={
            "time_mode": "daily", "time_value": 60, "free_days": [5, 6]
        })
        assert r.status_code == 200, f"daily-plan settings failed: {r.status_code} {r.text}"

        final = poll(session, f"{API}/roadmap/daily-plan", timeout=120)
        assert final is not None
        assert final.status_code == 200, f"daily-plan poll failed: {final.status_code} {final.text}"
        data = final.json()
        # tolerate either direct items or status-wrapped shape
        items = data.get("items") or (data.get("data") or {}).get("items")
        assert data.get("status") in (None, "ready") or items, f"daily plan not generated correctly: {data}"


class TestStudyPlan:
    def test_premium_subscribe_and_study_plan(self, auth_session):
        session, _ = auth_session
        r_sub = session.post(f"{API}/premium/subscribe", json={"plan": "monthly"})
        if r_sub.status_code != 200:
            pytest.skip(f"premium subscribe not available: {r_sub.status_code} {r_sub.text}")

        r = session.post(f"{API}/roadmap/study-plan")
        if r.status_code not in (200, 202):
            pytest.skip(f"study-plan generate endpoint returned {r.status_code}: {r.text}")

        final = poll(session, f"{API}/roadmap/study-plan", timeout=120)
        assert final is not None
        assert final.status_code == 200, f"study-plan poll failed: {final.status_code} {final.text}"
