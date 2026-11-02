// Kaam guided voice interview: Timbre asks each question out loud, the worker
// answers, Prisma transcribes live, and the answer stays editable.

const $ = (id) => document.getElementById(id);

const state = {
  lang: null,
  questions: [],
  index: 0,
  answers: [],
  mic: null,     // { stream, ctx }
  ws: null,      // Prisma session for the current answer
  pending: 0,    // speech segments Prisma has started but not yet returned
  detected: new Set(),
  sample: null,  // a sample worker from /api/samples, when running the demo
  player: null,  // one shared <audio>, unlocked by the first tap (needed on iOS)
  languages: {},
};

const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
  for (const id of ["welcome", "interview", "done"]) $(`screen-${id}`).hidden = id !== screen;
}

function setMic(text, live = false) {
  $("mic-status").textContent = text;
  $("mic-dot").classList.toggle("live", live);
}

// ---------- Welcome ----------

async function loadLanguages() {
  const langs = await (await fetch("/api/languages")).json();
  for (const { code, label } of langs) {
    state.languages[code] = label;
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", () => {
      state.lang = code;
      for (const b of $("languages").children) b.setAttribute("aria-pressed", String(b === btn));
      updateStart();
    });
    $("languages").append(btn);
  }
}

function updateStart() {
  $("start").disabled = !(state.lang && $("consent").checked);
}

$("consent").addEventListener("change", updateStart);

async function beginInterview() {
  state.questions = await (await fetch(`/api/questions/${state.lang}`)).json();
  state.index = 0;
  state.answers = [];
  const banner = $("sample-banner");
  banner.hidden = !state.sample;
  if (state.sample) {
    banner.textContent = `Sample: ${state.sample.name}, ${state.sample.trade.toLowerCase()} · ${state.sample.scene_label} · synthetic voice`;
  }
  show("interview");
  askQuestion();
}

$("start").addEventListener("click", async () => {
  $("welcome-error").hidden = true;
  unlockAudio();
  try {
    await startMic();
    await beginInterview();
  } catch (err) {
    $("welcome-error").textContent = `Could not start: ${err.message}`;
    $("welcome-error").hidden = false;
  }
});

async function loadSamples() {
  const samples = await (await fetch("/api/samples")).json();
  $("samples").replaceChildren(...samples.map((sample) => {
    const btn = document.createElement("button");
    btn.className = "sample";
    const name = document.createElement("b");
    name.textContent = `${sample.name} · ${sample.trade}`;
    const lang = document.createElement("span");
    lang.className = "lang";
    lang.textContent = state.languages[sample.language] || sample.language;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = `${sample.place} · ${sample.scene_label}`;
    btn.append(name, lang, meta);
    btn.addEventListener("click", async () => {
      unlockAudio();
      state.sample = sample;
      state.lang = sample.language;
      try {
        await beginInterview();
      } catch (err) {
        $("welcome-error").textContent = `Could not start the sample: ${err.message}`;
        $("welcome-error").hidden = false;
      }
    });
    return btn;
  }));
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
    if (ws && ws.readyState === WebSocket.OPEN && ws.listening) ws.send(pcm.slice(i, i + frame).buffer);
  }
  await Promise.race([playback, sleep(1500)]);
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
    if (state.ws && state.ws.readyState === WebSocket.OPEN && state.ws.listening) state.ws.send(e.data);
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
  state.mic.stream.getTracks().forEach((t) => t.stop());
  state.mic.ctx.close();
  state.mic = null;
}

// ---------- Interview ----------

// The question is on screen even if its audio fails, so this never rejects.
function playQuestion() {
  return playUrl(`/api/questions/${state.lang}/${state.index}/audio`);
}

async function askQuestion() {
  const q = state.questions[state.index];
  const total = state.questions.length;
  $("question").textContent = q.text;
  $("progress-label").textContent = `Question ${state.index + 1} of ${total}`;
  $("progress-bar").style.width = `${(state.index / total) * 100}%`;
  $("answer").value = "";
  $("live").textContent = "";
  $("next").textContent = state.index === total - 1 ? "Finish" : "Next";
  state.detected = new Set();

  setMic("Listen to the question…");
  setButtons(false);
  await playQuestion();
  // Warm the cache so the next question plays without a synthesis delay.
  if (state.index + 1 < total) fetch(`/api/questions/${state.lang}/${state.index + 1}/audio`);
  await startAnswer();
  if (state.sample) {
    setMic(`${state.sample.name.split(" ")[0]} is answering…`, true);
    await playSampleAnswer();
    await nextQuestion();
    return;
  }
  setButtons(true);
}

function setButtons(enabled) {
  for (const id of ["next", "rerecord", "replay"]) $(id).disabled = !enabled;
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
      setMic("Listening… speak now", true);
      resolve();
    };
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === "speech_start") state.pending++;
      // Words in progress, shown above the answer until Prisma finalizes them.
      if (event.type === "partial_transcript") $("live").textContent = event.text || "";
      if (event.type === "transcript" || event.type === "final_transcript") {
        state.pending = Math.max(0, state.pending - 1);
        $("live").textContent = "";
        if (event.detected_language_code) state.detected.add(event.detected_language_code);
        if (event.text) {
          const box = $("answer");
          box.value = box.value ? `${box.value.trimEnd()} ${event.text}` : event.text;
        }
      }
      if (event.type === "error") setMic(event.message || "Speech service error");
      ws.dispatchEvent(new CustomEvent("kaam", { detail: event }));
    };
    ws.onerror = () => {
      setMic("Could not connect to speech service");
      resolve();
    };
  });
}

// Stop sending audio, let Prisma finish the last segment, then close.
function finishAnswer() {
  const ws = state.ws;
  state.ws = null;
  if (!ws || ws.readyState !== WebSocket.OPEN) return Promise.resolve();
  ws.listening = false;
  setMic("Finishing…");

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
  if (state.ws) state.ws.close();
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
  $("answer").value = "";
  $("live").textContent = "";
  state.detected = new Set();
  await startAnswer();
  setButtons(true);
});

$("replay").addEventListener("click", async () => {
  setButtons(false);
  if (state.ws) state.ws.listening = false;
  setMic("Listen to the question…");
  await playQuestion();
  if (state.ws) {
    state.ws.listening = true;
    setMic("Listening… speak now", true);
  }
  setButtons(true);
});

// ---------- Done ----------

async function finishInterview() {
  stopMic();
  show("done");
  $("review").replaceChildren(...state.answers.map((a) => {
    const li = document.createElement("li");
    const q = document.createElement("div");
    q.className = "q";
    q.textContent = a.question;
    const t = document.createElement("div");
    t.textContent = a.transcript || "(no answer)";
    li.append(q, t);
    return li;
  }));

  // Sample workers already have a voice; real workers pick theirs.
  if (state.sample) {
    saveAndBuild(state.sample.gender);
  } else {
    $("voice-choice").hidden = false;
  }
}

for (const btn of document.querySelectorAll("#voice-choice button")) {
  btn.addEventListener("click", () => {
    $("voice-choice").hidden = true;
    saveAndBuild(btn.dataset.voice);
  });
}

async function saveAndBuild(introVoice) {
  $("saved").textContent = "Saving…";
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
  if (!resp.ok) {
    $("saved").textContent = `Could not save (${resp.status}).`;
    return;
  }
  state.interviewId = (await resp.json()).id;
  buildProfile();
}

async function buildProfile() {
  $("build").hidden = true;
  $("saved").textContent = "Writing your resume and recording your introduction…";
  const resp = await fetch(`/api/interviews/${state.interviewId}/profile`, { method: "POST" });
  if (resp.ok) {
    location.href = `/p/${state.interviewId}`;
    return;
  }
  const body = await resp.json().catch(() => ({}));
  $("saved").textContent = `Could not build the resume: ${body.detail || resp.status}`;
  $("build").hidden = false;
}

$("build").addEventListener("click", buildProfile);

$("restart").addEventListener("click", () => location.reload());

loadLanguages().then(loadSamples);
