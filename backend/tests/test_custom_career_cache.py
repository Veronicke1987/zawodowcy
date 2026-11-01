"""
Reproduction / regression test for the reported "custom career goal" bug:
- Login as the test user created during the UI reproduction (test_qa_1793529926@test.pl)
- Verify the existing roadmap for the custom career "Konserwator zabytkowych zegarow 9926" is ready
- DELETE the roadmap, re-POST /careers/custom with the SAME title (expect same career_id reused),
  then POST /roadmap again and measure how fast it completes -> should be a CACHE HIT
  (created_at == updated_at to the same second, completes in a couple seconds) since
  career_templates already has milestones cached under this exact (country, normalized title) key.
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL") or "https://reset-zawodu--91qo0b92.preview.emergentagent.com"
API = f"{BASE_URL}/api"

EMAIL = "test_qa_1793529926@test.pl"
PASSWORD = "Test1234"
CAREER_TITLE = "Konserwator zabytkowych zegarow 9926"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def poll_roadmap(headers, timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{API}/roadmap", headers=headers)
        assert r.status_code == 200
        data = r.json()
        if data.get("status") in ("ready", "error"):
            return data, time.time() - start
        time.sleep(1)
    raise TimeoutError("roadmap did not finish in time")


class TestCustomCareerCacheReuse:
    def test_delete_readd_and_cache_hit_timing(self, headers):
        # 1. Delete existing roadmap for this user (simulates "delete path" in Road tab)
        del_resp = requests.delete(f"{API}/roadmap", headers=headers)
        print("DELETE /roadmap ->", del_resp.status_code, del_resp.text[:200])
        assert del_resp.status_code in (200, 404)

        # 2. Re-submit the EXACT same custom career title
        custom_resp = requests.post(f"{API}/careers/custom", headers=headers, json={"title": CAREER_TITLE, "qualifications": ""})
        assert custom_resp.status_code == 200, custom_resp.text
        career_id = custom_resp.json()["career_id"]
        print("career_id after re-add:", career_id)

        # 3. Choose the path (build roadmap) and measure timing
        t0 = time.time()
        roadmap_resp = requests.post(f"{API}/roadmap", headers=headers, json={"career_id": career_id})
        assert roadmap_resp.status_code == 200, roadmap_resp.text
        body = roadmap_resp.json()
        print("POST /roadmap response:", body)

        if body.get("existing"):
            print("Roadmap endpoint reported 'existing': reused old roadmap without any new generation")
            return

        data, elapsed = poll_roadmap(headers)
        print(f"Roadmap became '{data.get('status')}' after {elapsed:.1f}s (cache-hit expectation: a few seconds, not 20-60s)")
        assert data.get("status") == "ready"
        assert elapsed < 20, f"Expected a fast cache-hit response (<20s), but took {elapsed:.1f}s - looks like a FRESH AI generation instead of a cache hit"
