// ?trailer=1: a fixed, recordable cut of a real call. Loaded only by that URL (see the end of game.js).
//
// The call runs on the real engine: the server plays a fixed script (backend/trailer.py) through
// the normal scoring, pressure, recovery, digits and Boss. Only the player's lines (pre-recorded,
// no microphone) and the LLM's judgement are fixed, so every recording is the same. This file is
// the camera, the sound and the cuts, built from the game's own screens and helpers. It never
// writes to localStorage and never ends, submits or reports the call, so nothing is counted.
// ?trailer=1&autoplay=1 starts without a click (for a capture browser); &scene=08 starts at a scene.
(() => {
  "use strict";
  const Q = new URLSearchParams(location.search);
  const AUTO = Q.get("autoplay") === "1";
  const FROM = Q.get("scene");
  const RAW = Q.get("raw") === "1";  // clean plates for an editor: no camera, no overlays, voices only
  const CLIPS = "/audio/trailer/";
  // What the player says, exactly as backend/trailer.py expects it.
  const STEPS = [
    { id: "c_intro", said: "नमस्ते दादी जी, मैं बैंक से बोल रहा हूँ।", clip: "d_who" },
    { id: "c_press1", said: "आपका खाता आज बंद हो जाएगा, अभी करना होगा।", clip: "d_hurry" },
    { id: "c_press2", said: "पुलिस केस बन जाएगा, जल्दी कीजिए!", clip: "d_son" },
    { id: "c_reassure", said: "अरे नहीं दादी जी, आराम से। मैं आपकी मदद के लिए हूँ।", clip: "d_soft" },
    { id: "c_secret", said: "बस ये बात किसी को मत बताइएगा।", clip: "d_child" },
    { id: "c_ask", said: "आपके फ़ोन पर एक OTP आया होगा, बस वो बता दीजिए।", clip: "d_write" },
  ];
  const ALL_CLIPS = ["d_hello", "d_not_otp", "p_check", "j_ref", "m_1", "m_2", "m_3", ...STEPS.flatMap((s) => [s.id, s.clip])];

  // ---------- stage ----------
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "trailer.css";
  document.head.append(css);
  document.body.classList.add("trailer");
  if (RAW) document.body.classList.add("raw");
  const el = (tag, attrs = {}, html = "") => Object.assign(document.createElement(tag), attrs, html ? { innerHTML: html } : {});
  const stage = el("div", { id: "tr-stage" });
  const camEl = el("div", { id: "tr-cam" });
  const pulse = el("div", { id: "tr-pulse" }, "<i></i><i></i><i></i>");
  const words = {};
  for (const id of ["side-l", "side-r", "mid", "sub", "unknown", "otp-k", "otp-n", "final", "credit"]) words[id] = el("div", { id: `tr-${id}`, className: "tr-type" });
  const otp = el("div", { id: "tr-otp" }, "<span>1</span><span>9</span><span>3</span><span>0</span>");
  const black = el("div", { id: "tr-black" });
  const play = el("div", { id: "tr-play" }, AUTO ? "" : "▶&nbsp;&nbsp;PLAY");
  stage.append(pulse, camEl, black, ...Object.values(words), otp, play);  // black sits under the words: they are written on it
  document.body.append(stage);
  camEl.append($("app"));

  let base = 1.5;
  function fit() { base = Math.min(innerHeight / 720, innerWidth / 405) * (RAW ? 1 : 0.98); }
  fit();
  // The camera: scale s (1 = the whole phone in frame) looking at (fx, fy) in the phone's own pixels.
  function cam(s, fx = 202.5, fy = 360, ms = 0, ease = "cubic-bezier(.22,.8,.2,1)") {
    if (RAW) { s = 1; fx = 202.5; fy = 360; ms = 0; }
    const k = base * s;
    camEl.style.transition = ms ? `transform ${ms}ms ${ease}` : "none";
    camEl.style.transform = `translate(${(202.5 - fx) * k}px, ${(360 - fy) * k}px) scale(${k})`;
  }
  const FACE = [202.5, 372], BUBBLE = [202.5, 196], BOSS = [202.5, 556], OTP = [202.5, 96], TALK = [202.5, 640];
  function blackOn(fade = false) { if (RAW) return; black.classList.toggle("fade", fade); black.style.opacity = 1; }
  function blackOff(fade = false) { black.classList.toggle("fade", fade); black.style.opacity = 0; }
  function say1(id, html) { if (RAW) return; words[id].innerHTML = html; words[id].classList.add("on"); }
  function unsay(...ids) { for (const id of ids) words[id].classList.remove("on"); }
  function quietAll() { for (const w of Object.values(words)) w.classList.remove("on"); otp.querySelectorAll("span").forEach((s) => s.classList.remove("on")); otp.classList.remove("merged"); }

  // ---------- sound: the game's context, a phone line, a quiet score ----------
  const S = { ctx: null };
  function initSound() {
    unlockAudio();  // the game's own context, voice element and lip sync
    const ctx = (S.ctx = audio.ctx);
    S.master = ctx.createGain(); S.master.gain.value = 0.72; S.master.connect(ctx.destination);
    S.music = ctx.createGain(); S.music.gain.value = 0.0001; if (!RAW) S.music.connect(S.master);
    S.musicLevel = 0.5;
    S.sfx = ctx.createGain(); S.sfx.gain.value = 0.6; if (!RAW) S.sfx.connect(S.master);
    S.ui = ctx.createGain(); S.ui.gain.value = 0.35; if (!RAW) S.ui.connect(S.master);
    // Everyone on the other end of the call is heard through a phone line; the player is heard dry, close.
    const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 300;
    const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 3600;
    const pk = ctx.createBiquadFilter(); pk.type = "peaking"; pk.frequency.value = 1800; pk.gain.value = 3; pk.Q.value = 0.9;
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -22; comp.ratio.value = 3; comp.attack.value = 0.005; comp.release.value = 0.15;
    S.line = ctx.createGain(); S.line.gain.value = 1.15;
    hp.connect(lp).connect(pk).connect(comp).connect(S.line).connect(S.master);
    if (audio.analyser) { audio.analyser.disconnect(); audio.analyser.connect(hp); }
    S.me = new Audio();
    const meSrc = ctx.createMediaElementSource(S.me);
    S.meGain = ctx.createGain(); S.meGain.gain.value = 1.0;
    meSrc.connect(S.meGain).connect(S.master);
    // A barely-there room, so silence is a place, not a gap.
    const n = ctx.createBufferSource(); n.buffer = noise(ctx, 4); n.loop = true;
    const nf = ctx.createBiquadFilter(); nf.type = "lowpass"; nf.frequency.value = 380;
    S.room = ctx.createGain(); S.room.gain.value = 0;
    n.connect(nf).connect(S.room); if (!RAW) S.room.connect(S.master); n.start();
    // the game's beeps stay out of the trailer
    for (const k of Object.keys(sfx)) sfx[k] = () => {};
  }
  function noise(ctx, secs) {
    const b = ctx.createBuffer(1, ctx.sampleRate * secs, ctx.sampleRate), d = b.getChannelData(0);
    let last = 0, seed = 7;
    for (let i = 0; i < d.length; i++) { seed = (seed * 16807) % 2147483647; const w = seed / 2147483647 * 2 - 1; last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; }
    return b;
  }
  const now = () => S.ctx.currentTime;
  function ramp(param, value, secs) { const t = now(); param.cancelScheduledValues(t); param.setValueAtTime(Math.max(0.0001, param.value), t); param.exponentialRampToValueAtTime(Math.max(0.0001, value), t + secs); }
  function osc(freq, start, dur, { type = "sine", gain = 0.1, attack = 0.01, release = 0.2, dest = S.sfx, detune = 0 } = {}) {
    const o = S.ctx.createOscillator(), g = S.ctx.createGain();
    o.type = type; o.frequency.value = freq; o.detune.value = detune;
    g.gain.setValueAtTime(0.0001, start);
    g.gain.exponentialRampToValueAtTime(gain, start + attack);
    g.gain.setValueAtTime(gain, Math.max(start + attack, start + dur - release));
    g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    o.connect(g).connect(dest); o.start(start); o.stop(start + dur + 0.05);
    return o;
  }
  // The Hang Up ring: three rising notes, twice. The second call is the same figure, a semitone down, closer and dry.
  function ring(mirror = false) {
    const t = now() + 0.02, k = mirror ? 0.9439 : 1, g = mirror ? 0.2 : 0.13;
    [[0, 554.4], [0.13, 659.3], [0.26, 880], [0.62, 554.4], [0.75, 659.3], [0.88, 880]].forEach(([at, f]) => {
      osc(f * k, t + at, 0.34, { type: "triangle", gain: g, attack: 0.006, release: 0.25 });
      osc(f * k * 2, t + at, 0.18, { gain: g * 0.18, attack: 0.004, release: 0.15 });
      if (!mirror) osc(f, t + at + 0.18, 0.3, { type: "sine", gain: g * 0.25, attack: 0.01, release: 0.25 });  // a soft echo, gone the second time
    });
  }
  function vibrate() {
    const t = now() + 0.02;
    for (const at of [0, 0.62]) {
      const o = S.ctx.createOscillator(), g = S.ctx.createGain(), f = S.ctx.createBiquadFilter(), am = S.ctx.createOscillator(), amg = S.ctx.createGain();
      o.type = "square"; o.frequency.value = 148; f.type = "lowpass"; f.frequency.value = 320;
      am.frequency.value = 23; amg.gain.value = 0.05; am.connect(amg).connect(g.gain);
      g.gain.setValueAtTime(0.0001, t + at); g.gain.exponentialRampToValueAtTime(0.09, t + at + 0.03);
      g.gain.setValueAtTime(0.09, t + at + 0.42); g.gain.exponentialRampToValueAtTime(0.0001, t + at + 0.48);
      o.connect(f).connect(g).connect(S.sfx); o.start(t + at); o.stop(t + at + 0.5); am.start(t + at); am.stop(t + at + 0.5);
    }
  }
  function click(level = 1) {  // a real switch, not a "UI sound"
    const t = now() + 0.01, b = S.ctx.createBufferSource(), f = S.ctx.createBiquadFilter(), g = S.ctx.createGain();
    b.buffer = noise(S.ctx, 0.05); f.type = "highpass"; f.frequency.value = 1800;
    g.gain.setValueAtTime(0.16 * level, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.03);
    b.connect(f).connect(g).connect(S.ui); b.start(t);
    osc(1700, t, 0.03, { gain: 0.05 * level, attack: 0.002, release: 0.02, dest: S.ui });
  }
  function hangupTone() { const t = now() + 0.05; osc(425, t, 0.16, { gain: 0.06, release: 0.03 }); osc(425, t + 0.32, 0.16, { gain: 0.06, release: 0.03 }); }
  function digitTone(i) { osc([196, 196, 196, 147][i], now() + 0.01, 0.9, { type: "sine", gain: 0.13, attack: 0.008, release: 0.8 }); }
  function resonance() { const t = now() + 0.02; osc(41.2, t, 5.2, { gain: 0.32, attack: 0.05, release: 4.5 }); osc(82.4, t, 4, { gain: 0.08, attack: 0.05, release: 3.5 }); osc(164.8, t, 3, { type: "triangle", gain: 0.02, attack: 0.3, release: 2.5 }); }

  // The score: a few states, never wall to wall.
  const M = { nodes: [], timer: null };
  function musicOff(secs = 0.05) {
    clearInterval(M.timer); M.timer = null;
    ramp(S.music.gain, 0.0001, secs);
    const old = M.nodes; M.nodes = [];
    setTimeout(() => old.forEach((o) => { try { o.stop(); } catch (e) { /* done */ } }), secs * 1000 + 100);
  }
  function pad(freqs, gain = 0.05, cutoff = 520) {
    const f = S.ctx.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = cutoff; f.Q.value = 0.4; f.connect(S.music);
    for (const fr of freqs) for (const d of [-6, 6]) {
      const o = S.ctx.createOscillator(), g = S.ctx.createGain(); o.type = "triangle"; o.frequency.value = fr; o.detune.value = d;
      g.gain.value = gain; o.connect(g).connect(f); o.start(); M.nodes.push(o);
    }
    return f;
  }
  function pluck(f, at = 0) { osc(f, now() + at, 1.6, { type: "sine", gain: 0.05, attack: 0.004, release: 1.5, dest: S.music }); osc(f * 2, now() + at, 0.6, { gain: 0.012, attack: 0.003, release: 0.5, dest: S.music }); }
  function heartbeat(period, gain) {
    clearInterval(M.timer);
    const beat = () => { const t = now() + 0.02; osc(55, t, 0.22, { gain, attack: 0.01, release: 0.18, dest: S.music }); osc(55, t + 0.2, 0.2, { gain: gain * 0.6, attack: 0.01, release: 0.17, dest: S.music }); };
    beat(); M.timer = setInterval(beat, period);
  }
  function music(state) {
    if (state !== "pressure" && state !== "suspicion") musicOff(0.4);
    S.musicLevel = { curious: 0.55, suspicion: 0.7, pressure: 0.8, victory: 0.7, mirror: 0.6, release: 0.5 }[state] || 0.5;
    setTimeout(() => {
      if (state === "curious") { pad([55, 82.4], 0.05, 480); pluck(220, 0.2); pluck(329.6, 2.6); pluck(261.6, 5.0); }
      if (state === "suspicion") { if (!M.nodes.length) pad([55, 82.4], 0.05, 480); heartbeat(900, 0.18); }
      if (state === "pressure") { if (!M.nodes.length) pad([55, 82.4], 0.05, 620); heartbeat(620, 0.24); }
      if (state === "victory") { pad([110, 138.6, 164.8], 0.035, 900); pluck(440, 0.1); pluck(554.4, 0.5); }
      if (state === "mirror") { pad([51.9, 77.8], 0.055, 460); pluck(207.7, 0.4); pluck(311.1, 2.8); }
      if (state === "release") { pad([110, 164.8], 0.04, 700); }
      ramp(S.music.gain, S.musicLevel, state === "victory" ? 1.2 : 1.6);
    }, state === "pressure" || state === "suspicion" ? 0 : 420);
  }
  // Voices: music steps back while anyone speaks.
  function duck(on) { ramp(S.music.gain, on ? S.musicLevel * 0.35 : S.musicLevel, on ? 0.15 : 0.6); }
  const blobs = {};
  async function preload() {
    await Promise.all([...ALL_CLIPS.map((c) => `${CLIPS}${c}.mp3`), "/audio/num_1.mp3", "/audio/num_9.mp3", "/audio/num_3.mp3", "/audio/num_0.mp3"].map(async (u) => {
      blobs[u] = URL.createObjectURL(await (await fetch(u)).blob());
    }));
  }
  const src = (name) => blobs[name.startsWith("/") ? name : `${CLIPS}${name}.mp3`];
  const mark = (kind, data) => window.__L && window.__L(kind, data);  // a capture can line its cuts up with these
  async function them(name) { mark("voice", { name }); duck(true); await say(src(name)); duck(false); }  // through the line, with her mouth moving
  function me(name) {  // the player, close and dry
    mark("voice", { name });
    duck(true);
    return new Promise((resolve) => { S.me.src = src(name); S.me.onended = () => { duck(false); resolve(); }; S.me.play().catch(() => resolve()); });
  }

  // ---------- the real call ----------
  const T = { turns: [] };
  async function startCall() {
    const r = await post("/api/game/start", { hour: 20, lang: "en", trailer: true });
    T.game = await r.json();
    state.game = T.game;
    state.lang = "hi";
    for (const s of STEPS) {
      const t = await post(`/api/game/${T.game.id}/turn`, { said: s.said });
      T.turns.push(await t.json());
    }
    setArt("dadi");
    buildCallScreen(T.game, true);
    state.signal = "";
    setSuspicion(T.game.suspicion);
    $("boss").classList.add("hush");
  }
  const slots = () => [...document.querySelectorAll("#s-game .slot")];
  function setDigits(list) { slots().forEach((s, i) => { s.textContent = list[i] ?? "?"; s.className = list[i] ? "slot got" : "slot"; }); }
  async function talk(i, { typed = true } = {}) {  // hold, speak, let go: what the player actually does
    const s = STEPS[i];
    state.holding = true; $("b-talk").classList.add("down"); updateTalk(); click(0.6);
    $("you-said").textContent = "";
    const wordsOf = s.said.split(" ");
    const dur = { c_intro: 2.64, c_press1: 3.1, c_press2: 2.18, c_reassure: 3.58, c_secret: 2.04, c_ask: 3.58 }[s.id];
    let k = 0;
    const typer = typed ? setInterval(() => { k = Math.min(wordsOf.length, k + 1); $("you-said").textContent = wordsOf.slice(0, k).join(" "); }, (dur * 1000) / wordsOf.length) : null;
    await me(s.id);
    clearInterval(typer); $("you-said").textContent = s.said;
    state.holding = false; $("b-talk").classList.remove("down"); state.busy = true; updateTalk(); click(0.35);
  }
  async function answer(i, { digits = true, boss = true, wait = 450 } = {}) {  // the engine's verdict, then her voice
    const r = T.turns[i];
    await sleep(wait);
    state.signal = (r.signal || "").toUpperCase();
    setSuspicion(r.suspicion);
    $("dadi-slot").classList.toggle("fond", r.trust >= 55);
    if (boss && r.boss) { $("boss").classList.remove("hush"); setBoss(r.boss); }
    bubble(r.reply, r.reply_en);
    const speaking = them(STEPS[i].clip);
    await speaking;
    state.busy = false; updateTalk();
    if (digits) for (const d of r.digits) { const sl = slots()[d.index]; setSlot(sl, d.digit); digitTone(1); await sleep(380); }
    return r;
  }
  const digitsAfter = (n) => T.turns.slice(0, n).flatMap((t) => t.digits.map((d) => d.digit));

  // ---------- scenes ----------
  const SCENES = [
    ["01", async () => {  // black, a phone vibrating, the ring, "Hello?"
      blackOn(); cam(2.6, ...FACE); show("game"); ramp(S.room.gain, 0.014, 1.5);
      await sleep(600); vibrate(); await sleep(1150); vibrate();
      await sleep(950);
      pulse.className = "on"; say1("unknown", "Unknown number"); blackOff(true); camEl.style.opacity = 0;
      ring(); await sleep(1250); ring(); await sleep(1150);
      click(); pulse.className = ""; unsay("unknown");
      await sleep(140);
      camEl.style.opacity = 1; blackOff();
      await them("d_hello");
      music("curious");
    }],
    ["02", async () => {  // the first move, and she asks who's calling
      cam(1.0, 202.5, 360, 600);
      await sleep(250);
      await talk(0);
      cam(1.35, ...BUBBLE.map((v, i) => (i ? v + 90 : v)), 600);
      setTimeout(() => say1("side-l", "Read the<br>person."), 1500);
      await answer(0);
      await sleep(350); unsay("side-l");
    }],
    ["03", async () => {  // pushing: once, then too hard
      music("suspicion");
      cam(1.0, 202.5, 360, 500);
      await talk(1);
      await answer(1, { boss: false, wait: 350 });
      music("pressure");
      await talk(2);
      cam(1.5, ...FACE, 500);
      setTimeout(() => { cam(1.25, 202.5, 470, 450); $("boss").classList.remove("hush"); setBoss(T.turns[2].boss); click(0.4); }, 1600);
      await answer(2, { boss: false, wait: 250 });
      await sleep(900);
    }],
    ["04", async () => {  // a softer line brings her back
      musicOff(0.8); setTimeout(() => music("curious"), 900);
      cam(1.0, 202.5, 360, 500);
      await talk(3);
      const r = T.turns[3];
      await sleep(250);
      cam(1.12, 202.5, 400, 450);
      state.signal = r.signal.toUpperCase(); setSuspicion(r.suspicion); setBoss(r.boss); click(0.4);
      bubble(r.reply, r.reply_en);
      await them(STEPS[3].clip);
      state.busy = false; updateTalk();
      cam(2.1, ...OTP, 400);
      for (const d of r.digits) { setSlot(slots()[d.index], d.digit); digitTone(1); await sleep(420); }
      await sleep(200);
    }],
    ["05", async () => {  // everyone plays differently
      musicOff(0.3);
      const keep = digitsAfter(4);
      $("boss").classList.add("hush");
      for (const [role, line, sub] of [["didi", "p_check", ["Wait. मैं ये check करती हूँ।", "Wait. I'll check this."]], ["dadaji", "j_ref", ["Reference number बताइए।", "Reference number, please."]]]) {
        blackOn(); await sleep(160);
        setArt(role); setDigits([]); state.signal = ""; setSuspicion(12); bubble(sub[0], sub[1]);
        cam(1.75, 202.5, 330); pulse.className = "on"; blackOff(); ring();
        await them(line);
        await sleep(150);
        pulse.className = "";
      }
      blackOn(true); await sleep(350);
      say1("mid", "Everyone plays<br>differently.");
      await sleep(1500); unsay("mid"); await sleep(250);
      setArt("dadi"); setDigits(keep); bubble("");
      cam(1.0, 202.5, 360); blackOff();
    }],
    ["06", async () => {  // faster now
      music("pressure");
      await talk(5);
      cam(1.3, ...BUBBLE.map((v, i) => (i ? v + 100 : v)), 400);
      await answer(5, { boss: false, digits: false, wait: 250 });
    }],
    ["07", async () => {  // she reads it out, and it feels like winning
      cam(2.2, ...OTP, 500);
      musicOff(0.4); setTimeout(() => music("victory"), 300);
      const d = T.turns[5].digits[0];
      await say(src(`/audio/num_${d.digit}.mp3`));
      setSlot(slots()[d.index], d.digit); digitTone(1);
      await sleep(550);
      say1("side-r", "OTP<br>received.");
      await sleep(1450);
      musicOff(0.03); ramp(S.room.gain, 0.0001, 0.05);
      blackOn(); unsay("side-r");
    }],
    ["08", async () => {  // the digits, one at a time, and what they really are
      await sleep(1000);
      say1("otp-k", "The OTP");
      const sp = otp.querySelectorAll("span");
      for (let i = 0; i < 4; i++) { await sleep(i ? 820 : 600); sp[i].classList.add("on"); digitTone(i); }
      await sleep(1050);
      unsay("otp-k"); otp.classList.add("merged"); resonance();
      await sleep(900);
      say1("otp-n", "India's cyber-fraud helpline");
      await sleep(1200);
      say1("sub", "“That wasn't an OTP, beta.”");
      await them("d_not_otp");
      await sleep(1300);
      quietAll();
    }],
    ["09", async () => {  // silence, then your phone
      blackOn(); await sleep(1250);
      show("flip");
      $("flip-kicker").textContent = "Incoming call"; $("flip-title").textContent = "Unknown number";
      $("flip-line").textContent = ""; $("flip-note").textContent = ""; $("flip-choices").hidden = true;
      cam(1.0); camEl.style.opacity = 1;
      pulse.className = "slow on"; ring(true);
      await sleep(400); blackOff(true);
      await sleep(1550); ring(true); await sleep(1500);
    }],
    ["10", async () => {  // a stranger, using your words
      click(); pulse.className = ""; $("flip-kicker").textContent = "On call";
      music("mirror"); ramp(S.room.gain, 0.012, 1);
      S.line.gain.value = 1.3;  // closer than before
      await them("m_1");
      $("flip-line").textContent = "“आपका खाता आज बंद हो जाएगा… मैं आपकी मदद के लिए हूँ।”";
      $("flip-note").textContent = "Those are your words. It's someone else's voice.";
      cam(1.25, 202.5, 300, 900);
      await them("m_2");
      await sleep(250);
      $("flip-choices").hidden = false;
      await them("m_3");
      await sleep(950);
      $("b-flip-hang").classList.add("pressed"); click(1.2);
      await sleep(260);
      musicOff(0.06); ramp(S.room.gain, 0.0001, 0.06); hangupTone();
      $("flip-choices").hidden = true; $("flip-kicker").textContent = "You hung up";
      await sleep(550);
      blackOn();
    }],
    ["11", async () => {  // nothing, then the name
      await sleep(1100);
      say1("final", "<b>Hang Up</b><small>Learn to recognise manipulation.</small>");
      music("release");
      await sleep(1600);
      say1("credit", "Built with Gnani AI");
      await sleep(2300);
      musicOff(1.8);
      await sleep(1700);
      window.__trailerDone = true;
    }],
  ];

  // Jumping in mid-way: put the call where that scene expects it.
  function prepareFor(id) {
    const n = { "03": 1, "04": 3, "05": 4, "06": 4, "07": 5 }[id];
    if (n === undefined) return;
    show("game"); setDigits(digitsAfter(n)); const r = T.turns[n - 1];
    state.signal = (r.signal || "").toUpperCase(); setSuspicion(r.suspicion); blackOff();
  }

  async function run() {
    play.remove();
    initSound();
    let i = Math.max(0, SCENES.findIndex(([id]) => id === FROM));
    if (FROM && i > 0) prepareFor(SCENES[i][0]);
    for (; i < SCENES.length; i++) {
      window.__trailerScene = SCENES[i][0];
      mark("scene", { id: SCENES[i][0] });
      await SCENES[i][1]();
    }
  }

  (async () => {
    blackOn();
    await Promise.all([preload(), startCall()]);
    window.__trailerReady = true;
    if (AUTO) return run();
    document.body.classList.add("ready");
    play.addEventListener("click", run, { once: true });
  })().catch((err) => { console.error(err); play.textContent = "Couldn't start the trailer. Reload to try again."; });
})();
