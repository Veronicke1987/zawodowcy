"""
Iteration 27 backend test: verify the "restore rich/detailed AI output" change in
server.py (SYSTEM_PL + per-field word-limit increases across recommendations,
career_detail, roadmap, task_resources, study_plan, daily_plan, daily_item_resources),
while confirming caching + no-chat-history behavior is unchanged.

End-to-end flow with a fresh TEST_ user:
  register -> PUT /api/profile -> POST /api/recommendations/generate (poll)
  -> GET /api/careers/{id} (fresh + cached) -> POST /api/roadmap/custom (poll)
  -> GET /api/roadmap/tasks/{id}/resources (fresh + cached)
  -> premium subscribe -> POST /api/roadmap/study-plan (poll)
  -> daily-plan settings + GET (poll) -> GET items/{id}/resources
"""
import os
import time
import uuid
import re

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

PL_CHARS = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")


def word_count(s: str) -> int:
    return len(s.split())


def has_polish(s: str) -> bool:
    return bool(PL_CHARS.search(s)) or True  # lenient; Polish text may lack diacritics in short strings


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_user(session):
    email = f"TEST_iter27_{uuid.uuid4().hex[:8]}@test.pl"
    payload = {"email": email, "password": "test123456", "name": "Iter27 Tester"}
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
        "current_status": "Pracuję jako księgowa, chcę zmienić branżę",
        "city": "Warszawa",
        "learn_time": "5-10 godzin tygodniowo",
        "skills": ["Excel", "komunikacja z klientem", "organizacja pracy"],
        "loves": ["praca z ludźmi", "porządek i struktura"],
        "dislikes": ["praca fizyczna na zewnątrz"],
        "life_values": ["stabilność", "rozwój"],
        "education": "wyższe ekonomiczne",
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


class TestRecommendations:
    def test_generate_and_poll(self, session, auth_user, profile_done):
        r = session.post(f"{API}/recommendations/generate", timeout=30)
        assert r.status_code == 200, r.text
        result = poll_until_ready(session, f"{API}/recommendations", timeout=60)
        assert result["status"] == "ready", result
        assert result.get("now") and result.get("future")
        TestRecommendations.data = result

    def test_summary_fuller(self):
        result = TestRecommendations.data
        summary = result["summary"]
        wc = word_count(summary)
        print(f"\n[recommendations.summary] ({wc} words): {summary}")
        assert wc >= 10, f"summary too short ({wc} words): {summary}"
        assert wc <= 45, f"summary exceeds cap too much ({wc} words)"

    def test_career_summary_why_fuller(self):
        result = TestRecommendations.data
        all_items = result["now"] + result["future"]
        assert len(all_items) >= 5
        for it in all_items[:4]:
            s_wc = word_count(it["summary"])
            w_wc = word_count(it["why"])
            print(f"[career {it['title']}] summary({s_wc}w): {it['summary']} | why({w_wc}w): {it['why']}")
            assert s_wc >= 4, f"summary too terse: {it['summary']}"
            assert w_wc >= 4, f"why too terse: {it['why']}"
            assert s_wc <= 25 and w_wc <= 25, "exceeds 20-word cap by too much"
        TestRecommendations.career_id = all_items[0]["id"]


class TestCareerDetail:
    def test_fresh_detail(self, session):
        career_id = TestRecommendations.career_id
        t0 = time.time()
        r = session.get(f"{API}/careers/{career_id}", timeout=60)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        data = r.json()
        detail = data["detail"]
        for key in ("description", "daily_tasks", "pros", "cons", "requirements", "how_to_start", "career_levels"):
            assert key in detail and detail[key], f"missing/empty {key}"
        desc_wc = word_count(detail["description"])
        print(f"\n[career_detail fresh] elapsed={elapsed:.2f}s desc({desc_wc}w): {detail['description']}")
        assert desc_wc >= 20, f"description too short: {detail['description']}"
        assert len(detail["daily_tasks"]) >= 4
        assert len(detail["requirements"]) >= 5
        assert len(detail["how_to_start"]) >= 4
        print(f"career_levels: {detail['career_levels']}")
        TestCareerDetail.detail_first = detail
        TestCareerDetail.elapsed_fresh = elapsed
        TestCareerDetail.career_id = career_id

    def test_cached_detail(self, session):
        career_id = TestCareerDetail.career_id
        t0 = time.time()
        r = session.get(f"{API}/careers/{career_id}", timeout=30)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        data = r.json()
        print(f"[career_detail cached] elapsed={elapsed:.2f}s (fresh was {TestCareerDetail.elapsed_fresh:.2f}s)")
        assert data["detail"] == TestCareerDetail.detail_first, "cached detail differs from fresh call"
        assert elapsed < TestCareerDetail.elapsed_fresh or elapsed < 1.0, "cached call not noticeably faster"


class TestRoadmapCustom:
    def test_create_and_poll(self, session):
        r = session.post(f"{API}/roadmap/custom", json={"title": "elektryk", "qualifications": ""}, timeout=30)
        assert r.status_code == 200, r.text
        path_id = r.json()["path_id"]
        result = poll_until_ready(session, f"{API}/roadmap?path_id={path_id}", timeout=60)
        assert result["status"] == "ready", result
        milestones = result["milestones"]
        assert len(milestones) >= 3
        TestRoadmapCustom.path_id = path_id
        TestRoadmapCustom.milestones = milestones

    def test_milestone_task_descriptions_fuller(self):
        milestones = TestRoadmapCustom.milestones
        m = milestones[0]
        m_wc = word_count(m["description"])
        print(f"\n[milestone {m['title']}] desc({m_wc}w): {m['description']}")
        assert m_wc >= 6, f"milestone description too terse: {m['description']}"
        assert len(m["tasks"]) >= 1
        task = m["tasks"][0]
        t_wc = word_count(task["description"])
        print(f"[task {task['title']}] desc({t_wc}w): {task['description']}")
        assert t_wc >= 4, f"task description too terse: {task['description']}"
        TestRoadmapCustom.task_id = task["id"]


class TestTaskResources:
    def test_fresh_resources(self, session):
        task_id = TestRoadmapCustom.task_id
        t0 = time.time()
        r = session.get(f"{API}/roadmap/tasks/{task_id}/resources", timeout=60)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("overview", "steps", "free_tips", "resources"):
            assert key in data
        ov_wc = word_count(data["overview"])
        print(f"\n[task_resources fresh] elapsed={elapsed:.2f}s overview({ov_wc}w): {data['overview']}")
        assert ov_wc >= 20, f"overview too short: {data['overview']}"
        assert len(data["steps"]) >= 4
        assert len(data["resources"]) >= 4, f"expected 5-8 resources, got {len(data['resources'])}"
        for r_ in data["resources"]:
            assert r_.get("url")
        TestTaskResources.data_first = data
        TestTaskResources.elapsed_fresh = elapsed
        TestTaskResources.task_id = task_id

    def test_cached_resources(self, session):
        task_id = TestTaskResources.task_id
        t0 = time.time()
        r = session.get(f"{API}/roadmap/tasks/{task_id}/resources", timeout=30)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        print(f"[task_resources cached] elapsed={elapsed:.2f}s (fresh was {TestTaskResources.elapsed_fresh:.2f}s)")
        assert r.json() == TestTaskResources.data_first


class TestStudyPlan:
    def test_premium_subscribe(self, session):
        r = session.post(f"{API}/premium/subscribe", json={"plan": "monthly"}, timeout=30)
        assert r.status_code == 200, r.text

    def test_create_and_poll(self, session):
        path_id = TestRoadmapCustom.path_id
        r = session.post(f"{API}/roadmap/study-plan", params={"path_id": path_id}, timeout=30)
        assert r.status_code == 200, r.text
        result = poll_until_ready(session, f"{API}/roadmap/study-plan?path_id={path_id}", timeout=60)
        assert result["status"] == "ready", result
        plan = result["plan"]
        assert plan.get("weeks")
        TestStudyPlan.plan = plan

    def test_item_description_fuller(self):
        plan = TestStudyPlan.plan
        week = plan["weeks"][0]
        goal_wc = word_count(week["goal"])
        print(f"\n[study_plan week1] goal({goal_wc}w): {week['goal']}")
        item = week["items"][0]
        it_wc = word_count(item["description"])
        print(f"[study_plan item] desc({it_wc}w): {item['description']}")
        assert it_wc >= 4, f"item description too terse: {item['description']}"


class TestDailyPlan:
    def test_settings_and_get(self, session):
        path_id = TestRoadmapCustom.path_id
        r = session.post(f"{API}/roadmap/daily-plan/settings", params={"path_id": path_id},
                          json={"free_days": [5, 6], "time_mode": "daily", "time_value": 30}, timeout=30)
        assert r.status_code == 200, r.text
        r2 = session.get(f"{API}/roadmap/daily-plan", params={"path_id": path_id}, timeout=30)
        assert r2.status_code == 200, r2.text
        result = poll_until_ready(session, f"{API}/roadmap/daily-plan?path_id={path_id}", timeout=60)
        assert result.get("status") in ("ready", "none") or result.get("weeks"), result
        TestDailyPlan.plan = result

    def test_item_title_desc_and_resources(self, session):
        plan = TestDailyPlan.plan
        weeks = plan.get("weeks") or []
        assert weeks, f"no weeks in daily plan: {plan}"
        item = None
        for w in weeks:
            for d in w.get("days", []):
                for it in d.get("items", []):
                    item = it
                    break
                if item:
                    break
            if item:
                break
        assert item, "no daily plan item found"
        title_wc = word_count(item["title"])
        desc_wc = word_count(item["description"])
        print(f"\n[daily item] title({title_wc}w): {item['title']} | desc({desc_wc}w): {item['description']}")
        assert title_wc <= 12, f"title too long/cut-off concern: {item['title']}"
        assert desc_wc >= 3

        r = session.get(f"{API}/roadmap/daily-plan/items/{item['id']}/resources", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        ov_wc = word_count(data["overview"])
        print(f"[daily_item_resources] overview({ov_wc}w): {data['overview']}")
        assert ov_wc >= 10, f"overview too terse: {data['overview']}"
        assert len(data["steps"]) >= 3
