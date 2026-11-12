from backend import accounts, db

from .conftest import signup


def test_register_signs_in_and_never_returns_secrets(client):
    r = signup(client)
    assert r.json() == {"user": {"username": "kavya_k"}}
    cookie = r.headers["set-cookie"]
    assert "hu_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert client.get("/api/auth/me").json() == {"user": {"username": "kavya_k"}}
    stored = db.row("SELECT password_hash FROM users")["password_hash"]
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    token = client.cookies.get(accounts.COOKIE)
    assert db.row("SELECT COUNT(*) FROM auth_sessions WHERE token_hash = ?", (token,))[0] == 0  # only its hash is kept


def test_duplicate_registration_is_refused_case_insensitively(client, other):
    signup(client, "Kavya_K")
    r = other.post("/api/auth/register", json={"username": "kavya_k", "password": "another pass"})
    assert r.status_code == 400 and "taken" in r.json()["detail"]
    assert db.row("SELECT COUNT(*) FROM users")[0] == 1


def test_weak_or_odd_credentials_are_refused(client):
    assert client.post("/api/auth/register", json={"username": "ab", "password": "longenough"}).status_code == 400
    assert client.post("/api/auth/register", json={"username": "bad name!", "password": "longenough"}).status_code == 400
    assert client.post("/api/auth/register", json={"username": "fine_name", "password": "short"}).status_code == 400


def test_login_logout_and_wrong_password(client, other):
    signup(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json() == {"user": None}

    wrong = other.post("/api/auth/login", json={"username": "kavya_k", "password": "nope nope"})
    assert wrong.status_code == 401 and wrong.json()["detail"] == "Wrong username or password."
    unknown = other.post("/api/auth/login", json={"username": "nobody_here", "password": "nope nope"})
    assert unknown.status_code == 401 and unknown.json()["detail"] == wrong.json()["detail"]  # no hint which was wrong

    ok = other.post("/api/auth/login", json={"username": "KAVYA_K", "password": "correct horse"})
    assert ok.status_code == 200 and other.get("/api/auth/me").json()["user"]["username"] == "kavya_k"


def test_logout_revokes_the_session_server_side(client):
    signup(client)
    token = client.cookies.get(accounts.COOKIE)
    client.post("/api/auth/logout")
    client.cookies.set(accounts.COOKIE, token)  # a copied cookie is useless afterwards
    assert client.get("/api/auth/me").json() == {"user": None}
    assert client.get("/api/player").status_code == 401


def test_protected_endpoint_needs_a_session(client):
    assert client.get("/api/player").status_code == 401
    signup(client)
    assert client.get("/api/player").status_code == 200


def test_session_persists_across_requests_and_expires(client):
    signup(client)
    for _ in range(3):
        assert client.get("/api/auth/me").json()["user"]
    with db.tx() as conn:
        conn.execute("UPDATE auth_sessions SET expires_at = 0")
    assert client.get("/api/auth/me").json() == {"user": None}
    assert db.row("SELECT COUNT(*) FROM auth_sessions")[0] == 0


def test_login_attempts_are_rate_limited(client):
    signup(client)
    client.post("/api/auth/logout")
    codes = [client.post("/api/auth/login", json={"username": "kavya_k", "password": f"guess {i}"}).status_code for i in range(10)]
    assert codes[:8] == [401] * 8 and codes[-1] == 429


def test_cross_site_posts_are_refused(client):
    r = client.post("/api/auth/register", json={"username": "evil_one", "password": "longenough"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert db.row("SELECT COUNT(*) FROM users")[0] == 0
