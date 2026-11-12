"""Test setup: a fresh database per test, and a deterministic stand-in for the language model.

Only the network call to the model is replaced. The engine (tactics, trust, suspicion, digits,
counter-moves, scoring, endings) and the database are the real ones.
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="hangup-tests-")
os.environ.update({
    "DATA_DIR": _TMP, "DATABASE_PATH": os.path.join(_TMP, "boot.db"), "S3_BUCKET": "", "GAMES_PER_IP_PER_HOUR": "100000",
    "LLM_MODEL": "stub", "LLM_API_KEY": "stub", "LLM_BASE_URL": "http://llm.invalid", "REDIRECT_TO": "", "DEBUG": "",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import accounts, config, db, game, llm, main  # noqa: E402


def fake_model(said: str) -> dict:
    """What a model would say about the line: the tactic the engine's own detector sees, good quality."""
    tactic = game.detect_tactic(said)
    return {"reply": "अच्छा बेटा, और बताओ।", "reply_en": "Okay child, tell me more.", "tactic": tactic,
            "quality": 3 if tactic != "none" else 1, "contradiction": False, "claimed_name": None, "gags": [], "confessed": False}


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    db.close()
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "hangup.db"))
    db.migrate()

    async def complete_live(system, user, temperature, deadline):
        said = user.split('The player just said: "', 1)[-1].split('"\n', 1)[0]
        return fake_model(said)

    monkeypatch.setattr(llm, "complete_live", complete_live)
    main.games.clear()
    main._starts.clear()
    for limiter in (accounts.login_by_ip, accounts.login_by_name, accounts.signup_by_ip):
        limiter.reset()
    yield
    db.close()


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def other():
    """A second, independent browser."""
    with TestClient(main.app) as c:
        yield c


def signup(c, name="kavya_k", password="correct horse"):
    r = c.post("/api/auth/register", json={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return r


def start(c, **extra):
    body = {"hour": 18, "lang": "hi", **extra}
    r = c.post("/api/game/start", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def finish_call(c, game_id, digits=4, answers=(0, 0, 0)):
    """End a call with a chosen number of digits won, through the real end and answers routes."""
    g = main.games[game_id]
    g.digits = digits
    end = c.post(f"/api/game/{game_id}/end", json={}).json()
    graded = c.post(f"/api/game/{game_id}/answers", json={"answers": list(answers)}).json()
    return end, graded
