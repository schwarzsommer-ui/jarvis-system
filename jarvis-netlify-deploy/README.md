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
- Responsive Layout, Accessibility und klare Lade-/Fehlerzustände.
- Als nächstes: persistente Job-Ansicht, News-/Marktdaten-Adapter und authentifizierte Nutzer-Sessions.

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
