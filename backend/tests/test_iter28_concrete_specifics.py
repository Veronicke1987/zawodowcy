"""
Iteration 28 backend test: verify the "concrete, named specifics" prompt change in
server.py for career_detail (how_to_start), task_resources, and daily_item_resources.
Previously the user complained AI advice was too generic ("find a course"); the updated
prompts now require NAMED courses/platforms/urzad pracy programs (KFS, bon szkoleniowy, etc).

This is a qualitative/content-quality check — uses heuristics (named platform keywords,
quote-marked course names, specific urzad pracy program keywords) to judge whether output
reads as concrete vs generic, rather than a strict schema check.

End-to-end flow with a fresh TEST_ user:
  register -> PUT /api/profile -> POST /api/recommendations/generate (poll)
  -> GET /api/careers/{id} (fresh) -> inspect how_to_start
  -> POST /api/roadmap/custom (poll) -> GET /api/roadmap/tasks/{id}/resources (fresh+cached)
  -> daily-plan settings + GET (poll) -> find item WITHOUT milestone_task_id
     -> GET /api/roadmap/daily-plan/items/{id}/resources
"""
import os
import time
import uuid
import re

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

# Keywords/signals that indicate a NAMED, concrete platform/program (not exhaustive, heuristic)
PLATFORM_KEYWORDS = [
    "udemy", "coursera", "youtube", "linkedin learning", "kursera", "edx",
    "skillshare", "pracuj.pl", "e-petycje", "kurs", "szkolenie", "platform",
    "kanał", "channel", "akademi", "bootcamp",
]
URZAD_PRACY_PROGRAMS = ["kfs", "bon szkoleniowy", "bon na zasiedlenie", "staż", "dofinansowanie",
                         "krajowego funduszu szkoleniowego", "fundusz pracy", "bon"]
# Generic vague phrases that should NOT dominate (if content ONLY has these, it's a fail)
GENERIC_PHRASES = ["zrób kurs", "znajdź szkolenie", "weź udział w kursie", "skorzystaj ze szkolenia",
                    "zapisz się na kurs", "poszukaj kursu"]


def has_quoted_name(s: str) -> bool:
    """Detect named course/channel in Polish-style quotes » « or regular quotes."""
    return bool(re.search(r"[»«\"\u201e\u201c].{2,60}[»«\"\u201d\u201f]", s))


def has_named_specific(text_blob: str) -> bool:
    low = text_blob.lower()
    has_platform = any(k in low for k in PLATFORM_KEYWORDS)
    has_urzad = any(k in low for k in URZAD_PRACY_PROGRAMS)
    has_quote = has_quoted_name(text_blob)
    return has_platform or has_urzad or has_quote


def word_count(s: str) -> int:
    return len(s.split())


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_user(session):
    email = f"TEST_iter28_{uuid.uuid4().hex[:8]}@test.pl"
    payload = {"email": email, "password": "test123456", "name": "Iter28 Tester"}
    r = session.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token
    session.headers.update({"Authorization": f"Bearer {token}"})
    return {"email": email, "token": token}


@pytest.fixture(scope="module")
def profile_done(session, auth_user):
    answers = {
        "reset_mode": "search",
        "current_status": "Pracuję jako kasjerka, chcę zmienić branżę na kadry",
        "city": "Kraków",
        "learn_time": "5-10 godzin tygodniowo",
        "skills": ["Excel", "komunikacja z klientem", "organizacja pracy"],
        "loves": ["praca z dokumentami", "porządek i struktura"],
        "dislikes": ["praca fizyczna na zewnątrz"],
        "life_values": ["stabilność", "rozwój"],
        "education": "średnie",
    }
    r = session.put(f"{API}/profile", json={"answers": answers}, timeout=30)
    assert r.status_code == 200, r.text
    return answers


def poll_until_ready(session, url, timeout=60, interval=2):
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = session.get(url, timeout=30)
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("status") in ("ready", "error"):
            return last
        time.sleep(interval)
    raise TimeoutError(f"Polling timed out for {url}, last={last}")


class TestCareerDetailConcrete:
    def test_full_flow_to_career_detail(self, session, auth_user, profile_done):
        r = session.post(f"{API}/recommendations/generate", timeout=30)
        assert r.status_code == 200, r.text
        result = poll_until_ready(session, f"{API}/recommendations", timeout=60)
        assert result["status"] == "ready", result
        all_items = result["now"] + result["future"]
        assert len(all_items) >= 1
        career_id = all_items[0]["id"]

        r = session.get(f"{API}/careers/{career_id}", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        detail = data["detail"]
        how_to_start = detail["how_to_start"]
        assert isinstance(how_to_start, list) and len(how_to_start) >= 4

        print(f"\n[career_detail.how_to_start] for '{data['career']['title']}':")
        for i, step in enumerate(how_to_start):
            print(f"  {i+1}. {step}")

        concrete_count = sum(1 for s in how_to_start if has_named_specific(s))
        print(f"concrete/named items: {concrete_count}/{len(how_to_start)}")
        assert concrete_count >= 1, (
            f"NONE of the how_to_start items appear to name a specific course/platform/program: {how_to_start}"
        )
        TestCareerDetailConcrete.career_title = data["career"]["title"]


class TestTaskResourcesConcrete:
    def test_create_roadmap_and_poll(self, session):
        r = session.post(f"{API}/roadmap/custom", json={"title": "kadrowa", "qualifications": ""}, timeout=30)
        assert r.status_code == 200, r.text
        path_id = r.json()["path_id"]
        result = poll_until_ready(session, f"{API}/roadmap?path_id={path_id}", timeout=60)
        assert result["status"] == "ready", result
        milestones = result["milestones"]
        assert len(milestones) >= 1
        TestTaskResourcesConcrete.path_id = path_id
        TestTaskResourcesConcrete.milestones = milestones

        # Try to find a task with type course/studies/certificate, else fall back to first task
        chosen = None
        for m in milestones:
            for t in m["tasks"]:
                if t.get("type") in ("course", "studies", "certificate"):
                    chosen = t
                    break
            if chosen:
                break
        if not chosen:
            chosen = milestones[0]["tasks"][0]
        TestTaskResourcesConcrete.task = chosen
        print(f"\n[chosen task] title={chosen['title']} type={chosen.get('type')}")

    def test_fresh_resources_concrete(self, session):
        task = TestTaskResourcesConcrete.task
        t0 = time.time()
        r = session.get(f"{API}/roadmap/tasks/{task['id']}/resources", timeout=60)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("overview", "steps", "free_tips", "resources"):
            assert key in data

        print(f"\n[task_resources fresh] elapsed={elapsed:.2f}s")
        print(f"overview: {data['overview']}")
        print("steps:")
        for s in data["steps"]:
            print(f"  - {s}")
        print("free_tips:")
        for s in data["free_tips"]:
            print(f"  - {s}")
        print("resource titles:")
        for res in data["resources"]:
            print(f"  - [{res.get('type')}] {res.get('title')} (platform={res.get('platform')})")

        steps_concrete = sum(1 for s in data["steps"] if has_named_specific(s))
        tips_concrete = sum(1 for s in data["free_tips"] if has_named_specific(s))
        titles_nonempty = [res.get("title", "") for res in data["resources"]]
        titles_concrete = sum(1 for t in titles_nonempty if len(t.split()) >= 2 and not any(g in t.lower() for g in GENERIC_PHRASES))

        print(f"steps_concrete={steps_concrete}/{len(data['steps'])}, tips_concrete={tips_concrete}/{len(data['free_tips'])}, "
              f"titles_concrete={titles_concrete}/{len(titles_nonempty)}")

        assert steps_concrete >= 1, f"No steps appear concrete/named: {data['steps']}"
        assert tips_concrete >= 1, f"No free_tips appear concrete/named: {data['free_tips']}"
        assert titles_concrete >= 1, f"No resource titles appear concrete: {titles_nonempty}"

        for res in data["resources"]:
            assert res.get("url")

        TestTaskResourcesConcrete.data_first = data
        TestTaskResourcesConcrete.elapsed_fresh = elapsed

    def test_cached_resources_still_cached(self, session):
        task = TestTaskResourcesConcrete.task
        t0 = time.time()
        r = session.get(f"{API}/roadmap/tasks/{task['id']}/resources", timeout=30)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        print(f"[task_resources cached] elapsed={elapsed:.2f}s (fresh was {TestTaskResourcesConcrete.elapsed_fresh:.2f}s)")
        assert r.json() == TestTaskResourcesConcrete.data_first, "cached payload differs - caching may be broken"
        assert elapsed < TestTaskResourcesConcrete.elapsed_fresh or elapsed < 1.0


class TestDailyItemResourcesConcrete:
    def test_settings_and_get(self, session):
        path_id = TestTaskResourcesConcrete.path_id
        r = session.post(f"{API}/roadmap/daily-plan/settings", params={"path_id": path_id},
                          json={"free_days": [5, 6], "time_mode": "daily", "time_value": 30}, timeout=30)
        assert r.status_code == 200, r.text
        result = poll_until_ready(session, f"{API}/roadmap/daily-plan?path_id={path_id}", timeout=60)
        assert result.get("status") in ("ready", "none") or result.get("weeks"), result
        TestDailyItemResourcesConcrete.plan = result

    def test_item_without_milestone_task_resources_concrete(self, session):
        plan = TestDailyItemResourcesConcrete.plan
        weeks = plan.get("weeks") or []
        assert weeks, f"no weeks in daily plan: {plan}"
        no_task_item = None
        for w in weeks:
            for d in w.get("days", []):
                for it in d.get("items", []):
                    if not it.get("milestone_task_id"):
                        no_task_item = it
                        break
                if no_task_item:
                    break
            if no_task_item:
                break

        if not no_task_item:
            pytest.skip("No daily-plan item without milestone_task_id found to test generic daily_item_resources path")

        print(f"\n[daily item w/o milestone_task_id] title={no_task_item['title']}")
        r = session.get(f"{API}/roadmap/daily-plan/items/{no_task_item['id']}/resources", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("overview", "steps", "free_tips", "resources"):
            assert key in data

        print(f"overview: {data['overview']}")
        print("steps:")
        for s in data["steps"]:
            print(f"  - {s}")
        print("free_tips:")
        for s in data["free_tips"]:
            print(f"  - {s}")
        print("resource titles:")
        for res in data["resources"]:
            print(f"  - [{res.get('type')}] {res.get('title')} (platform={res.get('platform')})")

        steps_concrete = sum(1 for s in data["steps"] if has_named_specific(s))
        tips_concrete = sum(1 for s in data["free_tips"] if has_named_specific(s))
        assert steps_concrete >= 1 or tips_concrete >= 1, (
            f"Neither steps nor free_tips appear concrete/named: steps={data['steps']} tips={data['free_tips']}"
        )
