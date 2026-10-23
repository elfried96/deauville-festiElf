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

// Until real photos are uploaded, each artist or venue gets a quiet tone,
// always the same one, and a caption saying which photo goes there.
const TONES = ["#d9d3cb", "#c9cfd4", "#d6cfc6", "#cdd2cb", "#d3ccd1", "#cfcac2"];

function toneOf(text) {
  let sum = 0;
  for (const character of text) {
    sum += character.charCodeAt(0);
  }
  return TONES[sum % TONES.length];
}

function photoHtml(name, photoUrl, caption = true) {
  const tone = `style="--tone: ${toneOf(name)}"`;
  if (photoUrl) {
    return `<div class="photo" ${tone}><img src="${escapeHtml(photoUrl)}" alt="" /></div>`;
  }
  const label = caption ? `<span class="caption">Photo · ${escapeHtml(name)}</span>` : "";
  return `<div class="photo" ${tone} aria-hidden="true">${label}</div>`;
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

function rowHtml(performance, photos) {
  const first = performance.artists[0];
  const photo = first
    ? photoHtml(first.name, photos[first.slug], false)
    : photoHtml(performance.title, "", false);
  return `
    <li class="row">
      <div class="row-time">${formatTime(performance.start)}
        <small>to ${formatTime(performance.end)}</small></div>
      ${photo}
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

const state = { day: null, venue: "", kind: "", photos: {} };

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
  for (const artist of artists) {
    state.photos[artist.slug] = artist.photo_url;
  }

  selectDay(festival.days[0]);
  showNow(festival);
  showArtists(artists);
  showVenues(venues);
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
  const rows = performances.map((p) => rowHtml(p, state.photos));
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

function showVenues(venues) {
  document.getElementById("venue-grid").innerHTML = venues
    .map(
      (venue) => `
      <div class="tile">
        ${photoHtml(venue.name, "")}
        <span class="tile-head">
          <span class="tile-name">${escapeHtml(venue.name)}</span>
          <span class="tile-note">${venue.capacity} seats</span>
        </span>
        <span class="tile-text">${escapeHtml(venue.address)}</span>
      </div>`,
    )
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
