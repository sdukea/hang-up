// Renders a worker's shareable Kaam profile card from /api/profiles/{id}.

const $ = (id) => document.getElementById(id);
const profileId = location.pathname.split("/").filter(Boolean).pop();
const pageUrl = `${location.origin}/p/${profileId}`;

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function initials(name) {
  return (name || "?").trim().split(/\s+/).slice(0, 2).map((w) => [...w][0]).join("").toUpperCase();
}

function fact(label, value) {
  const row = el("div");
  row.append(el("dt", label), el("dd", value));
  return row;
}

function setPlaying(btn, playing) {
  btn.classList.toggle("playing", playing);
  btn.querySelector("use").setAttribute("href", playing ? "#i-pause" : "#i-play");
}

let current = null; // { audio, button }

function voiceButton(label, src) {
  const btn = el("button");
  btn.innerHTML = '<svg class="icon"><use href="#i-play"/></svg>';
  btn.append(el("span", label));
  btn.addEventListener("click", () => {
    const same = current && current.button === btn;
    if (current) {
      current.audio.pause();
      setPlaying(current.button, false);
      current = null;
    }
    if (same) return;
    const audio = new Audio(src);
    audio.onended = () => { setPlaying(btn, false); current = null; };
    audio.play();
    setPlaying(btn, true);
    current = { audio, button: btn };
  });
  return btn;
}

function renderSample(sample, comparison) {
  $("sample-note").textContent = `Example: a fictional worker with a synthetic voice, ${sample.scene_label.toLowerCase()}. Kaam made this card live from that audio.`;
  $("comparison").replaceChildren(...comparison.map((c) => {
    const li = el("li");
    const said = el("div", null, "said");
    said.append(el("span", "Said"), el("span", c.script));
    const heard = el("div", null, "heard");
    heard.append(el("span", "Heard"), el("span", c.heard || "(nothing)"));
    li.append(el("div", c.question, "q"), said, heard);
    return li;
  }));
  $("sample-block").hidden = false;
}

// The worker who just made this card sees its actions in their own language.
async function renderOwnerView(language) {
  const ui = await (await fetch(`/api/ui/${language}`)).json();
  $("ready").textContent = ui.ready;
  $("ready").lang = language;
  $("ready").hidden = false;
  $("whatsapp-label").textContent = ui.whatsapp;
  $("copy-label").textContent = ui.copy;
  $("download-label").textContent = ui.image;
  $("print-label").textContent = ui.print;
  copiedLabel = ui.copied;
}

let copiedLabel = "Copied";

function render({ profile: p, audio, language, language_name: languageName, sample, comparison }) {
  const name = p.name || "Kaam worker";
  const native = language !== "en-IN";
  document.title = `${name} · ${p.trade_en || "Kaam"}`;

  $("avatar").textContent = initials(p.name);
  $("trade").textContent = p.trade_en;
  $("name").textContent = name;
  if (native && p.name_native && p.name_native !== p.name) {
    $("name-native").textContent = p.name_native;
    $("name-native").lang = language;
    $("name-native").hidden = false;
  }
  $("place").textContent = [p.current_city, p.hometown && p.hometown !== p.current_city ? `from ${p.hometown}` : null]
    .filter(Boolean).join(" · ");
  $("headline").textContent = p.headline_en;
  if (native && p.headline_native) {
    $("headline-native").textContent = p.headline_native;
    $("headline-native").lang = language;
  } else {
    $("headline-native").hidden = true;
  }

  const facts = [];
  if (p.years_experience != null) facts.push(fact("Experience", `${p.years_experience} years`));
  if (p.languages_spoken.length) facts.push(fact("Speaks", p.languages_spoken.join(", ")));
  if (p.preferred_areas.length) facts.push(fact("Wants to work in", p.preferred_areas.join(", ")));
  $("facts").replaceChildren(...facts);

  $("skills").replaceChildren(...p.skills_en.map((skill) => el("li", skill)));

  const first = (p.name || "me").split(/\s+/)[0];
  const voices = [];
  if (audio.native) voices.push(voiceButton(languageName, audio.native));
  if (audio.en) voices.push(voiceButton("English", audio.en));
  if (voices.length) voices.unshift(el("p", `Hear ${first}`, "voice-label"));
  $("voice").replaceChildren(...voices);

  const qr = qrcode(0, "M");
  qr.addData(pageUrl);
  qr.make();
  $("qr").src = qr.createDataURL(6, 0);

  // Resume details
  $("summary").textContent = p.summary_en;
  if (native && p.summary_native) {
    $("summary-native").textContent = p.summary_native;
    $("summary-native").lang = language;
    $("summary-native").hidden = false;
  }
  if (p.experience.length) {
    $("experience").replaceChildren(...p.experience.map((x) => {
      const li = el("li");
      const title = [x.role_en, x.where_en].filter(Boolean).join(" · ");
      li.append(el("strong", title));
      if (x.duration) li.append(el("span", ` (${x.duration})`));
      if (x.details_en) li.append(el("div", x.details_en));
      return li;
    }));
  } else {
    $("experience-block").hidden = true;
  }
  if (p.proud_of_en) $("proud").textContent = p.proud_of_en;
  else $("proud-block").hidden = true;

  if (p.expected_pay_en) $("pay").textContent = p.expected_pay_en;
  else $("pay-block").hidden = true;

  // Sharing
  const shareText = `${name} · ${p.trade_en}. Hear ${first} talk about their work: ${pageUrl} #KaamChallenge`;
  $("whatsapp").href = `https://wa.me/?text=${encodeURIComponent(shareText)}`;
  $("copy").addEventListener("click", async () => {
    const label = $("copy-label");
    const original = label.textContent;
    await navigator.clipboard.writeText(pageUrl);
    label.textContent = copiedLabel;
    setTimeout(() => { label.textContent = original; }, 2000);
  });
  $("download").addEventListener("click", async () => {
    $("download").disabled = true;
    // A saved image can't play audio, so it keeps only the QR code.
    const canvas = await html2canvas($("card"), {
      scale: 2,
      backgroundColor: null,
      onclone: (doc) => {
        doc.getElementById("voice").remove();
        doc.querySelector(".kcard-bottom").style.justifyContent = "center";
      },
    });
    const link = document.createElement("a");
    link.download = `kaam-${(p.name || "profile").toLowerCase().replace(/\s+/g, "-")}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
    $("download").disabled = false;
  });
  $("print").addEventListener("click", () => window.print());

  if (sample && comparison) renderSample(sample, comparison);
  if (new URLSearchParams(location.search).has("new")) renderOwnerView(language);

  $("status").hidden = true;
  for (const id of ["card", "actions", "resume"]) $(id).hidden = false;
}

fetch(`/api/profiles/${profileId}`)
  .then((r) => {
    if (r.status === 404) throw new Error("This card doesn't exist. Check the link.");
    if (!r.ok) throw new Error("Couldn't load this card. Try again in a minute.");
    return r.json();
  })
  .then(render)
  .catch((err) => {
    console.warn(err);
    $("status").textContent = err.message.startsWith("Co") || err.message.startsWith("This") ? err.message : "Couldn't load this card. Try again in a minute.";
  });
