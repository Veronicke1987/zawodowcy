"""
Content-richness regression test: verifies that profile `summary` (run_recommendations),
career_detail `description`/`how_to_start`, and task_resources `overview`/`steps` are
genuinely long multi-sentence paragraphs after the "nie licz się ze słowami" prompt changes
(word caps removed). Uses real OpenAI gpt-4.1-mini (no mocks).
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/") or os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ANSWERS = {
    "reset_mode": "search",
    "personality": {"extro_intro": 60, "team_solo": 40, "routine_variety": 70, "risk_safety": 30},
    "current_job": "Sprzedawca w sklepie odzieżowym",
    "skills": ["Obsluga klienta", "Kasa fiskalna", "Excel podstawy"],
    "likes": ["Praca z ludzmi", "Organizacja"],
    "dislikes": ["Praca fizyczna ciezka"],
    "city": "Warszawa",
    "education": "Srednie",
}


@pytest.fixture(scope="module")
def auth_session():
    session = requests.Session()
    email = f"TEST_content_{int(time.time())}@test.pl"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "Content Test"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return session


def _sentence_count(text: str) -> int:
    return len([s for s in text.replace("...", ".").split(".") if s.strip()])


class TestRecommendationsRichness:
    def test_profile_summary_is_long_and_multi_sentence(self, auth_session):
        r = auth_session.put(f"{API}/profile", json={"answers": ANSWERS})
        assert r.status_code == 200, r.text

        r = auth_session.post(f"{API}/recommendations/generate")
        assert r.status_code == 200, r.text

        data = None
        for _ in range(40):
            time.sleep(3)
            r = auth_session.get(f"{API}/recommendations")
            data = r.json()
            if data.get("status") in ("ready", "error"):
                break
        assert data is not None and data.get("status") == "ready", f"recommendations did not finish: {data}"

        summary = data.get("summary", "")
        print(f"\n--- profile summary ({len(summary)} chars, {_sentence_count(summary)} sentences) ---\n{summary}\n")
        assert len(summary) > 250, f"summary too short ({len(summary)} chars): {summary}"
        assert _sentence_count(summary) >= 4, f"summary has too few sentences: {summary}"

        now_items = data.get("now", [])
        assert len(now_items) >= 1
        career = now_items[0]
        assert len(career.get("summary", "")) > 100, career.get("summary")
        assert len(career.get("why", "")) > 100, career.get("why")
        print(f"--- career[0] summary: {career['summary']}\n--- career[0] why: {career['why']}")

        auth_session.career_id = career["id"]  # stash for next test class

    def test_career_detail_richness(self, auth_session):
        r = auth_session.get(f"{API}/recommendations")
        data = r.json()
        career_id = data["now"][0]["id"]
        r = auth_session.get(f"{API}/careers/{career_id}")
        assert r.status_code == 200, r.text
        detail = r.json()["detail"]
        description = detail.get("description", "")
        print(f"\n--- career_detail.description ({len(description)} chars, {_sentence_count(description)} sentences) ---\n{description}\n")
        assert len(description) > 250, f"description too short: {description}"
        assert _sentence_count(description) >= 4

        how_to_start = detail.get("how_to_start", [])
        assert len(how_to_start) >= 4
        avg_len = sum(len(x) for x in how_to_start) / len(how_to_start)
        print(f"--- how_to_start avg item length: {avg_len:.0f} chars; sample: {how_to_start[0]}")
        assert avg_len > 60, f"how_to_start items too short on average: {avg_len}"
