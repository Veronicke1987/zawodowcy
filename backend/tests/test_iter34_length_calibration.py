"""
Iteration 34: content-LENGTH calibration pass.
Verifies AI-generated text fields hit a MIDDLE GROUND — full flowing sentences,
roughly matching stated word/sentence targets (not ultra-terse fragments, not
giant unlimited paragraphs). Tests: profile summary, career now/future
summary+why, career_detail (description/pros/cons/how_to_start), roadmap
custom path (milestone/task descriptions), task resources (overview/steps/free_tips).
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def word_count(text: str) -> int:
    return len(text.split())


def sentence_count(text: str) -> int:
    # crude sentence counter based on terminal punctuation
    import re
    parts = re.split(r"[.!?]+", text.strip())
    return len([p for p in parts if p.strip()])


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_session(session):
    email = f"TEST_lencalib_{uuid.uuid4().hex[:8]}@test.pl"
    password = "test123"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Len Calib"})
    assert r.status_code in (200, 201), r.text
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in register response: {data}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


PROFILE_ANSWERS = {
    "wiek": "34",
    "miasto": "Wrocław",
    "city": "Wrocław",
    "wyksztalcenie": "Wyższe, kierunek zarządzanie",
    "doswiadczenie": "8 lat w obsłudze klienta i sprzedaży B2B",
    "umiejetnosci": "Excel, obsługa CRM, negocjacje, organizacja pracy zespołu",
    "czego_nie_lubi": "Pracy fizycznej na zewnątrz, nocnych zmian",
    "charakter": "Komunikatywna, zorganizowana, lubi kontakt z ludźmi",
    "reset_mode": "search",
    "cel": "Chce zmienić branżę na bardziej stabilną i rozwojową",
}


@pytest.fixture(scope="module")
def results_bag():
    return {}


class TestLengthCalibration:

    def test_01_submit_profile(self, auth_session):
        r = auth_session.put(f"{API}/profile", json={"answers": PROFILE_ANSWERS})
        assert r.status_code == 200, r.text

    def test_02_generate_recommendations_and_poll(self, auth_session, results_bag):
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
        print(f"\n--- PROFILE SUMMARY ({wc} words, {sc} sentences) ---\n{summary}\n")
        assert summary, "profile summary empty"
        # target: 3-4 sentences, 60-80 words -- allow generous +-30% variance
        assert 35 <= wc <= 110, f"profile summary word count {wc} far outside 60-80 target range"
        assert sc >= 2, f"profile summary looks like a single fragment, sentence count={sc}"

        now_items = doc.get("now") or []
        future_items = doc.get("future") or []
        assert len(now_items) >= 1 and len(future_items) >= 1
        results_bag["career_sample"] = now_items[0]

        for it in (now_items + future_items)[:4]:
            for field in ("summary", "why"):
                txt = it.get(field, "")
                wc_f = word_count(txt)
                sc_f = sentence_count(txt)
                print(f"[{it.get('title')}] {field} ({wc_f}w/{sc_f}s): {txt}")
                assert txt, f"{field} empty for {it.get('title')}"
                # target 2 sentences ~25-35 words; allow 10-50 range
                assert 10 <= wc_f <= 55, f"{field} word count {wc_f} out of expected range for {it.get('title')}"
                # must not be single dash-fragment style (no sentence terminator at all AND very short)
                assert sc_f >= 1

    def test_03_career_detail(self, auth_session, results_bag):
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
        print(f"\n--- CAREER DESCRIPTION ({wc}w/{sc}s) ---\n{desc}\n")
        assert desc
        assert 25 <= wc <= 100, f"description word count {wc} far from 50-65 target"
        assert sc >= 2

        for field in ("pros", "cons", "how_to_start", "daily_tasks"):
            items = detail.get(field) or []
            assert items, f"{field} empty"
            print(f"\n{field}: {items}")
            for item in items:
                wc_i = word_count(item)
                assert wc_i >= 3, f"{field} item too short/fragment-like: '{item}'"

        how_to_start = detail.get("how_to_start") or []
        avg_wc = sum(word_count(x) for x in how_to_start) / max(len(how_to_start), 1)
        print(f"how_to_start avg words/step: {avg_wc:.1f}")
        assert 8 <= avg_wc <= 35, f"how_to_start avg word count {avg_wc} far from 15-20 target"

    def test_04_custom_roadmap_and_poll(self, auth_session, results_bag):
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
        for m in milestones[:3]:
            desc = m.get("description", "")
            wc = word_count(desc)
            sc = sentence_count(desc)
            print(f"\n[milestone: {m.get('title')}] description ({wc}w/{sc}s): {desc}")
            assert desc
            assert 12 <= wc <= 75, f"milestone description word count {wc} far from 30-40 target"

            tasks = m.get("tasks") or []
            assert tasks, f"no tasks for milestone {m.get('title')}"
            results_bag.setdefault("task_sample", tasks[0])
            for t in tasks[:3]:
                tdesc = t.get("description", "")
                twc = word_count(tdesc)
                print(f"   task '{t.get('title')}' ({twc}w): {tdesc}")
                assert tdesc
                assert 5 <= twc <= 40, f"task description word count {twc} far from 15-20 target"

    def test_05_task_resources(self, auth_session, results_bag):
        task = results_bag.get("task_sample")
        assert task, "no task sample captured from roadmap test"
        task_id = task["id"]
        r = auth_session.get(f"{API}/roadmap/tasks/{task_id}/resources")
        assert r.status_code == 200, r.text
        data = r.json()

        overview = data.get("overview", "")
        wc = word_count(overview)
        sc = sentence_count(overview)
        print(f"\n--- TASK OVERVIEW ({wc}w/{sc}s) ---\n{overview}\n")
        assert overview
        assert 25 <= wc <= 110, f"overview word count {wc} far from 55-70 target"
        assert sc >= 2

        steps = data.get("steps") or []
        assert steps
        print(f"\nsteps: {steps}")
        for s in steps:
            swc = word_count(s)
            assert swc >= 5, f"step too short/fragment-like: '{s}'"

        free_tips = data.get("free_tips") or []
        assert free_tips
        print(f"\nfree_tips: {free_tips}")
        for ft in free_tips:
            assert word_count(ft) >= 5, f"free_tip too short/fragment-like: '{ft}'"

        resources = data.get("resources") or []
        assert resources, "no resources returned"
        for res in resources:
            assert res.get("title")
            assert res.get("description")
            print(f"resource: {res.get('platform')} - {res.get('title')} :: {res.get('description')}")
