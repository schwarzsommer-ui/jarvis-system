import customtkinter as ctk
import threading
import psutil
from core.brain import JarvisBrain

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class JarvisHUD(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("J.A.R.V.I.S. — MARK XXXIX COMMAND CENTRE")
        self.geometry("1200x750")
        
        self.brain = JarvisBrain()
        self.setup_ui()
        self.update_system_stats()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Linkes Panel: System Monitor & Agent Status
        self.left_panel = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color="#121212")
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        
        self.sys_label = ctk.CTkLabel(self.left_panel, text="⚡ SYSTEM MONITOR", font=("Consolas", 15, "bold"), text_color="#1f6aa5")
        self.sys_label.pack(padx=20, pady=(20, 10), anchor="w")

        self.cpu_label = ctk.CTkLabel(self.left_panel, text="CPU: 0.0%", font=("Consolas", 12))
        self.cpu_label.pack(padx=20, pady=2, anchor="w")
        self.cpu_bar = ctk.CTkProgressBar(self.left_panel, width=260)
        self.cpu_bar.pack(padx=20, pady=2)
        self.cpu_bar.set(0)

        self.mem_label = ctk.CTkLabel(self.left_panel, text="MEM: 0.0%", font=("Consolas", 12))
        self.mem_label.pack(padx=20, pady=(10, 2), anchor="w")
        self.mem_bar = ctk.CTkProgressBar(self.left_panel, width=260)
        self.mem_bar.pack(padx=20, pady=2)
        self.mem_bar.set(0)

        self.agent_header = ctk.CTkLabel(self.left_panel, text="🤖 ACTIVE AGENTS", font=("Consolas", 15, "bold"), text_color="#00ffcc")
        self.agent_header.pack(padx=20, pady=(25, 5), anchor="w")

        self.console_box = ctk.CTkTextbox(self.left_panel, width=260, height=320, font=("Consolas", 10), fg_color="#1a1a1a", text_color="#00ffcc")
        self.console_box.pack(padx=20, pady=10)
        self.console_box.insert("end", "[SYS] Command Centre Online.\n[AGENT] Operations: Active\n[AGENT] Intelligence Core: Ready\n")
        self.console_box.configure(state="disabled")

        # Rechtes Panel: Command Stream & Chat
        self.right_panel = ctk.CTkFrame(self, fg_color="#181818")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.chat_frame = ctk.CTkFrame(self.right_panel, fg_color="#1e1e1e", corner_radius=8)
        self.chat_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        self.chat_display = ctk.CTkTextbox(self.chat_frame, font=("Arial", 13), fg_color="#1e1e1e", text_color="#e0e0e0")
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.chat_display.insert("end", "JARVIS: Willkommen zurück, Sir. Alle Protokolle des Command Centre sind aktiv.\n\n")
        self.chat_display.configure(state="disabled")

        # Input Frame unten rechts
        self.input_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Geben Sie einen Befehl oder eine Frage ein...", height=40, font=("Arial", 13))
        self.entry.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.entry.bind("<Return>", lambda event: self.handle_submit())

        self.send_btn = ctk.CTkButton(self.input_frame, text="EXECUTE", width=120, height=40, font=("Arial", 12, "bold"), command=self.handle_submit)
        self.send_btn.grid(row=0, column=1, sticky="e")

    def update_system_stats(self):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        self.cpu_label.configure(text=f"CPU: {cpu}%")
        self.cpu_bar.set(cpu / 100.0)
        self.mem_label.configure(text=f"MEM: {mem}%")
        self.mem_bar.set(mem / 100.0)
        self.after(1000, self.update_system_stats)

    def append_chat(self, sender, message, agent_type=""):
        self.chat_display.configure(state="normal")
        if agent_type:
            self.chat_display.insert("end", f"[{agent_type}] {sender}: {message}\n\n")
        else:
            self.chat_display.insert("end", f"{sender}: {message}\n\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def log_to_console(self, text):
        self.console_box.configure(state="normal")
        self.console_box.insert("end", f"{text}\n")
        self.console_box.see("end")
        self.console_box.configure(state="disabled")

    def handle_submit(self):
        prompt = self.entry.get().strip()
        if not prompt:
            return
        self.entry.delete(0, "end")
        self.append_chat("Sir", prompt)
        self.log_to_console(f"INPUT: {prompt[:25]}...")
        
        threading.Thread(target=self.process_async, args=(prompt,), daemon=True).start()

    def process_async(self, prompt):
        result = self.brain.ask(prompt)
        if isinstance(result, tuple) and len(result) == 2:
            response, agent_used = result
        else:
            response, agent_used = str(result), "INTELLIGENCE CORE"
        self.log_to_console(f"ROUTED -> {agent_used}")
        self.after(0, lambda: self.append_chat("JARVIS", response, agent_used))

if __name__ == "__main__":
    app = JarvisHUD()
    app.mainloop()