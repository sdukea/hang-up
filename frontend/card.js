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

function stat(value, label) {
  const box = el("div", null, "stat");
  box.append(el("b", value), el("span", label));
  return box;
}

let current = null; // { audio, button }

function voiceButton(label, src) {
  const btn = el("button", label);
  btn.addEventListener("click", () => {
    if (current && current.button === btn) {
      current.audio.pause();
      btn.classList.remove("playing");
      current = null;
      return;
    }
    if (current) {
      current.audio.pause();
      current.button.classList.remove("playing");
    }
    const audio = new Audio(src);
    audio.onended = () => { btn.classList.remove("playing"); current = null; };
    audio.play();
    btn.classList.add("playing");
    current = { audio, button: btn };
  });
  return btn;
}

function renderSample(sample, comparison) {
  $("sample-note").textContent = `Sample profile: a fictional worker with a synthetic voice, recorded ${sample.scene_label.toLowerCase()}. Everything below was produced live by Kaam from that audio.`;
  $("sample-note").hidden = false;
  $("comparison").replaceChildren(...comparison.map((c) => {
    const li = el("li");
    const said = el("div", null, "said");
    said.append(el("span", "Said"), el("span", c.script));
    const heard = el("div", null, "heard");
    heard.append(el("span", "Heard"), el("span", c.heard || "(nothing)"));
    li.append(el("div", c.question, "q"), said, heard);
    return li;
  }));
  $("comparison-block").hidden = false;
}

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

  const stats = [];
  if (p.years_experience != null) stats.push(stat(`${p.years_experience} yrs`, "experience"));
  if (p.languages_spoken.length) stats.push(stat(p.languages_spoken.join(" · "), "speaks"));
  if (p.preferred_areas.length) stats.push(stat(p.preferred_areas.join(", "), "wants to work in"));
  $("stats").replaceChildren(...stats);

  $("skills").replaceChildren(...p.skills_en.map((skill, i) => {
    const li = el("li", skill);
    const translated = native && p.skills_native[i];
    if (translated && translated !== skill) {
      const small = el("small", translated);
      small.lang = language;
      li.append(small);
    }
    return li;
  }));

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
  }
  if (p.experience.length) {
    $("experience").replaceChildren(...p.experience.map((x) => {
      const li = el("li");
      const title = [x.role_en, x.where_en].filter(Boolean).join(" · ");
      li.append(el("strong", title));
      if (x.duration) li.append(el("span", ` (${x.duration})`));
      if (x.details_en) li.append(el("div", x.details_en, "muted"));
      return li;
    }));
  } else {
    $("experience-block").hidden = true;
  }
  if (p.proud_of_en) $("proud").textContent = p.proud_of_en;
  else $("proud-block").hidden = true;

  const details = [
    ["Trade", p.trade_en],
    ["Experience", p.years_experience != null ? `${p.years_experience} years` : null],
    ["Hometown", p.hometown],
    ["Lives in", p.current_city],
    ["Wants to work in", p.preferred_areas.join(", ")],
    ["Expected pay", p.expected_pay_en],
    ["Languages", p.languages_spoken.join(", ")],
  ].filter(([, v]) => v);
  $("details").replaceChildren(...details.flatMap(([k, v]) => [el("dt", k), el("dd", v)]));

  // Sharing
  const shareText = `${name} · ${p.trade_en}. Hear ${first} talk about their work: ${pageUrl} #KaamChallenge`;
  $("whatsapp").href = `https://wa.me/?text=${encodeURIComponent(shareText)}`;
  $("copy").addEventListener("click", async () => {
    await navigator.clipboard.writeText(pageUrl);
    $("copy").textContent = "Link copied";
    setTimeout(() => { $("copy").textContent = "Copy link"; }, 2000);
  });
  $("download").addEventListener("click", async () => {
    $("download").textContent = "Preparing…";
    const canvas = await html2canvas($("card"), { scale: 2, backgroundColor: null });
    const link = document.createElement("a");
    link.download = `kaam-${(p.name || "profile").toLowerCase().replace(/\s+/g, "-")}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
    $("download").textContent = "Download card";
  });
  $("print").addEventListener("click", () => window.print());

  if (sample && comparison) renderSample(sample, comparison);

  $("status").hidden = true;
  for (const id of ["card", "actions", "resume"]) $(id).hidden = false;
}

fetch(`/api/profiles/${profileId}`)
  .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? "Profile not found." : `Error ${r.status}`))))
  .then(render)
  .catch((err) => { $("status").textContent = err.message; });
