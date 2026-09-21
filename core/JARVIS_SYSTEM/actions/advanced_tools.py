import json, os, datetime, psutil

NOTES_FILE = os.path.join(os.path.dirname(__file__), "notes.json")

def create_note(title: str, content: str) -> str:
    """Erstellt eine neue Notiz oder Datei-Eintrag."""
    notes = {}
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                notes = json.load(f)
        except Exception:
            notes = {}
    notes[title] = {
        "content": content,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=4, ensure_ascii=False)
    return f"Notiz '{title}' erfolgreich gespeichert."

def get_system_status() -> str:
    """Liest die aktuelle Auslastung des PCs aus (CPU, RAM, Akku)."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    bat_str = f", Akku: {battery.percent}%" if battery else ""
    return f"CPU-Auslastung: {cpu}%, RAM-Belegung: {ram}%{bat_str}."
