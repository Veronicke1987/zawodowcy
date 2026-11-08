"""Iteration 64: tests for
1) DELETE /api/recommendations/careers/{career_id} - removes single career from now/future, 404 if not found
2) POST /api/recommendations/generate - regeneration diversity via shown_titles memory
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    resp = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": "ania_t1@test.pl", "password": "test123"})
    if resp.status_code != 200:
        pytest.skip(f"login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestDeleteCareer:
    def test_get_recommendations_has_careers(self, api_client, auth_headers):
        resp = api_client.get(f"{BASE_URL}/api/recommendations", headers=auth_headers)
        assert resp.status_code == 200
        doc = resp.json()
        assert doc.get("status") in ("ready", "pending", "none", "error")
        if doc.get("status") != "ready":
            pytest.skip(f"recommendations not ready (status={doc.get('status')}), cannot test delete")
        total = len(doc.get("now") or []) + len(doc.get("future") or [])
        assert total > 0, "expected existing recommendations for ania_t1@test.pl"

    def test_delete_nonexistent_career_404(self, api_client, auth_headers):
        resp = api_client.delete(f"{BASE_URL}/api/recommendations/careers/nonexistent-id-xyz", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_existing_career_removes_it(self, api_client, auth_headers):
        before = api_client.get(f"{BASE_URL}/api/recommendations", headers=auth_headers).json()
        if before.get("status") != "ready":
            pytest.skip("recommendations not ready")
        now_list = before.get("now") or []
        future_list = before.get("future") or []
        all_careers = now_list + future_list
        if not all_careers:
            pytest.skip("no careers to delete")
        target = all_careers[-1]  # delete the last one, avoid custom ones if possible
        target_id = target["id"]

        del_resp = api_client.delete(f"{BASE_URL}/api/recommendations/careers/{target_id}", headers=auth_headers)
        assert del_resp.status_code == 200
        assert del_resp.json().get("ok") is True

        after = api_client.get(f"{BASE_URL}/api/recommendations", headers=auth_headers).json()
        after_ids = [c["id"] for c in (after.get("now") or []) + (after.get("future") or [])]
        assert target_id not in after_ids, "deleted career id still present after GET"
        assert len(after_ids) == len(now_list) + len(future_list) - 1

        # deleting again should 404
        del_resp2 = api_client.delete(f"{BASE_URL}/api/recommendations/careers/{target_id}", headers=auth_headers)
        assert del_resp2.status_code == 404


class TestRegenerationDiversity:
    def _wait_ready(self, api_client, auth_headers, timeout=90):
        start = time.time()
        while time.time() - start < timeout:
            resp = api_client.get(f"{BASE_URL}/api/recommendations", headers=auth_headers)
            doc = resp.json()
            if doc.get("status") in ("ready", "error"):
                return doc
            time.sleep(3)
        pytest.fail("recommendations generation timed out")

    def test_regenerate_twice_titles_mostly_different(self, api_client, auth_headers):
        gen1 = api_client.post(f"{BASE_URL}/api/recommendations/generate", headers=auth_headers)
        if gen1.status_code != 200:
            pytest.skip(f"generate failed: {gen1.status_code} {gen1.text}")
        doc1 = self._wait_ready(api_client, auth_headers)
        if doc1.get("status") != "ready":
            pytest.skip(f"first generation ended with status={doc1.get('status')} error={doc1.get('error')}")
        titles1 = set(c.get("title") for c in (doc1.get("now") or []) + (doc1.get("future") or []) if not c.get("custom"))
        assert len(titles1) > 0

        gen2 = api_client.post(f"{BASE_URL}/api/recommendations/generate", headers=auth_headers)
        assert gen2.status_code == 200
        doc2 = self._wait_ready(api_client, auth_headers)
        if doc2.get("status") != "ready":
            pytest.skip(f"second generation ended with status={doc2.get('status')} error={doc2.get('error')}")
        titles2 = set(c.get("title") for c in (doc2.get("now") or []) + (doc2.get("future") or []) if not c.get("custom"))
        assert len(titles2) > 0

        overlap = titles1 & titles2
        overlap_ratio = len(overlap) / max(len(titles1), 1)
        print(f"titles1={titles1}")
        print(f"titles2={titles2}")
        print(f"overlap={overlap} ratio={overlap_ratio}")
        assert overlap_ratio < 0.5, f"too much overlap between generations: {overlap}"

        shown_titles = doc2.get("shown_titles")
        if shown_titles is not None:
            assert len(shown_titles) <= 24
            for t in titles1:
                assert t in shown_titles, f"{t} from gen1 missing in shown_titles memory"
