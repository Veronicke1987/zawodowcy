"""
Iteration 26: targeted regression test for the trimmed career_detail endpoint
(GET /api/careers/{career_id}) - removed user-profile injection into the prompt,
added explicit isolation instruction. Verifies:
  - full flow: register -> profile -> recommendations.generate -> poll -> career_id
  - fresh (uncached) career_detail call returns 200 with all expected keys
  - repeat call is served from cache (fast, identical)
  - no 500/502s, Polish content, realistic career_levels
  - quick regression: /api/roadmap/custom and /api/roadmap/tasks/{id}/resources still 200
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"

SAMPLE_ANSWERS = {
    "reset_mode": "search",
    "current_status": "Pracuję jako księgowa, szukam zmiany.",
    "likes": "Lubię pracę z ludźmi, kreatywne zadania, organizację wydarzeń.",
    "dislikes": "Nie lubię monotonnej pracy biurowej i długich godzin przy komputerze.",
    "strengths": "Komunikatywność, dobra organizacja, znajomość Excela.",
    "learn_time": "5-10 godzin tygodniowo",
    "education": "Wyższe ekonomiczne",
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_session(session):
    email = f"TEST_iter26_{uuid.uuid4().hex[:8]}@test.pl"
    password = "test123456"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Iter26 Tester"})
    assert r.status_code == 201, f"register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def wait_for_status(session, url, timeout=120, interval=3):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = session.get(url)
        assert r.status_code == 200, f"{url} -> {r.status_code} {r.text}"
        last = r.json()
        if last.get("status") in ("ready", "error"):
            return last
        time.sleep(interval)
    pytest.fail(f"Timed out waiting for {url}, last={last}")


class TestCareerDetailTrimmed:

    def test_01_profile_and_recommendations(self, auth_session):
        r = auth_session.put(f"{API}/profile", json={"answers": SAMPLE_ANSWERS})
        assert r.status_code == 200, f"profile failed: {r.status_code} {r.text}"

        r = auth_session.post(f"{API}/recommendations/generate")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        doc = wait_for_status(auth_session, f"{API}/recommendations", timeout=150)
        assert doc["status"] == "ready", f"recommendations generation failed: {doc}"
        now_list = doc.get("now") or []
        future_list = doc.get("future") or []
        assert len(now_list) + len(future_list) > 0, "no careers returned"

        global_store["career"] = (now_list + future_list)[0]
        print(f"Picked career for detail test: {global_store['career']}")

    def test_02_career_detail_fresh_uncached(self, auth_session):
        career = global_store["career"]
        career_id = career["id"]
        t0 = time.time()
        r = auth_session.get(f"{API}/careers/{career_id}")
        elapsed = time.time() - t0
        assert r.status_code == 200, f"career_detail failed: {r.status_code} {r.text}"
        data = r.json()
        print(f"Fresh call took {elapsed:.2f}s")

        assert "career" in data and "detail" in data and "job_links" in data
        detail = data["detail"]
        for key in ("description", "daily_tasks", "pros", "cons", "requirements", "how_to_start", "career_levels"):
            assert key in detail, f"missing key {key} in detail: {detail}"

        for arr_key in ("daily_tasks", "pros", "cons", "requirements", "how_to_start", "career_levels"):
            assert isinstance(detail[arr_key], list) and len(detail[arr_key]) > 0, f"{arr_key} should be non-empty list"

        assert isinstance(detail["description"], str) and len(detail["description"]) > 10

        # Polish language heuristic check - look for common Polish diacritics / words
        full_text = " ".join(
            [detail["description"]] + detail["daily_tasks"] + detail["pros"] + detail["cons"] + detail["requirements"]
            + detail["how_to_start"] + detail["career_levels"]
        ).lower()
        polish_markers = ["ą", "ę", "ć", "ś", "ł", "ż", "ź", "ń", "ó", " i ", " z ", " w "]
        assert any(m in full_text for m in polish_markers), f"content doesn't look Polish: {full_text[:300]}"

        print(f"career_levels for '{career['title']}': {detail['career_levels']}")
        global_store["fresh_detail"] = detail
        global_store["career_id"] = career_id
        global_store["fresh_elapsed"] = elapsed

    def test_03_career_detail_cached_repeat(self, auth_session):
        career_id = global_store["career_id"]
        t0 = time.time()
        r = auth_session.get(f"{API}/careers/{career_id}")
        elapsed = time.time() - t0
        assert r.status_code == 200, f"cached career_detail failed: {r.status_code} {r.text}"
        data = r.json()
        print(f"Cached call took {elapsed:.2f}s (fresh was {global_store['fresh_elapsed']:.2f}s)")

        assert data["detail"] == global_store["fresh_detail"], "cached detail does not match freshly generated detail"
        # Cached call should be noticeably fast (no LLM round trip)
        assert elapsed < 5, f"cached call took too long ({elapsed:.2f}s), may not be using cache"

    def test_04_regression_roadmap_custom(self, auth_session):
        r = auth_session.post(f"{API}/roadmap/custom", json={"title": "Analityk danych", "qualifications": "Excel, SQL"})
        assert r.status_code == 200, f"roadmap/custom failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "pending"
        path_id = data.get("path_id")
        assert path_id

        doc = wait_for_status(auth_session, f"{API}/roadmap?path_id={path_id}", timeout=150)
        assert doc["status"] == "ready", f"roadmap generation failed: {doc}"
        global_store["roadmap_doc"] = doc

    def test_05_regression_task_resources(self, auth_session):
        doc = global_store.get("roadmap_doc")
        assert doc, "no roadmap doc from previous test"
        milestones = doc.get("milestones") or []
        task_id = None
        for m in milestones:
            for t in m.get("tasks", []):
                task_id = t["id"]
                break
            if task_id:
                break
        assert task_id, f"no tasks found in roadmap: {doc}"

        r = auth_session.get(f"{API}/roadmap/tasks/{task_id}/resources")
        assert r.status_code == 200, f"task_resources failed: {r.status_code} {r.text}"
        data = r.json()
        assert data, "empty task_resources response"
        print(f"task_resources response keys: {list(data.keys())}")


global_store = {}
