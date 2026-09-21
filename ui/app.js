const form = document.querySelector("#agent-form");
const messageInput = document.querySelector("#message");
const modeInput = document.querySelector("#mode");
const providerInput = document.querySelector("#provider");
const taskInput = document.querySelector("#task");
const counter = document.querySelector("#counter");
const reply = document.querySelector("#reply");
const state = document.querySelector("#state");
const askButton = document.querySelector("#ask-button");
const voiceButton = document.querySelector("#voice-button");
const voiceStatus = document.querySelector("#voice-status");
const speakToggle = document.querySelector("#speak-toggle");
const agentStatus = document.querySelector("#agent-status");
const actionSummary = document.querySelector("#action-summary");
const checkButton = document.querySelector("#check-button");
const checkSummary = document.querySelector("#check-summary");
const checkList = document.querySelector("#check-list");
const orb = document.querySelector("#orb");
const networkCanvas = document.querySelector("#network-canvas");
const networkStage = document.querySelector("#network-stage");
const visualState = document.querySelector("#visual-state");
const planDetails = document.querySelector("#plan-details");
const planLists = {
  steps: document.querySelector("#steps"),
  files: document.querySelector("#files"),
  tests: document.querySelector("#tests"),
  risks: document.querySelector("#risks")
};
const bridgeStatus = document.querySelector("#bridge-status");
const activityLog = document.querySelector("#activity-log");
const commandHistory = document.querySelector("#command-history");
const historyCount = document.querySelector("#history-count");
const sceneTimeline = document.querySelector("#scene-timeline");
const clearActivity = document.querySelector("#clear-activity");
const capabilityNodes = [...document.querySelectorAll("[data-capability]")];
const quickCommands = [...document.querySelectorAll("[data-command]")];
const sceneWorkspace = document.querySelector("#scene-workspace");
const sceneMode = document.querySelector("#scene-mode");
const sceneVisual = document.querySelector("#scene-visual");
const sceneKicker = document.querySelector("#scene-kicker");
const sceneTitle = document.querySelector("#scene-title");
const sceneSubtitle = document.querySelector("#scene-subtitle");
const sceneStatus = document.querySelector("#scene-status");
const sceneProgress = document.querySelector("#scene-progress-bar");
const sceneResponse = document.querySelector("#scene-response");
const sceneProvider = document.querySelector("#scene-provider");
const sceneSignals = document.querySelector("#scene-signals");
const sceneRegionTitle = document.querySelector("#scene-region-title");
const sceneRegionMeta = document.querySelector("#scene-region-meta");
const sceneRegionNews = document.querySelector("#scene-region-news");
const sceneRegionWeather = document.querySelector("#scene-region-weather");
const sceneRegionTime = document.querySelector("#scene-region-time");
const sceneRegionCoordinates = document.querySelector("#scene-region-coordinates");
const sceneRegionImage = document.querySelector("#scene-region-image");
const telemetry = {
  processCount: document.querySelector("#process-count"),
  memoryValue: document.querySelector("#memory-value"),
  memoryMeter: document.querySelector("#memory-meter"),
  latencyValue: document.querySelector("#latency-value"),
  latencyState: document.querySelector("#latency-state"),
  state: document.querySelector("#telemetry-state")
};
const clock = document.querySelector("#clock");
const dateLabel = document.querySelector("#date-label");
const greeting = document.querySelector(".hero-strip h1");
let taskWindow = null;
let pendingTaskPayload = null;
let threeReady = null;
let threeScene = null;
let threeFrameToken = 0;
let commandHistoryState = [];
let sceneAutoOpen = false;

function renderCommandHistory() {
  if (!commandHistory) return;
  commandHistory.replaceChildren();
  if (!commandHistoryState.length) {
    const empty = document.createElement("li");
    empty.className = "history-empty";
    empty.textContent = "Noch keine Befehle";
    commandHistory.appendChild(empty);
  } else {
    commandHistoryState.forEach((entry, index) => {
      const item = document.createElement("li");
      item.className = "history-entry";
      item.style.setProperty("--history-index", index);
      const marker = document.createElement("i");
      const text = document.createElement("span");
      text.textContent = entry.message;
      const time = document.createElement("time");
      time.textContent = entry.time;
      item.append(marker, text, time);
      commandHistory.appendChild(item);
    });
  }
  if (historyCount) historyCount.textContent = String(commandHistoryState.length).padStart(2, "0");
}

function rememberCommand(message, mode) {
  commandHistoryState.unshift({
    message: message.slice(0, 92),
    mode,
    time: new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" }).format(new Date())
  });
  commandHistoryState = commandHistoryState.slice(0, 6);
  window.localStorage.setItem("jarvis-command-history", JSON.stringify(commandHistoryState));
  renderCommandHistory();
}

function restoreCommandHistory() {
  try {
    const stored = JSON.parse(window.localStorage.getItem("jarvis-command-history") || "[]");
    if (Array.isArray(stored)) commandHistoryState = stored.slice(0, 6);
  } catch {
    commandHistoryState = [];
  }
  renderCommandHistory();
}

function renderTimeline(message, status = "active") {
  if (!sceneTimeline) return;
  const steps = message.split(/\s*(?:;|\bund dann\b|\bdann\b|\bdanach\b|\beanschließend\b|\beanschliessend\b)\s*/i)
    .map((step) => step.trim())
    .filter(Boolean);
  sceneTimeline.replaceChildren();
  steps.forEach((step, index) => {
    const item = document.createElement("li");
    item.className = index === 0 && status === "active" ? "timeline-active" : status === "done" ? "timeline-done" : "";
    item.style.setProperty("--timeline-index", index);
    const marker = document.createElement("i");
    const text = document.createElement("span");
    text.textContent = step;
    item.append(marker, text);
    sceneTimeline.appendChild(item);
  });
}

function updateHudClock() {
  const now = new Date();
  if (clock) {
    clock.textContent = new Intl.DateTimeFormat("de-DE", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }).format(now);
  }
  if (dateLabel) {
    dateLabel.textContent = new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    }).format(now).replace(/\./g, "").toUpperCase();
  }
  if (greeting) {
    const hour = now.getHours();
    const salutation = hour < 5 ? "Gute Nacht" : hour < 12 ? "Guten Morgen" : hour < 18 ? "Guten Tag" : "Guten Abend";
    greeting.firstChild.textContent = `${salutation}, `;
  }
}

const cityCoordinates = {
  berlin: [52.52, 13.405, "BERLIN"],
  tokyo: [35.6762, 139.6503, "TOKYO"],
  tokio: [35.6762, 139.6503, "TOKYO"],
  london: [51.5072, -0.1276, "LONDON"],
  paris: [48.8566, 2.3522, "PARIS"],
  moskau: [55.7558, 37.6173, "MOSCOW"],
  moscow: [55.7558, 37.6173, "MOSCOW"],
  newyork: [40.7128, -74.006, "NEW YORK"],
  "new york": [40.7128, -74.006, "NEW YORK"],
  washington: [38.9072, -77.0369, "WASHINGTON"],
  peking: [39.9042, 116.4074, "BEIJING"],
  beijing: [39.9042, 116.4074, "BEIJING"],
  singapur: [1.3521, 103.8198, "SINGAPORE"],
  singapore: [1.3521, 103.8198, "SINGAPORE"]
  ,reykjavik: [64.1466, -21.9426, "REYKJAVIK"]
  ,wien: [48.2082, 16.3738, "VIENNA"]
  ,vienna: [48.2082, 16.3738, "VIENNA"]
  ,rom: [41.9028, 12.4964, "ROME"]
  ,rome: [41.9028, 12.4964, "ROME"]
  ,madrid: [40.4168, -3.7038, "MADRID"]
  ,amsterdam: [52.3676, 4.9041, "AMSTERDAM"]
  ,istanbul: [41.0082, 28.9784, "ISTANBUL"]
  ,dubai: [25.2048, 55.2708, "DUBAI"]
  ,mumbai: [19.076, 72.8777, "MUMBAI"]
  ,delhi: [28.6139, 77.209, "NEW DELHI"]
  ,seoul: [37.5665, 126.978, "SEOUL"]
  ,sydney: [-33.8688, 151.2093, "SYDNEY"]
  ,toronto: [43.6532, -79.3832, "TORONTO"]
  ,mexiko: [19.4326, -99.1332, "MEXICO CITY"]
  ,mexicocity: [19.4326, -99.1332, "MEXICO CITY"]
};
const countryCoordinates = {
  deutschland: [51.1657, 10.4515, "DEUTSCHLAND"],
  germany: [51.1657, 10.4515, "GERMANY"],
  japan: [36.2048, 138.2529, "JAPAN"],
  frankreich: [46.2276, 2.2137, "FRANKREICH"],
  france: [46.2276, 2.2137, "FRANCE"],
  italien: [41.8719, 12.5674, "ITALIEN"],
  italy: [41.8719, 12.5674, "ITALY"],
  spanien: [40.4637, -3.7492, "SPANIEN"],
  spain: [40.4637, -3.7492, "SPAIN"],
  uk: [55.3781, -3.436, "UNITED KINGDOM"],
  england: [52.3555, -1.1743, "ENGLAND"],
  usa: [39.8283, -98.5795, "USA"],
  amerika: [39.8283, -98.5795, "USA"],
  kanada: [56.1304, -106.3468, "KANADA"],
  canada: [56.1304, -106.3468, "CANADA"],
  australien: [-25.2744, 133.7751, "AUSTRALIEN"],
  australia: [-25.2744, 133.7751, "AUSTRALIA"],
  brasilien: [-14.235, -51.9253, "BRASILIEN"],
  brazil: [-14.235, -51.9253, "BRAZIL"],
  indien: [20.5937, 78.9629, "INDIEN"],
  india: [20.5937, 78.9629, "INDIA"],
  china: [35.8617, 104.1954, "CHINA"],
  russland: [61.524, 105.3188, "RUSSLAND"],
  russia: [61.524, 105.3188, "RUSSIA"]
};
const locationCache = new Map();
const regionImages = {
  BERLIN: "https://images.unsplash.com/photo-1560969184-10fe8719e047?auto=format&fit=crop&w=900&q=80",
  TOKYO: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=900&q=80",
  LONDON: "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=900&q=80",
  PARIS: "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=900&q=80",
  ROME: "https://images.unsplash.com/photo-1529260830199-42c24126f198?auto=format&fit=crop&w=900&q=80"
};

function inferLocation(message) {
  const value = message.toLowerCase().replace(/[.,!?]/g, " ");
  const cityKey = Object.keys(cityCoordinates)
    .sort((a, b) => b.length - a.length)
    .find((name) => new RegExp(`(^|\\s)${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?=\\s|$)`, "i").test(value));
  const key = cityKey || Object.keys(countryCoordinates)
    .sort((a, b) => b.length - a.length)
    .find((name) => new RegExp(`(^|\\s)${name}(?=\\s|$)`, "i").test(value));
  if (!key) return null;
  const [lat, lon, label] = cityKey ? cityCoordinates[key] : countryCoordinates[key];
  return { lat, lon, label, precision: cityKey ? "city" : "country" };
}

async function geocodeLocation(message) {
  const known = inferLocation(message);
  if (known) return known;
  const query = message
    .replace(/^(zeige|zeig|was|wie|aktuell|neueste|news|nachrichten|informationen|infos)\b/gi, "")
    .replace(/\b(über|ueber|in|von|für|fuer|zu|der|die|das|mir|aktuell|heute)\b/gi, " ")
    .replace(/[?!.,]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!query || query.length < 2 || query.length > 80) return null;
  if (locationCache.has(query)) return locationCache.get(query);
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&addressdetails=1&q=${encodeURIComponent(query)}`,
      { headers: { Accept: "application/json" } }
    );
    if (!response.ok) return null;
    const places = await response.json();
    const place = places[0];
    if (!place || !Number.isFinite(Number(place.lat)) || !Number.isFinite(Number(place.lon))) return null;
    const location = {
      lat: Number(place.lat),
      lon: Number(place.lon),
      label: String(place.name || place.display_name.split(",")[0]).toUpperCase(),
      precision: ["city", "town", "village", "municipality"].includes(place.type) ? "city" : "region"
    };
    locationCache.set(query, location);
    return location;
  } catch {
    return null;
  }
}

function locationPoint(THREE, latitude, longitude, radius) {
  const phi = (90 - latitude) * Math.PI / 180;
  const theta = (longitude + 180) * Math.PI / 180;
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

function worldPixel(latitude, longitude, zoom) {
  const scale = 256 * 2 ** zoom;
  const x = (longitude + 180) / 360 * scale;
  const sin = Math.sin(latitude * Math.PI / 180);
  const y = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale;
  return { x, y, scale };
}

function createWorldMap(location) {
  if (!sceneVisual || !location) return;
  const old = sceneVisual.querySelector(".scene-map");
  old?.remove();
  const zoom = location.precision === "city" ? 5 : 4;
  const center = worldPixel(location.lat, location.lon, zoom);
  const tileSize = 256;
  const map = document.createElement("div");
  map.className = "scene-map";
  const tileX = Math.floor(center.x / tileSize);
  const tileY = Math.floor(center.y / tileSize);
  const originX = tileX - 1;
  const originY = tileY - 1;
  for (let y = 0; y < 3; y += 1) {
    for (let x = 0; x < 3; x += 1) {
      const image = document.createElement("img");
      image.alt = "";
      image.loading = "eager";
      image.src = `https://tile.openstreetmap.org/${zoom}/${originX + x}/${originY + y}.png`;
      image.style.left = `${x * 256}px`;
      image.style.top = `${y * 256}px`;
      map.appendChild(image);
    }
  }
  const localX = center.x - originX * tileSize;
  const localY = center.y - originY * tileSize;
  map.style.left = `calc(50% - ${localX}px)`;
  map.style.top = `calc(50% - ${localY}px)`;
  const pin = document.createElement("span");
  pin.className = "scene-map-pin";
  pin.textContent = location.label;
  pin.style.left = `${localX}px`;
  pin.style.top = `${localY}px`;
  map.appendChild(pin);
  const mapCities = [
    ["BERLIN", 52.52, 13.405], ["LONDON", 51.5072, -0.1276],
    ["PARIS", 48.8566, 2.3522], ["MOSCOW", 55.7558, 37.6173],
    ["TOKYO", 35.6762, 139.6503], ["NEW YORK", 40.7128, -74.006]
  ];
  mapCities.forEach(([label, lat, lon]) => {
    if (label === location.label) return;
    const point = worldPixel(lat, lon, zoom);
    const marker = document.createElement("span");
    marker.className = `scene-map-city${label === location.label ? " is-active" : ""}`;
    marker.textContent = label;
    marker.style.left = `${point.x - originX * tileSize}px`;
    marker.style.top = `${point.y - originY * tileSize}px`;
    map.appendChild(marker);
  });
  sceneVisual.prepend(map);
}

function weatherLabel(code) {
  if (!Number.isFinite(code)) return "WETTER NICHT VERFÜGBAR";
  if (code === 0) return "KLAR";
  if ([1, 2, 3].includes(code)) return "BEWÖLKT";
  if ([45, 48].includes(code)) return "NEBEL";
  if ([51, 53, 55, 56, 57].includes(code)) return "NIESELREGEN";
  if ([61, 63, 65, 66, 67].includes(code)) return "REGEN";
  if ([71, 73, 75, 77].includes(code)) return "SCHNEE";
  if ([80, 81, 82].includes(code)) return "SCHAUER";
  if ([95, 96, 99].includes(code)) return "GEWITTER";
  return "WETTER";
}

function createNewsBriefing(location, items, scope = "regional") {
    const stories = items
      .filter((item) => item?.title)
      .map((item) => ({ title: item.title.trim(), description: String(item.description || "").trim() }));
    if (!stories.length) {
      return `Für ${location.label} liegen im Moment keine bestätigten Meldungen vor.`;
    }
    const scopeText = scope === "local" ? "direkt aus der Region" : "aus dem regionalen Nachrichtenumfeld";
    const lead = stories[0];
    const leadDetails = lead.description ? ` Wichtig ist dabei: ${lead.description}` : "";
    if (stories.length === 1) {
      return `Für ${location.label} gibt es aktuell eine bestätigte Meldung ${scopeText}. Das Wichtigste zuerst: ${lead.title}.${leadDetails}`;
    }
    const remaining = stories.slice(1).map((story) => story.description
      ? `${story.title}. Dazu: ${story.description}`
      : story.title);
    const additional = remaining.length === 1
      ? remaining[0]
      : `${remaining.slice(0, -1).join(", ")} sowie ${remaining.at(-1)}`;
    return `Für ${location.label} gibt es aktuell mehrere bestätigte Entwicklungen ${scopeText}. Das Wichtigste zuerst: ${lead.title}.${leadDetails} Außerdem wird ausführlicher berichtet: ${additional}. Das ist der derzeitige verifizierte Nachrichtenstand; bei neuen Meldungen wird die Übersicht aktualisiert.`;
}

function selectGermanVoice() {
    const voices = window.speechSynthesis?.getVoices?.() || [];
    const preferredNames = /stefan|conrad|killian|thorsten|google deutsch|microsoft.*(natural|online)|natural|premium|enhanced/i;
    return voices.find((voice) => /^de(-|_)/i.test(voice.lang) && preferredNames.test(voice.name))
      || voices.find((voice) => /^de(-|_)/i.test(voice.lang))
      || null;
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

async function speakGerman(text) {
    try {
      const response = await fetch("/.netlify/functions/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      if (response.ok && response.headers.get("content-type")?.includes("audio/")) {
        const audio = new Audio(URL.createObjectURL(await response.blob()));
        audio.onended = () => URL.revokeObjectURL(audio.src);
        await audio.play();
        return;
      }
    } catch {
      // Browser speech remains the safe fallback when ElevenLabs is unavailable.
    }
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const voice = selectGermanVoice();
    const chunks = String(text).match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g) || [String(text)];
    chunks.map((chunk) => chunk.trim()).filter(Boolean).forEach((chunk) => {
      const utterance = new SpeechSynthesisUtterance(chunk);
      utterance.lang = "de-DE";
      utterance.rate = .92;
      utterance.pitch = 1;
      utterance.volume = 1;
      if (voice) utterance.voice = voice;
      window.speechSynthesis.speak(utterance);
    });
}

if ("speechSynthesis" in window) {
  window.speechSynthesis.addEventListener("voiceschanged", () => selectGermanVoice());
}

function updateRegionFacts(location, data) {
  if (!location) return;
  if (sceneRegionMeta && data?.scope) {
    sceneRegionMeta.textContent = `${location.precision === "city" ? "STADT-FIXIERUNG" : "REGIONS-FIXIERUNG"} · ${data.scope === "local" ? "LOKALER" : "REGIONALER"} FEED`;
  }
  if (sceneRegionCoordinates) sceneRegionCoordinates.textContent =
    `${location.lat.toFixed(2)}° ${location.lat >= 0 ? "N" : "S"} · ${Math.abs(location.lon).toFixed(2)}° ${location.lon >= 0 ? "E" : "W"}`;
  const current = data?.weather;
  if (sceneRegionWeather) sceneRegionWeather.textContent = current
    ? `${weatherLabel(Number(current.weather_code))} · ${Math.round(Number(current.temperature_2m))}°C`
  : "WETTER NICHT VERFÜGBAR";
  if (sceneRegionTime) {
    const time = data?.timezone ? new Intl.DateTimeFormat("de-DE", {
      timeZone: data.timezone, hour: "2-digit", minute: "2-digit"
    }).format(new Date()) : "--:--";
    sceneRegionTime.textContent = `ORTSZEIT ${time}`;
  }
  if (sceneRegionNews && data?.newsAvailable) {
    sceneRegionNews.replaceChildren();
    data.news.forEach((story) => {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = story.title;
      item.appendChild(title);
      if (story.description) {
        const detail = document.createElement("span");
        detail.textContent = story.description;
        item.appendChild(detail);
      }
      sceneRegionNews.appendChild(item);
    });
  }
}

async function loadRegionData(location) {
  if (!location) return null;
  const response = await fetch(
    `/.netlify/functions/region?label=${encodeURIComponent(location.label)}&query=${encodeURIComponent(location.label.toLowerCase())}&lat=${location.lat}&lon=${location.lon}`
  );
  if (!response.ok) throw new Error("Region data unavailable.");
  return response.json();
}

async function startThreeScene(mode, message = "") {
  if (!sceneVisual) return;
  threeFrameToken += 1;
  const frameToken = threeFrameToken;
  if (threeScene) {
    threeScene.renderer.dispose();
    threeScene = null;
  }
  if (!threeReady) {
    threeReady = import("https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js");
  }
  try {
    const THREE = await threeReady;
    const old = sceneVisual.querySelector(".scene-3d-canvas");
    if (old) old.remove();
    sceneVisual.querySelectorAll(".scene-location-label").forEach((node) => node.remove());
    const canvas = document.createElement("canvas");
    canvas.className = "scene-3d-canvas";
    canvas.setAttribute("aria-label", `${mode} 3D visualization`);
    sceneVisual.appendChild(canvas);
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(sceneVisual.clientWidth, sceneVisual.clientHeight, false);
    const camera = new THREE.PerspectiveCamera(42, sceneVisual.clientWidth / sceneVisual.clientHeight, .1, 100);
    const location = mode === "world"
      ? (inferLocation(message) || await geocodeLocation(message))
      : null;
    camera.position.z = location ? 4.9 : 4.1;
    if (location) {
      if (sceneWorkspace) sceneWorkspace.dataset.location = location.label;
      if (sceneTitle) sceneTitle.textContent = `${location.label} / INTELLIGENCE`;
      if (sceneSubtitle) sceneSubtitle.textContent =
        `Orbital scan wird auf ${location.label} fokussiert. Lokale und globale Signale werden abgeglichen.`;
      if (sceneRegionCoordinates) sceneRegionCoordinates.textContent =
        `${location.lat.toFixed(2)}° ${location.lat >= 0 ? "N" : "S"} · ${Math.abs(location.lon).toFixed(2)}° ${location.lon >= 0 ? "E" : "W"}`;
      if (mode === "world") createWorldMap(location);
      if (sceneRegionImage) {
        sceneRegionImage.src = regionImages[location.label] || "https://images.unsplash.com/photo-1470214304380-aadaedcfff1b?auto=format&fit=crop&w=900&q=80";
        sceneRegionImage.alt = `${location.label} city view`;
      }
    }
    const scene = new THREE.Scene();
    const group = new THREE.Group();
    scene.add(group);
    const earthGroup = new THREE.Group();
    group.add(earthGroup);
    const colors = { world: 0x4bd9e8, markets: 0xff9252, code: 0x62d39a, system: 0x9a8cff, assistant: 0xffb46b };
    const color = colors[mode] || colors.assistant;
    const accent = mode === "markets" ? 0xffd27d : mode === "code" ? 0xb2ffd9 : 0xa7f7ff;
    const core = new THREE.Mesh(
      new THREE.SphereGeometry(mode === "world" ? 1.3 : 1.08, 64, 64),
      new THREE.MeshPhongMaterial({
        color: mode === "world" ? 0x102a43 : color,
        emissive: mode === "world" ? 0x09233e : color,
        emissiveIntensity: mode === "world" ? .55 : .28,
        transparent: true,
        opacity: .94
      })
    );
    if (mode === "world") {
      const loader = new THREE.TextureLoader();
      const textureUrl = "https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg";
      const normalUrl = "https://threejs.org/examples/textures/planets/earth_normal_2048.jpg";
      const specularUrl = "https://threejs.org/examples/textures/planets/earth_specular_2048.jpg";
      const earthMaterial = new THREE.MeshPhongMaterial({
        color: 0x8edfff,
        emissive: 0x061526,
        emissiveIntensity: .36,
        shininess: 18,
        specular: 0x4d9bb8
      });
      const earth = new THREE.Mesh(new THREE.SphereGeometry(1.28, 96, 96), earthMaterial);
      earthGroup.add(earth);
      loader.load(textureUrl, (texture) => {
        if (frameToken !== threeFrameToken) return;
        earthMaterial.map = texture;
        earthMaterial.color.set(0xffffff);
        earthMaterial.needsUpdate = true;
      });
      loader.load(normalUrl, (texture) => {
        if (frameToken !== threeFrameToken) return;
        earthMaterial.normalMap = texture;
        earthMaterial.normalScale.set(.35, .35);
        earthMaterial.needsUpdate = true;
      });
      loader.load(specularUrl, (texture) => {
        if (frameToken !== threeFrameToken) return;
        earthMaterial.specularMap = texture;
        earthMaterial.needsUpdate = true;
      });
      const nightMaterial = new THREE.MeshBasicMaterial({
        color: 0xffb56b,
        transparent: true,
        opacity: .55,
        blending: THREE.AdditiveBlending
      });
      const nightLayer = new THREE.Mesh(new THREE.SphereGeometry(1.286, 96, 96), nightMaterial);
      earthGroup.add(nightLayer);
      loader.load("https://threejs.org/examples/textures/planets/earth_lights_2048.png", (texture) => {
        if (frameToken !== threeFrameToken) return;
        nightMaterial.map = texture;
        nightMaterial.needsUpdate = true;
      });
      const cloudMaterial = new THREE.MeshPhongMaterial({
        color: 0xd9f7ff,
        transparent: true,
        opacity: .16,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      });
      const clouds = new THREE.Mesh(new THREE.SphereGeometry(1.315, 96, 96), cloudMaterial);
      earthGroup.add(clouds);
      loader.load("https://threejs.org/examples/textures/planets/earth_clouds_1024.png", (texture) => {
        if (frameToken !== threeFrameToken) return;
        cloudMaterial.map = texture;
        cloudMaterial.needsUpdate = true;
      });
      group.userData.earth = earth;
      group.userData.clouds = clouds;
    } else {
      group.add(core);
    }
    if (mode === "world") {
      const globeLines = new THREE.Group();
      const globeMaterial = new THREE.LineBasicMaterial({ color: 0x3b9db9, transparent: true, opacity: .34 });
      for (let latitude = -60; latitude <= 60; latitude += 20) {
        const points = [];
        for (let longitude = -180; longitude <= 180; longitude += 6) {
          points.push(locationPoint(THREE, latitude, longitude, 1.315));
        }
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        globeLines.add(new THREE.Line(geometry, globeMaterial));
      }
      for (let longitude = -180; longitude < 180; longitude += 20) {
        const points = [];
        for (let latitude = -90; latitude <= 90; latitude += 6) {
          points.push(locationPoint(THREE, latitude, longitude, 1.315));
        }
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        globeLines.add(new THREE.Line(geometry, globeMaterial));
      }
      earthGroup.add(globeLines);
      if (location) {
        const pinPosition = locationPoint(THREE, location.lat, location.lon, 1.42);
        const pin = new THREE.Mesh(
          new THREE.SphereGeometry(.065, 20, 20),
          new THREE.MeshBasicMaterial({ color: 0xff775f })
        );
        pin.position.copy(pinPosition);
        earthGroup.add(pin);
        const pinRing = new THREE.Mesh(
          new THREE.TorusGeometry(.14, .012, 8, 48),
          new THREE.MeshBasicMaterial({ color: 0xff775f, transparent: true, opacity: .9 })
        );
        pinRing.position.copy(pinPosition);
        pinRing.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), pinPosition.clone().normalize());
        earthGroup.add(pinRing);
        group.userData.locationPin = pin;
        group.userData.locationRing = pinRing;
        const label = document.createElement("span");
        label.className = "scene-location-label";
        label.textContent = location.label;
        sceneVisual.appendChild(label);
      }
    }
    const wire = new THREE.Mesh(
      new THREE.SphereGeometry(mode === "world" ? 1.33 : 1.1, 28, 18),
      new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: .22 })
    );
    wire.rotation.set(.4, .2, 0);
    if (mode !== "world") group.add(wire);
    const atmosphere = new THREE.Mesh(
      new THREE.SphereGeometry(mode === "world" ? 1.42 : 1.18, 48, 48),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .13, side: THREE.BackSide })
    );
    if (mode !== "world") group.add(atmosphere);
    if (mode === "world") {
      const atmosphereMaterial = new THREE.MeshBasicMaterial({
        color: 0x2db7ff,
        transparent: true,
        opacity: .16,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending
      });
      earthGroup.add(new THREE.Mesh(new THREE.SphereGeometry(1.42, 64, 64), atmosphereMaterial));
    }
    const orbitalRingCount = mode === "world" ? 1 : 3;
    for (let index = 0; index < orbitalRingCount; index += 1) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(1.5 + index * .18, .008, 8, 160),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: mode === "world" ? .2 : .5 - index * .1 })
      );
      ring.rotation.set(index * .65, index * .82, index * .3);
      group.add(ring);
    }
    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(1.36, .018, 8, 180),
      new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: mode === "world" ? .25 : .7 })
    );
    halo.rotation.set(Math.PI / 2.3, .25, 0);
    group.add(halo);
    const signalGeometry = new THREE.BufferGeometry();
    const signalPositions = [];
    for (let index = 0; index < 180; index += 1) {
      const angle = (index / 180) * Math.PI * 2;
      const radius = 1.55 + Math.sin(index * 2.7) * .08;
      signalPositions.push(Math.cos(angle) * radius, (Math.random() - .5) * .18, Math.sin(angle) * radius);
    }
    signalGeometry.setAttribute("position", new THREE.Float32BufferAttribute(signalPositions, 3));
    group.add(new THREE.Points(signalGeometry, new THREE.PointsMaterial({
      color: accent, size: .035, transparent: true, opacity: .9
    })));
    const points = new THREE.BufferGeometry();
    const pointPositions = [];
    for (let index = 0; index < 420; index += 1) {
      pointPositions.push((Math.random() - .5) * 12, (Math.random() - .5) * 7, (Math.random() - .5) * 5);
    }
    points.setAttribute("position", new THREE.Float32BufferAttribute(pointPositions, 3));
    scene.add(new THREE.Points(points, new THREE.PointsMaterial({ color, size: .018, transparent: true, opacity: .72 })));
    scene.add(new THREE.DirectionalLight(0xffffff, 2.2));
    scene.add(new THREE.AmbientLight(color, 1.2));
    const resize = () => {
      if (!sceneVisual.isConnected) return;
      const width = sceneVisual.clientWidth;
      const height = sceneVisual.clientHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    const animate = () => {
      if (
        frameToken !== threeFrameToken ||
        !sceneVisual.isConnected ||
        !sceneWorkspace?.classList.contains("open")
      ) {
        renderer.dispose();
        return;
      }
      if (mode === "world" && location) {
        const target = locationPoint(THREE, location.lat, location.lon, 1).normalize();
        const desired = new THREE.Quaternion().setFromUnitVectors(
          target,
          new THREE.Vector3(0, 0, 1)
        );
        // A stronger initial slerp makes the city lock visibly converge instead
        // of leaving the requested location off-center during the transition.
        group.quaternion.slerp(desired, .075);
      } else {
        group.rotation.y += mode === "markets" ? .006 : mode === "world" ? .0012 : .0025;
      }
      if (!(mode === "world" && location)) {
        group.rotation.x = Math.sin(Date.now() * .00035) * .08;
      }
      wire.rotation.y -= .004;
      wire.rotation.z += .0015;
      halo.rotation.z += mode === "code" ? .008 : .003;
      halo.scale.setScalar(1 + Math.sin(Date.now() * .0012) * .025);
      core.scale.setScalar(1 + Math.sin(Date.now() * .0015) * .018);
      if (location) {
        const closeZoom = location.precision === "city" ? 2.05 : 2.28;
        camera.position.z += ((closeZoom + Math.sin(Date.now() * .0008) * .018) - camera.position.z) * .024;
        group.userData.locationPin?.scale.setScalar(1 + Math.sin(Date.now() * .004) * .25);
        group.userData.locationRing?.scale.setScalar(1 + Math.sin(Date.now() * .0025) * .22);
      }
      if (mode === "world") {
        earthGroup.rotation.y += location ? .00008 : .00028;
        if (group.userData.clouds) group.userData.clouds.rotation.y += .00042;
      }
      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    };
    window.addEventListener("resize", resize, { once: true });
    threeScene = { renderer, scene, group };
    animate();
  } catch {
    threeReady = null;
  }
}

function inferWorkspace(message) {
  const value = message.toLowerCase();
  if (/(welt|news|politik|krieg|nachrichten|globale|weltlage|land|stadt|region)/.test(value)
    || /(was passiert|aktuell in|informationen über|informationen ueber|neueste meldungen)/.test(value)
    || Object.keys(cityCoordinates).some((city) => value.includes(city))
    || Object.keys(countryCoordinates).some((country) => value.includes(country))) return "world";
  if (/(markt|krypto|bitcoin|forex|xauusd|gold|trading)/.test(value)) return "markets";
  if (/(code|projekt|python|fehler|debug|build|deploy)/.test(value)) return "code";
  if (/(status|system|laptop|pc|desktop|app|datei)/.test(value)) return "system";
  return "assistant";
}

function openTaskWindow(message) {
  const mode = inferWorkspace(message);
  sceneAutoOpen = mode === "world";
  sceneWorkspace?.classList.remove("scene-mode-world", "scene-mode-markets", "scene-mode-code", "scene-mode-system", "scene-mode-assistant", "scene-switching");
  sceneWorkspace?.classList.add(`scene-mode-${mode}`);
  if (sceneWorkspace) sceneWorkspace.dataset.mode = mode;
  if (!sceneAutoOpen) {
    sceneWorkspace?.classList.remove("open", "scene-entered", "scene-switching");
    sceneWorkspace?.setAttribute("aria-hidden", "true");
    rememberCommand(message, mode);
    renderTimeline(message, "active");
    return mode;
  }
  const views = {
    world: ["WELT-INTELLIGENZ", "Was geht in der Welt ab?", "Aktuelle Daten werden geprüft und kompakt zusammengefasst."],
    markets: ["MARKT-INTELLIGENZ", "Märkte im Fokus", "Nur bestätigte Marktdaten werden angezeigt; fehlende Daten bleiben leer."],
    code: ["PROJEKTARBEITSBEREICH", "Projektanalyse", "Dateien, Änderungen und Checks werden strukturiert."],
    system: ["DESKTOP-STEUERUNG", "Systemübersicht", "Lokale Statusdaten werden sicher aus der Bridge geladen."],
    assistant: ["JARVIS-ARBEITSBEREICH", "Dein Auftrag", "Jarvis passt die Ansicht an deine Anfrage an."]
  };
  const view = views[mode] || views.assistant;
  sceneWorkspace?.classList.add("open");
  rememberCommand(message, mode);
  renderTimeline(message, "active");
  sceneWorkspace?.classList.remove("scene-entered");
  requestAnimationFrame(() => sceneWorkspace?.classList.add("scene-entered"));
  startThreeScene(mode, message);
  sceneWorkspace?.setAttribute("aria-hidden", "false");
  if (sceneMode) sceneMode.textContent = view[0];
  if (sceneKicker) sceneKicker.textContent = view[0];
  const location = mode === "world" ? inferLocation(message) : null;
  if (sceneTitle) sceneTitle.textContent = location ? `${location.label} / INTELLIGENCE` : view[1];
  if (sceneSubtitle) sceneSubtitle.textContent = location
    ? `Der Ortsscan wird auf ${location.label} fokussiert. Lokale und globale Signale werden abgeglichen.`
    : view[2];
  if (sceneStatus) sceneStatus.textContent = "ANALYSIERT";
  if (sceneProgress) sceneProgress.style.width = "12%";
  if (sceneResponse) sceneResponse.textContent = "Auftrag empfangen. Verifizierte Daten und Kontext werden geladen ...";
  if (sceneProvider) sceneProvider.textContent = "";
  if (sceneSignals) sceneSignals.replaceChildren();
  if (sceneRegionTitle) sceneRegionTitle.textContent = location ? `${location.label} / LIVE-NEWS` : "REGIONALE INTELLIGENZ";
  if (sceneRegionMeta) sceneRegionMeta.textContent = location
    ? `${location.precision === "city" ? "STADT-FIXIERUNG" : "REGIONS-FIXIERUNG"} · RSS-STREAM`
    : "GLOBALER RSS-STREAM";
  if (sceneRegionNews && !(mode === "world" && sceneRegionNews.querySelector("strong"))) {
    sceneRegionNews.replaceChildren();
    const item = document.createElement("li");
    item.textContent = "Regionale Meldungen werden synchronisiert ...";
    sceneRegionNews.appendChild(item);
  }
  addActivity(`SZENE · ${mode.toUpperCase()}`);
  return mode;
}

function updateTaskWindow(payload) {
  pendingTaskPayload = payload;
  if (sceneWorkspace && sceneAutoOpen) {
    sceneWorkspace.classList.remove("scene-switching");
    void sceneWorkspace.offsetWidth;
    sceneWorkspace.classList.add("scene-switching");
    window.setTimeout(() => sceneWorkspace.classList.remove("scene-switching"), 420);
    sceneWorkspace.classList.add("open");
    if (sceneVisual) {
      sceneVisual.querySelectorAll(".scene-layer").forEach((node) => node.remove());
      const mode = sceneWorkspace.dataset.mode || "assistant";
      const layer = document.createElement("div");
      layer.className = `scene-layer scene-layer-${mode}`;
      layer.innerHTML = mode === "world"
        ? '<div class="scene-orbital-grid" aria-hidden="true"></div><span class="scene-signal signal-one"></span><span class="scene-signal signal-two"></span><span class="scene-signal signal-three"></span>'
        : mode === "markets"
          ? '<span class="scene-market-line"></span><span class="scene-market-line line-two"></span><span class="scene-market-ticks"></span>'
          : mode === "code"
            ? '<span class="scene-code-rain">010101<br>101100<br>011010</span><b class="scene-code-bracket">{ }</b>'
            : mode === "system"
              ? '<span class="scene-system-pulse"></span><span class="scene-system-pulse pulse-two"></span>'
              : '<span class="scene-assistant-wave"></span>';
      sceneVisual.appendChild(layer);
    }
    sceneStatus && (sceneStatus.textContent = payload.state === "thinking" ? "DATEN WERDEN GELADEN" : payload.state === "error" ? "FEHLER" : "ANTWORT BEREIT");
    sceneProgress && (sceneProgress.style.width = payload.state === "thinking" ? "54%" : "100%");
    if (sceneResponse) {
      sceneResponse.replaceChildren();
      const message = payload.message || "Keine Antwort erhalten.";
      message.split(/\n+/).filter(Boolean).forEach((line, index) => {
        const row = document.createElement("div");
        row.className = line.startsWith("- ") ? "scene-response-item" : "scene-response-line";
        row.style.setProperty("--response-index", index);
        row.textContent = line;
        sceneResponse.appendChild(row);
      });
    }
    if (payload.state !== "thinking") {
      const originalCommand = messageInput?.value || "";
      renderTimeline(originalCommand, payload.state === "error" ? "active" : "done");
    }
    sceneProvider && (sceneProvider.textContent = payload.provider ? `· ${String(payload.provider).toUpperCase()}` : "");
    if (sceneSignals) {
      sceneSignals.replaceChildren();
      const items = payload.state === "thinking"
        ? ["Anfrage erkannt", "Daten- und Kontextprüfung aktiv", "Keine unbestätigten Daten werden ausgegeben"]
        : ["Antwort synchronisiert", payload.state === "error" ? "Fehler transparent gemeldet" : "Datenstatus in Antwort berücksichtigt"];
      items.forEach((text) => {
        const item = document.createElement("li");
        item.textContent = text;
        sceneSignals.appendChild(item);
      });
    }
    if (sceneRegionNews) {
      sceneRegionNews.replaceChildren();
      const lines = String(payload.message || "")
        .split(/\n+/)
        .map((line) => line.replace(/^[-•]\s*/, "").trim())
        .filter((line) => line.length > 8)
        .slice(0, 5);
      (lines.length ? lines : ["Noch keine bestätigten regionalen Meldungen verfügbar."]).forEach((text) => {
        const item = document.createElement("li");
        item.textContent = text;
        sceneRegionNews.appendChild(item);
      });
    }
  }
  if (!taskWindow || taskWindow.closed) return;
  taskWindow.postMessage({ type: "jarvis-result", ...payload }, window.location.origin);
}

document.querySelector("#scene-close")?.addEventListener("click", () => {
  threeFrameToken += 1;
  if (threeScene) {
    threeScene.renderer.dispose();
    threeScene = null;
  }
  sceneWorkspace?.classList.add("scene-closing");
  window.setTimeout(() => sceneWorkspace?.classList.remove("open", "scene-closing", "scene-entered"), 360);
  sceneWorkspace?.setAttribute("aria-hidden", "true");
  sceneAutoOpen = false;
});

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin || event.data?.type !== "workspace-ready") return;
  if (event.source === taskWindow && pendingTaskPayload) {
    taskWindow.postMessage({ type: "jarvis-result", ...pendingTaskPayload }, window.location.origin);
  }
});
document.querySelectorAll("[data-scroll]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector(button.dataset.scroll)?.scrollIntoView({ behavior: "smooth" });
  });
});

function addActivity(message, tone = "normal") {
  if (!activityLog) return;
  const item = document.createElement("li");
  item.dataset.tone = tone;
  item.innerHTML = `<i></i><span></span><time>jetzt</time>`;
  item.querySelector("span").textContent = message;
  activityLog.prepend(item);
  while (activityLog.children.length > 6) activityLog.lastElementChild.remove();
}

restoreCommandHistory();

function setCapability(name) {
  capabilityNodes.forEach((node) => node.classList.toggle("active", node.dataset.capability === name));
}

async function checkLocalBridge() {
  if (!bridgeStatus) return;
  const started = performance.now();
  try {
    const response = await fetch("http://127.0.0.1:8765/api/status", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error("offline");
    bridgeStatus.textContent = "BRÜCKE ONLINE";
    bridgeStatus.style.color = "#65f6a5";
    telemetry.state && (telemetry.state.textContent = "LIVE");
    const elapsed = Math.round(performance.now() - started);
    if (telemetry.latencyValue) telemetry.latencyValue.textContent = `${elapsed} ms`;
    if (telemetry.latencyState) telemetry.latencyState.textContent = elapsed < 250 ? "OPTIMAL" : "SLOW";
    if (telemetry.processCount) telemetry.processCount.textContent = data.system?.processes ?? "--";
    if (telemetry.memoryValue) {
      const used = Number(data.system?.memoryUsedGb);
      const total = Number(data.system?.memoryTotalGb);
      telemetry.memoryValue.textContent = Number.isFinite(used) ? `${used.toFixed(1)} GB` : "--";
      if (Number.isFinite(used) && Number.isFinite(total) && total > 0 && telemetry.memoryMeter) {
        telemetry.memoryMeter.style.width = `${Math.min(100, Math.round((used / total) * 100))}%`;
      }
    }
    addActivity("LOKALE BRIDGE VERBUNDEN");
  } catch {
    bridgeStatus.textContent = "CLOUD-MODUS";
    bridgeStatus.style.color = "#fcd34d";
    telemetry.state && (telemetry.state.textContent = "CLOUD ONLY");
    telemetry.latencyValue && (telemetry.latencyValue.textContent = "--");
    telemetry.latencyState && (telemetry.latencyState.textContent = "OFFLINE");
    addActivity("LOKALE BRIDGE NICHT ERREICHBAR", "warning");
  }
}

clearActivity?.addEventListener("click", () => {
  activityLog.replaceChildren();
  addActivity("AKTIVITÄTSLOG ZURÜCKGESETZT");
});

quickCommands.forEach((button) => {
  button.addEventListener("click", () => {
    messageInput.value = button.dataset.command || "";
    messageInput.dispatchEvent(new Event("input"));
    messageInput.focus();
  });
});

const visualStates = {
  idle: "BEREIT",
  listening: "HÖRT ZU",
  thinking: "DENKT",
  researching: "RECHERCHIERT",
  speaking: "SPRICHT",
  success: "ERLEDIGT",
  confirmation: "BESTÄTIGUNG NÖTIG",
  error: "FEHLER"
};

function setVisualState(nextState) {
  const stateName = visualStates[nextState] ? nextState : "idle";
  Object.keys(visualStates).forEach((name) => networkStage?.classList.remove(`state-${name}`));
  networkStage?.classList.add(`state-${stateName}`);
  if (visualState) visualState.textContent = visualStates[stateName];
  if (agentStatus && stateName !== "idle") agentStatus.textContent = visualStates[stateName];
  const capability = {
    listening: "voice",
    researching: "web",
    thinking: "code",
    confirmation: "files",
    speaking: "voice",
    success: "automations"
  }[stateName];
  setCapability(capability || "");
  if (stateName !== "idle") addActivity(`STATUS · ${visualStates[stateName]}`);
}

function startNetworkMap() {
  if (!networkCanvas) return;
  const context = networkCanvas.getContext("2d");
  const stage = networkCanvas.parentElement;
  const nodes = Array.from({ length: 28 }, (_, index) => ({
    x: Math.random(),
    y: Math.random(),
    phase: index * 0.7,
    radius: 1.2 + Math.random() * 2.3
  }));
  const resize = () => {
    const scale = window.devicePixelRatio || 1;
    networkCanvas.width = stage.clientWidth * scale;
    networkCanvas.height = stage.clientHeight * scale;
    context.setTransform(scale, 0, 0, scale, 0, 0);
  };
  const draw = (time) => {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    context.clearRect(0, 0, width, height);
    const points = nodes.map((node) => ({
      x: node.x * width + Math.sin(time / (networkStage?.classList.contains("state-thinking") ? 650 : 1900) + node.phase) * 6,
      y: node.y * height + Math.cos(time / (networkStage?.classList.contains("state-listening") ? 700 : 1700) + node.phase) * 5,
      radius: node.radius
    }));
    points.forEach((point, index) => {
      points.slice(index + 1).forEach((other) => {
        const distance = Math.hypot(point.x - other.x, point.y - other.y);
        if (distance > 82) return;
        context.strokeStyle = `rgba(255, 151, 78, ${0.24 * (1 - distance / 82)})`;
        context.lineWidth = 0.7;
        context.beginPath();
        context.moveTo(point.x, point.y);
        context.lineTo(other.x, other.y);
        context.stroke();
      });
      context.fillStyle = "#ffad67";
      context.shadowBlur = 10;
      context.shadowColor = "#ff7331";
      context.beginPath();
      context.arc(point.x, point.y, point.radius, 0, Math.PI * 2);
      context.fill();
      context.shadowBlur = 0;
    });
    requestAnimationFrame(draw);
  };
  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(draw);
}

startNetworkMap();
updateHudClock();
window.setInterval(updateHudClock, 1000);
setVisualState("idle");
checkLocalBridge();
window.setInterval(checkLocalBridge, 15000);

const checks = [
  ["geminiConfigured", "Gemini Flash"],
  ["ollamaConfigured", "Ollama-Fallback"],
  ["makeConfigured", "Make.com-Webhooks"],
  ["monitoringConfigured", "Marktdaten/Monitoring"],
  ["runnerConfigured", "Privater Code-Runner"],
  ["storageConfigured", "Persistenter Speicher"],
  ["accessControlConfigured", "Zugriffsschutz"]
];

function renderSystemCheck(data) {
  checkList.replaceChildren();
  let ready = 0;
  for (const [key, label] of checks) {
    const item = document.createElement("li");
    const available = data[key] === true;
    if (available) ready += 1;
    item.className = available ? "check-ready" : "check-missing";
    item.textContent = `${available ? "OK" : "OFFEN"} · ${label}`;
    checkList.appendChild(item);
  }
  checkSummary.textContent = `${ready}/${checks.length} Bereiche bereit. Fehlende optionale Dienste brauchen eigene Konten, Keys oder einen privaten Runner.`;
}

async function runSystemCheck() {
  checkButton.disabled = true;
  setVisualState("researching");
  checkSummary.textContent = "System wird geprüft ...";
  addActivity("SYSTEMCHECK GESTARTET");
  try {
    const response = await fetch("/.netlify/functions/health", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Systemcheck fehlgeschlagen.");
    renderSystemCheck(data);
    addActivity("SYSTEMCHECK ABGESCHLOSSEN");
    setVisualState("success");
    window.setTimeout(() => setVisualState("idle"), 1800);
  } catch (error) {
    checkSummary.textContent = `Systemcheck nicht erreichbar: ${error.message}`;
    checkList.replaceChildren();
    setVisualState("error");
  } finally {
    checkButton.disabled = false;
  }
}

checkButton.addEventListener("click", runSystemCheck);
runSystemCheck();

function renderList(element, values) {
  element.replaceChildren();
  for (const value of Array.isArray(values) ? values : []) {
    const item = document.createElement("li");
    item.textContent = value;
    element.appendChild(item);
  }
}

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SpeechRecognition ? new SpeechRecognition() : null;
if (recognition) {
  recognition.lang = "de-DE";
  recognition.interimResults = false;
  recognition.onstart = () => {
    setVisualState("listening");
    if (voiceStatus) voiceStatus.textContent = "HÖRT ZU";
    voiceButton.disabled = true;
  };
  recognition.onend = () => {
    if (voiceStatus?.textContent === "HÖRT ZU") {
      setVisualState("idle");
      voiceStatus.textContent = "";
    }
    voiceButton.disabled = false;
  };
  recognition.onerror = (event) => {
    const messages = {
      "not-allowed": "Mikrofon blockiert. Erlaube den Mikrofonzugriff für diese Website.",
      "service-not-allowed": "Spracherkennung wird von diesem Browser nicht erlaubt.",
      "audio-capture": "Kein Mikrofon gefunden oder das Mikrofon wird bereits verwendet.",
      "no-speech": "Keine Sprache erkannt. Sprich nach dem Klick deutlich.",
      "network": "Spracherkennung ist momentan nicht erreichbar."
    };
    const message = messages[event.error] || `Mikrofonfehler: ${event.error || "unbekannt"}.`;
    setVisualState("error");
    state.textContent = message;
    reply.className = "error";
    reply.textContent = message;
    if (voiceStatus) voiceStatus.textContent = "FEHLER";
    addActivity(`MIKRO · ${message}`);
    voiceButton.disabled = false;
  };
  recognition.onresult = (event) => {
    messageInput.value = event.results[0][0].transcript;
    messageInput.dispatchEvent(new Event("input"));
    messageInput.focus();
  };
} else {
  document.querySelector("#voice-button")?.setAttribute("title", "Spracherkennung ist in diesem Browser nicht verfügbar.");
  voiceButton.disabled = true;
}

voiceButton.addEventListener("click", async () => {
  voiceButton.disabled = true;
  if (voiceStatus) voiceStatus.textContent = "MIKROFON WIRD AKTIVIERT";
  try {
    const localResponse = await fetchWithTimeout("http://127.0.0.1:8765/api/listen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timeout: 5, phrase_time_limit: 12 })
    }, 12000);
    const localData = await localResponse.json();
    if (localResponse.ok && localData.text) {
      messageInput.value = localData.text;
      messageInput.dispatchEvent(new Event("input"));
      messageInput.focus();
      setVisualState("idle");
      if (voiceStatus) voiceStatus.textContent = "TEXT ERKANNT";
      voiceButton.disabled = false;
      return;
    }
    if (localResponse.status !== 404 && localResponse.status !== 405
      && localResponse.status !== 408 && localResponse.status !== 503) {
      throw new Error(localData.error || "Lokale Spracherkennung fehlgeschlagen.");
    }
  } catch (error) {
    if (error.name !== "AbortError" && !String(error.message).includes("Failed to fetch")) {
      setVisualState("error");
      state.textContent = error.message;
      reply.className = "error";
      reply.textContent = error.message;
      if (voiceStatus) voiceStatus.textContent = "FEHLER";
      addActivity(`MIKRO · ${error.message}`);
      voiceButton.disabled = false;
      return;
    }
  }
  voiceButton.disabled = false;
  if (!recognition) {
    const message = "Lokale Spracherkennung ist nicht erreichbar und dieser Browser unterstützt keine Spracherkennung.";
    setVisualState("error");
    state.textContent = message;
    reply.className = "error";
    reply.textContent = message;
    if (voiceStatus) voiceStatus.textContent = "FEHLER";
    addActivity(`MIKRO · ${message}`);
    return;
  }
  try {
    if (navigator.mediaDevices?.getUserMedia) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
    }
    voiceStatus && (voiceStatus.textContent = "HÖRT ZU");
    recognition.start();
  } catch (error) {
    const message = error.name === "NotAllowedError"
      ? "Mikrofon blockiert. Erlaube den Mikrofonzugriff für diese Website."
      : "Mikrofon konnte nicht gestartet werden.";
    setVisualState("error");
    state.textContent = message;
    reply.className = "error";
    reply.textContent = message;
    if (voiceStatus) voiceStatus.textContent = "FEHLER";
    addActivity(`MIKRO · ${message}`);
  }
});

messageInput.addEventListener("input", () => {
  counter.textContent = `${messageInput.value.length} / 12000`;
});

messageInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;

  const workspaceMode = openTaskWindow(message);
  askButton.disabled = true;
  addActivity(`ANFRAGE · ${message.slice(0, 52)}`);
  setVisualState(taskInput.value === "monitoring" ? "researching" : "thinking");
  if (agentStatus) agentStatus.textContent = "ARBEITET";
  orb?.classList.add("thinking");
  state.textContent = "DENKT ...";
  reply.className = "";
  reply.textContent = `Auftrag empfangen.\n\nJarvis arbeitet jetzt daran:\n• Anfrage verstehen\n• relevante Informationen sammeln\n• vollständige Antwort und nächste Aktionen vorbereiten`;
  addActivity("AUFTRAG SOFORT ANGEZEIGT");
  updateTaskWindow({
    mode: workspaceMode,
    state: "thinking",
    message: `Auftrag empfangen.\n\nJarvis analysiert jetzt:\n• ${message.slice(0, 180)}\n• relevante Daten und Projektkontext\n• vollständige Antwort für alle Ansichten`
  });
  const progressSteps = [
    "KONTEXT WIRD GELADEN",
    "RELEVANTE DATEN WERDEN GESAMMELT",
    "ANTWORT WIRD VORBEREITET"
  ];
  let progressIndex = 0;
  const progressTimer = window.setInterval(() => {
    if (progressIndex >= progressSteps.length) return;
    state.textContent = progressSteps[progressIndex];
    addActivity(progressSteps[progressIndex]);
    progressIndex += 1;
  }, 650);

  try {
    const requestBody = JSON.stringify({
      message,
      provider: providerInput.value,
      task: taskInput.value,
      mode: modeInput.value
    });
    let data;
    let localResponse;
    if (/wie spät|wie spaet|uhrzeit|welcher tag|welches datum/.test(message.toLowerCase())) {
      const now = new Date();
      data = {
        reply: `Es ist ${new Intl.DateTimeFormat("de-DE", {
          dateStyle: "full",
          timeStyle: "short"
        }).format(now)}.`,
        confirmationRequired: false,
        provider: "browser-local",
        model: "Intl.DateTimeFormat"
      };
      state.textContent = "LOKALE ANTWORT ERHALTEN";
    }
    if (workspaceMode !== "world") {
      if (!data) try {
          localResponse = await fetchWithTimeout("http://127.0.0.1:8765/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: message })
          }, 8000);
          const localData = await localResponse.json();
          if (localResponse.ok && localData.result) {
            data = {
              reply: localData.result,
              confirmationRequired: Boolean(localData.confirmationRequired),
              plan: localData.plan || null,
              provider: localData.provider ? `${localData.provider}-local` : "local",
              model: localData.model || "",
              conversationState: localData.conversation_state || null
            };
            if (agentStatus) agentStatus.textContent = "LOKALER FALLBACK";
            state.textContent = "LOKALE ANTWORT ERHALTEN";
          }
      } catch {
        localResponse = null;
      }
    }
    if (!data && workspaceMode === "world") {
      data = {
        reply: "Regionale Nachrichten werden geladen.",
        confirmationRequired: false,
        provider: "regional-feed",
        model: ""
      };
    }
    if (!data) {
      const response = await fetchWithTimeout("/.netlify/functions/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: requestBody
      }, 30000);
      data = await response.json();
      if (!response.ok) throw new Error(data.error || "Agent nicht erreichbar.");
    }
    if (workspaceMode === "world") {
      try {
        const location = inferLocation(message) || await geocodeLocation(message);
        const locationQuery = location?.label || "";
        const newsResponse = await fetch(
          `/.netlify/functions/news?query=${encodeURIComponent(locationQuery.toLowerCase())}`
        );
        const newsData = await newsResponse.json();
        if (newsResponse.ok && newsData.ok) {
          data.reply = createNewsBriefing(location || { label: "die Welt" }, newsData.items);
          data.provider = "netlify-news";
          data.confirmationRequired = false;
        }
        if (location) {
          try {
            const regionData = await loadRegionData(location);
            updateRegionFacts(location, regionData);
            if (regionData.newsAvailable) {
              data.reply = createNewsBriefing(location, regionData.news, regionData.scope);
              data.provider = "regional-feed";
            }
          } catch {
            updateRegionFacts(location, null);
          }
        }
      } catch {
        // The provider response remains available when the optional feed proxy is offline.
      }
    }
    reply.textContent = data.reply;
    if (data.conversationState) {
      window.localStorage.setItem("jarvis-conversation-state", JSON.stringify(data.conversationState));
    }
    updateTaskWindow({
      mode: workspaceMode,
      state: data.confirmationRequired ? "confirmation" : "success",
      message: data.reply,
      provider: data.provider || "jarvis",
      model: data.model || ""
    });
    addActivity(`ANTWORT VON ${data.provider || "JARVIS"}`);
    actionSummary.hidden = !data.confirmationRequired;
    setVisualState(data.confirmationRequired ? "confirmation" : "speaking");
    const plan = data.plan || {};
    Object.entries(planLists).forEach(([key, element]) => renderList(element, plan[key]));
    planDetails.hidden = !data.plan;
    if (speakToggle.checked && "speechSynthesis" in window) {
      speakGerman(data.reply);
    }
    if (agentStatus) agentStatus.textContent = "BEREIT";
    state.textContent = "ANTWORT ERHALTEN";
    if (!data.confirmationRequired) window.setTimeout(() => setVisualState("success"), 500);
  } catch (error) {
    reply.className = "error";
    reply.textContent = `Fehler: ${error.message}`;
    updateTaskWindow({
      mode: workspaceMode,
      state: "error",
      message: error.message
    });
    state.textContent = "FEHLER";
    if (agentStatus) agentStatus.textContent = "FEHLER";
    setVisualState("error");
  } finally {
    window.clearInterval(progressTimer);
    askButton.disabled = false;
    orb?.classList.remove("thinking");
  }
});

import("https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js").then((THREE) => {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 10);
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(112, 112);
  orb.replaceChildren(renderer.domElement);
  const globe = new THREE.Mesh(
    new THREE.SphereGeometry(1, 20, 20),
    new THREE.MeshBasicMaterial({ color: 0x67e8f9, wireframe: true })
  );
  scene.add(globe);
  camera.position.z = 2.8;
  const animate = () => {
    globe.rotation.y += 0.008;
    globe.rotation.x += 0.003;
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  };
  animate();
}).catch((error) => {
  console.info("Three.js enhancement unavailable; using CSS orb.", error);
});
