# RCA helper (iteration 7): capture raw Sonnet output for study plan prompt to check truncation vs malformed JSON
import asyncio, json, re, sys, uuid
sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone  # noqa: E402


async def main():
    doc = await server.db.roadmaps.find_one({"study_plan.status": "error", "career.title": {"$exists": True}}, sort=[("created_at", -1)])
    todo = [f"- [{m['title']}] {t['title']}: {t['description']}" for m in doc["milestones"] for t in m["tasks"] if not t.get("done")]
    prompt = f"""Ścieżka kariery: {doc['career']['title']}.
Czas, który użytkownik może poświęcić na naukę: 5 godzin tygodniowo.
Do zdobycia (w kolejności drogi):
{chr(10).join(todo[:20])}

Ułóż realistyczny plan nauki na 8 tygodni, skupiony na najbliższych punktach drogi. Każdy tydzień: cel i 3-5 konkretnych zadań z liczbą godzin.
Uwzględnij darmowe materiały, kursy z urzędu pracy, ćwiczenia praktyczne i budowanie portfolio/CV.
Zwróć JSON:
{{"hours_per_week": liczba, "summary": "1-2 zdania",
 "weeks": [{{"week": 1, "focus": "temat tygodnia", "goal": "co umiesz po tygodniu",
            "items": [{{"title": "zadanie", "description": "1 zdanie jak to zrobić", "hours": liczba}}]}}],
 "tips": ["3 rady motywacyjne/organizacyjne"]}}"""
    chat = LlmChat(api_key=server.LLM_KEY, session_id=str(uuid.uuid4()), system_message=server.SYSTEM_PL).with_model(*server.ANALYSIS_MODEL)
    text, last = "", None
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            text += ev.content
        elif isinstance(ev, StreamDone):
            last = ev
            break
    print("LEN", len(text))
    print("DONE_EVENT", repr(last)[:500])
    print("TAIL", repr(text[-300:]))
    m = re.search(r"\{.*\}", text, re.S)
    try:
        json.loads(m.group(0))
        print("JSON OK")
    except Exception as e:
        print("JSON ERR", e)
        pos = e.pos if hasattr(e, "pos") else 0
        print("CONTEXT", repr(m.group(0)[max(0, pos - 150):pos + 50]))

asyncio.run(main())
