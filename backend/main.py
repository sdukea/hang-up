"""Scam Dadi backend: runs each call, and proxies microphone audio to Prisma.

The OTP and the scoring live here, so a player can't read them from the page.
Browsers can't set the headers Prisma needs, and this keeps the API key private.
"""

import asyncio
import json
import logging
import random
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, game, tts
from .storage import store
from .stt import FINAL_EVENTS, PrismaStream

log = logging.getLogger("dadi")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Scam Dadi")
FRONTEND = config.ROOT / "frontend"
STATS_KEY = "stats.json"

games: dict[str, game.Game] = {}
speech: dict[str, tuple[str, float]] = {}
_starts: dict[str, deque] = defaultdict(deque)
_listen_sessions = 0
stats = {
    "plays": 0, "cracked": 0, "busted": 0, "timeouts": 0, "seconds": 0,
    "quiz_before": [0, 0], "quiz_after": [0, 0],  # [answered correctly, answered]
}
_stats_dirty = False


@app.on_event("startup")
async def load_stats():
    try:
        saved = await store.get(STATS_KEY)
        if saved:
            stats.update(json.loads(saved))
    except Exception as e:
        log.warning("Could not load stats: %s", e)
    asyncio.create_task(_save_stats_forever())


async def _save_stats_forever():
    global _stats_dirty
    while True:
        await asyncio.sleep(20)
        if _stats_dirty:
            _stats_dirty = False
            try:
                await store.put(STATS_KEY, json.dumps(stats).encode(), "application/json")
            except Exception as e:
                log.warning("Could not save stats: %s", e)


def _get_game(game_id: str) -> game.Game:
    g = games.get(game_id)
    if not g:
        raise HTTPException(status_code=404, detail="This call has ended.")
    return g


def _seconds_left(g: game.Game) -> float:
    # A little grace for the phone ringing before the player's clock starts.
    return game.GAME_SECONDS + 15 - (time.time() - g.started)


def _purge():
    cutoff = time.time() - 900
    for key in [k for k, g in games.items() if g.started < cutoff]:
        del games[key]
    for key in [k for k, (_, at) in speech.items() if at < cutoff]:
        del speech[key]


@app.get("/api/health")
async def health(deep: bool = False):
    status = {"ok": True}
    if deep:
        ok = bool(config.GNANI_API_KEY and config.LLM_MODEL)
        try:
            await store.exists("health")
        except Exception as e:
            log.warning("Storage check failed: %s", e)
            ok = False
        status["ok"] = ok
        if not ok:
            return Response(json.dumps(status), status_code=503, media_type="application/json")
    return status


@app.get("/api/stats")
async def public_stats():
    return {
        "plays": stats["plays"], "cracked": stats["cracked"],
        "minutes": round(stats["seconds"] / 60),
    }


class Start(BaseModel):
    hour: int = Field(ge=0, le=23)
    returning_name: str | None = Field(default=None, max_length=40)
    quiz: bool | None = None


@app.post("/api/game/start")
async def start_game(body: Start, request: Request):
    global _stats_dirty
    _purge()
    ip = request.client.host if request.client else "?"
    hits, now = _starts[ip], time.time()
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= config.GAMES_PER_IP_PER_HOUR:
        raise HTTPException(status_code=429, detail="Dadi has gone for her nap. Try again in a while.")
    hits.append(now)

    g = game.Game(body.hour, body.returning_name)
    games[g.id] = g
    if body.quiz is not None:
        stats["quiz_before"][0] += 1 if body.quiz is False else 0
        stats["quiz_before"][1] += 1
        _stats_dirty = True
    greet = "greet_back" if body.returning_name else f"greet_{g.mood_key}_{random.randrange(2)}"
    return {
        "id": g.id, "seconds": game.GAME_SECONDS, "mood": g.mood_key, "mood_name": g.mood["name"],
        "tagline": g.mood["tagline"], "twist": g.twist["label"], "greet": greet,
        "suspicion": round(g.suspicion), "boss": g.boss_hint(),
        "playbook": [{"id": t, "label": game.TACTICS[t]["label"]} for t in game.PLAYBOOK],
    }


class Turn(BaseModel):
    said: str = Field(min_length=1, max_length=600)


@app.post("/api/game/{game_id}/turn")
async def play_turn(game_id: str, body: Turn):
    g = _get_game(game_id)
    if g.outcome:
        raise HTTPException(status_code=409, detail="This call has ended.")
    result = await g.turn(body.said, _seconds_left(g))
    if result["canned"] is None:
        token = f"{g.id}-{g.turns}"
        speech[token] = (result["reply"], time.time())
        result["speech"] = f"/api/speech/{token}"
    else:
        result["speech"] = f"/audio/canned_{result['canned']}.mp3"
    return result


@app.get("/api/speech/{token}")
async def spoken_reply(token: str):
    """Only speaks replies the game itself generated, never arbitrary text."""
    item = speech.pop(token, None)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        audio = await tts.synthesize(item[0], "hi-IN", voice=config.DADI_VOICE, model=config.TTS_MODEL, speed=config.DADI_SPEED)
    except (tts.TTSError, RuntimeError) as e:
        log.warning("Speech failed: %s", e)
        raise HTTPException(status_code=502, detail="Dadi lost her voice")
    return Response(content=audio, media_type="audio/mpeg")


class Counter(BaseModel):
    effect: str = Field(max_length=20)
    passed: bool


@app.post("/api/game/{game_id}/counter")
async def counter_move(game_id: str, body: Counter):
    g = _get_game(game_id)
    if body.effect not in game.COUNTER_EFFECTS:
        raise HTTPException(status_code=400, detail="Unknown move")
    return g.counter_result(body.effect, body.passed)


@app.post("/api/game/{game_id}/end")
async def end_game(game_id: str):
    global _stats_dirty
    g = _get_game(game_id)
    if not g.outcome:
        g.finish_state(_seconds_left(g))
    first_report = not getattr(g, "reported", False)
    report = g.report()
    if first_report:
        g.reported = True
        stats["plays"] += 1
        stats["seconds"] += min(game.GAME_SECONDS, int(time.time() - g.started))
        if report["outcome"] == "cracked":
            stats["cracked"] += 1
        elif report["outcome"] == "busted":
            stats["busted"] += 1
        elif report["outcome"] == "timeout":
            stats["timeouts"] += 1
        _stats_dirty = True
    report["crack_rate"] = round(100 * stats["cracked"] / max(1, stats["plays"]), 1)
    return report


class Quiz(BaseModel):
    answer: bool


@app.post("/api/quiz")
async def quiz_after(body: Quiz):
    global _stats_dirty
    stats["quiz_after"][0] += 1 if body.answer is False else 0
    stats["quiz_after"][1] += 1
    _stats_dirty = True
    return {"correct": body.answer is False}


@app.websocket("/ws/listen")
async def listen(browser: WebSocket):
    """Browser sends PCM16 mono audio at 16 kHz; we send back Prisma events.

    The text frame "flush" sends trailing silence so Prisma finishes the last
    words, then replies {"type": "flushed"}.
    """
    global _listen_sessions
    await browser.accept()
    if _listen_sessions >= config.MAX_LISTEN_SESSIONS:
        await browser.send_json({"type": "error", "message": "busy"})
        await browser.close()
        return
    try:
        prisma = PrismaStream()
        await prisma.connect()
    except Exception as e:
        log.warning("Prisma connect failed: %s", e)
        await browser.send_json({"type": "error", "message": "unavailable"})
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
                await prisma.flush(600)
                await browser.send_json({"type": "flushed"})

    async def prisma_to_browser():
        async for event in prisma.events():
            if event.get("type") in FINAL_EVENTS:
                log.info("[heard] %s", event.get("text"))
            await browser.send_json(event)

    tasks = [asyncio.create_task(browser_to_prisma()), asyncio.create_task(prisma_to_browser())]
    try:
        await asyncio.wait(tasks, timeout=config.MAX_SESSION_SECONDS, return_when=asyncio.FIRST_COMPLETED)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        _listen_sessions -= 1
        for t in tasks:
            t.cancel()
        await prisma.close()


class Frontend(StaticFiles):
    """Revalidate on every load, so players never keep an old version after a deploy."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", Frontend(directory=FRONTEND, html=True), name="frontend")
