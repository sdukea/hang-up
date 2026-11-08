"""What's going on in her life today, and how it changes the conversation.

A character (character.py) is who picks up. A scenario is the problem the player
walks into: she's waiting for a courier, she got a strange SMS this morning, her
son is on his way home, a bank warned her about calls like this... Each one
changes what lands, what costs, how much time there is, and what happens during
the call.

The engine owns all of it. Events fire on rules the player can work out
afterwards (the turn, her trust or suspicion, what the player said or did), never
on the LLM's whim. A scene keeps memory of what has happened, so later events and
her replies can refer back to it. Events cost time or suspicion; none of them
ends the call on its own.
"""

import random
import re

# A scenario:
#   premise    what's on her mind, for the LLM
#   surface    how she lets it slip early on, so the player can discover it
#   fits       which characters it makes sense for
#   mods       on top of hers: tactic multipliers, starting suspicion, pace, ask heat
#   hooks      topics that land because they're on her mind: (pattern, tactic, multiplier)
#   events     tried in order each turn; the first whose condition holds fires, once
#   reveal     the after-call explanation, and the clue that gave it away
#
# An event:
#   when       a condition on the scene (see Scene.holds)
#   action     an existing counter-move to run (hold, callback, shout...) or None
#   clip/why   which recorded line and on-screen note go with it
#   say        what she does this turn, for the LLM
#   then       consequences after the turn: suspicion, trust, flags, facts, the clock
#   title/note the pop-up the player sees, and boss: Boss's reaction (never the future)
SCENARIOS = {
    "delivery": {
        "premise": "She is waiting for an important parcel today and keeps one ear on the door.",
        "surface": "Mention, naturally, that you're waiting for a parcel and keep glancing at the door.",
        "fits": lambda c: c["situation"] not in ("night", "leaving", "nap"),
        "mods": {"weights": {"urgency": 1.15}},
        "hooks": [(r"parcel|courier|delivery|package|पार्सल|कूरियर", "fear", 1.4)],
        "long_line": 22,  # her attention is on the door: rambling loses her
        "events": [
            {"id": "door", "when": {"turn_at_least": 3}, "action": "hold", "clip": "hold_door",
             "why": "Dadi has gone to answer the door",
             "say": "End your reply by noticing the doorbell, in a word or two. It might be your parcel.",
             "then": {"fact": "The courier came to the door in the middle of the call.", "flag": "door"},
             "title": "THE DOORBELL", "note": "Her parcel. Your clock keeps running.",
             "boss": ("Darwaza! Line pe ruk, jaldi mat kar.", "The door! Hold on, don't rush her.")},
            {"id": "parcel_check", "when": {"flag": "door", "suspicion_at_least": 45},
             "say": "You just looked at the parcel properly. Wonder aloud whether this caller's story about parcels even matches it.",
             "then": {"suspicion": 6, "fact": "She compared the caller's story with her real parcel."},
             "title": "SHE CHECKED THE PARCEL", "note": "Your story has to match what's in her hands."},
        ],
        "reveal": "She was waiting for a parcel.", "tell": "She kept mentioning the door and a delivery.",
    },
    "strange_sms": {
        "premise": "This morning she got an SMS she couldn't understand, full of numbers, and it has been bothering her.",
        "surface": "Bring up the confusing message you got this morning and ask if the caller knows about it.",
        "fits": lambda c: True,
        "mods": {"weights": {"authority": 1.2}, "contradiction": 8, "story": 2},
        "hooks": [(r"message|sms|msg|मैसेज|text", "authority", 1.35)],
        "events": [
            {"id": "reads_it", "when": {"trust_at_least": 30},
             "say": "Get your phone out and squint at this morning's message. Read out a word or two, never any number.",
             "then": {"trust": 3, "fact": "She got this morning's SMS out and started reading it."},
             "title": "SHE FOUND THE MESSAGE", "note": "She's looking at her phone now."},
            {"id": "forward_it", "when": {"suspicion_at_least": 45, "turn_at_least": 3}, "action": "callback",
             "say": "Say this message worries you more now and you think you should check it with the police.",
             "then": {"fact": "She wanted the message checked before doing anything."},
             "title": "SHE WANTS IT CHECKED", "note": "She's going to show the message to family.",
             "boss": ("Woh check karwana chahti hai. Soch samajh ke.", "She wants it checked. Think carefully.")},
        ],
        "reveal": "She had a confusing SMS this morning.", "tell": "She asked about a message she'd received.",
    },
    "son_coming": {
        "premise": "Her son is on his way home and will walk in soon.",
        "surface": "Mention that your son will be home any minute.",
        "fits": lambda c: c["situation"] != "leaving",
        "mods": {"weights": {"urgency": 1.3, "secrecy": 0.9}},
        "hooks": [],
        "events": [
            {"id": "son_home_hidden", "when": {"turn_at_least": 4, "used": "secrecy", "suspicion_below": 60},
             "say": "Your son just walked in. Lower your voice, tell the caller you won't say anything to him, and carry on quietly.",
             "then": {"trust": 4, "flag": "son_home", "fact": "Her son came home, and she hid the call from him."},
             "title": "HER SON CAME HOME", "note": "She's hiding the call from him. Isolation works on her."},
            {"id": "son_home", "when": {"turn_at_least": 4}, "action": None,
             "say": "Your son just walked in and is asking who's on the phone. Tell the caller, and say he wants to know.",
             "then": {"suspicion": 14, "flag": "son_home", "fact": "Her son came home and asked who was calling."},
             "title": "HER SON CAME HOME", "note": "He's asking who you are. Nobody told her to keep this quiet.",
             "boss": ("Ghar wala aa gaya. Ab sambhal.", "Family's home. Handle it.")},
        ],
        "reveal": "Her son was on his way home.", "tell": "She said her son would be home soon.",
    },
    "warned": {
        "premise": "This morning her bank sent a warning about fake calls, and a neighbour said the same. She is on guard.",
        "surface": "Mention the warning you got this morning about calls like this.",
        "fits": lambda c: True,
        "mods": {"start": 15, "weights": {"authority": 0.75, "rapport": 1.2}, "ask_heat": 10},
        "hooks": [],
        "events": [
            {"id": "checks", "when": {"used": "authority", "suspicion_at_least": 30}, "action": "callback",
             "say": "Say you're going to check with the police station yourself, exactly like the warning said.",
             "then": {"fact": "She tried to check the caller's claim, as the warning told her to."},
             "title": "SHE REMEMBERED THE WARNING", "note": "She's doing what the warning said.",
             "boss": ("Usse warning mili hui hai. Bada dawa mat kar.", "She's been warned. Don't overclaim.")},
        ],
        "reveal": "She'd been warned about calls like this that morning.", "tell": "She mentioned a warning.",
    },
    "pension": {
        "premise": "Her pension hasn't arrived this month and she's anxious and full of questions about it.",
        "surface": "Mention that your pension still hasn't come this month.",
        "fits": lambda c: True,
        "mods": {"weights": {"fear": 1.2}, "contradiction": 10, "trap": 0.85},
        "hooks": [(r"pension|पेंशन|bank|बैंक|account|खाता", "authority", 1.35)],
        "events": [
            {"id": "asks", "when": {"turn_at_least": 2},
             "say": "Ask the caller one pointed question about exactly what they know about your pension.",
             "then": {"fact": "She asked the caller what they knew about her pension."},
             "title": "SHE HAS QUESTIONS", "note": "She's testing what you know."},
            {"id": "passbook", "when": {"trust_at_least": 35}, "action": "hold", "clip": "hold_passbook",
             "why": "Dadi is looking for her passbook",
             "say": "End your reply by saying you want to check your passbook.",
             "then": {"fact": "She went to find her passbook to check.", "flag": "passbook"},
             "title": "SHE WENT FOR HER PASSBOOK", "note": "She wants to check for herself."},
        ],
        "reveal": "Her pension hadn't arrived that month.", "tell": "She kept bringing up her pension.",
    },
    "battery": {
        "premise": "Her phone battery is nearly dead and the charger is in the other room.",
        "surface": "Mention that your phone battery is almost finished.",
        "fits": lambda c: c["situation"] != "chai",
        "mods": {"weights": {"urgency": 1.2, "rapport": 0.9}},
        "hooks": [],
        "long_line": 20,
        "events": [
            {"id": "beep", "when": {"turn_at_least": 3}, "clip": "battery_low",
             "say": "Your phone just beeped for low battery. React briefly.",
             "then": {"clock": 50, "fact": "Her phone warned that the battery was about to die."},
             "title": "HER BATTERY IS DYING", "note": "Less than a minute left on her phone."},
        ],
        "reveal": "Her phone battery was about to die.", "tell": "She said her battery was low.",
    },
    "other_call": {
        "premise": "Her friend keeps ringing on the other line to gossip, and she wants to get back to her.",
        "surface": "Mention that your friend is trying to call you on the other line.",
        "fits": lambda c: c["social"] in ("alone", "helper") and c["situation"] not in ("nap", "puja"),
        "mods": {"weights": {"secrecy": 0.8, "rapport": 1.15}},
        "hooks": [],
        "events": [
            {"id": "call_waiting", "when": {"turn_at_least": 2}, "action": "hold", "clip": "hold_call",
             "why": "Dadi is talking to her friend on the other line",
             "say": "End your reply by noticing your friend is calling on the other line.",
             "then": {"flag": "friend", "fact": "She took her friend's call in the middle of this one."},
             "title": "SHE PUT YOU ON HOLD", "note": "Her friend is on the other line."},
            {"id": "told_friend", "when": {"flag": "friend", "used": "secrecy"},
             "say": "Admit, a bit guiltily, that you told your friend about this call while you had her on the line.",
             "then": {"suspicion": 10, "fact": "She told her friend about the call, secret or not."},
             "title": "SHE TOLD HER FRIEND", "note": "So much for keeping it secret."},
        ],
        "reveal": "Her friend kept calling on the other line.", "tell": "She mentioned a friend trying to call.",
    },
}

# Used for the staged demo: conversational events only, nothing that interrupts the call.
DEMO_SCENARIO = "strange_sms"


def candidates(c: dict) -> list[str]:
    return sorted(k for k, s in SCENARIOS.items() if s["fits"](c))


def pick(c: dict, code: str) -> str:
    rng = random.Random(f"scene-{code}")
    return rng.choice(candidates(c))


def apply(c: dict, key: str) -> dict:
    """Her numbers with the scenario on top. Not renormalised: the situation really
    can make some approaches stronger or weaker today."""
    s = SCENARIOS[key]
    m = s.get("mods", {})
    c = dict(c, weights=dict(c["weights"]))
    for t, x in m.get("weights", {}).items():
        c["weights"][t] = round(min(1.9, max(0.4, c["weights"][t] * x)), 2)
    c["dislikes"] = sorted((t for t in c["weights"] if c["weights"][t] < 0.8), key=c["weights"].get)[:2]
    c["start"] = min(25, c["start"] + m.get("start", 0))
    c["contradiction"] += m.get("contradiction", 0)
    c["trap"] = max(c["trap"], m.get("trap", 0))
    c["ask_heat"] = m.get("ask_heat", 0)
    c["story"] = m.get("story", 3)
    c["scenario"] = key
    return c


class Scene:
    """The scenario as it plays out: which events fired, what she now knows, and flags
    the player's choices have set."""

    def __init__(self, key: str, demo: bool = False):
        self.key = key
        self.spec = SCENARIOS[key]
        self.demo = demo
        self.fired: list[str] = []
        self.flags: set[str] = set()
        self.facts: list[str] = []
        self.pending: dict | None = None

    def holds(self, when: dict, g, said: str, saying: tuple = ()) -> bool:
        checks = {
            "turn_at_least": lambda v: g.turns >= v,
            "trust_at_least": lambda v: g.trust >= v,
            "suspicion_at_least": lambda v: g.suspicion >= v,
            "suspicion_below": lambda v: g.suspicion < v,
            "used": lambda v: bool(g.tactics.get(v)) or v in saying,  # counts what they're saying right now
            "flag": lambda v: v in self.flags,
            "said": lambda v: bool(re.search(v, said, re.I)),
        }
        return all(checks[k](v) for k, v in when.items())

    def next_event(self, g, said: str, saying: tuple = ()) -> dict | None:
        """At most one event a turn, decided before she replies so she can react to it."""
        for e in self.spec["events"]:
            if e["id"] in self.fired:
                continue
            if self.demo and (e.get("action") or "clock" in e.get("then", {})):
                continue  # the staged demo never gets interrupted
            # An event that would be a second version of one already fired stays quiet.
            if e.get("then", {}).get("flag") and e["then"]["flag"] in self.flags:
                continue
            if self.holds(e["when"], g, said, saying):
                self.fired.append(e["id"])
                self.pending = e
                return e
        return None

    def settle(self, g) -> dict:
        """Apply the event's consequences after the turn is scored."""
        e, self.pending = self.pending, None
        if not e:
            return {}
        then = e.get("then", {})
        before = g.suspicion
        # An event can make things worse, but never ends the call by itself.
        g.suspicion = max(0.0, min(max(before, 95.0), g.suspicion + then.get("suspicion", 0)))
        g.trust = min(100.0, max(0.0, g.trust + then.get("trust", 0)))
        if then.get("flag"):
            self.flags.add(then["flag"])
        if then.get("fact"):
            self.facts.append(then["fact"])
        g.log("event", event=e["id"], name=e["title"].capitalize(), susp=round(g.suspicion - before))
        return {"title": e["title"], "note": e["note"], "clip": e.get("clip"), "why": e.get("why"),
                "clock": then.get("clock"), "action": e.get("action")}

    def hook(self, said: str, tactic: str) -> float:
        """A topic that's already on her mind lands harder."""
        for pattern, t, x in self.spec.get("hooks", []):
            if t == tactic and re.search(pattern, said, re.I):
                return x
        return 1.0

    def prompt(self, g) -> str:
        bits = [f"What's going on in her life today: {self.spec['premise']}"]
        if g.turns <= 2 and not self.facts:
            bits.append(self.spec["surface"])
        if self.facts:
            bits.append("Things that have happened during this call, which you remember: " + " ".join(self.facts))
        if self.pending:
            bits.append(f"This turn: {self.pending['say']}")
        return " ".join(bits)

    def reveal(self) -> dict:
        return {"id": self.key, "reveal": self.spec["reveal"], "tell": self.spec["tell"], "events": list(self.fired)}
