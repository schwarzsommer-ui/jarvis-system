import json
from pathlib import Path


class AudioDeviceManager:
    """Keeps microphone selection stable across Windows device-index changes."""

    def __init__(self, filepath=None):
        root = Path(__file__).resolve().parents[1]
        self.filepath = Path(filepath or root / "core" / "audio_devices.json")
        self.selected_name = self._load_selected_name()

    def _load_selected_name(self):
        try:
            payload = json.loads(self.filepath.read_text(encoding="utf-8"))
            return str(payload.get("input_name", "")).strip()
        except (OSError, json.JSONDecodeError, AttributeError):
            return ""

    def _save_selected_name(self, name):
        self.filepath.write_text(
            json.dumps({"input_name": name}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.selected_name = name

    def list_input_devices(self):
        try:
            import speech_recognition as sr
            names = sr.Microphone.list_microphone_names()
        except (ImportError, OSError):
            return []
        return [
            {"index": index, "name": str(name)}
            for index, name in enumerate(names)
            if str(name).strip()
        ]

    def selected_index(self):
        devices = self.list_input_devices()
        if self.selected_name:
            for device in devices:
                if device["name"] == self.selected_name:
                    return device["index"]
        return None

    def select_input(self, name):
        wanted = str(name).strip()
        for device in self.list_input_devices():
            if device["name"] == wanted:
                self._save_selected_name(wanted)
                return device
        raise ValueError(f"Mikrofon nicht gefunden: {wanted}")

    def status(self):
        devices = self.list_input_devices()
        return {
            "selected": self.selected_name,
            "selected_index": self.selected_index(),
            "devices": devices,
        }
