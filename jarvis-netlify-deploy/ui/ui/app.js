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
const orb = document.querySelector("#orb");
const planDetails = document.querySelector("#plan-details");
const planLists = {
  steps: document.querySelector("#steps"),
  files: document.querySelector("#files"),
  tests: document.querySelector("#tests"),
  risks: document.querySelector("#risks")
};

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
    voiceStatus.textContent = "HÖRT ZU";
    voiceButton.disabled = true;
  };
  recognition.onend = () => {
    voiceStatus.textContent = "BEREIT";
    voiceButton.disabled = false;
  };
  recognition.onerror = () => {
    voiceStatus.textContent = "FEHLER";
    voiceButton.disabled = false;
  };
  recognition.onresult = (event) => {
    messageInput.value = event.results[0][0].transcript;
    messageInput.dispatchEvent(new Event("input"));
    messageInput.focus();
  };
} else {
  voiceStatus.textContent = "NICHT VERFÜGBAR";
  voiceButton.disabled = true;
}

voiceButton.addEventListener("click", () => recognition?.start());

messageInput.addEventListener("input", () => {
  counter.textContent = `${messageInput.value.length} / 12000`;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;

  askButton.disabled = true;
  agentStatus.textContent = "ARBEITET";
  orb.classList.add("thinking");
  state.textContent = "DENKT ...";
  reply.className = "";
  reply.textContent = "Jarvis strukturiert deine Anfrage ...";

  try {
    const response = await fetch("/.netlify/functions/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, provider: providerInput.value, task: taskInput.value, mode: modeInput.value })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unbekannter Agent-Fehler.");
    reply.textContent = data.reply;
    actionSummary.hidden = !data.confirmationRequired;
    const plan = data.plan || {};
    Object.entries(planLists).forEach(([key, element]) => renderList(element, plan[key]));
    planDetails.hidden = !data.plan;
    if (speakToggle.checked && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(data.reply));
    }
    agentStatus.textContent = "BEREIT";
    state.textContent = "ANTWORT ERHALTEN";
  } catch (error) {
    reply.className = "error";
    reply.textContent = `Fehler: ${error.message}`;
    state.textContent = "FEHLER";
    agentStatus.textContent = "FEHLER";
  } finally {
    askButton.disabled = false;
    orb.classList.remove("thinking");
  }
});

import("https://cdn.jsdelivr.net/npm/three@0.164/build/three.module.js").then((THREE) => {
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
