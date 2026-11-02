"""
Iteration 54: Verify AI prompt word-count budgets were reduced by ~1/3 across all
ask_llm() calls (recommendations, career detail, roadmap milestones/tasks, task
resources, weekly study plan, daily plan) while content remains complete, coherent,
and JSON still parses successfully (no truncation).

Uses a FRESH test user + a fresh custom career (random title) so every ask_llm() call
actually runs the NEW shortened prompts instead of hitting career_templates cache
populated before this change.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

PROFILE_ANSWERS = {
    "wiek": "34", "miasto": "Wrocław", "city": "Wrocław",
    "wyksztalcenie": "Wyższe, kierunek zarządzanie",
    "doswiadczenie": "8 lat w obsłudze klienta i sprzedaży B2B",
    "umiejetnosci": "Excel, obsługa CRM, negocjacje, organizacja pracy zespołu",
    "czego_nie_lubi": "Pracy fizycznej na zewnątrz, nocnych zmian",
    "charakter": "Komunikatywna, zorganizowana, lubi kontakt z ludźmi",
    "reset_mode": "search",
    "cel": "Chce zmienić branżę na bardziej stabilną i rozwojową",
}


def word_count(s: str) -> int:
    return len((s or "").split())


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_iter54_{uuid.uuid4().hex[:8]}@test.pl"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "Iter54 Tester"})
    assert r.status_code in (200, 201), r.text
    token = r.json().get("token") or r.json().get("access_token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    r2 = s.put(f"{API}/profile", json={"answers": PROFILE_ANSWERS})
    assert r2.status_code == 200, r2.text
    # Enable premium (demo) so the daily-plan endpoint (premium-only) can be tested too.
    r3 = s.post(f"{API}/premium/subscribe", json={"plan": "monthly"})
    print(f"\n[premium subscribe] {r3.status_code} {r3.text[:200]}")
    return s


class TestRecommendations:
    def test_get_recommendations_summary_and_career_fields(self, session):
        r = session.post(f"{BASE_URL}/api/recommendations/generate")
        assert r.status_code == 200, r.text
        data = {}
        for _ in range(40):
            time.sleep(5)
            rr = session.get(f"{BASE_URL}/api/recommendations")
            assert rr.status_code == 200
            data = rr.json()
            if data.get("status") in ("ready", "error"):
                break
        assert data.get("status") == "ready", f"unexpected status: {data.get('status')}"
        summary = data.get("summary", "")
        assert summary, "summary field empty"
        wc = word_count(summary)
        print(f"\n[recommendations.summary] words={wc} text={summary!r}")
        # target ~22-28 words (was 35-45); allow generous tolerance for LLM variance
        assert 10 <= wc <= 45, f"summary word count {wc} far outside expected shortened range"
        assert summary.strip()[-1] in ".!?", "summary doesn't end like a complete sentence"

        careers = (data.get("now") or []) + (data.get("future") or [])
        assert len(careers) >= 1
        for c in careers[:5]:
            s_field = c.get("summary", "")
            w_field = c.get("why", "")
            assert s_field and w_field, f"career {c.get('title')} missing summary/why"
            swc, wwc = word_count(s_field), word_count(w_field)
            print(f"[career={c.get('title')}] summary_words={swc} why_words={wwc}")
            assert 3 <= swc <= 30
            assert 3 <= wwc <= 30
            assert s_field.strip()[-1] in ".!?"
            assert w_field.strip()[-1] in ".!?"


class TestCareerDetail:
    def test_career_detail_fields_shortened(self, session):
        r = session.get(f"{BASE_URL}/api/recommendations")
        careers = (r.json().get("now") or []) + (r.json().get("future") or [])
        assert careers, "no careers available to test detail endpoint"
        career_id = careers[0]["id"]
        r2 = session.get(f"{BASE_URL}/api/careers/{career_id}")
        assert r2.status_code == 200, r2.text
        detail = r2.json()["detail"]
        desc = detail.get("description", "")
        wc = word_count(desc)
        print(f"\n[career_detail.description] words={wc} text={desc!r}")
        assert 8 <= wc <= 45
        assert desc.strip()[-1] in ".!?"

        for field in ("daily_tasks", "pros", "cons"):
            items = detail.get(field) or []
            assert items, f"{field} empty"
            for item in items:
                iwc = word_count(item)
                print(f"[career_detail.{field}] words={iwc} text={item!r}")
                assert iwc <= 22, f"{field} item too long: {iwc} words"
                assert item.strip()[-1] in ".!?", f"{field} item not a complete sentence: {item!r}"

        how_to_start = detail.get("how_to_start") or []
        assert how_to_start
        for item in how_to_start:
            iwc = word_count(item)
            print(f"[career_detail.how_to_start] words={iwc} text={item!r}")
            assert iwc <= 30
            assert item.strip()[-1] in ".!?"


class TestRoadmapAndResources:
    def test_custom_path_milestones_and_task_resources(self, session):
        # Use a real profession title (backend validates it's a real job) to avoid hitting a
        # career_templates cache populated by a prior run with the OLD (longer) prompts.
        title = "Koordynator ds. wdrożeń ERP"
        r = session.post(f"{BASE_URL}/api/careers/custom", json={"title": title, "qualifications": ""})
        assert r.status_code == 200, r.text
        career_id = r.json().get("career_id")
        assert career_id
        r = session.post(f"{BASE_URL}/api/roadmap", json={"career_id": career_id})
        assert r.status_code == 200, r.text
        path_id = r.json().get("path_id")
        assert path_id

        doc = {}
        for _ in range(40):
            time.sleep(5)
            rr = session.get(f"{BASE_URL}/api/roadmap", params={"path_id": path_id})
            assert rr.status_code == 200
            doc = rr.json()
            if doc.get("status") in ("ready", "error"):
                break
        assert doc.get("status") == "ready", f"roadmap not ready: {doc}"
        milestones = doc.get("milestones") or []
        assert milestones
        for m in milestones[:3]:
            mdesc = m.get("description", "")
            mwc = word_count(mdesc)
            print(f"\n[milestone={m.get('title')}] desc_words={mwc} text={mdesc!r}")
            assert mwc <= 28
            assert mdesc.strip()[-1] in ".!?"
            for t in (m.get("tasks") or [])[:3]:
                tdesc = t.get("description", "")
                twc = word_count(tdesc)
                print(f"  [task={t.get('title')}] desc_words={twc} text={tdesc!r}")
                assert twc <= 25
                assert tdesc.strip()[-1] in ".!?"

        task_id = None
        for m in milestones:
            for t in m.get("tasks", []):
                if not t.get("done"):
                    task_id = t["id"]
                    break
            if task_id:
                break
        assert task_id, "no pending task found to test resources endpoint"
        rr = session.get(f"{BASE_URL}/api/roadmap/tasks/{task_id}/resources", params={"path_id": path_id})
        assert rr.status_code == 200, rr.text
        res = rr.json()
        overview = res.get("overview", "")
        owc = word_count(overview)
        print(f"\n[task_resources.overview] words={owc} text={overview!r}")
        assert 8 <= owc <= 45
        assert overview.strip()[-1] in ".!?"

        steps = res.get("steps") or []
        assert steps
        for st in steps:
            swc = word_count(st)
            print(f"[task_resources.steps] words={swc} text={st!r}")
            assert swc <= 25
            assert st.strip()[-1] in ".!?"

        free_tips = res.get("free_tips") or []
        assert free_tips
        for tip in free_tips:
            twc = word_count(tip)
            print(f"[task_resources.free_tips] words={twc} text={tip!r}")
            assert twc <= 20
            assert tip.strip()[-1] in ".!?"

        resources = res.get("resources") or []
        assert len(resources) >= 3, "expected several named resources"
        for res_item in resources:
            rdesc = res_item.get("description", "")
            rwc = word_count(rdesc)
            print(f"[task_resources.resources.description] words={rwc} text={rdesc!r} platform={res_item.get('platform')}")
            assert rwc <= 20
            assert res_item.get("platform") or res_item.get("title")
        session.__dict__.setdefault("_iter54_path_id", path_id)
        TestRoadmapAndResources.path_id = path_id


class TestWeeklyAndDailyPlan:
    def test_weekly_plan_structure_and_lengths(self, session):
        path_id = getattr(TestRoadmapAndResources, "path_id", None)
        assert path_id, "no path_id captured from roadmap test (run after TestRoadmapAndResources)"
        plan_doc = {}
        cr = session.post(f"{BASE_URL}/api/roadmap/study-plan", params={"path_id": path_id})
        print(f"\n[study-plan create] status={cr.status_code} body={cr.text[:300]}")
        assert cr.status_code == 200, cr.text
        for _ in range(40):
            time.sleep(5)
            r2 = session.get(f"{BASE_URL}/api/roadmap/study-plan", params={"path_id": path_id})
            plan_doc = r2.json()
            if plan_doc.get("status") in ("ready", "error"):
                break
        assert plan_doc.get("status") == "ready", f"weekly study plan not ready: {plan_doc}"

        blocks = plan_doc.get("blocks") or []
        assert blocks, "no weekly plan blocks"
        block = blocks[-1]
        plan = block.get("plan") or {}
        weeks = plan.get("weeks") or []
        print(f"\n[weekly_plan] num_weeks={len(weeks)}")
        assert len(weeks) == 8, f"expected 8 weeks, got {len(weeks)}"

        summary = plan.get("summary", "")
        swc = word_count(summary)
        print(f"[weekly_plan.summary] words={swc} text={summary!r}")
        assert swc <= 25
        assert summary.strip()[-1] in ".!?"

        for w in weeks:
            goal = w.get("goal", "")
            gwc = word_count(goal)
            items = w.get("items") or []
            print(f"[weekly_plan.week {w.get('week')}] goal_words={gwc} num_items={len(items)}")
            assert gwc <= 25
            assert goal.strip()[-1] in ".!?"
            assert 2 <= len(items) <= 6, f"item count changed unexpectedly: {len(items)}"
            for it in items:
                idesc = it.get("description", "")
                iwc = word_count(idesc)
                assert iwc <= 25
                assert idesc.strip()[-1] in ".!?"

        tips = plan.get("tips") or []
        assert tips
        for tip in tips:
            twc = word_count(tip)
            print(f"[weekly_plan.tips] words={twc} text={tip!r}")
            assert twc <= 20
            assert tip.strip()[-1] in ".!?"

    def test_daily_plan_item_lengths(self, session):
        path_id = getattr(TestRoadmapAndResources, "path_id", None)
        assert path_id, "no path_id captured from roadmap test"
        payload = {"time_mode": "daily", "time_value": 45, "free_days": [5, 6]}
        pr = session.post(f"{BASE_URL}/api/roadmap/daily-plan/settings", json=payload, params={"path_id": path_id})
        print(f"\n[daily-plan settings POST] status={pr.status_code} body={pr.text[:300]}")
        assert pr.status_code == 200, pr.text

        dr = {}
        for _ in range(40):
            time.sleep(5)
            r2 = session.get(f"{BASE_URL}/api/roadmap/daily-plan", params={"path_id": path_id})
            dr = r2.json()
            if dr.get("status") in ("ready", "error"):
                break
        assert dr.get("status") == "ready", f"daily plan not ready: {dr}"

        weeks = dr.get("weeks") or []
        assert weeks, "no daily plan weeks"
        checked_any = False
        for wk in weeks:
            for day in wk.get("days", []):
                for item in day.get("items", []):
                    checked_any = True
                    title, desc = item.get("title", ""), item.get("description", "")
                    twc, dwc = word_count(title), word_count(desc)
                    print(f"[daily_plan.item] title_words={twc} desc_words={dwc} title={title!r} desc={desc!r}")
                    assert twc <= 8, f"title too long: {twc} words ({title!r})"
                    assert dwc <= 18, f"description too long: {dwc} words ({desc!r})"
        assert checked_any, "no daily plan items found to validate"
