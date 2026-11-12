-- Accounts, sessions, player progress, unlocks, calls and what happened in them.
-- Never store a player's words, audio, phone numbers or OTPs here.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL,
    last_seen_at  INTEGER NOT NULL
);

CREATE TABLE auth_sessions (
    token_hash   TEXT    PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   INTEGER NOT NULL,
    expires_at   INTEGER NOT NULL,
    last_used_at INTEGER NOT NULL
);
CREATE INDEX auth_sessions_user ON auth_sessions(user_id);

CREATE TABLE player_profiles (
    user_id        INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    games          INTEGER NOT NULL DEFAULT 0,   -- calls that reached an ending
    completed      INTEGER NOT NULL DEFAULT 0,   -- ...and had their red-flag questions answered
    cracked        INTEGER NOT NULL DEFAULT 0,
    busted         INTEGER NOT NULL DEFAULT 0,
    timeouts       INTEGER NOT NULL DEFAULT 0,
    hung_up        INTEGER NOT NULL DEFAULT 0,
    reformed       INTEGER NOT NULL DEFAULT 0,
    abandoned      INTEGER NOT NULL DEFAULT 0,
    total_score    INTEGER NOT NULL DEFAULT 0,
    best_score     INTEGER NOT NULL DEFAULT 0,
    quiz_correct   INTEGER NOT NULL DEFAULT 0,
    quiz_answered  INTEGER NOT NULL DEFAULT 0,
    mirror_calls   INTEGER NOT NULL DEFAULT 0,   -- the call that turns on them
    mirror_hung_up INTEGER NOT NULL DEFAULT 0,
    recoveries     INTEGER NOT NULL DEFAULT 0,   -- eased off right after she pushed back, and she settled
    red_flags      INTEGER NOT NULL DEFAULT 0,   -- e.g. stopped her checking with the police
    updated_at     INTEGER NOT NULL
);

CREATE TABLE unlocks (
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role           TEXT    NOT NULL,
    unlocked_at    INTEGER NOT NULL,
    source_session TEXT,
    met_at         INTEGER,                      -- NULL: they pick up the player's next call
    PRIMARY KEY (user_id, role)
);

CREATE TABLE game_sessions (
    id            TEXT    PRIMARY KEY,           -- the call's id
    user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,  -- NULL for guests
    mode          TEXT    NOT NULL,              -- free, daily, challenge
    role          TEXT    NOT NULL,
    code          TEXT    NOT NULL,              -- the seed: same code, same person and scenario
    scenario      TEXT,
    temperament   TEXT,
    lang          TEXT    NOT NULL,
    boss_off      INTEGER NOT NULL DEFAULT 0,
    difficulty    INTEGER NOT NULL DEFAULT 0,
    game_version  TEXT    NOT NULL,
    status        TEXT    NOT NULL CHECK (status IN ('active', 'ended', 'completed', 'abandoned')),
    outcome       TEXT,
    digits        INTEGER NOT NULL DEFAULT 0,
    call_score    INTEGER,
    knowledge     INTEGER,
    final_score   INTEGER,
    ranked        INTEGER NOT NULL DEFAULT 0,
    turns         INTEGER NOT NULL DEFAULT 0,
    offline_turns INTEGER NOT NULL DEFAULT 0,
    started_at    INTEGER NOT NULL,
    ended_at      INTEGER,
    completed_at  INTEGER,
    duration_s    INTEGER
);
CREATE INDEX game_sessions_user ON game_sessions(user_id, started_at);
CREATE INDEX game_sessions_status ON game_sessions(status, started_at);
CREATE INDEX game_sessions_board ON game_sessions(final_score DESC) WHERE status = 'completed' AND user_id IS NOT NULL;
CREATE INDEX game_sessions_daily ON game_sessions(code, final_score DESC) WHERE status = 'completed' AND ranked = 1;

CREATE TABLE game_events (
    id              INTEGER PRIMARY KEY,
    session_id      TEXT    NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL,
    type            TEXT    NOT NULL,            -- move, cutoff, counter, mirror, ended, completed
    tactic          TEXT,
    notes           TEXT,                        -- engine notes, comma-separated: too_soon, recovered...
    trust_delta     INTEGER,
    suspicion_delta INTEGER,
    digits          INTEGER,
    result          TEXT,                        -- counter passed/failed, outcome, hung up...
    created_at      INTEGER NOT NULL,
    UNIQUE (session_id, seq)
);
