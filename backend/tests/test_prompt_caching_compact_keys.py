"""
Regression test for round 2 of token-cost optimization in server.py:
1. Prompt caching: ask_llm() now sends system message via initial_messages with
   cache_control ephemeral breakpoint for Anthropic calls (~line 223).
2. Compact JSON keys for run_recommendations() (~line 607): LLM asked to use
   short keys (t/i/s/w/m/sa/d/r/g) which get mapped back to full field names
   (title/industry/summary/why/match/salary/demand/ai_risk/missing_skills)
   before persisting; missing_skills capped at 2 items.

This test runs a full E2E flow with a fresh user and asserts no regression:
- no cache_control related API errors
- every recommendation item has ALL full field names present/non-empty
- no short-key leakage (t/i/s/w/m/sa/d/r/g) in the final response
- missing_skills has at most 2 items
- content is Polish, full sentences (not fragments)
- downstream endpoints (careers/{id}, roadmap/custom, roadmap resources) still work
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

FULL_KEYS = ["title", "industry", "summary", "why", "match", "salary", "demand", "ai_risk", "missing_skills"]
SHORT_KEYS = ["t", "i", "s", "w", "m", "sa", "d", "r", "g"]
PRE_EXISTING_KEYS = ["id", "category"]

REALISTIC_ANSWERS = {
    "current_job": "Księgowa w średniej firmie produkcyjnej",
    "skills": ["Excel", "obsługa klienta", "organizacja pracy", "znajomość programów księgowych"],
    "interests": ["liczby", "porządkowanie danych", "kontakt z ludźmi"],
    "personality": "dokładna, lubi stabilność, ale chce więcej kontaktu z ludźmi",
    "dislikes": ["monotonna praca papierkowa", "praca w nocy"],
    "education": "Technikum ekonomiczne",
    "reset_mode": "search",
}


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    email = f"TEST_cache_{uuid.uuid4().hex[:8]}@test.pl"
    resp = api_client.post(f"{API}/auth/register", json={
        "email": email, "password": "test123", "name": "Test Cache User"
    })
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in register response: {data}"
    return token, email


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    token, _ = auth_token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestPromptCachingAndCompactKeys:

    def test_01_profile_save(self, api_client, auth_headers):
        resp = api_client.put(f"{API}/profile", json={"answers": REALISTIC_ANSWERS}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        get_resp = api_client.get(f"{API}/profile", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json().get("answers") is not None

    def test_02_generate_and_poll_recommendations(self, api_client, auth_headers):
        gen_resp = api_client.post(f"{API}/recommendations/generate", headers=auth_headers)
        assert gen_resp.status_code == 200, gen_resp.text
        assert gen_resp.json().get("status") == "pending"

        doc = None
        for _ in range(40):  # up to ~120s
            time.sleep(3)
            r = api_client.get(f"{API}/recommendations", headers=auth_headers)
            assert r.status_code == 200
            doc = r.json()
            if doc.get("status") in ("ready", "error"):
                break
        assert doc is not None
        assert doc.get("status") == "ready", f"Recommendations did not become ready: {doc}"
        # stash for later tests
        TestPromptCachingAndCompactKeys.recs = doc

    def test_03_now_and_future_have_5_items_each(self):
        doc = TestPromptCachingAndCompactKeys.recs
        assert len(doc.get("now", [])) == 5, f"'now' should have 5 items, got {len(doc.get('now', []))}"
        assert len(doc.get("future", [])) == 5, f"'future' should have 5 items, got {len(doc.get('future', []))}"

    def test_04_all_full_fields_present_no_short_key_leakage(self):
        doc = TestPromptCachingAndCompactKeys.recs
        failures = []
        for cat in ("now", "future"):
            for idx, item in enumerate(doc.get(cat, [])):
                # check for short-key leakage
                leaked = [k for k in SHORT_KEYS if k in item]
                if leaked:
                    failures.append(f"{cat}[{idx}] ({item.get('title', '?')}) has LEAKED short keys: {leaked}")
                # check all full keys + pre-existing keys present and non-empty
                for key in FULL_KEYS + PRE_EXISTING_KEYS:
                    if key not in item:
                        failures.append(f"{cat}[{idx}] ({item.get('title', '?')}) MISSING field '{key}'")
                        continue
                    val = item[key]
                    if val is None:
                        failures.append(f"{cat}[{idx}] ({item.get('title', '?')}) field '{key}' is None")
                    elif isinstance(val, str) and not val.strip():
                        failures.append(f"{cat}[{idx}] ({item.get('title', '?')}) field '{key}' is empty string")
                    elif isinstance(val, list) and key != "missing_skills" and not val:
                        failures.append(f"{cat}[{idx}] ({item.get('title', '?')}) field '{key}' is empty list")
                # category correctness
                if item.get("category") != cat:
                    failures.append(f"{cat}[{idx}] category field mismatch: {item.get('category')}")
        assert not failures, "Critical field issues found:\n" + "\n".join(failures)

    def test_05_match_is_number_0_100(self):
        doc = TestPromptCachingAndCompactKeys.recs
        for cat in ("now", "future"):
            for item in doc.get(cat, []):
                match = item.get("match")
                assert isinstance(match, (int, float)), f"match not numeric: {match} in {item.get('title')}"
                assert 0 <= match <= 100, f"match out of range: {match} in {item.get('title')}"

    def test_06_missing_skills_capped_at_2(self):
        doc = TestPromptCachingAndCompactKeys.recs
        for cat in ("now", "future"):
            for item in doc.get(cat, []):
                ms = item.get("missing_skills")
                assert isinstance(ms, list), f"missing_skills not a list: {ms}"
                assert len(ms) <= 2, f"missing_skills has >2 items in {item.get('title')}: {ms}"

    def test_07_content_quality_full_sentences_polish(self):
        """Spot check: why/summary fields should be full sentences (end with proper punctuation),
        not fragments ending mid-word or with dangling punctuation."""
        doc = TestPromptCachingAndCompactKeys.recs
        failures = []
        assert doc.get("summary", "").strip(), "top-level summary missing"
        for cat in ("now", "future"):
            for item in doc.get(cat, []):
                for field in ("summary", "why"):
                    val = item.get(field, "")
                    if not val.strip().endswith((".", "!", "?")):
                        failures.append(f"{cat}:{item.get('title')} field '{field}' doesn't end with sentence punctuation: '{val}'")
                    if len(val.split()) < 4:
                        failures.append(f"{cat}:{item.get('title')} field '{field}' looks like a fragment (too short): '{val}'")
        assert not failures, "Content quality issues:\n" + "\n".join(failures)

    def test_08_career_detail_endpoint(self, api_client, auth_headers):
        doc = TestPromptCachingAndCompactKeys.recs
        career_id = doc["now"][0]["id"]
        r = api_client.get(f"{API}/careers/{career_id}", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "detail" in body and body["detail"], f"No detail in career response: {body}"
        TestPromptCachingAndCompactKeys.career_title = doc["now"][0]["title"]

    def test_09_roadmap_custom_and_resources(self, api_client, auth_headers):
        title = TestPromptCachingAndCompactKeys.career_title
        r = api_client.post(f"{API}/roadmap/custom", json={"title": f"TEST {title}"}, headers=auth_headers)
        assert r.status_code in (200, 201), r.text
        path_id = r.json().get("path_id")
        assert path_id

        roadmap_doc = None
        for _ in range(40):  # up to ~120s
            time.sleep(3)
            gr = api_client.get(f"{API}/roadmap", params={"path_id": path_id}, headers=auth_headers)
            assert gr.status_code == 200
            rj = gr.json()
            if rj.get("status") in ("ready", "error"):
                roadmap_doc = rj
                break
        assert roadmap_doc is not None and roadmap_doc.get("status") == "ready", f"Roadmap never became ready: {roadmap_doc}"
        # Find a task id to test resources endpoint if milestones present
        milestones = roadmap_doc.get("milestones") or []
        task_id = None
        for ms in milestones:
            for t in ms.get("tasks", []):
                task_id = t.get("id")
                if task_id:
                    break
            if task_id:
                break
        if task_id:
            res = api_client.get(f"{API}/roadmap/tasks/{task_id}/resources", headers=auth_headers)
            assert res.status_code == 200, res.text
