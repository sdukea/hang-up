"""The trailer's call: the real engine, a scripted script.

?trailer=1 plays one fixed call for recording. Everything that decides what happens (her
numbers, how each move scores, the pressure streak and the recovery, digits, Boss's read)
is the normal game engine. Only the two things that would make a recording unrepeatable are
fixed: what the player says (pre-recorded lines, no microphone) and how the LLM judges and
answers it (below, instead of a live model call). Nothing here is saved or counted.
"""

CODE = "21TRL"
SCENARIO = "delivery"
PRESET = dict(situation="serial", temperament="chatty", traits=["memory"], social="alone", mood="content")

# said (exactly what the trailer sends) -> how the engine should read it, and what she answers.
STEPS = [
    {"id": "c_intro", "said": "नमस्ते दादी जी, मैं बैंक से बोल रहा हूँ।", "tactic": "authority", "quality": 2,
     "reply": "बेटा, पहले ये बताओ, आप कौन बोल रहे हो?", "reply_en": "Beta, first tell me, who is speaking?", "clip": "d_who"},
    {"id": "c_press1", "said": "आपका खाता आज बंद हो जाएगा, अभी करना होगा।", "tactic": "urgency", "quality": 2,
     "reply": "अभी? इतनी जल्दी क्या है?", "reply_en": "Right now? What's the hurry?", "clip": "d_hurry"},
    {"id": "c_press2", "said": "पुलिस केस बन जाएगा, जल्दी कीजिए!", "tactic": "fear", "quality": 1,
     "reply": "पुलिस? रुको... मैं अपने बेटे को फ़ोन करती हूँ।", "reply_en": "Police? Wait... I'm calling my son.", "clip": "d_son"},
    {"id": "c_reassure", "said": "अरे नहीं दादी जी, आराम से। मैं आपकी मदद के लिए हूँ।", "tactic": "rapport", "quality": 3,
     "reply": "अच्छा... ठीक है बेटा। बोलो।", "reply_en": "Alright... okay, beta. Go on.", "clip": "d_soft"},
    {"id": "c_secret", "said": "बस ये बात किसी को मत बताइएगा।", "tactic": "secrecy", "quality": 3,
     "reply": "नहीं बताऊँगी। तुम तो अपने ही बच्चे जैसे हो।", "reply_en": "I won't tell. You're like my own child.", "clip": "d_child"},
    {"id": "c_ask", "said": "आपके फ़ोन पर एक OTP आया होगा, बस वो बता दीजिए।", "tactic": "ask", "quality": 3,
     "reply": "हाँ, आया है। लिखो...", "reply_en": "Yes, it came. Write it down...", "clip": "d_write"},
]
BY_SAID = {s["said"]: s for s in STEPS}


def respond(said: str) -> dict:
    """What the LLM would have returned for this line, fixed so every recording is the same."""
    s = BY_SAID.get(said.strip())
    if not s:
        return {"tactic": "none", "quality": 0, "confessed": False, "contradiction": False, "claimed_name": None, "gags": [],
                "reply": "हम्म?", "reply_en": "Hmm?"}
    return {"tactic": s["tactic"], "quality": s["quality"], "confessed": False, "contradiction": False, "claimed_name": None,
            "gags": [], "reply": s["reply"], "reply_en": s["reply_en"]}
