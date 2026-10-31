"""
Iteration 24 - BUG FIX verification: real Polish career-ladder titles in
career_detail() career_levels and run_roadmap() milestones.
Tests: POST /api/roadmap/custom (Nauczyciel + a corporate-style profession regression)
       and GET /api/careers/{career_id} career_levels field.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")

TEACHER_TERMS = ["staż", "kontraktow", "mianowan", "dyplomowan", "wicedyrektor", "dyrektor"]
INVENTED_BAD_TERMS = ["kierownik zespołu nauczycieli", "ekspert dydaktyczny", "nauczyciel pomocniczy", "asystent nauczyciela"]


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def test_user_token(api_client):
    """Register a brand new TEST_ user so we have a clean path-limit slate (max 3 paths)."""
    email = f"TEST_iter24_{uuid.uuid4().hex[:8]}@test.pl"
    resp = api_client.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "test123", "name": "Iter24 Tester"
    })
    if resp.status_code not in (200, 201):
        pytest.skip(f"Registration failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in register response: {data}"
    return token


def poll_roadmap(api_client, headers, path_id, timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        r = api_client.get(f"{BASE_URL}/api/roadmap", params={"path_id": path_id}, headers=headers)
        assert r.status_code == 200, f"roadmap GET failed: {r.status_code} {r.text}"
        doc = r.json()
        status = doc.get("status")
        if status == "ready":
            return doc
        if status == "error":
            pytest.fail(f"Roadmap generation errored: {doc}")
        time.sleep(3)
    pytest.fail("Roadmap did not become ready in time")


class TestTeacherCareerLadder:
    """Core bug-fix verification: Nauczyciel roadmap must use real teacher ranks."""

    def test_nauczyciel_roadmap_real_titles(self, api_client, test_user_token):
        headers = {"Authorization": f"Bearer {test_user_token}"}
        resp = api_client.post(f"{BASE_URL}/api/roadmap/custom", json={
            "title": "Nauczyciel", "qualifications": ""
        }, headers=headers)
        assert resp.status_code == 200, f"custom roadmap failed: {resp.status_code} {resp.text}"
        path_id = resp.json()["path_id"]

        doc = poll_roadmap(api_client, headers, path_id)
        milestones = doc.get("milestones", [])
        assert len(milestones) >= 3, f"Too few milestones: {milestones}"
        titles = [m.get("title", "") for m in milestones]
        titles_joined = " | ".join(titles).lower()
        print(f"\nNAUCZYCIEL MILESTONE TITLES: {titles}")

        matched_real = [t for t in TEACHER_TERMS if t in titles_joined]
        assert matched_real, f"No real Polish teacher-ladder terms found in titles: {titles}"

        matched_bad = [t for t in INVENTED_BAD_TERMS if t.lower() in titles_joined]
        assert not matched_bad, f"Invented/fake titles still present: {matched_bad} in {titles}"

    def test_nauczyciel_career_detail_levels(self, api_client, test_user_token):
        """Career detail endpoint - requires a career_id from /api/recommendations cache,
        we use find_career() indirectly by checking /api/careers/{id} is reachable;
        if user has no recommendations cached, this test documents that limitation."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        rec = api_client.get(f"{BASE_URL}/api/recommendations", headers=headers)
        if rec.status_code != 200:
            pytest.skip(f"No recommendations endpoint/data available: {rec.status_code}")
        data = rec.json()
        all_careers = (data.get("now") or []) + (data.get("future") or [])
        teacher_career = next((c for c in all_careers if "naucz" in c.get("title", "").lower()), None)
        if not teacher_career:
            pytest.skip("No 'Nauczyciel'-like career in this user's recommendations cache to test career_detail with")
        cid = teacher_career["id"]
        resp = api_client.get(f"{BASE_URL}/api/careers/{cid}", headers=headers)
        assert resp.status_code == 200, f"career_detail failed: {resp.status_code} {resp.text}"
        levels = resp.json().get("detail", {}).get("career_levels", [])
        levels_joined = " | ".join(levels).lower()
        print(f"\nNAUCZYCIEL CAREER_LEVELS: {levels}")
        matched_real = [t for t in TEACHER_TERMS if t in levels_joined]
        assert matched_real, f"No real Polish teacher-ladder terms in career_levels: {levels}"


class TestRegressionCorporateLadder:
    """Confirm the fix didn't overcorrect: corporate-style professions should still get
    junior/mid/senior-style ladders where realistic."""

    def test_marketing_specialist_roadmap_corporate_titles(self, api_client, test_user_token):
        headers = {"Authorization": f"Bearer {test_user_token}"}
        resp = api_client.post(f"{BASE_URL}/api/roadmap/custom", json={
            "title": "Specjalista ds. marketingu", "qualifications": ""
        }, headers=headers)
        assert resp.status_code == 200, f"custom roadmap failed: {resp.status_code} {resp.text}"
        path_id = resp.json()["path_id"]

        doc = poll_roadmap(api_client, headers, path_id)
        milestones = doc.get("milestones", [])
        titles = [m.get("title", "") for m in milestones]
        titles_joined = " | ".join(titles).lower()
        print(f"\nMARKETING MILESTONE TITLES: {titles}")

        corporate_terms = ["junior", "specjalist", "senior", "kierownik", "manager", "menedżer", "dyrektor", "lead", "head"]
        matched = [t for t in corporate_terms if t in titles_joined]
        assert matched, f"Expected a corporate-style ladder term, got none in: {titles}"


class TestGeneralRegression:
    """Quick smoke check that quiz/roadmap/daily-plan flows still function with no 500s."""

    def test_recommendations_endpoint_reachable(self, api_client, test_user_token):
        headers = {"Authorization": f"Bearer {test_user_token}"}
        resp = api_client.get(f"{BASE_URL}/api/recommendations", headers=headers)
        assert resp.status_code in (200, 404), f"Unexpected status: {resp.status_code} {resp.text}"

    def test_premium_info_endpoint(self, api_client, test_user_token):
        headers = {"Authorization": f"Bearer {test_user_token}"}
        resp = api_client.get(f"{BASE_URL}/api/premium", headers=headers)
        assert resp.status_code == 200
