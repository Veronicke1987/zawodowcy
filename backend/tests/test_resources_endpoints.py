"""
Backend tests for AI resource/details endpoints (task_resources, daily_item_resources)
Covers:
- /api/roadmap/custom -> create a custom career path with milestones/tasks
- /api/roadmap/tasks/{task_id}/resources -> fresh LLM generation + caching
- /api/roadmap/daily-plan/settings + GET /api/roadmap/daily-plan -> daily plan generation
- /api/roadmap/daily-plan/items/{item_id}/resources -> fresh LLM generation (item without milestone_task_id)
- Sanity checks: /api/careers/{career_id}, register/login
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = (os.environ.get('EXPO_BACKEND_URL') or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Register a fresh test user and return bearer token."""
    email = f"TEST_resources_{uuid.uuid4().hex[:10]}@test.pl"
    password = "test12345"
    resp = api_client.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Test Resources"})
    assert resp.status_code in (200, 201), f"register failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"no token in register response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestSanity:
    def test_register_login_roundtrip(self, api_client):
        email = f"TEST_sanity_{uuid.uuid4().hex[:10]}@test.pl"
        password = "test12345"
        r1 = api_client.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Sanity"})
        assert r1.status_code in (200, 201)
        r2 = api_client.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r2.status_code == 200
        body = r2.json()
        assert body.get("token") or body.get("access_token")

    def test_careers_detail_endpoint(self, api_client, auth_headers):
        # fetch some career id via careers list if exists, else try a plausible id
        list_resp = api_client.get(f"{API}/careers", headers=auth_headers)
        if list_resp.status_code == 200 and isinstance(list_resp.json(), list) and list_resp.json():
            career_id = list_resp.json()[0].get("id") or list_resp.json()[0].get("career_id")
            if career_id:
                detail = api_client.get(f"{API}/careers/{career_id}", headers=auth_headers)
                assert detail.status_code == 200, f"careers detail failed: {detail.status_code} {detail.text}"
                assert "title" in detail.json() or "career" in detail.json()
        else:
            pytest.skip("No /api/careers list endpoint or empty result; skipping careers detail check")


class TestCustomRoadmapAndTaskResources:
    """Create custom career path then fetch task resources (fresh + cached)."""

    @pytest.fixture(scope="class")
    def roadmap_task(self, api_client, auth_headers):
        resp = api_client.post(f"{API}/roadmap/custom", json={"title": "Grafik komputerowy", "qualifications": "brak doświadczenia"}, headers=auth_headers)
        assert resp.status_code in (200, 201, 202), f"custom roadmap failed: {resp.status_code} {resp.text}"
        body = resp.json()
        # The custom endpoint may return job status (pending) - poll roadmap if needed
        path_id = body.get("path_id")
        status = body.get("status")
        deadline = time.time() + 90
        doc = None
        while time.time() < deadline:
            rm = api_client.get(f"{API}/roadmap", headers=auth_headers)
            if rm.status_code == 200:
                rm_body = rm.json()
                if rm_body.get("status") == "ready" and rm_body.get("milestones"):
                    doc = rm_body
                    break
                if rm_body.get("status") == "error":
                    pytest.fail(f"roadmap generation errored: {rm_body}")
            time.sleep(3)
        assert doc is not None, "roadmap did not become ready within timeout"
        task_id = None
        for m in doc["milestones"]:
            for t in m["tasks"]:
                task_id = t["id"]
                break
            if task_id:
                break
        assert task_id, "no task found in generated roadmap"
        return task_id

    def test_task_resources_fresh_generation(self, api_client, auth_headers, roadmap_task):
        task_id = roadmap_task
        resp = api_client.get(f"{API}/roadmap/tasks/{task_id}/resources", headers=auth_headers, timeout=90)
        assert resp.status_code == 200, f"task resources failed: {resp.status_code} {resp.text}"
        data = resp.json()
        for field in ["overview", "steps", "free_tips", "specializations", "time_estimate", "resources"]:
            assert field in data, f"missing field {field} in {data}"
        assert isinstance(data["steps"], list) and len(data["steps"]) > 0
        assert isinstance(data["free_tips"], list) and len(data["free_tips"]) > 0
        assert isinstance(data["resources"], list)
        assert 4 <= len(data["resources"]) <= 9, f"expected ~5-8 resources, got {len(data['resources'])}"
        for r in data["resources"]:
            for key in ["type", "platform", "title", "description", "query", "url"]:
                assert key in r, f"resource missing key {key}: {r}"
        # qualitative length check - overview should be more than a trivially short one-liner
        assert len(data["overview"].split()) >= 8, f"overview too short: {data['overview']}"
        # store for cache test
        TestCustomRoadmapAndTaskResources._first_response = data
        TestCustomRoadmapAndTaskResources._task_id = task_id

    def test_task_resources_cached_on_second_call(self, api_client, auth_headers):
        task_id = getattr(TestCustomRoadmapAndTaskResources, "_task_id", None)
        if not task_id:
            pytest.skip("No task_id from previous test (fresh generation must have failed)")
        start = time.time()
        resp = api_client.get(f"{API}/roadmap/tasks/{task_id}/resources", headers=auth_headers, timeout=30)
        elapsed = time.time() - start
        assert resp.status_code == 200
        data = resp.json()
        first = TestCustomRoadmapAndTaskResources._first_response
        assert data == first, "cached response should be identical to first response"
        assert elapsed < 5, f"cached response took too long ({elapsed}s), may not be cached"


class TestDailyPlanItemResources:
    @pytest.fixture(scope="class")
    def daily_item_no_milestone(self, api_client, auth_headers):
        # Daily plan requires an active, ready roadmap first - create one for this user/worker.
        custom_resp = api_client.post(f"{API}/roadmap/custom", json={"title": "Specjalista ds. HR", "qualifications": "brak doświadczenia"}, headers=auth_headers)
        assert custom_resp.status_code in (200, 201, 202), f"custom roadmap failed: {custom_resp.status_code} {custom_resp.text}"
        deadline = time.time() + 90
        ready = False
        while time.time() < deadline:
            rm = api_client.get(f"{API}/roadmap", headers=auth_headers)
            if rm.status_code == 200 and rm.json().get("status") == "ready" and rm.json().get("milestones"):
                ready = True
                break
            if rm.status_code == 200 and rm.json().get("status") == "error":
                pytest.fail(f"roadmap generation errored: {rm.json()}")
            time.sleep(3)
        assert ready, "roadmap did not become ready within timeout for daily plan setup"

        settings_resp = api_client.post(
            f"{API}/roadmap/daily-plan/settings",
            json={"time_mode": "daily", "time_value": 60, "free_days": [5, 6]},
            headers=auth_headers,
        )
        assert settings_resp.status_code in (200, 201), f"settings failed: {settings_resp.status_code} {settings_resp.text}"

        deadline = time.time() + 120
        plan = None
        while time.time() < deadline:
            resp = api_client.get(f"{API}/roadmap/daily-plan", headers=auth_headers)
            assert resp.status_code == 200
            body = resp.json()
            if body.get("status") == "ready" and body.get("weeks"):
                plan = body
                break
            if body.get("status") == "error":
                pytest.fail(f"daily plan generation errored: {body}")
            time.sleep(3)
        assert plan is not None, "daily plan did not become ready within timeout"

        item_id = None
        for w in plan["weeks"]:
            for d in w.get("days", []):
                for it in d.get("items", []):
                    if not it.get("milestone_task_id"):
                        item_id = it["id"]
                        break
                if item_id:
                    break
            if item_id:
                break
        if not item_id:
            pytest.skip("No daily plan item without milestone_task_id found")
        return item_id

    def test_daily_item_resources_fresh_generation(self, api_client, auth_headers, daily_item_no_milestone):
        item_id = daily_item_no_milestone
        resp = api_client.get(f"{API}/roadmap/daily-plan/items/{item_id}/resources", headers=auth_headers, timeout=90)
        assert resp.status_code == 200, f"daily item resources failed: {resp.status_code} {resp.text}"
        data = resp.json()
        for field in ["overview", "steps", "free_tips", "resources"]:
            assert field in data, f"missing field {field} in {data}"
        assert isinstance(data["resources"], list)
        assert 3 <= len(data["resources"]) <= 7, f"expected ~4-6 resources, got {len(data['resources'])}"
        for r in data["resources"]:
            for key in ["type", "platform", "title", "description", "query", "url"]:
                assert key in r, f"resource missing key {key}: {r}"
        assert len(data["overview"].split()) >= 5, f"overview too short: {data['overview']}"
