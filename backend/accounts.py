"""Accounts: usernames, password hashes, and browser sessions.

Passwords are hashed with scrypt (memory-hard, standard library) and a random salt per user. A session
is a random 256-bit token kept in an HttpOnly cookie; only its SHA-256 is stored, so a copy of the
database can't be used to sign in. Nothing here ever logs or returns a password or a hash.
"""

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque

from . import config, db

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,20}")
PASSWORD_MIN, PASSWORD_MAX = 8, 128
COOKIE = "hu_session"
_N, _R, _P = 2 ** 14, 8, 1  # scrypt cost: ~16 MB and tens of milliseconds per attempt


class AccountError(ValueError):
    pass


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(key))
    except (ValueError, TypeError):
        return False


_DUMMY = hash_password(secrets.token_hex(8))  # so an unknown username takes as long as a wrong password


def check_new(username: str, password: str) -> None:
    if not USERNAME_RE.fullmatch(username):
        raise AccountError("Usernames are 3 to 20 letters, numbers or underscores.")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise AccountError(f"Passwords need at least {PASSWORD_MIN} characters.")


def public(user) -> dict:
    """The only fields about an account that ever leave the server."""
    return {"username": user["username"]}


def register(username: str, password: str) -> dict:
    username = username.strip()
    check_new(username, password)
    hashed = hash_password(password)
    now = int(time.time())
    with db.tx() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise AccountError("That username is taken.")
        cur = conn.execute("INSERT INTO users (username, password_hash, created_at, updated_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
                           (username, hashed, now, now, now))
        conn.execute("INSERT INTO player_profiles (user_id, updated_at) VALUES (?, ?)", (cur.lastrowid, now))
        conn.execute("INSERT INTO unlocks (user_id, role, unlocked_at, met_at) VALUES (?, 'dadi', ?, ?)", (cur.lastrowid, now, now))
    return {"id": cur.lastrowid, "username": username}


def login(username: str, password: str) -> dict | None:
    user = db.row("SELECT id, username, password_hash FROM users WHERE username = ?", (username.strip(),))
    if not user:
        verify_password(password, _DUMMY)
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "username": user["username"]}


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with db.tx() as conn:
        conn.execute("INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at, last_used_at) VALUES (?, ?, ?, ?, ?)",
                     (_digest(token), user_id, now, now + config.SESSION_DAYS * 86400, now))
        conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now, user_id))
    return token


def resolve(token: str | None) -> dict | None:
    """The signed-in user for a cookie, or None. Expired sessions are removed."""
    if not token or len(token) > 100:
        return None
    found = db.row("SELECT s.user_id, s.expires_at, s.last_used_at, u.username FROM auth_sessions s "
                   "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (_digest(token),))
    if not found:
        return None
    now = int(time.time())
    if found["expires_at"] < now:
        revoke(token)
        return None
    if now - found["last_used_at"] > 300:  # don't write on every request
        with db.tx() as conn:
            conn.execute("UPDATE auth_sessions SET last_used_at = ? WHERE token_hash = ?", (now, _digest(token)))
            conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now, found["user_id"]))
    return {"id": found["user_id"], "username": found["username"]}


def revoke(token: str | None) -> None:
    if token:
        with db.tx() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_digest(token),))


class Limiter:
    """At most `limit` attempts per key in a sliding window. In memory: one instance, by design."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self.hits.clear()


login_by_ip = Limiter(20, 900)
login_by_name = Limiter(8, 900)
signup_by_ip = Limiter(6, 3600)
