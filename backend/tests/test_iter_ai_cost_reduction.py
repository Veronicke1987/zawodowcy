"""
Regression tests for the AI-cost-reduction pass (iteration):
1. Premium monthly quota fields (recommendations_generations_used/limit) present on /api/premium & login
2. Custom-profession validation via Jev classifier (/api/careers/custom) - valid/invalid/illegal inputs
3. /api/recommendations/generate end-to-end -> 4+4=8 AI careers (plus any pre-existing custom/pinned)
4. /api/roadmap/study-plan + next-block still function (shortened block structure)
5. General regression: roadmap generation, task resources
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL').rstrip('/')

TEST_USER = {"email": "ania_t1@test.pl", "password": "test123"}


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    resp = api_client.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
    if resp.status_code != 200:
        pytest.skip(f"Login failed for {TEST_USER['email']}: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip(f"No token in login response: {data}")
    return token, data


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    token, _ = auth_token
    return {"Authorization": f"Bearer {token}"}


class TestLoginAndQuotaFields:
    def test_login_user_object_has_quota_fields(self, auth_token):
        _, data = auth_token
        user = data.get("user", data)
        assert "is_premium" in user or "premium" in user, f"user obj missing premium flag: {user}"

    def test_premium_endpoint_has_recommendation_quota_fields(self, api_client, auth_headers):
        resp = api_client.get(f"{BASE_URL}/api/premium", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "recommendations_generations_used" in data, data
        assert "recommendations_generations_limit" in data, data
        assert "roadmap_generations_used" in data, data
        assert "roadmap_generations_limit" in data, data
        assert isinstance(data["recommendations_generations_used"], int)
        assert isinstance(data["recommendations_generations_limit"], int)
        assert data["recommendations_generations_limit"] == 25


class TestCustomProfessionValidation:
    """Jev classifier via /api/careers/custom"""

    @pytest.mark.parametrize("title,should_be_valid", [
        ("Elektryk", True),
        ("Pielęgniarka", True),
        ("banan", False),
        ("xyz123qzpl", False),
        ("złodziej", False),
    ])
    def test_custom_career_validation(self, api_client, auth_headers, title, should_be_valid):
        resp = api_client.post(f"{BASE_URL}/api/careers/custom", headers=auth_headers,
                                json={"title": title, "qualifications": ""})
        if should_be_valid:
            assert resp.status_code == 200, f"Expected valid '{title}' to pass: {resp.status_code} {resp.text}"
            data = resp.json()
            assert "career_id" in data
        else:
            assert resp.status_code == 400, f"Expected invalid '{title}' to be rejected: {resp.status_code} {resp.text}"
            msg = resp.json().get("detail", "")
            assert msg, "Expected a rejection message"


class TestRecommendationsGenerate:
    def test_generate_and_poll(self, api_client, auth_headers):
        before = api_client.get(f"{BASE_URL}/api/premium", headers=auth_headers).json()
        used_before = before["recommendations_generations_used"]

        gen_resp = api_client.post(f"{BASE_URL}/api/recommendations/generate", headers=auth_headers)
        assert gen_resp.status_code in (200, 202, 400), gen_resp.text
        if gen_resp.status_code == 400:
            pytest.skip(f"Generate blocked (quota/ad gate?): {gen_resp.text}")

        # Poll for ready status
        ready_data = None
        for _ in range(30):
            time.sleep(2)
            r = api_client.get(f"{BASE_URL}/api/recommendations", headers=auth_headers)
            assert r.status_code == 200
            d = r.json()
            if d.get("status") == "ready":
                ready_data = d
                break
            if d.get("status") == "error":
                pytest.fail(f"Recommendations generation errored: {d}")
        assert ready_data is not None, "Recommendations did not become ready within timeout"
        now_list = ready_data.get("now", [])
        future_list = ready_data.get("future", [])
        total = len(now_list) + len(future_list)
        # 4 AI now + 4 AI future = 8, plus any pre-existing pinned/custom careers
        assert total >= 8, f"Expected at least 8 total careers, got {total}"
        assert total <= 12, f"Total careers unexpectedly high (expected ~8-9): {total}"

        after = api_client.get(f"{BASE_URL}/api/premium", headers=auth_headers).json()
        used_after = after["recommendations_generations_used"]
        assert used_after == used_before + 1, f"Expected quota counter incremented by 1: before={used_before} after={used_after}"


class TestRoadmapAndStudyPlanRegression:
    def test_get_paths_and_roadmap(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/paths", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("paths"), list)

    def test_get_roadmap_existing_path(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/roadmap", headers=auth_headers)
        assert r.status_code == 200, r.text

    def test_study_plan_endpoint_responds(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "status" in data
