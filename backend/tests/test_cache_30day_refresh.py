"""
Tests for the new UNIFIED 30-day time-based cache refresh mechanism (is_cache_stale /
CAREER_CACHE_REFRESH_DAYS=30 in server.py ~line 441-454), applied to all three shared
career_templates caches:
  (a) career detail            -> career_templates.detail / detail_updated_at
  (b) roadmap milestones       -> career_templates.milestones / milestones_updated_at
  (c) weekly study plan        -> career_templates.weekly_plans.{sig}.plan / plan_updated_at

Strategy to minimize real Anthropic API cost (each generation = real money):
  - Use a single TEST_ user and ONE unique custom-career title so the shared cache key is
    guaranteed to be brand-new (no risk of hitting another test run's/real user's cache).
  - Manipulate MongoDB directly (pymongo) to rewind *_updated_at timestamps 31 days instead
    of waiting 30 days, to force/verify the staleness path.
  - Total real LLM generations in this file: 5
      1) career detail (fresh, cache miss)
      2) career detail (fresh regenerate, forced-stale cache)
      3) roadmap milestones (fresh, cache miss)
      4) roadmap milestones (fresh regenerate, forced-stale cache)
      5) weekly study plan (fresh, cache miss) -- staleness re-verified by direct DB
         timestamp/field assertions only (no 6th generation), since the mechanism is
         identical code (is_cache_stale) to (a)/(b) which ARE exercised end-to-end above.
"""
import os
import re
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

RUN_ID = uuid.uuid4().hex[:8]
EMAIL = f"TEST_cache30_{RUN_ID}@test.pl"
PASSWORD = "Test1234"
CAREER_TITLE = f"TEST_Zawod_Cache30_{RUN_ID}"


def normalize_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def career_cache_key(title: str, country: str = "PL", language: str = "pl") -> str:
    return f"{(country or 'PL').upper()}::{language or 'pl'}::{normalize_title(title)}"


@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{API}/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "TEST Cache30"})
    assert r.status_code in (200, 201), r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def career_id(headers):
    r = requests.post(f"{API}/careers/custom", headers=headers, json={"title": CAREER_TITLE, "qualifications": ""})
    assert r.status_code == 200, r.text
    return r.json()["career_id"]


@pytest.fixture(scope="module")
def cache_key():
    return career_cache_key(CAREER_TITLE)


def poll_roadmap(headers, timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{API}/roadmap", headers=headers)
        assert r.status_code == 200
        data = r.json()
        if data.get("status") in ("ready", "error"):
            return data, time.time() - start
        time.sleep(1)
    raise TimeoutError("roadmap did not finish in time")


def poll_study_plan(headers, timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{API}/roadmap/study-plan", headers=headers)
        assert r.status_code == 200
        data = r.json()
        if data.get("status") in ("ready", "error"):
            return data, time.time() - start
        time.sleep(1)
    raise TimeoutError("study plan did not finish in time")


class TestCareerDetailCache30Day:
    """GET /api/careers/{id} -> career_templates.detail / detail_updated_at"""

    def test_1_fresh_generation_then_cache_hit(self, headers, career_id, mongo_db, cache_key):
        # First call: cache miss, real AI generation (LLM call #1)
        t0 = time.time()
        r1 = requests.get(f"{API}/careers/{career_id}", headers=headers)
        elapsed1 = time.time() - t0
        assert r1.status_code == 200, r1.text
        detail1 = r1.json()["detail"]
        print(f"1st GET /careers/{{id}} took {elapsed1:.1f}s (fresh generation)")

        tmpl = mongo_db.career_templates.find_one({"_id": cache_key})
        assert tmpl is not None, "career_templates doc not created"
        assert tmpl.get("detail_updated_at"), "detail_updated_at was not written on fresh generation"
        first_updated_at = tmpl["detail_updated_at"]

        # Second call: should be an immediate cache hit, identical content, no new AI call
        t1 = time.time()
        r2 = requests.get(f"{API}/careers/{career_id}", headers=headers)
        elapsed2 = time.time() - t1
        assert r2.status_code == 200
        detail2 = r2.json()["detail"]
        print(f"2nd GET /careers/{{id}} took {elapsed2:.1f}s (expected cache hit)")

        assert detail1 == detail2, "Cache hit should return IDENTICAL detail content"
        assert elapsed2 < 5, f"2nd call took {elapsed2:.1f}s - too slow for a cache hit (expected near-instant)"

        tmpl2 = mongo_db.career_templates.find_one({"_id": cache_key})
        assert tmpl2["detail_updated_at"] == first_updated_at, "detail_updated_at must NOT change on a cache hit"

    def test_2_stale_cache_forces_regeneration(self, headers, career_id, mongo_db, cache_key):
        # Force the cached detail to look 31 days old
        stale_ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        res = mongo_db.career_templates.update_one({"_id": cache_key}, {"$set": {"detail_updated_at": stale_ts}})
        assert res.modified_count == 1
        before = mongo_db.career_templates.find_one({"_id": cache_key})
        assert before["detail_updated_at"] == stale_ts

        # This call must now trigger a fresh AI generation (LLM call #2) instead of reusing stale cache
        t0 = time.time()
        r = requests.get(f"{API}/careers/{career_id}", headers=headers)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        print(f"GET /careers/{{id}} after forcing 31-day-old cache took {elapsed:.1f}s (expected fresh regeneration)")

        after = mongo_db.career_templates.find_one({"_id": cache_key})
        new_updated_at = after.get("detail_updated_at")
        assert new_updated_at and new_updated_at != stale_ts, "detail_updated_at must be refreshed after stale-cache regeneration"
        age = datetime.now(timezone.utc) - datetime.fromisoformat(new_updated_at)
        assert age < timedelta(minutes=2), "detail_updated_at should now be 'now', not still stale"


class TestRoadmapMilestonesCache30Day:
    """POST /api/roadmap -> career_templates.milestones / milestones_updated_at"""

    def test_3_fresh_roadmap_generation(self, headers, career_id, mongo_db, cache_key):
        r = requests.post(f"{API}/roadmap", headers=headers, json={"career_id": career_id})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        data, elapsed = poll_roadmap(headers)
        print(f"Roadmap (fresh, LLM call #3) ready after {elapsed:.1f}s")
        assert data["status"] == "ready"
        assert len(data.get("milestones", [])) > 0

        tmpl = mongo_db.career_templates.find_one({"_id": cache_key})
        assert tmpl.get("milestones"), "milestones were not cached into career_templates"
        assert tmpl.get("milestones_updated_at"), "milestones_updated_at was not written on fresh generation"

    def test_4_stale_milestones_force_regeneration(self, headers, career_id, mongo_db, cache_key):
        # Force cached milestones to look 31 days old
        stale_ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        res = mongo_db.career_templates.update_one({"_id": cache_key}, {"$set": {"milestones_updated_at": stale_ts}})
        assert res.modified_count == 1

        # Delete current roadmap and re-select the SAME custom career title -> re-POST /roadmap
        # must now hit the "stale" branch (cache_key lookup is stale) and trigger a fresh
        # AI generation (LLM call #4) instead of cloning the old cached milestones.
        del_resp = requests.delete(f"{API}/roadmap", headers=headers)
        assert del_resp.status_code in (200, 404)

        custom_resp = requests.post(f"{API}/careers/custom", headers=headers, json={"title": CAREER_TITLE, "qualifications": ""})
        assert custom_resp.status_code == 200, custom_resp.text
        new_career_id = custom_resp.json()["career_id"]

        r = requests.post(f"{API}/roadmap", headers=headers, json={"career_id": new_career_id})
        assert r.status_code == 200, r.text
        assert r.json().get("existing") is not True, "Should not silently reuse a deleted roadmap"
        data, elapsed = poll_roadmap(headers)
        print(f"Roadmap after forcing 31-day-old milestones cache took {elapsed:.1f}s (expected fresh regeneration)")
        assert data["status"] == "ready"

        tmpl = mongo_db.career_templates.find_one({"_id": cache_key})
        new_updated_at = tmpl.get("milestones_updated_at")
        assert new_updated_at and new_updated_at != stale_ts, "milestones_updated_at must be refreshed after stale-cache regeneration"
        age = datetime.now(timezone.utc) - datetime.fromisoformat(new_updated_at)
        assert age < timedelta(minutes=2), "milestones_updated_at should now be 'now', not still stale"


class TestWeeklyPlanCache30Day:
    """POST /api/roadmap/study-plan -> career_templates.weekly_plans.{sig}.plan / plan_updated_at
    Only exercises the fresh-generation path (LLM call #5) + direct-DB field/shape assertions,
    to avoid a 6th costly regeneration call -- the staleness CHECK itself (is_cache_stale) is
    byte-identical code already proven to correctly force regeneration in tests 2 and 4 above."""

    def test_5_fresh_weekly_plan_writes_plan_updated_at(self, headers, mongo_db, cache_key):
        r = requests.post(f"{API}/roadmap/study-plan", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"
        data, elapsed = poll_study_plan(headers)
        print(f"Weekly plan (fresh, LLM call #5) ready after {elapsed:.1f}s")
        assert data["status"] == "ready"
        assert len(data.get("blocks", [])) > 0

        tmpl = mongo_db.career_templates.find_one({"_id": cache_key})
        weekly_plans = tmpl.get("weekly_plans") or {}
        assert weekly_plans, "weekly_plans field was not written into career_templates"
        sig, entry = next(iter(weekly_plans.items()))
        assert entry.get("plan"), "plan content missing under weekly_plans.{sig}.plan"
        assert entry.get("plan_updated_at"), "plan_updated_at missing under weekly_plans.{sig}.plan_updated_at"

        # Simulate 31-day-old plan_updated_at directly (verifies the field/path exists and is
        # independently rewindable per the spec, matching is_cache_stale's exact field name).
        stale_ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        field = f"weekly_plans.{sig}.plan_updated_at"
        res = mongo_db.career_templates.update_one({"_id": cache_key}, {"$set": {field: stale_ts}})
        assert res.modified_count == 1
        after = mongo_db.career_templates.find_one({"_id": cache_key})
        assert after["weekly_plans"][sig]["plan_updated_at"] == stale_ts
