"""
Iteration 41 regression test: custom career race condition fix.
Simulates: register -> quiz (triggers background run_recommendations) -> IMMEDIATELY
add custom career -> wait for recommendations to become ready -> assert custom career
still present in recommendations.now (was previously wiped by the background job's $set).
"""
import os
import random
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def test_custom_career_survives_recommendations_race(api_client):
    assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"
    rand = random.randint(100000, 999999)
    email = f"TEST_qa_race_{rand}@test.pl"
    password = "Test1234"

    # Register
    r = api_client.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": password, "country": "PL"})
    assert r.status_code in (200, 201), r.text
    token = r.json().get("token") or r.json().get("access_token")
    if not token:
        # maybe login required separately
        r2 = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
        assert r2.status_code == 200, r2.text
        token = r2.json().get("token") or r2.json().get("access_token")
    assert token, "No token returned from register/login"
    api_client.headers.update({"Authorization": f"Bearer {token}"})

    # Minimal profile/quiz answers - adjust keys loosely, try common endpoint
    answers = {"interests": ["technology"], "skills": ["analytical"], "education": "wyzsze", "experience": "brak"}
    r = api_client.put(f"{BASE_URL}/api/profile", json={"answers": answers})
    assert r.status_code in (200, 201), r.text

    r = api_client.post(f"{BASE_URL}/api/recommendations/generate", json={})
    assert r.status_code in (200, 201), r.text

    # IMMEDIATELY add custom career while job likely still pending
    # Use a realistic job-title-like string (with random suffix) so the LLM profession
    # validator (validate_profession) doesn't reject it as nonsense text.
    custom_title = f"Inzynier QA Race Test {rand}"
    r = api_client.post(f"{BASE_URL}/api/careers/custom", json={"title": custom_title, "qualifications": ""})
    assert r.status_code in (200, 201), r.text
    custom_id = r.json().get("id") or r.json().get("career_id")

    # Poll recommendations until ready (max 90s)
    status = None
    for _ in range(45):
        r = api_client.get(f"{BASE_URL}/api/recommendations")
        assert r.status_code == 200, r.text
        data = r.json()
        status = data.get("status")
        if status == "ready":
            break
        time.sleep(2)

    assert status == "ready", f"recommendations never became ready, last status={status}"

    now_titles = [c.get("title") for c in data.get("now", [])]
    assert custom_title in now_titles, f"BUG: custom career wiped out by race condition. now_titles={now_titles}"
    print(f"PASS: custom career '{custom_title}' survived the race. now has {len(now_titles)} careers.")
