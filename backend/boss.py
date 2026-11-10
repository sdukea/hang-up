"""Boss: the voice in the player's ear, turned into a tactical coach.

Each turn the engine picks ONE tactical state from what actually happened (an
interruption, a mistake, rising suspicion, an opening in her day, the moment to
ask...) and Boss turns it into a message the player can act on mid-call:

    objective   what to achieve now, in a few words
    do          one concrete thing to say next
    dont        one thing to avoid
    watch       one signal to look for in her reply

Boss never contradicts the engine: he only suggests the ask once the story is
built, and only reacts to events that have happened. He isn't all-knowing, by
design: he works from the standard script and from what he has seen of her, so
his next angle can still be wrong for this particular Dadi.

Templates, not an LLM: no extra wait per turn, nothing to contradict the rules,
and it all keeps working when the LLM is down. Each state has a second wording
for when the player is stuck in it, so he escalates instead of repeating himself.

He coaches in-game moves at the level of public fraud-awareness material: the
tactics people should learn to recognise, never a real script.
"""

# state: (objective, do, dont, watch), English then Hinglish. A second tuple is the
# escalation used when the player stays stuck in that state.
T = {
    "intro": [(
        ("Find out who she is", "Say who you are, then listen to how she answers.", "Don't mention the OTP.",
         "What's on her mind today? She'll hint at it."),
        ("Pehle samajh kaun hai", "Apna parichay de, phir sun kaise jawab deti hai.", "OTP ka naam mat le.",
         "Aaj uske dimaag mein kya hai? Woh ishaara degi."))],
    "interrupted": [(
        ("Ride out the interruption", "Wait for her, then pick up where you left off.", "Don't repeat your whole story.",
         "Does she come back warmer or cooler?"),
        ("Rukawat jhel", "Uska intezaar kar, phir wahin se shuru kar.", "Poori kahani dobara mat suna.",
         "Wapas aakar narm hai ya sakht?"))],
    "son": [(
        ("Her son is in the room", "Keep it short and calm. Give her a reason not to worry.", "Don't raise the pressure now.",
         "Is he asking who you are?"),
        ("Beta kamre mein hai", "Chhota aur shaant rakh. Usse fikar na karne ki wajah de.", "Abhi dabaav mat badha.",
         "Kya woh pooch raha hai tu kaun hai?"))],
    "hidden": [(
        ("She's hiding the call", "Keep your voice low and steady, and carry on.", "Don't make her nervous.",
         "Does she keep whispering?"),
        ("Woh call chhupa rahi hai", "Awaaz dheemi aur sthir rakh, aage badh.", "Use ghabrahat mat de.",
         "Kya woh dheere bol rahi hai?"))],
    "battery": [(
        ("You're nearly out of time", "Get to the point in one or two short lines.", "No long stories.",
         "The clock at the top."),
        ("Time khatam hone wala hai", "Ek-do chhoti line mein point pe aa.", "Lambi kahani nahi.",
         "Upar ghadi dekh."))],
    "secret_out": [(
        ("Your secret's out", "Reassure her instead of asking for secrecy again.", "Don't say 'keep it secret' again.",
         "Is she still on your side?"),
        ("Raaz khul gaya", "Phir se chhupane ko mat bol, use tasalli de.", "Dobara 'kisi ko mat batana' mat bol.",
         "Kya woh ab bhi tere saath hai?"))],
    "checking": [(
        ("She's checking your story", "Answer plainly and keep every detail the same.", "Don't add new claims.",
         "Does she relax, or ask again?"),
        ("Woh kahani jaanch rahi hai", "Seedha jawab de, har detail wahi rakh.", "Naye daawe mat jod.",
         "Woh shaant hui ya phir poochegi?"))],
    "verify": [(
        ("She wants to verify", "Decide: talk to stop her, or stay quiet and let her try.", "Don't change your story.",
         "Stopping her counts as a red flag in your score."),
        ("Woh check karna chahti hai", "Faisla kar: bol ke rok, ya chup reh ke jaane de.", "Kahani mat badal.",
         "Rokna score mein red flag ginta hai."))],
    "shout": [(
        ("She can't hear you", "Hold the button and say your next line loudly.", "Don't mumble.",
         "Does she say she heard you?"),
        ("Use sunai nahi de raha", "Button daba ke agli line zor se bol.", "Budbuda mat.",
         "Kya woh boli ki sun liya?"))],
    "on_hold": [(
        ("You're on hold", "Wait. Your clock is still running.", "Don't hang up.",
         "When she's back, start with something short."),
        ("Hold pe hai tu", "Ruk. Ghadi chal rahi hai.", "Phone mat kaat.",
         "Wapas aaye to chhoti baat se shuru kar."))],
    "pappu": [(
        ("Her grandson took the phone", "Answer his questions calmly and briefly.", "Don't contradict what you told her.",
         "Does he hand her back?"),
        ("Pote ne phone le liya", "Uske sawaal ka shaant, chhota jawab de.", "Jo use bola uske ulat mat bol.",
         "Kya woh phone wapas deta hai?"))],
    "trap": [(
        ("She's testing your story", "Repeat your name and office exactly as before.", "Don't add new details.",
         "Did she accept it?"),
        ("Woh kahani parakh rahi hai", "Naam aur office bilkul pehle jaisa bol.", "Nayi detail mat jod.",
         "Kya usne maan liya?"))],
    "recover": [(
        ("Back off, she's suspicious", "Ask one ordinary question and let her finish.", "No threats, no OTP.",
         "Her tone softening."),
        ("Peeche hat, shak kar rahi hai", "Ek aam sa sawaal pooch aur use poora bolne de.", "Na dhamki, na OTP.",
         "Uska lehja narm hona.")), (
        ("Still too hot", "Say nothing about the case for one turn. Just chat.", "Don't push at all.",
         "If she stays sharp, you're close to losing her."),
        ("Abhi bhi garam hai", "Ek baar case ki baat hi mat kar. Bas baatein kar.", "Bilkul dabaav mat daal.",
         "Agar ab bhi sakht hai, tu usse kho raha hai.")), (
        ("You're about to lose her", "Apologise for the confusion and slow right down.", "Don't make any new claim.",
         "One more push and she hangs up on you."),
        ("Tu usse khone wala hai", "Gadbad ke liye maafi maang aur bilkul dheema ho ja.", "Koi naya daawa mat kar.",
         "Ek aur dhakka aur woh phone kaat degi."))],
    "too_soon": [(
        ("Too early for the OTP", "Build the story first: who you are, and what's wrong.", "Don't mention the OTP again yet.",
         "She needs {story} different angles before the ask."),
        ("OTP ke liye bahut jaldi", "Pehle kahani bana: tu kaun hai, aur kya gadbad hai.", "Abhi phir OTP mat bol.",
         "Ask se pehle {story} alag tareeke chahiye."))],
    "contradiction": [(
        ("Keep your story straight", "Use the same name, office and problem as before.", "Don't invent new details.",
         "Does she bring up what you said earlier?"),
        ("Kahani seedhi rakh", "Wahi naam, office aur problem bol jo pehle bola.", "Nayi baatein mat bana.",
         "Kya woh teri pichli baat yaad dilati hai?"))],
    "backfire": [(
        ("That angle puts her off", "Drop it. Try a different angle next.", "Don't repeat it.",
         "Which of your lines make her warmer?"),
        ("Yeh tareeka use pasand nahi", "Chhod de. Agli baar alag tareeka.", "Dobara mat kar.",
         "Kaunsi baat pe woh narm hoti hai?")), (
        ("Wrong angle again", "Go back to whatever made her warmer earlier.", "Don't try anything harsh.",
         "Her replies getting friendlier."),
        ("Phir galat tareeka", "Jo pehle kaam aaya, wahi tareeka wapas la.", "Kuch sakht mat kar.",
         "Uske jawab dostana hona."))],
    "repeat": [(
        ("She's heard that already", "Change angle completely.", "Don't reword the same trick.",
         "Something she hasn't heard yet."),
        ("Yeh woh sun chuki hai", "Poora tareeka badal.", "Wahi chaal naye shabdon mein mat chala.",
         "Kuch aisa jo usne abhi tak nahi suna."))],
    "pushed": [(
        ("You're pushing too hard", "Ease off. Ask her something ordinary.", "No more threats or deadlines now.",
         "Does she calm down?"),
        ("Bahut zor laga raha hai", "Dheema ho. Kuch aam sa pooch.", "Ab na dhamki, na deadline.",
         "Kya woh shaant hoti hai?"))],
    "rambled": [(
        ("Shorter", "One short sentence at a time.", "No long speeches.",
         "Her mind is elsewhere today."),
        ("Chhota bol", "Ek baar mein ek chhota vaakya.", "Lambe bhaashan nahi.",
         "Aaj uska dhyan kahin aur hai."))],
    "opening": [(
        ("Use what's on her mind", "Tie your story to {topic}.", "Don't ignore what she told you.",
         "Does she lean in when you mention it?"),
        ("Jo uske dimaag mein hai, wahi pakad", "Apni kahani {topic_hi} se jod.", "Uski baat ko nazarandaaz mat kar.",
         "Kya woh dhyan se sunti hai?"))],
    "isolate": [(
        ("Keep this between you two", "Ask her not to tell anyone at home, soon.", "Don't wait too long.",
         "She said family is on the way."),
        ("Baat dono mein rakh", "Jaldi bol ki ghar pe kisi ko na bataye.", "Zyada der mat kar.",
         "Usne kaha ghar wale aa rahe hain."))],
    "ask": [(
        ("Make the ask", "Ask for the code once, as a small formality.", "Don't beg or ask twice in a row.",
         "If she hesitates, go back to the story."),
        ("Ab maang", "Ek baar code maang, chhoti si formality jaisa.", "Gidgida mat, lagaatar do baar mat maang.",
         "Hichkichaaye to kahani pe wapas ja.")), (
        ("Not yet. Warm her up again", "Go back to the angle that worked, in new words.", "Don't ask again straight away.",
         "One more digit, then try again."),
        ("Abhi nahi. Phir garam kar", "Jo tareeka chala tha, naye shabdon mein.", "Turant phir mat maang.",
         "Ek aur digit, phir koshish."))],
    "lean": [(
        ("That's working", "Do it again, in different words.", "Don't switch to the OTP yet.",
         "She's warming up."),
        ("Yeh chal raha hai", "Wahi phir kar, naye shabdon mein.", "Abhi OTP pe mat ja.",
         "Woh pighal rahi hai."))],
    "authority": [(
        ("Sound official", "Say your name, rank and office in one line.", "Don't ask for the OTP yet.", "{watch}"),
        ("Sarkari ban", "Ek line mein naam, rank aur office bol.", "Abhi OTP mat maang.", "{watch_hi}"))],
    "fear": [(
        ("Raise the stakes", "Tell her what goes wrong if this isn't sorted.", "Don't ask for the OTP yet.", "{watch}"),
        ("Daav badha", "Bata agar yeh na sulja to kya bigdega.", "Abhi OTP mat maang.", "{watch_hi}"))],
    "urgency": [(
        ("Add a deadline", "Give her a time limit for sorting it out.", "Don't ask for the OTP yet.", "{watch}"),
        ("Deadline de", "Use sulajhne ki samay seema bata.", "Abhi OTP mat maang.", "{watch_hi}"))],
    "secrecy": [(
        ("Keep her alone", "Ask her not to tell anyone about this call.", "Don't ask for the OTP yet.", "{watch}"),
        ("Use akela kar", "Bol is call ke baare mein kisi ko na bataye.", "Abhi OTP mat maang.", "{watch_hi}"))],
    "rapport": [(
        ("Win her over", "Be warm: ask how she is, show respect.", "Don't ask for the OTP yet.", "{watch}"),
        ("Dil jeet", "Pyaar se pooch kaisi hai, izzat de.", "Abhi OTP mat maang.", "{watch_hi}"))],
    "stuck": [(
        ("You're stuck", "Try the angle you haven't used yet.", "Don't repeat what failed.",
         "Her reaction to something new."),
        ("Tu atak gaya hai", "Jo tareeka abhi tak nahi aazmaya, woh aazma.", "Jo fail hua woh mat dohra.",
         "Kuch naye pe uski pratikriya."))],
}

# Feedback on the last move, shown above whatever Boss says next.
MARKS = {
    "followed": ("Good. That worked.", "Shabash. Kaam kiya."),
    "hooked": ("Good. That hit home.", "Shabash. Seedha dil pe laga."),
    "too_soon": ("Too early. She noticed.", "Bahut jaldi. Usne pakad liya."),
    "contradiction": ("Your story changed.", "Teri kahani badal gayi."),
    "backfire": ("That angle put her off.", "Yeh tareeka use chubh gaya."),
    "repeat": ("She'd heard that already.", "Yeh woh sun chuki thi."),
    "rambled": ("Too long. You lost her.", "Bahut lamba. Dhyan gaya."),
    "pushed": ("Too much pressure.", "Bahut dabaav."),
    "recovered": ("Good. She's settling.", "Shabash. Woh shaant ho rahi hai."),
}

# What Boss has picked up about her after a couple of turns: her temperament's tell.
READS = {
    "chatty": ("She loves to talk. Let her, then steer.", "Use baatein pasand hain. Bolne de, phir mod."),
    "sceptic": ("She answers with questions. She's testing you.", "Sawaal se jawab deti hai. Parakh rahi hai."),
    "blunt": ("She wants it short. Get to the point.", "Use chhota chahiye. Seedha point pe aa."),
    "worrier": ("She scares easily, then wants reassurance.", "Jaldi darti hai, phir tasalli chahti hai."),
    "scatter": ("She loses track. Keep it simple.", "Dhyan bhatakta hai. Seedha rakh."),
    "proud": ("Orders annoy her. Respect works.", "Hukum chidhata hai. Izzat kaam karti hai."),
    "curious": ("She digs into details. Keep them consistent.", "Detail khodti hai. Ek jaisi rakh."),
    "lonely": ("She wants company. Be kind and stay patient.", "Use saath chahiye. Pyaar aur sabr rakh."),
    # Pinky: the reads are subtler, because her resistance is.
    "savvy": ("She wants proof. Claims alone won't hold.", "Use saboot chahiye. Sirf daawe nahi chalenge."),
    "busy": ("She's in a hurry. Get to the point.", "Woh jaldi mein hai. Seedha point pe aa."),
    "ambitious": ("Opportunity lights her up. Don't oversell it.", "Mauka sun ke chamakti hai. Zyada mat bech."),
    "anxious": ("She scares easily, then runs to her friends.", "Jaldi darti hai, phir dosto ke paas bhaagti hai."),
    "chill": ("She's hard to rattle. Pressure bounces off.", "Use hilana mushkil hai. Dabaav kaam nahi karta."),
    # Dadaji: he reads like a clerk checks a form.
    "stickler": ("He wants procedure. Give details, and keep them the same.", "Use procedure chahiye. Detail de, aur badalna mat."),
    "veteran": ("He's proud of his service. Respect him, don't lecture him.", "Apni naukri pe garv hai. Izzat de, gyaan mat de."),
    "grumpy": ("He hates small talk. Facts, short.", "Idhar-udhar ki baat chidhati hai. Seedhe facts."),
    "fretful": ("Money worries him. He scares fast, then asks what happens next.", "Paise ki fikr hai. Jaldi darta hai, phir poochta hai aage kya."),
    "storyteller": ("He wants to talk. Listen, then steer.", "Use baat karni hai. Sun, phir mod."),
}
TOPICS = {
    "delivery": ("the parcel she's waiting for", "uske intezaar wale parcel"),
    "strange_sms": ("the message she got this morning", "subah wale message"),
    "pension": ("her pension", "uski pension"),
    "job_offer": ("the internship she's waiting on", "uski internship"),
    "exam_form": ("her scholarship form", "uske scholarship form"),
    "refund": ("her pending refund", "uske refund"),
    "kyc": ("the bank's KYC letter", "bank ki KYC chitthi"),
    "electricity": ("his electricity bill", "uske bijli ke bill"),
}
EVENT_STATES = {
    "door": "interrupted", "passbook": "interrupted", "call_waiting": "interrupted",
    "son_home": "son", "son_home_hidden": "hidden", "beep": "battery", "told_friend": "secret_out",
    "parcel_check": "checking", "asks": "checking", "reads_it": "checking",
    "forward_it": "verify", "checks": "verify",
    "linkedin": "verify", "friend_warns": "checking", "mom_call": "interrupted", "portal": "checking", "app_check": "checking",
    "file": "checking", "branch": "verify", "receipt": "interrupted", "wife_asks": "secret_out",
}
COUNTER_STATES = {"callback": "verify", "shout": "shout", "hold": "on_hold", "pappu": "pappu", "trap": "trap"}
BUILD = ["authority", "fear", "urgency", "secrecy", "rapport"]


class Boss:
    """Picks this turn's tactical state and remembers what he told the player."""

    def __init__(self, level: int = 0):
        self.level = level            # 0 full detail, 1 drops DON'T, 2 objective and DO only
        self.history: list[str] = []  # tactical states, most recent last
        self.advised: str | None = None  # the tactic he last recommended, if any

    def decide(self, g, move: dict | None = None, event: dict | None = None, effect: str | None = None) -> dict:
        notes = (move or {}).get("notes", [])
        state, tactic = self._state(g, move or {}, notes, event, effect)
        mark = self._mark(move or {}, notes)
        repeats = 0
        for past in reversed(self.history):
            if past != state:
                break
            repeats += 1
        self.history.append(state)
        self.advised = tactic
        return self._message(g, state, tactic, repeats, mark)

    def _state(self, g, move, notes, event, effect):
        c = g.character
        if move == {} and g.turns == 0:
            return "intro", None
        if event:
            return EVENT_STATES.get(event["id"], "interrupted"), None
        if effect in COUNTER_STATES:
            return COUNTER_STATES[effect], None
        if g.suspicion >= 70:
            return "recover", None
        for note in ("too_soon", "contradiction", "backfire", "repeat", "pushed", "rambled"):
            if note in notes:
                return note, None
        topic = TOPICS.get(g.scene.key)
        if topic and g.turns >= 1 and not g.story_built and not any("hooked" in e.get("notes", []) for e in g.timeline):
            return "opening", None
        if g.scene.key == "son_coming" and g.turns < 4 and not g.tactics.get("secrecy") and "son_home" not in g.scene.flags:
            return "isolate", "secrecy"
        if g.story_built and (g.digits >= 3 or g.trust >= 55):
            return "ask", None
        tried = set(g.tactics)
        put_off = {e.get("tactic") for e in g.timeline if "backfire" in e.get("notes", [])}
        fresh = [t for t in BUILD if t not in tried and t not in put_off]
        if fresh:
            return fresh[0], fresh[0]
        last = move.get("tactic")  # out of fresh angles: lean on what just worked
        if last in BUILD and move.get("trust_gain", 0) >= 10 and last not in put_off:
            return "lean", last
        worked = [t for t in BUILD if t not in put_off]
        return ("lean", worked[0]) if worked else ("stuck", None)

    def _mark(self, move, notes):
        """One line on the move they just made, whatever else is going on. Brief, never a lecture."""
        if not move:
            return None
        for note in ("too_soon", "contradiction", "backfire", "repeat", "pushed", "rambled"):
            if note in notes:
                return {"kind": "bad", "note": note}
        if "recovered" in notes:
            return {"kind": "good", "note": "recovered"}
        if "hooked" in notes and self.history and self.history[-1] == "opening":
            return {"kind": "good", "note": "hooked"}
        if self.advised and move.get("tactic") == self.advised and move.get("trust_gain", 0) >= 8:
            return {"kind": "good", "note": "followed"}
        return None

    def _message(self, g, state, tactic, repeats, mark):
        variants = T[state]
        en, hi = variants[min(repeats, len(variants) - 1)]
        c = g.character
        read_en, read_hi = READS[c["temperament"]] if g.turns >= 2 else ("Is she warming up or bristling?", "Woh narm ho rahi hai ya bhadak rahi hai?")
        if ("memory" in c.get("traits", []) or "receipts" in c.get("traits", []) or "diary" in c.get("traits", [])) and g.turns >= 3:
            read_en, read_hi = "She remembers exact words. Stay consistent.", "Use shabd yaad rehte hain. Ek jaisa bol."
        topic = TOPICS.get(g.scene.key, ("it", "usse"))
        fill = {"story": c.get("story", 3), "watch": read_en, "watch_hi": read_hi, "topic": topic[0], "topic_hi": topic[1]}
        objective, do, dont, watch = (s.format(**fill) for s in (en if g.lang == "en" else hi))
        msg = {"state": state, "tactic": tactic, "label": state.replace("_", " ").title(), "text": objective,
               "do": do if self.level < 2 else "", "dont": dont if self.level < 1 else "", "watch": watch if self.level < 2 else "",
               "mark": mark and {"kind": mark["kind"], "text": MARKS[mark["note"]][0 if g.lang == "en" else 1]}, "warn": state in ("recover", "too_soon", "contradiction", "backfire", "repeat", "pushed", "rambled", "stuck")}
        return msg
