from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict
from typing import Annotated, Any, Optional, List
from datetime import datetime, timezone, timedelta, date
from urllib.parse import quote, quote_plus, urlparse, urlencode
from pathlib import Path
from bson import ObjectId
from email.mime.text import MIMEText
from html import escape
from html.parser import HTMLParser
import asyncio
import base64
import bcrypt
import httpx
import ipaddress
import jwt
import json
import logging
import os
import re
import secrets as pysecrets
import uuid
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone  # noqa: E402

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"
LLM_KEY = os.environ['ANTHROPIC_API_KEY']
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
ANALYSIS_MODEL = ("anthropic", "claude-haiku-5-5")
FAST_MODEL = ("anthropic", "claude-haiku-5-5")

# Emergent managed email proxy (password-reset codes). This is a CONSTANT, never read
# from the environment, so it survives deployment. The key itself is provisioned by
# Emergent; if it isn't set yet, email sends fail gracefully (503) instead of crashing boot.
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Zawodowcy")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

# Gmail API (OAuth) — lets the owner send transactional emails (password-reset codes)
# straight from their own Gmail address instead of the Emergent managed proxy above.
# Preferred when configured; falls back to the Emergent proxy if Gmail isn't connected
# yet or a send attempt fails. Credentials come from Google Cloud Console (OAuth client);
# the refresh token is obtained once via the admin-only connect flow below and stored in
# MongoDB (never in .env), since it is generated at runtime, not provisioned up front.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_GMAIL_SENDER = os.environ.get("GOOGLE_GMAIL_SENDER", "support.zawodowcy@gmail.com")
BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL", "").rstrip("/")
GOOGLE_REDIRECT_URI = f"{BACKEND_PUBLIC_URL}/api/auth/google/callback"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("reset")

app = FastAPI()


@app.get("/health", include_in_schema=False)
@app.head("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


api = APIRouter(prefix="/api")
_bg_tasks: set = set()


def spawn(coro):
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)
bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------- models
PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: dict):
        return cls.model_validate(doc)

    def to_mongo(self) -> dict:
        d = self.model_dump(by_alias=True, exclude_none=False)
        if d.get("_id") is None:
            d.pop("_id", None)
        return d


class UserDoc(BaseDocument):
    email: str
    name: str = ""
    password_hash: str
    role: str = "user"
    created_at: str
    premium: Optional[dict] = None
    streak: Optional[dict] = None
    country: str = "PL"


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=200)
    name: str = ""
    country: Optional[str] = None


class ForgotPasswordIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=200)


class ProfileIn(BaseModel):
    answers: dict


class RoadmapIn(BaseModel):
    career_id: str


class CustomPathIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    qualifications: str = Field(default="", max_length=1000)


class TaskToggle(BaseModel):
    done: bool


class DailyPlanSettingsIn(BaseModel):
    time_mode: str  # "daily" | "weekly"
    time_value: int = Field(gt=0, le=600)
    free_days: List[int] = Field(default_factory=list)  # 0=poniedziałek .. 6=niedziela


class CountryIn(BaseModel):
    country: str


# ---------------------------------------------------------------- auth helpers
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def make_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + timedelta(days=30)}, JWT_SECRET, algorithm=JWT_ALG)


async def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UserDoc:
    denied = HTTPException(status_code=401, detail="Sesja wygasła. Zaloguj się ponownie.")
    if not cred:
        raise denied
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.InvalidTokenError:
        raise denied
    uid = payload.get("sub")
    if not uid or not ObjectId.is_valid(uid):
        raise denied
    doc = await db.users.find_one({"_id": ObjectId(uid)})
    if not doc:
        raise denied
    return UserDoc.from_mongo(doc)


async def touch_streak(user: UserDoc) -> dict:
    """Updates the daily login streak. Consecutive days +1; missing exactly one day
    offers a same-day restore (via ad); missing more resets to a fresh streak of 1."""
    s = user.streak or {}
    today = date.today()
    if s.get("last_seen") == today.isoformat():
        return s
    count = s.get("count", 0)
    best = s.get("best", 0)
    pending_restore = False
    lost_count = s.get("lost_count", 0)
    last_counted_raw = s.get("last_counted")
    last_counted = date.fromisoformat(last_counted_raw) if last_counted_raw else None
    if last_counted is None:
        count = 1
        last_counted = today
    else:
        gap = (today - last_counted).days
        if gap == 1:
            count += 1
            last_counted = today
        elif gap == 2:
            pending_restore = True
            lost_count = count
            # keep count/last_counted untouched — restorable only today
        elif gap >= 3:
            count = 1
            last_counted = today
    best = max(best, count)
    new_streak = {"count": count, "best": best, "last_counted": last_counted.isoformat(),
                  "last_seen": today.isoformat(), "pending_restore": pending_restore, "lost_count": lost_count}
    await db.users.update_one({"_id": ObjectId(user.id)}, {"$set": {"streak": new_streak}})
    return new_streak


async def public_user(u: UserDoc) -> dict:
    profile = await db.profiles.find_one({"user_id": u.id}, {"_id": 0, "user_id": 1})
    streak = await touch_streak(u)
    country = u.country if u.country in COUNTRY_CONFIG else "PL"
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "has_profile": bool(profile),
            "is_premium": bool(u.premium and u.premium.get("active")), "streak": streak, "country": country,
            "roadmap_generations_used": await roadmap_gen_used(u.id), "roadmap_generations_limit": PREMIUM_MONTHLY_GENERATIONS}


# ---------------------------------------------------------------- LLM helpers
async def ask_llm(model: tuple, system: str, prompt: str) -> dict:
    # claude-haiku-5-5 (and other "extended thinking" capable Anthropic models) generate internal
    # reasoning tokens by default that are billed as output but never surfaced via TextDelta — this
    # was silently inflating output tokens ~5x (confirmed: 10 472 -> 2 049 output tokens for an
    # identical recommendations call once thinking is disabled). We only ever need the final JSON,
    # never the reasoning trace, so disable it outright for Anthropic and cap max_tokens sanely
    # (real payloads measure well under 2k tokens; 4k leaves headroom without paying for runaway output).
    params = {"max_tokens": 4096}
    messages = None
    if model[0] == "anthropic":
        params["thinking"] = {"type": "disabled"}
        # SYSTEM_PL is byte-for-byte identical on every single call in the whole app — mark it as an
        # Anthropic prompt-cache breakpoint so repeated calls within the cache window are billed at
        # ~10% of the normal input-token price instead of full price every time.
        messages = [{"role": "system", "content": system, "cache_control": {"type": "ephemeral"}}]
    chat = LlmChat(api_key=LLM_KEY, session_id=str(uuid.uuid4()), system_message=system, initial_messages=messages).with_model(*model).with_params(**params)
    text = ""
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            text += ev.content
        elif isinstance(ev, StreamDone):
            break
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON in LLM response")
    return json.loads(m.group(0))


SYSTEM_PL = (
    "Jesteś doświadczonym polskim doradcą zawodowym i analitykiem rynku pracy. "
    "Znasz aktualne oferty pracy publikowane w Polsce na Pracuj.pl, OLX Praca, LinkedIn, Indeed i w urzędach pracy, "
    "w tym typowe wymagania pracodawców. Odpowiadasz WYŁĄCZNIE poprawnym JSON-em, bez komentarzy i bez markdown. "
    "Wszystkie teksty po polsku, zawsze PEŁNYMI, płynnymi zdaniami — jak doświadczony doradca piszący zwięzłą, ale konkretną i pomocną "
    "poradę, NIGDY jako urwane frazy czy pojedyncze słowa po myślnikach/przecinkach. Trzymaj się podanej liczby zdań i orientacyjnej "
    "liczby słów dla każdego pola — to realny budżet długości, nie podłoga ani sufit do naciągania: pisz dokładnie tyle, ile potrzeba "
    "na pełne, sensowne zdanie w tym limicie, bez lania wody, ale też bez ucinania w połowie myśli."
)

# Country picker: language of generated AI content, local job-market context (job boards, the
# equivalent of "urząd pracy"/labour office with its real schemes) and currency all follow this.
COUNTRY_CONFIG = {
    "PL": {"name": "Polska", "language_name": "polskim", "currency_fmt": "np. 6 000 – 8 500 zł brutto",
           "job_portals": "Pracuj.pl, OLX Praca, LinkedIn, Indeed", "employment_agency": "Urząd Pracy (bon szkoleniowy, KFS, staż, dofinansowanie studiów podyplomowych)"},
    "US": {"name": "USA", "language_name": "angielskim (amerykańska odmiana)", "currency_fmt": "e.g. $55,000 – $75,000 / year",
           "job_portals": "LinkedIn, Indeed, ZipRecruiter, Glassdoor", "employment_agency": "state workforce agencies, e.g. CareerOneStop and WIOA-funded training programs"},
    "GB": {"name": "Wielka Brytania", "language_name": "angielskim (brytyjska odmiana)", "currency_fmt": "e.g. £28,000 – £38,000 / year",
           "job_portals": "LinkedIn, Indeed, Reed, TotalJobs", "employment_agency": "Jobcentre Plus and the National Careers Service (Skills Bootcamps funding)"},
    "AU": {"name": "Australia", "language_name": "angielskim (australijska odmiana)", "currency_fmt": "e.g. A$65,000 – A$85,000 / year",
           "job_portals": "SEEK, LinkedIn, Indeed", "employment_agency": "Services Australia / jobactive providers and Skills Checkpoint programs"},
    "DE": {"name": "Niemcy", "language_name": "niemieckim", "currency_fmt": "z.B. 3.200 – 4.500 € brutto/Monat",
           "job_portals": "LinkedIn, Indeed, StepStone, Xing", "employment_agency": "Agentur für Arbeit (Bildungsgutschein)"},
    "NL": {"name": "Holandia", "language_name": "niderlandzkim", "currency_fmt": "bijv. €3.000 – €4.200 bruto/maand",
           "job_portals": "LinkedIn, Indeed, Nationale Vacaturebank", "employment_agency": "UWV (STAP-budget)"},
}


def system_message(country: str) -> str:
    cfg = COUNTRY_CONFIG.get(country) or COUNTRY_CONFIG["PL"]
    if country == "PL" or country not in COUNTRY_CONFIG:
        return SYSTEM_PL
    return SYSTEM_PL + (
        f" WAŻNE: mimo że powyższe instrukcje są po polsku, Twoja odpowiedź (cała treść w JSON) musi być CAŁKOWICIE napisana "
        f"w języku {cfg['language_name']}, naturalnie jak dla native speakera — żadnego polskiego tekstu w odpowiedzi. "
        f"Dopasuj WSZYSTKIE realia rynku pracy do kraju: {cfg['name']}. Oferty pracy i nazwy stanowisk jak na portalach "
        f"{cfg['job_portals']}. Zamiast polskiego urzędu pracy/KFS/bonu szkoleniowego używaj lokalnego odpowiednika: "
        f"{cfg['employment_agency']}. Widełki wynagrodzeń podawaj w lokalnej walucie, np. w formacie: {cfg['currency_fmt']}. "
        f"NIGDY nie używaj złotówek ani polskich instytucji dla tego kraju."
    )


def profile_text(answers: dict) -> str:
    return json.dumps(answers, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- shared AI-content cache
# Career roadmaps, career descriptions and weekly study plans are expensive AI generations
# that are, content-wise, the SAME for every user who picks the same career (in the same
# country/language). Instead of paying for a fresh AI generation per user, we generate once,
# persist the result keyed by (country, normalized title) in `career_templates`, and clone it
# for every later user who picks that same career — only a small, cheap AI call (or none) is
# then needed to personalize which steps that specific user already has done.
def normalize_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def career_cache_key(title: str, country: str) -> str:
    return f"{(country or 'PL').upper()}::{normalize_title(title)}"


def clone_milestones(milestones: list) -> list:
    """Deep-ish copy of a cached template's milestones for a brand-new user: same ids/content,
    every task reset to NOT done (per-user progress is decided separately, see mark_done_tasks)."""
    return [{**m, "tasks": [{**t, "done": False} for t in m.get("tasks", [])]} for m in milestones]


def find_task_in_milestones(milestones: list, task_id: str) -> Optional[dict]:
    for m in milestones:
        for t in m.get("tasks", []):
            if t["id"] == task_id:
                return t
    return None


def qualifications_text_from_answers(answers: dict) -> str:
    """Pulls out only the quiz fields relevant to 'what does this person already know/have',
    used for the cheap already-done-marking call — never the full survey (mood/preferences etc.
    don't matter for that decision)."""
    keys = ["current_job", "education", "education_field", "certificates", "certificates_other",
            "languages", "languages_level", "achievements",
            "recznie_wskazane_stanowisko_docelowe", "kwalifikacje_do_tego_stanowiska"]
    parts = []
    for k in keys:
        v = answers.get(k)
        if not v:
            continue
        parts.append(f"{k}: {', '.join(v)}" if isinstance(v, list) else f"{k}: {v}")
    return "; ".join(parts)


async def mark_done_tasks(milestones: list, qualifications_text: str, country: str) -> set:
    """Cheap, short follow-up call used only when a cached roadmap template is reused: given the
    (already generated) task list and this specific user's qualifications, decide which task ids
    they should already have ticked off — far smaller/cheaper than regenerating the whole path."""
    if not qualifications_text.strip():
        return set()
    compact = [{"id": t["id"], "title": t.get("title", ""), "type": t.get("type", "other")}
               for m in milestones for t in m.get("tasks", [])]
    if not compact:
        return set()
    prompt = f"""Użytkownik ma już: {qualifications_text}
Oto lista zadań do zdobycia na ścieżce kariery (id, tytuł, typ):
{json.dumps(compact, ensure_ascii=False)}
Które z tych zadań użytkownik już spełnia na podstawie posiadanych kwalifikacji/wykształcenia/doświadczenia? Zwróć TYLKO JSON:
{{"done_ids": ["id1", "id2"]}}"""
    try:
        data = await ask_llm(FAST_MODEL, system_message(country), prompt)
        valid_ids = {c["id"] for c in compact}
        return {i for i in data.get("done_ids", []) if i in valid_ids}
    except Exception:
        logger.exception("mark_done_tasks failed")
        return set()


async def apply_cached_roadmap(user_id: str, job_id: str, milestones: list, qualifications_text: str, country: str):
    """Fast path for a roadmap cache hit: no full generation, just a small done-marking call."""
    try:
        done_ids = await mark_done_tasks(milestones, qualifications_text, country)
        for m in milestones:
            for t in m.get("tasks", []):
                if t["id"] in done_ids:
                    t["done"] = True
        await db.roadmaps.update_one({"user_id": user_id, "job_id": job_id},
                                     {"$set": {"status": "ready", "milestones": milestones, "updated_at": now_iso()}})
    except Exception as e:
        logger.exception("apply_cached_roadmap failed")
        await db.roadmaps.update_one({"user_id": user_id, "job_id": job_id},
                                     {"$set": {"status": "error", "error": str(e)[:200]}})


async def validate_profession(title: str) -> tuple[bool, str]:
    """Blocks custom-path titles that are illegal/criminal activities, or that simply
    aren't a real job/profession at all (so the roadmap generator never has to hallucinate
    a path for nonsense input). Fails OPEN (allows) if the classifier call itself errors,
    so a transient API hiccup never blocks a legitimate user."""
    prompt = f"""Oceń wpisany przez użytkownika tekst: "{title}"
Czy to prawdziwy, legalny zawód lub stanowisko pracy, które realnie istnieje na rynku pracy w Polsce?
Odpowiedz "nie" (valid=false), jeśli to:
- czynność przestępcza lub nielegalna w Polsce (np. złodziej, zabójca/płatny zabójca, gwałciciel, handlarz narkotykami,
  "pirat drogowy"/nielegalny przewoźnik, oszust, haker przestępczy, stręczyciel, prostytutka/prostytucja, przemytnik),
- cokolwiek, co NIE jest zawodem/stanowiskiem pracy (np. przedmiot, zwierzę, jedzenie, miejsce, uczucie, czynność
  abstrakcyjna typu "być", zaimek typu "ja", losowy tekst, wulgaryzm, puste/bez sensu).
W razie wątpliwości, czy to realny i legalny zawód, odpowiedz "tak" (valid=true) — blokuj tylko oczywiste przypadki.
Zwróć TYLKO JSON: {{"valid": true/false, "reason": "krótkie uzasadnienie po polsku (max 1 zdanie), pokazywane użytkownikowi tylko gdy valid=false"}}"""
    try:
        data = await ask_llm(FAST_MODEL, SYSTEM_PL, prompt)
        return bool(data.get("valid", True)), str(data.get("reason") or "")
    except Exception:
        logger.exception("profession validation failed, failing open")
        return True, ""


def job_links(title: str) -> list:
    q = quote_plus(title)
    slug = quote(title.lower().replace(" ", "-"))
    return [
        {"label": "Pracuj.pl", "url": f"https://www.pracuj.pl/praca/{quote(title)};kw"},
        {"label": "OLX Praca", "url": f"https://www.olx.pl/praca/q-{slug}/"},
        {"label": "LinkedIn", "url": f"https://www.linkedin.com/jobs/search/?keywords={q}&location=Polska"},
        {"label": "Indeed", "url": f"https://pl.indeed.com/jobs?q={q}"},
    ]


PLATFORM_SEARCH = {
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "coursera": "https://www.coursera.org/search?query={q}",
    "udemy": "https://www.udemy.com/courses/search/?q={q}",
    "linkedin learning": "https://www.linkedin.com/learning/search?keywords={q}",
    "edx": "https://www.edx.org/search?q={q}",
    "google": "https://www.google.com/search?q={q}",
}


def resource_url(r: dict, city: str) -> str:
    rtype = (r.get("type") or "").lower()
    platform = (r.get("platform") or "").lower()
    q = r.get("query") or r.get("title") or ""
    if rtype == "youtube":
        return PLATFORM_SEARCH["youtube"].format(q=quote_plus(q))
    if rtype == "urzad_pracy":
        return PLATFORM_SEARCH["google"].format(q=quote_plus(f"{q} urząd pracy {city}".strip()))
    if rtype == "studies":
        return PLATFORM_SEARCH["google"].format(q=quote_plus(f"rekrutacja {q} {city}".strip()))
    for key, tpl in PLATFORM_SEARCH.items():
        if key in platform:
            return tpl.format(q=quote_plus(q))
    return PLATFORM_SEARCH["google"].format(q=quote_plus(q))


# ---------------------------------------------------------------- email (password reset)
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def _gmail_refresh_access_token() -> Optional[str]:
    """Exchanges the stored refresh token for a short-lived Gmail API access token.
    Returns None if Gmail was never connected (no refresh token saved yet)."""
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return None
    doc = await db.integration_tokens.find_one({"provider": "gmail_send"})
    if not doc or not doc.get("refresh_token"):
        return None
    async with httpx.AsyncClient(timeout=20) as client_http:
        resp = await client_http.post(GOOGLE_TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": doc["refresh_token"], "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        logger.warning(f"Gmail token refresh failed: {resp.status_code} {resp.text}")
        return None
    return resp.json().get("access_token")


async def _gmail_send(*, to: str, subject: str, html: str, reply_to: str | None = None) -> Optional[str]:
    """Sends via Gmail API using the owner's connected account. Returns the Gmail
    message id on success, or None if Gmail isn't connected / the send failed — callers
    fall back to the Emergent managed proxy in that case."""
    access_token = await _gmail_refresh_access_token()
    if not access_token:
        return None
    msg = MIMEText(html, "html", "utf-8")
    msg["To"] = to
    msg["From"] = f"{EMAIL_FROM_NAME} <{GOOGLE_GMAIL_SENDER}>"
    msg["Subject"] = subject
    if reply_to or EMAIL_REPLY_TO:
        msg["Reply-To"] = reply_to or EMAIL_REPLY_TO
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    try:
        async with httpx.AsyncClient(timeout=30) as client_http:
            resp = await client_http.post(GMAIL_SEND_URL, headers={"Authorization": f"Bearer {access_token}"}, json={"raw": raw})
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        logger.warning(f"Gmail send failed, falling back: {e}")
        return None


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None) -> str | None:
    """Internal helper — html always comes from our own server-side templates below,
    never from request input (G4). Tries the owner's connected Gmail account first
    (if any), then falls back to the Emergent managed email proxy."""
    _assert_safe_email(subject, html)
    gmail_id = await _gmail_send(to=to, subject=subject, html=html, reply_to=reply_to)
    if gmail_id:
        return gmail_id
    if not EMAIL_KEY:
        logger.warning("Neither Gmail nor EMERGENT_EMAIL_KEY configured — email not sent")
        raise HTTPException(status_code=503, detail="Wysyłka e-maili jest chwilowo niedostępna. Spróbuj ponownie za chwilę.")
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client_http:
            resp = await client_http.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            code = e.response.json().get("code", "")
        except ValueError:
            code = ""
        if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning(f"Email paused: {code} ({e.response.status_code}): {e.response.json().get('message', '')}")
            raise HTTPException(status_code=503, detail="Wysyłka e-maili jest chwilowo niedostępna.")
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail="Nie udało się wysłać e-maila.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        raise HTTPException(status_code=500, detail="Nie udało się wysłać e-maila.")


def reset_code_email_html(code: str, name: str) -> str:
    greeting = f"Cześć {escape(name)}," if name else "Cześć,"
    return (
        '<table role="presentation" width="100%" style="background:#F7F7F8;padding:32px 0">'
        '<tr><td align="center">'
        '<table role="presentation" width="100%" style="max-width:420px;background:#FFFFFF;border-radius:16px;overflow:hidden;'
        'font-family:Arial,sans-serif">'
        '<tr><td style="background:#FA5252;padding:24px;text-align:center">'
        '<span style="color:#FFFFFF;font-size:22px;font-weight:800">Zawodowcy</span></td></tr>'
        f'<tr><td style="padding:28px 28px 8px 28px;color:#1A1A1A;font-size:15px;line-height:22px">{greeting}</td></tr>'
        '<tr><td style="padding:0 28px 8px 28px;color:#1A1A1A;font-size:15px;line-height:22px">'
        'otrzymaliśmy prośbę o zresetowanie hasła do Twojego konta w aplikacji Zawodowcy. Wpisz poniższy kod w aplikacji, '
        'aby ustawić nowe hasło:</td></tr>'
        '<tr><td style="padding:16px 28px" align="center">'
        f'<span style="display:inline-block;background:#FFE3E3;color:#C92A2A;font-size:32px;font-weight:800;letter-spacing:8px;'
        f'padding:14px 20px;border-radius:12px">{escape(code)}</span></td></tr>'
        '<tr><td style="padding:0 28px 24px 28px;color:#666666;font-size:13px;line-height:19px">'
        'Kod jest ważny przez 15 minut. Jeśli to nie Ty prosiłeś/aś o reset hasła, po prostu zignoruj tę wiadomość — '
        'Twoje hasło pozostanie bez zmian.</td></tr>'
        '<tr><td style="padding:16px 28px;border-top:1px solid #EFEFEF;color:#999999;font-size:11px">'
        'Wiadomość wysłana przez Zawodowcy. Nigdy nie prosimy o podanie hasła przez e-mail.</td></tr>'
        '</table></td></tr></table>'
    )


# ---------------------------------------------------------------- auth routes
@api.post("/auth/register", status_code=201)
async def register(data: Credentials):
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Podaj poprawny adres e-mail.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Konto z tym adresem już istnieje.")
    role = "admin" if email in ADMIN_EMAILS else "user"
    grant = await db.premium_grants.find_one({"email": email})
    premium = {"active": True, "plan": "gift", "since": now_iso(), "granted_by": grant.get("granted_by")} if grant else None
    country = (data.country or "").strip().upper()
    if country not in COUNTRY_CONFIG:
        country = "PL"
    user = UserDoc(email=email, name=data.name.strip(), password_hash=hash_pw(data.password), role=role,
                   premium=premium, created_at=now_iso(), country=country)
    try:
        res = await db.users.insert_one(user.to_mongo())
    except DuplicateKeyError:
        raise HTTPException(409, "Konto z tym adresem już istnieje.")
    if grant:
        await db.premium_grants.delete_one({"email": email})
    user.id = str(res.inserted_id)
    return {"access_token": make_token(user.id), "user": await public_user(user)}


@api.post("/auth/login")
async def login(data: Credentials):
    ident = data.email.strip().lower()
    query = {"email": ident} if "@" in ident else {"username_lower": ident}
    doc = await db.users.find_one(query)
    if not doc or not verify_pw(data.password, doc["password_hash"]):
        raise HTTPException(401, "Nieprawidłowy login/e-mail lub hasło.")
    user = UserDoc.from_mongo(doc)
    return {"access_token": make_token(user.id), "user": await public_user(user)}


RESET_CODE_TTL_MIN = 15
RESET_COOLDOWN_SEC = 60
RESET_MAX_ATTEMPTS = 5


@api.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordIn):
    """Always answers with the same generic message, whether or not the e-mail exists,
    so this endpoint can never be used to discover which e-mails have an account."""
    email = data.email.strip().lower()
    generic = {"ok": True, "message": "Jeśli to konto istnieje, wysłaliśmy na podany adres e-mail kod do zresetowania hasła."}
    if "@" not in email:
        return generic
    doc = await db.users.find_one({"email": email})
    if not doc:
        return generic
    last_req = doc.get("reset_requested_at")
    if last_req:
        try:
            if (datetime.now(timezone.utc) - datetime.fromisoformat(last_req)).total_seconds() < RESET_COOLDOWN_SEC:
                return generic  # within cooldown — don't spam another send
        except ValueError:
            pass
    code = f"{pysecrets.randbelow(1_000_000):06d}"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=RESET_CODE_TTL_MIN)).isoformat()
    logger.info(f"password reset code for {email}: {code} (delivered via email; logged here only as a fallback while email delivery is being provisioned)")
    await db.users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"reset_code_hash": hash_pw(code), "reset_code_expires": expires, "reset_attempts": 0, "reset_requested_at": now_iso()}},
    )
    try:
        await send_email(to=email, subject="Kod do zresetowania hasła — Zawodowcy", html=reset_code_email_html(code, doc.get("name", "")))
    except HTTPException:
        logger.exception("forgot-password: email send failed")
    return generic


@api.post("/auth/reset-password")
async def reset_password(data: ResetPasswordIn):
    email = data.email.strip().lower()
    invalid = HTTPException(400, "Nieprawidłowy lub wygasły kod. Poproś o nowy.")
    doc = await db.users.find_one({"email": email})
    if not doc or not doc.get("reset_code_hash") or not doc.get("reset_code_expires"):
        raise invalid
    if doc.get("reset_attempts", 0) >= RESET_MAX_ATTEMPTS:
        raise HTTPException(400, "Zbyt wiele nieudanych prób. Poproś o nowy kod.")
    if datetime.now(timezone.utc) > datetime.fromisoformat(doc["reset_code_expires"]):
        raise invalid
    if not verify_pw(data.code.strip(), doc["reset_code_hash"]):
        await db.users.update_one({"_id": doc["_id"]}, {"$inc": {"reset_attempts": 1}})
        raise invalid
    await db.users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"password_hash": hash_pw(data.new_password)},
         "$unset": {"reset_code_hash": "", "reset_code_expires": "", "reset_attempts": "", "reset_requested_at": ""}},
    )
    user = UserDoc.from_mongo(await db.users.find_one({"_id": doc["_id"]}))
    return {"access_token": make_token(user.id), "user": await public_user(user)}


@api.get("/auth/me")
async def me(user: UserDoc = Depends(current_user)):
    return await public_user(user)


@api.post("/streak/restore")
async def restore_streak(user: UserDoc = Depends(current_user)):
    s = user.streak or {}
    if not s.get("pending_restore"):
        raise HTTPException(400, "Nie masz utraconej serii do przywrócenia.")
    today = date.today()
    count = s.get("lost_count", 0) + 1
    best = max(s.get("best", 0), count)
    new_streak = {"count": count, "best": best, "last_counted": today.isoformat(), "last_seen": today.isoformat(),
                  "pending_restore": False, "lost_count": 0}
    await db.users.update_one({"_id": ObjectId(user.id)}, {"$set": {"streak": new_streak}})
    return {"streak": new_streak}


# ---------------------------------------------------------------- profile
@api.put("/profile")
async def save_profile(data: ProfileIn, user: UserDoc = Depends(current_user)):
    await db.profiles.update_one(
        {"user_id": user.id},
        {"$set": {"user_id": user.id, "answers": data.answers, "updated_at": now_iso()}},
        upsert=True,
    )
    return {"ok": True}


@api.get("/profile")
async def get_profile(user: UserDoc = Depends(current_user)):
    doc = await db.profiles.find_one({"user_id": user.id}, {"_id": 0})
    return doc or {"answers": None}


@api.get("/account/countries")
async def list_countries():
    return {"countries": [{"code": c, "name": cfg["name"]} for c, cfg in COUNTRY_CONFIG.items()]}


@api.patch("/account/country")
async def set_country(data: CountryIn, user: UserDoc = Depends(current_user)):
    code = (data.country or "").upper()
    if code not in COUNTRY_CONFIG:
        raise HTTPException(400, "Nieznany kraj.")
    await db.users.update_one({"_id": ObjectId(user.id)}, {"$set": {"country": code}})
    user = UserDoc.from_mongo(await db.users.find_one({"_id": ObjectId(user.id)}))
    return await public_user(user)


# ---------------------------------------------------------------- recommendations
MODE_RULES = {
    "search": "TRYB: Szukam swojej drogi — proponuj zawody najlepiej dopasowane do umiejętności, zainteresowań i charakteru (także w obecnej branży).",
    "industry": (
        "TRYB: ZMIANA BRANŻY — NIE proponuj stanowisk w obecnej branży użytkownika (patrz current_job). Proponuj zawody w INNYCH branżach, "
        "najlepiej w tych z target_industries, które wykorzystują jego przenośne umiejętności (np. obsługa programów, organizacja, kontakt z klientem, języki). "
        "Unikaj ról, których rdzeniem są te same obowiązki co obecnie (np. księgowa → NIE analityk finansowy/kontroler/fintech nawet w innej branży). "
        "W polu 'why' wyjaśnij, które jego umiejętności przenoszą się do nowej branży."
    ),
    "life": (
        "TRYB: NOWY ROZDZIAŁ — ZMIANA ŻYCIA. Użytkownik chce zacząć od nowa. NIE proponuj niczego w jego obecnej branży ani zawodów "
        "o podobnym charakterze obowiązków (np. księgowa → NIE analityk finansowy, NIE kontroler, NIE kadry). Proponuj ZUPEŁNIE INNY rodzaj pracy i rytm dnia, "
        "dopasowany do pomysłu/marzenia (idea), kuszących kierunków (new_directions), pasji (loves), wartości (life_values) i tego, czego nie lubi. "
        "Jeśli użytkownik ma konkretny pomysł (idea) i jest on realny — niech będzie pierwszą propozycją w odpowiedniej kategorii. "
        "Możesz proponować też własną działalność, rzemiosło, pracę z ludźmi/zwierzętami/naturą, pracę zdalną czy za granicą. "
        "'now' = nowe zawody, w które da się wejść szybko (krótki kurs, praca od zaraz, przyuczenie), 'future' = wymagające dłuższej nauki. "
        "W 'summary' zacznij od motywującego zdania o nowym początku."
    ),
}


async def run_recommendations(user_id: str, answers: dict, job_id: str, country: str = "PL"):
    # Compact JSON keys below (t/i/s/w/m/sa/d/r/g) exist purely to cut OUTPUT tokens: this call
    # repeats the same 9 fields across 10 career objects, so every character saved on field NAMES
    # (not content) is pure waste avoided x10. Mapped back to the real field names the app/DB use
    # right after parsing — no frontend or schema change needed.
    prompt = f"""Profil użytkownika (odpowiedzi z ankiety):
{profile_text(answers)}

Zaproponuj zawody dopasowane do tej osoby, w dwóch kategoriach:
- "now": 5 zawodów, które może wykonywać JUŻ TERAZ z obecnymi umiejętnościami (wymagania typowych ofert spełnia lub prawie spełnia),
- "future": 5 zawodów, które do niej pasują, ale wymagają zdobycia nowych umiejętności.
Nie ograniczaj się do oczywistych zawodów — uwzględnij też mniej znane stanowiska realnie występujące w polskich ogłoszeniach
(np. wdrożeniowiec systemów ERP, specjalista ds. wdrożeń, koordynator logistyki, analityk danych, specjalista ds. obsługi klienta B2B itp.).
Weź pod uwagę to, czego użytkownik nie lubi, jego charakter i odporność zawodu na automatyzację przez AI.

{MODE_RULES.get(answers.get("reset_mode") or "search", MODE_RULES["search"])}

Aby oszczędzić tokeny, użyj KRÓTKICH kluczy JSON dokładnie jak w przykładzie (bez pełnych nazw pól). Zwróć JSON:
{{"summary": "2 pełne zdania (ok. 35-45 słów) — zwięzły, konkretny opis profilu użytkownika: mocne strony i kierunek, w jakim warto szukać pracy",
 "now": [{{"t": "nazwa stanowiska jak w ogłoszeniach", "i": "branża", "s": "1 pełne zdanie (ok. 15-20 słów) — czym dokładnie zajmuje się osoba na tym stanowisku na co dzień",
          "w": "1 pełne zdanie (ok. 15-20 słów) — dlaczego akurat ten zawód realnie pasuje do TEJ osoby",
          "m": 0-100, "sa": "np. 6 000 – 8 500 zł brutto", "d": "wysoki|średni|niski", "r": "niskie|średnie|wysokie",
          "g": ["czego jeszcze brakuje, max 2 krótkie frazy"]}}],
 "future": [ ...ten sam format... ]}}"""
    try:
        data = await ask_llm(ANALYSIS_MODEL, system_message(country), prompt)
        key_map = {"t": "title", "i": "industry", "s": "summary", "w": "why", "m": "match",
                   "sa": "salary", "d": "demand", "r": "ai_risk", "g": "missing_skills"}
        for cat in ("now", "future"):
            items = data.get(cat) or []
            expanded = []
            for it in items:
                full = {key_map.get(k, k): v for k, v in it.items()}
                full["id"] = uuid.uuid4().hex[:12]
                full["category"] = cat
                full["country"] = country
                expanded.append(full)
            data[cat] = expanded
        # This job can take up to a minute. If the user added a custom career (POST /careers/custom)
        # while it was still running, that career was $push-ed into "now" in the meantime — re-read
        # it right before this overwrite and merge it back in, so this $set never silently wipes it out.
        current = await db.recommendations.find_one({"user_id": user_id}, {"_id": 0, "now": 1})
        custom_now = [c for c in (current or {}).get("now", []) if c.get("custom")]
        await db.recommendations.update_one(
            {"user_id": user_id, "job_id": job_id},
            {"$set": {"status": "ready", "mode": answers.get("reset_mode") or "search", "summary": data.get("summary", ""),
                      "now": custom_now + data["now"], "future": data["future"], "updated_at": now_iso()}},
        )
    except Exception as e:
        logger.exception("recommendations failed")
        await db.recommendations.update_one({"user_id": user_id, "job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:200]}})


@api.post("/recommendations/generate")
async def generate_recommendations(user: UserDoc = Depends(current_user)):
    prof = await db.profiles.find_one({"user_id": user.id})
    if not prof:
        raise HTTPException(400, "Najpierw wypełnij ankietę.")
    job_id = uuid.uuid4().hex
    await db.recommendations.update_one(
        {"user_id": user.id},
        {"$set": {"user_id": user.id, "status": "pending", "job_id": job_id, "started_at": now_iso(), "country": user.country}},
        upsert=True,
    )
    spawn(run_recommendations(user.id, prof["answers"], job_id, user.country))
    return {"status": "pending"}


@api.get("/recommendations")
async def get_recommendations(user: UserDoc = Depends(current_user)):
    doc = await db.recommendations.find_one({"user_id": user.id}, {"_id": 0})
    if doc and await expire_stale(db.recommendations, user.id, doc):
        doc["status"] = "error"
    return doc or {"status": "none"}


async def expire_stale(coll, user_id: str, doc: dict) -> bool:
    """Jobs lost on a server restart would stay pending forever; fail them after 4 minutes."""
    if doc.get("status") != "pending" or not doc.get("started_at"):
        return False
    if datetime.now(timezone.utc) - datetime.fromisoformat(doc["started_at"]) < timedelta(minutes=4):
        return False
    await coll.update_one({"user_id": user_id, "job_id": doc.get("job_id")}, {"$set": {"status": "error"}})
    return True


async def find_career(user_id: str, career_id: str) -> tuple[dict, str]:
    doc = await db.recommendations.find_one({"user_id": user_id}, {"_id": 0})
    if doc:
        for it in (doc.get("now") or []) + (doc.get("future") or []):
            if it["id"] == career_id:
                return it, it.get("country") or doc.get("country") or "PL"
    raise HTTPException(404, "Nie znaleziono zawodu.")


@api.get("/careers/{career_id}")
async def career_detail(career_id: str, user: UserDoc = Depends(current_user)):
    career, country = await find_career(user.id, career_id)
    cache_key = career_cache_key(career["title"], country)
    tmpl = await db.career_templates.find_one({"_id": cache_key}, {"_id": 0, "detail": 1})
    if tmpl and tmpl.get("detail"):
        return {"career": career, "detail": tmpl["detail"], "job_links": job_links(career["title"])}
    prompt = f"""To jest odrębne, samodzielne zapytanie — dotyczy WYŁĄCZNIE poniższego jednego zawodu, nie odwołuj się do innych zawodów ani wcześniejszych rozmów.
Zawód: {career['title']} (branża: {career.get('industry', '')}).

Opisz ten zawód szczegółowo, na podstawie typowych ofert pracy w Polsce (Pracuj.pl, OLX, LinkedIn). W polu "how_to_start" bądź KONKRETNY —
nazwij z imienia realne kursy/szkolenia/platformy i wskaż gdzie ich szukać (np. "kurs »Kadry i płace od podstaw« na Platformie Vademecum
Kadrowego", "szkolenie finansowane z KFS w urzędzie pracy"), a nie ogólniki typu "zrób kurs" czy "znajdź szkolenie". JEŚLI wymaga to studiów —
podaj nazwę kierunku (ew. 1-2 pokrewne kierunki) i wymień 2-3 PRZYKŁADOWE, różne uczelnie w Polsce, które go oferują, jako opcje do wyboru
(np. "kierunek Logistyka — dostępny m.in. na Uniwersytecie Ekonomicznym w Krakowie, Politechnice Warszawskiej lub w WSB") — NIGDY nie wskazuj
jednej konkretnej uczelni jako jedynej słusznej drogi. Zwróć JSON:
{{"description": "2 pełne zdania (ok. 30-40 słów) — zwięzły opis zawodu: czym się zajmuje i jak wygląda typowy dzień pracy",
 "daily_tasks": ["5-6 typowych codziennych zadań, pełne zdania (ok. 10-14 słów każde), nie pojedyncze słowa"],
 "pros": ["4-5 plusów, pełne zdania (ok. 10-14 słów) z krótkim wyjaśnieniem dlaczego to plus"], "cons": ["3-4 minusy, pełne zdania (ok. 10-14 słów) z krótkim wyjaśnieniem dlaczego to minus"],
 "requirements": ["6-9 typowych wymagań z ogłoszeń, krótkie frazy, np. wykształcenie, znajomość programów, prawo jazdy kat. B, języki"],
 "how_to_start": ["5-6 konkretnych, nazwanych z imienia kroków, każdy pełnym zdaniem (ok. 15-20 słów) z kontekstem (kursy/platformy/programy urzędu pracy z nazwy, a dla studiów: kierunek + kilka przykładowych uczelni)"],
 "career_levels": ["4-5 kolejnych, REALNYCH, oficjalnie istniejących w Polsce stanowisk/stopni awansu w TYM KONKRETNYM zawodzie, od wejściowego do najwyższego — np. dla nauczyciela: nauczyciel stażysta, kontraktowy, mianowany, dyplomowany, wicedyrektor, dyrektor szkoły; dla programisty: junior, mid, senior, lead, CTO. NIE wymyślaj nazw stanowisk, których nie ma w tym zawodzie — jeśli nie masz pewności, użyj najbardziej powszechnie znanej, rzeczywistej struktury awansu."]}}"""
    try:
        detail = await ask_llm(FAST_MODEL, system_message(country), prompt)
    except Exception:
        logger.exception("detail failed")
        raise HTTPException(502, "Nie udało się przygotować opisu. Spróbuj ponownie.")
    await db.career_templates.update_one(
        {"_id": cache_key},
        {"$set": {"title": career["title"], "country": country, "detail": detail, "updated_at": now_iso()},
         "$setOnInsert": {"created_at": now_iso()}},
        upsert=True,
    )
    return {"career": career, "detail": detail, "job_links": job_links(career["title"])}


# ---------------------------------------------------------------- premium (demo mode, no real payments yet)
PREMIUM_PATH_LIMIT = 3
PREMIUM_MONTHLY_GENERATIONS = 25  # new career-path generations per month included with Premium; the weekly/daily
# study plan for an already-generated path is always free and never counts against this.
PREMIUM_PLANS = {
    "monthly": {"label": "Miesięczny", "price": "19 zł", "period": "miesiąc"},
    "yearly": {"label": "Roczny", "price": "149,99 zł", "period": "rok"},
}


class PremiumIn(BaseModel):
    plan: str


class CancelPremiumIn(BaseModel):
    reason: Optional[str] = None
    detail: Optional[str] = None


CANCELLATION_REASONS = {"too_expensive", "no_longer_needed", "not_satisfied", "got_job", "other"}


def is_premium(u: UserDoc) -> bool:
    return bool(u.premium and u.premium.get("active"))


def _gen_month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def roadmap_gen_used(user_id: str) -> int:
    doc = await db.gen_usage.find_one({"user_id": user_id, "month": _gen_month_key()})
    return (doc or {}).get("count", 0)


async def bump_roadmap_gen(user_id: str):
    """Counts one brand-new career-path (roadmap) generation toward the Premium monthly
    quota. Only called when a NEW roadmap is actually generated — reactivating an existing
    path (same title) and generating/redoing that path's study plan never call this."""
    await db.gen_usage.update_one({"user_id": user_id, "month": _gen_month_key()}, {"$inc": {"count": 1}}, upsert=True)


@api.get("/premium")
async def premium_info(user: UserDoc = Depends(current_user)):
    return {"is_premium": is_premium(user), "premium": user.premium, "plans": PREMIUM_PLANS,
            "path_limit": PREMIUM_PATH_LIMIT, "roadmap_generations_used": await roadmap_gen_used(user.id),
            "roadmap_generations_limit": PREMIUM_MONTHLY_GENERATIONS, "demo": True}


@api.post("/premium/subscribe")
async def premium_subscribe(data: PremiumIn, user: UserDoc = Depends(current_user)):
    if data.plan not in PREMIUM_PLANS:
        raise HTTPException(400, "Nieznany plan.")
    premium = {"active": True, "plan": data.plan, "since": now_iso(), "demo": True}
    await db.users.update_one({"_id": ObjectId(user.id)}, {"$set": {"premium": premium}})
    return {"ok": True, "premium": premium}


@api.post("/premium/cancel")
async def premium_cancel(data: CancelPremiumIn, user: UserDoc = Depends(current_user)):
    # Reason is optional: the user may cancel without picking one. A recognized
    # category is stored as-is, free text ("other") falls back to "other", and
    # skipping the step entirely is tracked separately as "not_specified".
    raw_reason = (data.reason or "").strip()
    if raw_reason in CANCELLATION_REASONS:
        reason = raw_reason
    elif raw_reason:
        reason = "other"
    else:
        reason = "not_specified"
    detail = (data.detail or "").strip()[:500]
    plan = (user.premium or {}).get("plan")
    await db.premium_cancellations.insert_one({
        "user_id": user.id, "email": user.email, "plan": plan,
        "reason": reason, "detail": detail, "canceled_at": now_iso(),
    })
    await db.users.update_one({"_id": ObjectId(user.id)}, {"$set": {"premium": None}})
    return {"ok": True}


# ---------------------------------------------------------------- roadmap / paths
ROADMAP_PROJ = {"_id": 0, "milestones.tasks.resources": 0}


async def get_path(user_id: str, path_id: Optional[str] = None, projection: Optional[dict] = None):
    q = {"user_id": user_id}
    if path_id:
        q["path_id"] = path_id
        return await db.roadmaps.find_one(q, projection)
    doc = await db.roadmaps.find_one({**q, "active": True}, projection)
    if not doc:
        doc = await db.roadmaps.find_one(q, projection, sort=[("created_at", -1)])
    return doc


async def run_roadmap(user_id: str, career: dict, answers: dict, job_id: str, country: str = "PL", cache_key: Optional[str] = None):
    prompt = f"""Użytkownik wybrał ścieżkę kariery: {career['title']} (branża: {career.get('industry', '')}).
Profil użytkownika: {profile_text(answers)}

Zbuduj ścieżkę kariery w formie drogi: 4-5 DUŻYCH punktów (stanowisk) od wejściowego do najwyższego, UŻYWAJĄC REALNYCH, oficjalnie
istniejących w Polsce nazw stanowisk/stopni awansu zawodowego DLA TEGO KONKRETNEGO zawodu — nie każdy zawód ma strukturę
korporacyjną (junior/specjalista/senior/kierownik/dyrektor)! Np. dla nauczyciela realna ścieżka to: nauczyciel stażysta →
kontraktowy → mianowany → dyplomowany → wicedyrektor → dyrektor szkoły; dla programisty: junior → mid → senior → lead → CTO;
dla lekarza: lekarz stażysta → rezydent → specjalista → ordynator. NIE wymyślaj stanowisk, których nie ma w tym zawodzie —
jeśli nie masz pewności, użyj najbardziej powszechnie znanej, rzeczywistej struktury awansu w tym konkretnym zawodzie w Polsce.
Do każdego stanowiska podaj 3-5 MAŁYCH punktów (zadań), które użytkownik musi zdobyć/wykonać, aby dostać to stanowisko —
opartych na wymaganiach z prawdziwych ofert pracy (np. studia z danej dziedziny, kurs Excela, znajomość programu Symfonia/SAP/Comarch,
prawo jazdy kat. B, certyfikat, język angielski B2, 2 lata doświadczenia). Uwzględnij to, co użytkownik już ma — takie zadania oznacz "already_has": true.
Zwróć JSON:
{{"milestones": [{{"title": "stanowisko", "description": "1 pełne zdanie (ok. 18-25 słów) — czym się zajmuje na tym stanowisku", "salary": "widełki brutto", "years": "np. 0-2 lata",
   "requirements": ["wymagania z ofert, pełne frazy, nie pojedyncze słowa"],
   "tasks": [{{"title": "krótka nazwa zadania", "description": "1 pełne zdanie (ok. 15-20 słów) — co dokładnie trzeba zrobić i jak to zdobyć",
              "type": "studies|course|skill|certificate|language|license|experience|other", "already_has": false}}]}}]}}"""
    try:
        data = await ask_llm(ANALYSIS_MODEL, system_message(country), prompt)
        milestones = []
        for m in data.get("milestones", []):
            m["id"] = uuid.uuid4().hex[:10]
            tasks = []
            for t in m.get("tasks", []):
                tasks.append({"id": uuid.uuid4().hex[:10], "title": t.get("title", ""), "description": t.get("description", ""),
                              "type": t.get("type", "other"), "done": bool(t.get("already_has"))})
            m["tasks"] = tasks
            milestones.append(m)
        await db.roadmaps.update_one({"user_id": user_id, "job_id": job_id}, {"$set": {"status": "ready", "milestones": milestones, "updated_at": now_iso()}})
        if cache_key:
            # Persist the generated structure as the shared template for every future user who
            # picks this exact career (strip this user's personal done-flags — those are decided
            # per-user by mark_done_tasks on reuse).
            await db.career_templates.update_one(
                {"_id": cache_key},
                {"$set": {"title": career["title"], "country": country, "milestones": clone_milestones(milestones), "updated_at": now_iso()},
                 "$setOnInsert": {"created_at": now_iso()}},
                upsert=True,
            )
    except Exception as e:
        logger.exception("roadmap failed")
        await db.roadmaps.update_one({"user_id": user_id, "job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:200]}})


@api.post("/roadmap")
async def choose_path(data: RoadmapIn, user: UserDoc = Depends(current_user)):
    career, path_country = await find_career(user.id, data.career_id)
    await db.roadmaps.delete_many({"user_id": user.id, "status": "error"})
    existing = await db.roadmaps.find({"user_id": user.id}, {"_id": 0, "path_id": 1, "career": 1, "status": 1}).to_list(100)
    same = next((d for d in existing if d["career"]["title"].strip().lower() == career["title"].strip().lower() and d.get("status") != "error"), None)
    if same:
        await db.roadmaps.update_many({"user_id": user.id}, {"$set": {"active": False}})
        await db.roadmaps.update_one({"user_id": user.id, "path_id": same["path_id"]}, {"$set": {"active": True}})
        return {"status": same["status"], "path_id": same["path_id"], "existing": True}
    if len(existing) >= PREMIUM_PATH_LIMIT:
        raise HTTPException(403, f"Masz już {PREMIUM_PATH_LIMIT} ścieżki. Usuń jedną w zakładce Droga, aby dodać nową.")
    prof = await db.profiles.find_one({"user_id": user.id}) or {}
    answers = prof.get("answers", {})
    # Careers proposed via "Własny zawód" carry their own typed qualifications instead of quiz answers.
    custom_qualifications = career.get("qualifications")
    if custom_qualifications is not None:
        answers = {**answers, "recznie_wskazane_stanowisko_docelowe": career["title"],
                   "kwalifikacje_do_tego_stanowiska": custom_qualifications or "Użytkownik nie ma jeszcze żadnych kwalifikacji ani doświadczenia w tym kierunku — zaczyna od zera."}
    job_id = uuid.uuid4().hex
    path_id = uuid.uuid4().hex[:12]
    await db.roadmaps.update_many({"user_id": user.id}, {"$set": {"active": False}})
    await db.roadmaps.insert_one({"user_id": user.id, "path_id": path_id, "active": True, "career": career, "status": "pending",
                                  "job_id": job_id, "milestones": [], "country": path_country, "started_at": now_iso(), "created_at": now_iso()})
    cache_key = career_cache_key(career["title"], path_country)
    template = await db.career_templates.find_one({"_id": cache_key}, {"_id": 0, "milestones": 1})
    if template and template.get("milestones"):
        qualifications_text = custom_qualifications if custom_qualifications is not None else qualifications_text_from_answers(answers)
        spawn(apply_cached_roadmap(user.id, job_id, clone_milestones(template["milestones"]), qualifications_text, path_country))
    else:
        await bump_roadmap_gen(user.id)
        spawn(run_roadmap(user.id, career, answers, job_id, path_country, cache_key))
    return {"status": "pending", "path_id": path_id}


@api.post("/careers/custom")
async def propose_custom_career(data: CustomPathIn, user: UserDoc = Depends(current_user)):
    """Lets a user skip the profiling quiz entirely by typing the exact position they want
    (and, optionally, their current qualifications for it). This adds it to their career list —
    the same place quiz-suggested careers live — so they review it and explicitly build the path
    from there, exactly like any other suggested career, instead of jumping straight to a roadmap."""
    title = data.title.strip()
    if not title:
        raise HTTPException(400, "Podaj nazwę stanowiska.")
    valid, reason = await validate_profession(title)
    if not valid:
        raise HTTPException(400, reason or f"„{title}” nie jest prawidłowym, legalnym zawodem. Wpisz prawdziwe stanowisko pracy.")
    qualifications = data.qualifications.strip()
    doc = await db.recommendations.find_one({"user_id": user.id}, {"_id": 0, "now": 1})
    existing = next((it for it in (doc or {}).get("now", []) if it.get("title", "").strip().lower() == title.lower()), None)
    if existing:
        await db.recommendations.update_one(
            {"user_id": user.id, "now.id": existing["id"]},
            {"$set": {"now.$.qualifications": qualifications, "now.$.country": user.country}},
        )
        return {"career_id": existing["id"]}
    career = {"id": uuid.uuid4().hex[:12], "title": title, "industry": "", "summary": "Twój własny cel zawodowy.",
              "why": "", "match": 100, "category": "now", "country": user.country, "qualifications": qualifications, "custom": True}
    await db.recommendations.update_one(
        {"user_id": user.id},
        {"$push": {"now": career}, "$setOnInsert": {"user_id": user.id, "status": "ready", "summary": "", "future": [], "country": user.country}},
        upsert=True,
    )
    return {"career_id": career["id"]}


@api.get("/roadmap")
async def get_roadmap(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    doc = await get_path(user.id, path_id, ROADMAP_PROJ)
    if doc and await expire_stale(db.roadmaps, user.id, doc):
        doc["status"] = "error"
    return doc or {"status": "none"}


@api.get("/paths")
async def list_paths(user: UserDoc = Depends(current_user)):
    docs = await db.roadmaps.find({"user_id": user.id}, {"_id": 0, "path_id": 1, "career": 1, "status": 1, "active": 1,
                                                         "milestones.tasks.done": 1, "created_at": 1}).sort("created_at", 1).to_list(100)
    out = []
    for d in docs:
        tasks = [t for m in d.get("milestones", []) for t in m.get("tasks", [])]
        out.append({"path_id": d["path_id"], "title": d["career"]["title"], "status": d["status"], "active": bool(d.get("active")),
                    "progress": round(100 * sum(1 for t in tasks if t.get("done")) / len(tasks)) if tasks else 0})
    return {"paths": out, "limit": PREMIUM_PATH_LIMIT, "is_premium": is_premium(user)}


@api.post("/paths/{path_id}/activate")
async def activate_path(path_id: str, user: UserDoc = Depends(current_user)):
    if not await db.roadmaps.find_one({"user_id": user.id, "path_id": path_id}, {"_id": 1}):
        raise HTTPException(404, "Nie znaleziono ścieżki.")
    await db.roadmaps.update_many({"user_id": user.id}, {"$set": {"active": False}})
    await db.roadmaps.update_one({"user_id": user.id, "path_id": path_id}, {"$set": {"active": True}})
    return {"ok": True}


@api.delete("/paths/{path_id}")
async def delete_path(path_id: str, user: UserDoc = Depends(current_user)):
    res = await db.roadmaps.delete_one({"user_id": user.id, "path_id": path_id})
    if not res.deleted_count:
        raise HTTPException(404, "Nie znaleziono ścieżki.")
    if not await db.roadmaps.find_one({"user_id": user.id, "active": True}, {"_id": 1}):
        newest = await db.roadmaps.find_one({"user_id": user.id}, {"_id": 1}, sort=[("created_at", -1)])
        if newest:
            await db.roadmaps.update_one({"_id": newest["_id"]}, {"$set": {"active": True}})
    return {"ok": True}


@api.delete("/roadmap")
async def delete_roadmap(user: UserDoc = Depends(current_user)):
    await db.roadmaps.delete_many({"user_id": user.id})
    return {"ok": True}


def locate_task(doc: dict, task_id: str):
    for mi, m in enumerate(doc.get("milestones", [])):
        for ti, t in enumerate(m.get("tasks", [])):
            if t["id"] == task_id:
                return mi, ti, m, t
    raise HTTPException(404, "Nie znaleziono zadania.")


@api.patch("/roadmap/tasks/{task_id}")
async def toggle_task(task_id: str, data: TaskToggle, user: UserDoc = Depends(current_user)):
    res = await db.roadmaps.update_one(
        {"user_id": user.id, "milestones.tasks.id": task_id},
        {"$set": {"milestones.$[].tasks.$[t].done": data.done}},
        array_filters=[{"t.id": task_id}],
    )
    if not res.matched_count:
        raise HTTPException(404, "Nie znaleziono zadania.")
    return {"ok": True, "done": data.done}


@api.get("/roadmap/tasks/{task_id}/resources")
async def task_resources(task_id: str, user: UserDoc = Depends(current_user)):
    doc = await db.roadmaps.find_one({"user_id": user.id, "milestones.tasks.id": task_id})
    if not doc:
        raise HTTPException(404, "Nie znaleziono zadania.")
    _, _, milestone, task = locate_task(doc, task_id)
    path_country = doc.get("country") or user.country
    cache_key = career_cache_key(doc["career"]["title"], path_country)
    tmpl = await db.career_templates.find_one({"_id": cache_key, "milestones.tasks.id": task_id}, {"_id": 0, "milestones": 1})
    if tmpl:
        tmpl_task = find_task_in_milestones(tmpl.get("milestones", []), task_id)
        if tmpl_task and tmpl_task.get("resources"):
            return tmpl_task["resources"]
    if task.get("resources"):
        return task["resources"]
    prof = await db.profiles.find_one({"user_id": user.id}) or {}
    city = (prof.get("answers") or {}).get("city", "") or ""
    prompt = f"""To jest odrębne, samodzielne zapytanie — dotyczy WYŁĄCZNIE poniższego jednego punktu drogi. Nie odwołuj się do innych
zadań z tej ścieżki ani do żadnych wcześniejszych rozmów czy wcześniej wygenerowanych treści — nie istnieją.
Ścieżka kariery: {doc['career']['title']}. Stanowisko docelowe: {milestone['title']}.
Zadanie do zdobycia: {task['title']} — {task['description']} (typ: {task['type']}).
Miejscowość użytkownika: {city or 'nie podano'}.

Podpowiedz, jak zdobyć ten punkt. Jeśli to studia — opisz kierunek (lub 1-2 pokrewne kierunki), tryby (dzienne/zaoczne/podyplomowe), możliwe
specjalizacje, gdzie szukać rekrutacji. DLA STUDIÓW NIGDY nie wskazuj jednej konkretnej uczelni jako jedynej słusznej drogi — zamiast tego
podaj nazwę kierunku i wymień 2-3 PRZYKŁADOWE, różne uczelnie w Polsce, które go oferują, jako opcje do wyboru (np. "kierunek Logistyka —
dostępny m.in. na Uniwersytecie Ekonomicznym w Krakowie, Politechnice Warszawskiej lub w WSB", a nie "idź na Logistykę na Politechnice Warszawskiej").
Jeśli to umiejętność/program (np. Excel) — kanały YouTube, platformy szkoleniowe, jak korzystać darmowo (np. Excel w przeglądarce w Microsoft 365 online),
kursy finansowane przez urząd pracy (bon szkoleniowy, KFS), webinary.
WAŻNE — bądź KONKRETNY, nie ogólnikowy, ale nie narzucaj jednej jedynej opcji tam, gdzie realnie jest wybór: dla KURSÓW/SZKOLEŃ/KANAŁÓW w "steps"
i "free_tips" zawsze podawaj NAZWY WŁASNE — konkretny kurs/szkolenie, konkretną platformę lub kanał (np. "kurs »Excel od podstaw do zaawansowanego«
na Udemy", "szkolenie kadrowo-płacowe finansowane z Krajowego Funduszu Szkoleniowego (KFS) w powiatowym urzędzie pracy", "kanał YouTube »ExcelPL«"),
a nie ogólniki typu "znajdź kurs" czy "skorzystaj ze szkolenia". Jeśli dotyczy urzędu pracy, nazwij DOKŁADNIE jaki to rodzaj wsparcia (bon
szkoleniowy, KFS, staż, dofinansowanie studiów podyplomowych, bon na zasiedlenie) i co trzeba tam zrobić (jaki wniosek, do kogo). Dla STUDIÓW
(patrz wyżej) podawaj kierunek + kilka przykładowych uczelni, nigdy jedną wskazaną z imienia jako jedyną.
Zwróć JSON:
{{"overview": "2 pełne zdania (ok. 30-40 słów) — zwięzłe wyjaśnienie czym jest ten punkt i dlaczego jest ważny",
 "steps": ["4-5 konkretnych, nazwanych z imienia kroków jak to zdobyć, każdy pełnym zdaniem (ok. 15-20 słów) z kontekstem (z nazwami kursów/platform/programów, a dla studiów: kierunek + kilka przykładowych uczelni)"],
 "free_tips": ["2-4 konkretne, nazwane z imienia sposoby zrobienia tego za darmo lub taniej, pełne zdania (ok. 12-16 słów)"],
 "specializations": ["tylko dla studiów/kursów: możliwe specjalizacje, inaczej pusta lista"],
 "time_estimate": "ile to zwykle trwa",
 "resources": [{{"type": "youtube|course|studies|urzad_pracy|webinar|certificate|article", "platform": "np. YouTube, Coursera, Udemy, LinkedIn Learning, Google (dla studiów: nazwa uczelni jako JEDEN z kilku przykładów)",
                "title": "konkretna, realna nazwa kursu/kanału/szkolenia, a dla studiów: nazwa kierunku (nie pojedyncza narzucona uczelnia)", "description": "1 pełne zdanie (ok. 10-14 słów), co dokładnie zawiera i dlaczego warto",
                "query": "fraza wyszukiwania po polsku"}}]}}
Podaj 5-8 zasobów, w tym przynajmniej jeden YouTube i jeden urzad_pracy."""
    try:
        data = await ask_llm(FAST_MODEL, system_message(path_country), prompt)
    except Exception:
        logger.exception("resources failed")
        raise HTTPException(502, "Nie udało się przygotować podpowiedzi. Spróbuj ponownie.")
    for r in data.get("resources", []):
        r["url"] = resource_url(r, city)
    await db.roadmaps.update_one(
        {"user_id": user.id, "milestones.tasks.id": task_id},
        {"$set": {"milestones.$[].tasks.$[t].resources": data}},
        array_filters=[{"t.id": task_id}],
    )
    await db.career_templates.update_one(
        {"_id": cache_key, "milestones.tasks.id": task_id},
        {"$set": {"milestones.$[].tasks.$[t].resources": data}},
        array_filters=[{"t.id": task_id}],
    )
    return data


# ---------------------------------------------------------------- weekly study plan (shared
# per-career cache, 8-week "blocks", checkable items — available to free users via one ad)
def pending_signature(milestones: list) -> tuple[str, list]:
    """The weekly plan's content only really depends on what's still left to do — not on which
    specific user is asking. Signature = the next (up to) 2 not-done tasks, in path order; every
    user who reaches the same point on the same shared career path gets the same cached plan."""
    pending = []
    for m in milestones:
        for t in m.get("tasks", []):
            if not t.get("done"):
                pending.append({"id": t["id"], "title": t.get("title", ""), "description": t.get("description", ""),
                                 "milestone_title": m.get("title", "")})
    sig = "_".join(p["id"] for p in pending[:2]) or "complete"
    return sig, pending[:2]


def weekly_plan_context(career_title: str, pending: list) -> str:
    todo = "\n".join(f"- [{p['milestone_title']}] {p['title']}: {p['description']}" for p in pending)
    return f"""Ścieżka kariery: {career_title}.
Najbliższe punkty do zdobycia (w kolejności drogi):
{todo or '- wszystko zdobyte, zaplanuj szukanie pracy i rozwój'}
Załóż przeciętne możliwości czasowe osoby uczącej się po godzinach (ok. 5-10h/tydzień)."""


async def generate_weekly_plan_ai(context: str, country: str) -> dict:
    prompt = f"""{context}

Ułóż realistyczny plan nauki na 8 tygodni, skupiony na najbliższych punktach drogi. Każdy tydzień: cel i 3-5 konkretnych zadań z liczbą godzin.
Uwzględnij darmowe materiały, kursy z urzędu pracy, ćwiczenia praktyczne i budowanie portfolio/CV. Nie wymyślaj konkretnych, brzmiących oficjalnie
nazw firm/akademii/programów, których istnienia nie jesteś pewien — używaj ogólnych, realnych kategorii (platformy typu YouTube/Udemy/Coursera,
szkolenia finansowane z KFS/bonu szkoleniowego w urzędzie pracy).
Zwróć JSON:
{{"hours_per_week": liczba, "summary": "1 pełne zdanie (ok. 15-20 słów) — podsumowanie planu i podejścia",
 "weeks": [{{"week": 1, "focus": "temat tygodnia", "goal": "1 pełne zdanie (ok. 15-20 słów) — co umiesz po tygodniu",
            "items": [{{"title": "zadanie", "description": "1 pełne zdanie (ok. 15-20 słów) — jak dokładnie to zrobić, z konkretami", "hours": liczba}}]}}],
 "tips": ["3 rady motywacyjne/organizacyjne, pełne zdania (ok. 12-16 słów)"]}}"""
    plan = await ask_llm(ANALYSIS_MODEL, system_message(country), prompt)
    for w in plan.get("weeks", []):
        for it in w.get("items", []):
            it["id"] = uuid.uuid4().hex[:10]
            it["done"] = False
    return plan


def clone_weekly_plan(plan: dict) -> dict:
    return {**plan, "weeks": [{**w, "items": [{**it, "done": False} for it in w.get("items", [])]} for w in plan.get("weeks", [])]}


WEEKLY_PLAN_REFRESH_EVERY = 4  # every Nth time a given (career, pending-signature) combo is requested, regenerate via AI and overwrite the cache, instead of serving it forever


async def get_or_build_weekly_plan(cache_key: str, sig: str, career_title: str, pending: list, country: str) -> dict:
    field = f"weekly_plans.{sig}"
    res = await db.career_templates.find_one_and_update(
        {"_id": cache_key},
        {"$inc": {f"{field}.hits": 1}, "$set": {"title": career_title, "country": country, "updated_at": now_iso()},
         "$setOnInsert": {"created_at": now_iso()}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    entry = (res.get("weekly_plans") or {}).get(sig) or {}
    hits = entry.get("hits", 1)
    cached_plan = entry.get("plan")
    if cached_plan and hits % WEEKLY_PLAN_REFRESH_EVERY != 0:
        return clone_weekly_plan(cached_plan)
    plan = await generate_weekly_plan_ai(weekly_plan_context(career_title, pending), country)
    await db.career_templates.update_one({"_id": cache_key}, {"$set": {f"{field}.plan": plan}})
    return clone_weekly_plan(plan)


async def run_study_block(user_id: str, path_id: str, job_id: str, career_title: str, sig: str, pending: list, country: str):
    try:
        cache_key = career_cache_key(career_title, country)
        plan = await get_or_build_weekly_plan(cache_key, sig, career_title, pending, country)
        await db.roadmaps.update_one({"user_id": user_id, "path_id": path_id, "study_plan.blocks.job_id": job_id},
                                     {"$set": {"study_plan.blocks.$.status": "ready", "study_plan.blocks.$.plan": plan, "study_plan.blocks.$.updated_at": now_iso()}})
    except Exception as e:
        logger.exception("study block failed")
        await db.roadmaps.update_one({"user_id": user_id, "path_id": path_id, "study_plan.blocks.job_id": job_id},
                                     {"$set": {"study_plan.blocks.$.status": "error", "study_plan.blocks.$.error": str(e)[:200]}})


@api.post("/roadmap/study-plan")
async def create_study_plan(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    # Weekly plan is available to free users too (gated by a rewarded ad on the client side,
    # skipped automatically for Premium); its content persists in a shared DB cache once generated.
    doc = await get_path(user.id, path_id, {"_id": 0, "path_id": 1, "status": 1, "career": 1, "milestones": 1, "study_plan": 1, "country": 1})
    if not doc or doc["status"] != "ready":
        raise HTTPException(400, "Najpierw wybierz ścieżkę i poczekaj, aż droga będzie gotowa.")
    if (doc.get("study_plan") or {}).get("blocks"):
        raise HTTPException(400, "Plan tygodniowy już istnieje.")
    job_id = uuid.uuid4().hex
    sig, pending = pending_signature(doc.get("milestones", []))
    block = {"index": 0, "status": "pending", "job_id": job_id, "pending_sig": sig, "started_at": now_iso()}
    await db.roadmaps.update_one({"user_id": user.id, "path_id": doc["path_id"]}, {"$set": {"study_plan.blocks": [block]}})
    spawn(run_study_block(user.id, doc["path_id"], job_id, doc["career"]["title"], sig, pending, doc.get("country") or user.country))
    return {"status": "pending"}


@api.post("/roadmap/study-plan/next-block")
async def create_next_study_block(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    doc = await get_path(user.id, path_id, {"_id": 0, "path_id": 1, "career": 1, "milestones": 1, "study_plan": 1, "country": 1})
    blocks = (doc or {}).get("study_plan", {}).get("blocks") or []
    if not blocks:
        raise HTTPException(400, "Najpierw ułóż plan tygodniowy.")
    if any(b.get("status") == "pending" for b in blocks):
        return {"status": "pending"}
    next_index = len(blocks)
    job_id = uuid.uuid4().hex
    sig, pending = pending_signature(doc.get("milestones", []))
    block = {"index": next_index, "status": "pending", "job_id": job_id, "pending_sig": sig, "started_at": now_iso()}
    await db.roadmaps.update_one({"user_id": user.id, "path_id": doc["path_id"]}, {"$push": {"study_plan.blocks": block}})
    spawn(run_study_block(user.id, doc["path_id"], job_id, doc["career"]["title"], sig, pending, doc.get("country") or user.country))
    return {"status": "pending"}


@api.get("/roadmap/study-plan")
async def get_study_plan(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    doc = await get_path(user.id, path_id, {"_id": 0, "study_plan": 1, "career": 1, "path_id": 1})
    if not doc:
        return {"status": "none", "is_premium": is_premium(user)}
    blocks = (doc.get("study_plan") or {}).get("blocks") or []
    if not blocks:
        return {"status": "none", "career": doc.get("career"), "path_id": doc["path_id"], "is_premium": is_premium(user)}
    for b in blocks:
        if b.get("status") == "pending" and b.get("started_at") and datetime.now(timezone.utc) - datetime.fromisoformat(b["started_at"]) > timedelta(minutes=4):
            b["status"] = "error"
    last = blocks[-1]
    return {"status": last["status"], "blocks": blocks, "can_generate_next": last["status"] == "ready",
            "career": doc.get("career"), "path_id": doc["path_id"], "is_premium": is_premium(user)}


@api.patch("/roadmap/study-plan/items/{item_id}")
async def toggle_study_item(item_id: str, data: TaskToggle, path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    q: dict = {"user_id": user.id, "study_plan.blocks.plan.weeks.items.id": item_id}
    if path_id:
        q["path_id"] = path_id
    res = await db.roadmaps.update_one(
        q, {"$set": {"study_plan.blocks.$[].plan.weeks.$[].items.$[it].done": data.done}}, array_filters=[{"it.id": item_id}])
    if not res.matched_count:
        raise HTTPException(404, "Nie znaleziono punktu planu.")
    return {"ok": True, "done": data.done}


# ---------------------------------------------------------------- daily plan (free + premium)
WEEKDAY_NAMES_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
FREE_UNLOCKED_STUDY_DAYS = 2  # free users get this many study days per week for free; the rest needs an ad


def week_unlock_day(week_start: date) -> date:
    """2 days before this (rolling, not necessarily Monday-aligned) week ends — when the NEXT week becomes generatable."""
    return week_start + timedelta(days=5)


async def run_daily_plan(user_id: str, path_id: str, job_id: str, week_index: int, week_start: date, premium: bool, is_next: bool = False, country: str = "PL"):
    doc = await db.roadmaps.find_one({"user_id": user_id, "path_id": path_id})
    settings = (doc.get("daily_plan") or {}).get("settings", {})
    free_days = {d for d in settings.get("free_days", []) if 0 <= d <= 6}
    done_ids = {t["id"] for m in doc.get("milestones", []) for t in m.get("tasks", []) if t.get("done")}
    pending = [{"id": t["id"], "title": t["title"], "type": t.get("type", "other")}
               for m in doc.get("milestones", []) for t in m.get("tasks", []) if not t.get("done")]
    time_desc = (f"{settings.get('time_value')} minut dziennie w dni nauki" if settings.get("time_mode") == "daily"
                 else f"{settings.get('time_value')} godzin tygodniowo, rozłożone elastycznie na dni nauki")
    # week_start isn't always a Monday — the very first week starts on the day the user
    # actually sets up the plan (so e.g. a Saturday start never contains already-past days).
    window = [week_start + timedelta(days=i) for i in range(7)]
    day_lines = "\n".join(
        f"- {WEEKDAY_NAMES_PL[d.weekday()]} ({d.isoformat()}): {'WOLNY, nic nie planuj' if d.weekday() in free_days else 'dzień nauki'}"
        for d in window
    )
    prompt = f"""Ścieżka kariery: {doc['career']['title']}.
Zadania do zdobycia (z ID), w kolejności drogi:
{json.dumps(pending[:25], ensure_ascii=False)}

Dni tego tygodnia w kolejności chronologicznej (ten tydzień NIE zawsze zaczyna się w poniedziałek):
{day_lines}
Czas na naukę: {time_desc}.

Dla KAŻDEGO dnia nauki (pomijając dni wolne) zaplanuj 1-3 konkretne, wykonalne TEGO DNIA czynności
(np. "Obejrzyj wprowadzenie do funkcji VLOOKUP w Excelu na YouTube"), każdą powiązaną z ID jednego z zadań z listy
powyżej (pole task_id), chyba że to czynność ogólna (np. szukanie ofert, przegląd postępów) — wtedy task_id = null.
WAŻNE — realizm: każda czynność musi dać się faktycznie zrobić w czasie {time_desc} JEDNEGO dnia. NIGDY nie pisz czynności
sugerujących ukończenie w jeden dzień czegoś, co trwa tygodnie/miesiące — np. NIE "ukończ kurs X", "zdobądź certyfikat Y",
"zdobądź doświadczenie przez staż", "weź udział w szkoleniu Z" jako jednodniowe zadanie. Zamiast tego pisz o MAŁYM, konkretnym
kroku w stronę tego celu, np. "Obejrzyj 1. lekcję kursu o sprzedaży IT na YouTube/Udemy", "Przeczytaj ofertę szkolenia
finansowanego z KFS i zapisz potrzebne dokumenty", "Sprawdź 3 aktualne oferty stażu w urzędzie pracy i wybierz jedną do zgłoszenia",
"Zrób pierwsze ćwiczenie z rozdziału 2 podręcznika/kursu". NIE wymyślaj konkretnych, brzmiących oficjalnie nazw firm/akademii/programów
szkoleniowych ani nie twierdź z pewnością, że dana oferta (np. konkretny staż) jest akurat dostępna w konkretnym mieście użytkownika —
jeśli nie masz pewności, formułuj czynność jako sprawdzenie/wyszukanie oferty, a nie jako pewnik.
Jeśli zadanie jest bardzo długoterminowe (studia, wieloetapowy kurs, certyfikacja trwająca miesiące), oznacz powiązaną
czynność jako long_term=true i zaplanuj dla niej tylko JEDNĄ czynność w CAŁYM tygodniu, najlepiej w ostatnim
dniu nauki z listy powyżej — sformułowaną jako mały krok lub przegląd postępów, NIGDY jako "ukończ"/"zdobądź" (np.
"Sprawdź swoje postępy w nauce na studiach/kursie w tym tygodniu" albo "Zrealizuj kolejny moduł kursu").
Nie planuj nic w dni wolne.
Zwróć JSON z polem "weekday" = numer dnia tygodnia zgodnie z datami powyżej (0=poniedziałek, 1=wtorek, 2=środa, 3=czwartek, 4=piątek, 5=sobota, 6=niedziela):
{{"days": [{{"weekday": 0-6, "items": [{{"title": "krótka nazwa (max 8 słów)", "description": "max 18 słów, co dokładnie zrobić",
            "minutes": liczba, "task_id": "id z listy lub null", "long_term": true/false}}]}}]}}"""
    status_field = "daily_plan.next_status" if is_next else "daily_plan.status"
    job_field = "daily_plan.next_job_id" if is_next else "daily_plan.job_id"
    try:
        data = await ask_llm(ANALYSIS_MODEL, system_message(country), prompt)
        by_weekday = {d.get("weekday"): d.get("items", []) for d in data.get("days", [])}
        study_pos = 0
        days_out = []
        for d in window:
            wd = d.weekday()
            is_free = wd in free_days
            items = []
            locked = False
            if not is_free:
                locked = (not premium) and study_pos >= FREE_UNLOCKED_STUDY_DAYS
                for it in by_weekday.get(wd, []):
                    items.append({"id": uuid.uuid4().hex[:10], "title": it.get("title", ""), "description": it.get("description", ""),
                                  "minutes": it.get("minutes"), "milestone_task_id": it.get("task_id"),
                                  "long_term": bool(it.get("long_term")), "done": False})
                study_pos += 1
            days_out.append({"date": d.isoformat(), "weekday": wd, "free": is_free, "locked": locked, "items": items})
        week = {"index": week_index, "start_date": week_start.isoformat(), "days": days_out}
        await db.roadmaps.update_one({"user_id": user_id, "path_id": path_id, job_field: job_id},
                                     {"$set": {status_field: "ready"}, "$push": {"daily_plan.weeks": week}})
    except Exception as e:
        logger.exception("daily plan failed")
        await db.roadmaps.update_one({"user_id": user_id, "path_id": path_id, job_field: job_id},
                                     {"$set": {status_field: "error", "daily_plan.error": str(e)[:200]}})


@api.post("/roadmap/daily-plan/settings")
async def set_daily_plan_settings(data: DailyPlanSettingsIn, path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    if not is_premium(user):
        raise HTTPException(403, "Plan dzienny to funkcja Premium. Przejdź na Premium, aby go odblokować.")
    if data.time_mode not in ("daily", "weekly"):
        raise HTTPException(400, "Nieprawidłowy tryb czasu.")
    doc = await get_path(user.id, path_id, {"_id": 0, "path_id": 1, "status": 1, "country": 1})
    if not doc or doc["status"] != "ready":
        raise HTTPException(400, "Najpierw wybierz ścieżkę i poczekaj, aż droga będzie gotowa.")
    free_days = sorted({d for d in data.free_days if 0 <= d <= 6})
    if len(free_days) >= 7:
        raise HTTPException(400, "Zostaw przynajmniej jeden dzień nauki w tygodniu.")
    settings = {"time_mode": data.time_mode, "time_value": data.time_value, "free_days": free_days}
    job_id = uuid.uuid4().hex
    # the first (or redone) week always starts TODAY, never on a calendar Monday — a user
    # setting this up on a Saturday must never see already-past days (Mon-Fri) in their plan.
    week_start = date.today()
    await db.roadmaps.update_one({"user_id": user.id, "path_id": doc["path_id"]},
                                 {"$set": {"daily_plan": {"settings": settings, "status": "pending", "job_id": job_id, "weeks": [], "started_at": now_iso()}}})
    spawn(run_daily_plan(user.id, doc["path_id"], job_id, 0, week_start, is_premium(user), country=doc.get("country") or user.country))
    return {"status": "pending"}


@api.post("/roadmap/daily-plan/next-week")
async def generate_next_week(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    if not is_premium(user):
        raise HTTPException(403, "Plan dzienny to funkcja Premium. Przejdź na Premium, aby go odblokować.")
    doc = await get_path(user.id, path_id, {"_id": 0, "path_id": 1, "daily_plan": 1, "country": 1})
    dp = (doc or {}).get("daily_plan")
    if not dp or dp.get("status") != "ready" or not dp.get("weeks"):
        raise HTTPException(400, "Najpierw ułóż plan dzienny.")
    if dp.get("next_status") == "pending":
        return {"status": "pending"}
    last = dp["weeks"][-1]
    last_start = date.fromisoformat(last["start_date"])
    next_index = last["index"] + 1
    if any(w["index"] == next_index for w in dp["weeks"]):
        return {"status": "ready"}
    if date.today() < week_unlock_day(last_start):
        raise HTTPException(400, "Kolejny tydzień odblokuje się w sobotę bieżącego tygodnia.")
    job_id = uuid.uuid4().hex
    await db.roadmaps.update_one({"user_id": user.id, "path_id": doc["path_id"]},
                                 {"$set": {"daily_plan.next_status": "pending", "daily_plan.next_job_id": job_id, "daily_plan.next_started_at": now_iso()}})
    spawn(run_daily_plan(user.id, doc["path_id"], job_id, next_index, last_start + timedelta(days=7), is_premium(user), is_next=True, country=doc.get("country") or user.country))
    return {"status": "pending"}


@api.post("/roadmap/daily-plan/weeks/{week_index}/unlock")
async def unlock_week(week_index: int, path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    q: dict = {"user_id": user.id, "daily_plan.weeks.index": week_index}
    if path_id:
        q["path_id"] = path_id
    res = await db.roadmaps.update_one(q, {"$set": {"daily_plan.weeks.$[w].days.$[].locked": False}}, array_filters=[{"w.index": week_index}])
    if not res.matched_count:
        raise HTTPException(404, "Nie znaleziono tygodnia.")
    return {"ok": True}


def _serialize_daily_week(week: dict, premium: bool) -> dict:
    out_days = []
    for d in week.get("days", []):
        locked = bool(d.get("locked")) and not premium
        if locked:
            out_days.append({**d, "items": [], "locked": True, "locked_count": len(d.get("items", []))})
        else:
            out_days.append({**d, "locked": False, "locked_count": 0})
    return {**week, "days": out_days}


@api.get("/roadmap/daily-plan")
async def get_daily_plan(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    doc = await get_path(user.id, path_id, {"_id": 0, "daily_plan": 1, "career": 1, "path_id": 1})
    if not doc or not doc.get("daily_plan"):
        return {"status": "none"}
    dp = doc["daily_plan"]
    if dp.get("status") == "pending" and dp.get("started_at") and datetime.now(timezone.utc) - datetime.fromisoformat(dp["started_at"]) > timedelta(minutes=4):
        dp["status"] = "error"
    if dp.get("next_status") == "pending" and dp.get("next_started_at") and datetime.now(timezone.utc) - datetime.fromisoformat(dp["next_started_at"]) > timedelta(minutes=4):
        dp["next_status"] = "error"
    premium = is_premium(user)
    weeks = [_serialize_daily_week(w, premium) for w in dp.get("weeks", [])]
    can_generate_next = False
    if weeks and dp.get("status") == "ready" and dp.get("next_status") != "pending":
        last_start = date.fromisoformat(weeks[-1]["start_date"])
        next_index = weeks[-1]["index"] + 1
        if date.today() >= week_unlock_day(last_start) and not any(w["index"] == next_index for w in weeks):
            can_generate_next = True
    return {"status": dp.get("status"), "settings": dp.get("settings"), "weeks": weeks,
            "next_status": dp.get("next_status", "none"), "can_generate_next": can_generate_next,
            "career": doc.get("career"), "path_id": doc["path_id"], "is_premium": premium}


@api.patch("/roadmap/daily-plan/items/{item_id}")
async def toggle_daily_item(item_id: str, data: TaskToggle, path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    q: dict = {"user_id": user.id, "daily_plan.weeks.days.items.id": item_id}
    if path_id:
        q["path_id"] = path_id
    res = await db.roadmaps.update_one(
        q, {"$set": {"daily_plan.weeks.$[].days.$[].items.$[it].done": data.done}}, array_filters=[{"it.id": item_id}])
    if not res.matched_count:
        raise HTTPException(404, "Nie znaleziono punktu planu.")
    return {"ok": True, "done": data.done}


def _find_daily_item(doc: dict, item_id: str):
    for w in doc.get("daily_plan", {}).get("weeks", []):
        for d in w.get("days", []):
            for it in d.get("items", []):
                if it["id"] == item_id:
                    return it
    return None


@api.get("/roadmap/daily-plan/items/{item_id}/resources")
async def daily_item_resources(item_id: str, user: UserDoc = Depends(current_user)):
    doc = await db.roadmaps.find_one({"user_id": user.id, "daily_plan.weeks.days.items.id": item_id})
    if not doc:
        raise HTTPException(404, "Nie znaleziono punktu planu.")
    item = _find_daily_item(doc, item_id)
    if not item:
        raise HTTPException(404, "Nie znaleziono punktu planu.")
    if item.get("milestone_task_id"):
        return await task_resources(item["milestone_task_id"], user)
    if item.get("resources"):
        return item["resources"]
    prof = await db.profiles.find_one({"user_id": user.id}) or {}
    city = (prof.get("answers") or {}).get("city", "") or ""
    prompt = f"""To jest odrębne, samodzielne zapytanie — dotyczy WYŁĄCZNIE poniższej jednej czynności. Nie odwołuj się do innych
czynności z planu, innych zadań ani żadnych wcześniejszych rozmów czy wcześniej wygenerowanych treści — nie istnieją.
Czynność z planu dnia na ścieżce kariery "{doc['career']['title']}": {item['title']} — {item['description']}.
Miejscowość użytkownika: {city or 'nie podano'}.

Podpowiedz, jak dokładnie wykonać tę czynność dziś. Podaj konkretne, darmowe lub tanie materiały.
WAŻNE — bądź KONKRETNY, nie ogólnikowy: w "steps" i "free_tips" podawaj NAZWY WŁASNE — konkretny kurs/szkolenie/kanał (np. "obejrzyj odcinek
»Tabele przestawne krok po kroku« na kanale YouTube »Kurs Excel PL«"), a jeśli dotyczy urzędu pracy, nazwij dokładnie formę wsparcia
(bon szkoleniowy, KFS, staż) — nie pisz ogólnie "znajdź kurs" czy "skorzystaj ze szkolenia". Jeśli dotyczy studiów, nigdy nie wskazuj jednej
konkretnej uczelni jako jedynej słusznej — podaj kierunek i kilka przykładowych uczelni, które go oferują.
Zwróć JSON:
{{"overview": "1 pełne zdanie (ok. 18-25 słów) — czym jest ta czynność i dlaczego pomaga w drodze do celu",
 "steps": ["3-4 konkretne, nazwane z imienia kroki, każdy pełnym zdaniem (ok. 15-20 słów) z kontekstem"],
 "free_tips": ["2-3 konkretne, nazwane z imienia sposoby zrobienia tego za darmo, pełne zdania (ok. 12-16 słów)"], "specializations": [], "time_estimate": "ile to zwykle trwa",
 "resources": [{{"type": "youtube|course|studies|urzad_pracy|webinar|certificate|article", "platform": "np. YouTube, Coursera, Google",
                "title": "konkretna, realna nazwa kursu/kanału/szkolenia (nie ogólnik)", "description": "1 pełne zdanie (ok. 10-14 słów), co dokładnie zawiera",
                "query": "fraza wyszukiwania po polsku"}}]}}
Podaj 4-6 zasob\u00f3w, w tym przynajmniej jeden YouTube."""
    try:
        data = await ask_llm(FAST_MODEL, system_message(doc.get("country") or user.country), prompt)
    except Exception:
        logger.exception("daily item resources failed")
        raise HTTPException(502, "Nie udało się przygotować podpowiedzi. Spróbuj ponownie.")
    for r in data.get("resources", []):
        r["url"] = resource_url(r, city)
    await db.roadmaps.update_one(
        {"user_id": user.id, "daily_plan.weeks.days.items.id": item_id},
        {"$set": {"daily_plan.weeks.$[].days.$[].items.$[it].resources": data}}, array_filters=[{"it.id": item_id}])
    return data


# ---------------------------------------------------------------- admin panel
async def admin_user(user: UserDoc = Depends(current_user)) -> UserDoc:
    if user.role != "admin":
        raise HTTPException(403, "Brak uprawnień administratora.")
    return user


class GrantIn(BaseModel):
    email: str = Field(max_length=320)


class PremiumToggle(BaseModel):
    active: bool


def admin_row(d: dict) -> dict:
    p = d.get("premium") or {}
    return {"id": str(d["_id"]), "email": d.get("email"), "name": d.get("name", ""), "role": d.get("role", "user"),
            "is_premium": bool(p.get("active")), "premium_plan": p.get("plan"), "created_at": d.get("created_at")}


@api.get("/admin/stats")
async def admin_stats(_: UserDoc = Depends(admin_user)):
    return {"users": await db.users.count_documents({}),
            "premium": await db.users.count_documents({"premium.active": True}),
            "gifted": await db.users.count_documents({"premium.plan": "gift"}),
            "pending_grants": await db.premium_grants.count_documents({}),
            "paths": await db.roadmaps.count_documents({}),
            "cancellations": await db.premium_cancellations.count_documents({})}


@api.get("/admin/cancellations")
async def admin_cancellations(_: UserDoc = Depends(admin_user)):
    docs = await db.premium_cancellations.find({}, {"_id": 0}).sort("canceled_at", -1).to_list(200)
    by_reason: dict[str, int] = {}
    for d in docs:
        by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
    return {"total": len(docs), "by_reason": by_reason, "recent": docs[:50]}


# ---------------------------------------------------------------- gmail connect (owner's own mailbox)
@api.get("/admin/google/status")
async def google_status(_: UserDoc = Depends(admin_user)):
    configured = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    doc = await db.integration_tokens.find_one({"provider": "gmail_send"})
    return {"configured": configured, "connected": bool(doc and doc.get("refresh_token")),
            "sender": GOOGLE_GMAIL_SENDER, "connected_at": (doc or {}).get("connected_at")}


@api.get("/admin/google/connect")
async def google_connect(_: UserDoc = Depends(admin_user)):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(400, "Najpierw dodaj GOOGLE_CLIENT_ID i GOOGLE_CLIENT_SECRET.")
    state = pysecrets.token_urlsafe(24)
    await db.oauth_states.insert_one({"state": state, "purpose": "gmail_connect", "created_at": datetime.now(timezone.utc)})
    params = {
        "client_id": GOOGLE_CLIENT_ID, "redirect_uri": GOOGLE_REDIRECT_URI, "response_type": "code",
        "scope": GMAIL_SCOPE, "access_type": "offline", "prompt": "consent",
        "login_hint": GOOGLE_GMAIL_SENDER, "state": state,
    }
    return {"url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}


@api.post("/admin/google/disconnect")
async def google_disconnect(_: UserDoc = Depends(admin_user)):
    await db.integration_tokens.delete_one({"provider": "gmail_send"})
    return {"ok": True}


def _oauth_result_page(ok: bool, message: str) -> HTMLResponse:
    color = "#16a34a" if ok else "#dc2626"
    html_doc = f"""<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zawodowcy — Gmail</title></head>
<body style="font-family:-apple-system,system-ui,sans-serif;display:flex;min-height:100vh;
align-items:center;justify-content:center;background:#f8fafc;margin:0;padding:24px;">
<div style="max-width:420px;text-align:center;">
<h1 style="color:{color};font-size:22px;margin-bottom:12px;">{"Połączono pomyślnie" if ok else "Nie udało się połączyć"}</h1>
<p style="color:#334155;font-size:15px;line-height:1.5;">{escape(message)}</p>
<p style="color:#94a3b8;font-size:13px;margin-top:24px;">Możesz teraz zamknąć tę kartę i wrócić do aplikacji.</p>
</div></body></html>"""
    return HTMLResponse(content=html_doc, status_code=200 if ok else 400)


@api.get("/auth/google/callback", include_in_schema=False)
async def google_oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Public redirect target — Google sends the admin's browser here after they grant
    (or deny) access to their Gmail account. Not behind auth: Google cannot attach a
    bearer token on a browser redirect, so a one-time `state` nonce guards against CSRF."""
    if error:
        return _oauth_result_page(False, f"Google zwrócił błąd: {error}. Spróbuj połączyć ponownie z panelu administratora.")
    if not (code and state):
        return _oauth_result_page(False, "Brak wymaganych parametrów w odpowiedzi Google.")
    state_doc = await db.oauth_states.find_one_and_delete({"state": state, "purpose": "gmail_connect"})
    if not state_doc or (datetime.now(timezone.utc) - state_doc["created_at"]).total_seconds() > 600:
        return _oauth_result_page(False, "Link wygasł lub został już użyty. Wróć do panelu administratora i spróbuj ponownie.")
    try:
        async with httpx.AsyncClient(timeout=20) as client_http:
            resp = await client_http.post(GOOGLE_TOKEN_URL, data={
                "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "code": code,
                "redirect_uri": GOOGLE_REDIRECT_URI, "grant_type": "authorization_code",
            })
        resp.raise_for_status()
        tokens = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Gmail token exchange failed: {e.response.status_code} {e.response.text}")
        return _oauth_result_page(False, "Google odrzucił wymianę kodu na token. Sprawdź Client ID / Client Secret i spróbuj ponownie.")
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return _oauth_result_page(False, "Google nie zwrócił refresh tokena. Cofnij dostęp aplikacji na myaccount.google.com/permissions i spróbuj połączyć ponownie.")
    await db.integration_tokens.update_one(
        {"provider": "gmail_send"},
        {"$set": {"refresh_token": refresh_token, "sender": GOOGLE_GMAIL_SENDER, "connected_at": now_iso()}},
        upsert=True,
    )
    return _oauth_result_page(True, f"Konto {GOOGLE_GMAIL_SENDER} zostało połączone. Kody odzyskiwania hasła będą teraz wysyłane z tego adresu.")


@api.get("/admin/users")
async def admin_users(q: str = "", _: UserDoc = Depends(admin_user)):
    flt = {"$or": [{"email": {"$regex": re.escape(q.strip()), "$options": "i"}},
                   {"name": {"$regex": re.escape(q.strip()), "$options": "i"}}]} if q.strip() else {}
    docs = await db.users.find(flt, {"password_hash": 0}).sort("created_at", -1).to_list(200)
    grants = await db.premium_grants.find({}, {"_id": 0}).to_list(200)
    return {"users": [admin_row(d) for d in docs], "pending": grants}


@api.post("/admin/users/{user_id}/premium")
async def admin_set_premium(user_id: str, data: PremiumToggle, admin: UserDoc = Depends(admin_user)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(404, "Nie znaleziono użytkownika.")
    premium = {"active": True, "plan": "gift", "since": now_iso(), "granted_by": admin.email} if data.active else None
    res = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"premium": premium}})
    if not res.matched_count:
        raise HTTPException(404, "Nie znaleziono użytkownika.")
    return {"ok": True, "is_premium": data.active}


@api.post("/admin/premium/grant")
async def admin_grant_by_email(data: GrantIn, admin: UserDoc = Depends(admin_user)):
    email = data.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Podaj poprawny adres e-mail.")
    premium = {"active": True, "plan": "gift", "since": now_iso(), "granted_by": admin.email}
    res = await db.users.update_one({"email": email}, {"$set": {"premium": premium}})
    if res.matched_count:
        return {"ok": True, "status": "granted", "message": f"Nadano Premium dla {email}."}
    await db.premium_grants.update_one({"email": email}, {"$set": {"email": email, "granted_by": admin.email, "created_at": now_iso()}}, upsert=True)
    return {"ok": True, "status": "pending", "message": f"{email} nie ma jeszcze konta — Premium włączy się automatycznie po rejestracji."}


@api.delete("/admin/premium/grant/{email}")
async def admin_remove_grant(email: str, _: UserDoc = Depends(admin_user)):
    await db.premium_grants.delete_one({"email": email.strip().lower()})
    return {"ok": True}


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    async for d in db.roadmaps.find({"path_id": {"$exists": False}}, {"_id": 1}):
        await db.roadmaps.update_one({"_id": d["_id"]}, {"$set": {"path_id": uuid.uuid4().hex[:12], "active": True}})
    await db.users.create_index("username_lower", unique=True, sparse=True)
    await db.gen_usage.create_index([("user_id", 1), ("month", 1)], unique=True)
    await db.premium_grants.create_index("email", unique=True)
    await db.oauth_states.create_index("created_at", expireAfterSeconds=600)
    await db.integration_tokens.create_index("provider", unique=True)
    if ADMIN_EMAILS:
        await db.users.update_many({"email": {"$in": list(ADMIN_EMAILS)}}, {"$set": {"role": "admin"}})
    email = os.environ.get("ADMIN_EMAIL")
    username = os.environ.get("ADMIN_USERNAME")
    pw = os.environ.get("ADMIN_PASSWORD")
    if email and pw and not await db.users.find_one({"email": email}):
        await db.users.insert_one(UserDoc(email=email, name="Admin", password_hash=hash_pw(pw), role="admin", created_at=now_iso()).to_mongo())
    if email and username:  # never overwrites the password, only attaches the login name
        await db.users.update_one({"email": email}, {"$set": {"username": username, "username_lower": username.strip().lower()}})


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
