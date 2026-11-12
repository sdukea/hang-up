"""Hang Up backend: runs each call, and proxies microphone audio to Prisma.

The OTP and the scoring live here, so a player can't read them from the page.
Browsers can't set the headers Prisma needs, and this keeps the API key private.
"""

import asyncio
import json
import mimetypes
import logging
import os
import random
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import accounts, character, config, db, game, gender, progress, scenario, scoring, tts
from .storage import store
from .stt import PrismaStream

log = logging.getLogger("dadi")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Hang Up")


@app.middleware("http")
async def moved(request: Request, call_next):
    """The game has a new address. The health check stays here so the host keeps this running."""
    if config.REDIRECT_TO and request.url.path != "/api/health":
        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"{config.REDIRECT_TO}{request.url.path}{query}", status_code=302)
    return await call_next(request)
@app.middleware("http")
async def same_origin(request: Request, call_next):
    """Browsers send Origin on cross-site POSTs. Anything that changes state must come from this site."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin and origin.split("://", 1)[-1] != request.headers.get("host", ""):
            return JSONResponse({"detail": "Cross-site request refused."}, status_code=403)
    return await call_next(request)


FRONTEND = config.ROOT / "frontend"
STATS_KEY = "stats.json"

games: dict[str, game.Game] = {}
speech: dict[str, tuple[str, float, str, str, str]] = {}  # token -> text, made at, voice, language, model
_starts: dict[str, deque] = defaultdict(deque)
_listen_sessions = 0
stats = {
    "plays": 0, "cracked": 0, "busted": 0, "timeouts": 0, "reformed": 0, "seconds": 0,
    "flip": [0, 0],  # [hung up, answered], from the last round
    "quiz_before": [0, 0], "quiz_after": [0, 0],  # [answered correctly, answered]
}
_stats_dirty = False
IST = timezone(timedelta(hours=5, minutes=30))


def today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


@app.on_event("startup")
async def load_stats():
    await db.restore(store)
    await db.run(db.migrate)
    # Calls live in memory; any the database still thinks are running died with the last process.
    swept = await db.run(progress.sweep, set(), True)
    if swept:
        log.info("Closed %d calls left running by the last process", swept)
    asyncio.create_task(db.snapshot_forever(store))
    try:
        saved = await store.get(STATS_KEY)
        if saved:
            stats.update(json.loads(saved))
    except Exception as e:
        log.warning("Could not load stats: %s", e)
    asyncio.create_task(_save_stats_forever())
    asyncio.create_task(_stay_awake())


async def _stay_awake():
    """Render's free tier sleeps after 15 idle minutes, and the next player waits for a cold start.

    Render sets RENDER_EXTERNAL_URL, so this only runs there. The ping goes out through the public
    URL, which is what counts as traffic. It reads the health check and nothing else.
    """
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            await asyncio.sleep(600)
            try:
                await client.get(f"{url}/api/health")
            except Exception as e:
                log.warning("Keep-awake ping failed: %s", e)


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


async def current_user(request: Request) -> dict | None:
    """Who is signed in, from the session cookie. Never from anything the browser says about itself."""
    token = request.cookies.get(accounts.COOKIE)
    if not token:
        return None
    try:
        return await db.run(accounts.resolve, token)
    except Exception as e:
        log.warning("Session lookup failed: %s", e)
        return None


async def signed_in(request: Request) -> dict:
    user = await current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in first.")
    return user


async def _get_game(game_id: str, request: Request) -> game.Game:
    """A call, only for whoever started it. A signed-in player's call can't be touched from another
    account (or signed out); a guest's call is reachable only by its unguessable id."""
    g = games.get(game_id)
    if not g:
        raise HTTPException(status_code=404, detail="This call has ended.")
    if g.user_id is not None:
        user = await current_user(request)
        if not user or user["id"] != g.user_id:
            raise HTTPException(status_code=404, detail="This call has ended.")
    return g


async def _persist(fn, *args, **kwargs):
    """Record something about a call. The call itself never waits on, or fails because of, the database."""
    try:
        return await db.run(fn, *args, **kwargs)
    except Exception as e:
        log.warning("Couldn't save %s: %s", fn.__name__, e)
        return None


def _seconds_left(g: game.Game) -> float:
    # A little grace for the phone ringing before the player's clock starts.
    left = game.GAME_SECONDS + 15 - (time.time() - g.started)
    if g.clock_end:  # a scenario cut the call short (her battery is dying)
        left = min(left, g.clock_end + 5 - time.time())
    return left


def _purge():
    cutoff = time.time() - 900
    for key in [k for k, g in games.items() if g.started < cutoff]:
        if games[key].persisted and not games[key].outcome:
            asyncio.get_running_loop().create_task(_persist(progress.abandon, key))
        del games[key]
    for key in [k for k, (_, at, *_rest) in speech.items() if at < cutoff]:
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


# ---------- accounts ----------

class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=accounts.PASSWORD_MAX)


def _set_session(request: Request, response: Response, token: str) -> None:
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(accounts.COOKIE, token, max_age=config.SESSION_DAYS * 86400, httponly=True,
                        secure=secure, samesite="lax", path="/")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


@app.post("/api/auth/register")
async def register(body: Credentials, request: Request, response: Response):
    if not accounts.signup_by_ip.allow(_ip(request)):
        raise HTTPException(status_code=429, detail="Too many new accounts from here. Try again later.")
    try:
        user = await db.run(accounts.register, body.username, body.password)
    except accounts.AccountError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _set_session(request, response, await db.run(accounts.create_session, user["id"]))
    return {"user": accounts.public(user)}


@app.post("/api/auth/login")
async def login(body: Credentials, request: Request, response: Response):
    if not accounts.login_by_ip.allow(_ip(request)) or not accounts.login_by_name.allow(body.username.strip().lower()):
        raise HTTPException(status_code=429, detail="Too many tries. Wait a few minutes.")
    user = await db.run(accounts.login, body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    _set_session(request, response, await db.run(accounts.create_session, user["id"]))
    return {"user": accounts.public(user)}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    await db.run(accounts.revoke, request.cookies.get(accounts.COOKIE))
    response.delete_cookie(accounts.COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
async def me(request: Request):
    user = await current_user(request)
    return {"user": accounts.public(user) if user else None}


@app.get("/api/player")
async def player(user: dict = Depends(signed_in)):
    return await db.run(progress.player_view, user["id"])


@app.get("/api/leaderboard")
async def leaderboard():
    return {"top": await db.run(progress.leaderboard, 20)}


# ---------- a call ----------

class Start(BaseModel):
    hour: int = Field(ge=0, le=23)
    returning_name: str | None = Field(default=None, max_length=40)
    quiz: bool | None = None
    demo: bool = False
    lang: Literal["hi", "en"] = "hi"
    code: str | None = Field(default=None, max_length=8)   # a friend's challenge
    daily: bool = False
    boss_off: bool = False
    recent: list[str] = Field(default_factory=list, max_length=8)  # scenarios, tempers and people this browser met lately
    roles: list[str] = Field(default_factory=lambda: ["dadi"], max_length=4)  # who this browser has unlocked
    meet: str | None = Field(default=None, max_length=10)  # someone just unlocked: they answer next
    calls: int = Field(default=0, ge=0, le=100000)  # calls this browser has played: Boss says less as they learn
    trailer: bool = False  # ?trailer=1: the fixed call for recording; never counted, saved or ranked


SHARED_CLIPS = {"flip_open", "flip_ask", "parents"}  # the mirror caller and Dadi's note, whoever picked up


def _audio(g: game.Game, clip: str) -> str:
    folder = "" if clip in SHARED_CLIPS else g.character["audio"]
    return f"/audio/{folder}{'en/' if g.lang == 'en' else ''}{clip}.mp3"


def _his(g: game.Game, out):
    """Dadaji's calls get he/him in everything the player reads. Nobody else's text is touched."""
    return gender.masc_all(out) if g.role == "dadaji" else out


def pick_role(body: "Start") -> str:
    """Who picks up in free play. A newly unlocked person is guaranteed once; after that it's
    a controlled choice among everyone unlocked, leaning away from whoever answered lately."""
    allowed = ["dadi"] + [r for r in body.roles if r in character.ROLES and r != "dadi"]
    if body.meet in allowed:
        return body.meet
    recent = [x[2:] for x in body.recent if x.startswith("r:")]
    weights = [0.35 if recent[:2] == [r, r] else 0.7 if recent[:1] == [r] else 1.0 for r in allowed]
    return random.choices(allowed, weights)[0]


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

    user = None if body.demo or body.trailer else await current_user(request)
    if user:  # who can pick up, who's due, how experienced: the database decides, not the browser
        ctx = await db.run(progress.start_context, user["id"])
        body.roles, body.meet, body.calls, body.recent = ctx["roles"], ctx["meet"], ctx["calls"], ctx["recent"]
    code = game.daily_code(today()) if body.daily and not body.trailer else body.code
    if not code and not body.demo and not body.trailer:  # free play: who picks up, and not the same situation twice in a row
        role = pick_role(body)
        for _ in range(12):
            code = game.new_code(body.hour, role)
            c = character.generate(code)
            temper = "t:" + character.R(c)["temperaments"][c["temperament"]]["label"].capitalize()  # as the report shows it
            if scenario.pick(c, code) not in body.recent and temper not in body.recent:
                break
    # A returning caller makes her warier, so shared scenarios ignore it to stay fair.
    returning = None if body.demo or body.daily or body.code or body.trailer else body.returning_name
    g = game.Game(body.hour, returning, demo=body.demo, lang=body.lang, code=code, boss_off=body.boss_off, daily=body.daily,
                  boss_level=0 if body.calls < 3 else 1 if body.calls < 10 else 2, trailer=body.trailer)
    g.user_id = user["id"] if user else None
    g.persisted = False
    g.lock = asyncio.Lock()       # one request at a time per call: a double-tap can't play two turns at once
    g.seq = 0                     # the last turn number handled, so a retried turn isn't played twice
    g.last_turn = None
    g.pending: dict[str, int] = {}  # counter-moves the server actually issued and the player hasn't met yet
    games[g.id] = g
    if not g.demo and not g.trailer:  # demo and trailer runs never touch the database
        mode = "daily" if g.daily else "challenge" if body.code else "free"
        g.persisted = bool(await _persist(progress.open_session, g, g.user_id, mode))
    if body.quiz is not None and not g.demo and not g.trailer:
        stats["quiz_before"][0] += 1 if body.quiz is False else 0
        stats["quiz_before"][1] += 1
        _stats_dirty = True
    greet = "greet_back" if g.returning_name else f"greet_{g.mood_key}_{0 if g.demo else random.randrange(2)}"
    return _his(g, {
        "id": g.id, "seconds": game.GAME_SECONDS, "mood": g.mood_key, "name": character.display_name(g.character, "en"), "greet": greet,
        "suspicion": round(g.suspicion), "boss": g.boss_hint(), "intel": g.intel(),
        "playbook": [{"id": t, "label": game.TACTICS[t]["label"]} for t in game.PLAYBOOK],
        "story_built": g.story_built, "demo": g.demo, "lang": g.lang,
        "code": g.code, "daily": g.daily, "boss_off": g.boss_off,
        "role": g.role, "title": {"dadi": "Dadi", "didi": "Pinky", "dadaji": "Dadaji"}[g.role], "audio": g.character["audio"],
        "saved": g.persisted and g.user_id is not None,
        **({"debug": character.debug(g.character)} if config.DEBUG else {}),
    })


class Turn(BaseModel):
    said: str = Field(min_length=1, max_length=600)
    seq: int | None = Field(default=None, ge=1, le=10_000)  # the page's turn number: a retry repeats it


async def _log_new(g: game.Game, since: int) -> None:
    """Save the engine's record of what just happened (never the player's words)."""
    if not g.persisted:
        return
    for i, entry in enumerate(g.timeline[since:], start=since):
        await _persist(progress.add_event, g.id, i, **progress.event_from_timeline(g, entry))


@app.post("/api/game/{game_id}/turn")
async def play_turn(game_id: str, body: Turn, request: Request):
    g = await _get_game(game_id, request)
    async with g.lock:
        if body.seq is not None and body.seq <= g.seq:
            if body.seq == g.seq and g.last_turn is not None:
                return g.last_turn  # the same request again: the same answer, nothing played twice
            raise HTTPException(status_code=409, detail="That turn was already played.")
        if g.outcome:
            raise HTTPException(status_code=409, detail="This call has ended.")
        since = len(g.timeline)
        result = await g.turn(body.said, _seconds_left(g))
        if result.get("effect") in game.COUNTER_EFFECTS:
            g.pending[result["effect"]] = g.pending.get(result["effect"], 0) + 1
        out = _speakable(g, result)
        g.seq, g.last_turn = body.seq or g.seq + 1, out
        await _log_new(g, since)
        return out


def _speakable(g: game.Game, result: dict) -> dict:
    if not result["reply"]:
        result["speech"] = None
    elif result["canned"] is None:
        token = f"{g.id}-{g.turns}"
        speech[token] = (result["reply"], time.time(), g.character["voice"], g.lang, g.character["model"])
        result["speech"] = f"/api/speech/{token}"
    else:
        result["speech"] = _audio(g, result["canned"])
    return _his(g, result)


@app.get("/api/speech/{token}")
async def spoken_reply(token: str):
    """Only speaks replies the game itself generated, never arbitrary text."""
    item = speech.pop(token, None)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    audio = tts.stream(item[0], config.TTS_LANGS[item[3]], voice=item[2], model=item[4], speed=config.DADI_SPEED)
    try:
        first = await anext(audio)
    except (tts.TTSError, RuntimeError, StopAsyncIteration) as e:
        log.warning("Speech failed: %s", e)
        raise HTTPException(status_code=502, detail="Dadi lost her voice")

    async def rest():
        yield first
        try:
            async for chunk in audio:
                yield chunk
        except tts.TTSError as e:
            log.warning("Speech stopped early: %s", e)

    return StreamingResponse(rest(), media_type="audio/mpeg")


@app.post("/api/game/{game_id}/flip")
async def flip_round(game_id: str, request: Request):
    """The last round: a stranger's voice calls the player, using the player's own words."""
    g = await _get_game(game_id, request)
    tactic, line = g.mirror_line()  # the pattern they leaned on hardest, in their own words
    if not line:
        return {"own_line": None, "pattern": None, "speech": _audio(g, "flip_open")}
    token = f"{g.id}-flip"
    speech[token] = (line, time.time(), config.PAPPU_VOICE, g.lang, config.TTS_MODEL)
    return {"own_line": line, "pattern": game.TACTICS[tactic]["label"], "speech": f"/api/speech/{token}"}


class FlipResult(BaseModel):
    hung_up: bool


@app.post("/api/game/{game_id}/flip/result")
async def flip_result(game_id: str, body: FlipResult, request: Request):
    global _stats_dirty
    g = await _get_game(game_id, request)
    if not g.outcome:
        raise HTTPException(status_code=409, detail="Finish the call first.")
    if g.persisted:
        await _persist(progress.record_mirror, g, g.user_id, body.hung_up)
    if not g.demo and not g.trailer and not getattr(g, "flip_counted", False):
        g.flip_counted = True
        stats["flip"][0] += 1 if body.hung_up else 0
        stats["flip"][1] += 1
        _stats_dirty = True
    return {"ok": True}


class CutOff(BaseModel):
    said: str = Field(min_length=1, max_length=600)


@app.post("/api/game/{game_id}/cutoff")
async def cut_off(game_id: str, body: CutOff, request: Request):
    g = await _get_game(game_id, request)
    async with g.lock:
        since = len(g.timeline)
        result = g.cut_off(body.said)
        if result is None:
            raise HTTPException(status_code=409, detail="No reason to interrupt.")
        await _log_new(g, since)
        return _his(g, result)


class Counter(BaseModel):
    effect: str = Field(max_length=20)
    passed: bool


@app.post("/api/game/{game_id}/counter")
async def counter_move(game_id: str, body: Counter, request: Request):
    g = await _get_game(game_id, request)
    if body.effect not in game.COUNTER_EFFECTS:
        raise HTTPException(status_code=400, detail="Unknown move")
    async with g.lock:
        # Only a counter-move she actually made, and only once: otherwise "I passed" is free trust.
        if not g.pending.get(body.effect) or g.outcome:
            raise HTTPException(status_code=409, detail="She didn't do that.")
        g.pending[body.effect] -= 1
        since = len(g.timeline)
        result = g.counter_result(body.effect, body.passed)
        await _log_new(g, since)
        return _his(g, result)


class End(BaseModel):
    # Which lessons this browser has already seen, so repeats get shorter. Counts only.
    seen: dict[str, int] = Field(default_factory=dict, max_length=20)
    last: str | None = Field(default=None, max_length=30)


@app.post("/api/game/{game_id}/end")
async def end_game(game_id: str, request: Request, body: End | None = None):
    global _stats_dirty
    g = await _get_game(game_id, request)
    async with g.lock:
        if not g.outcome:
            g.finish_state(_seconds_left(g))
        if not g.outcome:  # they hung up, or their clock ran out first
            g.outcome = "hung_up"
        saved = await _persist(progress.record_end, g, g.user_id) if g.persisted else None
    first_report = not getattr(g, "reported", False)
    report = g.report(body.seen if body else None, body.last if body else None)
    if first_report and not g.demo and not g.trailer:
        g.reported = True
        stats["plays"] += 1
        stats["seconds"] += min(game.GAME_SECONDS, int(time.time() - g.started))
        if report["outcome"] == "cracked":
            stats["cracked"] += 1
        elif report["outcome"] == "busted":
            stats["busted"] += 1
        elif report["outcome"] == "timeout":
            stats["timeouts"] += 1
        elif report["outcome"] == "reformed":
            stats["reformed"] += 1
        _stats_dirty = True
    report["crack_rate"] = round(100 * stats["cracked"] / max(1, stats["plays"]), 1)
    if saved is not None and g.user_id is not None:
        if saved["recorded"]:
            g.unlocked_now = saved["unlocked"]
        report["unlocked"] = getattr(g, "unlocked_now", [])
        report["saved"] = True
    return _his(g, report)


class Answers(BaseModel):
    answers: list[int] = Field(max_length=3)


@app.post("/api/game/{game_id}/answers")
async def answer_questions(game_id: str, body: Answers, request: Request):
    """The three questions about this run. The first answers are the ones that count."""
    global _stats_dirty
    g = await _get_game(game_id, request)
    if not g.outcome:
        raise HTTPException(status_code=409, detail="Finish the call first.")
    async with g.lock:
        first = g.knowledge is None
        result = scoring.grade(g, body.answers)
        if g.persisted:
            await _persist(progress.record_end, g, g.user_id)  # in case the end was never reported
            await _persist(progress.record_completion, g, g.user_id)
    if g.persisted and g.user_id is not None:
        view = await _persist(progress.player_view, g.user_id)
        if view:
            result["player"] = {"best_score": view["stats"]["best_score"], "rank": view["rank"], "completed": view["stats"]["completed"]}
    if first and not g.demo and not g.trailer:
        stats["quiz_after"][0] += sum(result["correct"])
        stats["quiz_after"][1] += len(result["correct"])
        _stats_dirty = True
    return _his(g, result)


@app.post("/api/game/{game_id}/submit")
async def submit_score(game_id: str, request: Request, user: dict = Depends(signed_in)):
    """Where this daily run stands on today's board. Entries come from the server's own record of
    completed, ranked calls, under the account's name; nothing the browser sends is a score."""
    g = await _get_game(game_id, request)
    if not g.daily or not g.persisted or g.user_id != user["id"]:
        raise HTTPException(status_code=409, detail="This run can't go on the board.")
    if not scoring.ranked(g) or g.knowledge is None or not g.outcome:
        raise HTTPException(status_code=409, detail="This run can't go on the board.")
    date = today()
    if g.code != game.daily_code(date):
        raise HTTPException(status_code=409, detail="That was yesterday's Dadi.")
    top, players = await db.run(progress.daily_board, date)
    rank = await db.run(progress.daily_rank, date, user["username"])
    return {"rank": rank, "of": players, "top": top}


@app.get("/api/daily")
async def daily_board():
    date = today()
    top, players = await db.run(progress.daily_board, date)
    # Who picks up stays a secret until she does.
    return {"date": date, "top": top, "players": players}


@app.post("/api/game/{game_id}/abandon")
async def abandon_game(game_id: str, request: Request):
    """The page was reloaded or closed mid-call. A live, timed call can't resume, so it's closed and
    not counted, and the player is told. Idempotent: an unknown or finished call is simply ignored."""
    g = games.get(game_id)
    if g is not None:
        if g.user_id is not None:
            user = await current_user(request)
            if not user or user["id"] != g.user_id:
                return {"abandoned": False}
        if g.outcome:
            return {"abandoned": False}
        del games[game_id]
    elif not await db.run(db.row, "SELECT 1 FROM game_sessions WHERE id = ? AND user_id IS NULL", (game_id,)):
        user = await current_user(request)  # a call from a past process: only its owner can close it
        if not user or not await db.run(db.row, "SELECT 1 FROM game_sessions WHERE id = ? AND user_id = ?", (game_id, user["id"])):
            return {"abandoned": False}
    return {"abandoned": bool(await _persist(progress.abandon, game_id))}


@app.websocket("/ws/listen")
async def listen(browser: WebSocket):
    """Browser sends PCM16 mono audio at 16 kHz; we send back Prisma events.

    The text frame "flush" sends trailing silence so Prisma finishes the last
    words, then replies {"type": "flushed"}. `?lang=en` listens for English.
    """
    global _listen_sessions
    await browser.accept()
    if _listen_sessions >= config.MAX_LISTEN_SESSIONS:
        await browser.send_json({"type": "error", "message": "busy"})
        await browser.close()
        return
    try:
        prisma = PrismaStream(config.STT_LANG_EN if browser.query_params.get("lang") == "en" else config.STT_LANG)
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


mimetypes.add_type("application/vnd.android.package-archive", ".apk")


class Frontend(StaticFiles):
    """Revalidate on every load, so players never keep an old version after a deploy."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", Frontend(directory=FRONTEND, html=True), name="frontend")
