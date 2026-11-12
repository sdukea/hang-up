import asyncio

from backend import config, db, main, progress

from .conftest import signup, start
from .test_games import SCRIPT

ASK = "Ab bas verification ke liye jo OTP aaya hai woh bata dijiye."


def play(client, gid):
    """A whole call through the real engine, turn by turn, until it ends or the script runs out."""
    lines = SCRIPT + [ASK, "Dadi ji OTP bata dijiye, bas yahi process hai.", ASK]
    seq = 0
    for line in lines:
        seq += 1
        r = client.post(f"/api/game/{gid}/turn", json={"said": line, "seq": seq}).json()
        effect = r.get("effect")
        if effect in ("shout", "callback"):  # meet her counter-move the way a player would
            client.post(f"/api/game/{gid}/counter", json={"effect": effect, "passed": effect == "shout"})
        if r.get("outcome"):
            break
    return client.post(f"/api/game/{gid}/end", json={}).json()


def test_a_real_call_played_turn_by_turn_is_recorded_faithfully(client):
    signup(client)
    outcomes = []
    for code in ["10AQX", "21BQX", "02CQX", "13DQX", "30EQX", "41FQX"]:
        gid = start(client, code=code)["id"]
        report = play(client, gid)
        g = main.games[gid]
        s = db.row("SELECT outcome, digits, turns, call_score FROM game_sessions WHERE id = ?", (gid,))
        assert (s["outcome"], s["digits"], s["turns"]) == (report["outcome"], g.digits, g.turns)
        assert s["call_score"] == report["call_score"]["total"]
        moves = db.row("SELECT COUNT(*) FROM game_events WHERE session_id = ? AND type = 'move'", (gid,))[0]
        assert moves == g.turns
        outcomes.append(report["outcome"])
    assert "cracked" in outcomes  # the engine still lets a good, patient script through
    assert client.get("/api/player").json()["stats"]["games"] == len(outcomes)


class Bucket:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def put(self, key, data, content_type):
        self.data[key] = data


def test_the_database_survives_a_wiped_disk_through_the_bucket(client, monkeypatch, tmp_path):
    signup(client, "survivor")
    bucket = Bucket()
    monkeypatch.setattr(config, "S3_BUCKET", "game-bucket")
    asyncio.run(db.snapshot(bucket))
    assert db.SNAPSHOT_KEY in bucket.data
    db.close()
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "wiped" / "hangup.db"))  # a fresh disk
    asyncio.run(db.restore(bucket))
    db.migrate()
    assert db.row("SELECT username FROM users")["username"] == "survivor"
