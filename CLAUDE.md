# J.A.R.V.I.S. Projektanweisungen

## Zweck

J.A.R.V.I.S. ist ein lokales Python-System mit einer statischen Netlify-Oberfläche.
Die Oberfläche sendet Befehle an Make.com; Zugangsdaten und API-Schlüssel bleiben
ausschließlich in `.env`.

## Wichtige Bereiche

- `core/brain.py`: Anbieter-Auswahl und KI-Aufrufe
- `gui_jarvis.py`: lokale Desktop-Oberfläche
- `JarvisUI/`: Netlify-Frontend und Functions
- `automation/make_scenarios.json`: Make.com-Szenario-Vorlagen
- `config/services.json`: Integrations-Konfiguration

## Lokale Einrichtung

1. `.env.example` nach `.env` kopieren.
2. `JARVIS_PROVIDER=auto` verwenden: Gemini wird bevorzugt, Ollama ist der lokale Fallback.
3. Für Gemini `GEMINI_API_KEY` eintragen; niemals Schlüssel committen.
4. Für Make.com die Webhook-Variablen in `.env` setzen.
5. Mit `.\start_jarvis.ps1 -CheckOnly` prüfen.

## Änderungsregeln

- Keine echten Secrets in Dateien, Commits, Logs oder Antworten ausgeben.
- Externe Aktionen (Nachrichten, E-Mails, Trades oder Kontoeinstellungen) nur nach
  ausdrücklicher Bestätigung ausführen.
- Finanzdaten als Szenarien und nicht als Anlageberatung formulieren.
- Bestehende Python-, HTML-, CSS- und JavaScript-Strukturen beibehalten.
- Änderungen mit dem kleinsten passenden Test oder Syntaxcheck verifizieren.

## Claude Code

Claude Code benötigt entweder ein Claude Pro/Max-Konto oder einen gültigen
Anthropic-API-Key. Der Schlüssel wird lokal über `ANTHROPIC_API_KEY` gesetzt und
nicht in dieses Projekt geschrieben.
