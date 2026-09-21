/* =========================================================
   J.A.R.V.I.S CONTROL INTERFACE — dashboard.js  (V3 / HUD)
   SSE-Client + Panel-Rendering + HUD-Effekte

   Erwartetes Nachrichtenformat vom Server (JSON pro SSE-Event):

   { "type": "log",      "level": "info|warn|error|debug",
                          "message": "...", "timestamp": "..." }

   { "type": "queue",    "action": "add|update|remove",
                          "id": "req-1", "title": "...",
                          "status": "pending|running|done|error",
                          "meta": "..." }

   { "type": "memory",   "category": "commands|plans|requests|results|errors",
                          "id": "m-1", "content": {...} | "...",
                          "timestamp": "..." }

   { "type": "workflow", "action": "add|update|remove",
                          "id": "wf-1", "title": "...",
                          "status": "pending|running|done|error",
                          "meta": "..." }

   { "type": "safety",   "level": "warning|critical",
                          "message": "...", "timestamp": "..." }

   { "type": "agents",   "agents": [
                            { "name": "planner", "role": "planner",
                              "capabilities": ["plan","prioritize","summarize"],
                              "status": "online|busy|offline", "metadata": {} },
                            ...
                          ] }
     -- als Voll-Snapshot ("agents"-Array vorhanden) ODER inkrementell:
   { "type": "agents", "action": "add|update|remove", "id": "planner",
                        "name": "planner", "role": "planner",
                        "capabilities": [...], "status": "online", "metadata": {} }

   Ist das Backend-Format anders, muss nur handleMessage() bzw.
   updateAgent() unten angepasst werden — der Rest bleibt gleich.
   ========================================================= */

const API_URL = window.JARVIS_V2_API || "http://127.0.0.1:8787";
const EVENTS_URL = `${API_URL}/events`;
const MAX_LOG_LINES = 400;
const MAX_ENTRIES_PER_PANEL = 200;
const RECONNECT_DELAY_MS = 3000;
const GAUGE_CIRCUMFERENCE = 213.6; // 2 * PI * r(34)

let reconnectTimer = null;
let msgCount = 0;

const state = {
  queue: new Map(),      // id -> item
  workflows: new Map(),  // id -> item
  agents: new Map(),     // id -> agent
  memory: {
    commands: [],
    plans: [],
    requests: [],
    results: [],
    errors: []
  },
  safety: [],
  activeMemoryTab: "commands"
};

/* ---------------- DOM refs ---------------- */

const el = {
  connStatus: document.getElementById("conn-status"),
  clock: document.getElementById("clock"),
  msgCounter: document.getElementById("msg-counter"),
  reconnectInfo: document.getElementById("reconnect-info"),
  brandTitle: document.getElementById("brand-title"),

  queueList: document.getElementById("queue-list"),
  queueCount: document.getElementById("queue-count"),

  logList: document.getElementById("log-list"),
  autoscroll: document.getElementById("autoscroll-toggle"),
  btnClearLogs: document.getElementById("btn-clear-logs"),

  memoryTabs: document.getElementById("memory-tabs"),
  memoryBody: document.getElementById("memory-body"),

  workflowList: document.getElementById("workflow-list"),
  workflowCount: document.getElementById("workflow-count"),

  safetyList: document.getElementById("safety-list"),
  safetyCount: document.getElementById("safety-count"),

  agentsList: document.getElementById("agents-list"),
  agentsCount: document.getElementById("agents-count"),

  gaugeAgentsFill: document.getElementById("gauge-agents-fill"),
  gaugeAgentsVal: document.getElementById("gauge-agents-val"),
  gaugeQueueFill: document.getElementById("gauge-queue-fill"),
  gaugeQueueVal: document.getElementById("gauge-queue-val"),
  gaugeSafetyFill: document.getElementById("gauge-safety-fill"),
  gaugeSafetyVal: document.getElementById("gauge-safety-val")
};

/* ---------------- Clock ---------------- */

function tickClock() {
  const now = new Date();
  el.clock.textContent = now.toLocaleTimeString("de-DE", { hour12: false });
}
setInterval(tickClock, 1000);
tickClock();

/* ---------------- REST + SSE ---------------- */

async function hydrate() {
  try {
    const response = await fetch(`${API_URL}/status`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    handleAgents({ agents: data.agents || [] });
    state.queue.clear();
    (data.executor_queue || []).forEach((request) => updateQueue({
      id: request.id,
      title: request.type || request.id,
      status: request.status || "pending",
      meta: request.command || request.context?.reason || ""
    }));
    (data.workflows || []).forEach((workflow, index) => updateWorkflow({
      id: workflow.id || `workflow-${index}`,
      title: workflow.name || workflow.id || "Workflow",
      status: workflow.status || "planned",
      meta: workflow.description || ""
    }));
    updateVitals();
  } catch (error) {
    pushLog({ level: "warn", message: `Status konnte nicht geladen werden: ${error.message}`, timestamp: nowIso() });
  }
}

function connect() {
  clearTimeout(reconnectTimer);
  setConnectionState("connecting");

  const stream = new EventSource(EVENTS_URL);
  stream.onopen = () => {
    setConnectionState("online");
    el.reconnectInfo.textContent = "";
    pushLog({ level: "info", message: `Live-Stream verbunden: ${EVENTS_URL}`, timestamp: nowIso() });
  };
  stream.onmessage = (event) => {
    msgCount++;
    el.msgCounter.textContent = `${msgCount} Nachrichten empfangen`;
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      pushLog({ level: "warn", message: `Ungültige Nachricht empfangen: ${truncate(event.data, 120)}`, timestamp: nowIso() });
      return;
    }
    handleMessage(data);
  };
  stream.onerror = () => {
    setConnectionState("offline");
    stream.close();
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  let secondsLeft = Math.round(RECONNECT_DELAY_MS / 1000);
  el.reconnectInfo.textContent = `Reconnect in ${secondsLeft}s...`;
  const countdown = setInterval(() => {
    secondsLeft -= 1;
    if (secondsLeft > 0) {
      el.reconnectInfo.textContent = `Reconnect in ${secondsLeft}s...`;
    } else {
      clearInterval(countdown);
    }
  }, 1000);
  reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
}

function setConnectionState(stateName) {
  el.connStatus.classList.remove("status-online", "status-offline");
  if (stateName === "online") {
    el.connStatus.classList.add("status-online");
    el.connStatus.innerHTML = '<span class="pulse-dot"></span>ONLINE';
  } else if (stateName === "connecting") {
    el.connStatus.classList.add("status-offline");
    el.connStatus.innerHTML = '<span class="pulse-dot"></span>CONNECTING';
  } else {
    el.connStatus.classList.add("status-offline");
    el.connStatus.innerHTML = '<span class="pulse-dot"></span>OFFLINE';
  }
}

/* ---------------- Message Routing ---------------- */

function handleMessage(data) {
  if (!data || typeof data !== "object") return;
  const payload = data.payload || data;

  switch (data.type) {
    case "log":
      pushLog(data);
      break;
    case "queue":
      updateQueue(payload);
      break;
    case "memory":
      pushMemory(payload);
      break;
    case "workflow":
      updateWorkflow(payload);
      break;
    case "safety":
    case "safety.warning":
      pushSafety({ ...payload, timestamp: data.timestamp || payload.timestamp });
      break;
    case "agents":
      handleAgents(payload);
      break;
    case "executor.request":
      if (payload.request) {
        updateQueue({
          id: payload.request.id,
          title: payload.request.type,
          status: payload.request.status || "pending",
          meta: payload.request.context?.reason || ""
        });
      }
      break;
    case "task.enqueued":
      updateQueue({
        id: payload.task_id,
        title: payload.kind || payload.task_id,
        status: "queued",
        meta: payload.decision?.reason || ""
      });
      break;
    case "memory.updated":
      pushMemory({ category: "commands", id: payload.key, content: payload.value, timestamp: data.timestamp });
      break;
    default:
      // Unbekannter Typ: als Log-Zeile zur Sichtbarkeit anzeigen
      pushLog({ level: "debug", message: `Unbekannter Message-Typ: ${JSON.stringify(data).slice(0, 160)}`, timestamp: nowIso() });
  }
}

/* ---------------- Executor Queue ---------------- */

function updateQueue(data) {
  const { action = "update", id } = data;
  if (!id) return;

  if (action === "remove") {
    state.queue.delete(id);
  } else {
    state.queue.set(id, {
      id,
      title: data.title || data.id,
      status: data.status || "pending",
      meta: data.meta || ""
    });
  }
  renderQueue();
  updateVitals();
}

function renderQueue() {
  el.queueCount.textContent = state.queue.size;
  if (state.queue.size === 0) {
    el.queueList.innerHTML = '<div class="empty-hint">Keine aktiven Requests</div>';
    return;
  }
  const items = Array.from(state.queue.values()).reverse();
  el.queueList.innerHTML = items.map(item => `
    <div class="queue-item">
      <div class="title">${escapeHtml(item.title)}</div>
      <div class="row">
        <span>${escapeHtml(item.meta || item.id)}</span>
        <span class="status-pill ${escapeAttr(item.status)}">${escapeHtml(item.status)}</span>
      </div>
    </div>
  `).join("");
}

/* ---------------- Logs ---------------- */

function pushLog(data) {
  const line = document.createElement("div");
  line.className = "log-line";
  const level = (data.level || "info").toLowerCase();
  line.innerHTML = `
    <span class="log-time">${formatTime(data.timestamp)}</span>
    <span class="log-level ${escapeAttr(level)}">${level.toUpperCase()}</span>
    <span class="log-msg">${escapeHtml(data.message ?? "")}</span>
  `;

  if (el.logList.querySelector(".empty-hint")) {
    el.logList.innerHTML = "";
  }
  el.logList.appendChild(line);

  while (el.logList.children.length > MAX_LOG_LINES) {
    el.logList.removeChild(el.logList.firstChild);
  }

  if (el.autoscroll.checked) {
    el.logList.scrollTop = el.logList.scrollHeight;
  }
}

el.btnClearLogs.addEventListener("click", () => {
  el.logList.innerHTML = '<div class="empty-hint">Warte auf Log-Stream...</div>';
});

/* ---------------- Memory Viewer ---------------- */

function pushMemory(data) {
  const category = state.memory.hasOwnProperty(data.category) ? data.category : "commands";
  state.memory[category].push({
    id: data.id,
    content: data.content,
    timestamp: data.timestamp || nowIso()
  });
  if (state.memory[category].length > MAX_ENTRIES_PER_PANEL) {
    state.memory[category].shift();
  }
  if (category === state.activeMemoryTab) {
    renderMemory();
  }
}

function renderMemory() {
  const entries = state.memory[state.activeMemoryTab] || [];
  if (entries.length === 0) {
    el.memoryBody.innerHTML = '<div class="empty-hint">Keine Daten</div>';
    return;
  }
  const items = entries.slice().reverse();
  el.memoryBody.innerHTML = items.map(entry => `
    <div class="memory-entry">
      <div class="meta">
        <span>${escapeHtml(entry.id || "—")}</span>
        <span>${formatTime(entry.timestamp)}</span>
      </div>
      <pre>${escapeHtml(formatContent(entry.content))}</pre>
    </div>
  `).join("");
}

function formatContent(content) {
  if (content === undefined || content === null) return "";
  if (typeof content === "string") return content;
  try {
    return JSON.stringify(content, null, 2);
  } catch (err) {
    return String(content);
  }
}

el.memoryTabs.addEventListener("click", (event) => {
  const btn = event.target.closest(".tab");
  if (!btn) return;
  el.memoryTabs.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  state.activeMemoryTab = btn.dataset.tab;
  renderMemory();
});

/* ---------------- Workflows ---------------- */

function updateWorkflow(data) {
  const { action = "update", id } = data;
  if (!id) return;

  if (action === "remove") {
    state.workflows.delete(id);
  } else {
    state.workflows.set(id, {
      id,
      title: data.title || data.id,
      status: data.status || "pending",
      meta: data.meta || ""
    });
  }
  renderWorkflows();
}

function renderWorkflows() {
  el.workflowCount.textContent = state.workflows.size;
  if (state.workflows.size === 0) {
    el.workflowList.innerHTML = '<div class="empty-hint">Keine aktiven Workflows</div>';
    return;
  }
  const items = Array.from(state.workflows.values()).reverse();
  el.workflowList.innerHTML = items.map(item => `
    <div class="workflow-item">
      <div class="title">${escapeHtml(item.title)}</div>
      <div class="row">
        <span>${escapeHtml(item.meta || item.id)}</span>
        <span class="status-pill ${escapeAttr(item.status)}">${escapeHtml(item.status)}</span>
      </div>
    </div>
  `).join("");
}

/* ---------------- Safety Warnings ---------------- */

function pushSafety(data) {
  state.safety.push({
    level: (data.level || "warning").toLowerCase(),
    message: data.message || "",
    timestamp: data.timestamp || nowIso()
  });
  if (state.safety.length > MAX_ENTRIES_PER_PANEL) {
    state.safety.shift();
  }
  renderSafety();
  updateVitals();
}

function renderSafety() {
  el.safetyCount.textContent = state.safety.length;
  if (state.safety.length === 0) {
    el.safetyList.innerHTML = '<div class="empty-hint">Keine Warnungen</div>';
    return;
  }
  const items = state.safety.slice().reverse();
  el.safetyList.innerHTML = items.map(item => `
    <div class="safety-item ${item.level === "critical" ? "critical" : ""}">
      <div class="row">
        <span>${item.level.toUpperCase()}</span>
        <span>${formatTime(item.timestamp)}</span>
      </div>
      <div class="msg">${escapeHtml(item.message)}</div>
    </div>
  `).join("");
}

/* ---------------- Agenten ---------------- */

function handleAgents(data) {
  if (Array.isArray(data.agents)) {
    state.agents.clear();
    data.agents.forEach(a => {
      const id = a.id || a.name;
      if (!id) return;
      state.agents.set(id, {
        id,
        name: a.name || id,
        role: a.role || "",
        capabilities: Array.isArray(a.capabilities) ? a.capabilities : [],
        status: a.status || "online",
        metadata: a.metadata || {}
      });
    });
  } else {
    updateAgent(data);
    return; // updateAgent rendert + aktualisiert Vitals bereits selbst
  }
  renderAgents();
  updateVitals();
}

function updateAgent(data) {
  const { action = "update" } = data;
  const id = data.id || data.name;
  if (!id) return;

  if (action === "remove") {
    state.agents.delete(id);
  } else {
    state.agents.set(id, {
      id,
      name: data.name || id,
      role: data.role || "",
      capabilities: Array.isArray(data.capabilities) ? data.capabilities : [],
      status: data.status || "online",
      metadata: data.metadata || {}
    });
  }
  renderAgents();
  updateVitals();
}

function renderAgents() {
  el.agentsCount.textContent = state.agents.size;
  if (state.agents.size === 0) {
    el.agentsList.innerHTML = '<div class="empty-hint">Keine Agenten registriert</div>';
    return;
  }
  const items = Array.from(state.agents.values());
  el.agentsList.innerHTML = items.map(agent => {
    const statusClass = agent.status === "offline" ? "offline"
      : (agent.status === "busy" || agent.status === "running") ? "busy" : "";
    const metaStr = formatContent(agent.metadata);
    const capsHtml = agent.capabilities.map(c => `<span class="cap-pill">${escapeHtml(c)}</span>`).join("");
    return `
      <div class="agent-card">
        <div class="agent-head">
          <span class="status-ring ${statusClass}"></span>
          <span class="agent-name">${escapeHtml(agent.name)}</span>
          ${agent.role ? `<span class="agent-role">${escapeHtml(agent.role)}</span>` : ""}
        </div>
        ${capsHtml ? `<div class="agent-caps">${capsHtml}</div>` : ""}
        ${metaStr && metaStr !== "{}" ? `<div class="agent-meta">${escapeHtml(metaStr)}</div>` : ""}
      </div>
    `;
  }).join("");
}

/* ---------------- HUD Vitals (Gauges) ---------------- */

function setGauge(circleEl, valEl, percent) {
  const pct = Math.max(0, Math.min(100, Math.round(percent)));
  const offset = GAUGE_CIRCUMFERENCE - (pct / 100) * GAUGE_CIRCUMFERENCE;
  circleEl.style.strokeDashoffset = offset;
  valEl.textContent = `${pct}%`;
}

function updateVitals() {
  const totalAgents = state.agents.size;
  const onlineAgents = Array.from(state.agents.values()).filter(a => a.status !== "offline").length;
  const agentsPct = totalAgents === 0 ? 100 : (onlineAgents / totalAgents) * 100;
  setGauge(el.gaugeAgentsFill, el.gaugeAgentsVal, agentsPct);

  const queuePct = Math.min(100, (state.queue.size / 8) * 100);
  setGauge(el.gaugeQueueFill, el.gaugeQueueVal, queuePct);

  const safetyPct = Math.max(0, 100 - state.safety.length * 10);
  setGauge(el.gaugeSafetyFill, el.gaugeSafetyVal, safetyPct);
}

/* ---------------- Glitch-Effekt (Branding) ---------------- */

function scheduleGlitch() {
  const delay = 4000 + Math.random() * 5000;
  setTimeout(() => {
    el.brandTitle.classList.add("glitch");
    setTimeout(() => el.brandTitle.classList.remove("glitch"), 350);
    scheduleGlitch();
  }, delay);
}

/* ---------------- Partikel-Hintergrund (Konstellation) ---------------- */

function initParticles() {
  const canvas = document.getElementById("particles");
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  let particles = [];
  let width = 0, height = 0;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }
  window.addEventListener("resize", resize);
  resize();

  const COUNT = Math.max(25, Math.min(70, Math.floor(window.innerWidth / 24)));
  for (let i = 0; i < COUNT; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3
    });
  }

  function step() {
    ctx.clearRect(0, 0, width, height);

    ctx.fillStyle = "rgba(53, 231, 255, 0.6)";
    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0 || p.x > width) p.vx *= -1;
      if (p.y < 0 || p.y > height) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 1.4, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.strokeStyle = "rgba(53, 231, 255, 0.14)";
    ctx.lineWidth = 1;
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.globalAlpha = 1 - dist / 120;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;
    requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ---------------- Helpers ---------------- */

function nowIso() {
  return new Date().toISOString();
}

function formatTime(ts) {
  if (!ts) return "--:--:--";
  const date = new Date(ts);
  if (isNaN(date.getTime())) return String(ts);
  return date.toLocaleTimeString("de-DE", { hour12: false });
}

function truncate(str, len) {
  const s = String(str);
  return s.length > len ? s.slice(0, len) + "…" : s;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(str) {
  return String(str).replace(/[^a-zA-Z0-9_-]/g, "");
}

/* ---------------- Init ---------------- */

initParticles();
scheduleGlitch();
updateVitals();
hydrate();
connect();
