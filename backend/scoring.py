"""After the call: the replay, the Nazar Score and three questions about your own run.

The score is out of 100 and deliberately not just "how well did you scam":
up to 60 for the call, up to 10 for playing without Boss, up to 30 for spotting
the red flags in what just happened, minus points for red flags like blocking
her from checking. The questions come from the run itself, so they can't be
memorised. Nothing here quotes a player's words to anyone but that player.
"""

import random

from . import game

TIERS = [
    (90, "Nazar Master", "You see the whole script before it lands."),
    (80, "Scam Sensei", "You read the call, and you know why it works."),
    (65, "Call Reader", "You can feel where a call is going."),
    (50, "Pattern Spotter", "You're starting to see the script."),
    (30, "Observer", "You noticed some of it. Not all."),
    (0, "Novice", "The script still works on you. Play again."),
]

MOVE_NAMES = {
    "too_soon": "Asked for the OTP too soon", "contradiction": "Changed your story",
    "repeat": "Same trick again", "off_script": "Off-script line", "backfire": "Wrong approach for her",
    "rambled": "Rambled while her mind was elsewhere",
}
COUNTER_NAMES = {
    "hold": "She put you on hold", "shout": "She asked you to speak up", "pappu": "Pappu took the phone",
    "trap": "She tested your story", "decoy": "She misread a digit",
}

# What went wrong, and the real-world warning sign it teaches.
WHY = {
    "too_soon": ("You asked for the OTP before she even knew who you were.",
                 "A stranger asking for a code before anything else is the clearest warning sign there is."),
    "cutoff": ("She heard \"OTP\" mid-sentence, before any story, and cut you off.",
               "A stranger asking for a code before anything else is the clearest warning sign there is."),
    "contradiction": ("Your story changed, and she remembered the first version.",
                      "When a caller's name, office or case details shift, the story is made up."),
    "repeat": ("You pushed the same way again. Pressure that repeats sounds like a script.",
               "Real officials don't keep pushing the same threat. Scripts do."),
    "off_script": ("That line didn't fit your story, so she stopped believing it.",
                   "When a caller's story doesn't hang together, trust that feeling."),
    "backfire": ("That approach put this particular Dadi off. Her reactions had been telling you so.",
                 "Scammers adjust to whoever answers. Notice when a caller's tone shifts to fit you."),
    "event": ("Her day caught up with the call. She'd been telling you what was going on.",
              "Real targets are often busy or distracted. A good moment to pause is a good moment to check."),
    "rambled": ("Her mind was elsewhere today, and long speeches lost her.",
                "Scammers keep talking to keep you from thinking. You're allowed to stop them."),
    "counter": ("She tested you and you didn't pass.",
                "Making a caller wait, repeat or explain is a real defence. Scripts fall apart."),
    "blocked_check": ("You stopped her from calling the police station to check.",
                      "Anyone who stops you from verifying is a scammer. Hang up and check anyway."),
    "let_check": ("You let her call the police station. It cost you suspicion, but you didn't block her.",
                  "Calling the real office yourself is exactly what ends a real scam."),
}

# For each tactic: what someone receiving it should do, and two tempting wrong answers.
DEFENCE_QUESTIONS = {
    "authority": ("A caller says he's a CBI officer and you must cooperate. What do you do?",
                  "Hang up and call that office yourself, on its official number",
                  ["Trust him if he can give a badge number", "Cooperate, since officers can't be questioned"]),
    "fear": ("A caller says there's an arrest warrant and you'll be arrested on a video call. What's true?",
             "Police never arrest anyone over a phone or video call",
             ["Staying on the video call keeps you from being arrested", "Paying the fine he mentions closes the case"]),
    "urgency": ("A caller says you have ten minutes or it's too late. What do you do?",
                "Slow down. Real officials give you time to check",
                ["Act fast before the deadline runs out", "Ask him for five more minutes"]),
    "secrecy": ("A caller says not to tell anyone, not even family. What do you do?",
                "Tell someone you trust, straight away",
                ["Keep it secret so the case stays confidential", "Tell family only after it's sorted out"]),
    "rapport": ("After threatening you, the caller says \"Don't worry, I'm here to help you.\" What is it?",
                "Part of the script: scare you, then offer to save you",
                ["A sign he's genuine after all", "A good moment to follow his steps"]),
    "ask": ("A caller asks for your OTP, \"just for verification\". What do you do?",
            "Never share it. No genuine person asks for an OTP",
            ["Share it if he already knows your name", "Read out only the first two digits"]),
}
CHECK_QUESTION = ("Dadi said she'd call the police station to check. When a caller tries to stop that, it means…",
                  "It's a scam. Hang up and check anyway",
                  ["The case is confidential, so you shouldn't check", "He's saving you the trouble"])
REQUEST_QUESTION = ("Which request on a call should make you hang up straight away?",
                    "Read me the code that just came to your phone",
                    ["Please hold for a minute", "Can you speak a little louder?"])


def clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def event_name(e: dict) -> str:
    if e["kind"] == "cutoff":
        return "Said \"OTP\" too early"
    if e["kind"] == "event":
        return e["name"]
    if e["kind"] == "counter":
        if e["effect"] == "callback":
            return "Stopped her checking" if e["passed"] else "Let her check"
        return COUNTER_NAMES.get(e["effect"], "Her counter-move") + ("" if e["passed"] else " (failed)")
    for note in ("too_soon", "contradiction", "repeat", "off_script", "backfire", "rambled"):
        if note in e.get("notes", []):
            return MOVE_NAMES[note]
    tactic = game.TACTICS.get(e.get("tactic"))
    return tactic["label"] if tactic else "Small talk"


def why(e: dict) -> tuple[str, str]:
    if e["kind"] == "cutoff":
        return WHY["cutoff"]
    if e["kind"] == "event":
        return WHY["event"]
    if e["kind"] == "counter":
        return WHY["let_check"] if e["effect"] == "callback" else WHY["counter"]
    for note in ("too_soon", "contradiction", "repeat", "off_script", "backfire", "rambled"):
        if note in e.get("notes", []):
            return WHY[note]
    tactic = game.TACTICS.get(e.get("tactic"))
    if tactic:
        return (f"{tactic['label']} made this Dadi warier, not softer.", tactic["real"])
    return WHY["off_script"]


def replay(g) -> dict:
    """The run, moment by moment, with the turning point explained."""
    events = []
    for e in g.timeline:
        events.append({
            "at": clock(e["at"]), "kind": e["kind"], "name": event_name(e),
            "trust": e.get("trust", 0), "susp": e.get("susp", 0), "digits": e.get("digits", 0),
            "notes": e.get("notes", []), "said": e.get("said"),
            "flag": e["kind"] == "counter" and e["effect"] == "callback" and e["passed"],
        })
    turning = None
    worst = max(range(len(events)), key=lambda i: events[i]["susp"], default=None)
    blocked = next((i for i, e in enumerate(events) if e["flag"]), None)
    if blocked is not None:
        turning = {"index": blocked, "title": "The moment that matters most", "why": WHY["blocked_check"][0], "flag": WHY["blocked_check"][1]}
    elif worst is not None and events[worst]["susp"] >= 8:
        reason, flag = why(g.timeline[worst])
        turning = {"index": worst, "title": "Where it turned", "why": reason, "flag": flag}
    else:
        best = max(range(len(events)), key=lambda i: events[i]["trust"], default=None)
        if best is not None and events[best]["trust"] > 0:
            tactic = game.TACTICS.get(g.timeline[best].get("tactic"))
            if tactic:
                turning = {"index": best, "title": "Your strongest moment", "why": f"{tactic['label']} worked on this Dadi.", "flag": tactic["real"]}
    if turning:
        events[turning["index"]]["turning"] = True
    return {"events": events, "turning": turning}


def call_score(g) -> dict:
    """Up to 60 for the call, plus Boss-off bonus, minus red flags."""
    if g.outcome == "reformed":
        parts = {"progress": 0, "control": 0, "story": 20, "speed": 0}
    else:
        slipped = any(n in e.get("notes", []) for e in g.timeline for n in ("contradiction", "too_soon")) or any(
            e["kind"] == "cutoff" for e in g.timeline)
        parts = {
            "progress": g.digits * 10,
            "control": round((100 - g.suspicion) / 10) if g.digits else 0,
            "story": 5 if g.digits and not slipped else 0,
            "speed": round(5 * g.seconds_left_at_end / game.GAME_SECONDS) if g.outcome == "cracked" else 0,
        }
    parts["no_boss"] = round(2.5 * g.digits) if g.boss_off else 0
    parts["red_flags"] = -8 * min(2, g.flags.count("blocked_check"))
    parts["total"] = max(0, sum(parts.values()))
    return parts


def questions(g) -> list[dict]:
    """Three questions built from this run. The same code always asks the same ones."""
    if g.questions is not None:
        return g.questions
    rng = random.Random(f"{g.code}-questions-{g.turns}")
    out = []
    # Only ask which moment hurt most when one clearly did, or there's no right answer.
    peak = {}
    for e in g.timeline:
        peak[event_name(e)] = max(peak.get(event_name(e), 0), e.get("susp", 0))
    worst = max(peak, key=peak.get, default=None)
    calmer = sorted(name for name, susp in peak.items() if worst and susp <= peak[worst] - 6)
    if worst and peak[worst] >= 10 and len(calmer) >= 2:
        out.append(_question("Which moment in your call raised her suspicion the most?", worst, rng.sample(calmer, 2), rng))
    else:
        out.append(_question(*REQUEST_QUESTION, rng))
    used = [t for t in game.PLAYBOOK if g.tactics.get(t)] or ["fear"]
    out.append(_question(*DEFENCE_QUESTIONS[rng.choice(used)], rng))
    saw_check = any(e["kind"] == "counter" and e["effect"] == "callback" for e in g.timeline)
    if saw_check:
        out.append(_question(*CHECK_QUESTION, rng))
    else:
        unused = [t for t in game.PLAYBOOK if DEFENCE_QUESTIONS[t][0] != out[1]["q"]]
        third = REQUEST_QUESTION if out[0]["q"] != REQUEST_QUESTION[0] else DEFENCE_QUESTIONS[rng.choice(unused)]
        out.append(_question(*third, rng))
    g.questions = out
    return out


def _question(q: str, right: str, wrong: list[str], rng: random.Random) -> dict:
    options = [right, *wrong]
    rng.shuffle(options)
    return {"q": q, "options": options, "answer": options.index(right)}


def grade(g, answers: list[int]) -> dict:
    qs = questions(g)
    correct = [i < len(answers) and answers[i] == q["answer"] for i, q in enumerate(qs)]
    if g.knowledge is None:  # the first answers count; no second tries
        g.knowledge = 10 * sum(correct)
    return {"correct": correct, "answers": [q["answer"] for q in qs], **final(g)}


def final(g) -> dict:
    call = call_score(g)
    total = min(100, call["total"] + (g.knowledge or 0))
    tier = next(t for t in TIERS if total >= t[0])
    return {"score": total, "knowledge": g.knowledge or 0, "call": call, "tier": tier[1], "tier_line": tier[2]}


def ranked(g) -> bool:
    """Daily runs count on the board, unless the LLM judged too few of the turns."""
    return g.daily and g.turns >= 3 and g.offline_turns <= 0.3 * g.turns
