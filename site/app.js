// Grondstof webspeler: leest episodes.json, toont golfvorm, hoofdstukken en een meelees-transcript.
const $ = (id) => document.getElementById(id);
const audio = $("audio");
const canvas = $("wave");
const state = { episode: null, cues: [], cueEls: [], chapterEls: [], peaks: [], pps: 12 };

const fmt = (s) => {
  s = Math.max(0, Math.floor(s || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};
const longDate = (iso) =>
  new Date(iso + "T09:00:00").toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

async function init() {
  let index;
  try {
    index = await (await fetch("episodes.json", { cache: "no-cache" })).json();
  } catch {
    return;
  }
  const show = index.show;
  $("rss-copy").addEventListener("click", async () => {
    await navigator.clipboard.writeText(show.feedUrl);
    $("rss-copy").textContent = "Gekopieerd ✓";
    setTimeout(() => ($("rss-copy").textContent = "RSS-feed kopiëren"), 2000);
  });
  if (show.linkedinUrl) $("linkedin-link").href = show.linkedinUrl;
  for (const [id, url] of [["spotify-link", show.spotifyUrl], ["apple-link", show.appleUrl]]) {
    if (url) Object.assign($(id), { href: url, hidden: false, target: "_blank", rel: "noopener" });
  }
  renderArchive(index.episodes);
  const wanted = location.hash.slice(1);
  const first = index.episodes.find((e) => e.id === wanted) || index.episodes[0];
  if (first) load(first);
}

function renderArchive(episodes) {
  $("archive").innerHTML = "";
  for (const ep of episodes) {
    const li = document.createElement("li");
    li.innerHTML = `<a href="#${ep.id}"><small>${longDate(ep.date)} · ${fmt(ep.duration)}</small><strong></strong></a>`;
    li.querySelector("strong").textContent = ep.title;
    li.querySelector("a").addEventListener("click", (e) => {
      e.preventDefault();
      history.replaceState(null, "", `#${ep.id}`);
      load(ep, true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    $("archive").appendChild(li);
  }
}

async function load(summary, autoplay = false) {
  const ep = await (await fetch(summary.detailUrl.replace(/^.*\/episodes\//, "episodes/"))).json();
  state.episode = ep;
  state.cues = ep.transcript;
  state.peaks = ep.peaks;
  state.pps = ep.peaksPerSecond;
  $("hero-date").textContent = `Aflevering ${ep.number} · ${longDate(ep.date)}`;
  $("hero-title").textContent = ep.title;
  $("hero-summary").textContent = ep.summary;
  $("player").hidden = false;
  audio.src = summary.audioUrl.replace(/^.*\/audio\//, "audio/");
  $("t-total").textContent = fmt(ep.duration);

  const nod = ep.numberOfTheDay;
  $("number").hidden = !nod;
  if (nod) {
    $("number-value").textContent = nod.value;
    $("number-label").textContent = nod.label;
  }

  const tr = $("transcript");
  tr.innerHTML = "";
  state.cueEls = [];
  let lastChapter = -1;
  let p;
  for (const cue of ep.transcript) {
    if (cue.chapter !== lastChapter) {
      lastChapter = cue.chapter;
      const h = document.createElement("h3");
      h.textContent = ep.chapters[cue.chapter].title;
      tr.appendChild(h);
      p = document.createElement("p");
      tr.appendChild(p);
    }
    const span = document.createElement("span");
    span.textContent = cue.text + " ";
    span.addEventListener("click", () => seek(cue.start));
    p.appendChild(span);
    state.cueEls.push(span);
  }

  const list = $("chapters");
  list.innerHTML = "";
  state.chapterEls = ep.chapters.map((c) => {
    const li = document.createElement("li");
    const src = c.sources[0];
    li.innerHTML = `<button type="button"><time>${fmt(c.start)}</time><span><small>${c.kindLabel}</small><b></b></span></button>`;
    li.querySelector("b").textContent = c.title;
    li.querySelector("b").style.fontWeight = 500;
    if (src) {
      const a = document.createElement("a");
      Object.assign(a, { href: src.url, target: "_blank", rel: "noopener", textContent: src.publisher || "bron" });
      li.querySelector("span").appendChild(a);
    }
    li.querySelector("button").addEventListener("click", () => seek(c.start));
    list.appendChild(li);
    return li;
  });
  draw();
  if (autoplay) audio.play();
}

function seek(t) {
  audio.currentTime = t;
  if (audio.paused) audio.play();
}

function draw() {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const bars = Math.max(40, Math.floor(w / 4));
  const dur = state.episode ? state.episode.duration : 1;
  const progress = (audio.currentTime || 0) / dur;
  const grad = ctx.createLinearGradient(0, 0, w, 0);
  grad.addColorStop(0, "#ffb547");
  grad.addColorStop(1, "#ff6a1a");
  for (let i = 0; i < bars; i++) {
    const from = Math.floor((i / bars) * state.peaks.length);
    const to = Math.max(from + 1, Math.floor(((i + 1) / bars) * state.peaks.length));
    let v = 0;
    for (let j = from; j < to; j++) v = Math.max(v, state.peaks[j] || 0);
    const bh = Math.max(2, v * (h - 6));
    ctx.fillStyle = i / bars <= progress ? grad : "rgba(255,244,230,.22)";
    ctx.beginPath();
    ctx.roundRect(i * (w / bars) + 0.5, (h - bh) / 2, Math.max(1.5, w / bars - 1.6), bh, 2);
    ctx.fill();
  }
}

function tick() {
  const t = audio.currentTime;
  $("t-now").textContent = fmt(t);
  let active = -1;
  state.cues.forEach((c, i) => {
    if (t >= c.start) active = i;
  });
  state.cueEls.forEach((el, i) => el.classList.toggle("on", i === active));
  if (active >= 0 && !audio.paused) {
    const el = state.cueEls[active];
    const box = $("transcript");
    if (el.offsetTop < box.scrollTop + 40 || el.offsetTop > box.scrollTop + box.clientHeight - 80) {
      box.scrollTop = el.offsetTop - 60;
    }
  }
  if (state.episode) {
    const chapters = state.episode.chapters;
    let ci = 0;
    chapters.forEach((c, i) => {
      if (t >= c.start) ci = i;
    });
    state.chapterEls.forEach((el, i) => el.classList.toggle("on", i === ci));
    $("chapter-now").textContent = chapters[ci].title;
  }
  draw();
}

$("play").addEventListener("click", () => (audio.paused ? audio.play() : audio.pause()));
canvas.addEventListener("click", (e) => {
  if (!state.episode) return;
  const r = canvas.getBoundingClientRect();
  seek(((e.clientX - r.left) / r.width) * state.episode.duration);
});
audio.addEventListener("play", () => document.body.classList.add("playing"));
audio.addEventListener("pause", () => document.body.classList.remove("playing"));
audio.addEventListener("timeupdate", tick);
window.addEventListener("resize", draw);
init();
