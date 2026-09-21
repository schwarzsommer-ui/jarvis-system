import os
import json
import webbrowser
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from pathlib import Path

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


class JarvisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Jarvis Hub")
        self.root.geometry("1400x900")
        self.root.configure(bg="#0b1020")
        self.root.minsize(1100, 700)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.base_dir = Path(__file__).resolve().parent
        self.memory_file = self.base_dir / "jarvis_memory.json"
        self.notes_dir = self.base_dir / "notes"
        self.notes_dir.mkdir(exist_ok=True)

        self.memory = self.load_memory()
        self.voice_enabled = True

        self.build_ui()
        self.update_status()

    def load_memory(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {"facts": [], "tasks": [], "notes": []}

    def save_memory(self):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    def remember(self, text):
        if not text:
            return
        item = {"text": text, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.memory["facts"].append(item)
        self.save_memory()
        self.log(f"Memory saved: {text}")

    def log(self, text):
        self.log_box.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
        self.log_box.see(tk.END)

    def speak(self, text):
        if not self.voice_enabled:
            return
        if pyttsx3:
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 170)
                engine.setProperty("volume", 1.0)
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass

    def build_ui(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # Sidebar
        sidebar = tk.Frame(self.root, bg="#101827", width=220, padx=18, pady=18)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        title = tk.Label(sidebar, text="JARVIS", fg="#d9f3ff", bg="#101827",
                         font=("Segoe UI", 24, "bold"))
        title.pack(anchor="w", pady=(10, 20))

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=(0, 18))

        navs = ["Home", "Assistant", "Tools", "Memory", "Automation", "Settings"]
        for item in navs:
            btn = tk.Button(
                sidebar,
                text=item,
                bg="#121c2d" if item != "Home" else "#1b2436",
                fg="white",
                bd=0,
                height=2,
                activebackground="#1d2b42",
                font=("Segoe UI", 12),
                command=lambda x=item: self.log(f"Selected: {x}")
            )
            btn.pack(fill="x", pady=4)

        bottom = tk.Frame(sidebar, bg="#101827")
        bottom.pack(side="bottom", fill="x", pady=(120, 10))
        tk.Label(bottom, text="SYSTEM", bg="#101827", fg="#7dd3fc",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(bottom, text="Online • Ready", bg="#101827", fg="#a7f3d0",
                 font=("Segoe UI", 12)).pack(anchor="w", pady=(8, 0))

        content = tk.Frame(self.root, bg="#0b1020")
        content.grid(row=0, column=1, sticky="nsew", padx=22, pady=22)

        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1)

        topbar = tk.Frame(content, bg="#0b1020", height=60)
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        topbar.grid_columnconfigure(0, weight=1)

        tk.Label(topbar, text="Personal AI Hub", fg="#e5f3ff", bg="#0b1020",
                 font=("Segoe UI", 24, "bold")).grid(row=0, column=0, sticky="w", padx=6)

        status = tk.Frame(topbar, bg="#111827", bd=1, relief="solid", padx=18, pady=8)
        status.grid(row=0, column=1, sticky="e")
        tk.Label(status, text="●", bg="#111827", fg="#34d399",
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(status, text="Listening", bg="#111827", fg="#d1fae5",
                 font=("Segoe UI", 11)).pack(side="left", padx=(4, 0))

        left_panel = tk.Frame(content, bg="#0b1020")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 12))

        hero = tk.Frame(left_panel, bg="#101a2e", bd=1, relief="solid", padx=22, pady=20)
        hero.pack(fill="x", pady=(0, 18))
        tk.Label(hero, text="Good evening, Tim", fg="#eaf7ff", bg="#101a2e",
                 font=("Segoe UI", 28, "bold")).pack(anchor="w")
        tk.Label(hero, text="Your system is ready. Open apps, take notes, remember tasks, and work with me.",
                 fg="#a7b7cc", bg="#101a2e", justify="left",
                 font=("Segoe UI", 14)).pack(anchor="w", pady=(10, 0))

        cards = tk.Frame(left_panel, bg="#0b1020")
        cards.pack(fill="x")

        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)
        cards.grid_columnconfigure(2, weight=1)

        for i, (name, value) in enumerate([("SYSTEM", "Healthy"), ("TASKS", "3 Active"), ("WEATHER", "21°C")]):
            card = tk.Frame(cards, bg="#111c30", bd=1, relief="solid", padx=18, pady=18)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            tk.Label(card, text=name, fg="#7dd3fc", bg="#111c30",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")
            tk.Label(card, text=value, fg="#eaf7ff", bg="#111c30",
                     font=("Segoe UI", 24, "bold")).pack(anchor="w", pady=(10, 0))

        right_panel = tk.Frame(content, bg="#101a2e", bd=1, relief="solid", padx=18, pady=18)
        right_panel.grid(row=1, column=1, sticky="nsew")

        tk.Label(right_panel, text="Quick Actions", fg="#eaf7ff", bg="#101a2e",
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 12))

        actions = [
            ("Open Chrome", self.open_chrome),
            ("Open Spotify", self.open_spotify),
            ("Open Notepad", self.open_notepad),
            ("Open GitHub", self.open_github),
            ("System Info", self.show_system_info),
        ]
        for label, cmd in actions:
            tk.Button(right_panel, text=label, bg="#111827", fg="white", bd=0,
                      height=2, activebackground="#1d2b42", font=("Segoe UI", 11),
                      command=cmd).pack(fill="x", pady=6)

        command_bar = tk.Frame(content, bg="#0f172a", bd=1, relief="solid", padx=12, pady=12)
        command_bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        command_bar.grid_columnconfigure(0, weight=1)

        self.command_entry = tk.Entry(command_bar, bg="#0f172a", fg="#eaf7ff",
                                      insertbackground="#eaf7ff", font=("Segoe UI", 18),
                                      bd=0)
        self.command_entry.insert(0, "Say: 'Jarvis, open Chrome'")
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(8, 10))

        tk.Button(command_bar, text="Execute", bg="#0ea5e9", fg="white",
                  bd=0, height=2, width=18, font=("Segoe UI", 12, "bold"),
                  command=self.execute_command).grid(row=0, column=1)

        self.log_box = scrolledtext.ScrolledText(content, bg="#0d1322", fg="#dfe8f8",
                                                insertbackground="#dfe8f8",
                                                font=("Consolas", 10), bd=0, wrap=tk.WORD)
        self.log_box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        self.log_box.configure(height=8)

        self.log("Jarvis initialized.")
        self.log(f"Memory file: {self.memory_file}")
        self.log("Ready for commands.")

    def on_close(self):
        self.save_memory()
        self.root.destroy()

    def update_status(self):
        now = datetime.now().strftime("%H:%M")
        self.root.title(f"Jarvis Hub - {now}")

        self.root.after(10000, self.update_status)

    def open_chrome(self):
        try:
            self.log("Opening Chrome...")
            subprocess.Popen(["chrome.exe"], shell=False)
            self.speak("Chrome wird geöffnet.")
        except Exception as e:
            self.log(f"Chrome launch failed: {e}")

    def open_spotify(self):
        try:
            self.log("Opening Spotify...")
            subprocess.Popen(["spotify.exe"], shell=False)
            self.speak("Spotify wird geöffnet.")
        except Exception as e:
            self.log(f"Spotify launch failed: {e}")

    def open_notepad(self):
        try:
            self.log("Opening Notepad...")
            subprocess.Popen(["notepad.exe"])
            self.speak("Notepad wird geöffnet.")
        except Exception as e:
            self.log(f"Notepad launch failed: {e}")

    def open_github(self):
        try:
            self.log("Opening GitHub...")
            webbrowser.open("https://github.com")
            self.speak("GitHub wird geöffnet.")
        except Exception as e:
            self.log(f"GitHub launch failed: {e}")

    def show_system_info(self):
        info = f"OS: {sys.platform}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        messagebox.showinfo("System Info", info)
        self.log("System info requested.")

    def create_note(self, text):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.notes_dir / f"note_{timestamp}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text)
        self.log(f"Note saved: {filename}")
        self.speak("Notiz gespeichert.")

    def execute_command(self):
        cmd = self.command_entry.get().strip()
        if not cmd or cmd.startswith("Say:"):
            self.log("Empty command.")
            return

        self.log(f"Command received: {cmd}")
        text = cmd.lower()

        if "chrome" in text:
            self.open_chrome()
            self.remember(f"Open command: Chrome")
            return

        if "spotify" in text:
            self.open_spotify()
            self.remember(f"Open command: Spotify")
            return

        if "notepad" in text:
            self.open_notepad()
            self.remember(f"Open command: Notepad")
            return

        if "github" in text:
            self.open_github()
            self.remember(f"Open command: GitHub")
            return

        if "time" in text:
            t = datetime.now().strftime("%H:%M")
            self.log(f"Current time: {t}")
            self.speak(f"Es ist {t}")
            return

        if "date" in text:
            d = datetime.now().strftime("%d.%m.%Y")
            self.log(f"Current date: {d}")
            self.speak(f"Heute ist der {d}")
            return

        if "remember" in text:
            remember_text = cmd[len("remember"):].strip()
            if remember_text:
                self.remember(remember_text)
                self.speak("Erinnerung gespeichert.")
                return

        if "note" in text or "notiz" in text:
            note_text = cmd
            if "note" in text:
                note_text = cmd.split("note", 1)[1].strip()
            elif "notiz" in text:
                note_text = cmd.split("notiz", 1)[1].strip()

            if note_text:
                self.create_note(note_text)
                self.remember(f"Note: {note_text}")
            else:
                self.log("No note content found.")
            return

        if "search" in text or "google" in text:
            query = cmd.replace("search", "").replace("google", "").strip()
            if not query:
                query = "jarvis ai"
            url = "https://www.google.com/search?q=" + query.replace(" ", "+")
            webbrowser.open(url)
            self.log(f"Search opened: {url}")
            self.speak("Suche gestartet.")
            return

        if "memory" in text or "erinnerungen" in text:
            if self.memory.get("facts"):
                info = "\n".join(item["text"] for item in self.memory["facts"][-5:])
                messagebox.showinfo("Jarvis Memory", info)
            else:
                messagebox.showinfo("Jarvis Memory", "Noch keine Erinnerungen gespeichert.")
            return

        self.log("Command not recognized.")
        self.speak("Befehl nicht erkannt.")
        messagebox.showinfo("Jarvis", f"Unbekannter Befehl: {cmd}")


if __name__ == "__main__":
    root = tk.Tk()
    app = JarvisApp(root)
    root.mainloop()