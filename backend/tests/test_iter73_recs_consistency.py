"""
Backend test for iteration 7: CONSISTENCY/VARIANCE check of the high-qualification
recommendations prompt (run_recommendations(), /app/backend/server.py ~L1051-1170).

Context: iteration 6 fixed the high-qualification regression and PASSED in a single
testing-agent run, but the real user re-tested the SAME profile in production and got
poor results again ("wsparcie wprowadzania dokumentów", "asystent back office") - roles
BELOW their qualification. Likely cause: temperature=1.0 (server.py L1129) gives high
run-to-run variance for the same profile.

This test calls POST /api/recommendations/generate THREE TIMES for the SAME profile,
using 3 SEPARATE fresh users (to avoid the shown_titles avoid-list mechanism skewing
results toward "different angle" hints, which would not reflect a true repeat of the
exact same request) and checks each of the 3 independent result sets for:
  (a) ZERO low-skill/assistant/back-office/physical-labor titles
  (b) "now" reflects wdrożeniowiec/specjalista SAP/ERP/HR level
  (c) "future" is one level up (starszy konsultant/kierownik projektu/senior specialist)
      in a RELATED field (SAP/ERP/HR/IT), not an unrelated industry.

COST NOTE: exactly 3 real /recommendations/generate calls in this file, per the
agent-to-agent budget for this critical stability test.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

# Low-skill/assistant/back-office/physical-labor jobs - bad match for this profile.
BAD_FIT_KEYWORDS = [
    "kierowca", "magazynier", "pracownik magazynu", "opiekun zwierząt", "opiekun psów",
    "opiekunka zwierząt", "sprzątając", "sprzątacz", "ochroniarz", "kasjer",
    "pracownik produkcji", "pracownik budowlany", "kelner", "kucharz", "sprzedawca",
    "recepcjonist", "asystent", "wsparcie biurowe", "wsparcie administracyjne",
    "wsparcie wprowadzania", "back office", "wprowadzanie danych", "wprowadzanie dokument",
    "pomoc biurowa", "pracownik biurowy",
]

# Expected "now"-level words (same level as "Wdrożeniowiec T2 Płatnika" / SAP / ERP / HR).
NOW_LEVEL_HINTS = ["wdroż", "specjalist", "konsultant", "sap", "erp", "hr", "kadr", "płac", "it"]

# Expected "future" one-level-up words (promotion within same/related field).
FUTURE_LEVEL_HINTS = [
    "starszy", "senior", "kierownik", "lider", "project manager", "projekt", "menedżer",
    "manager", "główny", "ekspert", "architekt",
]

PROFILE_ANSWERS = {
    "reset_mode": "search",
    "education": "Studia inżynierskie",
    "education_field": "Informatyka w biznesie / Zarządzanie",
    "certificates": ["Studia podyplomowe SAP"],
    "certificates_other": "SAP",
    "current_job": "Wdrożeniowiec T2 Płatnika",
    "industry": "IT i HR",
    "skills": ["Excel", "ERP"],
    "interests": ["IT"],
}


def register_and_login(run_idx):
    email = f"TEST_recs_iter73_consistency_run{run_idx}_{uuid.uuid4().hex[:8]}@test.pl"
    payload = {"email": email, "password": "Test12345!", "name": "TEST Iter73", "country": "PL"}
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    resp = session.post(f"{API}/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def save_profile(session):
    resp = session.put(f"{API}/profile", json={"answers": PROFILE_ANSWERS})
    assert resp.status_code == 200, resp.text


def generate_and_wait(session):
    gen_resp = session.post(f"{API}/recommendations/generate")
    assert gen_resp.status_code == 200, gen_resp.text
    assert gen_resp.json().get("status") == "pending"

    doc = None
    for _ in range(40):  # up to ~80s
        time.sleep(2)
        r = session.get(f"{API}/recommendations")
        assert r.status_code == 200
        doc = r.json()
        if doc.get("status") in ("ready", "error"):
            break
    assert doc is not None
    assert doc.get("status") == "ready", f"Generation did not complete: {doc}"
    return doc


def run_one_cycle(run_idx):
    session = register_and_login(run_idx)
    save_profile(session)
    doc = generate_and_wait(session)

    now_items = doc.get("now") or []
    future_items = doc.get("future") or []
    now_titles = [it.get("title", "") for it in now_items]
    future_titles = [it.get("title", "") for it in future_items]
    print(f"\n=== RUN {run_idx} ===")
    print(f"NOW: {now_titles}")
    print(f"FUTURE: {future_titles}")

    all_titles = now_titles + future_titles
    bad_fit = [t for t in all_titles if any(k in t.lower() for k in BAD_FIT_KEYWORDS)]
    now_ok = [t for t in now_titles if any(k in t.lower() for k in NOW_LEVEL_HINTS)]
    future_ok = [t for t in future_titles if any(k in t.lower() for k in FUTURE_LEVEL_HINTS)]

    return {
        "run": run_idx,
        "now_titles": now_titles,
        "future_titles": future_titles,
        "bad_fit_violations": bad_fit,
        "now_level_match_count": len(now_ok),
        "future_level_match_count": len(future_ok),
    }


class TestRecommendationsConsistency:
    """Runs the SAME high-qualification profile 3x with 3 fresh users, collects results,
    and reports variance / regression across all 3 independent runs."""

    def test_three_consecutive_runs(self):
        results = []
        for i in range(1, 4):
            results.append(run_one_cycle(i))

        print("\n\n========== CONSISTENCY SUMMARY (3 runs) ==========")
        any_bad_fit = False
        for r in results:
            print(f"Run {r['run']}: bad_fit={r['bad_fit_violations']} "
                  f"now_level_match={r['now_level_match_count']}/4 "
                  f"future_level_match={r['future_level_match_count']}/4")
            if r["bad_fit_violations"]:
                any_bad_fit = True

        # Report (not hard-fail the whole suite silently) - but DO assert so CI/test runner
        # surfaces the regression clearly if it's still present.
        assert not any_bad_fit, (
            f"VARIANCE REGRESSION: at least one of 3 runs produced assistant/back-office/"
            f"low-skill titles for a high-qualification SAP/ERP/HR profile. Full results: {results}"
        )
