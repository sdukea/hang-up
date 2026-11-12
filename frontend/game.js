// Hang Up: the call. The server holds the OTP and the rules; this file is the
// stage, the controls and the sound.

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (n) => Math.floor(Math.random() * n);
// A hung request must not hang the call.
const post = (url, body, ms = 12000) => {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), ms);
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
    signal: stop.signal,
  }).finally(() => clearTimeout(timer));
};

// Who's signed in, and their progress from the server. Guests have neither; the game works the same.
const account = { user: null, player: null };

const SHOUT_LEVEL = 0.32;      // how loud "louder!" means, on the 0-1 meter
const OTP_WORD = /\bo[\s.]*t[\s.]*p\b|[ओऑ][\s.]*ट[ीि][\s.]*प[ीि]/i;
// Safari replays media requests and needs byte ranges, so it waits for the whole reply.
const STREAMS_AUDIO = !/iP(hone|ad|od)|^((?!chrome|android).)*safari/i.test(navigator.userAgent);
const CLIP_STALL_MS = 10000;   // a clip that makes no progress for this long has failed
// [pop title, pop note, Boss in Hinglish, Boss in English]
const COUNTER_NOTES = {
  hold: ["DADI PUTS YOU ON HOLD", "Real defence: slow them down. Scams need you rushed.", "Hold pe daal diya! Line mat kaat. Asli scammers ghanton line pe rakhte hain, isi liye ghar waalon ko pata nahi chalta.", "She put you on hold! Don't hang up. Real scammers keep people on the line for hours, so the family never finds out."],
  shout: ["DADI CAN'T HEAR YOU", "Real defence: make them repeat. Scripts fall apart.", "Zor se bol! Button dabake chilla, warna shak badhega.", "Louder! Hold the button and shout, or she gets suspicious."],
  callback: ["DADI WILL CALL THE THANA", "Real defence: hang up and check it yourself.", "Thane phone karegi! Rokega to red flag lagega, asli scammers yahi karte hain. Jaane dega to time aur shak dono badhenge. Tera faisla.", "She's calling the police station! Stop her and it's a red flag, because that's what real scammers do. Let her and it costs time and suspicion. Your call."],
  pappu: ["DADI GETS PAPPU", "Real defence: bring in family. One call can end a scam.", "Khatra! Ghar waale aa gaye. Isi liye scammers bolte hain 'kisi ko mat batana'.", "Danger! Family's here. That's why scammers say 'tell nobody'."],
  trap: ["SHE'S TESTING YOUR STORY", "Real defence: make them repeat details. Liars slip.", "Yaad hai kya bola tha? Bilkul wahi bol, warna pakda jayega.", "Remember what you said? Say exactly that, or you're caught."],
};
const GAG_LABELS = {
  knee: "🦵 Ghutna", food: "🍛 Khana khaya?", shaadi: "💍 Shaadi kab?",
  chashma: "👓 Chashma lost", pappu: "🧑‍💻 Pappu", scooter: "🛵 The scooter",
};
const OUTCOME_STAMP = { busted: "BUSTED", timeout: "TIME UP", hung_up: "YOU FLED", cracked: "CRACKED", reformed: "YOU STOPPED" };
const NOT_ANSWERING = "Nobody's answering. Try again in a minute.";
const CUTOFF_HI = [
  "अरे अरे अरे, रुक! अभी नाम भी ढंग से नहीं बताया, और सीधे OTP? तू कैसा अफ़सर है रे?",
  "OTP? OTP? बेटा, पहली मुलाक़ात में कोई OTP माँगता है क्या? पहले बता, तू है कौन?",
  "चुप! बीच में मत बोल। यही OTP वाली बात शर्मा जी को भी किसी ने बोली थी।",
];
const CUTOFF_DIDI_HI = [
  "Excuse me? Intro तक नहीं दिया, और सीधा OTP? Bro, seriously?",
  "OTP? पहली line में? ये तो literally scam वाली reel है।",
  "Stop. बीच में मत बोलो। यही OTP वाली बात मेरी friend को भी किसी ने बोली थी।",
];
const CUTOFF_DIDI_EN = [
  "Excuse me? You didn't even introduce yourself, and straight to OTP? Bro, seriously?",
  "OTP? In the first line? This is literally the scam reel.",
  "Stop. Don't interrupt. Someone said this exact OTP thing to my friend too.",
];
// Pinky's versions of counter-move pop-ups, where hers differ.
const ROLE_NOTES = {
  didi: { callback: ["PINKY IS LOOKING YOU UP", "Real defence: check the number yourself, on the official site."] },
  dadaji: { callback: ["DADAJI WILL RING THE BRANCH", "Real defence: hang up and call the number on your passbook."],
            trap: ["HE'S READING FROM HIS DIARY", "Real defence: write down what they claim. Liars slip."] },
};
const ROLE_NAMES = { didi: "Pinky Didi", dadaji: "Dadaji" };
const CUTOFF_DADAJI_HI = [
  "रुको। नाम नहीं, department नहीं, और सीधा OTP? ये कौन सी procedure है?",
  "OTP? पैंतीस साल नौकरी की, पहली बात में कोई OTP नहीं माँगता था।",
  "बीच में मत बोलो। पहले reference number, फिर बाक़ी बात।",
];
const CUTOFF_DADAJI_EN = [
  "Stop. No name, no department, and straight to OTP? What procedure is this?",
  "OTP? Thirty-five years in service, and nobody ever asked for one in the first breath.",
  "Don't interrupt. Reference number first, then we talk.",
];
const CUTOFF_EN = [
  "Wait, wait! You haven't even told me your name, and you want my OTP? What kind of officer are you?",
  "OTP? OTP? Who asks for an OTP on the first meeting, beta? First tell me who you are.",
  "Quiet! Don't interrupt me. Someone said this same OTP thing to Sharma ji too.",
];
// The tactics, boiled down to what a player should remember.
const SCRIPT_PARTS = [
  { label: "Authority", tactics: ["authority"], line: "A big title, so you don't ask questions." },
  { label: "Pressure", tactics: ["fear", "urgency", "rapport"], line: "Fear, a deadline, then fake kindness, so you can't think." },
  { label: "Isolation", tactics: ["secrecy"], line: "\"Tell nobody\", because one relative can end the scam." },
  { label: "The OTP", tactics: ["ask"], line: "It all builds to this. Nobody genuine ever asks for it." },
];
const TACTIC_NAMES = { authority: "Fake Authority", fear: "Fear", urgency: "Urgency", secrecy: "Isolation", rapport: "Fake Kindness" };

const PARTS = {
  progress: "Digits", control: "Calm", story: "Story held", speed: "Speed", no_boss: "No Boss",
  red_flags: "Red flags", knowledge: "Red flags spotted",
};

const state = {
  lang: chosenLang(),   // "hi" or "en": what Dadi speaks and what Prisma listens for
  mode: "free",         // "free", "daily" (today's Dadi, ranked) or "challenge" (a friend's code)
  code: challengeCode(),
  daily: null,          // today's Dadi, from the server
  graded: null,         // the final score, once the questions are answered
  game: null,
  quizBefore: null,
  secondsLeft: 0,
  timerId: null,
  ws: null,
  over: false,
  busy: false,          // a reply is being worked out
  speaking: false,
  holding: false,
  lockedUntil: 0,       // Dadi has put them on hold
  shoutTries: 0,        // she's demanding they speak up
  shoutPending: false,
  callbackTimer: null,
  callbackPending: false,
  pappuHere: false,
  pendingDigits: [],
  peak: 0,
  finals: [],
  partial: "",
  pendingSegments: 0,
  idleAt: 0,
  idleCount: 0,
  gags: {},
  usedFillers: [],
  storyBuilt: false,    // she'll hear an OTP ask without cutting in
  starting: false,      // a call is being set up, so a second tap does nothing
  voiceDown: false,     // no mic or the speech service is full, so typing takes over
  voiceWarned: false,   // told them Dadi's voice dropped
  listenFails: 0,       // voice socket drops in a row
  deadMicHolds: 0,      // presses where the mic sent nothing at all
  heldAt: 0,
  cutoffs: 0,
  speechRun: 0,         // lets a press interrupt whatever Dadi is saying
  report: null,
};

// ---------- Dadi art ----------

const art = $("dadi-art");
document.querySelectorAll("[data-dadi]").forEach((el) => el.append(art.content.cloneNode(true)));

// Whoever picked up: their face goes everywhere the call shows one. The title screen stays Dadi.
function setArt(role) {
  const tpl = $(`${role}-art`) || $("dadi-art");
  document.querySelectorAll("#s-ring [data-dadi], #s-game [data-dadi], #s-end [data-dadi]").forEach((el) => el.replaceChildren(tpl.content.cloneNode(true)));
}
const who = () => (state.game && state.game.title) || "Dadi";
const WHO = () => who().toUpperCase();
const isPinky = () => Boolean(state.game && state.game.role === "didi");
const isDadaji = () => Boolean(state.game && state.game.role === "dadaji");

// He, not she: the page's own words during Dadaji's call. The same rules as backend/gender.py; keep them in step.
// Only the call screens change, and the original text comes back for the next Dadi or Pinky.
const G_VERBS = new Set(`let make help keep leave get give tell ask rush lose push scare calm hear watch catch convince trust call
annoy bore impress rattle frighten soften warm win wake stop flatter pressure isolate reassure remind interrupt
corner fool trick reach beat crack hand show put stuck caught called bring brought made let's lets lost
told asked rushed pushed scared calmed heard watched trusted annoyed bored impressed rattled frightened softened
warmed woke stopped flattered pressured isolated reassured reminded interrupted fooled tricked reached beat cracked
letting stopping making helping giving telling asking keeping leaving rushing pushing scaring calming losing`.split(/\s+/));
const G_NOUNS = new Set(`friend friends family son daughter grandson husband wife pension phone passbook battery trust suspicion mind story
guard replies reply tone own doubts attention hands name parcel savings diary file bank account money day life`.split(/\s+/));
const G_FOLLOW = new Set(`to into up down off out in on back again a an the that this what why how about with for and or but from
before after when if more less feel think know too over so just any some at by as than while until yet still now
here there enough alone going it something anything nothing someone anyone your you all first once twice properly
quickly anymore either is was will would can could`.split(/\s+/));
const DEV = "\u0900-\u0963\u0966-\u097F";
const G_WORDS = [
  [/hiding the call from him\b/g, "hiding the call from his son"],
  [/\bDADI\b/g, "DADAJI"], [/\bDadi\b/g, "Dadaji"], [new RegExp(`दादी(?!जी)`, "g"), "दादाजी"],
  [/\bgrandmothers\b/g, "grandfathers"], [/\bgrandmother\b/g, "grandfather"], [/\bGrandmother\b/g, "Grandfather"],
  [/\bgrandmotherly\b/g, "grandfatherly"], [/\bgranny\b/g, "grandpa"], [/\bold woman\b/g, "old man"],
  [/\bSHE'S\b/g, "HE'S"], [/\bSHE\b/g, "HE"], [/\bShe\b/g, "He"], [/\bshe\b/g, "he"],
  [/\bherself\b/g, "himself"], [/\bHerself\b/g, "Himself"], [/\bhers\b/g, "his"],
];
const G_THINGS = /\b(ghadi|kahani|baat|police|call|aawaz|awaaz|pension|line|gaadi|cheez|galti|chaal|warning|internship|battery|ghanti|script|trick|story|zindagi|duniya|bhasha)\b|घड़ी|कहानी|बात|पुलिस|आवाज़|पेंशन|लाइन|गाड़ी|चीज़|ग़लती|चाल/i;
const G_HIM = /\b(woh|wo|vo|use|usse|usko|uski|uska)\b|वो|वह|उसे|उसको/i;
const G_HINT = new RegExp(`[${DEV}]|\\b(hai|nahi|kar|raha|rahi|woh|tu|tera|teri|mat|aur|ab|bhi|ko|se|\\w+egi|gayi|chuki)\\b`, "i");
const G_VERB_FIXES = [
  [/\brahi\b/g, "raha"], [/\bgayi\b/g, "gaya"], [/\bthi\b/g, "tha"], [/\bhui\b/g, "hua"], [/\bchuki\b/g, "chuka"],
  [/\bsakti\b/g, "sakta"], [/\bakeli\b/g, "akela"], [/\b(\w+)egi\b/g, "$1ega"],
  [/\b(\w{2,})ti\b(?=\s+(hai|hain|thi|tha|ho|nahi|nahin)\b)/g, "$1ta"],
  [/रही/g, "रहा"], [/गई/g, "गया"], [new RegExp(`(?<![${DEV}])थी(?![${DEV}])`, "g"), "था"], [/ती है/g, "ता है"],
  [new RegExp(`ेगी(?![${DEV}])`, "g"), "ेगा"],
];
function gHer(word, offset, text) {
  const end = offset + word.length;
  const after = text.slice(end).match(/^\s*([A-Za-z']+)?/);
  const nxt = ((after && after[1]) || "").toLowerCase();
  const before = text.slice(0, offset).match(/([A-Za-z']+)\W*$/);
  const prev = before ? before[1].toLowerCase() : "";
  const obj = !nxt || G_FOLLOW.has(nxt) || !/^\s*[A-Za-z]/.test(text.slice(end)) || (G_VERBS.has(prev) && !G_NOUNS.has(nxt));
  const out = obj ? "him" : "his";
  return word === word.toUpperCase() ? out.toUpperCase() : word[0] === word[0].toUpperCase() ? out[0].toUpperCase() + out.slice(1) : out;
}
function masc(text) {
  if (!text) return text;
  for (const [re, to] of G_WORDS) text = text.replace(re, to);
  text = text.replace(/\b(her|Her|HER)\b/g, (m, w, off, str) => gHer(w, off, str));
  return (text.match(/[^.!?।]+[.!?।]*/g) || [text]).map((s) => {
    if (!G_HINT.test(s) || (G_THINGS.test(s) && !G_HIM.test(s))) return s;
    for (const [re, to] of G_VERB_FIXES) s = s.replace(re, to);
    return s;
  }).join("");
}
const G_SCREENS = "#s-ring, #s-game, #s-end, #s-flip, #s-report, #pops, #leave";
const G_SKIP = "#bubble, #you-said, #flip-line, #type-input, #board-list, #b-parents, #b-parents-play, q, script, style, svg";  // the parents' note is Kamla Dadi's, whoever picked up
const gOriginal = new Map();  // text node -> its words before regendering
const gWrote = new WeakMap();  // text node -> what regendering put there, so its own edits aren't mistaken for new text
let gBusy = false;
function regender(root = document.body) {
  if (gBusy) return;
  gBusy = true;
  try {
    if (!isDadaji()) {
      for (const [node, text] of gOriginal) if (node.isConnected && node.nodeValue !== text) node.nodeValue = text;
      gOriginal.clear();
      return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!el || !el.closest(G_SCREENS) || el.closest(G_SKIP) || !/[A-Za-z\u0900-\u097F]/.test(n.nodeValue)) continue;
      const fixed = masc(n.nodeValue);
      if (fixed !== n.nodeValue) {
        if (!gOriginal.has(n)) gOriginal.set(n, n.nodeValue);
        n.nodeValue = fixed;
        gWrote.set(n, fixed);
      }
    }
  } finally {
    gBusy = false;
  }
}
new MutationObserver((records) => {
  if (gBusy || !isDadaji()) return;
  for (const r of records) {
    if (r.type === "characterData") {
      if (gWrote.get(r.target) === r.target.nodeValue) continue;  // our own edit
      gOriginal.delete(r.target);
      regender(r.target.parentElement || document.body);
    }
    else for (const n of r.addedNodes) regender(n.nodeType === 1 ? n : n.parentElement || document.body);
  }
}).observe(document.body, { childList: true, subtree: true, characterData: true });

// ---------- Sound: one context, one voice channel ----------

const audio = { ctx: null, voice: new Audio(), analyser: null, connected: false, mouthData: null };
audio.voice.preload = "auto";

function resumeAudio() {
  if (audio.ctx && audio.ctx.state !== "running") audio.ctx.resume().catch(() => {});
}

function unlockAudio() {
  if (!audio.ctx) audio.ctx = new (window.AudioContext || window.webkitAudioContext)();
  resumeAudio();
  if (!audio.mouthMoving) {
    audio.mouthMoving = true;
    requestAnimationFrame(moveMouth);
  }
  // Routed through the context, Safari can leave her silent after the mic prompt.
  // There she plays directly, and the mouth keeps time on its own.
  if (STREAMS_AUDIO && !audio.connected) {
    try {
      const source = audio.ctx.createMediaElementSource(audio.voice);
      audio.analyser = audio.ctx.createAnalyser();
      audio.analyser.fftSize = 256;
      audio.mouthData = new Uint8Array(audio.analyser.fftSize);
      source.connect(audio.analyser);
      audio.analyser.connect(audio.ctx.destination);
      audio.connected = true;
    } catch (err) {
      console.warn("Lip sync unavailable", err);
    }
  }
  // Phones only let this player speak later if it starts during a tap.
  if (!audio.primed && !state.speaking) {
    audio.primed = true;
    audio.voice.muted = true;
    audio.voice.src = "/audio/num_0.mp3";
    audio.voice.play().catch(() => {}).finally(() => {
      if (!state.speaking) audio.voice.pause();
      audio.voice.muted = false;
    });
  }
}

// Dadi's mouth follows her real voice.
function moveMouth() {
  let level = 0;
  if (!audio.voice.paused && !audio.voice.muted) {
    if (audio.analyser) {
      audio.analyser.getByteTimeDomainData(audio.mouthData);
      let sum = 0;
      for (const v of audio.mouthData) sum += (v - 128) ** 2;
      level = Math.min(1, Math.sqrt(sum / audio.mouthData.length) / 40);
    } else {
      level = 0.4 + 0.3 * Math.sin(performance.now() / 85);
    }
  }
  document.documentElement.style.setProperty("--mouth", level.toFixed(2));
  requestAnimationFrame(moveMouth);
}

// Short synthesized effects, so the whole game stays tiny on mobile data.
function tone(freq, duration, { type = "square", gain = 0.08, at = 0, slide = 0 } = {}) {
  if (!audio.ctx) return;
  const t = audio.ctx.currentTime + at;
  const osc = audio.ctx.createOscillator();
  const amp = audio.ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  if (slide) osc.frequency.exponentialRampToValueAtTime(Math.max(30, freq + slide), t + duration);
  amp.gain.setValueAtTime(gain, t);
  amp.gain.exponentialRampToValueAtTime(0.0001, t + duration);
  osc.connect(amp).connect(audio.ctx.destination);
  osc.start(t);
  osc.stop(t + duration + 0.02);
}

const sfx = {
  tap: () => tone(520, 0.07, { gain: 0.05 }),
  radio: () => { tone(1500, 0.05, { gain: 0.03 }); tone(1100, 0.06, { gain: 0.03, at: 0.07 }); },
  trick: () => { tone(660, 0.09); tone(880, 0.12, { at: 0.09 }); },
  good: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.12, { at: i * 0.08, gain: 0.09 })),
  bad: () => tone(220, 0.35, { type: "sawtooth", slide: -120, gain: 0.09 }),
  warn: () => { tone(740, 0.12, { type: "sawtooth" }); tone(740, 0.12, { type: "sawtooth", at: 0.2 }); },
  tick: () => tone(1000, 0.04, { gain: 0.04 }),
  ring() { for (let i = 0; i < 2; i++) { tone(440, 0.4, { type: "sine", at: i * 0.5, gain: 0.08 }); tone(480, 0.4, { type: "sine", at: i * 0.5, gain: 0.08 }); } },
  siren() { for (let i = 0; i < 5; i++) tone(650, 0.45, { type: "sawtooth", slide: 400, at: i * 0.5, gain: 0.05 }); },
  whistle() { tone(1900, 1.4, { type: "sawtooth", gain: 0.025, slide: 150 }); },
  holdMusic() { [392, 440, 494, 440, 392, 330, 392, 440].forEach((f, i) => tone(f, 0.32, { type: "triangle", at: i * 0.36, gain: 0.05 })); },
};

function haptic(ms) { if (navigator.vibrate) navigator.vibrate(ms); }

// Play a clip on Dadi's voice channel. A new clip or a press of the talk button cuts
// off the last one. Only the clip playing now can touch the channel, and one that
// fails or stalls gives up, so nothing ever waits on her forever.
function say(url) {
  if (audio.stop) audio.stop();
  resumeAudio();
  return new Promise((resolve) => {
    const v = audio.voice;
    let stalled;
    const finish = (failed = false) => {
      if (audio.stop !== finish) return;
      audio.stop = null;
      clearTimeout(stalled);
      v.onended = v.onerror = v.ontimeupdate = null;
      state.speaking = false;
      updateTalk();
      if (failed) voiceTrouble();
      resolve();
    };
    const watch = () => {
      clearTimeout(stalled);
      stalled = setTimeout(() => finish(true), CLIP_STALL_MS);
    };
    audio.stop = finish;
    v.onended = () => finish();
    v.onerror = () => finish(true);
    v.ontimeupdate = watch;
    v.muted = false;
    v.src = url;
    state.speaking = true;
    updateTalk();
    watch();
    v.play().catch((err) => {
      if (err.name === "NotAllowedError") audio.primed = false;  // the next tap tries again
      finish(err.name !== "AbortError");
    });
  });
}

// Her words are always on screen, so a lost voice doesn't stop the game.
function voiceTrouble() {
  if (state.voiceWarned || $("s-game").hidden) return;
  state.voiceWarned = true;
  pop(`${WHO()}'S VOICE DROPPED`, "Read the lines on screen. The call goes on.", "move");
}

function hush() {
  state.speechRun++;
  audio.voice.pause();
  if (audio.stop) audio.stop();
}

const localClips = {};
const SHARED_CLIPS = new Set(["flip_open", "flip_ask", "parents"]);
const clipPath = (name) => `/audio/${SHARED_CLIPS.has(name) ? "" : (state.game && state.game.audio) || ""}${state.lang === "en" ? "en/" : ""}${name}.mp3`;
const clip = (name) => localClips[clipPath(name)] || clipPath(name);

// Her instant reactions have to be instant, so they're on the phone before she needs them.
function preloadClips() {
  const names = ["nothing_heard", ...[0, 1, 2].map((n) => `cutoff_${n}`), ...[...Array(10).keys()].map((n) => `filler_${n}`)];
  for (const path of names.map(clipPath)) {
    if (localClips[path]) continue;
    fetch(path)
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => { if (blob) localClips[path] = URL.createObjectURL(blob); })
      .catch(() => {});
  }
}

// ---------- Screens ----------

const SCREENS = ["title", "account", "brief", "ring", "game", "end", "flip", "report"];

function show(name) {
  for (const id of SCREENS) $(`s-${id}`).hidden = id !== name;
  regender();
  document.body.classList.toggle("in-game", name === "game" || name === "report");
  // Screens you can step back from get a history entry, so the phone's Back button works too.
  if (["account", "brief", "game", "report"].includes(name) && !(history.state && history.state.screen === name)) {
    try { history.pushState({ screen: name }, ""); } catch (err) { /* sandboxed */ }
  }
}

const screenNow = () => SCREENS.find((id) => !$(`s-${id}`).hidden);

function goHome() {
  hush();
  $("leave").hidden = true;
  show("title");
  loadStats();
  showUnlocks();
  refreshAccount();
}

// Leaving a live call always asks first. Leaving means hanging up: the ending still plays.
function askLeave() {
  if (!inCall()) return;
  releaseTalk();
  $("leave").hidden = false;
  $("b-stay").focus();
}

$("b-stay").addEventListener("click", () => { $("leave").hidden = true; });
$("b-leave").addEventListener("click", () => {
  $("leave").hidden = true;
  endCall("hung_up");
});
document.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => { sfx.tap(); goHome(); }));

window.addEventListener("popstate", () => {
  const now = screenNow();
  if (now === "game" && inCall()) {
    try { history.pushState({ screen: "game" }, ""); } catch (err) { /* sandboxed */ }
    askLeave();
  } else if (now === "brief" || now === "report" || now === "account") {
    goHome();
  } else if (now !== "title") {
    try { history.pushState({ screen: now }, ""); } catch (err) { /* mid-ending: stay put */ }
  }
});

function bubble(text, english) {
  const b = $("bubble");
  b.hidden = !text;
  if (text) {
    b.textContent = text;
    if (english) {
      const small = document.createElement("small");
      small.textContent = english;
      b.append(small);
    }
    b.style.animation = "none";
    void b.offsetWidth;
    b.style.animation = "";
  }
}

function pop(title, note = "", kind = "") {
  const el = document.createElement("div");
  el.className = `pop ${kind}`;
  el.textContent = title;
  if (note) {
    const small = document.createElement("small");
    small.textContent = note;
    el.append(small);
  }
  el.style.left = `${38 + rand(24)}%`;
  $("pops").append(el);
  setTimeout(() => el.remove(), 2900);
}

function jolt() {
  $("app").classList.remove("shake");
  void $("app").offsetWidth;
  $("app").classList.add("shake");
  haptic(60);
}

// Boss: one move at a time. The objective, then what to say, what to avoid, what to watch.
function setBoss(boss, tag) {
  if (!boss) return;
  $("boss-line").textContent = boss.text;
  $("boss-do").textContent = boss.do || "";
  quietBoss();
  const mark = $("boss-mark");
  mark.hidden = !boss.mark;
  if (boss.mark) {
    mark.className = `boss-mark ${boss.mark.kind}`;
    mark.textContent = `${boss.mark.kind === "good" ? "✓" : "✗"} ${boss.mark.text}`;
  }
  $("boss").classList.toggle("warn", Boolean(boss.warn));
  $("boss-tag").textContent = tag || (boss.warn ? "· Careful" : "· Your move");
  $("boss").classList.remove("new");
  void $("boss").offsetWidth;
  $("boss").classList.add("new");
  sfx.radio();
  if (boss.gone) $("boss-tag").textContent = "· Line dead";
}

// Boss speaks up when something changes, then fades back so Dadi stays the focus.
function quietBoss() {
  $("boss").classList.remove("quiet");
  clearTimeout(state.bossQuiet);
  state.bossQuiet = setTimeout(() => $("boss").classList.add("quiet"), 7000);
}

function setBossText(text, tag) {
  $("boss-line").textContent = text;
  $("boss-do").textContent = "";
  $("boss-mark").hidden = true;
  quietBoss();
  $("boss").classList.remove("warn");
  $("boss-tag").textContent = tag;
  $("boss").classList.remove("new");
  void $("boss").offsetWidth;
  $("boss").classList.add("new");
  sfx.radio();
}

function setSuspicion(value) {
  const fill = $("m-fill");
  fill.style.width = `${Math.min(100, value)}%`;
  fill.classList.toggle("warm", value >= 45 && value < 75);
  fill.classList.toggle("hot", value >= 75);
  $("m-word").textContent = state.signal || (value >= 90 ? "ABOUT TO HANG UP" : value >= 75 ? "SUSPICIOUS" : value >= 45 ? "UNSURE" : "CALM");
  const slot = $("dadi-slot");
  slot.classList.toggle("wary", value >= 45);
}

function updateTalk() {
  const btn = $("b-talk");
  const label = $("talk-label");
  const locked = Date.now() < state.lockedUntil || state.over;
  btn.classList.toggle("locked", locked || state.busy);
  btn.classList.toggle("alarm", (state.callbackPending || state.shoutPending) && !state.holding);
  if (state.holding) label.textContent = state.shoutPending ? "LOUDER!" : "TALKING…";
  else if (state.over) label.textContent = "CALL OVER";
  else if (locked) label.textContent = "ON HOLD…";
  else if (state.busy) label.textContent = state.speaking ? "LISTEN…" : `${WHO()} IS THINKING`;
  else if (state.voiceDown) label.textContent = "TYPE YOUR LINE BELOW";
  else if (state.callbackPending) label.textContent = "STOP HER, OR LET HER?";
  else if (state.shoutPending) label.textContent = "HOLD AND SHOUT!";
  else if (state.speaking) label.textContent = "HOLD TO INTERRUPT";
  else label.textContent = "HOLD TO TALK";
}

// ---------- Accounts ----------
// One quiet chip on the title. Behind it, sign-in, or your caller ID: calls, best, who can pick up,
// and the board. Demo and trailer runs never show it.

const getJSON = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
const quietMode = () => demoMode() || new URLSearchParams(location.search).get("trailer") === "1";

async function refreshAccount() {
  if (quietMode()) return;
  const me = await getJSON("/api/auth/me");
  account.user = (me && me.user) || null;
  account.player = account.user ? await getJSON("/api/player") : null;
  if (account.user && !account.player) account.user = null;  // the session ended between the two
  renderAccountChip();
  if (screenNow() === "title") { loadStats(); showUnlocks(); }
  if (screenNow() === "account") renderAccount();
}

function renderAccountChip() {
  const chip = $("b-account");
  chip.hidden = quietMode();
  chip.classList.toggle("in", Boolean(account.user));
  const st = account.player && account.player.stats;
  const label = account.user ? `${account.user.username}${st && st.completed ? `, best ${st.best_score}` : ""}. Your caller ID` : "Sign in";
  $("account-face").textContent = account.user ? account.user.username[0].toUpperCase() : "👤";
  $("account-name").textContent = label;
  chip.setAttribute("aria-label", label);
  chip.title = label;
}

let acctMode = "login";
function setAcctMode(mode) {
  acctMode = mode;
  document.querySelectorAll("[data-acct]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.acct === mode)));
  $("acct-title").textContent = mode === "login" ? "Sign in" : "Pick a caller ID";
  $("acct-submit").textContent = mode === "login" ? "Sign in" : "Create account";
  $("acct-pass").autocomplete = mode === "login" ? "current-password" : "new-password";
  $("acct-pass").placeholder = mode === "login" ? "" : "at least 8 characters";
  $("acct-user").placeholder = mode === "login" ? "" : "letters, numbers, _";
  $("acct-error").hidden = true;
}
document.querySelectorAll("[data-acct]").forEach((b) => b.addEventListener("click", () => { sfx.tap(); setAcctMode(b.dataset.acct); }));

$("b-account").addEventListener("click", () => {
  unlockAudio();
  sfx.tap();
  show("account");
  renderAccount();
  if (!account.user) setTimeout(() => $("acct-user").focus(), 50);
});

$("acct-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = $("acct-user").value.trim(), password = $("acct-pass").value;
  $("acct-submit").disabled = true;
  $("acct-error").hidden = true;
  const resp = await post(`/api/auth/${acctMode === "login" ? "login" : "register"}`, { username, password }).catch(() => null);
  const data = resp ? await resp.json().catch(() => null) : null;
  $("acct-submit").disabled = false;
  if (!resp || !resp.ok) {
    const detail = data && data.detail;
    $("acct-error").textContent = typeof detail === "string" ? detail : "Couldn't reach the game. Try again.";
    $("acct-error").hidden = false;
    sfx.bad();
    return;
  }
  $("acct-pass").value = "";
  sfx.good();
  await refreshAccount();
  renderAccount();
});

$("acct-logout").addEventListener("click", async () => {
  sfx.tap();
  await post("/api/auth/logout").catch(() => null);
  account.user = account.player = null;
  renderAccountChip();
  renderAccount();
});

$("home-play").addEventListener("click", () => {
  unlockAudio();
  sfx.tap();
  state.mode = state.code ? "challenge" : "free";
  show("brief");
});

const CAST = [["dadi", "Dadi"], ["didi", "Pinky Didi"], ["dadaji", "Dadaji"]];

function renderAccount() {
  const p = account.player;
  $("acct-out").hidden = Boolean(p);
  $("acct-in").hidden = !p;
  if (p) {
    const st = p.stats;
    $("home-name").textContent = p.username;
    $("hs-games").textContent = st.games;
    $("hs-best").textContent = st.completed ? st.best_score : "–";
    $("hs-hung").textContent = st.mirror_calls ? `${st.mirror_hung_up}/${st.mirror_calls}` : "–";
    $("hs-flags").textContent = st.quiz_answered ? `${st.quiz_correct}/${st.quiz_answered}` : "–";
    $("home-rank").textContent = p.rank ? `#${p.rank} on the all-time board. ${st.cracked} OTP${st.cracked === 1 ? "" : "s"} cracked, ${st.busted} times caught.`
      : st.games ? "Answer the three questions after a call to get a score and a place on the board." : "Your first call is waiting.";
    $("home-cast").replaceChildren(...CAST.map(([role, label]) => {
      const card = document.createElement("div");
      card.className = `cast${p.unlocked.includes(role) ? "" : " locked"}`;
      const tpl = $(`${role}-art`);
      if (tpl) card.append(tpl.content.cloneNode(true));
      card.append(document.createTextNode(label));
      return card;
    }));
    const next = p.next_unlock;
    $("home-next").textContent = next ? `🔒 Next: ${next.role === "didi" ? "Pinky Didi" : "Dadaji"}. ${next.need}${next.of > 1 ? ` (${next.have}/${next.of})` : ""}`
      : "Everyone can pick up now. You never know who will.";
  }
  getJSON("/api/leaderboard").then((board) => {
    const top = (board && board.top) || [];
    $("home-board-empty").hidden = top.length > 0;
    $("home-board").replaceChildren(...top.map((e) => {
      const li = document.createElement("li");
      if (account.user && e.name === account.user.username) li.className = "mine";
      li.textContent = `${e.name} · ${e.score} · ${e.games} call${e.games === 1 ? "" : "s"}`;
      return li;
    }));
  });
}

// A reload mid-call can't resume a live, timed call. Close it on the server, uncounted, and say so.
function recoverDroppedCall() {
  let id = null;
  try { id = sessionStorage.getItem("hu_live"); sessionStorage.removeItem("hu_live"); } catch (err) { return; }
  if (!id || quietMode()) return;
  post(`/api/game/${id}/abandon`).then((r) => (r.ok ? r.json() : null)).catch(() => null).then((d) => {
    if (!d || !d.abandoned || state.code) return;
    $("dare").textContent = "Your last call dropped when the page reloaded, so it wasn't counted. Start a fresh one.";
    $("dare").hidden = false;
  });
}

// ---------- Title ----------

async function loadStats() {
  const labels = document.querySelectorAll(".scoreboard small");
  if (account.player) {  // signed in: your own calls, not everyone's
    const st = account.player.stats;
    $("st-plays").textContent = st.games.toLocaleString("en-IN");
    $("st-rate").textContent = st.cracked.toLocaleString("en-IN");
    $("st-mins").textContent = st.completed ? st.best_score : "–";
    ["your calls", "you cracked", "your best"].forEach((t, i) => { labels[i].textContent = t; });
    return;
  }
  ["scammers tried", "cracked her", "minutes wasted"].forEach((t, i) => { labels[i].textContent = t; });
  try {
    const s = await (await fetch("/api/stats")).json();
    $("st-plays").textContent = s.plays.toLocaleString("en-IN");
    $("st-rate").textContent = s.cracked.toLocaleString("en-IN");
    $("st-mins").textContent = s.minutes.toLocaleString("en-IN");
  } catch (err) {
    console.warn(err);
  }
}

// Hindi is the default. ?lang=en picks English, and a player's choice is remembered.
function chosenLang() {
  const asked = new URLSearchParams(location.search).get("lang");
  if (asked === "en" || asked === "hi") return asked;
  return safeGet("dadi_lang") === "en" ? "en" : "hi";
}

function setLang(lang) {
  state.lang = lang;
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  $("speak-in").textContent = lang === "en" ? "English, or Hinglish." : "Hindi or Hinglish.";
}

for (const btn of document.querySelectorAll("[data-lang]")) {
  btn.addEventListener("click", () => {
    sfx.tap();
    setLang(btn.dataset.lang);
    safeSet("dadi_lang", btn.dataset.lang);
  });
}
setLang(state.lang);

$("b-start").addEventListener("click", () => {
  unlockAudio();
  sfx.tap();
  state.mode = state.code ? "challenge" : challengeCode("seed") ? "seed" : "free";
  show("brief");
});

// Inside the installed app, or on an iPhone, there's nothing to download.
if (matchMedia("(display-mode: standalone)").matches || document.referrer.startsWith("android-app://")
    || /iPhone|iPad|iPod/.test(navigator.userAgent)) $("b-apk").hidden = true;

$("b-daily").addEventListener("click", () => {
  unlockAudio();
  sfx.tap();
  state.mode = "daily";
  show("brief");
});

// ?c=32KQX is a friend's scenario: same Dadi, same moves. ?s= is the score to beat.
// ?seed= does the same quietly, for reproducing a character while developing.
function challengeCode(param = "c") {
  const c = (new URLSearchParams(location.search).get(param) || "").toUpperCase();
  return /^[0-4][0-4][A-Z]{3}[PD]?$/.test(c) ? c : null;
}

// Who can pick up, kept in this browser. New people join as the player gets better.
function unlocked() {
  try { return JSON.parse(safeGet("dadi_unlocked") || "[]"); } catch (err) { return []; }
}

// Dadis whose OTP this browser has got, by code: three different ones bring in Dadaji.
function crackedDadis() {
  try { return JSON.parse(safeGet("dadi_cracked") || "[]"); } catch (err) { return []; }
}

function showUnlocks() {
  const el = $("unlocks");
  const have = account.player ? account.player.unlocked : unlocked();
  const n = account.player ? account.player.cracked_dadis : crackedDadis().length;
  el.hidden = false;
  el.textContent = !have.includes("didi")
    ? "🔒 Next to pick up: Pinky Didi. Get any Dadi's OTP once."
    : !have.includes("dadaji")
      ? `✓ Pinky Didi can pick up now. 🔒 Next: Dadaji. Crack 3 different Dadis (${Math.min(n, 3)}/3).`
      : "✓ Pinky Didi and Dadaji can pick up now. You never know who will.";
}

// A first 1930 brings in Pinky; three different Dadis cracked bring in Dadaji. Whoever is new answers the very next call.
function unlockNext(r) {
  if (state.game.demo || r.outcome !== "cracked") return "";
  if (r.saved) {  // signed in: the server decided, and remembers
    const fresh = (r.unlocked || [])[0];
    return fresh === "didi" ? "NEW: Pinky Didi unlocked. She picks up your next call."
      : fresh === "dadaji" ? "NEW: Dadaji unlocked. He picks up your next call. Keep your story straight." : "";
  }
  const have = unlocked();
  if (state.game.role === "dadi" && state.game.code) {
    const done = crackedDadis();
    if (!done.includes(state.game.code)) safeSet("dadi_cracked", JSON.stringify([...done, state.game.code].slice(-20)));
  }
  if (!have.includes("didi")) {
    safeSet("dadi_unlocked", JSON.stringify([...have, "didi"]));
    safeSet("dadi_meet", "didi");
    return "NEW: Pinky Didi unlocked. She picks up your next call.";
  }
  if (!have.includes("dadaji") && crackedDadis().length >= 3) {
    safeSet("dadi_unlocked", JSON.stringify([...have, "dadaji"]));
    safeSet("dadi_meet", "dadaji");
    return "NEW: Dadaji unlocked. He picks up your next call. Keep your story straight.";
  }
  return "";
}

function setupTitle() {
  showUnlocks();
  if (state.code) {
    const dare = Number(new URLSearchParams(location.search).get("s"));
    $("dare").textContent = dare > 0 && dare <= 100
      ? `A friend scored ${dare}/100 on this call. Same person, same moves. Beat it.`
      : "A friend sent you this call. Same person, same moves. Beat them.";
    $("dare").hidden = false;
    $("b-start").textContent = "Take the challenge";
  }
  if (demoMode()) return;
  fetch("/api/daily").then((r) => (r.ok ? r.json() : null)).then((d) => {
    if (!d) return;
    state.daily = d;
    $("daily-name").textContent = "same call for everyone";
    $("b-daily").hidden = false;
  }).catch(() => {});
}
setupTitle();

for (const btn of document.querySelectorAll("[data-quiz]")) {
  btn.addEventListener("click", () => {
    unlockAudio();
    sfx.tap();
    state.quizBefore = btn.dataset.quiz === "true";
    beginCall();
  });
}

// ---------- Microphone ----------

const mic = { stream: null, nodes: null, ready: false, loaded: false, blocked: false };

async function startMic() {
  if (mic.ready) return true;
  try {
    mic.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: false, autoGainControl: true },
    });
    const ctx = audio.ctx;
    resumeAudio();  // a permission prompt can leave it suspended
    if (!mic.loaded) {
      await ctx.audioWorklet.addModule("/pcm-worklet.js");
      mic.loaded = true;
    }
    const worklet = new AudioWorkletNode(ctx, "pcm-worklet");
    worklet.port.onmessage = (e) => onMicFrame(e.data);
    const source = ctx.createMediaStreamSource(mic.stream);
    source.connect(worklet);
    // Chrome only runs nodes that lead to the speakers, so route through silence.
    const mute = ctx.createGain();
    mute.gain.value = 0;
    worklet.connect(mute).connect(ctx.destination);
    mic.nodes = { source, worklet, mute };
    mic.stream.getAudioTracks().forEach((track) => { track.onended = micLost; });
    mic.ready = true;
    mic.blocked = false;
    return true;
  } catch (err) {
    console.warn("No microphone", err);
    mic.blocked = err.name === "NotAllowedError";
    stopMic();
    return false;
  }
}

// The mic is only ever on during a call, so the browser's indicator goes out with it.
function stopMic() {
  if (mic.stream) {
    mic.stream.getTracks().forEach((track) => {
      track.onended = null;
      track.stop();
    });
  }
  if (mic.nodes) {
    mic.nodes.worklet.port.onmessage = null;
    mic.nodes.source.disconnect();
    mic.nodes.worklet.disconnect();
    mic.nodes.mute.disconnect();
  }
  mic.stream = mic.nodes = null;
  mic.ready = false;
}

const inCall = () => state.game && !state.over && !$("s-game").hidden;

// Another app or a phone call can take the mic mid-game. Try once to get it back.
async function micLost() {
  stopMic();
  if (!inCall() || state.voiceDown) return;
  releaseTalk();
  if (!(await startMic()) && inCall()) voiceUnavailable("We lost your microphone. Type your lines instead.");
}

function onMicFrame(buffer) {
  if (!state.holding) return;
  const samples = new Int16Array(buffer);
  let sum = 0;
  for (const v of samples) sum += v * v;
  const level = Math.min(1, (Math.sqrt(sum / samples.length) / 32768) * 5);
  state.peak = Math.max(state.peak, level);
  $("b-talk").style.setProperty("--level", level.toFixed(2));
  if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send(buffer);
}

function openListener() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/listen?lang=${state.lang}`);
  ws.binaryType = "arraybuffer";
  ws.onclose = () => {
    if (state.ws !== ws || state.over || state.voiceDown) return;
    if (++state.listenFails > 3) {
      voiceUnavailable("Your voice line keeps dropping. Type your lines instead.");
      return;
    }
    setTimeout(() => {
      if (state.ws === ws && !state.over && !state.voiceDown) openListener();
    }, 500 * state.listenFails);
  };
  ws.onmessage = (e) => {
    const event = JSON.parse(e.data);
    if (event.type === "speech_start") state.pendingSegments++;
    if (event.type === "partial_transcript") {
      state.partial = event.text || "";
      $("you-said").textContent = state.partial;
      if (state.holding && !state.storyBuilt && OTP_WORD.test(state.partial)) cutOff(state.partial);
    }
    if (event.type === "transcript" || event.type === "final_transcript") {
      state.pendingSegments = Math.max(0, state.pendingSegments - 1);
      if (event.text) state.finals.push(event.text);
      state.partial = "";
      $("you-said").textContent = state.finals.join(" ");
    }
    if (event.type === "flushed") state.flushed = true;
    if (event.type === "error") voiceUnavailable("Voice is full right now. Type your lines instead.");
  };
  state.ws = ws;
  return new Promise((resolve) => {
    ws.onopen = () => {
      state.listenFails = 0;
      resolve(true);
    };
    ws.onerror = () => resolve(false);
  });
}

// A call never dead-ends: without voice, typing plays the whole game.
function voiceUnavailable(message) {
  state.voiceDown = true;
  $("type-form").hidden = false;
  updateTalk();
  if (!$("s-game").hidden) pop("TYPE INSTEAD", message, "move");
}

async function playSpeech(url, stale = () => false, onReady = () => {}) {
  if (STREAMS_AUDIO) {
    onReady();
    return say(url);
  }
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), 15000);
  const blob = await fetch(url, { signal: stop.signal }).then((r) => (r.ok ? r.blob() : null)).catch(() => null);
  clearTimeout(timer);
  if (stale()) return;
  onReady();
  if (!blob) {
    voiceTrouble();
    return;
  }
  const local = URL.createObjectURL(blob);
  await say(local);
  URL.revokeObjectURL(local);
}

// ---------- Starting the call ----------

async function beginCall() {
  if (state.starting) return;
  state.starting = true;
  try {
    await runCall();
  } finally {
    state.starting = false;
  }
}

function startFailed(message) {
  stopMic();
  $("brief-error").textContent = message;
  $("brief-error").hidden = false;
}

async function runCall() {
  $("brief-error").hidden = true;
  // Never let an unanswered permission prompt freeze the game; typing still works.
  const hasMic = await Promise.race([startMic(), sleep(15000).then(() => false)]);
  const returning = safeGet("dadi_name");
  let data;
  try {
    const resp = await post("/api/game/start", {
      hour: forcedHour() ?? (demoMode() ? 18 : new Date().getHours()),
      demo: demoMode(),
      lang: state.lang,
      daily: state.mode === "daily",
      code: state.mode === "challenge" ? state.code : state.mode === "seed" ? challengeCode("seed") : null,
      boss_off: $("boss-off").checked,
      returning_name: returning,
      recent: recentScenarios(),
      roles: ["dadi", ...unlocked()],
      meet: safeGet("dadi_meet") || null,
      calls: Number(safeGet("dadi_calls") || 0),
      quiz: state.quizBefore,
    }, 30000);
    if (!resp.ok) {
      startFailed((await resp.json().catch(() => ({}))).detail || NOT_ANSWERING);
      return;
    }
    data = await resp.json();
  } catch (err) {
    console.warn(err);
    startFailed(NOT_ANSWERING);
    return;
  }
  try { sessionStorage.setItem("hu_live", data.id); } catch (err) { /* private window */ }
  Object.assign(state, {
    game: data, seq: 0, secondsLeft: data.seconds, over: false, busy: false, holding: false, lockedUntil: 0,
    voiceDown: !hasMic, shoutPending: false, shoutTries: 0, callbackPending: false, pappuHere: false, pendingDigits: [],
    finals: [], partial: "", idleCount: 0, gags: {}, report: null, storyBuilt: data.story_built, cutoffs: 0, callLost: false,
    voiceWarned: false, listenFails: 0, deadMicHolds: 0, flipPicked: null, graded: null, signal: "", mirrorPattern: null,
  });
  if (data.role && data.role === safeGet("dadi_meet")) safeSet("dadi_meet", "");  // the guaranteed first meeting is done
  setArt(data.role);
  buildCallScreen(data, hasMic);
  preloadClips();

  $("ring-mood").textContent = data.name;
  $("ring-tag").textContent = `${data.daily ? "Today's challenge · " : state.mode === "challenge" ? "Challenge · " : ""}You don't know her. Yet.`;
  showDebug(data.debug);
  show("ring");
  sfx.ring();
  if (hasMic) await Promise.race([openListener(), sleep(4000)]);
  await sleep(1400);
  sfx.ring();
  await sleep(1500);

  show("game");
  if (data.boss_off) setBossText(data.boss.text, "· No Boss");
  else setBoss(data.boss, "· Your first move");
  setSuspicion(data.suspicion);
  if (!hasMic) setTimeout(() => pop(mic.blocked ? "YOUR MIC IS BLOCKED" : "NO MICROPHONE", mic.blocked ? "Allow it in your browser settings, or just type." : "No problem. Just type your lines.", "move"), 1200);
  await say(clip(data.greet));
  if (state.over) return;
  startTimer();
  state.idleAt = Date.now() + 14000;
}

function buildCallScreen(data, hasMic) {
  document.querySelectorAll(".slot").forEach((s) => {
    s.textContent = "?";
    s.className = "slot";
  });
  bubble("");
  $("you-said").textContent = "";
  $("pappu").hidden = true;
  $("away").hidden = true;
  $("dadi-slot").className = "dadi-slot";
  $("demo-tag").hidden = !data.demo;
  $("type-form").hidden = hasMic;
  updateTalk();
}

function startTimer() {
  clearInterval(state.timerId);
  renderTimer();
  state.timerId = setInterval(() => {
    state.secondsLeft--;
    renderTimer();
    if (state.secondsLeft <= 10 && state.secondsLeft > 0) sfx.tick();
    if (state.secondsLeft <= 0) endCall("timeout");
    else maybeIdle();
    updateTalk();
  }, 1000);
}

function renderTimer() {
  const s = Math.max(0, state.secondsLeft);
  $("timer").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  $("timer").classList.toggle("low", s <= 20);
}

// Silence is a move too. Dadi notices.
function maybeIdle() {
  if (state.over || state.busy || state.holding || state.speaking || Date.now() < state.lockedUntil) return;
  if (state.callbackPending || Date.now() < state.idleAt) return;
  say(clip(`idle_${state.idleCount++ % 3}`));
  state.idleAt = Date.now() + 15000;
}

// ---------- Talking ----------

function pressTalk() {
  if (state.holding) return;
  if (state.voiceDown && !state.over) {
    $("type-form").hidden = false;
    $("type-input").focus();
    pop("TYPE YOUR LINE", mic.blocked ? "Your mic is blocked, and that's fine" : "Voice isn't available, and that's fine", "move");
    return;
  }
  if (state.over || state.busy || Date.now() < state.lockedUntil) {
    $("b-talk").classList.remove("nope");
    void $("b-talk").offsetWidth;
    $("b-talk").classList.add("nope");
    return;
  }
  unlockAudio();
  if (state.speaking) {
    hush();
    pop(`YOU INTERRUPTED ${WHO()}`, "", "gag");
  }
  state.holding = true;
  state.heldAt = Date.now();
  state.peak = 0;
  state.finals = [];
  state.partial = "";
  state.pendingSegments = 0;
  state.flushed = false;
  $("you-said").textContent = "";
  $("b-talk").classList.add("down");
  sfx.tap();
  haptic(20);
  if (state.callbackPending) blockCheck();
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    pop("RECONNECTING YOUR LINE", "Give it a second, then speak", "move");
    if (!state.ws || state.ws.readyState !== WebSocket.CONNECTING) openListener();
  }
  updateTalk();
}

async function releaseTalk() {
  if (!state.holding) return;
  state.holding = false;
  $("b-talk").classList.remove("down");
  $("b-talk").style.setProperty("--level", "0");
  state.busy = true;
  updateTalk();
  const heldFor = Date.now() - state.heldAt;
  const text = await collectSpeech();
  state.busy = false;
  if (state.over) return;
  // Not even silence reached us, so the mic isn't really working.
  if (!text && heldFor > 1000 && state.peak === 0) {
    resumeAudio();
    if (++state.deadMicHolds >= 2) {
      voiceUnavailable("Your mic isn't sending any sound. Type your lines instead.");
      return;
    }
  } else if (state.peak > 0) {
    state.deadMicHolds = 0;
  }
  await handleSaid(text, state.peak);
}

// Let Prisma finish the words it's still working on.
async function collectSpeech() {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send("flush");
    const deadline = Date.now() + 2800;
    while (Date.now() < deadline && state.ws.readyState === WebSocket.OPEN && !(state.flushed && state.pendingSegments === 0)) await sleep(60);
  }
  const text = [...state.finals, state.partial].join(" ").trim();
  state.finals = [];
  state.partial = "";
  return text;
}

// She hears "OTP" in Prisma's live words, before the player has built a story,
// and talks right over them. Pre-recorded, so it lands while they're mid-sentence.
async function cutOff(said) {
  state.holding = false;
  state.busy = true;
  state.speechRun++;
  $("b-talk").classList.remove("down");
  $("b-talk").style.setProperty("--level", "0");
  if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send("flush");
  const game = state.game;
  const judged = post(`/api/game/${game.id}/cutoff`, { said })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  pop(`${WHO()} CUT YOU OFF`, "You asked before building a story", "bad");
  sfx.bad();
  jolt();
  const which = state.cutoffs++ % 3;
  const [hi, en] = isPinky() ? [CUTOFF_DIDI_HI, CUTOFF_DIDI_EN] : isDadaji() ? [CUTOFF_DADAJI_HI, CUTOFF_DADAJI_EN] : [CUTOFF_HI, CUTOFF_EN];
  if (state.lang === "en") bubble(en[which]);
  else bubble(hi[which], en[which]);
  const line = say(clip(`cutoff_${which}`));
  const result = await judged;
  if (result) {
    setSuspicion(result.suspicion);
    setBoss(result.boss);
  }
  await line;
  state.busy = false;
  state.finals = [];
  state.partial = "";
  state.idleAt = Date.now() + 15000;
  updateTalk();
  if (result && result.outcome) await endCall(result.outcome);
}

async function handleSaid(text, peak, typed = false) {
  state.idleAt = Date.now() + 16000;
  if (!text) {
    await say(clip("nothing_heard"));
    return;
  }
  $("you-said").textContent = text;

  if (state.shoutPending && !typed) {
    if (peak < SHOUT_LEVEL) {
      state.shoutTries++;
      if (state.shoutTries >= 2) {
        state.shoutPending = false;
        applyCounter("shout", false);
        pop("TOO QUIET!", "She gets suspicious", "bad");
      }
      await say(clip("shout_fail"));
      updateTalk();
      return;
    }
    state.shoutPending = false;
    applyCounter("shout", true);
    pop("SHE HEARD YOU", "", "good");
    state.busy = true;
    await say(clip("shout_pass"));
  }

  await playTurn(text);
}

async function playTurn(text) {
  const game = state.game;
  state.busy = true;
  const run = ++state.speechRun;
  const stale = () => run !== state.speechRun || state.over;
  updateTalk();

  // She reacts instantly, then the real reply lands.
  const firstClip = state.pappuHere ? "pappu_back" : pickFiller();
  if (state.pappuHere) {
    state.pappuHere = false;
    $("pappu").hidden = true;
  }
  const reacting = say(clip(firstClip));
  let answered = false;
  state.seq += 1;
  const reply = post(`/api/game/${game.id}/turn`, { said: text, seq: state.seq })
    .then((resp) => {
      // The server restarted mid-call, or already knows how this call ended.
      if (resp.status === 404 || resp.status === 409) state.callLost = true;
      return resp.ok ? resp.json() : null;
    })
    .catch((err) => { console.warn(err); return null; })
    .finally(() => { answered = true; });
  await reacting;
  // Still thinking? A second mumble beats dead air.
  await Promise.race([reply, sleep(1000)]);
  if (!answered) await say(clip(pickFiller()));
  const result = await reply;
  if (state.over) return;
  if (state.callLost) {
    state.busy = false;
    await endCall("hung_up");
    return;
  }
  if (!result) {
    state.busy = false;
    pop("THE LINE BROKE UP", `${who()} didn't catch that. Say it again.`, "move");
    await say(clip("canned_0"));  // "the network dropped, say that again"
    return;
  }
  showMoveResult(result);
  state.storyBuilt = result.story_built;
  bubble(result.reply, result.reply_en);

  // Ordinary chatter can be talked over. A digit, an ending or her counter-move
  // can't, or the player would never see what they just won or triggered.
  const mustHear = Boolean(result.digits.length || result.outcome || result.effect || result.event || result.boss_gone);
  const canPress = () => {
    state.busy = mustHear;
    updateTalk();
  };
  if (result.speech && result.canned === null) {
    await playSpeech(result.speech, stale, canPress);
  } else {
    canPress();
    if (result.speech) await say(result.speech);
  }
  if (stale()) return;

  if (result.boss_gone) {
    pop("BOSS HAS GONE SILENT", "You're on your own now. What did you learn?", "bad");
    sfx.warn();
    jolt();
  }
  state.pendingDigits.push(...result.digits);
  await revealDigits(run);
  if (stale()) return;

  if (result.outcome) {
    state.busy = false;
    await endCall(result.outcome);
    return;
  }
  if (result.event) await showEvent(result.event, result.effect);
  if (result.effect) await runCounter(result.effect, result.event);
  state.busy = false;
  updateTalk();
  state.idleAt = Date.now() + 15000;
}

function pickFiller() {
  if (state.usedFillers.length >= 10) state.usedFillers = [];
  let n;
  do { n = rand(10); } while (state.usedFillers.includes(n));
  state.usedFillers.push(n);
  return `filler_${n}`;
}

// Every move shows which real trick it was. The lesson arrives as part of the fun.
function showMoveResult(r) {
  const move = r.move;
  state.signal = (r.signal || "").toUpperCase();  // how she sounds now, never a number
  setSuspicion(r.suspicion);
  const name = TACTIC_NAMES[move.tactic] || (move.tactic === "ask" ? "The OTP ask" : null);
  const notes = move.notes || [];
  if (notes.includes("story_held")) {
    pop("YOUR STORY HELD", "She believed you. For now.", "good");
    sfx.good();
  } else if (notes.includes("contradiction")) {
    pop("SHE CAUGHT YOUR LIE", "Real scammers slip too. Ask them to repeat their details.", "bad");
    sfx.bad();
    jolt();
  } else if (notes.includes("too_soon")) {
    pop("TOO SOON!", "You asked before building a story", "bad");
    sfx.bad();
    jolt();
  } else if (notes.includes("backfire")) {
    pop("SHE DIDN'T LIKE THAT", "That approach puts her off", "bad");
    sfx.bad();
  } else if (notes.includes("repeat")) {
    pop("SAME TRICK AGAIN?", "She noticed. Try something else.", "bad");
    sfx.warn();
  } else if (notes.includes("off_script")) {
    pop("THAT WASN'T A SCAM MOVE", "Boss is shaking his head", "gag");
  } else if (name && move.trust_gain >= 10) {
    pop(`${name.toUpperCase()}!`, "It's working", "good");
    sfx.trick();
  }
  $("dadi-slot").classList.toggle("fond", r.trust >= 55);
  setBoss(r.boss);
  for (const gag of r.gags || []) {
    state.gags[gag] = (state.gags[gag] || 0) + 1;
  }
  if (r.suspicion >= 75) sfx.warn();
}

async function revealDigits(run) {
  while (state.pendingDigits.length) {
    if (run !== state.speechRun || state.over) return;
    const d = state.pendingDigits.shift();
    const slot = document.querySelector(`.slot[data-slot="${d.index}"]`);
    await say(clip(`digit_intro_${d.index}`));
    if (run !== state.speechRun) { state.pendingDigits.unshift(d); return; }
    if (d.decoy !== undefined) {
      setSlot(slot, d.decoy);
      await say(clip(`num_${d.decoy}`));
      await sleep(500);
      slot.classList.add("fake");
      sfx.bad();
      pop("WRONG DIGIT!", "She misread it. On purpose?", "bad");
      await say(clip("decoy_fix"));
      slot.classList.remove("fake");
    }
    setSlot(slot, d.digit);
    sfx.good();
    jolt();
    pop(`DIGIT ${d.index + 1} OF 4!`, "", "good");
    await say(clip(`num_${d.digit}`));
  }
}

function setSlot(slot, value) {
  slot.textContent = value;
  slot.classList.remove("got");
  void slot.offsetWidth;
  slot.classList.add("got");
}

// ---------- Dadi fights back ----------

function applyCounter(effect, passed) {
  post(`/api/game/${state.game.id}/counter`, { effect, passed })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data) return;
      setSuspicion(data.suspicion);
      if (data.outcome && !state.over) endCall(data.outcome);
    })
    .catch((err) => console.warn(err));
}

// Something in her day just happened. The cause was always on screen or in her words.
async function showEvent(event, effect) {
  pop(event.title, event.note, "move");
  sfx.warn();
  if (event.clock) {
    state.secondsLeft = Math.min(state.secondsLeft, event.clock);
    renderTimer();
  }
  if (event.clip && effect !== "hold") await say(clip(event.clip));
}

async function runCounter(effect, event = null) {
  const note = ((ROLE_NOTES[state.game.role] || {})[effect]) || COUNTER_NOTES[effect];
  if (note) {
    pop(note[0].replace("DADI", WHO()), note[1], "move");

  }
  if (effect === "hold") {
    await say(clip((event && event.clip) || "hold"));
    await holdPhase(undefined, (event && event.why) || undefined);
  } else if (effect === "shout") {
    await say(clip("shout"));
    state.shoutPending = true;
    state.shoutTries = 0;
    updateTalk();
  } else if (effect === "callback") {
    await say(clip("callback"));
    state.busy = false;
    state.callbackPending = true;
    updateTalk();
    // Talk and you stop her (a red flag). Stay quiet and she tries: it costs time and suspicion.
    state.callbackTimer = setTimeout(async () => {
      if (!state.callbackPending || state.over) return;
      state.callbackPending = false;
      state.busy = true;
      pop("YOU LET HER CHECK", "It costs time and suspicion. No red flag.", "move");
      await holdPhase(6, isPinky() ? "Pinky is looking you up online" : isDadaji() ? "Dadaji is ringing the branch" : `${who()} is calling the police station`, false);
      if (state.over) return;
      applyCounter("callback", false);
      await say(clip("callback_fail"));
      state.busy = false;
      updateTalk();
    }, 6000);
  } else if (effect === "pappu") {
    $("pappu").hidden = false;
    await say(clip("pappu"));
    await say(clip("pappu_voice"));
    state.pappuHere = true;
  }
  updateTalk();
}

function blockCheck() {
  clearTimeout(state.callbackTimer);
  state.callbackPending = false;
  post(`/api/game/${state.game.id}/counter`, { effect: "callback", passed: true });
  pop("YOU STOPPED HER CHECKING", "Red flag: real scammers never let you verify", "bad");
  sfx.warn();
}

// The cruellest move: she walks away while your clock keeps running.
async function holdPhase(seconds = 5 + rand(4), why = isPinky() ? "Pinky took another call" : isDadaji() ? "Dadaji has gone to find his spectacles" : "Dadi has gone to check the cooker", back = true) {
  $("away-why").textContent = why;
  state.lockedUntil = Date.now() + seconds * 1000;
  $("dadi-slot").classList.add("gone");
  $("away").hidden = false;
  bubble("");
  sfx.whistle();
  updateTalk();
  for (let left = seconds; left > 0 && !state.over; left--) {
    $("away-count").textContent = left;
    if ((seconds - left) % 3 === 0) sfx.holdMusic();
    await sleep(1000);
  }
  state.lockedUntil = 0;
  $("away").hidden = true;
  $("dadi-slot").classList.remove("gone");
  updateTalk();
  if (!state.over && back) await say(clip("hold_back"));
}

// ---------- Talk button: touch, mouse and spacebar ----------

const talk = $("b-talk");
talk.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  talk.setPointerCapture(e.pointerId);
  pressTalk();
});
talk.addEventListener("pointerup", releaseTalk);
talk.addEventListener("pointercancel", releaseTalk);
talk.addEventListener("contextmenu", (e) => e.preventDefault());
// Leaving the app mid-press would otherwise keep the line open.
window.addEventListener("blur", releaseTalk);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) releaseTalk();
  else resumeAudio();
});
window.addEventListener("pagehide", stopMic);

window.addEventListener("keydown", (e) => {
  if (e.code !== "Space" || e.repeat || $("s-game").hidden || document.activeElement === $("type-input")) return;
  e.preventDefault();
  pressTalk();
});
window.addEventListener("keyup", (e) => {
  if (e.code !== "Space" || $("s-game").hidden || document.activeElement === $("type-input")) return;
  e.preventDefault();
  releaseTalk();
});

$("b-type").addEventListener("click", () => {
  $("type-form").hidden = !$("type-form").hidden;
  if (!$("type-form").hidden) $("type-input").focus();
});

$("type-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("type-input").value.trim();
  if (!text || state.busy || state.over || Date.now() < state.lockedUntil) return;
  unlockAudio();
  $("type-input").value = "";
  if (state.speaking) hush();
  if (state.callbackPending) blockCheck();
  await handleSaid(text, 1, true);
});

$("b-hang").addEventListener("click", askLeave);

// ---------- How it ends ----------

async function endCall(outcome) {
  if (state.over) return;
  state.over = true;
  try { sessionStorage.removeItem("hu_live"); } catch (err) { /* private window */ }
  $("leave").hidden = true;
  clearInterval(state.timerId);
  clearTimeout(state.callbackTimer);
  hush();
  state.holding = false;
  $("b-talk").classList.remove("down");
  if (state.ws) state.ws.close();
  stopMic();
  updateTalk();

  let report = null;
  try {
    const resp = await post(`/api/game/${state.game.id}/end`, seenLessons());
    if (resp.ok) report = await resp.json();
  } catch (err) {
    console.warn(err);
  }
  state.report = report || { outcome, digits: 0, rank: "Chhota Chor", rank_line: "", gags: {}, lessons: [], missed: [], name: state.game.name };
  if (report && report.claimed_name) safeSet("dadi_name", report.claimed_name);
  const final = state.report.outcome || outcome;

  show("end");
  $("end-flash").className = "end-flash";
  $("crack-stage").hidden = true;
  document.querySelector(".end-stage").hidden = false;
  if (final === "cracked") {
    await crackedEnding();
  } else {
    await normalEnding(final);
  }
  if (state.report.turns) await flipRound();
  showReport();
}

async function normalEnding(outcome) {
  $("end-stamp").textContent = OUTCOME_STAMP[outcome] || "CALL OVER";
  const line = {
    busted: `${who()} worked you out. She has reported you to 1930, the real cyber-fraud helpline.`,
    timeout: "She out-talked you. The call ended and you got nothing.",
    hung_up: isPinky() ? "You ran away. She's already telling her group chat." : isDadaji() ? "You ran away. He's already writing it in his diary." : "You ran away. Dadi hasn't even finished telling you about her knee.",
    reformed: "You found the ending most callers never look for: you stopped, and told her the truth.",
  }[outcome] || "";
  $("end-line").textContent = line;
  if (outcome === "busted") {
    $("end-flash").classList.add("siren");
    sfx.siren();
    jolt();
    await say(clip(`busted_${state.game.mood}`));
  } else {
    await say(clip(outcome === "timeout" ? "timeout" : outcome === "reformed" ? "reformed" : "hung_up"));
  }
  await sleep(1000);
}

// The digits you fought for were never an OTP. They're the number she was calling.
async function crackedEnding() {
  document.querySelector(".end-stage").hidden = true;
  $("crack-stage").hidden = false;
  $("crack-kicker").textContent = "You did it. You got the OTP.";
  $("crack-number").classList.remove("merged");
  $("crack-name").textContent = "";
  $("crack-text").textContent = "";
  sfx.good();
  await sleep(1000);
  await say(clip(state.game.mood === "chai" ? "reveal_setup_chai" : "reveal_setup"));
  await sleep(500);
  // No siren here. The quiet is what lands.
  $("crack-kicker").textContent = "That was never an OTP.";
  $("crack-number").classList.add("merged");
  $("crack-name").textContent = "India's cyber-fraud helpline";
  jolt();
  const again = safeGet("dadi_seen_1930");
  await say(clip(again ? "reveal_again" : "reveal_1930"));
  safeSet("dadi_seen_1930", "1");
  if (again) {
    await sleep(500);
    $("crack-text").textContent = "You already knew this number. That was the point.";
    await sleep(2600);
    return;
  }
  await sleep(1000);
  $("crack-text").textContent = state.lang === "en" ? "Now do you get it?" : "Ab samjhe? Now do you get it?";
  await say(clip("reveal_samjhe"));
  await sleep(1400);
  $("crack-text").textContent = "You weren't learning how to get an OTP. You were learning what happens around one.";
  await sleep(3200);
  $("crack-text").textContent = `${state.game.name} is fictional. Real ${isPinky() ? "people" : isDadaji() ? "grandfathers" : "grandmothers"} don't get this ending.`;
  await sleep(2600);
  $("crack-text").textContent = "So make sure yours know the number.";
  await sleep(2200);
}

// ---------- The last round: now it's your phone ----------

// Playing the scammer only helps if you practise the other side. A stranger's
// voice reads the player's own best line, then asks for an OTP. All they have to
// do is what a real target should: hang up.
async function flipRound() {
  show("flip");
  $("flip-kicker").textContent = "Incoming call";
  $("flip-title").textContent = "Unknown number";
  $("flip-line").textContent = "";
  $("flip-note").textContent = "";
  $("flip-choices").hidden = true;
  $("b-flip-next").hidden = true;
  sfx.ring();

  let answer;
  const choice = new Promise((resolve) => { answer = resolve; });
  $("b-flip-hang").onclick = () => answer("hang");
  $("b-flip-otp").onclick = () => answer("otp");

  const run = ++state.speechRun;
  let ownWords = false;
  (async () => {
    await sleep(1200);
    const call = await post(`/api/game/${state.game.id}/flip`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (run !== state.speechRun) return;
    if (call && call.own_line) {
      ownWords = true;
      state.mirrorPattern = call.pattern;
      $("flip-line").textContent = `"${call.own_line}"`;
      $("flip-note").textContent = "Those are your words. It's someone else's voice.";
    } else {
      $("flip-note").textContent = "Same script. This time it's your phone.";
    }
    await playSpeech(call ? call.speech : clip("flip_open"), () => run !== state.speechRun);
    if (run !== state.speechRun) return;
    $("flip-choices").hidden = false;  // they hear the script out, as a real target would
    await say(clip("flip_ask"));
    if (run !== state.speechRun) return;
    await sleep(6000);  // no answer is an answer too
    answer("froze");
  })().catch((err) => { console.warn(err); answer("froze"); });

  const picked = await choice;
  hush();
  $("flip-choices").hidden = true;
  const hungUp = picked === "hang";
  post(`/api/game/${state.game.id}/flip/result`, { hung_up: hungUp });
  state.flipPicked = picked;
  const script = ownWords ? "your own script" : "the same script you just ran";
  const Script = ownWords ? "Your own script" : "The same script";
  $("flip-kicker").textContent = hungUp ? "You hung up" : picked === "froze" ? "You froze" : "You gave the OTP";
  $("flip-title").textContent = hungUp ? `That was ${script}. And you hung up.` : `${Script} just worked on you.`;
  $("flip-line").textContent = "";
  const familiar = ownWords && state.mirrorPattern ? `Sound familiar? That's the ${state.mirrorPattern} you used on her. ` : "";
  $("flip-note").textContent = familiar + (hungUp
    ? "Hang up, then tell someone you trust."
    : "That's the feeling to recognise. In a real call, just hang up.");
  if (hungUp) sfx.good(); else { sfx.bad(); jolt(); }
  $("b-flip-next").hidden = false;
  const heard = say(clip(hungUp ? "flip_pass" : "flip_fail"));
  await new Promise((resolve) => { $("b-flip-next").onclick = resolve; });
  hush();
  await heard;
}

// ---------- The report: a lesson in disguise ----------

function showReport() {
  const r = state.report;
  show("report");
  $("s-report").scrollTop = 0;
  $("r-mood").textContent = r.name;
  const unlock = unlockNext(r);
  $("r-unlock").hidden = !unlock;
  $("r-unlock").textContent = unlock;
  renderWho(r.who);
  rememberScenario(r.who && r.who.scenario && r.who.scenario.id);
  rememberScenario(r.who && r.who.temperament && `t:${r.who.temperament.label}`);
  rememberScenario(r.who && `r:${r.who.role || "dadi"}`);
  if (!state.game.demo) safeSet("dadi_calls", Number(safeGet("dadi_calls") || 0) + 1);  // Boss says less as you learn
  $("r-rank").textContent = r.rank;
  $("r-rankline").textContent = r.rank_line;
  $("r-crack").textContent = state.game.demo ? "" : !r.crack_rate ? "Nobody has got all four digits yet." : `Only ${r.crack_rate}% of callers ever get all four digits.`;

  $("r-otp").replaceChildren(...[0, 1, 2, 3].map((i) => {
    const slot = document.createElement("div");
    slot.className = "slot";
    if (i < r.digits) {
      slot.classList.add("got");
      slot.textContent = r.otp ? r.otp[i] : "✓";
    } else {
      slot.textContent = "?";
    }
    return slot;
  }));

  $("r-result").textContent = {
    cracked: "You got the OTP. It was 1930.", busted: "She caught you.", timeout: "She out-talked you.",
    hung_up: "You hung up.", reformed: "You stopped, and told her the truth.",
  }[r.outcome] || r.rank;
  // One learning moment from what actually happened, and one thing to remember. The rest waits below.
  const lesson = r.learning || { headline: "", why: r.rank_line, remember: "Real officials give you time. Pressure is the warning sign." };
  $("r-learn").textContent = lesson.headline;
  $("r-why").textContent = lesson.why;
  $("r-also").textContent = lesson.also || "";
  $("r-remember").textContent = lesson.remember;
  $("r-hook").textContent = lesson.next || "";
  noteLesson(lesson.type);
  $("r-more").open = Boolean(r.daily);  // daily players need the questions to post a score

  // What they actually did in the last round. It's the one choice we really saw.
  $("r-flip").textContent = { hang: "Then your phone rang, and you hung up.", otp: "Then your phone rang, and you gave the OTP.", froze: "Then your phone rang, and you froze." }[state.flipPicked] || "";

  const lessons = r.lessons || [];
  const used = new Set(lessons.map((l) => l.tactic));
  $("r-lesson-title").textContent = lessons.length ? "The script you just ran. Calls like this are built on these four parts." : "Scam calls like this are built on these four parts.";
  $("r-lessons").replaceChildren(...SCRIPT_PARTS.map((part) => {
    const card = document.createElement("div");
    const wasUsed = part.tactics.some((t) => used.has(t));
    card.className = `lesson${wasUsed ? " used" : ""}`;
    const b = document.createElement("b");
    b.textContent = part.label;
    const mark = document.createElement("small");
    mark.textContent = wasUsed ? "YOU USED THIS" : "";
    const line = document.createElement("p");
    line.textContent = part.line;
    card.append(b, mark, line);
    return card;
  }));

  renderScore(null);
  renderQuestions(r.questions || []);
  $("run").hidden = true;
  $("board").hidden = true;
  $("b-share").textContent = "Challenge a friend";
  $("b-again-daily").hidden = !state.daily || r.daily || state.game.demo;

  const missed = r.missed || [];
  $("r-tip").textContent = missed.length ? `You never tried: ${missed.join(", ")}.` : "";
  $("r-next").textContent = "Next call, someone else picks up. Work them out faster.";

  // Dadi says the lesson that fits the last trick you used.
  const last = lessons.length ? lessons[lessons.length - 1].tactic : "fear";
  say(clip(`lesson_${last}`));
}

// ---------- Who picked up: only revealed once the call is over ----------

function renderWho(who) {
  $("who").hidden = !who;
  if (!who) return;
  $("who-name").textContent = `${who.name}, ${who.age}`;
  $("who-scene").textContent = who.scene;
  const items = [
    ...(who.scenario ? [{ reveal: who.scenario.reveal, tell: who.scenario.tell }] : []),
    { reveal: who.temperament.label, tell: who.temperament.tell }, ...who.traits,
  ];
  $("who-list").replaceChildren(...items.map((item) => {
    const li = document.createElement("li");
    const b = document.createElement("b");
    b.textContent = item.reveal;
    const tell = document.createElement("span");
    tell.textContent = `The clue: ${item.tell}`;
    li.append(b, tell);
    return li;
  }));
  $("who-play").textContent = `What worked best on her: ${TACTIC_NAMES[who.works]}. What worked worst: ${TACTIC_NAMES[who.fails]}.`;
}

// Lessons this browser has seen: repeats come back shorter, and last time's lesson gives way.
function seenLessons() {
  try { return { seen: JSON.parse(safeGet("dadi_seen") || "{}"), last: safeGet("dadi_last_lesson") }; } catch (err) { return {}; }
}

function noteLesson(type) {
  if (!type || state.game.demo) return;
  const { seen = {} } = seenLessons();
  seen[type] = (seen[type] || 0) + 1;
  safeSet("dadi_seen", JSON.stringify(seen));
  safeSet("dadi_last_lesson", type);
}

// The last few situations this browser saw, so free play doesn't repeat them back to back.
function recentScenarios() {
  try { return JSON.parse(safeGet("dadi_recent") || "[]").slice(0, 8); } catch (err) { return []; }
}

function rememberScenario(id) {
  if (!id || state.game.demo) return;
  // Keep each kind (scenario, temper, person) in its own short history, newest first.
  const kind = (x) => (x.includes(":") ? x.split(":")[0] : "s");
  const keep = [id, ...recentScenarios().filter((x) => x !== id)];
  const counts = {};
  safeSet("dadi_recent", JSON.stringify(keep.filter((x) => (counts[kind(x)] = (counts[kind(x)] || 0) + 1) <= (kind(x) === "r" ? 3 : 2)).slice(0, 8)));
}

// Development only: the server sends this when it runs with DEBUG=1.
function showDebug(profile) {
  $("debug-card").hidden = !profile;
  if (profile) $("debug-card").textContent = JSON.stringify(profile, null, 1).replace(/[{}"]/g, "").trim();
}

// ---------- Nazar Score: the call, plus what you spotted in it ----------

function renderScore(graded) {
  const r = state.report;
  const parts = { ...(graded ? graded.call : r.call_score) };
  delete parts.total;
  if (graded) parts.knowledge = graded.knowledge;
  $("s-num").textContent = graded ? graded.score : "?";
  $("s-tier").textContent = graded ? graded.tier : "Answer 3 questions";
  $("s-tierline").textContent = graded ? graded.tier_line : "They're about your own call. Then you get your score.";
  $("s-parts").replaceChildren(...Object.entries(parts).filter(([k, v]) => v || k === "progress").map(([k, v]) => {
    const chip = document.createElement("span");
    chip.className = `part${v < 0 ? " minus" : ""}`;
    chip.textContent = `${PARTS[k] || k} ${v > 0 ? "+" : ""}${v}`;
    return chip;
  }));
  $("s-best").textContent = "";
}

function renderQuestions(questions) {
  const picks = questions.map(() => null);
  $("quiz").hidden = !questions.length;
  $("b-answers").disabled = true;
  $("b-answers").hidden = false;
  $("q-list").replaceChildren(...questions.map((q, i) => {
    const box = document.createElement("div");
    box.className = "q";
    const text = document.createElement("p");
    text.textContent = `${i + 1}. ${q.q}`;
    box.append(text);
    q.options.forEach((option, j) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "opt";
      b.textContent = option;
      b.onclick = () => {
        if (state.graded) return;
        sfx.tap();
        picks[i] = j;
        box.querySelectorAll(".opt").forEach((o, k) => o.classList.toggle("picked", k === j));
        $("b-answers").disabled = picks.includes(null);
      };
      box.append(b);
    });
    return box;
  }));
  $("b-answers").onclick = () => lockAnswers(picks);
}

async function lockAnswers(picks) {
  $("b-answers").disabled = true;
  const graded = await post(`/api/game/${state.game.id}/answers`, { answers: picks })
    .then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!graded) {
    $("b-answers").disabled = false;
    pop("COULDN'T CHECK THOSE", "Try again in a moment", "move");
    return;
  }
  state.graded = graded;
  $("b-answers").hidden = true;
  document.querySelectorAll("#q-list .q").forEach((box, i) => {
    box.querySelectorAll(".opt").forEach((o, k) => {
      o.classList.toggle("right", k === graded.answers[i]);
      o.classList.toggle("wrong", k === picks[i] && !graded.correct[i]);
    });
  });
  const right = graded.correct.filter(Boolean).length;
  if (right === 3) sfx.good(); else if (!right) sfx.bad();
  renderScore(graded);
  $("s-best").textContent = personalBest(graded.score, graded);
  $("b-share").textContent = `Challenge a friend to beat ${graded.score}`;
  renderRun();
  renderBoard();
}

// Your best, per Dadi, and a streak for days you play today's Dadi.
function personalBest(score, graded) {
  if (state.game.demo) return "Demo run: not counted.";
  if (graded && graded.player) {  // signed in: saved to the account
    const before = account.player ? account.player.stats.best_score : 0;
    const had = account.player && account.player.stats.completed;
    const rank = graded.player.rank ? ` You're #${graded.player.rank} on the all-time board.` : "";
    refreshAccount();
    if (!had) return `Your first score, saved to ${account.user.username}. Now beat it.${rank}`;
    return (score > before ? `New personal best! (was ${before})` : `Your best: ${graded.player.best_score}.`) + rank;
  }
  const r = state.report;
  const notes = [];
  const best = Number(safeGet("dadi_best") || 0);
  if (score > best) {
    safeSet("dadi_best", score);
    notes.push(best ? `New personal best! (was ${best})` : "Your first score. Now beat it.");
  } else {
    notes.push(`Your best: ${best}.`);
  }
  if (r.daily) {
    const day = istDate();
    const yesterday = istDate(Date.now() - 86400000);
    const last = safeGet("dadi_daily_last");
    const streak = last === day ? Number(safeGet("dadi_streak") || 1) : last === yesterday ? Number(safeGet("dadi_streak") || 0) + 1 : 1;
    safeSet("dadi_daily_last", day);
    safeSet("dadi_streak", streak);
    if (streak > 1) notes.push(`${streak}-day streak.`);
  }
  if (!account.user) notes.push("Sign in to keep it.");
  return notes.join(" ");
}

function istDate(at = Date.now()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date(at));
}

// The run, moment by moment. Their own words are shown only to them, and never kept.
function renderRun() {
  const replay = state.report.replay || { events: [] };
  if (!replay.events.length) return;
  $("run").hidden = false;
  $("run-list").replaceChildren(...replay.events.map((e) => {
    const li = document.createElement("li");
    li.className = ["ev", e.susp >= 8 && "bad", e.trust >= 10 && "good", e.flag && "flag", e.turning && "turning"].filter(Boolean).join(" ");
    const time = document.createElement("span");
    time.className = "t";
    time.textContent = e.at;
    const name = document.createElement("b");
    name.textContent = e.name + (e.digits ? ` · +${e.digits} digit${e.digits > 1 ? "s" : ""}` : "");
    const deltas = document.createElement("em");
    deltas.textContent = [e.trust && `trust ${e.trust > 0 ? "▲" : "▼"}${Math.abs(e.trust)}`, e.susp && `suspicion ${e.susp > 0 ? "▲" : "▼"}${Math.abs(e.susp)}`].filter(Boolean).join(" · ");
    li.append(time, name, deltas);
    if (e.said) {
      const said = document.createElement("q");
      said.textContent = e.said;
      li.append(said);
    }
    return li;
  }));
  const turn = replay.turning;
  $("run-turn").hidden = !turn;
  if (turn) {
    $("run-turn-title").textContent = `${turn.title} · ${replay.events[turn.index].at}`;
    $("run-turn-why").textContent = turn.why;
    $("run-turn-flag").textContent = turn.flag;
  }
}

// Today's challenge has a board. Scores come from the server's own record of the call.
function renderBoard() {
  const r = state.report;
  if (!r.daily) return;
  $("board").hidden = false;
  $("board-form").hidden = true;
  showBoard(state.daily ? state.daily.top : []);
  if (!r.ranked) {
    $("board-note").textContent = "This run can't be ranked: the AI was offline for too much of the call. Try again later.";
    return;
  }
  if (!r.saved) {
    $("board-note").textContent = "Sign in before your next daily call to get on the board.";
    return;
  }
  $("board-note").textContent = "Checking the board…";
  post(`/api/game/${state.game.id}/submit`).then((resp) => (resp.ok ? resp.json() : null)).catch(() => null).then((data) => {
    if (!data) {
      $("board-note").textContent = "Couldn't reach the board. Your score is still saved.";
      return;
    }
    $("board-note").textContent = data.rank ? `You're #${data.rank} of ${data.of} today, as ${account.user.username}.` : "Your score is saved.";
    showBoard(data.top, data.rank);
    sfx.good();
  });
}

function showBoard(top, mine) {
  $("board-list").replaceChildren(...top.map((e, i) => {
    const li = document.createElement("li");
    if (mine && i + 1 === mine) li.className = "mine";
    li.textContent = `${e.name} · ${e.score}${e.boss_off ? " · no Boss" : ""}`;
    return li;
  }));
}

$("board-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("board-name").value.trim();
  if (name.length < 2) return;
  const resp = await post(`/api/game/${state.game.id}/submit`, { name }).catch(() => null);
  const data = resp ? await resp.json().catch(() => null) : null;
  if (!resp || !resp.ok) {
    $("board-note").textContent = (data && data.detail) || "Couldn't post that. Try again.";
    return;
  }
  safeSet("dadi_nick", name);
  $("board-form").hidden = true;
  $("board-note").textContent = data.rank ? `You're #${data.rank} of ${data.of} today.` : `Posted. The top ${data.of} are below.`;
  showBoard(data.top, data.rank);
  sfx.good();
});

$("b-again-daily").addEventListener("click", () => {
  unlockAudio();
  hush();
  sfx.tap();
  state.mode = "daily";
  show("brief");
});

$("b-again").addEventListener("click", () => {
  unlockAudio();
  hush();
  sfx.tap();
  loadStats();
  show("brief");
});

// ---------- Sharing ----------

const SITE = location.origin;

function challengeLink() {
  const r = state.report;
  return `${SITE}/?c=${r.code}${state.graded ? `&s=${state.graded.score}` : ""}${state.lang === "en" ? "&lang=en" : ""}`;
}

function shareText() {
  const r = state.report;
  if (state.graded && !state.game.demo) {
    return `I scored ${state.graded.score}/100 (${state.graded.tier}) against ${r.name} on Hang Up. Same call, same moves. Beat me, and learn how the real scam works: ${challengeLink()}`;
  }
  const line = r.outcome === "reformed"
    ? `I tried to fool ${r.name} on Hang Up. Then I confessed. She asked if I'd eaten.`
    : r.outcome === "cracked"
    ? `I got all 4 digits of ${r.name}'s OTP on Hang Up. Then she got me.`
    : `I tried to fool ${r.name} and got ${r.digits} of 4 OTP digits. Rank: ${r.rank}. She got me.`;
  return `${line} Try it, and learn how the real scam works: ${state.game.demo ? SITE : challengeLink()}`;
}

// A result card drawn on canvas, ready for a post or a status.
async function drawCard() {
  const r = state.report;
  await document.fonts.ready;
  const c = document.createElement("canvas");
  c.width = 1080;
  c.height = 1350;
  const g = c.getContext("2d");
  g.fillStyle = "#4a1398";
  g.fillRect(0, 0, 1080, 1350);
  g.save();
  g.translate(540, 560);
  for (let i = 0; i < 24; i++) {
    g.rotate(Math.PI / 12);
    if (i % 2) {
      g.fillStyle = "#5a1cb3";
      g.beginPath();
      g.moveTo(0, 0);
      g.lineTo(-180, -1400);
      g.lineTo(180, -1400);
      g.fill();
    }
  }
  g.restore();

  const outlined = (text, x, y, size, fill, shadow = "#1b0b2e") => {
    g.font = `${size}px Bungee`;
    g.textAlign = "center";
    g.fillStyle = shadow;
    g.fillText(text, x + size * 0.06, y + size * 0.06);
    g.fillStyle = fill;
    g.fillText(text, x, y);
  };
  // The logo: HANG UP and the red end-call button.
  g.font = "112px Bungee";
  const word = g.measureText("HANG UP").width;
  const left = 540 - (word + 130) / 2;
  outlined("HANG UP", left + word / 2, 150, 112, "#ffb300");
  const bx = left + word + 70, by = 112;
  g.fillStyle = "#1b0b2e";
  g.beginPath();
  g.arc(bx + 7, by + 7, 54, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = "#ff2d2d";
  g.strokeStyle = "#1b0b2e";
  g.lineWidth = 8;
  g.beginPath();
  g.arc(bx, by, 50, 0, Math.PI * 2);
  g.fill();
  g.stroke();
  g.save();
  g.translate(bx - 36, by - 36);
  g.scale(3, 3);
  g.fillStyle = "#fff";
  g.fill(new Path2D(document.querySelector(".end-call path").getAttribute("d")));
  g.restore();

  const art = new Image();
  const svg = (document.querySelector("#dadi-slot .dadi") || document.querySelector("#s-title .dadi")).cloneNode(true);
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  svg.setAttribute("width", "520");
  svg.setAttribute("height", "572");
  svg.querySelector(".d-mouth").style.display = "none";
  art.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(svg))}`;
  await new Promise((res) => { art.onload = res; art.onerror = res; });
  if (art.complete && art.naturalWidth) g.drawImage(art, 280, 190, 520, 572);

  g.fillStyle = "#ffb300";
  g.strokeStyle = "#1b0b2e";
  g.lineWidth = 10;
  const rankSize = r.rank.length > 15 ? 62 : 76;
  g.font = `${rankSize}px Bungee`;
  const w = Math.min(1000, g.measureText(r.rank).width + 90);
  g.save();
  g.translate(540, 740);
  g.rotate(-0.03);
  g.beginPath();
  g.roundRect(-w / 2, -70, w, 124, 22);
  g.fill();
  g.stroke();
  g.fillStyle = "#1b0b2e";
  g.textAlign = "center";
  g.fillText(r.rank, 0, 16);
  g.restore();

  const tile = 130;
  for (let i = 0; i < 4; i++) {
    const x = 540 - (tile * 4 + 66) / 2 + i * (tile + 22);
    const got = i < r.digits;
    g.fillStyle = got ? "#ffb300" : "#1b0b2e";
    g.strokeStyle = "#1b0b2e";
    g.beginPath();
    g.roundRect(x, 830, tile, 150, 18);
    g.fill();
    g.stroke();
    g.font = "76px Bungee";
    g.textAlign = "center";
    g.fillStyle = got ? "#1b0b2e" : "#8f77b5";
    g.fillText(got ? "✓" : "?", x + tile / 2, 932);  // never spoil the ending
  }

  g.textAlign = "center";
  g.fillStyle = "#fff3d6";
  g.font = "700 46px 'Baloo 2'";
  const top = Object.entries(r.gags || {}).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1])[0];
  g.fillText(r.name || "", 540, 1055);
  g.font = "700 40px 'Baloo 2'";
  if (state.graded) g.fillText(`Nazar Score ${state.graded.score}/100 · ${state.graded.tier}`, 540, 1112);
  else if (top) g.fillText(`${GAG_LABELS[top[0]].replace(/^\S+\s/, "")} × ${top[1]}`, 540, 1112);
  outlined(state.graded ? "CAN YOU BEAT ME?" : "CAN YOU BEAT HER?", 540, 1205, 64, "#ffffff", "#ff2e7e");
  g.fillStyle = "#fff3d6";
  g.font = "700 36px 'Baloo 2'";
  g.fillText(`${SITE.replace(/^https?:\/\//, "")}  ·  Real scam? Call 1930`, 540, 1290);
  return new Promise((res) => c.toBlob(res, "image/png"));
}

function saveFile(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

$("b-share").addEventListener("click", async () => {
  sfx.tap();
  const blob = await drawCard();
  const file = new File([blob], "hang-up.png", { type: "image/png" });
  const text = shareText();
  try {
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], text });
      return;
    }
  } catch (err) {
    if (err.name === "AbortError") return;
  }
  saveFile(blob, "hang-up.png");
  try { await navigator.clipboard.writeText(text); } catch (err) { console.warn(err); }
  pop("CARD SAVED, TEXT COPIED", "", "good");
  $("b-share").textContent = "Saved! Text copied";
});

$("b-parents").addEventListener("click", async () => {
  sfx.tap();
  const message = state.lang === "en"
    ? "Please listen to this short message from Dadi. It's about people who call pretending to be police or CBI. If anyone asks for an OTP or money, cut the phone and call 1930."
    : "कृपया ये दादी का छोटा सा मैसेज सुनिए। फ़ोन पर पुलिस या CBI बनकर ठगने वालों से बचने के लिए ज़रूरी है। कोई OTP या पैसे माँगे तो फ़ोन काटिए और 1930 पर कॉल कीजिए।";
  try {
    const blob = await (await fetch(clip("parents"))).blob();
    const file = new File([blob], "Dadi-ka-message.mp3", { type: "audio/mpeg" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], text: message });
      return;
    }
    saveFile(blob, "Dadi-ka-message.mp3");
  } catch (err) {
    if (err.name === "AbortError") return;
    console.warn(err);
  }
  window.open(`https://wa.me/?text=${encodeURIComponent(`${message} ${SITE}${clipPath("parents")}`)}`, "_blank", "noopener");
});

$("b-parents-play").addEventListener("click", () => {
  unlockAudio();
  say(clip("parents"));
});

// ---------- Real help, always one tap away ----------

function openSos() {
  $("sos-sheet").hidden = false;
}
$("b-sos").addEventListener("click", openSos);
$("b-sos-2").addEventListener("click", openSos);
$("b-sos-close").addEventListener("click", () => { $("sos-sheet").hidden = true; });

// ---------- Small things ----------

// ?hour=23 meets another Dadi on demand, for demos and recording.
function forcedHour() {
  const h = new URLSearchParams(location.search).get("hour");
  return h !== null && Number(h) >= 0 && Number(h) <= 23 ? Number(h) : null;
}

// ?demo=1 plays the same call every time, for recording. Speech and replies stay live.
function demoMode() {
  return new URLSearchParams(location.search).get("demo") === "1";
}

function safeGet(key) {
  try { return localStorage.getItem(key); } catch (err) { return null; }
}
function safeSet(key, value) {
  try { localStorage.setItem(key, value); } catch (err) { /* private window */ }
}

loadStats();
recoverDroppedCall();
refreshAccount();

// ?trailer=1: a fixed, recordable cut of a real call (trailer.js). Nothing loads unless asked for.
if (new URLSearchParams(location.search).get("trailer") === "1") {
  document.body.append(Object.assign(document.createElement("script"), { src: "trailer.js" }));
}
