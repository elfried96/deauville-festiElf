// Public website of the festival. Every piece of data comes from the API
// (see API.md). No framework: plain functions that fetch JSON and build HTML.

async function getJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Error ${response.status}`);
  }
  return data;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatDay(isoDay, options = { weekday: "long", day: "numeric", month: "long" }) {
  const day = new Date(isoDay + "T12:00");
  return day.toLocaleDateString("en-GB", options);
}

function formatTime(isoDateTime) {
  return isoDateTime.slice(11, 16);
}

function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) {
    return `${rest} min`;
  }
  return rest === 0 ? `${hours} h` : `${hours} h ${String(rest).padStart(2, "0")}`;
}

function datesText(festival) {
  const first = formatDay(festival.first_day, { day: "numeric" });
  const last = formatDay(festival.last_day, { day: "numeric", month: "long", year: "numeric" });
  return `${first} — ${last}`;
}

// --- Photos ----------------------------------------------------------------

// Each artist has their own colour, behind their portrait.
const TONES = ["#f2c4ae", "#c4d3f2", "#cfe3bf", "#f2dfa8", "#dfc8ea", "#bfe3dc"];

// Colours and portraits follow the alphabetical list of artists, so
// neighbours always differ and an artist looks the same on every page.
const toneByName = {};
const indexByName = {};
const photoByName = {};

function setTones(artists) {
  artists.forEach((artist, index) => {
    toneByName[artist.name] = TONES[index % TONES.length];
    indexByName[artist.name] = index;
    photoByName[artist.name] = artist.photo_url;
  });
}

function toneOf(name) {
  return toneByName[name] || TONES[name.length % TONES.length];
}

// --- Illustrated portraits ---------------------------------------------------
//
// Until an artist has a photo, they get a drawn silhouette of a comedian at
// the microphone, on their own colour. Four poses and five hairstyles give
// every artist of the festival a different portrait.

const INK = "#141414";
const MIC_HEAD = "#dcdad4";

const HAIR = [
  "",
  `<path d="M71 86c-2-26 13-37 29-37s32 11 30 37c-6-13-17-19-30-19s-23 6-29 19z"/>`,
  `<path d="M71 86c-2-26 13-37 29-37s32 11 30 37c-6-13-17-19-30-19s-23 6-29 19z"/>
   <circle cx="100" cy="44" r="13"/>`,
  `<path d="M67 92c-5-34 12-46 33-46s38 12 33 46l5 44c-12-2-18-10-20-26H82c-2 16-8 24-20 26z"/>`,
  `<circle cx="80" cy="66" r="13"/><circle cx="94" cy="56" r="14"/>
   <circle cx="110" cy="56" r="14"/><circle cx="123" cy="67" r="13"/>
   <circle cx="73" cy="82" r="9"/><circle cx="128" cy="82" r="9"/>`,
];

// An arm drawn twice: a wider stroke in the background colour first, so the
// arm stands out from the body.
function arm(d, tone, width = 15) {
  return `
    <path d="${d}" fill="none" stroke="${tone}" stroke-width="${width + 6}" stroke-linecap="round"/>
    <path d="${d}" fill="none" stroke="${INK}" stroke-width="${width}" stroke-linecap="round"/>`;
}

// A stage microphone: a grilled ball head, a metal ring and a tapered
// handle, drawn around (0, 0) = the centre of the head, handle downwards.
// With `hand`, a fist grips the handle.
function mic(x, y, angle, tone, hand = true) {
  const fist = hand
    ? `<ellipse cx="0" cy="30" rx="10" ry="9" fill="${INK}" stroke="${tone}" stroke-width="2.5"/>`
    : "";
  return `
    <g transform="translate(${x} ${y}) rotate(${angle})">
      <path d="M-7 13h14l-3 33c-1 3-7 3-8 0z" fill="#2b2b2b" stroke="${tone}" stroke-width="2"/>
      <rect x="-8.5" y="9" width="17" height="6" rx="3" fill="#8f8c85"/>
      <circle cx="0" cy="0" r="12.5" fill="${MIC_HEAD}" stroke="${tone}" stroke-width="2.5"/>
      <path d="M-11 -4h22M-12 1h24M-10 6h20M-5 -11v22M0 -12.5v25M5 -11v22"
            stroke="#a6a39b" stroke-width="1.1"/>
      ${fist}
    </g>`;
}

// Four poses: microphone at the mouth, the same with a raised arm, a
// microphone on a stand, and a microphone held low while telling a story.
const POSES = [
  (tone) => arm("M154 196c2-28-10-46-32-58", tone) + mic(112, 112, -14, tone),
  (tone) =>
    arm("M154 196c2-28-10-46-32-58", tone) +
    mic(112, 112, -14, tone) +
    arm("M56 176c-14-22-18-50-10-80", tone, 14) +
    `<circle cx="46" cy="92" r="10" stroke="${tone}" stroke-width="3"/>`,
  (tone) => `
    <path d="M104 200V146" stroke="${MIC_HEAD}" stroke-width="5"/>
    <path d="M84 199h40" stroke="${MIC_HEAD}" stroke-width="5" stroke-linecap="round"/>
    <rect x="98" y="138" width="12" height="10" rx="3" fill="#8f8c85"/>
    ${mic(106, 114, -6, tone, false)}`,
  (tone) =>
    arm("M152 196c0-18-14-30-31-36", tone) +
    mic(126, 132, 12, tone) +
    arm("M48 196c0-34 12-54 30-62", tone, 14),
];

function outfit(index, tone) {
  const shirt = "#f4f2ee";
  switch (index % 3) {
    case 0:
      return `
        <path d="M86 140l14 34 14-34z" fill="${shirt}"/>
        <path d="M84 139l16 40M116 139l-16 40" stroke="${tone}" stroke-width="2.5"/>`;
    case 1:
      return `
        <path d="M88 140l12 22 12-22z" fill="${shirt}"/>
        <path d="M90 150l10 6-10 6zM110 150l-10 6 10 6z" fill="${tone}"/>
        <circle cx="100" cy="156" r="3" fill="${tone}"/>`;
    default:
      return `<path d="M86 138h28v10c0 4-6 7-14 7s-14-3-14-7z" fill="${tone}" opacity="0.55"/>`;
  }
}

// Round glasses for one artist in three, in the colour of the microphone.
function glasses(index) {
  if (index % 3 !== 1) {
    return "";
  }
  return `
    <g fill="none" stroke="${MIC_HEAD}" stroke-width="3">
      <circle cx="89" cy="92" r="8"/><circle cx="111" cy="92" r="8"/>
      <path d="M97 91h6"/>
    </g>`;
}

// `crop` frames the face only, for small round avatars.
function portraitSvg(name, crop = false) {
  const index = indexByName[name] ?? name.length;
  const tone = toneOf(name);
  const hair = HAIR[(index * 3) % HAIR.length];
  const pose = POSES[index % POSES.length];
  const longHair = hair.includes("l5 44");
  return `
    <svg viewBox="${crop ? "38 42 124 124" : "0 0 200 200"}" fill="${INK}" aria-hidden="true">
      <path d="M100 0L40 200h120z" fill="#ffffff" opacity="0.18"/>
      <ellipse cx="100" cy="96" rx="74" ry="74" fill="#ffffff" opacity="0.28"/>
      ${longHair ? hair : ""}
      <path d="M38 200c4-44 28-64 62-64s58 20 62 64z"/>
      ${outfit(index, tone)}
      <rect x="89" y="110" width="22" height="30" rx="9"/>
      <ellipse cx="100" cy="90" rx="27" ry="31"/>
      ${longHair ? "" : hair}
      ${glasses(index + 1)}
      ${pose(tone)}
    </svg>`;
}

function photoHtml(name, photoUrl) {
  const tone = `style="--tone: ${toneOf(name)}"`;
  if (photoUrl) {
    return `<div class="photo" ${tone}><img src="${escapeHtml(photoUrl)}" alt="" /></div>`;
  }
  return `<div class="photo portrait" ${tone}>${portraitSvg(name)}</div>`;
}

// --- A performance ---------------------------------------------------------

const KIND_LABELS = { solo: "Solo", lineup: "Lineup", workshop: "Workshop" };

function artistLink(artist) {
  return `<a href="/artist.html?slug=${artist.slug}">${escapeHtml(artist.name)}</a>`;
}

function listOf(artists) {
  const links = artists.map(artistLink);
  if (links.length < 2) {
    return links.join("");
  }
  return `${links.slice(0, -1).join(", ")} and ${links[links.length - 1]}`;
}

function whoHtml(performance) {
  const artists = performance.artists;
  if (artists.length === 0) {
    return "";
  }
  if (performance.kind === "lineup") {
    return `Hosted by ${artistLink(artists[0])}, with ${listOf(artists.slice(1))}`;
  }
  if (performance.kind === "workshop") {
    return `Workshop with ${artistLink(artists[0])}`;
  }
  return listOf(artists);
}

function detailText(performance) {
  const kind = KIND_LABELS[performance.kind] || performance.kind;
  if (performance.kind === "workshop") {
    return `${kind} · ${performance.places_left} place(s) left`;
  }
  if (performance.kind === "solo" && performance.min_age > 0) {
    return `${kind} · ${performance.min_age}+`;
  }
  return `${kind} · ${formatDuration(performance.duration_minutes)}`;
}

// The artists of a performance as small overlapping portraits.
function avatarsHtml(artists) {
  const faces = artists.slice(0, 3).map((artist) => {
    const photo = photoByName[artist.name];
    const inside = photo ? `<img src="${escapeHtml(photo)}" alt="" />` : portraitSvg(artist.name, true);
    return `<span class="avatar" style="--tone: ${toneOf(artist.name)}">${inside}</span>`;
  });
  const more = artists.length > 3 ? `<span class="avatar more">+${artists.length - 3}</span>` : "";
  return `<div class="avatars" aria-hidden="true">${faces.join("")}${more}</div>`;
}

function rowHtml(performance) {
  return `
    <li class="row">
      <div class="row-time">${formatTime(performance.start)}
        <small>to ${formatTime(performance.end)}</small></div>
      ${avatarsHtml(performance.artists)}
      <div>
        <h3 class="row-title">${escapeHtml(performance.title)}</h3>
        <p class="row-who">${whoHtml(performance)}</p>
      </div>
      <div class="row-meta">
        <span>${escapeHtml(performance.venue_name)}</span>
        <span>${detailText(performance)}</span>
      </div>
    </li>`;
}

// --- Home page -------------------------------------------------------------

const state = { day: null, venue: "", kind: "" };

async function showHomePage() {
  const festival = await getJson("/api/festival");
  document.getElementById("dates").textContent =
    `${datesText(festival)} · Deauville, Normandy`;
  document.getElementById("footer-dates").textContent = datesText(festival);

  const days = document.getElementById("days");
  for (const day of festival.days) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tab";
    button.dataset.day = day;
    button.innerHTML = `<small>${formatDay(day, { weekday: "long" })}</small>
      <span>${formatDay(day, { day: "numeric", month: "long" })}</span>`;
    button.addEventListener("click", () => selectDay(day));
    days.appendChild(button);
  }

  const venues = await getJson("/api/venues");
  const filter = document.getElementById("venue-filter");
  for (const venue of venues) {
    filter.add(new Option(venue.name, venue.slug));
  }
  filter.addEventListener("change", () => {
    state.venue = filter.value;
    showProgramme();
  });
  const kindFilter = document.getElementById("kind-filter");
  kindFilter.addEventListener("change", () => {
    state.kind = kindFilter.value;
    showProgramme();
  });

  const artists = await getJson("/api/artists");
  setTones(artists);

  selectDay(festival.days[0]);
  const performances = await getJson("/api/programme");
  showFigures(festival, venues, artists, performances);
  showGlance(festival, performances);
  showNow(festival);
  showArtists(artists);
  showVenues(venues);
}

// The key figures under the cover, all computed from the API.
function showFigures(festival, venues, artists, performances) {
  const seats = venues.reduce((total, venue) => total + venue.capacity, 0);
  const figures = [
    [festival.days.length, "days"],
    [venues.length, "stages on the seafront"],
    [performances.length, "performances"],
    [artists.length, "comedians"],
    [seats.toLocaleString("en-GB"), "seats each evening"],
  ];
  document.getElementById("figures").innerHTML = figures
    .map(([value, label]) => `<div><dd>${value}</dd><dt>${label}</dt></div>`)
    .join("");
}

// The dark band: each day, its number of shows and its evening.
function showGlance(festival, performances) {
  const items = festival.days.map((day) => {
    const shows = performances.filter((p) => p.festival_day === day);
    const evening = shows.filter((p) => formatTime(p.start) >= "18:00").slice(0, 3);
    const lines = evening
      .map((p) => `<span><b>${formatTime(p.start)}</b>${escapeHtml(p.title)}</span>`)
      .join("");
    return `
      <li><a class="glance-day" href="#programme" data-day="${day}">
        <small>${formatDay(day, { weekday: "long" })}</small>
        <strong>${formatDay(day, { day: "numeric" })}</strong>
        <span class="count">${shows.length} shows</span>
        ${lines}
      </a></li>`;
  });
  const list = document.getElementById("glance");
  list.innerHTML = items.join("");
  for (const link of list.querySelectorAll(".glance-day")) {
    link.addEventListener("click", () => selectDay(link.dataset.day));
  }
}

function selectDay(day) {
  state.day = day;
  for (const button of document.querySelectorAll("#days .tab")) {
    button.setAttribute("aria-pressed", button.dataset.day === day);
  }
  showProgramme();
}

async function showProgramme() {
  let url = `/api/programme?day=${state.day}`;
  if (state.venue) {
    url += `&venue=${state.venue}`;
  }
  let performances = await getJson(url);
  if (state.kind) {
    performances = performances.filter((p) => p.kind === state.kind);
  }
  const rows = performances.map(rowHtml);
  document.getElementById("rows").innerHTML =
    rows.join("") || `<li class="empty">No performance matches these filters on this day.</li>`;
}

async function showNow(festival) {
  // "?at=2027-06-11T21:00" in the address pretends it is that moment.
  const at = new URLSearchParams(window.location.search).get("at");
  const url = at ? `/api/now?at=${encodeURIComponent(at)}` : "/api/now";
  const now = await getJson(url);
  const box = document.getElementById("now");

  if (now.now_playing.length > 0) {
    const current = now.now_playing[0];
    const next = now.up_next[0];
    box.innerHTML = `
      <span class="live-label">Live now</span>
      <strong>${escapeHtml(current.title)}</strong>
      <span class="muted">${escapeHtml(current.summary)} · ${escapeHtml(current.venue_name)}
        · until ${formatTime(current.end)}</span>
      <span class="spacer"></span>
      ${next ? `<span class="muted">Next: ${escapeHtml(next.title)} at ${formatTime(next.start)}</span>` : ""}`;
  } else if (now.up_next.length === 0) {
    box.innerHTML = `<span class="live-label">The festival is over</span>
      <span class="muted">See you next year on the boardwalk.</span>`;
  } else if (now.at < festival.first_day) {
    const evening = festival.days[1] || festival.days[0];
    box.innerHTML = `<span class="live-label">Starts ${formatDay(festival.first_day)}</span>
      <span class="spacer"></span>
      <a class="muted" href="?at=${evening}T21:00">Preview a festival evening</a>`;
  } else {
    const next = now.up_next[0];
    box.innerHTML = `<span class="live-label">Up next</span>
      <strong>${escapeHtml(next.title)}</strong>
      <span class="muted">${formatDay(next.festival_day)}, ${formatTime(next.start)}
        · ${escapeHtml(next.venue_name)}</span>`;
  }
}

function showArtists(artists) {
  document.getElementById("artist-count").textContent = `${artists.length} artists`;
  document.getElementById("artist-grid").innerHTML = artists
    .map(
      (artist) => `
      <a class="tile" href="/artist.html?slug=${artist.slug}">
        ${photoHtml(artist.name, artist.photo_url)}
        <span class="tile-head"><span class="tile-name">${escapeHtml(artist.name)}</span></span>
        <span class="tile-text">${escapeHtml(artist.bio)}</span>
      </a>`,
    )
    .join("");
}

// Photos of the venues (Wikimedia Commons, credited in the footer).
const VENUE_PHOTOS = {
  "grand-casino": "/images/casino.jpg",
  "theatre-des-planches": "/images/theatre.jpg",
  "le-kiosque": "/images/beach-cabins.jpg",
  "la-cabane": "/images/parasols-folded.jpg",
};

function showVenues(venues) {
  document.getElementById("venue-grid").innerHTML = venues
    .map((venue) => {
      const photo = VENUE_PHOTOS[venue.slug];
      const image = photo ? `<img src="${photo}" alt="" loading="lazy" />` : "";
      return `
      <div class="venue-card">
        <div class="photo" style="--tone: ${toneOf(venue.name)}">
          ${image}
          <span class="seats">${venue.capacity}<small>seats</small></span>
        </div>
        <span class="tile-name">${escapeHtml(venue.name)}</span>
        <span class="tile-text">${escapeHtml(venue.address)}</span>
      </div>`;
    })
    .join("");
}

// --- Artist page -----------------------------------------------------------

function roleOf(performance, slug) {
  if (performance.kind === "lineup") {
    return performance.host === slug ? "Host" : "Act";
  }
  if (performance.kind === "workshop") {
    return "Teacher";
  }
  return "Solo";
}

async function showArtistPage() {
  const slug = new URLSearchParams(window.location.search).get("slug");
  try {
    const artist = await getJson(`/api/artists/${slug}`);
    const everyone = await getJson("/api/artists");
    setTones(everyone);
    const photos = {};
    for (const other of everyone) {
      photos[other.slug] = other.photo_url;
    }

    document.title = `${artist.name} — Festival du Rire`;
    document.getElementById("crumb").textContent = artist.name;
    document.getElementById("artist-name").textContent = artist.name;
    document.getElementById("bio").textContent = artist.bio;
    document.getElementById("portrait").outerHTML = photoHtml(artist.name, artist.photo_url);

    const performances = artist.performances;
    const days = [...new Set(performances.map((p) => p.festival_day))];
    const roles = [...new Set(performances.map((p) => roleOf(p, slug)))];
    const dayRange = days.length
      ? days.length === 1
        ? formatDay(days[0], { weekday: "short" })
        : `${formatDay(days[0], { weekday: "short" })} — ${formatDay(days[days.length - 1], { weekday: "short" })}`
      : "—";
    document.getElementById("facts").innerHTML = `
      <div><dt>Performances</dt><dd>${performances.length}</dd></div>
      <div><dt>Days</dt><dd>${dayRange}</dd></div>
      <div><dt>Roles</dt><dd>${roles.join(", ") || "—"}</dd></div>`;

    document.getElementById("shows").innerHTML =
      performances
        .map((p) => {
          const others = p.artists.filter((a) => a.slug !== slug);
          const company = others.length ? ` · with ${listOf(others)}` : "";
          return `
          <li class="show">
            <div class="show-when"><small>${formatDay(p.festival_day)}</small>
              <span>${formatTime(p.start)}</span></div>
            <div class="show-body">
              <h3 class="row-title">${escapeHtml(p.title)}</h3>
              <p class="row-who">${escapeHtml(p.venue_name)}${company}</p>
            </div>
            <span class="pill">${roleOf(p, slug)}</span>
          </li>`;
        })
        .join("") || `<li class="empty">No performance yet.</li>`;

    const together = new Map();
    for (const performance of performances) {
      for (const other of performance.artists) {
        if (other.slug !== slug) {
          together.set(other.slug, other);
        }
      }
    }
    if (together.size === 0) {
      document.getElementById("with-section").hidden = true;
    }
    document.getElementById("with-grid").innerHTML = [...together.values()]
      .slice(0, 4)
      .map(
        (other) => `
        <a class="tile" href="/artist.html?slug=${other.slug}">
          ${photoHtml(other.name, photos[other.slug])}
          <span class="tile-head"><span class="tile-name">${escapeHtml(other.name)}</span></span>
        </a>`,
      )
      .join("");
  } catch (error) {
    document.getElementById("artist-name").textContent = "Artist not found";
    document.getElementById("bio").textContent = error.message;
    document.getElementById("with-section").hidden = true;
  }
}
