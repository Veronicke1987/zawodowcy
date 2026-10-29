from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict
from typing import Annotated, Any, Optional, List
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, quote_plus
from pathlib import Path
from bson import ObjectId
import asyncio
import bcrypt
import jwt
import json
import logging
import os
import re
import uuid

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone  # noqa: E402

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"
LLM_KEY = os.environ['EMERGENT_LLM_KEY']
ANALYSIS_MODEL = ("anthropic", "claude-sonnet-5-5")
FAST_MODEL = ("openai", "gpt-6-luna")

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


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=200)
    name: str = ""


class ProfileIn(BaseModel):
    answers: dict


class RoadmapIn(BaseModel):
    career_id: str


class TaskToggle(BaseModel):
    done: bool


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


async def public_user(u: UserDoc) -> dict:
    profile = await db.profiles.find_one({"user_id": u.id}, {"_id": 0, "user_id": 1})
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "has_profile": bool(profile),
            "is_premium": bool(u.premium and u.premium.get("active"))}


# ---------------------------------------------------------------- LLM helpers
async def ask_llm(model: tuple, system: str, prompt: str) -> dict:
    chat = LlmChat(api_key=LLM_KEY, session_id=str(uuid.uuid4()), system_message=system).with_model(*model)
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
    "Wszystkie teksty po polsku."
)


def profile_text(answers: dict) -> str:
    return json.dumps(answers, ensure_ascii=False, indent=1)


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


# ---------------------------------------------------------------- auth routes
@api.post("/auth/register", status_code=201)
async def register(data: Credentials):
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Podaj poprawny adres e-mail.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Konto z tym adresem już istnieje.")
    user = UserDoc(email=email, name=data.name.strip(), password_hash=hash_pw(data.password), created_at=now_iso())
    res = await db.users.insert_one(user.to_mongo())
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


@api.get("/auth/me")
async def me(user: UserDoc = Depends(current_user)):
    return await public_user(user)


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


# ---------------------------------------------------------------- recommendations
async def run_recommendations(user_id: str, answers: dict, job_id: str):
    prompt = f"""Profil użytkownika (odpowiedzi z ankiety):
{profile_text(answers)}

Zaproponuj zawody dopasowane do tej osoby, w dwóch kategoriach:
- "now": 5 zawodów, które może wykonywać JUŻ TERAZ z obecnymi umiejętnościami (wymagania typowych ofert spełnia lub prawie spełnia),
- "future": 5 zawodów, które do niej pasują, ale wymagają zdobycia nowych umiejętności.
Nie ograniczaj się do oczywistych zawodów — uwzględnij też mniej znane stanowiska realnie występujące w polskich ogłoszeniach
(np. wdrożeniowiec systemów ERP, specjalista ds. wdrożeń, koordynator logistyki, analityk danych, specjalista ds. obsługi klienta B2B itp.).
Weź pod uwagę to, czego użytkownik nie lubi, jego charakter i odporność zawodu na automatyzację przez AI.

Zwróć JSON:
{{"summary": "2-3 zdania podsumowania profilu i mocnych stron",
 "now": [{{"title": "nazwa stanowiska jak w ogłoszeniach", "industry": "branża", "summary": "1-2 zdania", "why": "dlaczego pasuje (1-2 zdania)",
          "match": 0-100, "salary": "np. 6 000 – 8 500 zł brutto", "demand": "wysoki|średni|niski", "ai_risk": "niskie|średnie|wysokie",
          "missing_skills": ["..."]}}],
 "future": [ ...ten sam format... ]}}"""
    try:
        data = await ask_llm(ANALYSIS_MODEL, SYSTEM_PL, prompt)
        for cat in ("now", "future"):
            items = data.get(cat) or []
            for it in items:
                it["id"] = uuid.uuid4().hex[:12]
                it["category"] = cat
            data[cat] = items
        await db.recommendations.update_one(
            {"user_id": user_id, "job_id": job_id},
            {"$set": {"status": "ready", "summary": data.get("summary", ""), "now": data["now"],
                      "future": data["future"], "updated_at": now_iso()}},
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
        {"$set": {"user_id": user.id, "status": "pending", "job_id": job_id, "started_at": now_iso()}},
        upsert=True,
    )
    spawn(run_recommendations(user.id, prof["answers"], job_id))
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


async def find_career(user_id: str, career_id: str) -> dict:
    doc = await db.recommendations.find_one({"user_id": user_id}, {"_id": 0})
    if doc:
        for it in (doc.get("now") or []) + (doc.get("future") or []):
            if it["id"] == career_id:
                return it
    raise HTTPException(404, "Nie znaleziono zawodu.")


@api.get("/careers/{career_id}")
async def career_detail(career_id: str, user: UserDoc = Depends(current_user)):
    career = await find_career(user.id, career_id)
    cached = await db.career_details.find_one({"user_id": user.id, "career_id": career_id}, {"_id": 0})
    if cached:
        return {"career": career, "detail": cached["detail"], "job_links": job_links(career["title"])}
    prof = await db.profiles.find_one({"user_id": user.id}) or {}
    prompt = f"""Zawód: {career['title']} (branża: {career.get('industry', '')}).
Profil użytkownika: {profile_text(prof.get('answers', {}))}

Opisz ten zawód na podstawie typowych ofert pracy w Polsce (Pracuj.pl, OLX, LinkedIn). Zwróć JSON:
{{"description": "3-4 zdania opisu zawodu",
 "daily_tasks": ["4-6 typowych codziennych zadań"],
 "pros": ["4-5 plusów"], "cons": ["3-5 minusów"],
 "requirements": ["5-8 typowych wymagań z ogłoszeń, np. wykształcenie, znajomość programów, prawo jazdy kat. B, języki"],
 "how_to_start": ["4-6 konkretnych kroków, co ta osoba powinna zrobić żeby zacząć pracę w tym zawodzie"],
 "career_levels": ["kolejne stanowiska od wejściowego do najwyższego, 4-5 pozycji"]}}"""
    try:
        detail = await ask_llm(FAST_MODEL, SYSTEM_PL, prompt)
    except Exception:
        logger.exception("detail failed")
        raise HTTPException(502, "Nie udało się przygotować opisu. Spróbuj ponownie.")
    await db.career_details.update_one(
        {"user_id": user.id, "career_id": career_id},
        {"$set": {"detail": detail, "created_at": now_iso()}},
        upsert=True,
    )
    return {"career": career, "detail": detail, "job_links": job_links(career["title"])}


# ---------------------------------------------------------------- premium (demo mode, no real payments yet)
PREMIUM_PATH_LIMIT = 3
FREE_CHAT_PER_DAY = 5
PREMIUM_PLANS = {
    "monthly": {"label": "Miesięczny", "price": "19,99 zł", "period": "miesiąc"},
    "yearly": {"label": "Roczny", "price": "149,99 zł", "period": "rok"},
}


class PremiumIn(BaseModel):
    plan: str


def is_premium(u: UserDoc) -> bool:
    return bool(u.premium and u.premium.get("active"))


@api.get("/premium")
async def premium_info(user: UserDoc = Depends(current_user)):
    return {"is_premium": is_premium(user), "premium": user.premium, "plans": PREMIUM_PLANS,
            "path_limit": PREMIUM_PATH_LIMIT, "free_chat_per_day": FREE_CHAT_PER_DAY, "demo": True}


@api.post("/premium/subscribe")
async def premium_subscribe(data: PremiumIn, user: UserDoc = Depends(current_user)):
    if data.plan not in PREMIUM_PLANS:
        raise HTTPException(400, "Nieznany plan.")
    premium = {"active": True, "plan": data.plan, "since": now_iso(), "demo": True}
    await db.users.update_one({"_id": ObjectId(user.id)}, {"$set": {"premium": premium}})
    return {"ok": True, "premium": premium}


@api.post("/premium/cancel")
async def premium_cancel(user: UserDoc = Depends(current_user)):
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


async def run_roadmap(user_id: str, career: dict, answers: dict, job_id: str):
    prompt = f"""Użytkownik wybrał ścieżkę kariery: {career['title']} (branża: {career.get('industry', '')}).
Profil użytkownika: {profile_text(answers)}

Zbuduj ścieżkę kariery w formie drogi: 4-5 DUŻYCH punktów (stanowisk) od wejściowego do najwyższego (np. junior → specjalista → senior → kierownik/ekspert → dyrektor).
Do każdego stanowiska podaj 3-5 MAŁYCH punktów (zadań), które użytkownik musi zdobyć/wykonać, aby dostać to stanowisko —
opartych na wymaganiach z prawdziwych ofert pracy (np. studia z danej dziedziny, kurs Excela, znajomość programu Symfonia/SAP/Comarch,
prawo jazdy kat. B, certyfikat, język angielski B2, 2 lata doświadczenia). Uwzględnij to, co użytkownik już ma — takie zadania oznacz "already_has": true.
Zwróć JSON:
{{"milestones": [{{"title": "stanowisko", "description": "1-2 zdania", "salary": "widełki brutto", "years": "np. 0-2 lata",
   "requirements": ["wymagania z ofert"],
   "tasks": [{{"title": "krótka nazwa zadania", "description": "1 zdanie co dokładnie zrobić",
              "type": "studies|course|skill|certificate|language|license|experience|other", "already_has": false}}]}}]}}"""
    try:
        data = await ask_llm(ANALYSIS_MODEL, SYSTEM_PL, prompt)
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
    except Exception as e:
        logger.exception("roadmap failed")
        await db.roadmaps.update_one({"user_id": user_id, "job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:200]}})


@api.post("/roadmap")
async def choose_path(data: RoadmapIn, user: UserDoc = Depends(current_user)):
    career = await find_career(user.id, data.career_id)
    await db.roadmaps.delete_many({"user_id": user.id, "status": "error"})
    existing = await db.roadmaps.find({"user_id": user.id}, {"_id": 0, "path_id": 1, "career": 1, "status": 1}).to_list(100)
    same = next((d for d in existing if d["career"]["title"] == career["title"] and d.get("status") != "error"), None)
    if same:
        await db.roadmaps.update_many({"user_id": user.id}, {"$set": {"active": False}})
        await db.roadmaps.update_one({"user_id": user.id, "path_id": same["path_id"]}, {"$set": {"active": True}})
        return {"status": same["status"], "path_id": same["path_id"], "existing": True}
    if not is_premium(user):
        await db.roadmaps.delete_many({"user_id": user.id})
    elif len(existing) >= PREMIUM_PATH_LIMIT:
        raise HTTPException(403, f"Masz już {PREMIUM_PATH_LIMIT} ścieżki. Usuń jedną w zakładce Droga, aby dodać nową.")
    prof = await db.profiles.find_one({"user_id": user.id}) or {}
    job_id = uuid.uuid4().hex
    path_id = uuid.uuid4().hex[:12]
    await db.roadmaps.update_many({"user_id": user.id}, {"$set": {"active": False}})
    await db.roadmaps.insert_one({"user_id": user.id, "path_id": path_id, "active": True, "career": career, "status": "pending",
                                  "job_id": job_id, "milestones": [], "started_at": now_iso(), "created_at": now_iso()})
    spawn(run_roadmap(user.id, career, prof.get("answers", {}), job_id))
    return {"status": "pending", "path_id": path_id}


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
    return {"paths": out, "limit": PREMIUM_PATH_LIMIT if is_premium(user) else 1, "is_premium": is_premium(user)}


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
    if task.get("resources"):
        return task["resources"]
    prof = await db.profiles.find_one({"user_id": user.id}) or {}
    city = (prof.get("answers") or {}).get("city", "") or ""
    prompt = f"""Ścieżka kariery: {doc['career']['title']}. Stanowisko docelowe: {milestone['title']}.
Zadanie do zdobycia: {task['title']} — {task['description']} (typ: {task['type']}).
Miejscowość użytkownika: {city or 'nie podano'}.

Podpowiedz, jak zdobyć ten punkt. Jeśli to studia — opisz kierunki, tryby (dzienne/zaoczne/podyplomowe), możliwe specjalizacje, gdzie szukać rekrutacji.
Jeśli to umiejętność/program (np. Excel) — kanały YouTube, platformy szkoleniowe, jak korzystać darmowo (np. Excel w przeglądarce w Microsoft 365 online),
kursy finansowane przez urząd pracy (bon szkoleniowy, KFS), webinary.
Zwróć JSON:
{{"overview": "2-3 zdania czym jest ten punkt i dlaczego jest ważny",
 "steps": ["3-5 konkretnych kroków jak to zdobyć"],
 "free_tips": ["2-4 sposoby zrobienia tego za darmo lub taniej"],
 "specializations": ["tylko dla studiów/kursów: możliwe specjalizacje, inaczej pusta lista"],
 "time_estimate": "ile to zwykle trwa",
 "resources": [{{"type": "youtube|course|studies|urzad_pracy|webinar|certificate|article", "platform": "np. YouTube, Coursera, Udemy, LinkedIn Learning, Google",
                "title": "nazwa zasobu", "description": "1 zdanie", "query": "fraza wyszukiwania po polsku"}}]}}
Podaj 5-8 zasobów, w tym przynajmniej jeden YouTube i jeden urzad_pracy."""
    try:
        data = await ask_llm(FAST_MODEL, SYSTEM_PL, prompt)
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
    return data


# ---------------------------------------------------------------- weekly study plan (premium)
async def run_study_plan(user_id: str, path_id: str, job_id: str):
    doc = await db.roadmaps.find_one({"user_id": user_id, "path_id": path_id})
    prof = await db.profiles.find_one({"user_id": user_id}) or {}
    answers = prof.get("answers", {})
    todo = [f"- [{m['title']}] {t['title']}: {t['description']}" for m in doc.get("milestones", []) for t in m["tasks"] if not t.get("done")]
    done = [t["title"] for m in doc.get("milestones", []) for t in m["tasks"] if t.get("done")]
    prompt = f"""Ścieżka kariery: {doc['career']['title']}.
Czas, który użytkownik może poświęcić na naukę: {answers.get('learn_time', 'nie podano')}. Obecna sytuacja: {answers.get('current_status', '')}.
Już zdobyte: {', '.join(done) or 'nic'}.
Do zdobycia (w kolejności drogi):
{chr(10).join(todo[:20]) or '- wszystko zdobyte, zaplanuj szukanie pracy i rozwój'}

Ułóż realistyczny plan nauki na 8 tygodni, skupiony na najbliższych punktach drogi. Każdy tydzień: cel i 3-5 konkretnych zadań z liczbą godzin.
Uwzględnij darmowe materiały, kursy z urzędu pracy, ćwiczenia praktyczne i budowanie portfolio/CV.
Zwróć JSON:
{{"hours_per_week": liczba, "summary": "1-2 zdania",
 "weeks": [{{"week": 1, "focus": "temat tygodnia", "goal": "co umiesz po tygodniu",
            "items": [{{"title": "zadanie", "description": "1 zdanie jak to zrobić", "hours": liczba}}]}}],
 "tips": ["3 rady motywacyjne/organizacyjne"]}}"""
    try:
        plan = await ask_llm(ANALYSIS_MODEL, SYSTEM_PL, prompt)
        await db.roadmaps.update_one({"user_id": user_id, "path_id": path_id, "study_plan.job_id": job_id},
                                     {"$set": {"study_plan.status": "ready", "study_plan.plan": plan, "study_plan.updated_at": now_iso()}})
    except Exception as e:
        logger.exception("study plan failed")
        await db.roadmaps.update_one({"user_id": user_id, "path_id": path_id, "study_plan.job_id": job_id},
                                     {"$set": {"study_plan.status": "error", "study_plan.error": str(e)[:200]}})


@api.post("/roadmap/study-plan")
async def create_study_plan(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    if not is_premium(user):
        raise HTTPException(402, "Plan nauki tydzień po tygodniu jest dostępny w Premium.")
    doc = await get_path(user.id, path_id, {"_id": 0, "path_id": 1, "status": 1})
    if not doc or doc["status"] != "ready":
        raise HTTPException(400, "Najpierw wybierz ścieżkę i poczekaj, aż droga będzie gotowa.")
    job_id = uuid.uuid4().hex
    await db.roadmaps.update_one({"user_id": user.id, "path_id": doc["path_id"]},
                                 {"$set": {"study_plan": {"status": "pending", "job_id": job_id, "started_at": now_iso()}}})
    spawn(run_study_plan(user.id, doc["path_id"], job_id))
    return {"status": "pending"}


@api.get("/roadmap/study-plan")
async def get_study_plan(path_id: Optional[str] = None, user: UserDoc = Depends(current_user)):
    doc = await get_path(user.id, path_id, {"_id": 0, "study_plan": 1, "career": 1, "path_id": 1})
    if not doc:
        return {"status": "none"}
    sp = doc.get("study_plan") or {"status": "none"}
    if sp.get("status") == "pending" and datetime.now(timezone.utc) - datetime.fromisoformat(sp["started_at"]) > timedelta(minutes=4):
        sp["status"] = "error"
    return {"status": sp.get("status"), "plan": sp.get("plan"), "career": doc.get("career"), "path_id": doc["path_id"]}


# ---------------------------------------------------------------- advisor chat
class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def today_start_iso() -> str:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def chat_remaining(user: UserDoc) -> Optional[int]:
    if is_premium(user):
        return None
    doc = await db.chat_usage.find_one({"user_id": user.id, "day": today_key()})
    return max(FREE_CHAT_PER_DAY - (doc or {}).get("count", 0), 0)


async def reserve_chat(user: UserDoc) -> Optional[int]:
    """Atomically use one free question (separate from message history, so clearing chat does not reset it)."""
    if is_premium(user):
        return None
    doc = await db.chat_usage.find_one_and_update(
        {"user_id": user.id, "day": today_key()}, {"$inc": {"count": 1}}, upsert=True, return_document=True)
    if doc["count"] > FREE_CHAT_PER_DAY:
        await db.chat_usage.update_one({"_id": doc["_id"]}, {"$inc": {"count": -1}})
        raise HTTPException(429, f"Wykorzystano {FREE_CHAT_PER_DAY} darmowych pytań na dziś. Wróć jutro lub przejdź na Premium.")
    return FREE_CHAT_PER_DAY - doc["count"]


async def refund_chat(user_id: str):
    await db.chat_usage.update_one({"user_id": user_id, "day": today_key(), "count": {"$gt": 0}}, {"$inc": {"count": -1}})


@api.get("/chat")
async def chat_history(user: UserDoc = Depends(current_user)):
    msgs = await db.chat_messages.find({"user_id": user.id}, {"_id": 0, "user_id": 0}).sort("created_at", -1).to_list(60)
    return {"messages": list(reversed(msgs)), "remaining": await chat_remaining(user), "limit": FREE_CHAT_PER_DAY,
            "is_premium": is_premium(user)}


@api.delete("/chat")
async def chat_clear(user: UserDoc = Depends(current_user)):
    await db.chat_messages.delete_many({"user_id": user.id})
    return {"ok": True}


@api.post("/chat/stream")
async def chat_stream(data: ChatIn, user: UserDoc = Depends(current_user)):
    remaining = await reserve_chat(user)
    prof = await db.profiles.find_one({"user_id": user.id}) or {}
    path = await get_path(user.id, None, ROADMAP_PROJ)
    path_txt = "Użytkownik nie wybrał jeszcze ścieżki kariery."
    if path and path.get("milestones"):
        lines = []
        for m in path["milestones"]:
            ts = ", ".join(f"{t['title']} ({'zdobyte' if t['done'] else 'do zrobienia'})" for t in m["tasks"])
            lines.append(f"- {m['title']}: {ts}")
        path_txt = f"Wybrana ścieżka: {path['career']['title']}\n" + "\n".join(lines)
    history = await db.chat_messages.find({"user_id": user.id}, {"_id": 0}).sort("created_at", -1).to_list(12)
    history_txt = "\n".join(f"{'Użytkownik' if h['role'] == 'user' else 'Doradca'}: {h['text']}" for h in reversed(history))
    system = (
        "Jesteś ciepłym, konkretnym doradcą zawodowym w aplikacji Reset, pomagającym ludziom zmienić zawód w Polsce. "
        "Odpowiadasz po polsku, zwięźle (maks. ok. 150-200 słów), praktycznie, z konkretnymi krokami. "
        "Pisz zwykłym tekstem bez markdown (bez **, # i tabel); listy zapisuj w nowych liniach zaczynając od '• '. Nie wymyślaj konkretnych adresów URL — zamiast tego podawaj frazy do wyszukania "
        "lub nazwy serwisów (Pracuj.pl, OLX Praca, LinkedIn, YouTube, urząd pracy, praca.gov.pl).\n\n"
        f"Profil użytkownika: {profile_text(prof.get('answers', {}))}\n\n{path_txt}"
    )
    prompt = (f"Dotychczasowa rozmowa:\n{history_txt}\n\n" if history_txt else "") + f"Nowe pytanie użytkownika: {data.text}"
    await db.chat_messages.insert_one({"id": uuid.uuid4().hex, "user_id": user.id, "role": "user", "text": data.text, "created_at": now_iso()})

    async def gen():
        chat = LlmChat(api_key=LLM_KEY, session_id=str(uuid.uuid4()), system_message=system).with_model(*FAST_MODEL)
        full = ""
        try:
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    full += ev.content
                    yield f"data: {json.dumps({'t': ev.content}, ensure_ascii=False)}\n\n"
                elif isinstance(ev, StreamDone):
                    break
        except Exception:
            logger.exception("chat failed")
            yield f"data: {json.dumps({'error': 'Doradca chwilowo nie odpowiada. Spróbuj ponownie.'}, ensure_ascii=False)}\n\n"
        if full:
            await db.chat_messages.insert_one({"id": uuid.uuid4().hex, "user_id": user.id, "role": "assistant", "text": full, "created_at": now_iso()})
        elif remaining is not None:
            await refund_chat(user.id)
        left = remaining if full or remaining is None else remaining + 1
        yield f"data: {json.dumps({'done': True, 'remaining': left})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.chat_messages.create_index([("user_id", 1), ("created_at", -1)])
    await db.chat_usage.create_index([("user_id", 1), ("day", 1)], unique=True)
    async for d in db.roadmaps.find({"path_id": {"$exists": False}}, {"_id": 1}):
        await db.roadmaps.update_one({"_id": d["_id"]}, {"$set": {"path_id": uuid.uuid4().hex[:12], "active": True}})
    await db.users.create_index("username_lower", unique=True, sparse=True)
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
