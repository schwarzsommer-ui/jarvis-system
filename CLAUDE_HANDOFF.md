# J.A.R.V.I.S. – Übergabe an Claude

## Zweck

Dies ist die vollständige Übergabe des aktuellen J.A.R.V.I.S.-Projekts. Das Projekt ist ein lokaler Windows-Agent mit Desktop-GUI, Browser-Automation, Windows-UI-Automation, lokaler Bridge, Multi-Agent-Orchestrierung, Memory, Monitoring, OCR und optionalen KI-Providern.

Zusätzlich liegt das vollständige, secrets-freie Projekt als `JARVIS_COMPLETE_CODE.zip` bei. Bitte zuerst die ZIP-Datei bzw. den Projektordner analysieren, bevor Code geändert wird.

## Arbeitsmodus für Claude

- Arbeite direkt am vorhandenen Projekt statt eine neue Demo zu erzeugen.
- Lies zuerst die betroffenen Dateien und bewahre bestehende Strukturen.
- Mache präzise, kleine Änderungen und teste jede Änderung.
- Keine echten Secrets ausgeben, speichern oder committen.
- `.env` niemals lesen, kopieren oder in Antworten ausgeben. Nur `.env.example` dokumentieren.
- Keine freien Shell-Befehle aus Nutzereingaben ableiten.
- Externe Aktionen wie E-Mails, Nachrichten, Käufe, Trades, Kontoeinstellungen und irreversible Änderungen benötigen eine ausdrückliche Bestätigung unmittelbar vor der Ausführung.
- Niemals Erfolg behaupten, wenn ein Tool keine bestätigte erfolgreiche Rückgabe geliefert hat.
- Finanzinformationen nur als Analyse, Szenarien und Risiken formulieren, nicht als Anlageberatung.

## Wichtige Projektbereiche

- `core/brain.py` – Provider-Auswahl, Intent-Routing, Gesprächskontext und Antworten
- `core/agent_tools.py` – sichere lokale Tools, Browser, Desktop, Windows-UI, Task-Queues und Multi-Agent-Orchestrierung
- `core/skill_manager.py` – lokaler Skill-Katalog und optionale Pakete
- `core/memory.py` – persistente Benutzerfakten und Memory
- `core/screen_vision.py` – Screenshots und Bildvalidierung
- `core/project_runner.py` – workspace-begrenztes Lesen, Schreiben, Reparieren und freigegebene Checks
- `local_copilot_server.py` – lokale HTTP-Bridge auf `127.0.0.1:8765`
- `gui_jarvis.py` – lokale Windows-GUI
- `main.py` – Desktop-Einstiegspunkt
- `start_jarvis.ps1` – Windows-Start und CheckOnly
- `ui/` – statische Weboberfläche
- `netlify/functions/` – öffentliche, sicher begrenzte Netlify-Endpoints
- `config/` – Integrations- und Providerkonfiguration ohne Secrets
- `requirements.txt` – Python-Abhängigkeiten

## Bereits umgesetzt

### Lokale Automation

- Allowlist für Windows-Apps und sichere URLs
- Öffnen von Apps, Webseiten, Dateien und Ordnern
- Maus, Tastatur, Clipboard, Fensterfokus und Screenshots
- `pywinauto`-basierte sichtbare Windows-UI-Aktionen
- UI-Klicks über sichtbare Texte
- UI-Felder über sichtbare Controls oder robuste Fallbacks ausfüllen
- App-Flows für lokale Windows-Anwendungen
- Systemstatus über `psutil`
- OCR über Pillow/Tesseract

### Browser-Agent

- Playwright-Browser-Session mit Wiederverwendung des Browser-Kontexts
- Navigation, Suche, Suchergebnisse, sichtbare Textklicks
- Formularfelder ausfüllen
- Formulare absenden
- Text, Snapshots und Screenshots lesen
- Browser-Workflows mit Suche, Öffnen, Klick und Verifikation
- Timeout-Grenzen und reduzierte redundante Lade-/Titelabfragen

### Task- und Workflow-System

- strukturierte Task-Queues
- lokale Multi-Step-Workflows
- Browser + Desktop + Status + Screenshot in einer Sequenz
- Abbruch bei fehlgeschlagener Verifikation
- Ergebnisse mit `ok`, `verified`, `message`, `data` und Fehlercodes

### Multi-Agent-Orchestrierung

`MultiAgentOrchestrator` in `core/agent_tools.py` koordiniert lokale Rollen:

1. Planner – strukturiert die Schritte
2. Operator – ruft die freigegebenen Tools auf
3. Verifier – prüft jede Rückgabe

Die Rollen kommunizieren über serialisierbare `AgentMessage`-Einträge. Ein gemeinsamer Kontext enthält Anfrage, Schrittzahl, letztes Ergebnis und abgeschlossene Schritte. Verschachtelte Orchestrierung ist absichtlich blockiert.

Verfügbare Einstiegspunkte:

- `execute_multi_agent`
- `multi_agent_orchestrate`
- `execute_local_workflow`
- `execute_task_queue`
- `desktop_orchestrate`

### Performance-Optimierungen

- TradingView-Initialisierung wird verzögert, bis sie wirklich benötigt wird.
- Identische `system_status`-Abfragen werden innerhalb eines Orchestrierungslaufs wiederverwendet.
- Tool-Ergebnisse werden rekursiv JSON-serialisierbar normalisiert.
- Browser-Timeouts sind begrenzt.
- redundante Browser-Lade- und Titelabfragen wurden reduziert.
- Aktionen mit Nebenwirkungen bleiben seriell und verifiziert.

## Provider und lokale Dienste

- `JARVIS_PROVIDER=auto` bevorzugt Gemini, wenn `GEMINI_API_KEY` gesetzt ist, sonst Ollama.
- Ollama ist der lokale Fallback.
- Claude-Unterstützung/Provider-Konfiguration darf nur über lokale Umgebungsvariablen erfolgen.
- Für Claude Code lokal: `ANTHROPIC_API_KEY` ausschließlich lokal setzen; niemals in Projektdateien schreiben.
- Zugangsdaten gehören ausschließlich in `.env`, die nicht weitergegeben wird.

## Starten unter Windows

```powershell
.\start_jarvis.ps1 -CheckOnly
.\start_jarvis.ps1
```

Alternativ:

```powershell
python -B .\main.py
```

Die lokale Bridge wird über `local_copilot_server.py` auf `127.0.0.1:8765` gestartet. Die Weboberfläche ist ein separates Netlify-Projekt; öffentliche Endpoints dürfen keine lokale Desktop-Steuerung ohne lokale Bridge und Bestätigung anbieten.

## Bisherige Validierung

- `python -m py_compile core\agent_tools.py core\brain.py local_copilot_server.py`
- `python -m compileall -q core`
- echter Playwright-Suchlauf
- echter Notepad-UI-Flow mit sichtbarem Texteingeben und Menü-Klick
- Systemstatus- und Screenshot-Workflow
- Multi-Agent-Test mit Planner-/Operator-/Verifier-Nachrichten
- JSON-Serialisierung der Orchestrierungsergebnisse

## Bekannte Grenzen

- Websites und Apps mit Login, Anti-Bot-Schutz, dynamischen Controls oder fehlenden Berechtigungen benötigen eigene, app-spezifische Flows.
- Nicht jede bereits geöffnete Browser-Registerkarte ist für die lokale Playwright-Session verfügbar. Eine explizit gestartete lokale Browser-Session ist zuverlässiger.
- `pywinauto`-Controls können je nach Windows-Version, Sprache und App-Version unterschiedliche Titel haben.
- Ein universeller Agent für jede beliebige Anwendung ohne app-spezifische Adapter ist technisch nicht garantiert.

## Empfohlene nächste Arbeiten

1. App-Adapter für Outlook, Teams, Explorer und VS Code mit stabilen UI-Targets ergänzen.
2. Browser-Form-Workflows mit expliziten Seitenprofilen und Verifikation nach Navigation, Eingabe und Submit erweitern.
3. Orchestrierung um parallele Planung unabhängiger, rein lesender Schritte erweitern; Aktionen mit Nebenwirkungen seriell lassen.
4. Retry-Strategien nur für idempotente, sichere Leseaktionen hinzufügen.
5. Tests für Browser-Session-Wiederverwendung, UI-Fallbacks, Fehlerabbrüche und Bestätigungsgrenzen ergänzen.
6. Öffentliche Weboberfläche und lokale Bridge klar trennen; niemals lokale Secrets oder freie Befehlsausführung in Netlify veröffentlichen.

## Auftrag an Claude

Übernimm dieses Projekt als bestehende Codebasis. Analysiere zuerst den aktuellen Stand und die ZIP-Datei. Verbessere J.A.R.V.I.S. schrittweise mit echten, getesteten Änderungen. Priorität haben Zuverlässigkeit, Geschwindigkeit, lokale Sichtbarkeit, klare Verifikation, sichere Bestätigungen und Wartbarkeit. Erfinde keine vorhandenen Fähigkeiten und melde jede nicht verifizierbare Aktion offen.
