# Hang Up — Solution pitch

*Gnani AI Internship Challenge · [Play](https://play-hangup.onrender.com) · [PDF](docs/Hang-Up-Pitch.pdf)*

Phone scams in India rarely rely on technology. They rely on a script: authority, urgency, isolation, then one small request for the code on your phone. **Hang Up is a voice game that lets people rehearse that script from the other side, so they recognise it in time.**

## The problem
Scam awareness is taught after the fact, as warnings, posters and news stories. Being told a pattern exists is weak protection when a confident voice is on the line and the clock is running. The people most targeted, often older relatives, have rarely heard the script before it is used on them.

## The insight
Psychology calls the best defence *inoculation*: people resist manipulation better after experiencing a weakened version of it. A game can deliver that dose safely, through voice, the same channel the real scam uses.

## The solution
You play the scam caller. On the other end is a grandmother who listens, reasons and answers in her own voice. You speak out loud, in Hindi or English.

- **Read the person.** Every call is someone new: a chatty Dadi, Pinky Didi who checks you online, Dadaji who wants a reference number. Situation, temperament and scenario change, so there is no answer to memorise.
- **Mistakes have consequences.** Push too hard and she grows suspicious; ease off and she settles. A coach names the tactic you just used, and what a real target should do about it.
- **Learn both sides.** Each tactic you use comes with its real-world counter: verify independently, slow down, tell someone.

> Win, and the four digits she reads out are **1 · 9 · 3 · 0**, India's cyber-fraud helpline. Then the game calls *you*, using your own lines. All you have to do is hang up.

## Built on Gnani AI
- **Prisma** streams speech-to-text, so you really talk and she can cut you off mid-sentence.
- **Timbre** gives every character a distinct voice (Dadi, Pinky, Dadaji, the mirror caller).
- An LLM writes her replies; a deterministic engine owns the rules, scoring and outcomes.

## Safety and reach
- No audio or transcripts stored; long numbers are masked before any text leaves the server.
- Runs in a phone browser, no install, about three minutes a call. Shareable challenge links and a daily call.
- A real-help button is always one tap away: call **1930** or report at cybercrime.gov.in.

## Why it matters
The goal isn't to teach people how scams work. It's to make the pattern familiar enough that, when it arrives for real, it is recognised before the code is read out.
