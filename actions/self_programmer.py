import os

ACTIONS_DIR = os.path.dirname(os.path.abspath(__file__))

def create_new_action(filename: str, code_content: str) -> str:
    """Erstellt eine neue Python-Aktionsdatei im actions-Ordner."""
    if not filename.endswith(".py"):
        filename += ".py"
    try:
        filepath = os.path.join(ACTIONS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(code_content)
        return f"Erfolg: {filename} gespeichert."
    except Exception as e:
        return f"Fehler: {str(e)}"
