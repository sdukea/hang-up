from backend import character, db, game, main

from .conftest import finish_call, signup, start


def unlocked(client):
    return client.get("/api/player").json()["unlocked"]


def dadi_code(i: int) -> str:
    """A different Dadi each time (no role letter means Dadi)."""
    return f"{i % 5}{(i // 5) % 5}{'ABCDEFGHIJ'[i]}QX"


def test_first_otp_unlocks_pinky_who_then_picks_up_next(client):
    signup(client)
    assert unlocked(client) == ["dadi"]
    end, _ = finish_call(client, start(client)["id"], digits=4)
    assert end["unlocked"] == ["didi"]
    assert unlocked(client) == ["dadi", "didi"]
    assert start(client)["role"] == "didi"  # guaranteed, once
    roles = {start(client)["role"] for _ in range(25)}
    assert roles <= {"dadi", "didi"} and "dadi" in roles


def test_failing_to_crack_unlocks_nothing(client):
    signup(client)
    end, _ = finish_call(client, start(client)["id"], digits=3)
    assert end["unlocked"] == [] and unlocked(client) == ["dadi"]


def test_dadaji_needs_three_different_dadis(client):
    signup(client)
    finish_call(client, start(client, code=dadi_code(0))["id"], digits=4)          # Pinky
    assert unlocked(client) == ["dadi", "didi"]
    # The same Dadi twice counts once.
    finish_call(client, start(client, code=dadi_code(0))["id"], digits=4)
    finish_call(client, start(client, code=dadi_code(1))["id"], digits=4)
    view = client.get("/api/player").json()
    assert "dadaji" not in view["unlocked"] and view["next_unlock"]["have"] == 2
    end, _ = finish_call(client, start(client, code=dadi_code(2))["id"], digits=4)
    assert end["unlocked"] == ["dadaji"] and unlocked(client) == ["dadi", "didi", "dadaji"]


def test_already_unlocked_is_not_unlocked_again(client):
    signup(client)
    for i in range(5):
        finish_call(client, start(client, code=dadi_code(i))["id"], digits=4)
    assert db.row("SELECT COUNT(*) FROM unlocks")[0] == 3
    end, _ = finish_call(client, start(client, code=dadi_code(6))["id"], digits=4)
    assert end["unlocked"] == []


def test_cracking_pinky_does_not_count_toward_dadaji(client):
    signup(client)
    finish_call(client, start(client)["id"], digits=4)  # Pinky unlocked
    for _ in range(3):
        finish_call(client, start(client, code=dadi_code(3)[:5] + "P")["id"], digits=4)  # Pinky's calls
    assert "dadaji" not in unlocked(client)


def test_unlock_survives_a_new_browser(client, other):
    signup(client, "same_player", "correct horse")
    finish_call(client, start(client)["id"], digits=4)
    other.post("/api/auth/login", json={"username": "same_player", "password": "correct horse"})
    assert unlocked(other) == ["dadi", "didi"]
    assert character.generate(start(other)["code"]).get("role", "dadi") == "didi"


def test_a_dropped_first_meeting_is_given_back(client):
    signup(client)
    finish_call(client, start(client)["id"], digits=4)  # Pinky unlocked, due next
    first = start(client)
    assert first["role"] == "didi"
    client.post(f"/api/game/{first['id']}/abandon")      # the page reloaded mid-call
    assert start(client)["role"] == "didi"               # she's still guaranteed
