# Tests for new feature: POST /api/roadmap/custom - lets a user skip the quiz and
# type a job title (+ optional qualifications) directly to get an AI-generated roadmap.
# Covers: happy path (with/without qualifications), duplicate-title reactivation,
# 422 validation on short title, and 403 at PREMIUM_PATH_LIMIT.
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")


@pytest.fixture(scope="module")
def fresh_client():
    """test_ui_fresh@test.pl has 0 roadmap paths at start of this module."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": "test_ui_fresh@test.pl", "password": "test123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    yield s
    # cleanup: delete all TEST_ custom paths created by this module
    paths = s.get(f"{BASE_URL}/api/paths").json().get("paths", [])
    for p in paths:
        if p["title"].startswith("TEST_"):
            s.delete(f"{BASE_URL}/api/paths/{p['path_id']}")


def poll_ready(session, path_id, timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        r = session.get(f"{BASE_URL}/api/roadmap", params={"path_id": path_id})
        assert r.status_code == 200
        data = r.json()
        if data.get("status") in ("ready", "error"):
            return data
        time.sleep(3)
    pytest.fail(f"roadmap {path_id} did not finish in {timeout}s")


class TestCustomPathHappyPath:
    def test_create_without_qualifications(self, fresh_client):
        r = fresh_client.post(f"{BASE_URL}/api/roadmap/custom", json={"title": "TEST_Grafik komputerowy", "qualifications": ""})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "pending"
        assert "path_id" in data and len(data["path_id"]) > 0
        ready = poll_ready(fresh_client, data["path_id"])
        assert ready["status"] == "ready", f"roadmap errored: {ready}"
        milestones = ready.get("milestones", [])
        assert len(milestones) >= 2, "expected several milestones"
        for m in milestones:
            assert m.get("title")
            assert isinstance(m.get("tasks"), list) and len(m["tasks"]) >= 1
        all_titles = " ".join(m["title"] for m in milestones).lower()
        assert "grafik" in all_titles or "projekt" in all_titles or "junior" in all_titles, \
            f"milestones don't look relevant to the typed position: {all_titles}"

    def test_create_with_qualifications(self, fresh_client):
        r = fresh_client.post(
            f"{BASE_URL}/api/roadmap/custom",
            json={"title": "TEST_Projektant UX", "qualifications": "Ukończony kurs Figma, 1 rok jako grafik"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "pending"
        ready = poll_ready(fresh_client, data["path_id"])
        assert ready["status"] == "ready", f"roadmap errored: {ready}"
        assert len(ready.get("milestones", [])) >= 2


class TestCustomPathDuplicateAndValidation:
    def test_duplicate_title_case_insensitive_reactivates(self, fresh_client):
        # module-level test depends on TestCustomPathHappyPath having run first (pytest preserves file order)
        r = fresh_client.post(f"{BASE_URL}/api/roadmap/custom", json={"title": "test_grafik komputerowy", "qualifications": ""})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("existing") is True
        # verify it reactivated the SAME path (not a new one) by checking /api/paths count unchanged
        paths = fresh_client.get(f"{BASE_URL}/api/paths").json()["paths"]
        titles = [p["title"] for p in paths]
        assert titles.count("TEST_Grafik komputerowy") == 1, "duplicate created a second path instead of reactivating"
        active = [p for p in paths if p["active"]]
        assert active and active[0]["path_id"] == data["path_id"]

    @pytest.mark.parametrize("title", ["", "a", " "])
    def test_title_too_short_returns_422(self, fresh_client, title):
        r = fresh_client.post(f"{BASE_URL}/api/roadmap/custom", json={"title": title})
        assert r.status_code == 422, f"expected 422 for title={title!r}, got {r.status_code}: {r.text}"


class TestCustomPathLimit:
    def test_hit_premium_limit_returns_403(self, fresh_client):
        # by now fresh_client has 2 distinct paths (Grafik, Projektant UX). Add a 3rd to hit limit=3.
        paths_before = fresh_client.get(f"{BASE_URL}/api/paths").json()["paths"]
        assert len(paths_before) == 2, f"expected 2 existing paths before this test, got {len(paths_before)}: {paths_before}"

        r = fresh_client.post(f"{BASE_URL}/api/roadmap/custom", json={"title": "TEST_Kurier rowerowy", "qualifications": ""})
        assert r.status_code == 200, r.text
        third = r.json()
        poll_ready(fresh_client, third["path_id"])

        # 4th distinct title should now 403
        r2 = fresh_client.post(f"{BASE_URL}/api/roadmap/custom", json={"title": "TEST_Weterynarz", "qualifications": ""})
        assert r2.status_code == 403, r2.text
        assert "3" in r2.text or "Premium" in r2.text or "ścież" in r2.text.lower()
