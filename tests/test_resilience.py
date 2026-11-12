import asyncio

from backend import db, game, main, progress

from .conftest import signup, start


def test_a_retried_turn_is_not_played_twice(client):
    signup(client)
    gid = start(client)["id"]
    first = client.post(f"/api/game/{gid}/turn", json={"said": "Main CBI se Inspector Sharma bol raha hoon", "seq": 1}).json()
    trust = main.games[gid].trust
    again = client.post(f"/api/game/{gid}/turn", json={"said": "Main CBI se Inspector Sharma bol raha hoon", "seq": 1}).json()
    assert again == first and main.games[gid].turns == 1 and main.games[gid].trust == trust
    assert client.post(f"/api/game/{gid}/turn", json={"said": "old", "seq": 0}).status_code == 422
    assert db.row("SELECT COUNT(*) FROM game_events WHERE session_id = ?", (gid,))[0] == 1


def test_simultaneous_turns_on_one_call_run_one_at_a_time(client):
    signup(client)
    gid = start(client)["id"]
    g = main.games[gid]

    async def both():
        lines = ["Main CBI se bol raha hoon", "Warrant nikla hai aapke naam par"]
        return await asyncio.gather(*(main.play_turn(gid, main.Turn(said=s, seq=i + 1), FakeRequest(client)) for i, s in enumerate(lines)))

    results = asyncio.run(both())
    assert g.turns == 2 and len(results) == 2
    assert [e["kind"] for e in g.timeline].count("move") == 2  # each turn applied once, never interleaved


class FakeRequest:
    """The bits of a request the route reads, carrying the test client's session cookie."""

    def __init__(self, client):
        self.cookies = dict(client.cookies)


def test_counter_moves_only_count_when_she_made_them_and_only_once(client):
    signup(client)
    gid = start(client)["id"]
    forged = client.post(f"/api/game/{gid}/counter", json={"effect": "shout", "passed": True})
    assert forged.status_code == 409 and main.games[gid].trust == 0
    main.games[gid].pending["shout"] = 1  # as if her last reply asked them to speak up
    assert client.post(f"/api/game/{gid}/counter", json={"effect": "shout", "passed": True}).status_code == 200
    assert client.post(f"/api/game/{gid}/counter", json={"effect": "shout", "passed": True}).status_code == 409
    assert main.games[gid].trust == 4


def test_reload_mid_call_abandons_it_cleanly_and_once(client):
    signup(client)
    gid = start(client)["id"]
    assert client.post(f"/api/game/{gid}/abandon").json() == {"abandoned": True}
    assert client.post(f"/api/game/{gid}/abandon").json() == {"abandoned": False}
    assert db.row("SELECT status FROM game_sessions WHERE id = ?", (gid,))["status"] == "abandoned"
    assert client.post(f"/api/game/{gid}/turn", json={"said": "hello"}).status_code == 404
    stats = client.get("/api/player").json()["stats"]
    assert stats["games"] == 0  # not counted as a game
    assert db.row("SELECT abandoned FROM player_profiles")[0] == 1


def test_finished_calls_cannot_be_abandoned_afterwards(client):
    signup(client)
    gid = start(client)["id"]
    main.games[gid].digits = 4
    client.post(f"/api/game/{gid}/end", json={})
    assert client.post(f"/api/game/{gid}/abandon").json() == {"abandoned": False}
    assert db.row("SELECT status FROM game_sessions WHERE id = ?", (gid,))["status"] == "ended"


def test_calls_left_running_by_a_dead_process_are_closed(client):
    signup(client)
    gid = start(client)["id"]
    main.games.clear()  # the process died
    assert progress.sweep(set(), everything=True) == 1
    assert db.row("SELECT status FROM game_sessions WHERE id = ?", (gid,))["status"] == "abandoned"


def test_two_tabs_play_two_independent_calls(client):
    signup(client)
    a, b = start(client)["id"], start(client)["id"]
    client.post(f"/api/game/{a}/turn", json={"said": "Main CBI se bol raha hoon", "seq": 1})
    assert main.games[a].turns == 1 and main.games[b].turns == 0
    main.games[a].digits = 4
    client.post(f"/api/game/{a}/end", json={})
    assert main.games[b].outcome is None
    assert {r["id"]: r["status"] for r in db.rows("SELECT id, status FROM game_sessions")} == {a: "ended", b: "active"}


def test_a_database_failure_never_breaks_the_call(client, monkeypatch):
    signup(client)
    gid = start(client)["id"]

    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(progress, "add_event", broken)
    r = client.post(f"/api/game/{gid}/turn", json={"said": "Main CBI se bol raha hoon", "seq": 1})
    assert r.status_code == 200 and r.json()["reply"]
