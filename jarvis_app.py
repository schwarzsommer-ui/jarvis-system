"""Windows desktop control center for the local J.A.R.V.I.S. stack."""

from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path("python.exe")
START_SCRIPT = PROJECT_ROOT / "start_v2.ps1"
DASHBOARD_URL = "http://127.0.0.1:8000/"
VOICE_URL = "http://127.0.0.1:8000/voice.html"
UI_VERSION = "mission-board-v2"
HEALTH_URL = "http://127.0.0.1:8787/health"
VOICE_SCRIPT = PROJECT_ROOT / "voice_wake_listener.py"
EDGE_PATHS = (
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
)


def monitor_layout() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    try:
        import ctypes
        from ctypes import wintypes

        monitors: list[tuple[int, int, int, int]] = []
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.RECT),
            ctypes.c_double,
        )

        def collect(_monitor, _dc, rect, _data):
            item = rect.contents
            monitors.append((item.left, item.top, item.right, item.bottom))
            return 1

        ctypes.windll.user32.EnumDisplayMonitors(0, 0, callback_type(collect), 0)
        if len(monitors) >= 2:
            monitors.sort(key=lambda item: item[0])
            return tuple(
                (left, top, right - left, bottom - top)
                for left, top, right, bottom in (monitors[0], monitors[-1])
            )
    except (AttributeError, OSError):
        pass
    return (0, 0, 1280, 1080), (1280, 0, 1920, 1080)


def hidden_process(command: list[str], cwd: Path = PROJECT_ROOT) -> subprocess.Popen:
    log_dir = PROJECT_ROOT / "Logs"
    log_dir.mkdir(exist_ok=True)
    log_name = "desktop_launcher.log" if "jarvis_app.py" in " ".join(command) else "background_services.log"
    log_file = (log_dir / log_name).open("a", encoding="utf-8")
    return subprocess.Popen(
        command,
        cwd=cwd,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )


def endpoint_online(url: str) -> bool:
    try:
        with urlopen(url, timeout=1.5) as response:
            return 200 <= response.status < 300
    except (OSError, URLError):
        return False


class JarvisLauncher:
    def __init__(self) -> None:
        self.window = tk.Tk()
        self.window.title("J.A.R.V.I.S. | Desktop Control")
        self.window.geometry("620x430")
        self.window.minsize(560, 390)
        self.window.configure(bg="#090b10")
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
        self._stack_started = False
        self._voice_started = False
        self._dashboard_opened = False
        self._build_ui()
        self.window.after(700, self.start_stack)
        self.window.after(3000, self.start_voice)
        self._poll_status()

    def _build_ui(self) -> None:
        self.status = tk.StringVar(value="Bereit für den Systemstart")
        self.backend_status = tk.StringVar(value="wird geprüft")
        self.dashboard_status = tk.StringVar(value="wird geprüft")

        tk.Label(
            self.window,
            text="J.A.R.V.I.S.",
            fg="#f6a04d",
            bg="#090b10",
            font=("Segoe UI Semibold", 30),
        ).pack(anchor="w", padx=34, pady=(28, 0))
        tk.Label(
            self.window,
            text="LOCAL COMMAND CENTER  /  NVIDIA → OLLAMA FALLBACK",
            fg="#87909d",
            bg="#090b10",
            font=("Consolas", 9),
        ).pack(anchor="w", padx=37, pady=(2, 24))

        status_frame = tk.Frame(self.window, bg="#11151c", highlightthickness=1, highlightbackground="#272e38")
        status_frame.pack(fill="x", padx=34)
        self._status_line(status_frame, "Backend API", self.backend_status)
        self._status_line(status_frame, "Dashboard", self.dashboard_status)
        self._status_line(status_frame, "Sicherheitsmodus", tk.StringVar(value="aktiv · lokale Aktionen live"))

        tk.Label(
            self.window,
            textvariable=self.status,
            fg="#c8d0da",
            bg="#090b10",
            font=("Segoe UI", 11),
        ).pack(anchor="w", padx=37, pady=(22, 12))

        actions = tk.Frame(self.window, bg="#090b10")
        actions.pack(fill="x", padx=34)
        self._button(actions, "J.A.R.V.I.S. starten", self.start_stack, "#d87d2f", "#ffffff").pack(
            side="left", fill="x", expand=True, padx=(0, 7)
        )
        self._button(actions, "Dashboard öffnen", self.open_dashboard, "#18202b", "#f2b56f").pack(
            side="left", fill="x", expand=True, padx=7
        )
        self._button(actions, "Wake Listener", self.start_voice, "#18202b", "#f2b56f").pack(
            side="left", fill="x", expand=True, padx=(7, 0)
        )

        tk.Label(
            self.window,
            text="Alle Dienste bleiben lokal auf diesem PC. Externe Aktionen bleiben geschützt.",
            fg="#68727f",
            bg="#090b10",
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=37, pady=(26, 0))

    @staticmethod
    def _status_line(parent: tk.Frame, label: str, value: tk.StringVar) -> None:
        row = tk.Frame(parent, bg="#11151c")
        row.pack(fill="x", padx=14, pady=8)
        tk.Label(row, text=label, width=20, anchor="w", fg="#9ca7b5", bg="#11151c", font=("Segoe UI", 10)).pack(side="left")
        tk.Label(row, textvariable=value, anchor="w", fg="#78dfaa", bg="#11151c", font=("Consolas", 10)).pack(side="left")

    @staticmethod
    def _button(parent: tk.Frame, text: str, command, background: str, foreground: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground="#f0a15a",
            activeforeground="#090b10",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            padx=10,
            pady=12,
        )

    def start_stack(self) -> None:
        if self._stack_started:
            return
        if not START_SCRIPT.exists():
            messagebox.showerror("Startfehler", f"Fehlt: {START_SCRIPT}")
            return
        self._stack_started = True
        hidden_process(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(START_SCRIPT),
            ]
        )
        self.status.set("Lokale Dienste werden gestartet …")

    def start_voice(self) -> None:
        if self._voice_started:
            return
        if not VOICE_SCRIPT.exists():
            messagebox.showerror("Wake Listener", f"Fehlt: {VOICE_SCRIPT}")
            return
        self._voice_started = True
        hidden_process([str(PYTHON), "-B", str(VOICE_SCRIPT)])
        self.status.set("Wake Listener wurde gestartet.")

    def _launch_browser_window(self, profile_name: str, url: str, x: int, y: int, width: int, height: int) -> bool:
        edge = os.environ.get("JARVIS_BROWSER")
        if not edge:
            edge = next((str(path) for path in EDGE_PATHS if path.exists()), "msedge.exe")
        edge_root = Path(os.environ.get("LOCALAPPDATA", str(PROJECT_ROOT))) / "JARVIS" / "edge"
        profile_dir = edge_root / profile_name
        profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(
                [
                    edge,
                    f"--user-data-dir={profile_dir}",
                    "--new-window",
                    "--app=" + url,
                    f"--window-position={x},{y}",
                    f"--window-size={width},{height}",
                ],
                cwd=PROJECT_ROOT,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            return False

    def open_dashboard(self) -> None:
        if self._dashboard_opened:
            return
        if not endpoint_online(DASHBOARD_URL):
            self.status.set("Dashboard ist noch nicht bereit. Starte zuerst J.A.R.V.I.S.")
            return
        left, right = monitor_layout()
        edge_root = Path(os.environ.get("LOCALAPPDATA", str(PROJECT_ROOT))) / "JARVIS" / "edge"
        self._close_jarvis_windows(edge_root)
        launched = []
        for profile_name, url, rect in (
            ("voice-v2", f"{VOICE_URL}?ui={UI_VERSION}", left),
            ("dashboard-v2", f"{DASHBOARD_URL}?ui={UI_VERSION}", right),
        ):
            if self._launch_browser_window(profile_name, url, *rect):
                launched.append(profile_name)
        self._dashboard_opened = bool(launched)
        if self._dashboard_opened:
            self.status.set("Sprachzentrale links und Dashboard rechts geöffnet.")
        else:
            self.status.set("Browser-Fenster konnten nicht geöffnet werden.")
        self.window.after(1200, self.window.withdraw)

    @staticmethod
    def _close_jarvis_windows(edge_root: Path) -> None:
        try:
            import psutil

            root_marker = str(edge_root).lower()
            for process in psutil.process_iter(["name", "cmdline"]):
                if process.info.get("name", "").lower() != "msedge.exe":
                    continue
                command_line = " ".join(process.info.get("cmdline") or []).lower()
                if root_marker in command_line:
                    process.terminate()
        except (ImportError, OSError):
            return

    def _poll_status(self) -> None:
        def check() -> None:
            backend = endpoint_online(HEALTH_URL)
            dashboard = endpoint_online(DASHBOARD_URL)
            self.window.after(0, lambda: self._apply_status(backend, dashboard))

        threading.Thread(target=check, daemon=True).start()
        self.window.after(2500, self._poll_status)

    def _apply_status(self, backend: bool, dashboard: bool) -> None:
        self.backend_status.set("online" if backend else "offline")
        self.dashboard_status.set("online" if dashboard else "offline")
        if dashboard and not self._dashboard_opened:
            self.open_dashboard()
        if backend and dashboard:
            self.status.set("System online · Dashboard geöffnet")
        elif dashboard:
            self.status.set("Dashboard geöffnet · Backend startet noch")

    def run(self) -> None:
        self.window.mainloop()


if __name__ == "__main__":
    JarvisLauncher().run()
