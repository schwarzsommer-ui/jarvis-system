import os
import subprocess
import webbrowser
import urllib.parse
from dotenv import load_dotenv

load_dotenv(override=True)

class JarvisBrain:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.client = None
        self.is_active = False
        
        if self.api_key.startswith("gsk_"):
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                self.is_active = True
            except Exception as e:
                print(f"Groq Init Error: {e}")

    def process_request(self, prompt):
        text = prompt.lower().strip()
        
        if "öffne" in text or "starte" in text:
            target = text.replace("öffne", "").replace("starte", "").strip()
            if "gmail" in target or "mail" in target:
                webbrowser.open("https://mail.google.com")
                return "Gmail wurde in deinem Browser geöffnet, Sir."
            elif "youtube" in target or "yt" in target:
                if " mit " in target:
                    parts = target.split(" mit ")
                    query = parts[1].strip()
                    webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
                    return f"YouTube-Suche nach '{query}' gestartet, Sir."
                webbrowser.open("https://www.youtube.com")
                return "YouTube wurde gestartet, Sir."
            elif "whatsapp" in target:
                webbrowser.open("https://web.whatsapp.com")
                return "WhatsApp Web wurde geladen, Sir."
            elif "spotify" in target:
                webbrowser.open("https://open.spotify.com")
                return "Spotify wurde geöffnet, Sir."
            elif "editor" in target or "notepad" in target:
                subprocess.Popen(["notepad.exe"], shell=False)
                return "Der Editor wurde gestartet, Sir."
            else:
                webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(target)}")
                return f"Web-Suche nach '{target}' ausgeführt, Sir."

        if not self.is_active or not self.client:
            return "SYSTEM ERROR: Kein gültiger Groq-API-Key konfiguriert, Sir."

        try:
            completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Du bist J.A.R.V.I.S., ein hochintelligenter, proaktiver und autonomer KI-Assistent im Stil von Tony Stark. Antworte präzise, futuristisch und auf Deutsch."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1024,
            )
            return completion.choices[0].message.content
        except Exception:
            try:
                fallback = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Du bist J.A.R.V.I.S., ein hochintelligenter KI-Assistent im Stil von Tony Stark."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1024,
                )
                return fallback.choices[0].message.content
            except Exception as inner_e:
                return f"KRITISCHER FEHLER: {str(inner_e)}"

    def ask(self, prompt):
        return self.process_request(prompt)

    def route_agent(self, prompt):
        return self.process_request(prompt), "INTELLIGENCE CORE"