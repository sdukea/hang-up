// Kaam guided voice interview: Timbre asks each question out loud, the worker
// answers, Prisma transcribes live, and the answer stays editable.

const $ = (id) => document.getElementById(id);

const state = {
  lang: null,
  ui: {},        // interface text in the worker's language
  questions: [],
  index: 0,
  answers: [],
  mic: null,     // { stream, ctx }
  ws: null,      // Prisma session for the current answer
  pending: 0,    // speech segments Prisma has started but not yet returned
  detected: new Set(),
  sample: null,  // a sample worker from /api/samples, when running the demo
  player: null,  // one shared <audio>, unlocked by the first tap (needed on iOS)
  retry: null,   // what "Try Again" does on the last screen
};

const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const t = (key) => state.ui[key] || key;
const getJson = async (url) => (await fetch(url)).json();

function unlockAudio() {
  if (state.player) return;
  state.player = new Audio(SILENT_WAV);
  state.player.play().catch(() => {});
}

function playUrl(url) {
  return new Promise((resolve) => {
    const p = state.player;
    p.pause();
    p.onended = p.onerror = () => resolve();
    p.src = url;
    p.play().catch(() => resolve());
  });
}

function show(screen) {
  for (const id of ["home", "samples", "intro", "interview", "done"]) $(`screen-${id}`).hidden = id !== screen;
  window.scrollTo(0, 0);
}

for (const btn of document.querySelectorAll("[data-go]")) {
  btn.addEventListener("click", () => {
    if (state.player) state.player.pause();
    show(btn.dataset.go);
  });
}

// mode: "wait" (Kaam is talking or busy), "live" (hearing the worker) or "bad"
function setMic(text, mode = "wait") {
  $("mic-status").textContent = text;
  $("mic-status").classList.toggle("bad", mode === "bad");
  $("mic").classList.toggle("live", mode === "live");
  $("mic-glyph").setAttribute("href", mode === "live" ? "#i-mic" : "#i-speaker");
  if (mode !== "live") setLevel(0);
}

function setLevel(level) {
  $("mic").style.setProperty("--level", level.toFixed(3));
}

function meter(buffer) {
  const samples = new Int16Array(buffer);
  let sum = 0;
  for (const v of samples) sum += v * v;
  setLevel(Math.min(1, (Math.sqrt(sum / samples.length) / 32768) * 7));
}

// ---------- Choosing a language ----------

function fillUi() {
  $("intro-title").textContent = t("intro_title");
  $("intro-text").textContent = t("intro");
  $("start-label").textContent = t("start");
  $("fix-label").textContent = t("fix");
  $("again-label").textContent = t("again");
  $("voice-q").textContent = t("voice_q");
  $("female-label").textContent = t("female");
  $("male-label").textContent = t("male");
  $("build").textContent = t("retry");
}

async function loadLanguages() {
  const langs = await getJson("/api/languages");
  $("languages").replaceChildren(...langs.map(({ code, label }) => {
    const btn = document.createElement("button");
    btn.className = "row";
    btn.lang = code;
    btn.textContent = label;
    btn.insertAdjacentHTML("beforeend", '<svg class="icon chevron"><use href="#i-chevron"/></svg>');
    btn.addEventListener("click", () => chooseLanguage(code));
    return btn;
  }));
}

async function chooseLanguage(code) {
  unlockAudio();
  state.lang = code;
  state.sample = null;
  state.ui = await getJson(`/api/ui/${code}`);
  document.documentElement.lang = code;
  fillUi();
  $("intro-error").hidden = true;
  show("intro");
  playUrl(`/api/ui/${code}/intro/audio`);
}

$("intro-replay").addEventListener("click", () => playUrl(`/api/ui/${state.lang}/intro/audio`));

$("start").addEventListener("click", async () => {
  state.player.pause();
  $("intro-error").hidden = true;
  try {
    await startMic();
    await beginInterview();
  } catch (err) {
    console.warn(err);
    $("intro-error").textContent = t("mic_blocked");
    $("intro-error").hidden = false;
  }
});

// ---------- Examples ----------

$("open-samples").addEventListener("click", () => show("samples"));

async function loadSamples() {
  const [samples, langs] = await Promise.all([getJson("/api/samples"), getJson("/api/languages")]);
  const labels = Object.fromEntries(langs.map((l) => [l.code, l.name]));
  $("samples").replaceChildren(...samples.map((sample) => {
    const btn = document.createElement("button");
    btn.className = "row";
    const who = document.createElement("span");
    const name = document.createElement("b");
    name.textContent = `${sample.name}, ${sample.trade.toLowerCase()}`;
    const where = document.createElement("small");
    where.textContent = sample.scene_label;
    who.append(name, where);
    const lang = document.createElement("span");
    lang.className = "trailing";
    lang.textContent = labels[sample.language];
    btn.append(who, lang);
    btn.addEventListener("click", () => startSample(sample));
    return btn;
  }));
}

async function startSample(sample) {
  unlockAudio();
  state.sample = sample;
  state.lang = sample.language;
  // People watching an example may not read this language, so the interface
  // stays in English and each question gets an English line beneath it.
  state.ui = await getJson("/api/ui/en-IN");
  state.gloss = await getJson("/api/questions/en-IN");
  fillUi();
  await beginInterview();
}

// ---------- Microphone ----------

async function startMic() {
  if (state.mic) return;
  const stream = await navigator.mediaDevices.getUserMedia({
    // Keep the raw signal: Prisma is trained on noisy audio, and browser noise
    // suppression can clip quiet speech.
    audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: true },
  });
  const ctx = new AudioContext();
  await ctx.audioWorklet.addModule("pcm-worklet.js");
  const worklet = new AudioWorkletNode(ctx, "pcm-worklet");
  worklet.port.onmessage = (e) => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN && state.ws.listening) {
      state.ws.send(e.data);
      meter(e.data);
    }
  };
  ctx.createMediaStreamSource(stream).connect(worklet);
  // Chrome only runs nodes that lead to the speakers, so route the worklet
  // there through a muted gain node.
  const mute = ctx.createGain();
  mute.gain.value = 0;
  worklet.connect(mute).connect(ctx.destination);
  if (ctx.state === "suspended") await ctx.resume();
  state.mic = { stream, ctx };
}

function stopMic() {
  if (!state.mic) return;
  state.mic.stream.getTracks().forEach((track) => track.stop());
  state.mic.ctx.close();
  state.mic = null;
}

// ---------- Sample worker playback ----------

// Decode a sample answer and resample it to 16 kHz PCM16, the format the
// microphone path sends. Decoding at 48 kHz first works in every browser.
async function decodeSample(url) {
  const data = await (await fetch(url)).arrayBuffer();
  const decoded = await new OfflineAudioContext(1, 1, 48000).decodeAudioData(data);
  const src = decoded.getChannelData(0);
  const ratio = decoded.sampleRate / 16000;
  const out = new Int16Array(Math.floor(src.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const pos = i * ratio;
    const j = Math.floor(pos);
    const a = src[j];
    const b = src[Math.min(j + 1, src.length - 1)];
    const v = Math.max(-1, Math.min(1, a + (b - a) * (pos - j)));
    out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  return out;
}

// Play the answer out loud and stream the same audio to Prisma in real time,
// exactly as if it were coming from the microphone.
async function playSampleAnswer() {
  const url = state.sample.audio[state.index];
  const pcm = await decodeSample(url);
  const playback = playUrl(url);
  const frame = 512;
  const start = performance.now();
  for (let i = 0; i < pcm.length; i += frame) {
    const wait = start + (i / 16000) * 1000 - performance.now();
    if (wait > 0) await sleep(wait);
    const ws = state.ws;
    if (ws && ws.readyState === WebSocket.OPEN && ws.listening) {
      const chunk = pcm.slice(i, i + frame).buffer;
      ws.send(chunk);
      meter(chunk);
    }
  }
  await Promise.race([playback, sleep(1500)]);
}

// ---------- Interview ----------

async function beginInterview() {
  state.questions = await getJson(`/api/questions/${state.lang}`);
  state.index = 0;
  state.answers = [];
  const banner = $("sample-banner");
  banner.hidden = !state.sample;
  if (state.sample) banner.textContent = `Example: ${state.sample.name}. ${state.sample.scene_label}. Synthetic voice.`;
  $("interview-actions").hidden = Boolean(state.sample);
  $("replay").hidden = Boolean(state.sample);
  show("interview");
  askQuestion();
}

function renderSteps() {
  const total = state.questions.length;
  $("steps").setAttribute("aria-label", `${state.index + 1} / ${total}`);
  $("steps").replaceChildren(...state.questions.map((_, i) => {
    const s = document.createElement("span");
    if (i < state.index) s.className = "done";
    if (i === state.index) s.className = "now";
    return s;
  }));
}

function renderAnswer() {
  const text = $("answer").value.trim();
  const live = $("spoken-live").textContent;
  $("spoken-final").textContent = text;
  $("fix").hidden = Boolean(state.sample) || !text || !$("answer").hidden;
  const last = state.index === state.questions.length - 1;
  $("next-label").textContent = text || live ? t(last ? "finish" : "next") : t(last ? "finish" : "skip");
}

function clearAnswer() {
  $("answer").value = "";
  $("answer").hidden = true;
  $("spoken").hidden = false;
  $("spoken-live").textContent = "";
  state.detected = new Set();
  renderAnswer();
}

async function askQuestion() {
  const q = state.questions[state.index];
  const total = state.questions.length;
  renderSteps();
  $("question").textContent = q.text;
  $("question").lang = state.lang;
  $("gloss").hidden = !state.sample;
  if (state.sample) $("gloss").textContent = state.gloss[state.index].text;
  clearAnswer();

  setMic(t("listen"));
  setButtons(false);
  await playUrl(`/api/questions/${state.lang}/${state.index}/audio`);
  // Warm the cache so the next question plays without a synthesis delay.
  if (state.index + 1 < total) fetch(`/api/questions/${state.lang}/${state.index + 1}/audio`);
  await startAnswer();
  if (state.sample) {
    setMic(`${state.sample.name.split(" ")[0]} is answering`, "live");
    await playSampleAnswer();
    await nextQuestion();
    return;
  }
  setButtons(true);
}

function setButtons(enabled) {
  for (const id of ["next", "rerecord", "replay", "fix"]) $(id).disabled = !enabled;
}

function startAnswer() {
  return new Promise((resolve) => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/listen?lang=${encodeURIComponent(state.lang)}`);
    ws.listening = false;
    state.ws = ws;
    state.pending = 0;

    ws.onopen = () => {
      ws.listening = true;
      setMic(t("speak"), "live");
      resolve();
    };
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === "speech_start") state.pending++;
      // Words in progress, shown in grey until Prisma finalizes them.
      if (event.type === "partial_transcript") {
        $("spoken-live").textContent = event.text || "";
        renderAnswer();
      }
      if (event.type === "transcript" || event.type === "final_transcript") {
        state.pending = Math.max(0, state.pending - 1);
        $("spoken-live").textContent = "";
        if (event.detected_language_code) state.detected.add(event.detected_language_code);
        if (event.text) {
          const box = $("answer");
          box.value = box.value ? `${box.value.trimEnd()} ${event.text}` : event.text;
        }
        renderAnswer();
      }
      if (event.type === "error") {
        console.warn("Speech service:", event.message);
        setMic(t("speech_error"), "bad");
      }
      ws.dispatchEvent(new CustomEvent("kaam", { detail: event }));
    };
    ws.onerror = () => {
      setMic(t("speech_error"), "bad");
      resolve();
    };
    ws.onclose = () => {
      if (state.ws === ws && ws.listening) setMic(t("speech_error"), "bad");
    };
  });
}

// Stop sending audio, let Prisma finish the last segment, then close.
function finishAnswer() {
  const ws = state.ws;
  state.ws = null;
  if (!ws || ws.readyState !== WebSocket.OPEN) return Promise.resolve();
  ws.listening = false;
  setMic(t("wait"));

  return new Promise((resolve) => {
    const done = () => { clearTimeout(timer); ws.close(); resolve(); };
    const timer = setTimeout(done, 4000);
    let flushed = false;
    ws.addEventListener("kaam", (e) => {
      if (e.detail.type === "flushed") flushed = true;
      if (flushed && state.pending === 0) setTimeout(done, 300);
    });
    ws.send("flush");
  });
}

function discardAnswer() {
  if (state.ws) {
    state.ws.listening = false;
    state.ws.close();
  }
  state.ws = null;
}

async function nextQuestion() {
  setButtons(false);
  await finishAnswer();
  const q = state.questions[state.index];
  state.answers.push({
    question_id: q.id,
    question: q.text,
    transcript: $("answer").value.trim(),
    detected_languages: [...state.detected],
  });
  state.index++;
  if (state.index < state.questions.length) {
    askQuestion();
  } else {
    finishInterview();
  }
}

$("next").addEventListener("click", nextQuestion);

$("rerecord").addEventListener("click", async () => {
  setButtons(false);
  discardAnswer();
  clearAnswer();
  await startAnswer();
  setButtons(true);
});

$("replay").addEventListener("click", async () => {
  setButtons(false);
  if (state.ws) state.ws.listening = false;
  setMic(t("listen"));
  await playUrl(`/api/questions/${state.lang}/${state.index}/audio`);
  if (state.ws) {
    state.ws.listening = true;
    setMic(t("speak"), "live");
  }
  setButtons(true);
});

$("fix").addEventListener("click", () => {
  $("spoken").hidden = true;
  $("answer").hidden = false;
  $("answer").focus();
  renderAnswer();
});
$("answer").addEventListener("input", renderAnswer);

$("close").addEventListener("click", () => {
  const hasWork = !state.sample && (state.answers.length || $("answer").value.trim());
  if (!hasWork || confirm(t("quit"))) location.href = "/";
});

// ---------- Making the card ----------

function finishInterview() {
  stopMic();
  show("done");
  // Sample workers already have a voice; real workers pick theirs.
  if (state.sample) {
    saveAndBuild(state.sample.gender);
  } else {
    $("voice-choice").hidden = false;
  }
}

for (const btn of document.querySelectorAll("[data-voice]")) {
  btn.addEventListener("click", () => saveAndBuild(btn.dataset.voice));
}

function showBuilding(text, retry = null) {
  $("voice-choice").hidden = true;
  $("building").hidden = false;
  $("building-text").textContent = text;
  document.querySelector(".spinner").hidden = Boolean(retry);
  $("build").hidden = !retry;
  state.retry = retry;
}

$("build").addEventListener("click", () => state.retry());

async function saveAndBuild(introVoice) {
  const again = () => saveAndBuild(introVoice);
  showBuilding(t("building"));
  try {
    const resp = await fetch("/api/interviews", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: state.lang,
        consent: true,
        answers: state.answers,
        sample_id: state.sample ? state.sample.id : null,
        intro_voice: introVoice,
      }),
    });
    if (!resp.ok) throw new Error(`save failed: ${resp.status}`);
    state.interviewId = (await resp.json()).id;
    await buildProfile();
  } catch (err) {
    console.warn(err);
    showBuilding(t("build_error"), again);
  }
}

async function buildProfile() {
  showBuilding(t("building"));
  try {
    const resp = await fetch(`/api/interviews/${state.interviewId}/profile`, { method: "POST" });
    if (!resp.ok) throw new Error(`build failed: ${resp.status}`);
    // The worker who just made it sees their card's actions in their language.
    location.href = `/p/${state.interviewId}${state.sample ? "" : "?new=1"}`;
  } catch (err) {
    console.warn(err);
    showBuilding(t("build_error"), buildProfile);
  }
}

loadLanguages();
loadSamples();
