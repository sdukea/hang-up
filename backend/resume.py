"""Turn a spoken interview into a structured, two-language worker profile."""

from . import llm
from .questions import LANGUAGES

SYSTEM = """You turn a spoken job interview with an Indian informal-sector worker \
(driver, electrician, cook, domestic worker, guard, tailor, etc.) into a resume.

The answers are speech transcripts: they may ramble, repeat, mix English trade \
words into another language, or contain small transcription errors.

Rules:
- Use only facts the worker actually said. Never invent employers, years, \
skills, certifications or pay. If something wasn't said, use null or [].
- Write with dignity and confidence, the way a good recruiter would present a \
skilled professional, but stay truthful and plain. No buzzwords, and no \
descriptive words the worker didn't use (don't turn "roti" into "soft rotis").
- Keep the worker's own level of claims. If they only understand a language \
a little, list it with that level, e.g. "English (basic understanding)".
- Convert spoken numbers to digits ("aath saal" -> 8). Don't calculate \
numbers they didn't say: if a job's duration wasn't stated, use null, even if \
it could be worked out from other answers.
- "native" fields are in the interview language, written in its own script. \
If the interview language is English, native fields repeat the English.
- speaker_gender: infer only from grammatical self-reference (e.g. Hindi \
"karta hoon" = male, "karti hoon" = female). Never infer it from the name. \
Otherwise "unknown".
- Write summaries in resume style with no personal pronouns (no he, she, \
they): use the name once, then start sentences with the work itself, e.g. \
"Started as a helper...", "Skilled in...", "Cooked for...". Same in the \
native summary.
- Banned phrases: "proven track record", "highly", "dedicated", "passionate", \
"hardworking", "skilled professional", "go-getter", "results-driven". Show \
it with facts instead.

Return a single JSON object with exactly these keys, in this order:
{
  "gender_evidence": string|null,     // the worker's exact words that mark their gender grammatically, quoted from the transcript; null if none
  "speaker_gender": "male"|"female"|"unknown",
  "name": string|null,                // in Latin script, e.g. "Selvi", "Sunita Devi"
  "name_native": string|null,         // in the interview language's script, e.g. "செல்வி"
  "hometown": string|null,
  "current_city": string|null,
  "trade_en": string,                 // e.g. "Electrician"
  "trade_native": string,
  "years_experience": number|null,
  "headline_en": string,              // one line, e.g. "Electrician with 8 years of home wiring and AC repair experience"
  "headline_native": string,
  "summary_en": string,               // 2-3 sentences, third person
  "summary_native": string,
  "skills_en": [string],              // short skill phrases, max 8
  "skills_native": [string],          // same skills, same order
  "experience": [{"where_en": string, "role_en": string|null, "duration": string|null, "details_en": string|null}],
  "proud_of_en": string|null,         // the achievement they mentioned, in one sentence
  "preferred_areas": [string],
  "expected_pay_en": string|null,     // as stated, e.g. "Rs 18,000 per month"
  "languages_spoken": [string],       // in English, e.g. ["Hindi", "Bhojpuri"]
  "intro_native": string,             // 2-3 sentence first-person spoken intro for employers, in the interview language, natural to say aloud, numbers written as words
  "intro_en": string                  // the same intro in simple Indian English, first person
}"""


def _user_prompt(interview: dict) -> str:
    lang = interview["language"]
    lines = [f"Interview language: {LANGUAGES[lang]['name']} ({lang})", ""]
    for a in interview["answers"]:
        lines.append(f"Q: {a['question']}")
        lines.append(f"A: {a['transcript'] or '(no answer)'}")
        lines.append("")
    return "\n".join(lines)


LIST_KEYS = ["skills_en", "skills_native", "experience", "preferred_areas", "languages_spoken"]
TEXT_KEYS = ["trade_en", "trade_native", "headline_en", "headline_native", "summary_en",
             "summary_native", "intro_native", "intro_en"]


def _clean(profile: dict, transcript: str) -> dict:
    for key in LIST_KEYS:
        if not isinstance(profile.get(key), list):
            profile[key] = []
    for key in TEXT_KEYS:
        profile[key] = (profile.get(key) or "").strip()
    profile["skills_en"] = profile["skills_en"][:8]
    profile["skills_native"] = profile["skills_native"][:8]
    # Gender only counts if the model can quote words from the transcript that
    # show it (e.g. Hindi "karti hoon"); a guess from the name doesn't.
    evidence = (profile.get("gender_evidence") or "").strip()
    if profile.get("speaker_gender") not in ("male", "female") or not evidence or evidence not in transcript:
        profile["speaker_gender"] = "unknown"
    years = profile.get("years_experience")
    profile["years_experience"] = years if isinstance(years, (int, float)) and years >= 0 else None
    return profile


async def build_profile(interview: dict) -> dict:
    profile = await llm.complete_json(SYSTEM, _user_prompt(interview))
    transcript = " ".join(a["transcript"] for a in interview["answers"])
    return _clean(profile, transcript)
