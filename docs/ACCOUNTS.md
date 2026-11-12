# Accounts, persistence and progression

How Hang Up keeps players, games, scores and unlocks: what was there before, what could break, and the
design that replaced it.

## 1. What was there before (inspected, not assumed)

| Concern | Where it lived | Risk |
|---|---|---|
| A live call (`game.Game`: OTP, trust, suspicion, digits, LLM history, timeline) | Python process memory, `main.games`, purged after 15 min | Lost on restart; no record of the game afterwards |
| Score | Server: `scoring.call_score` + `scoring.final` from the server's own timeline | Already authoritative. Kept exactly as it is |
| Outcome (cracked, busted, timeout, reformed, hung up) | Server: `Game.finish_state` | Already authoritative |
| Unlocks (Pinky, Dadaji) | Browser `localStorage` (`dadi_unlocked`, `dadi_cracked`, `dadi_meet`), sent to the server as `roles` and `meet` | **Client-controlled.** Anyone can unlock everyone by editing storage |
| Calls played (how much Boss says), best score, streak, recent scenarios | Browser `localStorage` | Client-controlled; lost with the browser |
| Daily leaderboard | JSON file per day in `store` (disk or S3), name typed by the player | Anyone can post under any name; one entry per game, but no identity |
| Public counters (plays, cracked, minutes) | `stats.json` in `store` | Anonymous totals. Unchanged |

### Things that would break, found before writing code

1. **Counter-move results were unchecked.** `POST /api/game/{id}/counter` accepted any effect, any number
   of times. `{"effect": "shout", "passed": true}` in a loop added 4 trust per request, and trust buys
   digits on the next turn. That is a score-forging hole, independent of accounts. Fixed: the server now
   records which counter-moves it actually issued, and each one resolves once.
2. **Two turns for one call could run at the same time.** `Game.turn` awaits the LLM, so a double-tap or
   a network retry interleaved two turns on the same state. Fixed with a per-game lock, plus a turn
   sequence number so a retried request returns the first result instead of playing a second turn.
3. **Unlocks and progress were client-owned.** For signed-in players the server now decides who can pick
   up, who is guaranteed next, and how many calls they've played. The browser's values are ignored for
   them. Guests keep the old browser-only behaviour, and nothing a guest stored is ever imported into an
   account (it would be forgeable).
4. **Restart = silent loss.** Calls live in memory by design (they hold the LLM conversation and timers;
   a live, timed voice call cannot meaningfully resume on another process). Now every non-demo call also
   has a database row, so a call that dies is recorded as `abandoned` instead of vanishing.
5. **Refresh mid-call.** The page kept nothing, so the call was orphaned on the server. Now the page
   remembers the live call for the tab; after a reload it tells the server, the call is closed as
   abandoned (not counted), and the player is told plainly. No duplicate game is created.
6. **The daily board trusted a typed name.** Board entries now come only from completed, ranked daily
   calls by signed-in players; the name is the account's username; the score is the server's.
7. **Demo and trailer runs.** Both already skipped every counter. They also skip the database entirely:
   no session, no events, no profile, no board, no login.
8. **Single global stats dict, single process.** Fine on one instance (Render free runs one). The
   database is the source of truth for anything per-player; nothing per-player is held in a global.

## 2. Architecture

- **SQLite, through the standard library.** No server, no new dependency, no ORM. One module
  (`backend/db.py`) owns the connection, transactions and migrations. Writes are tiny and rare (a few per
  call), WAL mode keeps reads non-blocking.
- **Durability on hosts that wipe their disk.** Render's free tier loses local files on every deploy. When
  `S3_BUCKET` is set (the same bucket the game already uses for its counters), the database is restored
  from the bucket at startup and a consistent snapshot (SQLite's online backup API) is uploaded within
  30 seconds of a change. Without a bucket, the file lives in `DATA_DIR`. Single instance only; see risks.
- **Passwords:** `hashlib.scrypt` (memory-hard, standard library), random 16-byte salt per user,
  constant-time comparison. Plaintext is never stored, logged or returned.
- **Sessions:** a random 256-bit token in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` over HTTPS).
  Only its SHA-256 is stored. 30-day expiry, revoked on logout.
- **CSRF:** `SameSite=Lax` plus an `Origin` check on every state-changing `/api/` request.
- **Rate limits:** sign-in attempts per IP and per username; sign-ups per IP.

## 3. Schema (`backend/migrations/0001_accounts.sql`)

```
users            id, username (unique, case-insensitive), password_hash, created_at, updated_at, last_seen_at
auth_sessions    token_hash (pk), user_id, created_at, expires_at, last_used_at
player_profiles  user_id (pk), games, completed, cracked, busted, timeouts, hung_up, reformed, abandoned,
                 total_score, best_score, quiz_correct, quiz_answered, mirror_calls, mirror_hung_up,
                 recoveries, red_flags, updated_at
unlocks          (user_id, role) pk, unlocked_at, source_session, met_at   -- met_at NULL: they pick up next
game_sessions    id (pk, the call's id), user_id (NULL for guests), mode, role, code (the seed), scenario,
                 temperament, lang, boss_off, difficulty, game_version, status, outcome, digits,
                 call_score, knowledge, final_score, ranked, turns, offline_turns, seq,
                 started_at, ended_at, completed_at, duration_s
game_events      id, session_id, seq, type, tactic, notes, trust_delta, suspicion_delta, digits, result,
                 created_at                                -- unique (session_id, seq)
schema_migrations version, applied_at
```

- **Status:** `active` (call running) → `ended` (outcome known, call score fixed) → `completed` (red-flag
  questions answered, final score fixed). `active` → `abandoned` if the call dies.
- **Events** store what the engine decided (tactic, notes such as `too_soon` or `recovered`, deltas,
  digits). Never the player's words, Dadi's replies, audio, phone numbers or OTPs.
- **The seed** is the call's code (`game.Game` seeds its RNG from it), so a session can be replayed.
- **Indexes:** session lookup by user and time, sweep by status and time, leaderboard by score among
  completed signed-in sessions, daily board by code, events by session and sequence.

## 4. What the server decides

Score, outcome, digits, completion, unlock conditions, who picks up, Boss's level, board entries. The
browser sends only what the player did: a line, a counter-move result for a counter-move the server
issued, the answers to the questions, whether they hung up on the mirror call.

- **Finalising happens once:** `UPDATE ... WHERE status = 'active'` (then `'ended'`) inside one
  transaction with the profile and unlock writes. A repeat request finds nothing to update and changes
  nothing.
- **Unlock rules, unchanged from the game:** Pinky after the first OTP from anyone; Dadaji after cracking
  three different Dadis (different codes). Whoever is new picks up the next call, once.
- **The LLM** writes dialogue and suggests a tactic and quality; the engine validates both and owns every
  number (unchanged).

## 5. Run commands

```bash
uv sync --dev                                   # dependencies, including pytest
uv run uvicorn backend.main:app --port 8000     # migrations run automatically on start
uv run pytest -q                                # the test suite
DATABASE_PATH=/path/to/hangup.db uv run python -m backend.db migrate   # create or migrate a database by hand
```

A fresh database is created on first start. Migrations are numbered SQL files applied in order inside a
transaction and recorded in `schema_migrations`; existing data is never dropped.
