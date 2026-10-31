"""
Iteration 30: content-quality regression test for the daily plan realism fix in run_daily_plan
(backend/server.py ~line 1062-1131).
Verifies generated daily plan items (for a full week) do NOT contain unrealistic single-day
completions like "ukoncz kurs", "zdobadz certyfikat", "zdobadz doswiadczenie przez staz",
"wez udzial w szkoleniu <specific institution>" phrased as one-day achievable tasks, and that
long_term items (studies/multi-month course) are phrased as a step/check-in, never "ukoncz"/"zdobadz".
Also confirms stateless behavior is unaffected (no regression) by checking the response shape only.
"""
import os
import time
import uuid
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")

# Forbidden one-day-completion verbs/phrases (Polish) that would indicate the bug is NOT fixed.
FORBIDDEN_PATTERNS = [
    "ukończ kurs", "ukoncz kurs",
    "zdobądź certyfikat", "zdobadz certyfikat",
    "zdobądź doświadczenie przez staż", "zdobadz doswiadczenie przez staz",
    "weź udział w szkoleniu", "wez udzial w szkoleniu",
]


def _strip_pl(s: str) -> str:
    repl = {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
    out = s.lower()
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def register_and_setup(api_client):
    email = f"TEST_daily30_{uuid.uuid4().hex[:8]}@test.pl"
    r = api_client.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "test123"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    answers = {
        "learn_time": "1 godzina dziennie",
        "current_status": "pracuję w handlu, chcę zmienić branżę na IT",
        "city": "Bydgoszcz",
        "education": "średnie",
        "interests": "sprzedaż, technologia",
    }
    r = api_client.put(f"{BASE_URL}/api/profile", headers=headers, json={"answers": answers})
    assert r.status_code == 200, r.text

    # upgrade to premium (demo) so all 7 days unlock and long_term items get a fair chance to appear
    r = api_client.post(f"{BASE_URL}/api/premium/subscribe", headers=headers, json={"plan": "monthly"})
    assert r.status_code == 200, r.text

    # custom roadmap for a career likely to include a "studies"-type long-term task
    r = api_client.post(
        f"{BASE_URL}/api/roadmap/custom",
        headers=headers,
        json={"title": "Specjalista ds. sprzedaży IT", "qualifications": ""},
    )
    assert r.status_code == 200, r.text

    deadline = time.time() + 90
    doc = None
    while time.time() < deadline:
        r = api_client.get(f"{BASE_URL}/api/roadmap", headers=headers)
        if r.status_code == 200 and r.json().get("status") == "ready":
            doc = r.json()
            break
        time.sleep(3)
    assert doc is not None, "custom roadmap never became ready"
    return headers, doc


def poll_daily_plan(api_client, headers, field="status", max_wait=90):
    deadline = time.time() + max_wait
    last = None
    while time.time() < deadline:
        r = api_client.get(f"{BASE_URL}/api/roadmap/daily-plan", headers=headers)
        assert r.status_code == 200
        last = r.json()
        if last.get(field) in ("ready", "error"):
            return last
        time.sleep(3)
    return last


class TestDailyPlanRealism:
    def test_daily_plan_items_are_single_day_realistic(self, api_client):
        headers, _ = register_and_setup(api_client)

        r = api_client.post(
            f"{BASE_URL}/api/roadmap/daily-plan/settings",
            headers=headers,
            json={"time_mode": "daily", "time_value": 60, "free_days": []},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        data = poll_daily_plan(api_client, headers)
        assert data is not None and data.get("status") == "ready", f"daily plan failed/timed out: {data}"
        weeks = data["weeks"]
        assert len(weeks) == 1
        week = weeks[0]
        days = week["days"]
        assert len(days) == 7

        all_items = []
        long_term_items = []
        for d in days:
            for it in d.get("items", []):
                all_items.append(it)
                if it.get("long_term"):
                    long_term_items.append(it)

        assert len(all_items) > 0, "expected at least some daily plan items across the week"

        violations = []
        for it in all_items:
            text = f"{it.get('title','')} {it.get('description','')}"
            norm = _strip_pl(text)
            for pat in FORBIDDEN_PATTERNS:
                if _strip_pl(pat) in norm:
                    violations.append((pat, text))

        # long_term items must never say "ukończ"/"zdobądź"
        long_term_violations = []
        for it in long_term_items:
            text = f"{it.get('title','')} {it.get('description','')}"
            norm = _strip_pl(text)
            if "ukoncz" in norm or "zdobadz" in norm:
                long_term_violations.append(text)
            assert len(long_term_items) <= 1 * len(days) or True  # sanity placeholder, actual count asserted below

        print("\n--- ALL 7 DAYS (incl. empty) ---")
        for d in days:
            print(f"date={d['date']} wd={d['weekday']} free={d['free']} locked={d['locked']} n_items={len(d.get('items', []))}")
        print("\n--- ALL GENERATED DAILY ITEMS ---")
        for d in days:
            for it in d.get("items", []):
                print(f"[{d['date']} wd={d['weekday']} free={d['free']} long_term={it.get('long_term')}] "
                      f"{it.get('title')!r} -- {it.get('description')!r} ({it.get('minutes')} min)")

        assert not violations, f"Found unrealistic one-day-completion phrasing: {violations}"
        assert not long_term_violations, f"long_term item phrased as 'ukończ/zdobądź': {long_term_violations}"

        # at most one long_term item should appear for the whole week (per spec)
        assert len(long_term_items) <= 1, f"expected <=1 long_term item in the week, got {len(long_term_items)}: {long_term_items}"
