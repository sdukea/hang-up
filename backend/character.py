"""Who picks up: a different grandmother every call, built from controlled parts.

A character is a situation, a temperament, one or two hidden traits, who else is
around, today's mood, her hearing and how much she knows about phones, plus a
name and an age. A seed (the scenario code) picks every part, so a daily
challenge or a friend's link meets the same person. Then a validation pass
re-rolls any part that doesn't fit the rest, so she's always one believable
person.

The engine reads only numbers from here: which tactics work on her, what
pressure costs, how fast she tires, which counter-moves she uses. The LLM gets a
plain description and has to act it out. It never decides the rules.

Every part comes with a clue the player can learn to spot, and a line that
explains it after the call. Unpredictable, but never random.
"""

import random
import secrets
import string

TACTICS = ["authority", "fear", "urgency", "secrecy", "rapport"]

# Hour bands: 0 morning, 1 late morning, 2 afternoon, 3 evening, 4 night.
def hour_band(hour: int) -> int:
    if 5 <= hour < 10:
        return 0
    if 10 <= hour < 14:
        return 1
    if 14 <= hour < 17:
        return 2
    if 17 <= hour < 21:
        return 3
    return 4


NAMES = [
    ("Kamla", "कमला"), ("Sushila", "सुशीला"), ("Shanti", "शांति"), ("Pushpa", "पुष्पा"), ("Savitri", "सावित्री"),
    ("Leela", "लीला"), ("Usha", "उषा"), ("Kusum", "कुसुम"), ("Saroj", "सरोज"), ("Prabha", "प्रभा"),
    ("Malti", "मालती"), ("Asha", "आशा"), ("Lata", "लता"), ("Nirmala", "निर्मला"), ("Sarla", "सरला"),
    ("Shakuntala", "शकुंतला"), ("Kaushalya", "कौशल्या"), ("Vidya", "विद्या"), ("Rajni", "रजनी"), ("Sudha", "सुधा"),
]

# Where she is when the phone rings. Each has recorded greetings and a busted line
# under its key, the hours it makes sense in, and who can plausibly be around.
SITUATIONS = {
    "puja": {
        "label": "in the middle of her puja", "bands": {0, 3},
        "voice": "She is in the middle of her puja: bell, aarti, bits of prayer. She blesses the caller and won't be hurried.",
        "mods": {"urgency": 0.6, "rapport": 1.15, "authority": 1.1}, "social": ["alone", "grandson"],
        "moods": ["content", "cheerful", "worried"], "effects": [],
    },
    "serial": {
        "label": "watching her TV serial", "bands": {1, 3, 4},
        "voice": "Her TV serial is on loud. Now and then she compares the caller to its invented villains, or shushes them for the ad break.",
        "mods": {"fear": 1.3, "rapport": 0.8}, "social": ["alone", "grandson", "neighbour"],
        "moods": ["content", "irritable", "cheerful"], "effects": [],
    },
    "nap": {
        "label": "woken from her nap", "bands": {1, 2},
        "voice": "She has just been woken from a nap. Groggy, yawning, and mishearing words in funny ways.",
        "mods": {"authority": 1.3, "secrecy": 0.85, "rapport": 0.9}, "social": ["alone", "grandson", "helper"],
        "moods": ["tired", "irritable"], "effects": ["shout"],
    },
    "chai": {
        "label": "at her kitty party", "bands": {2, 3},
        "voice": "Her friends {sharmila} and {bimla} are over for chai and the phone is on speaker. She repeats the caller's claims to the room, or one friend gets in a short sharp comment. One friend per reply at most.",
        "mods": {"secrecy": 1.35, "authority": 0.8}, "social": ["friends"],
        "moods": ["cheerful", "content"], "effects": [],
    },
    "night": {
        "label": "awake late at night", "bands": {4},
        "voice": "She can't sleep, and she is quietly glad anyone called. The house is dark and still.",
        "mods": {"rapport": 1.1, "fear": 0.85, "secrecy": 1.15}, "social": ["alone", "grandson"],
        "moods": ["content", "worried", "tired"], "effects": [],
    },
    "kitchen": {
        "label": "cooking", "bands": {0, 1, 3},
        "voice": "She is cooking, with the pressure cooker going, and keeps breaking off to stir something or check the gas.",
        "mods": {"urgency": 1.2, "secrecy": 1.1, "rapport": 0.9}, "social": ["alone", "grandson", "helper"],
        "moods": ["content", "irritable", "cheerful"], "effects": ["hold"],
    },
    "leaving": {
        "label": "about to go out", "bands": {0, 1, 2},
        "voice": "She was just leaving for the market and the auto is waiting outside. She is half out of the door and keeps saying so.",
        "mods": {"urgency": 1.35, "authority": 1.1, "rapport": 0.8}, "social": ["alone", "helper"],
        "moods": ["irritable", "content", "worried"], "effects": [], "pace": 1,
    },
    "searching": {
        "label": "hunting for something she's lost", "bands": {0, 1, 2, 3, 4},
        "voice": "She has lost something (her glasses, the keys or the TV remote) and keeps looking for it while she talks.",
        "mods": {"urgency": 1.15, "authority": 0.9}, "social": ["alone", "grandson", "neighbour", "helper"],
        "moods": ["content", "irritable", "cheerful", "worried"], "effects": ["decoy", "shout"],
    },
}

# Her core personality. Changes what works, what pressure costs, how long she
# talks and how quickly she gets suspicious. The habit is her tell.
TEMPERAMENTS = {
    "chatty": {
        "label": "warm and chatty", "mods": {"rapport": 1.3, "fear": 0.8, "urgency": 0.8, "secrecy": 1.1},
        "voice": "Warm and chatty. She tells little stories, asks about the caller's family, and gives away small details without meaning to.",
        "habit": "drifts into small stories and asks the caller personal questions", "pace": -1, "words": 24, "start": -5,
        "tell": "She talked a lot and kept asking about you.",
    },
    "sceptic": {
        "label": "sharp and sceptical", "mods": {"authority": 0.7, "secrecy": 0.9, "fear": 1.15, "rapport": 0.85},
        "voice": "Sharp and sceptical. Polite, but she questions every claim.",
        "habit": "fires short pointed questions: who, why, from where, how", "pace": 0, "words": 16, "start": 10,
        "tell": "She answered almost everything with a question.",
    },
    "blunt": {
        "label": "blunt and impatient", "mods": {"urgency": 0.6, "rapport": 0.6, "authority": 1.35},
        "voice": "Blunt and impatient. No small talk. She wants the caller to get to the point.",
        "habit": "cuts the caller short and tells them to get to the point", "pace": 1, "words": 13, "start": 0,
        "tell": "Her replies got shorter and sharper when you rambled.",
    },
    "worrier": {
        "label": "anxious and easily worried", "mods": {"fear": 1.4, "urgency": 1.35, "secrecy": 0.75},
        "voice": "Anxious. Bad news frightens her and she keeps asking whether everything will be all right.",
        "habit": "worries out loud and asks for reassurance again and again", "pace": 0, "words": 20, "start": -5,
        "tell": "She kept asking if everything would be all right.",
    },
    "scatter": {
        "label": "cheerful but scatterbrained", "mods": {"secrecy": 0.85, "authority": 1.1, "urgency": 1.2, "rapport": 0.9},
        "voice": "Cheerful and scatterbrained. She loses the thread, gets distracted by things around her, and asks the caller to repeat themselves.",
        "habit": "loses the thread and asks the caller to start again", "pace": 0, "words": 20, "start": -5,
        "tell": "She kept losing track and asking you to repeat yourself.",
    },
    "proud": {
        "label": "proud and stubborn", "mods": {"authority": 0.55, "fear": 0.6, "rapport": 1.3, "secrecy": 1.2},
        "voice": "Proud and stubborn. Nobody tells her what to do, and she is afraid of no one. Respect is the only way in.",
        "habit": "announces she isn't scared of anyone and won't be ordered about", "pace": 0, "words": 16, "start": 0,
        "tell": "She bristled at orders but softened at respect.",
    },
    "curious": {
        "label": "nosy and curious", "mods": {"secrecy": 1.35, "authority": 1.1, "rapport": 0.9},
        "voice": "Nosy and curious. She loves a story and asks follow-up questions about every detail of the caller's.",
        "habit": "asks follow-up questions about the details of the caller's story", "pace": 0, "words": 18, "start": 0,
        "tell": "She dug into every detail of your story.",
    },
    "lonely": {
        "label": "lonely and sweet", "mods": {"rapport": 1.45, "fear": 0.6, "urgency": 0.8},
        "voice": "Lonely and sweet. She is delighted to have someone to talk to and wants to keep them on the line. Threats make her sad, not scared.",
        "habit": "keeps the caller talking and asks them to stay a bit longer", "pace": -1, "words": 22, "start": -5,
        "tell": "She wanted company more than anything.",
    },
}

# Never announced. Each changes a rule, shows up in how she talks, and is
# explained after the call along with the clue that gave it away.
TRAITS = {
    "memory": {
        "cue": "Every so often, quote the caller's own earlier words back to them exactly.",
        "trap": 0.85, "contradiction": 12,
        "reveal": "She remembered every word you said.", "tell": "She repeated your earlier words back to you.",
    },
    "verifier": {
        "cue": "Mention, now and then, that you will check things yourself with the bank or the police station.",
        "effects": ["callback"], "first": "callback", "mods": {"authority": 0.85},
        "reveal": "She checks things herself.", "tell": "She talked about checking with someone.",
    },
    "pressure": {
        "cue": "Get sharper and more stubborn whenever you're rushed or threatened.",
        "mods": {"fear": 0.7, "urgency": 0.7}, "heat": {"fear": 7, "urgency": 7},
        "reveal": "Pressure made her dig in.", "tell": "She got sharper every time you pushed.",
    },
    "kindness": {
        "cue": "Soften noticeably whenever the caller is polite or asks about you.",
        "mods": {"rapport": 1.25}, "soft_repeat": "rapport",
        "reveal": "Kindness got further than threats.", "tell": "She warmed up whenever you were polite.",
    },
    "titles": {
        "cue": "Big titles don't impress you. Ask for names and offices, and sound unimpressed.",
        "mods": {"authority": 0.55}, "heat": {"authority": 6},
        "reveal": "Big titles didn't impress her.", "tell": "She asked for names and sounded unimpressed by your rank.",
    },
    "family": {
        "cue": "Keep saying you'll ask your son or grandson about this.",
        "mods": {"secrecy": 0.6}, "heat": {"secrecy": 5}, "effects": ["pappu", "callback"],
        "reveal": "She wanted her family's opinion first.", "tell": "She kept bringing up her family.",
    },
    "calm": {
        "cue": "Relax a little whenever the caller is patient and doesn't push.",
        "calm": 4,
        "reveal": "She calmed down when you slowed down.", "tell": "Her tone eased when you stopped pushing.",
    },
}

SOCIAL = {
    "alone": {"voice": "She is alone at home.", "reveal": "alone at home"},
    "grandson": {"voice": "Her grandson {pappu} is in the next room, and she may call him over.", "effects": ["pappu"],
                 "reveal": "with her grandson in the next room"},
    "friends": {"voice": "", "reveal": "with her friends over"},
    "neighbour": {"voice": "Her neighbour has dropped in and is sitting with her, listening.", "effects": ["callback"],
                  "mods": {"secrecy": 0.85}, "reveal": "with a neighbour sitting beside her"},
    "helper": {"voice": "Her household helper is working nearby and sometimes chips in.", "mods": {"secrecy": 0.9},
               "reveal": "with her helper working nearby"},
}

MOODS = {
    "cheerful": {"voice": "She is in a rare good mood today.", "start": -5, "reveal": "in a good mood"},
    "content": {"voice": "", "start": 0, "reveal": ""},
    "tired": {"voice": "She is tired and a bit slow today.", "start": 0, "pace": -1, "reveal": "tired"},
    "irritable": {"voice": "She is irritable today and short with people.", "start": 5, "pace": 1, "reveal": "irritable"},
    "worried": {"voice": "She is already worried about something at home today.", "start": 0, "mods": {"fear": 1.15}, "reveal": "already worried"},
}

HEARING = {
    "fine": {"voice": "", "effects": []},
    "weak": {"voice": "Her hearing aid battery is low, so she keeps asking the caller to speak up.", "effects": ["shout"]},
}

PHONES = {
    "unsure": {"voice": "Phones confuse her. She isn't sure what an OTP is and needs things explained.", "ask": 1.1},
    "savvy": {"voice": "She knows her way around a phone and knows exactly what an OTP is.", "ask": 0.85},
}

COUNTERS = ["hold", "shout", "callback", "decoy", "pappu"]
SHARPEN = 1.5


def new_code(hour: int, rng: random.Random | None = None) -> str:
    """A fresh scenario code: the hour band, then four characters of seed."""
    pick = rng or secrets.SystemRandom()
    tail = str(pick.randrange(5)) + "".join(pick.choice(string.ascii_uppercase) for _ in range(3))
    return f"{hour_band(hour)}{tail}"


def generate(code: str) -> dict:
    """Build one coherent grandmother from a scenario code. Same code, same person."""
    rng = random.Random(f"dadi-{code}")
    band = int(code[0]) if code[:1].isdigit() and int(code[0]) < 5 else 4
    c = {"code": code, "band": band}
    c["name"], c["name_hi"] = rng.choice(NAMES)
    c["age"] = rng.randint(70, 86)
    c["situation"] = rng.choice(sorted(k for k, s in SITUATIONS.items() if band in s["bands"]))
    c["temperament"] = rng.choice(sorted(TEMPERAMENTS))
    c["traits"] = rng.sample(sorted(TRAITS), rng.choice([1, 2, 2]))
    s = SITUATIONS[c["situation"]]
    c["social"] = rng.choice(s["social"])
    c["mood"] = rng.choice(s["moods"])
    c["hearing"] = "weak" if rng.random() < 0.25 else "fine"
    c["phone"] = rng.choice(sorted(PHONES))
    return validate(c, rng)


def preset(**parts) -> dict:
    """A fixed character through the same machinery, for the staged demo."""
    c = {"code": "DEMO", "band": 3, "name": "Kamla", "name_hi": "कमला", "age": 78, "situation": "chai",
         "temperament": "chatty", "traits": ["calm"], "social": "friends", "mood": "cheerful", "hearing": "fine", "phone": "unsure"}
    c.update(parts)
    return validate(c, random.Random(0))


# Each rule finds a clash and fixes the part that's out of place.
def _rules(c: dict) -> list[tuple[str, callable]]:
    s = SITUATIONS[c["situation"]]
    return [
        ("social fits the situation", lambda: c["social"] in s["social"],
         lambda rng: c.update(social=rng.choice(s["social"]))),
        ("mood fits the situation", lambda: c["mood"] in s["moods"],
         lambda rng: c.update(mood=rng.choice(s["moods"]))),
        ("a scatterbrain can't have perfect recall", lambda: not (c["temperament"] == "scatter" and "memory" in c["traits"]),
         lambda rng: _swap_trait(c, "memory", rng)),
        ("a worrier isn't hardened by pressure", lambda: not (c["temperament"] == "worrier" and "pressure" in c["traits"]),
         lambda rng: _swap_trait(c, "pressure", rng)),
        ("a lonely Dadi on her own, not at a party", lambda: not (c["temperament"] == "lonely" and c["social"] == "friends"),
         lambda rng: c.update(temperament=rng.choice(["chatty", "curious", "worrier"]))),
        ("titles and pride overlap; keep them distinct", lambda: not (c["temperament"] == "proud" and "titles" in c["traits"]),
         lambda rng: _swap_trait(c, "titles", rng)),
        ("a blunt Dadi isn't won over by sweetness", lambda: not (c["temperament"] == "blunt" and "kindness" in c["traits"]),
         lambda rng: _swap_trait(c, "kindness", rng)),
        ("a sceptic isn't charmed by sweetness either", lambda: not (c["temperament"] == "sceptic" and "kindness" in c["traits"]),
         lambda rng: _swap_trait(c, "kindness", rng)),
        ("the calm trait needs a temper to calm", lambda: not (c["temperament"] in ("chatty", "lonely") and "calm" in c["traits"]),
         lambda rng: _swap_trait(c, "calm", rng)),
        ("family trait needs family in reach", lambda: not ("family" in c["traits"] and c["social"] == "friends"),
         lambda rng: _swap_trait(c, "family", rng)),
        ("a sleepy Dadi isn't sharp with phones and memory at once",
         lambda: not (c["situation"] == "nap" and c["phone"] == "savvy" and "memory" in c["traits"]),
         lambda rng: c.update(phone="unsure")),
        ("no duplicate traits", lambda: len(set(c["traits"])) == len(c["traits"]),
         lambda rng: c.update(traits=sorted(set(c["traits"])))),
    ]


def _swap_trait(c: dict, bad: str, rng: random.Random) -> None:
    options = sorted(set(TRAITS) - set(c["traits"]) - {bad})
    c["traits"] = [t if t != bad else rng.choice(options) for t in c["traits"]]


def problems(c: dict) -> list[str]:
    return [name for name, ok, _ in _rules(c) if not ok()]


def validate(c: dict, rng: random.Random) -> dict:
    for _ in range(12):
        broken = [(name, fix) for name, ok, fix in _rules(c) if not ok()]
        if not broken:
            break
        broken[0][1](rng)
    c.update(mechanics(c))
    return c


def mechanics(c: dict) -> dict:
    """The numbers the engine plays by. Weights are normalised, so a character
    changes *what* works on her, not how easy she is overall."""
    parts = [SITUATIONS[c["situation"]], TEMPERAMENTS[c["temperament"]], SOCIAL[c["social"]], MOODS[c["mood"]],
             *[TRAITS[t] for t in c["traits"]]]
    weights = {t: 1.0 for t in TACTICS}
    heat = {t: 0 for t in TACTICS}
    for part in parts:
        for t, m in part.get("mods", {}).items():
            weights[t] *= m
        for t, h in part.get("heat", {}).items():
            heat[t] += h
    # Sharpen, so her likes and dislikes are clear enough to read and worth reading.
    weights = {t: min(1.8, max(0.45, w)) ** SHARPEN for t, w in weights.items()}
    mean = sum(weights.values()) / len(weights)
    weights = {t: round(min(1.8, max(0.45, w / mean)), 2) for t, w in weights.items()}

    # Pappu can only take the phone if he's actually there.
    effects = ["hold", "shout", "callback", "decoy"] + (["pappu"] if c["social"] == "grandson" else [])
    bias =[e for part in parts + [HEARING[c["hearing"]]] for e in part.get("effects", []) if e in effects]
    return {
        "weights": weights, "heat": heat,
        # At most her two least-liked approaches backfire, so there's always a clean route
        # through the three-tactic story for a player who reads her.
        "dislikes": sorted((t for t in weights if weights[t] < 0.8), key=weights.get)[:2],
        "pace": min(6, max(3, 4 + sum(part.get("pace", 0) for part in parts))),  # suspicion every turn adds
        "start": min(20, sum(part.get("start", 0) for part in parts)),     # suspicion when she picks up
        "ask": PHONES[c["phone"]]["ask"],
        "effects": effects, "bias": bias,
        "first": next((TRAITS[t]["first"] for t in c["traits"] if "first" in TRAITS[t]), None),
        "trap": max([TRAITS[t].get("trap", 0.5) for t in c["traits"]] or [0.5]),
        "contradiction": sum(TRAITS[t].get("contradiction", 0) for t in c["traits"]),
        "calm": sum(TRAITS[t].get("calm", 0) for t in c["traits"]),
        "soft_repeat": next((TRAITS[t]["soft_repeat"] for t in c["traits"] if "soft_repeat" in TRAITS[t]), None),
        "words": TEMPERAMENTS[c["temperament"]]["words"],
    }


# Her strongest and weakest spots, told to the LLM as how she reacts, so her replies
# give the player clues to read.
LIKES = {
    "authority": "Confidence and an official-sounding title impress her.", "fear": "Bad news and threats rattle her.",
    "urgency": "A deadline makes her want to get it over with.", "secrecy": "She enjoys being trusted with a secret.",
    "rapport": "Warmth and respect soften her.",
}
DISLIKES = {
    "authority": "Titles and official airs put her off.", "fear": "Threats make her dig in, not panic.",
    "urgency": "Being rushed annoys her.", "secrecy": "Being told to hide things from her family makes her wary.",
    "rapport": "Sweet talk and flattery bore her.",
}


def display_name(c: dict, lang: str) -> str:
    return f"{c['name_hi']} दादी" if lang == "hi" else f"{c['name']} Dadi"


def describe(c: dict, lang: str, friends: dict, pappu: str) -> str:
    """Who she is today, for the LLM. Traits are described as behaviour, never named."""
    s, t = SITUATIONS[c["situation"]], TEMPERAMENTS[c["temperament"]]
    about = [s["voice"].format(**friends), SOCIAL[c["social"]]["voice"].format(pappu=pappu), MOODS[c["mood"]]["voice"],
             HEARING[c["hearing"]]["voice"], PHONES[c["phone"]]["voice"]]
    return (f"You are {display_name(c, lang)}, {c['age']}. About her: {' '.join(b for b in about if b)} "
            f"Personality: {t['voice']} Her habit: she {t['habit']}. "
            f"How to play her: {' '.join(TRAITS[x]['cue'] for x in c['traits'])} "
            f"{LIKES[max(c['weights'], key=c['weights'].get)]} {DISLIKES[min(c['weights'], key=c['weights'].get)]} "
            "Show these in how you react to each line, never by stating them.")


def reveal(c: dict) -> dict:
    """After the call: who she was, and the clue behind each part of her."""
    s, t = SITUATIONS[c["situation"]], TEMPERAMENTS[c["temperament"]]
    mood = MOODS[c["mood"]]["reveal"]
    scene = f"{s['label'].capitalize()}, {SOCIAL[c['social']]['reveal']}" + (f", {mood}" if mood else "") + "."
    return {
        "name": f"{c['name']} Dadi", "age": c["age"], "scene": scene,
        "temperament": {"label": t["label"].capitalize(), "tell": t["tell"]},
        "traits": [{"reveal": TRAITS[x]["reveal"], "tell": TRAITS[x]["tell"]} for x in c["traits"]],
        "works": max(c["weights"], key=c["weights"].get), "fails": min(c["weights"], key=c["weights"].get),
    }


def debug(c: dict) -> dict:
    keys = ["code", "name", "age", "situation", "temperament", "traits", "social", "mood", "hearing", "phone",
            "weights", "dislikes", "heat", "pace", "start", "ask", "effects", "bias", "first", "trap", "contradiction", "calm", "words"]
    return {k: c[k] for k in keys}
