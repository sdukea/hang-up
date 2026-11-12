from backend import db, main, scoring

from .conftest import finish_call, signup, start

SCRIPT = [
    "Namaste Dadi ji, main CBI se Inspector Sharma bol raha hoon, badge number 4471.",
    "Aapke naam par giraftari ka warrant nikla hai, case bahut serious hai.",
    "Sirf das minute hain, jaldi kijiye warna police aa jayegi.",
    "Yeh baat kisi ko mat batana, family ko bhi nahi, case secret hai.",
    "Dadi ji main aapki madad karna chahta hoon, aap meri maa jaisi hain.",
]


def test_a_signed_in_call_is_recorded_with_its_seed(client):
    signup(client)
    data = start(client)
    s = db.row("SELECT * FROM game_sessions WHERE id = ?", (data["id"],))
    assert s["status"] == "active" and s["user_id"] is not None and s["code"] == data["code"]
    assert s["role"] == "dadi" and s["game_version"] and data["saved"] is True


def test_turns_change_state_on_the_server_and_save_moments_without_words(client):
    signup(client)
    data = start(client)
    before = main.games[data["id"]].trust
    for i, line in enumerate(SCRIPT[:3], start=1):
        r = client.post(f"/api/game/{data['id']}/turn", json={"said": line, "seq": i})
        assert r.status_code == 200, r.text
    g = main.games[data["id"]]
    assert g.turns == 3 and g.trust > before
    events = db.rows("SELECT * FROM game_events WHERE session_id = ? AND type = 'move' ORDER BY seq", (data["id"],))
    assert [e["tactic"] for e in events] == ["authority", "fear", "urgency"]
    stored = " ".join(str(v) for e in events for v in dict(e).values())
    assert "Sharma" not in stored and "warrant" not in stored  # the player's words are never kept


def test_the_score_is_the_servers_and_completion_happens_once(client):
    signup(client)
    data = start(client)
    end, graded = finish_call(client, data["id"], digits=3)
    g = main.games[data["id"]]
    assert graded["score"] == scoring.final(g)["score"]
    # Again, and again: nothing changes.
    client.post(f"/api/game/{data['id']}/end", json={})
    again = client.post(f"/api/game/{data['id']}/answers", json={"answers": [1, 1, 1]}).json()
    assert again["score"] == graded["score"]  # first answers count
    p = db.row("SELECT * FROM player_profiles")
    assert (p["games"], p["completed"], p["total_score"], p["best_score"]) == (1, 1, graded["score"], graded["score"])
    s = db.row("SELECT status, final_score, outcome FROM game_sessions WHERE id = ?", (data["id"],))
    assert (s["status"], s["final_score"]) == ("completed", graded["score"])
    assert db.row("SELECT COUNT(*) FROM game_events WHERE session_id = ? AND type = 'completed'", (data["id"],))[0] == 1


def test_profile_aggregates_follow_outcomes(client):
    signup(client)
    finish_call(client, start(client)["id"], digits=4)       # cracked
    g = start(client)
    main.games[g["id"]].suspicion = 100                       # busted
    client.post(f"/api/game/{g['id']}/end", json={})
    stats = client.get("/api/player").json()["stats"]
    assert (stats["games"], stats["cracked"], stats["busted"], stats["completed"]) == (2, 1, 1, 1)


def test_guest_calls_are_recorded_but_never_profiled_or_ranked(client):
    data = start(client)
    finish_call(client, data["id"], digits=4)
    s = db.row("SELECT user_id, status FROM game_sessions WHERE id = ?", (data["id"],))
    assert s["user_id"] is None and s["status"] == "completed"
    assert db.row("SELECT COUNT(*) FROM player_profiles")[0] == 0
    assert client.get("/api/leaderboard").json()["top"] == []
