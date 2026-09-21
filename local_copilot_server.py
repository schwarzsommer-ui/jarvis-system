"""Local browser bridge for the free Ollama-powered J.A.R.V.I.S. brain."""

import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil
import speech_recognition as sr

from core.brain import JarvisBrain
from core.project_runner import ProjectRunner
from core.monitoring import LocalMonitoring


brain = JarvisBrain()
runner = ProjectRunner()
monitoring = LocalMonitoring()
speech_recognizer = sr.Recognizer()
MAKE_FALLBACK_URL = os.getenv("MAKE_FALLBACK_URL", "").strip()
pending_project_command = None


def project_request_kind(prompt):
    lower = prompt.lower()
    if any(marker in lower for marker in (
        "öffne", "oeffne", "open", "starte", "start",
        "schreibe", "schreib", "tippe", "klick", "click",
        "screenshot", "bildschirm", "browser", "notepad",
        "desktop", "fenster", "app",
    )):
        return None
    if not any(marker in lower for marker in (
        "projekt", "codebase", "repository", "repo", "build", "test",
        "fehler", "debug", "syntax", "check", "prüfe", "pruefe",
    )):
        return None
    if any(marker in lower for marker in ("build", "baue", "kompiliere")):
        return "npm_build"
    if any(marker in lower for marker in ("pytest", "tests", "tests", "teste")):
        return "python_tests"
    return "python_syntax"


def project_confirmation(prompt):
    return prompt.lower().strip() in {
        "ja", "j", "okay", "ok", "bestätige", "bestaetige",
        "bestätigen", "bestaetigen", "mach", "ausführen", "ausfuehren",
    }


def add_verified_context(prompt):
    lower = prompt.lower()
    if not any(marker in lower for marker in ("welt", "news", "nachrichten", "politik", "weltlage")):
        return prompt
    news = monitoring.news()
    entries = []
    for source in news.get("sources", []):
        for item in source.get("items", [])[:2]:
            if item.get("title"):
                entries.append(
                    f"[{source.get('source')}] {item['title']} | "
                    f"{item.get('published') or 'Zeitpunkt unbekannt'} | {item.get('link')}"
                )
    if not entries:
        return (
            prompt
            + "\n\nVERIFIZIERTER DATENSTATUS: Der Live-Newsabruf ist fehlgeschlagen. "
            "Gib keine aktuellen Ereignisse als Fakten aus."
        )
    return (
        prompt
        + "\n\nVERIFIZIERTE LIVE-NEWS (Abrufzeitpunkt "
        + news.get("fetchedAt", "unbekannt")
        + " UTC). Nutze ausschließlich diese Meldungen für aktuelle Aussagen. "
        "Trenne Nachricht, Einordnung und Unsicherheit. Quellen dienen nur der internen Verifikation:\n"
        + "\n".join(f"- {entry}" for entry in entries)
    )


def verified_news_response(news):
    lines = [
        "LIVE-WELTBRIEFING",
        "",
        "Bestätigte Meldungen:",
    ]
    count = 0
    for source in news.get("sources", []):
        for item in source.get("items", [])[:5]:
            title = item.get("title", "").strip()
            if not title:
                continue
            published = item.get("published") or "Zeitpunkt nicht angegeben"
            lines.append(f"- {title} · {published}")
            count += 1
            if count >= 5:
                break
        if count >= 5:
            break
    if not count:
        return (
            "Keine aktuellen, verifizierten Weltmeldungen verfügbar. "
            "Der Live-Newsabruf lieferte keine verwertbaren Einträge."
        )
    lines.extend(["", "Nur bestätigte Meldungen; keine zusätzliche Einordnung erfunden."])
    return "\n".join(lines)


def verified_market_response(snapshot):
    lines = [
        "LIVE-MARKTSTATUS",
        "",
    ]
    for asset in snapshot.get("assets", []):
        if asset.get("ok"):
            lines.append(
                f"- {asset['symbol']}: {asset.get('price')} "
                f"({asset.get('change24h')}% / 24h)"
            )
        else:
            lines.append(f"- {asset['symbol']}: Live-Daten nicht erreichbar")
    lines.append("- XAUUSD und Forex: keine Live-Daten verbunden.")
    lines.append("Dies ist ein Datenstatus, keine Anlageberatung.")
    return "\n".join(lines)


def verified_system_response():
    memory = psutil.virtual_memory()
    return "\n".join([
        "SYSTEMSTATUS",
        f"- CPU: {psutil.cpu_percent(interval=0.15):.0f}%",
        f"- RAM: {memory.percent:.0f}% ({memory.used / (1024 ** 3):.1f} / {memory.total / (1024 ** 3):.1f} GB)",
        f"- Prozesse: {len(psutil.pids())}",
        "- Lokale Bridge: online",
        "- Projekt-Runner: aktiv und workspace-begrenzt",
    ])


def make_fallback(prompt):
    if not MAKE_FALLBACK_URL:
        return (
            "Make.com ist nicht konfiguriert. Der lokale Ollama-Agent bleibt aktiv; "
            "hinterlege MAKE_FALLBACK_URL oder MAKE_WEBHOOK_URL erst nach eigener Bestätigung."
        )
    payload = json.dumps({"command": prompt, "source": "local-copilot"}).encode("utf-8")
    request = urllib.request.Request(
        MAKE_FALLBACK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("result", data)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return f"Make-Fallback nicht erreichbar: {exc}"


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._json(204, {})

    def do_POST(self):
        global pending_project_command
        if self.path not in ("/api/ask", "/api/runner/read", "/api/runner/plan-write",
                             "/api/runner/write", "/api/runner/run",
                             "/api/runner/repair-plan", "/api/runner/repair-apply",
                             "/api/listen"):
            self._json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                self._json(400, {"error": "request_body_must_be_object"})
                return
            if self.path == "/api/listen":
                try:
                    with sr.Microphone() as source:
                        speech_recognizer.adjust_for_ambient_noise(source, duration=0.35)
                        audio = speech_recognizer.listen(
                            source,
                            timeout=float(payload.get("timeout", 5)),
                            phrase_time_limit=float(payload.get("phrase_time_limit", 12)),
                        )
                except sr.WaitTimeoutError:
                    self._json(408, {"error": "Keine Spracheingabe innerhalb des Zeitlimits."})
                    return
                except (OSError, AttributeError, RuntimeError) as exc:
                    self._json(503, {"error": f"Mikrofon ist lokal nicht verfügbar: {exc}"})
                    return
                try:
                    text = speech_recognizer.recognize_google(audio, language="de-DE")
                except sr.UnknownValueError:
                    self._json(422, {"error": "Keine verständliche Sprache erkannt."})
                    return
                except sr.RequestError as exc:
                    self._json(503, {"error": f"Kostenloser Spracherkennungsdienst nicht erreichbar: {exc}"})
                    return
                self._json(200, {"ok": True, "text": text})
                return
            if self.path == "/api/runner/read":
                self._json(200, {"ok": True, "result": runner.read_file(payload.get("path"))})
                return
            if self.path == "/api/runner/plan-write":
                self._json(200, {"ok": True, "result": runner.plan_write(
                    payload.get("path"), payload.get("content", "")
                )})
                return
            if self.path == "/api/runner/write":
                self._json(200, {"ok": True, "result": runner.execute_write(
                    payload.get("path"), payload.get("content", ""),
                    confirmed=bool(payload.get("confirmed")),
                    expected_old_sha256=payload.get("expected_old_sha256"),
                )})
                return
            if self.path == "/api/runner/repair-plan":
                self._json(200, {"ok": True, "result": runner.plan_repair(
                    payload.get("path"),
                    payload.get("content", ""),
                    payload.get("reason", ""),
                )})
                return
            if self.path == "/api/runner/repair-apply":
                result = runner.execute_repair(
                    payload.get("path"),
                    payload.get("content", ""),
                    confirmed=bool(payload.get("confirmed")),
                    expected_old_sha256=payload.get("expected_old_sha256"),
                    reason=payload.get("reason", ""),
                )
                self._json(200, {"ok": bool(result.get("ok")), "result": result})
                return
            if self.path == "/api/runner/run":
                self._json(200, {"ok": True, "result": runner.run_command(
                    payload.get("command"), confirmed=bool(payload.get("confirmed")),
                    timeout=payload.get("timeout", 120),
                )})
                return
            prompt = str(payload.get("command", "")).strip()
            if not prompt:
                self._json(400, {"error": "command_required"})
                return
            if pending_project_command and project_confirmation(prompt):
                command_name = pending_project_command
                pending_project_command = None
                result = runner.run_command(command_name, confirmed=True)
                brain.conversation_state["pending_action"] = None
                brain.conversation_state["last_tool_result"] = result
                ok = bool(result.get("ok"))
                answer = (
                    f"Projektcheck {command_name} abgeschlossen.\n"
                    f"Status: {'ERFOLGREICH' if ok else 'FEHLER'}\n"
                    f"Ausgabe:\n{result.get('output') or '(keine Ausgabe)'}"
                )
                self._json(200, {
                    "ok": True,
                    "source": "project-runner",
                    "result": answer,
                    "confirmationRequired": False,
                    "provider": "local-runner",
                    "model": "",
                    "conversation_state": brain.conversation_state,
                })
                return
            if pending_project_command and prompt.lower().strip() in {
                "nein", "n", "abbrechen", "stopp", "stop",
            }:
                pending_project_command = None
                brain.conversation_state["pending_action"] = None
                self._json(200, {
                    "ok": True,
                    "source": "project-runner",
                    "result": "Projektcheck abgebrochen.",
                    "confirmationRequired": False,
                    "conversation_state": brain.conversation_state,
                })
                return
            project_command = project_request_kind(prompt)
            if project_command:
                if project_command in {"python_syntax", "python_tests"}:
                    result = runner.run_command(project_command, confirmed=True)
                    label = "Python-Syntaxprüfung" if project_command == "python_syntax" else "Python-Tests"
                    answer = (
                        f"{label} automatisch ausgeführt.\n"
                        f"Status: {'ERFOLGREICH' if result.get('ok') else 'FEHLER'}\n"
                        f"Ausgabe:\n{result.get('output') or '(keine Ausgabe)'}"
                    )
                    brain.conversation_state["last_tool_result"] = result
                    self._json(200, {
                        "ok": True,
                        "source": "project-runner",
                        "result": answer,
                        "confirmationRequired": False,
                        "provider": "local-runner",
                        "model": "",
                        "conversation_state": brain.conversation_state,
                    })
                    return
                pending_project_command = project_command
                brain.conversation_state["pending_action"] = {
                    "type": "project_command",
                    "command": project_command,
                }
                command_labels = {
                    "python_syntax": "Python-Syntaxprüfung",
                    "python_tests": "Python-Tests",
                    "npm_build": "Frontend-Build",
                }
                label = command_labels[project_command]
                self._json(200, {
                    "ok": True,
                    "source": "project-runner",
                    "result": (
                        f"{label} ist vorbereitet. Ausgeführt wird nur der "
                        f"freigegebene Befehl '{project_command}' im Workspace "
                        f"{runner.workspace}. Antworte mit 'Ja' zum Starten "
                        "oder 'Nein' zum Abbrechen."
                    ),
                    "confirmationRequired": True,
                    "plan": {
                        "steps": [f"Freigegebenen Befehl prüfen: {project_command}",
                                  "Ausführung im Workspace starten",
                                  "Ergebnis und Fehlerausgabe anzeigen"],
                        "files": [],
                        "tests": [label],
                        "risks": ["Keine freie Shell; Workspace und Timeout sind begrenzt."],
                    },
                    "conversation_state": brain.conversation_state,
                })
                return
            if re.search(r"(?:;\s*|\bdann\b|\bdanach\b)", prompt, re.IGNORECASE):
                result = brain.process_request(add_verified_context(prompt))
                self._json(200, {
                    "ok": True,
                    "source": "local-sequence",
                    "result": result,
                    "provider": brain.provider,
                    "model": brain.model,
                    "conversation_state": brain.conversation_state,
                })
                return
            cloud_request = any(marker in prompt.lower() for marker in (
                "make.com", "make automation", "make szenario", "cloud",
                "tools auf make", "tools in make", "tool auf make",
                "tool in make", "make tools",
            ))
            if cloud_request:
                self._json(200, {"ok": True, "source": "make", "result": make_fallback(prompt)})
                return
            normalized_prompt = (
                prompt.lower()
                .replace("ä", "a")
                .replace("ö", "o")
                .replace("ü", "u")
                .replace("ß", "ss")
            )
            if (
                any(marker in normalized_prompt for marker in (
                    "offne", "oeffne", "offnen", "oeffnen", "starte", "starten",
                ))
                and any(marker in normalized_prompt for marker in (
                    "chart", "diagramm", "kurschart", "tradingview",
                ))
            ):
                result = brain.process_request(prompt)
                self._json(200, {
                    "ok": True,
                    "source": "intent-router",
                    "result": result,
                    "provider": brain.provider,
                    "model": brain.model,
                    "conversation_state": brain.conversation_state,
                })
                return
            if any(marker in prompt.lower() for marker in (
                "welt", "news", "nachrichten", "politik", "weltlage",
            )):
                self._json(200, {
                    "ok": True,
                    "source": "verified-rss",
                    "result": verified_news_response(monitoring.news()),
                })
                return
            if any(marker in prompt.lower() for marker in (
                "bitcoin", "krypto", "crypto", "forex", "xauusd",
                "gold", "markt", "aktie", "kurs", "preis",
            )):
                self._json(200, {
                    "ok": True,
                    "source": "verified-rss",
                    "result": verified_market_response(monitoring.markets()),
                })
                return
            if any(marker in prompt.lower() for marker in (
                "systemstatus", "system status", "status meines laptops",
                "status des laptops", "status meines pcs", "pc status",
            )):
                self._json(200, {
                    "ok": True,
                    "source": "verified-system",
                    "result": verified_system_response(),
                    "provider": "local-system",
                    "model": "",
                    "conversation_state": brain.conversation_state,
                })
                return
            result = brain.process_request(add_verified_context(prompt))
            lower = result.lower()
            unavailable = any(marker in lower for marker in (
                "nicht verfügbar", "nicht verfuegbar", "kann diese anfrage",
                "unbekanntes werkzeug", "nicht angeschlossen",
            ))
            if unavailable:
                result = make_fallback(prompt)
            self._json(200, {
                "ok": True,
                "result": result,
                "provider": brain.provider,
                "model": brain.model,
                "conversation_state": brain.conversation_state,
            })
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            self._json(400, {"error": f"invalid_json: {exc}"})
        except Exception as exc:
            # Never leave clients with a reset connection when an allowlisted
            # local action fails unexpectedly. Keep the detail server-side only.
            self._json(500, {"error": "local_action_failed", "detail": str(exc)})

    def do_GET(self):
        if self.path == "/api/monitoring/news":
            self._json(200, monitoring.news())
            return
        if self.path != "/api/status":
            self._json(404, {"error": "not_found"})
            return
        self._json(200, {
            "ok": True,
            "autonomyMode": "desktop_assistant",
            "autonomyPolicy": {
                "direct": [
                    "allowlisted_apps",
                    "safe_urls",
                    "keyboard_mouse",
                    "screenshots",
                    "workspace_reads",
                ],
                "confirmationRequired": [
                    "file_writes",
                    "project_commands",
                    "external_messages",
                    "destructive_actions",
                    "real_trades",
                ],
            },
            "provider": os.getenv("JARVIS_PROVIDER", "ollama"),
            "model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            "providers": {
                "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip()),
                "ollama": bool(brain.available_models),
                "nvidia_nim": bool(os.getenv("NIM_API_KEY", "").strip() and os.getenv("NIM_API_URL", "").strip()),
                "claude": bool(os.getenv("CLAUDE_API_KEY", "").strip()),
            },
            "skills": brain.plugins.list(),
            "audio": brain.audio_devices.status(),
            "runner": runner.status(),
            "monitoring": monitoring.status(),
            "system": {
                "processes": len(psutil.pids()),
                "memoryUsedGb": round(psutil.virtual_memory().used / (1024 ** 3), 1),
                "memoryTotalGb": round(psutil.virtual_memory().total / (1024 ** 3), 1),
            },
            "capabilities": [
                "chat", "voice", "screen_capture", "image_analysis", "memory",
                "open_allowlisted_apps", "open_safe_urls", "type_text",
                "keyboard_and_mouse",
                "create_folders", "move_paths", "confirmed_deletion",
                "window_positioning",
                "make_fallback", "allowlisted_skill_installation",
                "project_runner_preview", "project_runner_confirmed_writes",
                "allowlisted_project_checks",
            ],
        })

    def log_message(self, *_args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
