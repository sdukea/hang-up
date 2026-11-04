"""Kaam backend.

Proxies browser microphone audio to Prisma (browsers can't set the custom
headers Prisma needs, and this keeps the API key off the client) and relays
transcripts back. Also exposes Timbre TTS so the app can talk to the worker,
stores finished interviews, and turns them into shareable profile cards.
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import re
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel, Field

from . import config, llm, questions, resume, samples, tts
from .storage import store
from .stt import FINAL_EVENTS, PrismaStream

# Some systems map .m4a to audio/mp4a-latm, which Safari and Firefox won't play.
mimetypes.add_type("audio/mp4", ".m4a")

log = logging.getLogger("kaam")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Kaam")

FRONTEND = config.ROOT / "frontend"
ID_RE = re.compile(r"^[0-9a-f]{10}$")
# Profiles never change once written, so audio can be cached by browsers.
AUDIO_HEADERS = {"Cache-Control": "public, max-age=86400"}


_profile_requests: dict[str, deque] = defaultdict(deque)
_listen_sessions = 0


def _rate_limit(ip: str, limit: int, window_s: float = 3600) -> None:
    """In-memory sliding window; enough for a single-instance deployment."""
    now = time.monotonic()
    hits = _profile_requests[ip]
    while hits and now - hits[0] > window_s:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="Too many resumes from this network. Try again later.")
    hits.append(now)


async def _load(kind: str, item_id: str) -> dict:
    data = await store.get(f"{kind}/{item_id}.json") if ID_RE.match(item_id) else None
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    return json.loads(data)


async def _save(kind: str, item_id: str, record: dict) -> None:
    data = json.dumps(record, ensure_ascii=False, indent=2).encode()
    await store.put(f"{kind}/{item_id}.json", data, "application/json")


def _check_lang(lang: str) -> None:
    if lang not in questions.LANGUAGES:
        raise HTTPException(status_code=404, detail=f"Unsupported language: {lang}")


@app.get("/api/health")
async def health(deep: bool = False):
    """Liveness for the host; ?deep=1 also checks storage, for uptime alerts."""
    status = {"ok": True, "key_configured": bool(config.GNANI_API_KEY)}
    if deep:
        try:
            await store.exists("health")
            status["storage"] = "ok"
        except Exception as e:
            log.warning("Storage health check failed: %s", e)
            status.update(ok=False, storage="unreachable")
        status["ok"] = status["ok"] and status["key_configured"] and bool(config.LLM_MODEL)
        if not status["ok"]:
            return Response(json.dumps(status), status_code=503, media_type="application/json")
    return status


@app.get("/api/languages")
async def languages():
    return [{"code": code, **info} for code, info in questions.LANGUAGES.items()]


@app.get("/api/samples")
async def sample_workers():
    return samples.public_manifest()


@app.get("/api/questions/{lang}")
async def interview_questions(lang: str):
    _check_lang(lang)
    return questions.questions_for(lang)


async def _cached_speech(key: str, text: str, lang: str) -> Response:
    """Spoken prompt, synthesized once and stored to save credits."""
    audio = await store.get(key)
    if audio is None:
        try:
            audio = await tts.synthesize(text, lang)
        except (tts.TTSError, RuntimeError) as e:
            raise HTTPException(status_code=502, detail=str(e))
        await store.put(key, audio, "audio/wav")
    return Response(content=audio, media_type="audio/wav", headers=AUDIO_HEADERS)


@app.get("/api/questions/{lang}/{index}/audio")
async def question_audio(lang: str, index: int):
    _check_lang(lang)
    qs = questions.questions_for(lang)
    if not 0 <= index < len(qs):
        raise HTTPException(status_code=404, detail="No such question")
    key = f"cache/questions/{config.TTS_MODEL}-{config.TTS_VOICE}-{lang}-{qs[index]['id']}.wav"
    return await _cached_speech(key, qs[index]["text"], lang)


@app.get("/api/ui/{lang}")
async def ui_text(lang: str):
    _check_lang(lang)
    return questions.UI[lang]


@app.get("/api/ui/{lang}/intro/audio")
async def intro_audio(lang: str):
    """The consent notice read aloud. The text's hash keeps the cache honest if it changes."""
    _check_lang(lang)
    text = questions.UI[lang]["intro"]
    digest = hashlib.sha256(text.encode()).hexdigest()[:8]
    return await _cached_speech(f"cache/ui/{config.TTS_MODEL}-{config.TTS_VOICE}-{lang}-intro-{digest}.wav", text, lang)


class Answer(BaseModel):
    question_id: str = Field(max_length=40)
    question: str = Field(max_length=500)
    transcript: str = Field(max_length=4000)
    detected_languages: list[str] = Field(default=[], max_length=10)


class Interview(BaseModel):
    language: str
    consent: bool
    answers: list[Answer] = Field(min_length=1, max_length=len(questions.QUESTION_IDS))
    sample_id: str | None = Field(default=None, max_length=40)
    # Which voice introduces the worker on their card; chosen by the worker.
    intro_voice: Literal["male", "female"] | None = None


@app.post("/api/interviews")
async def save_interview(interview: Interview):
    _check_lang(interview.language)
    if not interview.consent:
        raise HTTPException(status_code=400, detail="Consent is required")
    if interview.sample_id and interview.sample_id not in samples.BY_ID:
        raise HTTPException(status_code=400, detail="Unknown sample worker")
    interview_id = uuid.uuid4().hex[:10]
    record = {
        "id": interview_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **interview.model_dump(),
    }
    await _save("interviews", interview_id, record)
    return {"id": interview_id}


@app.post("/api/interviews/{interview_id}/profile")
async def create_profile(interview_id: str, request: Request):
    """Write the resume with the LLM and record spoken intros with Timbre."""
    interview = await _load("interviews", interview_id)
    if await store.exists(f"profiles/{interview_id}.json"):
        return await _load("profiles", interview_id)
    _rate_limit(request.client.host if request.client else "?", config.PROFILES_PER_IP_PER_HOUR)
    lang = interview["language"]
    try:
        profile = await resume.build_profile(interview)
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # The worker's own choice wins; otherwise use gender only when their speech
    # showed it grammatically.
    voice_gender = interview.get("intro_voice") or profile["speaker_gender"]
    voice = {"male": config.TTS_VOICE_MALE, "female": config.TTS_VOICE_FEMALE}.get(voice_gender, config.TTS_VOICE)
    intros = {"en": ("en-IN", profile["intro_en"])}
    if lang != "en-IN":
        intros["native"] = (lang, profile["intro_native"])

    async def record_intro(which: str, intro_lang: str, text: str) -> str | None:
        try:
            wav = await tts.synthesize(text, intro_lang, voice=voice)
        except (tts.TTSError, RuntimeError) as e:
            log.warning("Intro TTS failed (%s): %s", which, e)
            return None
        await store.put(f"profiles/{interview_id}-{which}.wav", wav, "audio/wav")
        return f"/api/profiles/{interview_id}/audio/{which}"

    # Sequential: Timbre serves one request per account at a time.
    audio = {}
    for which, (intro_lang, text) in intros.items():
        if text and (url := await record_intro(which, intro_lang, text)):
            audio[which] = url

    record = {
        "id": interview_id,
        "language": lang,
        "language_name": questions.LANGUAGES[lang]["name"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "audio": audio,
    }
    if sample := samples.BY_ID.get(interview.get("sample_id") or ""):
        # Sample workers are fictional, so their transcripts can be public:
        # the card shows what was said next to what Prisma heard.
        script = dict(zip(questions.QUESTION_IDS, sample["answers"]))
        record["sample"] = {"id": sample["id"], "scene_label": sample["scene_label"]}
        record["comparison"] = [
            {"question": a["question"], "script": script.get(a["question_id"], ""), "heard": a["transcript"]}
            for a in interview["answers"]
        ]
    await _save("profiles", interview_id, record)
    return record


@app.get("/api/profiles/{profile_id}")
async def get_profile(profile_id: str):
    return await _load("profiles", profile_id)


@app.get("/api/profiles/{profile_id}/audio/{which}")
async def profile_audio(profile_id: str, which: str):
    valid = ID_RE.match(profile_id) and which in ("en", "native")
    audio = await store.get(f"profiles/{profile_id}-{which}.wav") if valid else None
    if audio is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(content=audio, media_type="audio/wav", headers=AUDIO_HEADERS)


@app.get("/p/{profile_id}")
async def profile_page(profile_id: str):
    return FileResponse(FRONTEND / "card.html")


@app.websocket("/ws/listen")
async def listen(browser: WebSocket, lang: str | None = None):
    """Browser sends PCM16 mono audio at STT_SAMPLE_RATE; we send back Prisma events.

    Text frames from the browser: "flush" sends trailing silence so Prisma
    finalizes the last segment, then replies {"type": "flushed"}.
    """
    global _listen_sessions
    await browser.accept()
    if _listen_sessions >= config.MAX_LISTEN_SESSIONS:
        await browser.send_json({"type": "error", "message": "Kaam is busy right now. Please try again in a minute."})
        await browser.close()
        return
    stt_lang = questions.stt_lang_for(lang) if lang in questions.LANGUAGES else config.STT_LANG
    try:
        prisma = PrismaStream(lang=stt_lang)
        await prisma.connect()
    except Exception as e:
        log.warning("Prisma connect failed: %s", e)
        await browser.send_json({"type": "error", "message": "Could not reach the speech service."})
        await browser.close()
        return
    _listen_sessions += 1

    async def browser_to_prisma():
        while True:
            msg = await browser.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes"):
                await prisma.send_audio(msg["bytes"])
            elif msg.get("text") == "flush":
                await prisma.flush()
                await browser.send_json({"type": "flushed"})

    async def prisma_to_browser():
        async for event in prisma.events():
            if event.get("type") in FINAL_EVENTS:
                log.info("[%s] %s", event.get("detected_language_code", "?"), event.get("text"))
            await browser.send_json(event)

    tasks = [asyncio.create_task(browser_to_prisma()), asyncio.create_task(prisma_to_browser())]
    try:
        done, _ = await asyncio.wait(tasks, timeout=config.MAX_ANSWER_SECONDS, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            await browser.send_json({"type": "error", "message": "That answer was very long, so listening stopped."})
            await browser.close()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        _listen_sessions -= 1
        for t in tasks:
            t.cancel()
        await prisma.close()


app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
