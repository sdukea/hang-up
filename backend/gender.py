"""He, not she: player-facing text for Dadaji, made from the text written for Dadi.

Only ever applied when Dadaji picks up, so Dadi's and Pinky's text never changes.
The same rules run in the browser (regender in game.js); keep the two in step.
"""

import re

# After these words, "her" is the object ("tell her", "let her talk"), so "him".
_VERBS = set("""let make help keep leave get give tell ask rush lose push scare calm hear watch catch convince trust call
annoy bore impress rattle frighten soften warm win wake stop flatter pressure isolate reassure remind interrupt
corner fool trick reach beat crack hand show put stuck caught called bring brought made let's lets lost
told asked rushed pushed scared calmed heard watched trusted annoyed bored impressed rattled frightened softened
warmed woke stopped flattered pressured isolated reassured reminded interrupted fooled tricked reached beat cracked
letting stopping making helping giving telling asking keeping leaving rushing pushing scaring calming losing
""".split())
# After "her", these are hers: "told her friend" is his friend, even after a verb.
_NOUNS = set("""friend friends family son daughter grandson husband wife pension phone passbook battery trust suspicion mind story
guard replies reply tone own doubts attention hands name parcel savings diary file bank account money day life""".split())
# Before these, "her" is still the object ("give her a reason", "rush her into it").
_FOLLOW = set("""to into up down off out in on back again a an the that this what why how about with for and or but from
before after when if more less feel think know too over so just any some at by as than while until yet still now
here there enough alone going it something anything nothing someone anyone your you all first once twice properly
quickly anymore either is was will would can could""".split())

_WORDS = [
    (r"hiding the call from him\b", "hiding the call from his son"),
    (r"\bDADI\b", "DADAJI"), (r"\bDadi\b", "Dadaji"), (r"दादी", "दादाजी"),
    (r"\bgrandmothers\b", "grandfathers"), (r"\bgrandmother\b", "grandfather"), (r"\bGrandmother\b", "Grandfather"),
    (r"\bgrandmotherly\b", "grandfatherly"), (r"\bgranny\b", "grandpa"), (r"\bold woman\b", "old man"),
    (r"\bSHE'S\b", "HE'S"), (r"\bSHE\b", "HE"), (r"\bShe\b", "He"), (r"\bshe\b", "he"),
    (r"\bherself\b", "himself"), (r"\bHerself\b", "Himself"), (r"\bhers\b", "his"),
]
_HER = re.compile(r"\b(her|Her|HER)\b")

# Hinglish and Hindi: a sentence about him gets masculine verbs. A sentence whose
# subject is some feminine thing (the clock, your story, the police) is left alone.
_THINGS = re.compile(r"\b(ghadi|kahani|baat|police|call|aawaz|awaaz|pension|line|gaadi|cheez|galti|chaal|warning|internship|"
                     r"battery|ghanti|script|trick|story|zindagi|duniya|bhasha)\b|घड़ी|कहानी|बात|पुलिस|आवाज़|पेंशन|लाइन|गाड़ी|चीज़|ग़लती|चाल", re.I)
_HIM = re.compile(r"\b(woh|wo|vo|use|usse|usko|uski|uska)\b|वो|वह|उसे|उसको", re.I)
_VERB_FIXES = [
    (r"\brahi\b", "raha"), (r"\bgayi\b", "gaya"), (r"\bthi\b", "tha"), (r"\bhui\b", "hua"), (r"\bchuki\b", "chuka"),
    (r"\bsakti\b", "sakta"), (r"\bakeli\b", "akela"), (r"\b(\w+)egi\b", r"\1ega"),
    (r"\b(\w{2,})ti\b(?=\s+(hai|hain|thi|tha|ho|nahi|nahin)\b)", r"\1ta"),
    (r"रही", "रहा"), (r"गई", "गया"), (r"(?<![\u0900-\u0963\u0966-\u097F])थी(?![\u0900-\u0963\u0966-\u097F])", "था"), (r"ती है", "ता है"),
    (r"ेगी(?![\u0900-\u0963\u0966-\u097F])", "ेगा"),
]
_SENTENCE = re.compile(r"[^.!?।]+[.!?।]*")
_HINDI_HINT = re.compile(r"[ऀ-ॿ]|\b(hai|nahi|kar|raha|rahi|woh|tu|tera|teri|mat|aur|ab|bhi|ko|se|\w+egi|gayi|chuki)\b", re.I)


def _her(m: re.Match) -> str:
    word, text, start, end = m.group(1), m.string, m.start(), m.end()
    after = re.match(r"\s*([A-Za-z']+)?", text[end:])
    nxt = (after.group(1) or "").lower() if after else ""
    before = re.search(r"([A-Za-z']+)\W*$", text[:start])
    prev = before.group(1).lower() if before else ""
    obj = not nxt or nxt in _FOLLOW or not re.match(r"\s*[A-Za-z]", text[end:]) or (prev in _VERBS and nxt not in _NOUNS)
    out = "him" if obj else "his"
    return out.upper() if word.isupper() else out.capitalize() if word[0].isupper() else out


def _hindi(sentence: str) -> str:
    if not _HINDI_HINT.search(sentence):
        return sentence
    if _THINGS.search(sentence) and not _HIM.search(sentence):
        return sentence
    for pat, rep in _VERB_FIXES:
        sentence = re.sub(pat, rep, sentence)
    return sentence


def masc(text: str) -> str:
    if not text:
        return text
    for pat, rep in _WORDS:
        text = re.sub(pat, rep, text)
    text = _HER.sub(_her, text)
    return "".join(_hindi(s) for s in _SENTENCE.findall(text)) or text


# Keys whose strings are someone's actual words (his reply, the player's line), never rewritten.
KEEP = {"reply", "reply_en", "said", "own_line", "line", "quote", "claimed_name", "you", "text_raw", "speech", "greet",
        "audio", "clip", "code", "id", "mood", "mood_key", "role", "lang"}


def masc_all(obj, key: str | None = None):
    if key in KEEP:
        return obj
    if isinstance(obj, str):
        return masc(obj)
    if isinstance(obj, list):
        return [masc_all(x, key) for x in obj]
    if isinstance(obj, dict):
        return {k: masc_all(v, k) for k, v in obj.items()}
    return obj
