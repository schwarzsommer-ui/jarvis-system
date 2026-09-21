(() => {
  const feed = document.querySelector("#v2-live-feed");
  const status = document.querySelector("#v2-live-status");
  const apiBase = window.JARVIS_V2_API || "http://127.0.0.1:8787";

  if (!feed || !status) return;

  const addEvent = (label, detail, tone = "normal") => {
    const item = document.createElement("li");
    item.className = `v2-event v2-event-${tone}`;
    const time = new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    item.innerHTML = `<span>${time}</span><b>${label}</b><small></small>`;
    item.querySelector("small").textContent = detail;
    feed.prepend(item);
    while (feed.children.length > 8) feed.lastElementChild.remove();
  };

  const refreshStatus = async () => {
    try {
      const response = await fetch(`${apiBase}/status`, { signal: AbortSignal.timeout(2500) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      status.textContent = `${data.agents?.length || 0} Agenten · ${data.skills?.length || 0} Skills`;
      addEvent("V2-Kern", "Backend online · Safe Mode aktiv", "good");
    } catch (error) {
      status.textContent = "V2-Backend offline";
      addEvent("V2-Kern", "Starte optional .\\start_v2.ps1 für Live-Events", "warn");
    }
  };

  const connect = () => {
    try {
      const source = new EventSource(`${apiBase}/events`);
      source.onopen = () => {
        status.textContent = "Live-Stream verbunden";
        addEvent("Live-Stream", "Events werden empfangen", "good");
      };
      source.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          addEvent(payload.type || "Event", JSON.stringify(payload.payload || {}));
        } catch {
          addEvent("Live-Stream", "Nicht lesbares Event empfangen", "warn");
        }
      };
      source.onerror = () => {
        status.textContent = "Live-Stream wartet";
        source.close();
        window.setTimeout(connect, 5000);
      };
    } catch {
      status.textContent = "Live-Stream nicht verfügbar";
    }
  };

  refreshStatus();
  connect();
})();
