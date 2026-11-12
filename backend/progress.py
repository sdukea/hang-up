"""What persists across calls: each call's record and its key moments, the player's progress, who they
have unlocked, and the boards. Every number comes from the server's own game.Game, never the browser.

Finalising is exactly-once: an UPDATE guarded by the current status, in the same transaction as the
profile and unlock writes. A repeated request finds nothing to update and changes nothing.
"""

import time
from datetime import datetime, timedelta, timezone

from . import character, config, db, game, scoring

IST = timezone(timedelta(hours=5, minutes=30))
ABANDON_AFTER = 20 * 60  # a call this old that never ended is gone (the clock is 200 s)
ROLE_ORDER = {"dadi": 0, "didi": 1, "dadaji": 2}
CRACKS_FOR_DADAJI = 3


def _now() -> int:
    return int(time.time())


def temperament(g: game.Game) -> str:
    c = g.character
    return character.R(c)["temperaments"][c["temperament"]]["label"].capitalize()


# ---------- starting a call ----------

def start_context(user_id: int) -> dict:
    """Who can pick up, who is due, how experienced they are, and what they met lately: all from the
    database, so a signed-in browser can't claim any of it."""
    unlocked = sorted(db.rows("SELECT role, met_at FROM unlocks WHERE user_id = ?", (user_id,)), key=lambda r: ROLE_ORDER.get(r["role"], 9))
    roles = [r["role"] for r in unlocked] or ["dadi"]
    meet = next((r["role"] for r in unlocked if r["met_at"] is None), None)
    calls = db.row("SELECT COUNT(*) FROM game_sessions WHERE user_id = ? AND status IN ('ended', 'completed')", (user_id,))[0]
    recent = []
    for s in db.rows("SELECT scenario, temperament, role FROM game_sessions WHERE user_id = ? AND status != 'abandoned' "
                     "ORDER BY started_at DESC LIMIT 3", (user_id,)):
        recent += [x for x in (s["scenario"], s["temperament"] and f"t:{s['temperament']}", f"r:{s['role']}") if x]
    return {"roles": roles, "meet": meet, "calls": calls, "recent": recent[:8]}


def open_session(g: game.Game, user_id: int | None, mode: str) -> bool:
    now = _now()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO game_sessions (id, user_id, mode, role, code, scenario, temperament, lang, boss_off, difficulty, "
            "game_version, status, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)",
            (g.id, user_id, mode, g.role, g.code, g.scene.key, temperament(g), g.lang, int(g.boss_off), g.difficulty,
             config.GAME_VERSION, now))
        if user_id is not None:  # the guaranteed first meeting with someone new is used up
            conn.execute("UPDATE unlocks SET met_at = ? WHERE user_id = ? AND role = ? AND met_at IS NULL", (now, user_id, g.role))
    return True


# ---------- during a call ----------

def add_event(session_id: str, seq: int, kind: str, *, tactic: str | None = None, notes: list[str] | None = None,
              trust: int | None = None, suspicion: int | None = None, digits: int | None = None, result: str | None = None) -> None:
    """One key moment. INSERT OR IGNORE on (session, seq): a retried request can't record it twice."""
    with db.tx() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO game_events (session_id, seq, type, tactic, notes, trust_delta, suspicion_delta, digits, result, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, seq, kind, tactic, ",".join(notes) if notes else None, trust, suspicion, digits, result, _now()))


def event_from_timeline(g: game.Game, entry: dict) -> dict:
    """The engine's own record of a moment, minus anything the player said."""
    return dict(
        kind=entry["kind"], tactic=entry.get("tactic") or entry.get("effect"), notes=entry.get("notes"),
        trust=entry.get("trust"), suspicion=entry.get("susp"), digits=entry.get("digits"),
        result=None if "passed" not in entry else ("passed" if entry["passed"] else "failed"))


# ---------- ending ----------

def _unlock(conn, user_id: int, session_id: str) -> list[str]:
    """The game's own rules: Pinky after the first OTP from anyone; Dadaji after three different Dadis."""
    have = {r[0] for r in conn.execute("SELECT role FROM unlocks WHERE user_id = ?", (user_id,))}
    new = []
    if "didi" not in have:
        new.append("didi")
    elif "dadaji" not in have:
        cracked = conn.execute("SELECT COUNT(DISTINCT code) FROM game_sessions WHERE user_id = ? AND role = 'dadi' "
                               "AND outcome = 'cracked' AND status IN ('ended', 'completed')", (user_id,)).fetchone()[0]
        if cracked >= CRACKS_FOR_DADAJI:
            new.append("dadaji")
    for role in new[:1]:  # one new person at a time, as the game always did
        conn.execute("INSERT OR IGNORE INTO unlocks (user_id, role, unlocked_at, source_session) VALUES (?, ?, ?, ?)",
                     (user_id, role, _now(), session_id))
    return new[:1]


def record_end(g: game.Game, user_id: int | None) -> dict:
    """The call reached an ending. Returns what it unlocked, if anything. Safe to call twice."""
    now = _now()
    call = scoring.call_score(g)
    recoveries = sum(1 for e in g.timeline if e["kind"] == "move" and "recovered" in e.get("notes", []))
    flags = len(g.flags)
    with db.tx() as conn:
        done = conn.execute(
            "UPDATE game_sessions SET status = 'ended', outcome = ?, digits = ?, call_score = ?, turns = ?, offline_turns = ?, "
            "ended_at = ?, duration_s = ? WHERE id = ? AND status = 'active'",
            (g.outcome, g.digits, call["total"], g.turns, g.offline_turns, now, min(game.GAME_SECONDS + 15, now - int(g.started)), g.id)).rowcount
        if not done:
            return {"recorded": False, "unlocked": []}
        conn.execute("INSERT OR IGNORE INTO game_events (session_id, seq, type, result, digits, created_at) VALUES (?, ?, 'ended', ?, ?, ?)",
                     (g.id, 10_000, g.outcome, g.digits, now))
        unlocked = []
        if user_id is not None:
            column = {"cracked": "cracked", "busted": "busted", "timeout": "timeouts", "reformed": "reformed"}.get(g.outcome, "hung_up")
            conn.execute(f"UPDATE player_profiles SET games = games + 1, {column} = {column} + 1, recoveries = recoveries + ?, "
                         "red_flags = red_flags + ?, updated_at = ? WHERE user_id = ?", (recoveries, flags, now, user_id))
            if g.outcome == "cracked":
                unlocked = _unlock(conn, user_id, g.id)
    return {"recorded": True, "unlocked": unlocked}


def record_completion(g: game.Game, user_id: int | None) -> bool:
    """The red-flag questions are answered: the final score is fixed. Safe to call twice."""
    result = scoring.final(g)
    now = _now()
    answered = len(g.questions or [])
    with db.tx() as conn:
        done = conn.execute(
            "UPDATE game_sessions SET status = 'completed', knowledge = ?, final_score = ?, ranked = ?, completed_at = ? "
            "WHERE id = ? AND status = 'ended'",
            (result["knowledge"], result["score"], int(scoring.ranked(g)), now, g.id)).rowcount
        if not done:
            return False
        conn.execute("INSERT OR IGNORE INTO game_events (session_id, seq, type, result, created_at) VALUES (?, ?, 'completed', ?, ?)",
                     (g.id, 10_001, str(result["score"]), now))
        if user_id is not None:
            conn.execute("UPDATE player_profiles SET completed = completed + 1, total_score = total_score + ?, "
                         "best_score = MAX(best_score, ?), quiz_correct = quiz_correct + ?, quiz_answered = quiz_answered + ?, "
                         "updated_at = ? WHERE user_id = ?",
                         (result["score"], result["score"], (g.knowledge or 0) // 10, answered, now, user_id))
    return True


def record_mirror(g: game.Game, user_id: int | None, hung_up: bool) -> bool:
    """The call that turns on them. Once per call."""
    now = _now()
    with db.tx() as conn:
        added = conn.execute("INSERT OR IGNORE INTO game_events (session_id, seq, type, result, created_at) VALUES (?, ?, 'mirror', ?, ?)",
                             (g.id, 10_002, "hung_up" if hung_up else "answered", now)).rowcount
        if added and user_id is not None:
            conn.execute("UPDATE player_profiles SET mirror_calls = mirror_calls + 1, mirror_hung_up = mirror_hung_up + ?, "
                         "updated_at = ? WHERE user_id = ?", (int(hung_up), now, user_id))
    return bool(added)


def abandon(session_id: str) -> bool:
    now = _now()
    with db.tx() as conn:
        found = conn.execute("SELECT user_id, role, started_at FROM game_sessions WHERE id = ? AND status = 'active'", (session_id,)).fetchone()
        if not found:
            return False
        conn.execute("UPDATE game_sessions SET status = 'abandoned', ended_at = ? WHERE id = ?", (now, session_id))
        if found["user_id"] is not None:
            conn.execute("UPDATE player_profiles SET abandoned = abandoned + 1, updated_at = ? WHERE user_id = ?", (now, found["user_id"]))
            # A dropped call doesn't use up someone's guaranteed first pickup.
            conn.execute("UPDATE unlocks SET met_at = NULL WHERE user_id = ? AND role = ? AND met_at = ?",
                         (found["user_id"], found["role"], found["started_at"]))
    return True


def sweep(live_ids: set[str], everything: bool = False) -> int:
    """Calls the database thinks are running but the server no longer has: closed as abandoned."""
    cutoff = _now() - (0 if everything else ABANDON_AFTER)
    stale = [r["id"] for r in db.rows("SELECT id FROM game_sessions WHERE status = 'active' AND started_at <= ?", (cutoff,))
             if r["id"] not in live_ids or everything]
    return sum(abandon(s) for s in stale)


# ---------- what the player sees ----------

def player_view(user_id: int) -> dict:
    p = db.row("SELECT * FROM player_profiles WHERE user_id = ?", (user_id,))
    user = db.row("SELECT username FROM users WHERE id = ?", (user_id,))
    roles = sorted((r["role"] for r in db.rows("SELECT role FROM unlocks WHERE user_id = ?", (user_id,))), key=lambda r: ROLE_ORDER.get(r, 9))
    cracked_dadis = db.row("SELECT COUNT(DISTINCT code) FROM game_sessions WHERE user_id = ? AND role = 'dadi' AND outcome = 'cracked' "
                           "AND status IN ('ended', 'completed')", (user_id,))[0]
    if "didi" not in roles:
        next_unlock = {"role": "didi", "need": "Get any Dadi's OTP once.", "have": 0, "of": 1}
    elif "dadaji" not in roles:
        next_unlock = {"role": "dadaji", "need": "Crack 3 different Dadis.", "have": min(cracked_dadis, 3), "of": 3}
    else:
        next_unlock = None
    rank = None
    if p["completed"]:
        rank = 1 + db.row("SELECT COUNT(*) FROM player_profiles WHERE completed > 0 AND best_score > ?", (p["best_score"],))[0]
    recent = [dict(r) for r in db.rows(
        "SELECT role, outcome, digits, final_score AS score, mode, started_at FROM game_sessions "
        "WHERE user_id = ? AND status IN ('ended', 'completed') ORDER BY started_at DESC LIMIT 5", (user_id,))]
    return {
        "username": user["username"],
        "stats": {
            "games": p["games"], "completed": p["completed"], "best_score": p["best_score"],
            "average_score": round(p["total_score"] / p["completed"]) if p["completed"] else None,
            "cracked": p["cracked"], "busted": p["busted"], "timeouts": p["timeouts"], "hung_up": p["hung_up"], "reformed": p["reformed"],
            "mirror_calls": p["mirror_calls"], "mirror_hung_up": p["mirror_hung_up"],
            "recoveries": p["recoveries"], "red_flags": p["red_flags"],
            "quiz_correct": p["quiz_correct"], "quiz_answered": p["quiz_answered"],
        },
        "unlocked": roles, "cracked_dadis": cracked_dadis, "next_unlock": next_unlock, "rank": rank, "recent": recent,
    }


def leaderboard(limit: int = 20) -> list[dict]:
    """Everyone's best completed score. Names only: never ids, never anything private."""
    out = db.rows(
        "SELECT u.username AS name, p.best_score AS score, p.completed AS games FROM player_profiles p "
        "JOIN users u ON u.id = p.user_id WHERE p.completed > 0 ORDER BY p.best_score DESC, p.completed DESC, u.username LIMIT ?",
        (limit,))
    return [{"rank": i + 1, **dict(r)} for i, r in enumerate(out)]


def _day_bounds(date: str) -> tuple[int, int]:
    start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST)
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp())


def daily_board(date: str, limit: int = 10) -> tuple[list[dict], int]:
    """Today's call: each signed-in player's best ranked run."""
    lo, hi = _day_bounds(date)
    best = db.rows(
        "SELECT name, score, boss_off FROM (SELECT u.username AS name, s.final_score AS score, s.boss_off, s.completed_at, "
        "ROW_NUMBER() OVER (PARTITION BY s.user_id ORDER BY s.final_score DESC, s.completed_at) AS n "
        "FROM game_sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.mode = 'daily' AND s.code = ? AND s.status = 'completed' AND s.ranked = 1 AND s.started_at >= ? AND s.started_at < ?) "
        "WHERE n = 1 ORDER BY score DESC, completed_at",
        (game.daily_code(date), lo, hi))
    entries = [{"name": r["name"], "score": r["score"], "boss_off": bool(r["boss_off"])} for r in best]
    return entries[:limit], len(entries)


def daily_rank(date: str, username: str) -> int | None:
    top, _ = daily_board(date, limit=10_000)
    return next((i + 1 for i, e in enumerate(top) if e["name"] == username), None)
