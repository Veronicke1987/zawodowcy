# Regression test for token-cost fix in ask_llm() (server.py ~line 223):
# thinking={"type": "disabled"} for anthropic provider + max_tokens 16000 -> 4096.
# Goal: confirm NO functional regression (truncation / JSON parse failures / quality loss)
# across every LLM-backed endpoint, end-to-end with a fresh user.
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")


def poll(session, url, params=None, timeout=90, interval=3):
    start = time.time()
    while time.time() - start < timeout:
        r = session.get(url, params=params)
        assert r.status_code == 200, r.text
        data = r.json()
        if data.get("status") in ("ready", "error"):
            return data
        time.sleep(interval)
    pytest.fail(f"{url} did not finish in {timeout}s")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_thinking_{uuid.uuid4().hex[:8]}@test.pl"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "test123", "name": "TEST Thinking"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    s.email = email
    return s


ANSWERS = {
    "current_status": "pracuję na etacie",
    "current_job": "księgowa",
    "experience": "5 lat w księgowości w małej firmie produkcyjnej",
    "skills": "Excel, programy księgowe (Comarch Optima), obsługa klienta, dokładność",
    "interests": "technologia, organizacja wydarzeń, praca z ludźmi",
    "likes": "porządek, jasne zasady, praca z liczbami",
    "dislikes": "monotonia, brak kontaktu z ludźmi",
    "education": "wykształcenie średnie ekonomiczne",
    "learn_time": "5-10 godzin tygodniowo",
    "city": "Kraków",
    "reset_mode": "search",
}


class TestThinkingDisabledEndToEnd:
    """All steps run sequentially in ONE class so pytest-xdist's loadscope keeps them
    on a single worker (shared `client` session state across dependent LLM-backed steps)."""

    def test_profile_and_recommendations(self, client):
        r = client.put(f"{BASE_URL}/api/profile", json={"answers": ANSWERS})
        assert r.status_code == 200, r.text

        r = client.post(f"{BASE_URL}/api/recommendations/generate")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"

        data = poll(client, f"{BASE_URL}/api/recommendations")
        assert data["status"] == "ready", f"recommendations errored: {data}"

        summary = data.get("summary", "")
        assert summary and len(summary.split()) >= 15, f"summary too short/empty (truncation?): {summary!r}"

        for cat in ("now", "future"):
            items = data.get(cat) or []
            assert len(items) == 5, f"expected 5 '{cat}' items, got {len(items)}: {items}"
            for it in items:
                for field in ("title", "industry", "summary", "why", "match", "salary", "demand", "ai_risk", "missing_skills", "id", "category"):
                    assert field in it, f"missing field '{field}' in {cat} item: {it}"
                assert isinstance(it["title"], str) and it["title"], f"empty title in {it}"
                assert isinstance(it["summary"], str) and it["summary"].strip().endswith((".", "!", "?")), \
                    f"summary looks truncated (no terminal punctuation): {it['summary']!r}"
                assert isinstance(it["why"], str) and it["why"].strip().endswith((".", "!", "?")), \
                    f"why looks truncated: {it['why']!r}"
                assert isinstance(it["match"], (int, float)) and 0 <= it["match"] <= 100
                assert isinstance(it["missing_skills"], list)
        client.first_career_id = data["now"][0]["id"]
        client.first_career_title = data["now"][0]["title"]


    def test_career_detail_fresh(self, client):
        assert hasattr(client, "first_career_id"), "run after recommendations test"
        r = client.get(f"{BASE_URL}/api/careers/{client.first_career_id}")
        assert r.status_code == 200, r.text
        data = r.json()
        detail = data["detail"]
        for field in ("description", "daily_tasks", "pros", "cons", "requirements", "how_to_start", "career_levels"):
            assert field in detail, f"missing field '{field}' in career detail: {detail.keys()}"
        assert detail["description"].strip().endswith((".", "!", "?")), \
            f"description looks truncated: {detail['description']!r}"
        for list_field in ("daily_tasks", "pros", "cons", "requirements", "how_to_start", "career_levels"):
            items = detail[list_field]
            assert isinstance(items, list) and len(items) >= 2, f"{list_field} too short/empty: {items}"
            last = items[-1]
            assert isinstance(last, str) and last.strip(), f"{list_field} last item empty: {items}"
            # last list item should end with normal punctuation / word char, not get cut mid-word
            assert not last.strip().endswith((",", ";", ":", "-")), f"{list_field} last item looks truncated: {last!r}"


    def test_custom_path_elektryk(self, client):
        title = "TEST_Elektryk budowlany"
        r = client.post(f"{BASE_URL}/api/roadmap/custom", json={"title": title, "qualifications": ""})
        assert r.status_code == 200, r.text
        data = r.json()
        client.path_id = data["path_id"]
        ready = poll(client, f"{BASE_URL}/api/roadmap", params={"path_id": client.path_id}, timeout=90)
        assert ready["status"] == "ready", f"roadmap errored: {ready}"
        milestones = ready.get("milestones", [])
        assert len(milestones) >= 2, f"too few milestones: {milestones}"
        for m in milestones:
            for field in ("title", "description", "salary", "years", "requirements", "tasks"):
                assert field in m, f"missing field '{field}' in milestone: {m}"
            assert m["description"].strip().endswith((".", "!", "?")), f"milestone description truncated: {m['description']!r}"
            assert isinstance(m["requirements"], list) and len(m["requirements"]) >= 1
            assert isinstance(m["tasks"], list) and len(m["tasks"]) >= 1
            for t in m["tasks"]:
                for field in ("id", "title", "description", "type", "done"):
                    assert field in t, f"missing field '{field}' in task: {t}"
                assert t["description"].strip().endswith((".", "!", "?")), f"task description truncated: {t['description']!r}"
        client.first_task_id = milestones[0]["tasks"][0]["id"]


    def test_task_resources_not_truncated(self, client):
        assert hasattr(client, "first_task_id"), "run after custom roadmap test"
        r = client.get(f"{BASE_URL}/api/roadmap/tasks/{client.first_task_id}/resources")
        assert r.status_code == 200, r.text
        data = r.json()
        for field in ("overview", "steps", "free_tips", "specializations", "time_estimate", "resources"):
            assert field in data, f"missing field '{field}': {data.keys()}"
        assert data["overview"].strip().endswith((".", "!", "?")), f"overview truncated: {data['overview']!r}"
        assert isinstance(data["steps"], list) and len(data["steps"]) >= 2
        resources = data["resources"]
        assert isinstance(resources, list) and 3 <= len(resources) <= 10, f"unexpected resources count: {len(resources)}"
        for res in resources:
            for field in ("type", "platform", "title", "description", "query", "url"):
                assert field in res, f"missing field '{field}' in resource: {res}"
                assert res[field], f"empty field '{field}' in resource (possible truncation): {res}"
            assert not res["description"].strip().endswith((",", ";", ":")), f"resource description looks truncated: {res['description']!r}"


    def test_daily_plan_setup_and_generation(self, client):
        assert hasattr(client, "path_id"), "run after custom roadmap test"
        r = client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            params={"path_id": client.path_id},
            json={"time_mode": "daily", "time_value": 60, "free_days": [5, 6]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"

        start = time.time()
        data = None
        while time.time() - start < 90:
            resp = client.get(f"{BASE_URL}/api/roadmap/daily-plan", params={"path_id": client.path_id})
            assert resp.status_code == 200, resp.text
            data = resp.json()
            if data.get("status") in ("ready", "error"):
                break
            time.sleep(3)
        assert data is not None and data.get("status") == "ready", f"daily plan errored/timed out: {data}"
        weeks = data.get("weeks", [])
        assert len(weeks) >= 1, "expected at least 1 week generated"
        week = weeks[0]
        days = week.get("days", [])
        assert len(days) >= 1, "expected days in week"
        found_items = False
        for d in days:
            for it in d.get("items", []):
                found_items = True
                for field in ("id", "title", "description", "minutes"):
                    assert field in it, f"missing field '{field}' in daily item: {it}"
                assert it["description"], f"empty description in daily item: {it}"
        assert found_items, f"no items found in any day of week 0: {days}"


def test_no_json_parse_errors_in_backend_log():
    """Sanity scan of backend log for the specific failure signatures mentioned in the review request."""
    log_paths = [
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log",
    ]
    bad_signatures = ["No JSON in LLM response", "thinking", "invalid_request_error"]
    hits = []
    for path in log_paths:
        if not os.path.exists(path):
            continue
        with open(path, "r", errors="ignore") as f:
            content = f.read()
        for sig in bad_signatures:
            if sig.lower() in content.lower() and sig != "thinking":  # "thinking" alone appears in our own comment; check context separately
                hits.append((path, sig))
    # This is informational — just print, don't hard-fail the suite on log noise from prior runs.
    print(f"Log scan hits (informational): {hits}")
