from backend import db, game, main

from .conftest import finish_call, signup, start


def test_completed_games_appear_with_the_servers_score(client):
    signup(client)
    _, graded = finish_call(client, start(client)["id"], digits=4)
    top = client.get("/api/leaderboard").json()["top"]
    assert top == [{"rank": 1, "name": "kavya_k", "score": graded["score"], "games": 1}]


def test_ended_but_unanswered_games_do_not_appear(client):
    signup(client)
    gid = start(client)["id"]
    main.games[gid].digits = 4
    client.post(f"/api/game/{gid}/end", json={})
    assert client.get("/api/leaderboard").json()["top"] == []


def test_demo_and_trailer_runs_never_reach_the_database(client):
    signup(client)
    for flags in ({"demo": True}, {"trailer": True}):
        gid = start(client, **flags)["id"]
        main.games[gid].digits = 4
        client.post(f"/api/game/{gid}/end", json={})
        client.post(f"/api/game/{gid}/answers", json={"answers": [0, 0, 0]})
    assert db.row("SELECT COUNT(*) FROM game_sessions")[0] == 0
    assert client.get("/api/leaderboard").json()["top"] == []
    assert client.get("/api/player").json()["stats"]["games"] == 0


def test_a_score_cannot_be_forged_by_the_browser(client):
    signup(client)
    gid = start(client)["id"]
    _, graded = finish_call(client, gid, digits=1, answers=(9, 9, 9))
    forged = client.post(f"/api/game/{gid}/submit", json={"name": "kavya_k", "score": 100})
    assert forged.status_code == 409  # not a daily run; and a score field is ignored regardless
    assert client.get("/api/leaderboard").json()["top"][0]["score"] == graded["score"] < 100


def test_daily_board_ranks_each_players_best_ranked_run(client, other):
    signup(client, "player_one")
    signup(other, "player_two")
    for c, digits in ((client, 2), (client, 4), (other, 3)):
        gid = start(c, daily=True)["id"]
        g = main.games[gid]
        g.turns = 3  # ranked runs need a few judged turns
        finish_call(c, gid, digits=digits)
    board = client.get("/api/daily").json()
    assert board["players"] == 2
    assert [e["name"] for e in board["top"]] == ["player_one", "player_two"]
    mine = client.post(f"/api/game/{gid}/submit")
    assert mine.status_code == 404  # that last call was the other player's
    gid = start(client, daily=True)["id"]
    main.games[gid].turns = 3
    finish_call(client, gid, digits=0)
    assert client.post(f"/api/game/{gid}/submit").json()["rank"] == 1  # their best still stands


def test_guests_cannot_post_to_the_daily_board(client):
    gid = start(client, daily=True)["id"]
    main.games[gid].turns = 3
    finish_call(client, gid, digits=4)
    assert client.post(f"/api/game/{gid}/submit").status_code == 401
    assert client.get("/api/daily").json()["players"] == 0
