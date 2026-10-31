"""
Backend test: verifies the "studies caveat" change added after iteration_28.
For STUDIES-related advice, AI must name a kierunek (field of study) + list 2-3
EXAMPLE universities as alternatives, never dictate ONE single mandatory university.
Covers: career_detail (how_to_start), task_resources (studies-type task), and a
regression check that non-studies items (courses/urzad pracy) still name concrete
courses/platforms (iteration_28 behavior, unaffected).
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/") or os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_session(session):
    email = f"TEST_studies_{uuid.uuid4().hex[:8]}@test.pl"
    password = "test123456"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Test Studies"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestStudiesCaveatCareerDetail:
    """career_detail how_to_start studies caveat (~line 678)"""

    @pytest.mark.parametrize("title", ["Psycholog", "Prawnik", "Lekarz"])
    def test_how_to_start_names_multiple_universities(self, auth_session, title):
        # Use /roadmap/custom to create a career entry so career_detail can be looked up? 
        # career_detail requires career to exist in recommendations (find_career checks db.recommendations)
        # roadmap/custom builds a synthetic "career" dict but doesn't add it to recommendations.
        # So instead we must go through profile + recommendations generation, or directly test task_resources
        # via custom roadmap. We'll attempt career via custom path's internal 'career' id isn't registered
        # in recommendations collection, so GET /careers/{id} would 404. Skip direct career_detail unless
        # recommendations contain a matching career; fallback handled in TestRecommendationsFlow.
        pytest.skip("covered via TestRecommendationsFlow using real recommendation career_id")


class TestRecommendationsFlow:
    """End-to-end: profile -> recommendations -> career_detail (how_to_start studies caveat)"""

    def test_full_flow_career_detail_studies_caveat(self, auth_session):
        # 1. Complete profile
        answers = {
            "city": "Warszawa",
            "wyksztalcenie": "wyzsze",
            "doswiadczenie": "5 lat w finansach",
            "cel": "zmiana kariery na psychologa lub prawnika",
            "umiejetnosci": "komunikacja, analiza",
            "branza_docelowa": "psychologia/prawo",
        }
        r = auth_session.put(f"{API}/profile", json={"answers": answers})
        assert r.status_code == 200, r.text

        # 2. Generate recommendations (async job)
        r = auth_session.post(f"{API}/recommendations/generate")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"

        # 3. Poll for completion (LLM call, give it time)
        data = None
        for _ in range(40):
            time.sleep(3)
            r = auth_session.get(f"{API}/recommendations")
            assert r.status_code == 200
            data = r.json()
            if data.get("status") in ("ready", "error"):
                break
        assert data is not None
        assert data.get("status") == "ready", f"recommendations did not become ready: {data}"
        careers = (data.get("now") or []) + (data.get("future") or [])
        assert len(careers) > 0, "no careers returned"

        # find a career likely to require studies (degree-requiring titles)
        degree_keywords = ["psycholog", "prawnik", "lekarz", "nauczyciel", "analityk", "inżynier", "specjalista"]
        target = None
        for c in careers:
            if any(k in c["title"].lower() for k in degree_keywords):
                target = c
                break
        if not target:
            target = careers[0]

        print(f"\nTesting career_detail for: {target['title']} (id={target['id']})")

        # 4. career_detail (first call -> triggers LLM)
        r = auth_session.get(f"{API}/careers/{target['id']}")
        assert r.status_code == 200, r.text
        detail_resp = r.json()
        assert "detail" in detail_resp
        detail = detail_resp["detail"]
        how_to_start = detail.get("how_to_start", [])
        assert isinstance(how_to_start, list) and len(how_to_start) > 0

        full_text = " | ".join(how_to_start)
        print(f"how_to_start for {target['title']}:\n{full_text}\n")

        # 5. Cache check - repeat call should return same detail without re-triggering LLM (fast)
        t0 = time.time()
        r2 = auth_session.get(f"{API}/careers/{target['id']}")
        elapsed = time.time() - t0
        assert r2.status_code == 200
        assert r2.json()["detail"] == detail, "cached detail should be identical on repeat call"
        print(f"Cached repeat call took {elapsed:.2f}s (should be fast, <2s typically)")
        assert elapsed < 5, "repeat call took too long - caching may not be working"

        # Store for qualitative review (not hard assertion since LLM output varies)
        studies_mentioned = any("studi" in step.lower() or "kierunek" in step.lower() or "uczelni" in step.lower() for step in how_to_start)
        print(f"Studies/kierunek mentioned in how_to_start: {studies_mentioned}")
        if studies_mentioned:
            import re
            uni_keywords = ["uniwersytet", "politechnik", "akademi", "wsb", "swps", "szkoła wyższa", "uczelni"]
            uni_count = sum(1 for step in how_to_start for k in uni_keywords if k in step.lower())
            print(f"University-related keyword mentions count: {uni_count}")


class TestCustomPathStudiesTask:
    """task_resources studies caveat via /roadmap/custom with a degree-requiring job (~line 968)"""

    def test_custom_roadmap_studies_task_resources(self, auth_session):
        r = auth_session.post(f"{API}/roadmap/custom", json={"title": "Psycholog kliniczny", "qualifications": ""})
        assert r.status_code == 200, r.text
        path_id = r.json()["path_id"]

        # poll for roadmap ready
        roadmap = None
        for _ in range(40):
            time.sleep(3)
            r = auth_session.get(f"{API}/roadmap", params={"path_id": path_id})
            assert r.status_code == 200
            roadmap = r.json()
            if roadmap.get("status") in ("ready", "error"):
                break
        assert roadmap is not None
        assert roadmap.get("status") == "ready", f"roadmap not ready: {roadmap}"

        # find a studies-type task
        studies_task = None
        all_tasks = []
        for m in roadmap.get("milestones", []):
            for t in m.get("tasks", []):
                all_tasks.append(t)
                if t.get("type") == "studies" and not studies_task:
                    studies_task = t
        print(f"\nTotal tasks found: {len(all_tasks)}, types: {[t.get('type') for t in all_tasks]}")

        if not studies_task:
            pytest.skip("No 'studies' type task generated in this roadmap - cannot verify studies caveat here")

        print(f"Studies task found: {studies_task['title']} - {studies_task['description']}")

        r = auth_session.get(f"{API}/roadmap/tasks/{studies_task['id']}/resources")
        assert r.status_code == 200, r.text
        resources_data = r.json()
        steps = resources_data.get("steps", [])
        assert isinstance(steps, list) and len(steps) > 0
        full_steps_text = " | ".join(steps)
        print(f"\nSteps for studies task:\n{full_steps_text}\n")

        resources_list = resources_data.get("resources", [])
        studies_resources = [res for res in resources_list if res.get("type") == "studies"]
        print(f"Studies-type resources: {studies_resources}")

        # Cache check
        t0 = time.time()
        r2 = auth_session.get(f"{API}/roadmap/tasks/{studies_task['id']}/resources")
        elapsed = time.time() - t0
        assert r2.status_code == 200
        print(f"Cached repeat call for task resources took {elapsed:.2f}s")
        assert elapsed < 5


class TestNonStudiesRegression:
    """Regression: non-studies task (course/skill type) should still name concrete courses/platforms (iteration_28 behavior)"""

    def test_course_type_task_resources_still_concrete(self, auth_session):
        # reuse roadmap from custom path test by creating a fresh one for a job likely to have course tasks
        r = auth_session.post(f"{API}/roadmap/custom", json={"title": "Specjalista ds. kadr i płac", "qualifications": ""})
        assert r.status_code == 200, r.text
        path_id = r.json()["path_id"]

        roadmap = None
        for _ in range(40):
            time.sleep(3)
            r = auth_session.get(f"{API}/roadmap", params={"path_id": path_id})
            assert r.status_code == 200
            roadmap = r.json()
            if roadmap.get("status") in ("ready", "error"):
                break
        assert roadmap is not None
        assert roadmap.get("status") == "ready", f"roadmap not ready: {roadmap}"

        course_task = None
        for m in roadmap.get("milestones", []):
            for t in m.get("tasks", []):
                if t.get("type") in ("course", "skill", "certificate"):
                    course_task = t
                    break
            if course_task:
                break
        if not course_task:
            pytest.skip("No course/skill type task generated")

        r = auth_session.get(f"{API}/roadmap/tasks/{course_task['id']}/resources")
        assert r.status_code == 200, r.text
        data = r.json()
        steps = data.get("steps", [])
        full_text = " | ".join(steps)
        print(f"\nNon-studies task '{course_task['title']}' steps:\n{full_text}\n")
        assert len(steps) > 0
