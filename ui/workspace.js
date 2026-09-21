const params = new URLSearchParams(window.location.search);
const mode = params.get("mode") || "assistant";
const visual = document.querySelector("#visual");
const title = document.querySelector("#title");
const subtitle = document.querySelector("#subtitle");
const modeLabel = document.querySelector("#mode-label");
const liveState = document.querySelector("#live-state");
const response = document.querySelector("#response");
const provider = document.querySelector("#provider");
const signals = document.querySelector("#signals");

function buildScene(modeName) {
  const visualRoot = document.querySelector("#visual");
  if (!visualRoot) return;
  const extras = modeName === "world"
    ? '<div class="map-grid"></div><div class="location-pin pin-a"></div><div class="location-pin pin-b"></div>'
    : modeName === "markets"
      ? '<div class="market-line"></div><div class="market-line market-line-two"></div><div class="market-ticks"></div>'
      : modeName === "code"
        ? '<div class="code-rain">010101<br>101100<br>011010</div><div class="code-bracket">{ }</div>'
        : modeName === "system"
          ? '<div class="system-pulse"></div><div class="system-pulse pulse-two"></div>'
          : '<div class="assistant-wave"></div>';
  visualRoot.insertAdjacentHTML("beforeend", extras);
}

const views = {
  world: ["WORLD INTELLIGENCE", "Was geht in der Welt ab?", "Globale Nachrichten, Politik und aktuelle Entwicklungen werden zusammengeführt."],
  markets: ["MARKET INTELLIGENCE", "Märkte im Überblick", "Krypto, Forex, Gold und relevante Marktbewegungen werden analysiert."],
  code: ["PROJECT WORKSPACE", "Projekt- und Codeansicht", "Dateien, Fehler, Tests und nächste Umsetzungsschritte werden strukturiert."],
  system: ["DESKTOP CONTROL", "Dein System im Blick", "Jarvis prüft lokale Dienste, Apps, Runner und den aktuellen Rechnerstatus."],
  assistant: ["JARVIS WORKSPACE", "Was soll ich für dich erledigen?", "Die passende Arbeitsansicht wird für deinen Auftrag geladen."]
};

const view = views[mode] || views.assistant;
modeLabel.textContent = view[0];
title.textContent = view[1];
subtitle.textContent = view[2];
document.querySelector("#workspace").classList.add(`mode-${mode}`);
buildScene(mode);
window.opener?.postMessage({ type: "workspace-ready" }, window.location.origin);

window.addEventListener("message", (event) => {
  if (event.origin === window.location.origin && event.data?.type === "workspace-transition") {
    document.querySelector("#workspace").classList.add("scene-exit");
    window.setTimeout(() => {
      document.querySelector("#workspace").className = `workspace-shell mode-${event.data.mode || "assistant"} scene-enter`;
      window.location.href = `workspace.html?mode=${encodeURIComponent(event.data.mode || "assistant")}&scene=${Date.now()}`;
    }, 220);
    return;
  }
  if (event.origin !== window.location.origin || event.data?.type !== "jarvis-result") return;
  const data = event.data;
  liveState.textContent = data.state === "error" ? "ERROR" : data.state === "confirmation" ? "CONFIRMATION" : "LIVE";
  document.querySelector("#workspace").classList.remove("state-thinking", "state-success", "state-error");
  document.querySelector("#workspace").classList.add(`state-${data.state || "success"}`);
  response.textContent = data.message || "Keine Antwort erhalten.";
  response.scrollTop = response.scrollHeight;
  provider.textContent = data.provider ? `· ${String(data.provider).toUpperCase()}` : "";
  signals.replaceChildren();
  const signalItems = data.state === "thinking"
    ? ["Auftrag sofort erkannt", "Kontext und Datenquellen werden geladen", "Vollständige Antwort wird vorbereitet"]
    : ["Auftrag erkannt", "Relevante Ansicht aktiviert", data.state === "confirmation" ? "Bestätigung erforderlich" : "Vollständige Antwort synchronisiert"];
  signalItems.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    signals.appendChild(item);
  });
});
