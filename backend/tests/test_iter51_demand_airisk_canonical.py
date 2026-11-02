"""
Iteration 51: verify fix for demand/ai_risk hardcoded-Polish-word bug.
Backend prompt now requests canonical English tokens high|medium|low and
normalize_level() maps any stray word (Polish/German/Dutch) down to one of
exactly those 3 canonical lowercase tokens. Frontend then translates them.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = (os.environ.get('EXPO_BACKEND_URL') or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"

CANONICAL = {"high", "medium", "low"}


def register(country="DE"):
    email = f"TESTDEMAND_{uuid.uuid4().hex[:10]}@test.pl"
    payload = {"email": email, "password": "Test@123", "name": "Test User", "country": country}
    r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code == 201, r.text
    data = r.json()
    return data["access_token"], data["user"], email


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def poll_recommendations(token, timeout=150):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(f"{API}/recommendations", headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("status") == "ready":
            return last
        time.sleep(3)
    pytest.fail(f"recommendations not ready in {timeout}s; last={last}")


@pytest.mark.slow
class TestDemandAiRiskCanonicalTokens:
    def test_de_country_en_language_demand_ai_risk_canonical(self):
        token, user, email = register(country="DE")
        r = requests.patch(f"{API}/account/language", json={"language": "en"}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 200
        assert r.json()["ui_language"] == "en"

        answers = {
            "reset_mode": "search",
            "current_job": "Księgowa",
            "education": "wyższe ekonomiczne",
            "city": "Berlin",
        }
        r2 = requests.put(f"{API}/profile", json={"answers": answers}, headers=auth_headers(token), timeout=30)
        assert r2.status_code == 200, r2.text

        r3 = requests.post(f"{API}/recommendations/generate", headers=auth_headers(token), timeout=30)
        assert r3.status_code in (200, 201, 202), r3.text

        data = poll_recommendations(token)
        now_list = data.get("now") or []
        future_list = data.get("future") or []
        all_careers = now_list + future_list
        assert len(all_careers) > 0, f"no careers returned: {data}"

        for career in all_careers:
            demand = career.get("demand")
            ai_risk = career.get("ai_risk")
            assert demand in CANONICAL, f"demand not canonical: {demand!r} in career {career.get('title')}"
            assert ai_risk in CANONICAL, f"ai_risk not canonical: {ai_risk!r} in career {career.get('title')}"
