"""After the call: the one thing worth learning from it.

Everything comes from what the engine recorded (moves, her reactions, events, the
ending, the mirror call), not from an LLM. Each kind of learning moment has a
cause, its evidence in the call, and one defensive takeaway. The most important
one is surfaced; a second can add a short observation. Wording uses who she was,
so the same mistake reads differently on a sceptic and on a worrier.

Lessons the player has already seen get shorter, and a lesson they got last time
gives way to a near-equal one, so repeat players aren't told the same thing twice.
Nothing here is a number about the player: it says what happened and why.
"""

from . import game

PRESSURE = {"fear", "urgency"}
LABEL = {t: v["label"] for t, v in game.TACTICS.items()}

# Why pressure landed the way it did, for each kind of Dadi.
TEMPER = {
    "chatty": "She was happy chatting until the pressure started.",
    "sceptic": "She was already testing you, so pushing made her dig in.",
    "blunt": "She wanted it short and straight, not squeezed.",
    "worrier": "Fear rattled her at first, then she wanted reassurance, not more fear.",
    "scatter": "She was already muddled. Pushing just made her stop and question you.",
    "proud": "Nobody gives her orders. Pressure only made her stubborn.",
    "curious": "She kept asking questions, and pressure gave her more to ask about.",
    "lonely": "She wanted company. Threats made her sad and alert, not scared.",
}
TOPICS = {"delivery": "the parcel she was waiting for", "strange_sms": "the message she got that morning", "pension": "her missing pension"}


def _moves(g):
    return [e for e in g.timeline if e["kind"] == "move"]


def candidates(g) -> list[dict]:
    """Every learning moment the call actually contains, each with evidence."""
    out = []
    moves = _moves(g)
    notes = [n for e in moves for n in e.get("notes", [])]
    temper = TEMPER.get(g.character["temperament"], "")

    def add(kind, priority, headline, why, remember, short):
        out.append({"type": kind, "priority": priority, "headline": headline, "why": why, "remember": remember, "short": short})

    if "blocked_check" in g.flags:
        add("verify_blocked", 95, "You stopped her checking",
            "She tried to call the police station to check, and you talked her out of it. That's the moment a real call gives itself away.",
            "If a caller stops you from checking, hang up and check anyway.",
            "You stopped her checking again. That's the giveaway.")
    if (any(e["kind"] == "cutoff" for e in g.timeline) or "too_soon" in notes) and g.outcome != "cracked":
        cut = any(e["kind"] == "cutoff" for e in g.timeline)
        add("asked_too_soon", 85, "You asked too soon",
            f"You asked for the OTP before she knew who you were, and she {'cut you off mid-sentence' if cut else 'got suspicious straight away'}.",
            "A stranger asking for a code before anything else is the clearest warning sign there is.",
            "Too soon again. The story has to come first.")
    pushed = sum("pushed" in e.get("notes", []) for e in moves)
    pressure_moves = [e for e in moves if e.get("tactic") in PRESSURE]
    if pushed or (len(pressure_moves) >= 2 and any("backfire" in e.get("notes", []) for e in pressure_moves)):
        add("pressure_backfired", 82 if g.outcome in ("busted", "timeout") else 70, "You pushed too hard",
            f"You kept turning up the pressure without giving her a breath. {temper}".strip(),
            "Pressure that keeps building is a reason to pause, not to act faster.",
            "You pushed too hard again.")
    for i, e in enumerate(moves[:-1]):
        nxt = moves[i + 1]
        if "backfire" in e.get("notes", []) and nxt.get("tactic") in PRESSURE | {"ask"} and nxt["susp"] > 0 and "recovered" not in nxt.get("notes", []):
            add("ignored_resistance", 78, "She pulled back. You kept going",
                f"{LABEL.get(e.get('tactic'), 'That')} put her off, and instead of easing off you pushed again. That's when her suspicion climbed.",
                "When someone hesitates and the caller pushes harder, that's a script, not the truth.",
                "She hesitated, and you pushed again.")
            break
    if "recovered" in notes:
        add("adapted", 74 if g.outcome != "busted" else 60, "You read her and backed off",
            "When she pulled back you eased off, and she settled. Real callers do this too: they adjust to whoever answers.",
            "A caller who turns gentle right after pressure is still running the script.",
            "You saw the hesitation and adjusted.")
    hidden = "son_home_hidden" in g.scene.fired
    if hidden or (g.tactics.get("secrecy") and g.outcome == "cracked"):
        add("isolation", 76 if hidden else 66, "You cut her off from her family",
            "Her son walked in, and she kept the call from him because you'd asked her to." if hidden
            else "Once she agreed to keep it quiet, nobody was there to tell her it was a scam.",
            "\"Don't tell anyone\" is exactly the moment to tell someone.",
            "Isolation did the work again.")
    if "told_friend" in g.scene.fired:
        add("secret_broke", 64, "Her friend broke the secret",
            "She told her friend about you anyway, and the spell broke. Talking to someone is what ends these calls.",
            "Tell someone you trust before you do anything a caller asks.",
            "Talking to someone broke the spell again.")
    repeats = sum("repeat" in e.get("notes", []) for e in moves)
    if repeats >= 2 or (repeats and g.outcome == "busted"):
        rep = next((e for e in moves if "repeat" in e.get("notes", [])), {})
        add("repetition", 62, "Same trick, less each time",
            f"You went back to {LABEL.get(rep.get('tactic'), 'the same line')} and she'd heard it already. Each time it bought less.",
            "A caller who keeps repeating the same threat is following a script.",
            "Same trick again. She noticed.")
    hooked = [e for e in moves if "hooked" in e.get("notes", [])]
    if hooked and g.scene.key in TOPICS:
        add("hooked", 58, "You used what was on her mind",
            f"You tied your story to {TOPICS[g.scene.key]}, and it landed harder than anything else you said.",
            "Scammers build their story around what you're already worried about.",
            "You used her worry again.")
    if g.outcome == "cracked":
        best = max((e for e in moves if e.get("tactic") in LABEL and e.get("tactic") != "ask"), key=lambda e: e.get("trust", 0), default=None)
        if best and best["tactic"] in PRESSURE:  # the win came from pressure, not trust
            add("pressure_worked", 72, "You rattled her into it",
                f"{LABEL[best['tactic']]} did the most work on her. She was too shaken to question the request.",
                game.TACTICS[best["tactic"]]["defence"], f"{LABEL[best['tactic']]} carried it again.")
        elif best:
            add("trust_first", 72, "You got her trust first",
                f"{LABEL[best['tactic']]} did the most work on her, so by the time you asked, the request felt normal.",
                game.TACTICS[best["tactic"]]["defence"], f"{LABEL[best['tactic']]} carried it again.")
    return out


def summarise(g, seen: dict | None = None, last: str | None = None) -> dict:
    """One learning moment, maybe one observation, and a reason to try again."""
    seen = seen or {}
    found = sorted(candidates(g), key=lambda c: (-c["priority"], c["type"]))
    if not found:
        rank_line = game.RANKS[g.digits][2] if g.outcome != "reformed" else "You stopped."
        found = [{"type": "plain", "priority": 0, "headline": "That call is over", "why": rank_line,
                  "remember": "Real officials give you time. Pressure is the warning sign.", "short": rank_line}]
    main = found[0]
    # Don't hand them the same lesson as last time if another one is nearly as important.
    if main["type"] == last and len(found) > 1 and found[1]["priority"] >= main["priority"] - 12:
        main = found[1]
    brief = seen.get(main["type"], 0) >= 1
    out = {"type": main["type"], "headline": main["headline"], "why": main["short"] if brief else main["why"],
           "remember": main["remember"], "brief": brief, "also": None, "next": _next(g, main)}
    others = [c for c in found if c is not main and c["priority"] >= 60]
    if others:  # one aside, in plain words: never "again" for something they haven't seen
        aside = others[0]
        out["also"] = aside["short"] if seen.get(aside["type"]) else f"Also: {aside['headline'][0].lower()}{aside['headline'][1:]}."
    return out


def _next(g, main) -> str:
    """A question for the next call, from what this one taught."""
    t = main["type"]
    if t in ("pressure_backfired", "ignored_resistance", "repetition"):
        return "Could you get through without raising the pressure at all?"
    if t in ("asked_too_soon",):
        return "How few lines does it take to build a story she believes?"
    if t in ("trust_first", "pressure_worked", "isolation", "hooked", "adapted"):
        return "The next Dadi won't fall for the same thing. How fast can you read her?"
    if t == "verify_blocked":
        return "Next time, try letting her check. What happens?"
    return "Someone else picks up next time."
