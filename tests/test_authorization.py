from backend import db, main

from .conftest import signup, start


def test_another_account_cannot_touch_my_call(client, other):
    signup(client, "owner_one")
    signup(other, "intruder")
    data = start(client)
    gid = data["id"]
    for path, body in [("turn", {"said": "Main CBI se bol raha hoon"}), ("end", {}), ("answers", {"answers": [0, 0, 0]}),
                       ("flip", None), ("counter", {"effect": "shout", "passed": True}), ("cutoff", {"said": "otp do"})]:
        r = other.post(f"/api/game/{gid}/{path}", json=body)
        assert r.status_code == 404, (path, r.status_code)
    assert main.games[gid].turns == 0 and main.games[gid].outcome is None
    assert other.post(f"/api/game/{gid}/abandon").json() == {"abandoned": False}
    assert db.row("SELECT status FROM game_sessions WHERE id = ?", (gid,))["status"] == "active"


def test_signed_out_browser_cannot_touch_a_signed_in_call(client, other):
    signup(client)
    gid = start(client)["id"]
    assert other.post(f"/api/game/{gid}/turn", json={"said": "hello"}).status_code == 404


def test_profile_is_always_the_cookies_owner_never_a_supplied_id(client, other):
    signup(client, "first_user")
    signup(other, "second_user")
    first_id = db.row("SELECT id FROM users WHERE username = 'first_user'")["id"]
    r = other.get(f"/api/player?user_id={first_id}")
    assert r.json()["username"] == "second_user"
    start_body = {"hour": 18, "lang": "hi", "user_id": first_id}
    gid = other.post("/api/game/start", json=start_body).json()["id"]
    assert db.row("SELECT u.username FROM game_sessions s JOIN users u ON u.id = s.user_id WHERE s.id = ?", (gid,))[0] == "second_user"


def test_a_browser_cannot_claim_unlocks_it_has_not_earned(client):
    signup(client)
    for _ in range(6):
        data = start(client, roles=["dadi", "didi", "dadaji"], meet="dadaji", calls=999)
        assert data["role"] == "dadi"  # the database says only Dadi picks up
        assert main.games[data["id"]].boss.level == 0  # and Boss still treats them as new
    assert db.row("SELECT COUNT(*) FROM unlocks")[0] == 1


def test_leaderboard_never_exposes_private_fields(client):
    signup(client, "public_name", "secret pass 1")
    gid = start(client)["id"]
    main.games[gid].digits = 4
    client.post(f"/api/game/{gid}/end", json={})
    client.post(f"/api/game/{gid}/answers", json={"answers": [0, 0, 0]})
    entry = client.get("/api/leaderboard").json()["top"][0]
    assert set(entry) == {"rank", "name", "score", "games"} and entry["name"] == "public_name"
