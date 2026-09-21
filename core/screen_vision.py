import os
import threading
import time
from datetime import datetime
from pathlib import Path


class ScreenVision:
    """Local screen capture with an optional single-frame live observer."""

    def __init__(self, output_dir=None):
        root = Path(__file__).resolve().parents[1]
        self.output_dir = Path(output_dir or root / "data" / "screenshots")
        self.live_path = self.output_dir / "live_latest.png"
        self._live_stop = threading.Event()
        self._live_thread = None
        self._live_updated_at = 0.0

    @staticmethod
    def validate_image(path, max_bytes=20 * 1024 * 1024):
        """Return a safe, existing image path or raise a clear user error."""
        candidate = Path(str(path)).expanduser()
        if not candidate.is_file():
            raise ValueError("Bilddatei nicht gefunden.")
        if candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            raise ValueError("Unterstützt werden PNG, JPG, JPEG, WEBP und BMP.")
        if candidate.stat().st_size > max_bytes:
            raise ValueError("Das Bild ist zu groß (maximal 20 MB).")
        return candidate.resolve()

    def capture(self, open_file=True):
        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError(
                "Screen-Aufnahme fehlt. Installiere pyautogui mit: "
                "python -m pip install pyautogui"
            ) from exc

        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("screen_%Y%m%d_%H%M%S_%f.png")
        path = self.output_dir / filename
        image = pyautogui.screenshot()
        image.save(path)
        if open_file and hasattr(os, "startfile"):
            os.startfile(str(path))
        return path

    def start_live(self, interval=0.25):
        """Keep a fresh local frame every 250 ms; never opens or uploads it."""
        if self._live_thread and self._live_thread.is_alive():
            return
        self._live_stop.clear()
        self._live_thread = threading.Thread(
            target=self._live_loop,
            args=(max(float(interval), 0.25),),
            name="jarvis-live-screen",
            daemon=True,
        )
        self._live_thread.start()

    def stop_live(self):
        self._live_stop.set()
        if self._live_thread and self._live_thread.is_alive():
            self._live_thread.join(timeout=2)

    def latest_live_frame(self):
        """Return the newest frame, or None until the first frame is ready."""
        return self.live_path if self.live_path.is_file() else None

    def live_frame_age(self):
        """Return the age of the newest frame in seconds."""
        if not self.live_path.is_file():
            return None
        return max(0.0, time.time() - self.live_path.stat().st_mtime)

    def refresh_live_frame(self):
        """Capture one current frame synchronously before answering a question."""
        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError(
                "Live-Bild fehlt. Installiere pyautogui mit: "
                "python -m pip install pyautogui"
            ) from exc
        self.output_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.live_path.with_suffix(".tmp.png")
        pyautogui.screenshot().save(temporary)
        temporary.replace(self.live_path)
        self._live_updated_at = time.time()
        return self.live_path

    def observe(self):
        """Return a local observation without sending it to an external service."""
        frame = self.refresh_live_frame()
        observation = {
            "frame": str(frame),
            "age_ms": round(self.live_frame_age() * 1000, 1),
        }
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            observation["active_window"] = win32gui.GetWindowText(hwnd)
        except ImportError:
            observation["active_window"] = None
        return observation

    def _live_loop(self, interval):
        try:
            import pyautogui
        except ImportError:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        while not self._live_stop.is_set():
            temporary = self.live_path.with_suffix(".tmp.png")
            try:
                pyautogui.screenshot().save(temporary)
                temporary.replace(self.live_path)
                self._live_updated_at = time.time()
            except (OSError, RuntimeError):
                pass
            self._live_stop.wait(interval)
