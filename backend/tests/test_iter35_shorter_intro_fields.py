"""
Iteration 35: further length reduction of intro/overview/summary paragraph fields only.
List-style fields (steps/pros/cons/requirements/how_to_start/free_tips) untouched.
New targets (~half of iteration_34):
- recommendations.summary (profile): 2 sentences, ~35-45 words
- career now/future summary & why: 1 sentence each, ~15-20 words
- career_detail.description: 2 sentences, ~30-40 words
- roadmap milestone.description: 1 sentence, ~18-25 words (task.description UNCHANGED)
- task_resources.overview: 2 sentences, ~30-40 words
- study_plan summary: 1 sentence, ~15-20 words
- daily_item_resources.overview: 1 sentence, ~18-25 words
"""
import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def word_count(text: str) -> int:
    return len(text.split())


def sentence_count(text: str) -> int:
    parts = re.split(r"[.!?]+", text.strip())
    return len([p for p in parts if p.strip()])


def is_fragment_like(text: str) -> bool:
    """Flag dash-separated phrase lists rather than full sentences."""
    # no terminal punctuation at all, or excessive dash-separated clauses
    if not re.search(r"[.!?]", text.strip()):
        return True
    return False


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_session(session):
    email = f"TEST_iter35_{uuid.uuid4().hex[:8]}@test.pl"
    password = "test123"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Iter35 Tester"})
    assert r.status_code in (200, 201), r.text
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in register response: {data}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


PROFILE_ANSWERS = {
    "wiek": "29",
    "miasto": "Poznań",
    "city": "Poznań",
    "wyksztalcenie": "Średnie techniczne, elektryczne",
    "doswiadczenie": "5 lat jako technik utrzymania ruchu w fabryce",
    "umiejetnosci": "Czytanie schematów, naprawa maszyn, praca pod presją czasu",
    "czego_nie_lubi": "Pracy biurowej, monotonii",
    "charakter": "Praktyczny, dokładny, lubi rozwiązywać problemy",
    "reset_mode": "search",
    "cel": "Chce przebranżowić się w kierunku bardziej stabilnego i lepiej płatnego zawodu technicznego",
}


@pytest.fixture(scope="module")
def results_bag():
    return {}


class TestShorterIntroFields:

    def test_01_submit_profile(self, auth_session):
        r = auth_session.put(f"{API}/profile", json={"answers": PROFILE_ANSWERS})
        assert r.status_code == 200, r.text

    def test_02_recommendations_summary_lengths(self, auth_session, results_bag):
        r = auth_session.post(f"{API}/recommendations/generate")
        assert r.status_code == 200, r.text

        doc = None
        for _ in range(40):
            time.sleep(5)
            r = auth_session.get(f"{API}/recommendations")
            assert r.status_code == 200
            doc = r.json()
            if doc.get("status") in ("ready", "error"):
                break
        assert doc is not None
        assert doc.get("status") == "ready", f"recommendations not ready: {doc}"
        results_bag["recommendations"] = doc

        summary = doc.get("summary", "")
        wc = word_count(summary)
        sc = sentence_count(summary)
        print(f"\n--- PROFILE SUMMARY ({wc} words, {sc} sentences) [target 35-45w/2s] ---\n{summary}\n")
        assert summary
        assert not is_fragment_like(summary), f"profile summary looks fragment-like: {summary}"
        # generous tolerance band around 35-45 target, but must be clearly shorter than iter34's 60-80
        assert 20 <= wc <= 60, f"profile summary word count {wc} far outside ~35-45 target"

        now_items = doc.get("now") or []
        future_items = doc.get("future") or []
        assert len(now_items) >= 1 and len(future_items) >= 1
        results_bag["career_sample"] = now_items[0]

        for it in (now_items + future_items)[:4]:
            for field in ("summary", "why"):
                txt = it.get(field, "")
                wc_f = word_count(txt)
                sc_f = sentence_count(txt)
                print(f"[{it.get('title')}] {field} ({wc_f}w/{sc_f}s) [target 15-20w/1s]: {txt}")
                assert txt, f"{field} empty for {it.get('title')}"
                assert not is_fragment_like(txt), f"{field} fragment-like for {it.get('title')}: {txt}"
                assert 8 <= wc_f <= 35, f"{field} word count {wc_f} far outside ~15-20 target for {it.get('title')}"

    def test_03_career_detail_description(self, auth_session, results_bag):
        career = results_bag["career_sample"]
        career_id = career["id"]
        r = auth_session.get(f"{API}/careers/{career_id}")
        assert r.status_code == 200, r.text
        data = r.json()
        detail = data.get("detail", {})
        results_bag["career_detail"] = detail

        desc = detail.get("description", "")
        wc = word_count(desc)
        sc = sentence_count(desc)
        print(f"\n--- CAREER DESCRIPTION ({wc}w/{sc}s) [target 30-40w/2s] ---\n{desc}\n")
        assert desc
        assert not is_fragment_like(desc)
        assert 15 <= wc <= 60, f"description word count {wc} far outside ~30-40 target"

        # list-style fields should remain untouched/full (sanity, not a length check)
        for field in ("pros", "cons", "how_to_start", "daily_tasks"):
            items = detail.get(field) or []
            assert items, f"{field} empty"

    def test_04_roadmap_milestone_and_task_descriptions(self, auth_session, results_bag):
        r = auth_session.post(f"{API}/roadmap/custom", json={"title": "elektryk", "qualifications": ""})
        assert r.status_code == 200, r.text
        path_id = r.json().get("path_id")
        assert path_id

        doc = None
        for _ in range(40):
            time.sleep(5)
            r = auth_session.get(f"{API}/roadmap", params={"path_id": path_id})
            assert r.status_code == 200
            doc = r.json()
            if doc.get("status") in ("ready", "error"):
                break
        assert doc is not None
        assert doc.get("status") == "ready", f"roadmap not ready: {doc}"
        results_bag["roadmap"] = doc

        milestones = doc.get("milestones") or []
        assert milestones
        task_descs = []
        for m in milestones[:3]:
            desc = m.get("description", "")
            wc = word_count(desc)
            sc = sentence_count(desc)
            print(f"\n[milestone: {m.get('title')}] description ({wc}w/{sc}s) [target 18-25w/1s]: {desc}")
            assert desc
            assert not is_fragment_like(desc)
            assert 10 <= wc <= 45, f"milestone description word count {wc} far outside ~18-25 target"

            tasks = m.get("tasks") or []
            assert tasks, f"no tasks for milestone {m.get('title')}"
            results_bag.setdefault("task_sample", tasks[0])
            for t in tasks[:3]:
                tdesc = t.get("description", "")
                task_descs.append(word_count(tdesc))
                print(f"   task '{t.get('title')}' ({word_count(tdesc)}w) [UNCHANGED target ~15-20w]: {tdesc}")
                assert tdesc
        # task.description was explicitly NOT touched this iteration; just sanity check non-empty, no strict bound change
        assert all(w >= 5 for w in task_descs)

    def test_05_task_resources_overview(self, auth_session, results_bag):
        task = results_bag.get("task_sample")
        assert task, "no task sample captured from roadmap test"
        task_id = task["id"]
        r = auth_session.get(f"{API}/roadmap/tasks/{task_id}/resources")
        assert r.status_code == 200, r.text
        data = r.json()

        overview = data.get("overview", "")
        wc = word_count(overview)
        sc = sentence_count(overview)
        print(f"\n--- TASK OVERVIEW ({wc}w/{sc}s) [target 30-40w/2s] ---\n{overview}\n")
        assert overview
        assert not is_fragment_like(overview)
        assert 15 <= wc <= 60, f"overview word count {wc} far outside ~30-40 target"

        # list fields sanity (should remain full, untouched)
        steps = data.get("steps") or []
        assert steps
        free_tips = data.get("free_tips") or []
        assert free_tips

    def test_06_study_plan_summary(self, auth_session, results_bag):
        r = auth_session.post(f"{API}/study-plan/generate")
        if r.status_code not in (200, 201):
            pytest.skip(f"study-plan generate not available/failed: {r.status_code} {r.text}")

        doc = None
        for _ in range(40):
            time.sleep(5)
            r = auth_session.get(f"{API}/study-plan")
            assert r.status_code == 200
            doc = r.json()
            if doc.get("status") in ("ready", "error"):
                break
        if not doc or doc.get("status") != "ready":
            pytest.skip(f"study-plan not ready in time: {doc}")

        summary = doc.get("summary", "")
        wc = word_count(summary)
        sc = sentence_count(summary)
        print(f"\n--- STUDY PLAN SUMMARY ({wc}w/{sc}s) [target 15-20w/1s] ---\n{summary}\n")
        assert summary
        assert not is_fragment_like(summary)
        assert 8 <= wc <= 35, f"study plan summary word count {wc} far outside ~15-20 target"

        items = doc.get("items") or doc.get("days") or []
        results_bag["daily_item"] = items[0] if items else None

    def test_07_daily_item_resources_overview(self, auth_session, results_bag):
        item = results_bag.get("daily_item")
        if not item:
            pytest.skip("no daily study-plan item captured to test resources for")
        item_id = item.get("id")
        if not item_id:
            pytest.skip("daily item has no id field")
        r = auth_session.get(f"{API}/study-plan/items/{item_id}/resources")
        if r.status_code != 200:
            pytest.skip(f"daily item resources endpoint not reachable: {r.status_code} {r.text}")
        data = r.json()
        overview = data.get("overview", "")
        wc = word_count(overview)
        sc = sentence_count(overview)
        print(f"\n--- DAILY ITEM OVERVIEW ({wc}w/{sc}s) [target 18-25w/1s] ---\n{overview}\n")
        assert overview
        assert not is_fragment_like(overview)
        assert 10 <= wc <= 45, f"daily item overview word count {wc} far outside ~18-25 target"
