# J.A.R.V.I.S. Services

Alle Einträge in `config/` sind Platzhalter. Echte Schlüssel gehören ausschließlich in Netlify Environment Variables.

## KI-Provider

- **Gemini Flash**: `GEMINI_API_KEY`, optional `GEMINI_API_URL` und `GEMINI_MODEL`
- **GPT-4o mini**: `GPT_API_KEY`, optional `GPT_API_URL` und `GPT_MODEL`
- **NVIDIA NIM**: `NIM_API_KEY`, optional `NIM_API_URL` und `NIM_MODEL`
- **Claude**: `CLAUDE_API_KEY`, `CLAUDE_MODEL` für den bestehenden Claude-Adapter

Die Provider-Auswahl kommt im JSON-Request als `provider` (`gemini`, `gpt` oder `nim`). Ein Provider darf nur verwendet werden, wenn sein Key und Endpoint serverseitig konfiguriert sind.

## Make.com und Webhooks

[make.json](./make.json) enthält Webhook-Platzhalter und Beispiel-Payloads für Telegram Alerts, Monitoring Events und Dashboard Updates. Die echte URL wird als `MAKE_WEBHOOK_URL` in Netlify eingetragen. Webhooks bleiben deaktiviert, bis Signaturprüfung, Rate-Limits und eine ausdrückliche Bestätigung vorhanden sind.

## Monitoring

[monitoring.json](./monitoring.json) definiert Platzhalter für Forex, XAUUSD, Krypto und News. Daten werden als Szenarien dargestellt, nicht als Anlageberatung. Preis- oder News-Provider müssen später als getrennte Adapter ergänzt werden.

## Dashboard

[dashboard.json](./dashboard.json) definiert Panels für Forex, XAUUSD, Krypto, News, Alerts und Systemstatus. Der Systemstatus kommt aus `/.netlify/functions/health`; die übrigen Panels sind standardmäßig deaktiviert.

## UI

[ui/index.html](../ui/index.html) enthält Eingabe, Provider- und Task-Auswahl, Dashboard und Monitoring-Platzhalter. [ui/app.js](../ui/app.js) sendet JSON an `/.netlify/functions/agent`, rendert Antworten und bietet Voice-/Animations-Hooks.

## Netlify Functions

- `agent`: validiert Requests, routet Provider und erzeugt eine Antwort bzw. einen sicheren Ausführungsplan.
- `health`: meldet Konfigurationsstatus ohne Geheimnisse.
- `job`: erstellt bestätigungspflichtige Job-Vorschläge; führt noch nichts aus.

## Projektinterne Ausführung

Ein öffentlicher Netlify-Handler erhält keinen sicheren Zugriff auf dein lokales Projekt. Für Dateiänderungen, Builds und Tests wird ein privater Runner mit Workspace-Allowlist, Command-Allowlist, Timeout, Audit-Log und Confirmation-ID benötigt. Unbeschränkte Shell- oder Löschbefehle werden nicht aktiviert.
