// Scam Dadi: the call. The server holds the OTP and the rules; this file is the
// stage, the controls and the sound.

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (n) => Math.floor(Math.random() * n);
const post = (url, body) => fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

const SHOUT_LEVEL = 0.32;      // how loud "louder!" means, on the 0-1 meter
const COUNTER_NOTES = {
  hold: ["DADI PUTS YOU ON HOLD", "Real defence: slow them down. Scams need you rushed.", "Hold pe daal diya! Line mat kaat. Asli scammers ghanton line pe rakhte hain, isi liye ghar waalon ko pata nahi chalta."],
  shout: ["DADI CAN'T HEAR YOU", "Real defence: make them repeat. Scripts fall apart.", "Zor se bol! Button dabake chilla, warna shak badhega."],
  callback: ["DADI WILL CALL THE THANA", "Real defence: hang up and check it yourself.", "Rok use! Thane ne sach bata diya to khel khatam. Isi liye scammers kabhi call back nahi karne dete. Jaldi bol!"],
  pappu: ["DADI GETS PAPPU", "Real defence: bring in family. One call ends most scams.", "Khatra! Ghar waale aa gaye. Isi liye scammers bolte hain 'kisi ko mat batana'."],
};
const GAG_LABELS = {
  knee: "🦵 Ghutna", food: "🍛 Khana khaya?", shaadi: "💍 Shaadi kab?",
  chashma: "👓 Chashma lost", pappu: "🧑‍💻 Pappu", scooter: "🛵 The scooter",
};
const OUTCOME_STAMP = { busted: "BUSTED", timeout: "TIME UP", hung_up: "YOU FLED", cracked: "CRACKED" };
const NEXT_DADI = [
  "Morning: Puja Dadi", "Late morning: Serial Dadi", "Afternoon: Sleepy Dadi",
  "Evening: Kitty Party Dadi", "Night: Lonely Night Dadi",
];

const state = {
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
  speechRun: 0,         // lets a press interrupt whatever Dadi is saying
  report: null,
};

// ---------- Dadi art ----------

const art = $("dadi-art");
document.querySelectorAll("[data-dadi]").forEach((el) => el.append(art.content.cloneNode(true)));

// ---------- Sound: one context, one voice channel ----------

const audio = { ctx: null, voice: new Audio(), analyser: null, connected: false, mouthData: null };
audio.voice.preload = "auto";

function unlockAudio() {
  if (!audio.ctx) audio.ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (audio.ctx.state === "suspended") audio.ctx.resume();
  if (!audio.connected) {
    try {
      const source = audio.ctx.createMediaElementSource(audio.voice);
      audio.analyser = audio.ctx.createAnalyser();
      audio.analyser.fftSize = 256;
      audio.mouthData = new Uint8Array(audio.analyser.fftSize);
      source.connect(audio.analyser);
      audio.analyser.connect(audio.ctx.destination);
      audio.connected = true;
      requestAnimationFrame(moveMouth);
    } catch (err) {
      console.warn("Lip sync unavailable", err);
    }
  }
}

// Dadi's mouth follows her real voice.
function moveMouth() {
  if (audio.analyser && !audio.voice.paused) {
    audio.analyser.getByteTimeDomainData(audio.mouthData);
    let sum = 0;
    for (const v of audio.mouthData) sum += (v - 128) ** 2;
    const level = Math.min(1, Math.sqrt(sum / audio.mouthData.length) / 40);
    document.documentElement.style.setProperty("--mouth", level.toFixed(2));
  } else {
    document.documentElement.style.setProperty("--mouth", "0");
  }
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
  drain() { for (let i = 0; i < 14; i++) tone(1200 - i * 70, 0.09, { at: i * 0.11, gain: 0.04 }); },
};

function haptic(ms) { if (navigator.vibrate) navigator.vibrate(ms); }

// Play a clip on Dadi's voice channel. A new press of the talk button cuts her off.
function say(url, { onEnded } = {}) {
  return new Promise((resolve) => {
    const v = audio.voice;
    const finish = () => {
      v.onended = v.onerror = null;
      state.speaking = false;
      updateTalk();
      if (onEnded) onEnded();
      resolve();
    };
    v.onended = finish;
    v.onerror = finish;
    audio.stop = finish;
    v.src = url;
    state.speaking = true;
    updateTalk();
    v.play().catch(finish);
  });
}

function hush() {
  state.speechRun++;
  audio.voice.pause();
  if (audio.stop) audio.stop();
}

const clip = (name) => `/audio/${name}.mp3`;

// ---------- Screens ----------

function show(name) {
  for (const id of ["title", "brief", "ring", "game", "end", "report"]) $(`s-${id}`).hidden = id !== name;
  document.body.classList.toggle("in-game", name === "game" || name === "report");
}

function bubble(text) {
  const b = $("bubble");
  b.hidden = !text;
  if (text) {
    b.textContent = text;
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

function setBoss(boss, tag) {
  if (!boss) return;
  $("boss-line").textContent = boss.text;
  $("boss-tag").textContent = tag || `· Next: ${boss.label}`;
  $("boss").classList.remove("new");
  void $("boss").offsetWidth;
  $("boss").classList.add("new");
  sfx.radio();
  document.querySelectorAll(".trick").forEach((el) => el.classList.toggle("next", el.dataset.id === boss.tactic && !el.classList.contains("used")));
}

function setBossText(text, tag) {
  $("boss-line").textContent = text;
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
  else if (state.busy) label.textContent = "DADI IS THINKING";
  else if (state.callbackPending) label.textContent = "QUICK! STOP HER!";
  else if (state.shoutPending) label.textContent = "HOLD AND SHOUT!";
  else if (state.speaking) label.textContent = "HOLD TO INTERRUPT";
  else label.textContent = "HOLD TO TALK";
}

// ---------- Title ----------

async function loadStats() {
  try {
    const s = await (await fetch("/api/stats")).json();
    $("st-plays").textContent = s.plays.toLocaleString("en-IN");
    $("st-rate").textContent = s.cracked.toLocaleString("en-IN");
    $("st-mins").textContent = s.minutes.toLocaleString("en-IN");
  } catch (err) {
    console.warn(err);
  }
}

$("b-start").addEventListener("click", () => {
  unlockAudio();
  sfx.tap();
  show("brief");
});

for (const btn of document.querySelectorAll("[data-quiz]")) {
  btn.addEventListener("click", () => {
    unlockAudio();
    sfx.tap();
    state.quizBefore = btn.dataset.quiz === "true";
    beginCall();
  });
}

// ---------- Microphone ----------

const mic = { ctx: null, stream: null, ready: false };

async function startMic() {
  if (mic.ready) return true;
  try {
    mic.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: false, autoGainControl: true },
    });
    const ctx = audio.ctx;
    await ctx.audioWorklet.addModule("/pcm-worklet.js");
    const worklet = new AudioWorkletNode(ctx, "pcm-worklet");
    worklet.port.onmessage = (e) => onMicFrame(e.data);
    ctx.createMediaStreamSource(mic.stream).connect(worklet);
    // Chrome only runs nodes that lead to the speakers, so route through silence.
    const mute = ctx.createGain();
    mute.gain.value = 0;
    worklet.connect(mute).connect(ctx.destination);
    mic.ready = true;
    return true;
  } catch (err) {
    console.warn("No microphone", err);
    return false;
  }
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
  const ws = new WebSocket(`${proto}://${location.host}/ws/listen`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = (e) => {
    const event = JSON.parse(e.data);
    if (event.type === "speech_start") state.pendingSegments++;
    if (event.type === "partial_transcript") {
      state.partial = event.text || "";
      $("you-said").textContent = state.partial;
    }
    if (event.type === "transcript" || event.type === "final_transcript") {
      state.pendingSegments = Math.max(0, state.pendingSegments - 1);
      if (event.text) state.finals.push(event.text);
      state.partial = "";
      $("you-said").textContent = state.finals.join(" ");
    }
    if (event.type === "flushed") state.flushed = true;
    if (event.type === "error") console.warn("Speech:", event.message);
  };
  state.ws = ws;
  return new Promise((resolve) => {
    ws.onopen = () => resolve(true);
    ws.onerror = () => resolve(false);
  });
}

// ---------- Starting the call ----------

async function beginCall() {
  $("brief-error").hidden = true;
  // Never let an unanswered permission prompt freeze the game; typing still works.
  const hasMic = await Promise.race([startMic(), sleep(15000).then(() => false)]);
  const returning = safeGet("dadi_name");
  let data;
  try {
    const resp = await post("/api/game/start", {
      hour: forcedHour() ?? new Date().getHours(),
      returning_name: returning,
      quiz: state.quizBefore,
    });
    if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail || "Dadi isn't answering. Try again in a minute.");
    data = await resp.json();
  } catch (err) {
    $("brief-error").textContent = err.message;
    $("brief-error").hidden = false;
    return;
  }
  Object.assign(state, {
    game: data, secondsLeft: data.seconds, over: false, busy: false, holding: false, lockedUntil: 0,
    shoutPending: false, shoutTries: 0, callbackPending: false, pappuHere: false, pendingDigits: [],
    finals: [], partial: "", idleCount: 0, gags: {}, report: null,
  });
  buildCallScreen(data, hasMic);

  $("ring-mood").textContent = data.mood_name;
  $("ring-tag").textContent = data.tagline;
  show("ring");
  sfx.ring();
  if (hasMic) await openListener();
  await sleep(1400);
  sfx.ring();
  await sleep(1500);

  show("game");
  setBossText(data.intel, `· Intel on ${data.mood_name}`);
  setSuspicion(data.suspicion);
  pop(data.mood_name.toUpperCase(), data.twist);
  await say(clip(data.greet));
  if (!state.over) setBoss(data.boss, "· Your first move");
  startTimer();
  state.idleAt = Date.now() + 14000;
}

function buildCallScreen(data, hasMic) {
  document.querySelectorAll(".slot").forEach((s) => {
    s.textContent = "?";
    s.className = "slot";
  });
  $("tricks").replaceChildren(...data.playbook.map((t) => {
    const el = document.createElement("div");
    el.className = "trick";
    el.dataset.id = t.id;
    el.textContent = t.label;
    return el;
  }));
  bubble("");
  $("you-said").textContent = "";
  $("pappu").hidden = true;
  $("away").hidden = true;
  $("dadi-slot").className = "dadi-slot";
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
  if (state.over || state.busy || Date.now() < state.lockedUntil) {
    $("b-talk").classList.remove("nope");
    void $("b-talk").offsetWidth;
    $("b-talk").classList.add("nope");
    return;
  }
  unlockAudio();
  if (state.speaking) {
    hush();
    pop("YOU INTERRUPTED DADI", "", "gag");
  }
  state.holding = true;
  state.peak = 0;
  state.finals = [];
  state.partial = "";
  state.pendingSegments = 0;
  state.flushed = false;
  $("you-said").textContent = "";
  $("b-talk").classList.add("down");
  sfx.tap();
  haptic(20);
  if (state.callbackPending) {
    clearTimeout(state.callbackTimer);
    state.callbackPending = false;
    post(`/api/game/${state.game.id}/counter`, { effect: "callback", passed: true });
    pop("STOPPED HER!", "", "good");
  }
  if (state.ws && state.ws.readyState !== WebSocket.OPEN && state.ws.readyState !== WebSocket.CONNECTING) openListener();
  updateTalk();
}

async function releaseTalk() {
  if (!state.holding) return;
  state.holding = false;
  $("b-talk").classList.remove("down");
  $("b-talk").style.setProperty("--level", "0");
  state.busy = true;
  updateTalk();
  const text = await collectSpeech();
  state.busy = false;
  if (state.over) return;
  await handleSaid(text, state.peak);
}

// Let Prisma finish the words it's still working on.
async function collectSpeech() {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send("flush");
    const deadline = Date.now() + 2800;
    while (Date.now() < deadline && !(state.flushed && state.pendingSegments === 0)) await sleep(60);
  }
  const text = [...state.finals, state.partial].join(" ").trim();
  state.finals = [];
  state.partial = "";
  return text;
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
        pop("TOO QUIET!", "Dadi gets suspicious", "bad");
      }
      await say(clip("shout_fail"));
      updateTalk();
      return;
    }
    state.shoutPending = false;
    applyCounter("shout", true);
    pop("SHE HEARD YOU", "", "good");
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
  let result = null;
  try {
    const resp = await post(`/api/game/${game.id}/turn`, { said: text });
    if (resp.ok) result = await resp.json();
  } catch (err) {
    console.warn(err);
  }
  await reacting;
  state.busy = false;
  if (state.over) return;
  if (!result) {
    await say(clip(`canned_${rand(6)}`));
    return;
  }
  if (run === state.speechRun || !state.speaking) showMoveResult(result);
  if (stale()) return;

  bubble(result.reply);
  if (result.speech) {
    const speechReady = await fetch(result.speech).then((r) => (r.ok ? r.blob() : null)).catch(() => null);
    if (stale()) return;
    if (speechReady) await say(URL.createObjectURL(speechReady));
    else await sleep(1600);
  }
  if (stale()) return;

  state.pendingDigits.push(...result.digits);
  await revealDigits(run);
  if (stale()) return;

  if (result.outcome) {
    await endCall(result.outcome);
    return;
  }
  if (result.effect) await runCounter(result.effect);
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
  setSuspicion(r.suspicion);
  const trick = document.querySelector(`.trick[data-id="${move.tactic}"]`);
  const notes = move.notes || [];
  if (notes.includes("contradiction")) {
    pop("SHE CAUGHT YOUR LIE", "Real scammers slip too. Ask them to repeat their details.", "bad");
    sfx.bad();
    jolt();
  } else if (notes.includes("too_soon")) {
    pop("TOO SOON!", "You asked before building a story", "bad");
    sfx.bad();
    jolt();
  } else if (notes.includes("repeat")) {
    pop("SAME TRICK AGAIN?", "Dadi noticed. Try something else.", "bad");
    sfx.warn();
  } else if (notes.includes("off_script")) {
    pop("THAT WASN'T A SCAM MOVE", "Boss is shaking his head", "gag");
  } else if (trick) {
    pop(`${trick.textContent.toUpperCase()}!`, move.trust_gain >= 10 ? "It's working" : "Weak. She's barely listening", move.trust_gain >= 10 ? "good" : "");
    sfx.trick();
  }
  if (trick && !trick.classList.contains("used")) trick.classList.add("used");
  $("dadi-slot").classList.toggle("fond", r.trust >= 55);
  setBoss(r.boss);
  for (const gag of r.gags || []) {
    state.gags[gag] = (state.gags[gag] || 0) + 1;
    if (GAG_LABELS[gag]) setTimeout(() => pop(`+1 ${GAG_LABELS[gag]}`, "", "gag"), 500);
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
    });
}

async function runCounter(effect) {
  const note = COUNTER_NOTES[effect];
  if (note) {
    pop(note[0], note[1], "move");
    setBossText(note[2], "· She's fighting back");
  }
  if (effect === "hold") {
    await say(clip("hold"));
    await holdPhase();
  } else if (effect === "shout") {
    await say(clip("shout"));
    state.shoutPending = true;
    state.shoutTries = 0;
    updateTalk();
  } else if (effect === "callback") {
    await say(clip("callback"));
    state.callbackPending = true;
    updateTalk();
    state.callbackTimer = setTimeout(async () => {
      if (!state.callbackPending || state.over) return;
      state.callbackPending = false;
      applyCounter("callback", false);
      pop("YOU LET HER CHECK", "Suspicion up", "bad");
      jolt();
      await say(clip("callback_fail"));
    }, 5000);
  } else if (effect === "pappu") {
    $("pappu").hidden = false;
    await say(clip("pappu"));
    await say(clip("pappu_voice"));
    state.pappuHere = true;
  }
  updateTalk();
}

// The cruellest move: she walks away while your clock keeps running.
async function holdPhase() {
  const seconds = 5 + rand(4);
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
  if (!state.over) await say(clip("hold_back"));
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
  $("type-input").value = "";
  if (state.speaking) hush();
  if (state.callbackPending) {
    clearTimeout(state.callbackTimer);
    state.callbackPending = false;
    post(`/api/game/${state.game.id}/counter`, { effect: "callback", passed: true });
  }
  await handleSaid(text, 1, true);
});

$("b-hang").addEventListener("click", () => endCall("hung_up"));

// ---------- How it ends ----------

async function endCall(outcome) {
  if (state.over) return;
  state.over = true;
  clearInterval(state.timerId);
  clearTimeout(state.callbackTimer);
  hush();
  state.holding = false;
  $("b-talk").classList.remove("down");
  if (state.ws) state.ws.close();
  updateTalk();

  let report = null;
  try {
    report = await (await post(`/api/game/${state.game.id}/end`)).json();
  } catch (err) {
    console.warn(err);
  }
  state.report = report || { outcome, digits: 0, rank: "Chhota Chor", rank_line: "", gags: {}, lessons: [], missed: [], weak: "", mood: state.game.mood_name, twist: state.game.twist };
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
  showReport();
}

async function normalEnding(outcome) {
  $("end-stamp").textContent = OUTCOME_STAMP[outcome] || "CALL OVER";
  const line = {
    busted: "Dadi worked you out. She has reported you to 1930, the real cyber-fraud helpline.",
    timeout: "She out-talked you. The call ended and you got nothing.",
    hung_up: "You ran away. Dadi hasn't even finished telling you about her knee.",
  }[outcome] || "";
  $("end-line").textContent = line;
  if (outcome === "busted") {
    $("end-flash").classList.add("siren");
    sfx.siren();
    jolt();
    await say(clip(`busted_${state.game.mood}`));
  } else {
    await say(clip(outcome === "timeout" ? "timeout" : "hung_up"));
  }
  await sleep(1000);
}

// If you win, it stops being funny. That's the point.
async function crackedEnding() {
  document.querySelector(".end-stage").hidden = true;
  $("crack-stage").hidden = false;
  $("crack-text").textContent = "";
  await say(clip("cracked"));
  await sleep(700);
  const money = $("crack-money");
  sfx.drain();
  const total = 1420000;
  for (let i = 1; i <= 30; i++) {
    money.textContent = `₹${Math.round(total * (1 - i / 30)).toLocaleString("en-IN")}`;
    await sleep(50);
  }
  money.classList.add("zero");
  await sleep(900);
  $("crack-text").textContent = "Kamla Dadi is fictional. The people who lose everything this way are not.";
  await sleep(2600);
  $("crack-text").textContent = "Real grandmothers lose everything to these exact tricks, and they have no AI defending them.";
  await sleep(3400);
}

// ---------- The report: a lesson in disguise ----------

function showReport() {
  const r = state.report;
  show("report");
  $("s-report").scrollTop = 0;
  $("r-mood").textContent = `${r.mood} · ${r.twist}`;
  $("r-rank").textContent = r.rank;
  $("r-rankline").textContent = r.rank_line;
  $("r-crack").textContent = !r.crack_rate ? "Nobody has cracked her yet." : `Only ${r.crack_rate}% of callers have ever cracked her.`;

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

  const gags = r.gags || {};
  $("r-gags").replaceChildren(...Object.entries(gags).filter(([, n]) => n > 0).map(([gag, n]) => {
    const chip = document.createElement("span");
    chip.className = "gag-chip";
    chip.textContent = `${GAG_LABELS[gag]} ×${n}`;
    return chip;
  }));

  const lessons = r.lessons || [];
  $("r-lesson-title").textContent = lessons.length
    ? "You just used the tricks real scammers use. Here's how to see through each one."
    : "You didn't use one real scam trick. Here's the one that matters most.";
  const shown = lessons.length ? lessons : [{ label: "Fear", real: "Threats of arrest are designed to stop you thinking.", defence: "There is no such thing as a 'digital arrest'. Police don't arrest anyone over a phone or video call." }];
  // The newest trick first. Keep it short, and let the curious open the rest.
  const ordered = [...shown].reverse();
  $("r-lessons").replaceChildren(...ordered.slice(0, 2).map(lessonCard));
  $("r-more").hidden = ordered.length <= 2;
  $("r-more").onclick = () => {
    $("r-lessons").append(...ordered.slice(2).map(lessonCard));
    $("r-more").hidden = true;
  };
  function lessonCard(l) {
    const card = document.createElement("div");
    card.className = "lesson";
    const b = document.createElement("b");
    b.textContent = l.label;
    const real = document.createElement("p");
    real.textContent = l.real;
    const def = document.createElement("p");
    def.className = "defence";
    def.textContent = `If it's you: ${l.defence}`;
    card.append(b, real, def);
    return card;
  }

  const missed = r.missed || [];
  const tip = [r.weak && `Today's Dadi: ${r.weak}`, missed.length ? `You never tried: ${missed.join(", ")}.` : ""].filter(Boolean).join(" ");
  $("r-tip").textContent = tip;
  $("r-next").textContent = `Next time, try a different hour. ${NEXT_DADI[rand(NEXT_DADI.length)]} plays by different rules.`;

  document.querySelectorAll("[data-after]").forEach((b) => { b.disabled = false; });
  $("r-check-answer").hidden = true;

  // Dadi says the lesson that fits the last trick you used.
  const last = lessons.length ? lessons[lessons.length - 1].tactic : "fear";
  say(clip(`lesson_${last}`));
}

for (const btn of document.querySelectorAll("[data-after]")) {
  btn.addEventListener("click", () => {
    sfx.tap();
    const answer = btn.dataset.after === "true";
    post("/api/quiz", { answer });
    document.querySelectorAll("[data-after]").forEach((b) => { b.disabled = true; });
    const el = $("r-check-answer");
    el.hidden = false;
    el.textContent = answer
      ? "No. There's no such thing as a digital arrest. If anyone says otherwise, it's a scam. Hang up."
      : "Correct. There's no such thing as a digital arrest. Now make sure your family knows too.";
  });
}

$("b-again").addEventListener("click", () => {
  unlockAudio();
  hush();
  sfx.tap();
  loadStats();
  show("brief");
});

// ---------- Sharing ----------

const SITE = location.origin;

function shareText() {
  const r = state.report;
  const line = r.outcome === "cracked"
    ? `I cracked Kamla Dadi's OTP on Scam Dadi. Only ${r.crack_rate}% ever have.`
    : `I tried to scam ${r.mood} and got ${r.digits} of 4 OTP digits. Rank: ${r.rank}. She got me.`;
  return `${line} Try it, and learn how the real scam works: ${SITE}`;
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
  outlined("SCAM DADI", 540, 150, 112, "#ffb300");

  const art = new Image();
  const svg = document.querySelector("#s-title .dadi").cloneNode(true);
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
    g.fillText(got ? (r.otp ? r.otp[i] : "✓") : "?", x + tile / 2, 932);
  }

  g.textAlign = "center";
  g.fillStyle = "#fff3d6";
  g.font = "700 46px 'Baloo 2'";
  const top = Object.entries(r.gags || {}).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1])[0];
  g.fillText(r.mood, 540, 1055);
  g.font = "700 40px 'Baloo 2'";
  if (top) g.fillText(`${GAG_LABELS[top[0]].replace(/^\S+\s/, "")} × ${top[1]}`, 540, 1112);
  outlined(r.outcome === "cracked" ? "I CRACKED HER" : "CAN YOU BEAT HER?", 540, 1205, 64, "#ffffff", "#ff2e7e");
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
  const file = new File([blob], "scam-dadi.png", { type: "image/png" });
  const text = shareText();
  try {
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], text });
      return;
    }
  } catch (err) {
    if (err.name === "AbortError") return;
  }
  saveFile(blob, "scam-dadi.png");
  try { await navigator.clipboard.writeText(text); } catch (err) { console.warn(err); }
  pop("CARD SAVED, TEXT COPIED", "", "good");
  $("b-share").textContent = "Saved! Text copied";
});

$("b-parents").addEventListener("click", async () => {
  sfx.tap();
  const message = "कृपया ये दादी का छोटा सा मैसेज सुनिए। फ़ोन पर पुलिस या CBI बनकर ठगने वालों से बचने के लिए ज़रूरी है। कोई OTP या पैसे माँगे तो फ़ोन काटिए और 1930 पर कॉल कीजिए।";
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
  window.open(`https://wa.me/?text=${encodeURIComponent(`${message} ${SITE}/audio/parents.mp3`)}`, "_blank", "noopener");
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

function safeGet(key) {
  try { return localStorage.getItem(key); } catch (err) { return null; }
}
function safeSet(key, value) {
  try { localStorage.setItem(key, value); } catch (err) { /* private window */ }
}

loadStats();
