import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.164/build/three.module.js";

const container = document.getElementById("globe-container");
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, .1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(innerWidth, innerHeight);
container.appendChild(renderer.domElement);
const globe = new THREE.Mesh(new THREE.SphereGeometry(5, 28, 28), new THREE.MeshBasicMaterial({ color: 0x19cfe0, wireframe: true }));
scene.add(globe); camera.position.z = 10;
function animate(){ requestAnimationFrame(animate); globe.rotation.y += .0018; globe.rotation.x += .0007; renderer.render(scene,camera); } animate();
addEventListener("resize",()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)});

const messages=document.getElementById("messages"), input=document.getElementById("chat-input");
const commandStatus=document.getElementById("command-status");
const digestOutput=document.getElementById("digest-output");
const digestStatus=document.getElementById("digest-status");
const voiceButton=document.getElementById("voice-btn");
const apiBase="http://127.0.0.1:8787";
const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
let recognition=null;
if(Recognition){
  recognition=new Recognition();
  recognition.lang="de-DE";
  recognition.interimResults=false;
  recognition.onstart=()=>{voiceButton.classList.add("listening");setActivity("sprache");setCommandStatus("Höre zu …")};
  recognition.onend=()=>{voiceButton.classList.remove("listening");if(commandStatus.textContent==="Höre zu …")setCommandStatus("Bereit")};
  recognition.onresult=event=>{input.value=event.results[0][0].transcript;input.focus()};
}
function addMessage(role,text){const item=document.createElement("div");item.className=`message ${role==="SIR"?"user":"jarvis"}`;const name=document.createElement("b");name.textContent=role;const body=document.createElement("p");body.textContent=text;item.append(name,body);messages.appendChild(item);messages.scrollTop=messages.scrollHeight}
function setCommandStatus(text){commandStatus.textContent=text}
const activityTypes=[
  {mode:"voice",icon:"◉",title:"SPRACHMODUS",detail:"Jarvis verarbeitet Sprache"},
  {mode:"vision",icon:"◈",title:"VISION",detail:"Bildschirm oder Bild wird geprüft"},
  {mode:"action",icon:"⚡",title:"AKTION",detail:"Jarvis führt deinen Befehl aus"},
  {mode:"keyboard",icon:"⌨",title:"TASTATUR",detail:"Tastatursteuerung aktiv"},
  {mode:"mouse",icon:"⌁",title:"MAUSSTEUERUNG",detail:"Mausaktion wird ausgeführt"},
  {mode:"research",icon:"◎",title:"RECHERCHE",detail:"Quellen und Marktdaten werden geprüft"},
  {mode:"memory",icon:"▣",title:"GEDÄCHTNIS",detail:"Information wird gespeichert oder geladen"},
  {mode:"danger",icon:"⚠",title:"BESTÄTIGUNG",detail:"Sicherheitsfreigabe erforderlich"},
  {mode:"chat",icon:"◉",title:"DIALOG",detail:"Jarvis denkt über deine Anfrage nach"}
];
function detectActivity(prompt){
  const text=prompt.toLowerCase();
  if(text.includes("mikrofon")||text.includes("sprich")||text.includes("sprache"))return "voice";
  if(text.includes("bild")||text.includes("sehen")||text.includes("screenshot")||text.includes("bildschirm"))return "vision";
  if(text.includes("tippe")||text.includes("schreib")||text.includes("taste")||text.includes("enter")||text.includes("shortcut"))return "keyboard";
  if(text.includes("klick")||text.includes("maus"))return "mouse";
  if(text.includes("löschen")||text.includes("loschen")||text.includes("herunterfahren")||text.includes("bestellung")||text.includes("echte order")||text.includes("senden"))return "danger";
  if(text.includes("merke")||text.includes("gedächtnis")||text.includes("gedachtnis")||text.includes("erinner"))return "memory";
  if(text.includes("suche")||text.includes("recher")||text.includes("news")||text.includes("markt")||text.includes("preis"))return "research";
  if(text.includes("öff")||text.includes("starte")||text.includes("öffne"))return "action";
  if(text.includes("analys"))return "research";
  return "chat";
}
function setActivity(prompt,detail){
  const item=activityTypes.find(entry=>entry.mode===detectActivity(prompt))||activityTypes.at(-1);
  document.body.dataset.mode=item.mode;
  document.getElementById("action-icon").textContent=item.icon;
  document.getElementById("action-title").textContent=item.title;
  document.getElementById("action-detail").textContent=detail||item.detail;
  document.getElementById("action-hud").classList.add("active");
}
async function ask(prompt){addMessage("SIR",prompt);setActivity(prompt);setCommandStatus("Lokaler Copilot arbeitet …");try{let response;try{response=await fetch("http://127.0.0.1:8765/api/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({command:prompt})});}catch{response=null}if(response&&response.ok){const payload=await response.json();const result=payload.result||"Keine Antwort erhalten.";addMessage("JARVIS",result);if("speechSynthesis" in window)window.speechSynthesis.speak(new SpeechSynthesisUtterance(result));setCommandStatus("Lokaler Copilot bereit");document.getElementById("action-detail").textContent="Aktion abgeschlossen";return}setCommandStatus("Claude arbeitet …");response=await fetch("/api/agent",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:prompt})});const payload=await response.json();if(!response.ok)throw new Error(payload.error||"Agent konnte nicht verarbeitet werden.");const result=payload.reply||"Keine Antwort erhalten.";addMessage("JARVIS",result);if("speechSynthesis" in window)window.speechSynthesis.speak(new SpeechSynthesisUtterance(result));setCommandStatus("Claude bereit");document.getElementById("action-detail").textContent="Claude-Antwort erhalten"}catch(error){addMessage("JARVIS",`Technischer Fehler: ${error.message}`);setCommandStatus("Fehler");document.getElementById("action-detail").textContent="Aktion fehlgeschlagen"}finally{setTimeout(()=>{document.body.dataset.mode="idle";document.getElementById("action-hud").classList.remove("active")},2200)}}
async function loadDigest(){try{const response=await fetch("/.netlify/functions/digest");if(!response.ok)throw new Error("Digest konnte nicht geladen werden.");const payload=await response.json();if(payload.digest)renderDigest(payload.digest)}catch(error){digestStatus.textContent="LOKAL BEREIT";digestStatus.className="badge warning";document.getElementById("digest-timestamp").textContent="Netlify-Funktion wartet auf den Make-Webhooks."}}
async function loadSetup(){
  const target=document.getElementById("setup-list");
  if(!target)return;
  try{
    const response=await fetch(`${apiBase}/setup/integrations`);
    if(!response.ok)throw new Error("Setup-Status konnte nicht geladen werden.");
    const payload=await response.json();
    target.innerHTML="";
    payload.integrations.forEach(item=>{
      const row=document.createElement("div");
      row.className="analysis-row";
      const state=item.status==="ready"?"BEREIT":"ANMELDEN";
      const missing=item.missing_configuration.length?`<small>Fehlt lokal: ${item.missing_configuration.join(", ")}</small>`:"<small>Konfiguration vollständig</small>";
      row.innerHTML=`<b>${item.name}</b><span>${state}<br>${missing}</span>`;
      if(item.status!=="ready"){
        const button=document.createElement("button");
        button.className="text-btn";
        button.textContent="Login öffnen →";
        button.addEventListener("click",async()=>{
          button.disabled=true;
          try{
            const opened=await fetch(`${apiBase}/setup/integrations/${item.id}/open`,{method:"POST"});
            if(!opened.ok)throw new Error("Login-Seite konnte nicht geöffnet werden.");
            button.textContent="Geöffnet";
          }catch(error){button.textContent="Fehler";setCommandStatus(error.message)}
        });
        row.appendChild(button);
      }
      target.appendChild(row);
    });
  }catch(error){
    target.innerHTML=`<p class="muted">API nicht erreichbar. Starte zuerst start_v2.ps1.</p>`;
  }
}
function renderDigest(payload){digestOutput.textContent=payload.digest;document.getElementById("global-summary").textContent="Letzter FX- & Gold-Digest";document.getElementById("digest-timestamp").textContent=`Empfangen: ${new Date(payload.timestamp).toLocaleString("de-DE")}`;digestStatus.textContent="AKTUELL";digestStatus.className="badge"} 
document.querySelectorAll(".nav").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll(".nav").forEach(n=>n.classList.remove("active"));document.querySelectorAll(".view").forEach(v=>v.classList.remove("active"));button.classList.add("active");document.getElementById(button.dataset.target).classList.add("active")}));
document.querySelectorAll("[data-prompt]").forEach(button=>button.addEventListener("click",()=>ask(button.dataset.prompt)));
document.getElementById("chat-form").addEventListener("submit",event=>{event.preventDefault();const text=input.value.trim();if(text){input.value="";ask(text)}});
voiceButton.addEventListener("click",()=>{if(recognition)recognition.start();else setCommandStatus("Spracheingabe wird von diesem Browser nicht unterstützt")});
document.getElementById("refresh-btn").addEventListener("click",loadDigest);
document.getElementById("setup-refresh")?.addEventListener("click",loadSetup);
loadDigest();
loadSetup();
function tick(){document.getElementById("clock").textContent=new Date().toLocaleString("de-DE",{dateStyle:"medium",timeStyle:"medium"});} tick();setInterval(tick,1000);
