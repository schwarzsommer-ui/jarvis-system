# J.A.R.V.I.S. Command Center

Die aktuelle Basis ist ein V2-Projektagent mit Provider-Auswahl (Claude, Gemini Flash, GPT-4o mini, NVIDIA NIM), Task-Auswahl (Projekt, Monitoring, Alert, Dashboard), strukturierten Plänen, Dashboard-/Monitoring-Platzhaltern, Voice-Grundlage und einer progressiven Three.js-Animation. Jarvis führt weiterhin keine unbeschränkten Shell-, Datei-, Trading- oder externen Aktionen in der öffentlichen Function aus.

## Struktur

```text
.
├── netlify/
│   └── functions/
│       ├── _shared/
│       │   ├── auth.js
│       │   └── response.js
│       ├── agent.js
│       ├── health.js
│       └── job.js
├── config/
│   ├── ai-services.js
│   ├── dashboard.json
│   ├── make.json
│   ├── monitoring.json
│   └── services.md
│   ├── jarvis-services.json
│   └── providers.json
├── ui/
│   ├── app.js
│   ├── _headers
│   ├── index.html
│   └── style.css
├── netlify.toml
└── README.md
```

Das Repository enthält daneben ältere lokale Jarvis- und UI-Komponenten. Die Root-Konfiguration deployt ausschließlich die oben genannte Command-Center-Oberfläche.

## Claude-Schlüssel in Netlify eintragen

1. In Netlify die Site öffnen.
2. **Project configuration → Environment variables** aufrufen.
3. `CLAUDE_API_KEY` als Secret mit deinem Anthropic-Key anlegen.
4. Optional `CLAUDE_MODEL` setzen. Ohne diese Variable verwendet V5 `claude-sonnet-5`.
5. Nach dem Anlegen einen neuen Deploy starten.

Der Schlüssel steht nur in Netlify Environment Variables. Er gehört nicht in HTML, JavaScript, Git oder diese Dokumentation.

Optional kann `JARVIS_ACCESS_TOKEN` gesetzt werden. Dann verlangen die geschützten Agent- und Job-Endpunkte den Header `Authorization: Bearer <TOKEN>`. Für eine produktive Mehrbenutzer-Anmeldung sollte später ein echter Identity-Provider (z. B. Netlify Identity oder Auth0) verwendet werden; ein einzelnes Shared Secret ist nur ein Übergang.

## Deploy

### Über Git

1. Das Repository zu GitHub, GitLab oder Bitbucket pushen.
2. In Netlify **Add new project → Import an existing project** wählen.
3. Das Repository verbinden. Die [netlify.toml](./netlify.toml) setzt `ui` als Publish-Verzeichnis und `netlify/functions` als Functions-Verzeichnis.
4. Deploy starten und anschließend `CLAUDE_API_KEY` hinterlegen bzw. den Deploy erneut ausführen.

### Mit Netlify CLI

```powershell
npm install -g netlify-cli
netlify login
netlify init
netlify deploy --prod
```

Im Repo-Root ausführen. Für lokale Tests kann `netlify dev` verwendet werden; der Endpoint ist dann `/.netlify/functions/agent`.

Der technische Status ist unter `/.netlify/functions/health` abrufbar. Er meldet nur, ob der Claude-Schlüssel konfiguriert ist, niemals den Schlüssel selbst.

`POST /.netlify/functions/job` erstellt einen sicheren Job-Vorschlag mit Status `awaiting_confirmation`. Er führt absichtlich nichts aus. Der Job-Endpoint ist die Schnittstelle für den späteren privaten Runner.

## Kostenlose lokale Stack-Lösung

Der stärkste kostenlose Weg ist ein lokaler Python-Stack ohne bezahlte SaaS-Desktop-Tools:

- `pyautogui` + `pywinauto` für Maus, Tastatur und sichtbare Windows-UI
- `playwright` für echte Browser-Automation auf lokalem Rechner
- `Pillow` + OCR/Visions-Tools für Screenshots und UI-Analyse
- `psutil` + `sounddevice` + `numpy` für System- und Live-Status
- Lokale LLMs wie Ollama oder Gemini mit freiem/limitiertem Account
- Keine kostenpflichtigen Remote-Desktop-Dienste nötig
- Die lokale Bridge bietet zusätzlich verifizierte Ordner-, Verschiebe- und
  Fensteraktionen über `core/agent_tools.py`; Löschen und Verschieben bleiben
  unmittelbar bestätigungspflichtig.

Damit läuft der Agent direkt auf dem PC, ohne Cloud-Steuerung. Die wichtigsten Sicherheitsgrenzen bleiben: nur erlaubte Apps, keine unbestätigten externen Aktionen, keine echten Trades/Bestellungen ohne Bestätigung.

### Gaming-sicherer Sprachmodus

Der optionale lokale Wake-Listener wird manuell gestartet:

```powershell
.\start_voice_listener.ps1
```

Er wartet stromsparend auf zwei Klatscher und danach „Hey Jarvis“. Erst nach
diesem Muster wird Sprache an die lokale API übertragen. „Jarvis aus“ beendet
die aktive Sitzung; der Listener kehrt in den Bereitschaftsmodus zurück.
Während ein konfiguriertes Spiel läuft, verschiebt der lokale Scheduler schwere
Obsidian- und Digest-Arbeiten. Telegram-Queue, Audit und Cloudflare-Relay
bleiben verfügbar. Den erkannten Gaming-Status liefert `GET /performance`.
Zusätzliche Spiele können über `JARVIS_GAME_PROCESSES` in `.env` ergänzt werden.

## Neuer lokaler Multi-Agent-Modus

Für die in diesem Projekt gewünschte CrewAI-/Ollama-Schicht gibt es einen
separaten, reproduzierbaren Windows-Ablauf. Er verändert die bestehende
Command-Center-Oberfläche nicht:

1. Python 3.11 oder 3.12 von [python.org](https://www.python.org/downloads/windows/)
   installieren und **Add Python to PATH** aktivieren.
2. Einen NVIDIA-NIM-Key im NVIDIA-Portal für die kostenlosen Modelle anlegen.
   Den Key nur lokal in `.env` als `NIM_API_KEY` eintragen; er wird nicht
   committed. `JARVIS_PROVIDER=auto` bevorzugt dann NVIDIA NIM automatisch.
   Ohne NIM-Key bleibt Ollama der lokale Fallback.
   `NIM_MODELS` enthält die bevorzugte Reihenfolge. Wenn ein Modell HTTP 402
   oder 429 wegen erschöpftem Kontingent liefert, markiert Jarvis es für die
   laufende Sitzung als erschöpft und versucht automatisch das nächste Modell.
   Sind alle NIM-Modelle erschöpft, wechselt Jarvis zu Ollama.
3. Ollama von [ollama.com/download](https://ollama.com/download) installieren,
   damit der Fallback verfügbar ist.
4. Im Projektordner aus PowerShell ausführen:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\setup_jarvis.ps1 -Install
   ```

   Das legt `venv`, `Logs` und `screenshots` an, installiert die optionale
   Multi-Agent-/Desktop-Schicht inklusive Open Interpreter und lädt
   standardmäßig `llama3.1`.
4. Die lokale Planung starten:

   ```powershell
   .\venv\Scripts\Activate.ps1
   python .\jarvis.py
   ```

   Ein anderes Ollama-Modell kann mit
   `.\setup_jarvis.ps1 -Install -OllamaModel llama3.1:8b` geladen werden.
   Open Interpreter kann danach mit `interpreter` separat gestartet werden.

`desktop_control.py` enthält die ausdrücklich aufrufbaren Funktionen für
Programmstart, Browser, Tastatureingabe, Klicks, Ordner und Screenshots. Das
Modul öffnet keinen Netzwerkzugang und führt keine Aktion beim Import aus.
CrewAI erstellt nur einen Plan; das tatsächliche Öffnen, Klicken oder Tippen
bleibt eine separate, sichtbare lokale Aktion. Für Nachrichten, E-Mails,
Trades, Kontoeinstellungen, Löschen oder Herunterfahren ist weiterhin eine
Bestätigung unmittelbar vor der Aktion erforderlich.

## Agent testen

Öffne die veröffentlichte Site, gib eine Anfrage ein und klicke **Jarvis fragen**. Alternativ:

```powershell
curl.exe -X POST https://DEINE-SITE.netlify.app/.netlify/functions/agent `
  -H "Content-Type: application/json" `
  -d '{\"message\":\"Plane eine V2 für Datei- und Build-Tools.\"}'
```

Erwartete Antwort:

```json
{"reply":"..."}
```

Ein Request kann `provider` (`gemini`, `gpt`, `nim` oder kompatibel `claude`), `task` (`monitoring`, `alert`, `dashboard` oder `default`) und `mode` (`plan`, `code` oder `debug`) enthalten. Ohne Provider wird Gemini verwendet; für die aktuell konfigurierte Claude-Installation kann die UI Claude auswählen. Ohne Schlüssel oder Endpoint antwortet die Function mit HTTP 503. Ungültige Methoden, JSON-Daten, Provider, Tasks, Modi oder leere Nachrichten werden mit einer passenden 4xx-Antwort abgewiesen.

Die Claude-Antwort wird als strukturierter Plan erwartet:

```json
{
  "summary": "...",
  "steps": [],
  "files": [],
  "tests": [],
  "risks": [],
  "suggestedActions": []
}
```

## Roadmap

### V2: Code schreiben und Fehler-Fixing (Planungsbasis umgesetzt)

- Datei lesen/schreiben, Patchen, Linting, Tests und Build als getrennte serverseitige Tools.
- Sicheres Tool-Protokoll mit erlaubten Arbeitsverzeichnissen und expliziter Bestätigung vor Dateiänderungen.
- Job-Status, Logs und Diff-Vorschau statt direkter, unsichtbarer Änderungen.
- Authentifizierung und Rate-Limits vor produktiven Schreib- oder Build-Aktionen.

### V3: Automationen (Platzhalter umgesetzt)

- Make.com-Webhooks mit validierten Payloads und getrennten Szenarien.
- Telegram, News-Feeds, Forex/XAUUSD und Krypto als klar abgegrenzte Integrationen.
- Bestätigungsschritt für Nachrichten, Trades, Kontoeinstellungen und andere externe Aktionen.
- Persistente Jobs, Retries, Audit-Logs und Monitoring.
- Die Function liefert `confirmationRequired: true`, Capability-Tags und eine Liste blockierter Aktionen zurück.
- API-Schlüssel bleiben ausschließlich in Netlify Environment Variables; es werden keine Secrets in die UI übertragen.
- [config/jarvis-services.json](./config/jarvis-services.json) dokumentiert deaktivierte Integrationsgrenzen ohne Zugangsdaten.

### V4: UI-Animationen und Dashboard (Grundlagen umgesetzt)

- Three.js-Orb als progressive Enhancement mit CSS-Fallback.
- Dashboard-Panels für Agent-Status, Tool-Sicherheit, Märkte und Voice-Status.
- Sprachsteuerung via Web Speech API sowie optionale TTS-Ausgabe.
- Die Vorlesefunktion setzt auf die deutsche Browser-/Windows-Sprachausgabe und
  bevorzugt natürliche Stimmen wie Microsoft Katja oder Microsoft Conrad, sofern
  sie auf dem Gerät installiert und im Browser verfügbar sind. Eine Stimme wird
  aus Lizenz- und Sicherheitsgründen nicht in das Repository kopiert.
- Für die lokale Python-Bridge ist zusätzlich die herunterladbare Open-Source-
  Piper-Stimme `de_DE-thorsten-medium` vorbereitet. Installation unter Windows:
  `powershell.exe -ExecutionPolicy Bypass -File .\scripts\install_piper_voice.ps1`.
  Liegt das Modell unter `models/voices`, wird es offline bevorzugt; andernfalls
  fällt Jarvis auf Edge TTS mit `de-DE-KillianNeural` und anschließend auf
  die lokale Systemstimme zurück.
- Responsive Layout, Accessibility und klare Lade-/Fehlerzustände.
- World-Intelligence-Szene mit echter Erdtextur, Wolken-, Nachtlicht- und Atmosphärenlayern.
- Ortsauflösung per Geocoding, automatischer Kamera-Fokus und animierter Location-Lock.
- Live-News-Proxy unter `/.netlify/functions/news` mit RSS-Quellen und optionalem Ortsfilter.
- Region-Proxy unter `/.netlify/functions/region` für Wetter, lokale Zeitzone,
  Koordinaten und regionale RSS-Feeds ohne API-Key.
- Internationale RSS-Titel werden im Region-Proxy über den konfigurierten
  Gemini-Provider ins Deutsche übersetzt. Wenn der Provider nicht verfügbar
  ist, bleiben die bestätigten Originaltitel erhalten, statt Inhalte zu erfinden.
- Optionale Premium-Sprachausgabe über [ElevenLabs](https://elevenlabs.io):
  `ELEVENLABS_API_KEY` und `ELEVENLABS_VOICE_ID` in Netlify setzen. Als
  passende legale Ausgangsstimme eignet sich eine ruhige, tiefe deutsche bzw.
  deutschfähige Multilingual-Stimme aus der ElevenLabs Voice Library, z. B.
  `Antoni` (Voice-ID `ErXwobaYiN019PkySvjV`), sofern sie in deinem Konto
  verfügbar ist. Das ist keine Filmstimmen-Imitation. Ohne Konfiguration bleibt
  die deutsche Browser-/Systemstimme der Fallback.
- Als nächstes: persistente Job-Ansicht, authentifizierte Nutzer-Sessions und weitere Datenadapter.

## Was für echte Ausführung noch konfiguriert werden muss

Die Konfigurationsdatei [config/providers.json](./config/providers.json) beschreibt die Grenzen. Vor produktiver Ausführung müssen ein privater Runner und eine Datenbank bereitgestellt werden:

1. `JARVIS_RUNNER_URL` und `JARVIS_RUNNER_TOKEN` nur in Netlify hinterlegen.
2. Runner in isolierter Umgebung mit Workspace-Allowlist, Command-Allowlist, Timeout und Audit-Log betreiben.
3. `JARVIS_DATABASE_URL` für Jobs, Projekte, Konversationen und Audit-Logs konfigurieren.
4. Make.com, Telegram, Marktdaten und Deploy-Hooks einzeln aktivieren und jeweils mit Bestätigung, Signaturprüfung und Rate-Limits schützen.
5. Erst danach die `executionEnabled`-Sperre in einem privaten, authentifizierten Ausführungsdienst ändern — niemals in der öffentlichen Planungsfunktion.

In [ui/index.html](./ui/index.html) sind die vorgesehenen Erweiterungspunkte für Sprachsteuerung, Three.js-Animationen und Dashboard-Panels kommentiert.

## API-Keys und Webhooks

In Netlify unter **Project configuration -> Environment variables**:

- `CLAUDE_API_KEY` und optional `CLAUDE_MODEL`
- `GEMINI_API_KEY`, `GEMINI_API_URL`, `GEMINI_MODEL`
- `GPT_API_KEY`, `GPT_API_URL`, `GPT_MODEL`
- `NIM_API_KEY`, `NIM_API_URL`, `NIM_MODEL`
- `MAKE_WEBHOOK_URL`

Nur der Provider, dessen Werte gesetzt sind, darf verwendet werden. `config/ai-services.js` und `config/make.json` enthalten nur Namen und Platzhalter, niemals echte Werte.

## Ausführung innerhalb des Projekts

Die öffentliche Netlify Function kann dein lokales Projekt nicht sicher direkt bearbeiten. Für automatische Dateiänderungen, Builds und Tests wird ein privater Runner benötigt. Dieser Runner muss auf das Projekt-Workspace begrenzt, authentifiziert, protokolliert und mit einer Allowlist versehen sein. Die öffentliche Function erzeugt daher nur einen strukturierten Plan bzw. einen bestätigungspflichtigen Job und führt keine beliebigen Nutzerbefehle aus.

### Lokaler Projektmodus

Der lokale Copilot enthält jetzt einen abgesicherten Projekt-Runner. Er ist nur
über `127.0.0.1:8765` erreichbar und arbeitet standardmäßig im Repository-Root.
Vor dem Start kann ein anderer Projektordner ausdrücklich gesetzt werden:

```powershell
$env:JARVIS_WORKSPACE = "C:\Pfad\zu\deinem\Projekt"
powershell.exe -ExecutionPolicy Bypass -File .\start_copilot.ps1
```

Der Runner kann Dateien lesen, eine Schreibvorschau erzeugen, nach Bestätigung
Dateien schreiben und die freigegebenen Prüfungen `python_syntax`,
`python_tests`, `npm_test` und `npm_build` ausführen. Jede Änderung und jeder
Befehl wird in `.jarvis/audit.jsonl` protokolliert. `.env`-Dateien,
Schlüssel-, Token- und Credential-Dateien sowie Pfade außerhalb des Workspace
werden abgewiesen. Schreibvorgänge und Befehle benötigen immer
`confirmed: true`; ohne Bestätigung wird nur ein Plan zurückgegeben.

Für kontrollierte Reparaturen stehen zusätzlich `repair-plan` und
`repair-apply` zur Verfügung. Der Reparaturplan enthält einen Unified-Diff,
alte/neue SHA-256-Hashes und den Grund der Änderung. Erst `repair-apply` mit
`confirmed: true` schreibt die Datei; ein abweichender alter Hash bricht ab.
Nach dem Schreiben sollte unmittelbar wieder `python_syntax`, `python_tests`
oder `npm_build` ausgeführt werden. Es gibt weiterhin keine freie Shell und
keine automatische Änderung von Secret-Dateien.

Beispiele für die lokale API:

```powershell
curl.exe -X POST http://127.0.0.1:8765/api/runner/plan-write `
  -H "Content-Type: application/json" `
  -d '{"path":"notes/example.txt","content":"Jarvis test"}'

curl.exe -X POST http://127.0.0.1:8765/api/runner/run `
  -H "Content-Type: application/json" `
  -d '{"command":"python_syntax","confirmed":true}'
```

Die Netlify-Oberfläche darf diesen lokalen Runner nicht direkt aufrufen. Für
eine spätere Kopplung muss zuerst eine authentifizierte, private Verbindung
mit Ablaufzeiten und derselben Bestätigungslogik eingerichtet werden.
