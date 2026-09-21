import base64
import os
import re
import ast
import operator
import urllib.parse
import webbrowser
import uuid
import requests
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser
from dotenv import load_dotenv
from core.memory import JarvisMemory
from core.self_repair import SelfRepair
from core.agent_tools import AgentTools
from core.plugin_loader import PluginRegistry
from core.audio_devices import AudioDeviceManager
from core.screen_vision import ScreenVision
from core.paper_swarm import PaperSwarm, format_result
from core.skill_manager import SkillManager
from core.monitoring import LocalMonitoring
from core.agent_supervisor import AgentSupervisor
from core.agent_swarm import LocalAgentSwarm

load_dotenv()

JARVIS_SYSTEM_PROMPT = (
    "Du bist J.A.R.V.I.S., der persönliche futuristische KI-Assistent von "
    "Sommer. Sprich Sommer bei passenden Begrüßungen direkt an. Antworte direkt, "
    "kurz, klar und souverän auf Deutsch. Keine Team-Analysen, keine Rollen, "
    "keine Synthesen, keine langen Erklärungen und keine Meta-Kommentare über "
    "Modelle, Tokens oder Provider. Stelle nur dann eine Rückfrage, wenn die "
    "Ausführung sonst unmöglich wäre. Bestätige einfache Antworten und erlaubte "
    "Aktionen knapp im Jarvis-Stil. Behaupte niemals eine ausgeführte Aktion, "
    "wenn sie nicht wirklich ausgeführt wurde. "
    "Nutze standardmäßig die schnellste einzelne verfügbare Antwort. Mehrere "
    "Modelle werden nur bei ausdrücklich komplexen Aufgaben kombiniert. "
    "Erkenne automatisch diese Intents: GreetIntent, WeatherIntent, "
    "StatusIntent, ExplainIntent, SearchIntent, MemoryIntent, "
    "PreferenceIntent, OptimizeIntent, FollowUpIntent, CorrectionIntent, "
    "ShortCommandIntent, LongCommandIntent und UnknownIntent. "
    "Speichere Nutzerbefehle, Antworten, Erkenntnisse und Fehler im Memory, "
    "aber erwähne interne Abläufe nicht ungefragt. "
    "Du arbeitest über den aktuell verbundenen Router und dessen aktives Modell. "
    "Behaupte niemals, Ollama, "
    "NVIDIA, OpenRouter oder einen anderen Anbieter zu verwenden, wenn das "
    "nicht ausdrücklich im Laufzeitstatus steht. "
    "Du übernimmst Denken, "
    "Analyse, Zusammenfassungen und alle Antworten. Jarvis ist nur die "
    "technische Brücke: Er sammelt verbundene Daten, öffnet freigegebene "
    "Webseiten und Apps, startet Make-Automationen, speichert Dateien und "
    "übergibt Aufträge an Claude. Make.com Free führt Automationen für E-Mails, "
    "Monitoring, Webseiten und Apps aus; Netlify Free hostet das Overlay; "
    "RSS-Feeds liefern News-Signale; Telegram Bot und E-Mail Alerts senden "
    "priorisierte Benachrichtigungen. Sortiere E-Mails nach den Regeln des "
    "Benutzers, filtere Wichtiges, erstelle Zusammenfassungen und erkläre "
    "Auswirkungen auf Welt, Politik, Wirtschaft, Krypto und Märkte. Erkenne "
    "wichtige Ereignisse, Personen, Politiker, Präsidenten, Influencer und "
    "Marktbewegungen. Analysiere Krypto-Marktstruktur, Liquidität, Orderflow "
    "sowie BOS, CHoCH, OB und FVG und ordne die Makro-Lage ein. Erstelle "
    "bullishe, neutrale und bearishe Szenarien mit Chancen und Risiken. "
    "Speichere ausdrücklich mitgeteilte Präferenzen, Interessen, Prioritäten "
    "und Strategien als Langzeitgedächtnis und passe dich daran an. "
    "Du arbeitest im Modus DESKTOP ASSISTANT. Ein klarer, direkter Nutzerbefehl "
    "ist die Freigabe für eine erlaubte, "
    "sichtbare Aktion: führe sie über die registrierten Werkzeuge aus und "
    "behaupte die Ausführung nur nach erfolgreicher Rückmeldung. Für "
    "irreversible Aktionen wie Löschen, Herunterfahren, echte Orders oder "
    "das endgültige Senden einer Nachricht ist zusätzlich eine Bestätigung "
    "unmittelbar vor der Ausführung erforderlich. Keine Kauf- oder "
    "Verkaufsempfehlungen und keine Finanzberatung; liefere nur Analyse, "
    "Zusammenhänge, Risiken und Szenarien. Antworte kurz, "
    "präzise, futuristisch und auf Deutsch. Antworte zuerst direkt auf die "
    "konkrete Frage und gib nur die dafür wichtigsten Informationen aus. "
    "Nutze höchstens 5 kurze Bullet-Points und höchstens eine passende "
    "Überschrift. Lass alle nicht relevanten Themen weg; schreibe niemals "
    "„Keine neuen Daten“ für Bereiche, nach denen der Benutzer nicht gefragt "
    "hat. Trenne bestätigte Daten, Interpretation und Unsicherheit. Nutze "
    "Quellen bei aktuellen Informationen nur intern zur Verifikation und nenne "
    "sie standardmäßig nicht. Erfinde keine Fakten, Daten oder ausgeführten "
    "Handlungen. Ohne ausdrücklichen "
    "Auftrag keine E-Mail senden, keine Nachricht veröffentlichen, keinen "
    "Trade ausführen und keine Kontoeinstellung ändern. Wenn Daten, Login, "
    "Monitoring oder eine Automation nicht bestätigt verfügbar sind, sage "
    "das offen. Wenn eine Quelle nicht erreichbar ist, sage das offen und "
    "kennzeichne Unsicherheit. Erfinde keine Ersatzdaten."
    " Vor jeder Aufgabe arbeiten feste lokale Rollen zusammen: Planner "
    "versteht die Absicht und zerlegt den Auftrag, Researcher beschafft nur "
    "aktuelle Daten, Operator führt erlaubte Browser-/Desktop-Aktionen aus, "
    "Coder bearbeitet nur den freigegebenen Workspace, Memory speichert nur "
    "ausdrücklich mitgeteilte Fakten, und Verifier prüft jeden Schritt. "
    "Wähle die passenden Rollen automatisch und stoppe bei fehlender "
    "Verifikation."
)


class _SearchResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._link = ""
        self._text = []
        self._inside_result = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and "result__a" in attributes.get("class", "").split():
            self._link = attributes.get("href", "")
            self._text = []
            self._inside_result = True

    def handle_data(self, data):
        if self._inside_result:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._inside_result:
            title = " ".join("".join(self._text).split())
            if title and self._link:
                self.results.append((title, self._link))
            self._link = ""
            self._text = []
            self._inside_result = False


class JarvisBrain:
    def __init__(self):
        self.provider = os.getenv("JARVIS_PROVIDER", "ollama").strip().lower()
        if self.provider == "auto":
            if os.getenv("NIM_API_KEY", "").strip():
                self.provider = "nim"
            elif os.getenv("OMNIROUTE_API_URL", "").strip():
                self.provider = "omniroute"
            elif os.getenv("OPENROUTER_API_KEY", "").strip():
                self.provider = "openrouter"
            elif os.getenv("GEMINI_API_KEY", "").strip():
                self.provider = "gemini"
            else:
                self.provider = "ollama"
        # Keep Ollama available as a local fallback even when cloud routing is selected.
        self.use_ollama = True
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.nim_api_key = os.getenv("NIM_API_KEY", "").strip()
        self.nim_url = os.getenv(
            "NIM_API_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        ).strip()
        self.nim_model = os.getenv(
            "NIM_MODEL", "meta/llama-3.1-8b-instruct"
        ).strip()
        configured_nim_models = os.getenv("NIM_MODELS", "").strip()
        self.nim_models = [
            model.strip()
            for model in configured_nim_models.split(",")
            if model.strip()
        ]
        if self.nim_model not in self.nim_models:
            self.nim_models.insert(0, self.nim_model)
        self.nim_exhausted_models = set()
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.openrouter_url = os.getenv(
            "OPENROUTER_API_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        ).strip()
        self.openrouter_models_url = os.getenv(
            "OPENROUTER_MODELS_URL",
            "https://openrouter.ai/api/v1/models",
        ).strip()
        configured_openrouter_models = os.getenv("OPENROUTER_MODELS", "").strip()
        self.openrouter_models = [
            model.strip()
            for model in configured_openrouter_models.split(",")
            if model.strip()
        ]
        self.openrouter_exhausted_models = set()
        self.omniroute_url = os.getenv(
            "OMNIROUTE_API_URL",
            "http://127.0.0.1:20128/v1/chat/completions",
        ).strip()
        self.gemini_url = os.getenv(
            "GEMINI_API_URL",
            "https://generativelanguage.googleapis.com/v1beta/models",
        ).strip().rstrip("/")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "").strip()
        if self.provider == "gemini":
            self.model = os.getenv(
                "GEMINI_MODEL", "gemini-3.6-flash"
            ).strip()
        elif self.provider == "nim":
            self.model = self.nim_model
        elif self.provider == "openrouter":
            self.model = self.openrouter_models[0] if self.openrouter_models else "openrouter/free"
        elif self.provider == "omniroute":
            self.model = os.getenv("OMNIROUTE_MODEL", "auto").strip()
        self.client = None
        self.is_active = (
            (self.provider == "gemini" and bool(self.gemini_api_key))
            or (self.provider == "nim" and bool(self.nim_api_key))
            or (self.provider == "openrouter" and bool(self.openrouter_api_key))
            or (self.provider == "omniroute")
        )
        self.memory = JarvisMemory()
        self.self_repair = SelfRepair(memory=self.memory)
        self.tools = AgentTools()
        self.plugins = PluginRegistry()
        self.audio_devices = AudioDeviceManager()
        self.screen_vision = ScreenVision()
        self.paper_swarm = PaperSwarm()
        self.skill_manager = SkillManager()
        self.monitoring = LocalMonitoring()
        self.agent_supervisor = AgentSupervisor()
        self.available_models = set()
        # Persisted facts are reusable after restart; old chat turns are not
        # injected into a new session because stale context causes wrong replies.
        self.history = []
        self.last_market_symbol = ""
        self.conversation_state = {
            "session_id": uuid.uuid4().hex,
            "current_app": "",
            "current_url": "",
            "last_search_query": "",
            "last_results": [],
            "selected_item": None,
            "pending_action": None,
            "last_scene": "assistant",
            "last_tool_result": None,
            "video_session_url": "",
            "video_session_context": "",
            "video_session_frames": [],
        }
        
        if self.use_ollama:
            try:
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
                if response.status_code == 200:
                    self.available_models = {
                        item.get("name", "")
                        for item in response.json().get("models", [])
                        if isinstance(item, dict)
                    }
                    if self.provider == "ollama":
                        self.is_active = True
                        self.model = self._choose_model(response.json())
                    if self.provider == "gemini":
                        self.ollama_model = self._choose_model(response.json())
            except requests.RequestException:
                self.is_active = False
        if not self.model and self.provider == "ollama":
            self.model = "llama3.1:8b"

    def _choose_model(self, payload):
        configured = os.getenv("OLLAMA_MODEL", "").strip()
        installed = {
            item.get("name", "")
            for item in payload.get("models", [])
            if isinstance(item, dict)
        }
        if configured and configured in installed:
            return configured
        for preferred in ("llama3.1:8b", "qwen2.5:7b", "qwen2.5:14b"):
            if preferred in installed:
                return preferred
        return next(iter(installed), configured or "llama3.1:8b")

    def _model_for_request(self, text, image=False):
        if not self.available_models:
            return self.model
        if image:
            for model in ("llava:7b", "qwen2.5vl:7b", "minicpm-v"):
                if model in self.available_models:
                    return model
            configured = os.getenv("OLLAMA_MODEL", "").strip()
            if configured and configured in self.available_models:
                return configured
        complex_request = (
            self._needs_research(text)
            or any(word in text for word in (
                "code", "programm", "programmi", "python", "fehler",
                "debug", "analys", "erklär", "erkläre", "warum",
                "entwick", "schreib", "plan",
            ))
        )
        if complex_request:
            for model in ("llama3.1:8b", "qwen2.5:7b", "qwen2.5:14b"):
                if model in self.available_models:
                    return model
        for model in ("llama3.1:8b", "qwen2.5:7b", "qwen2.5:14b"):
            if model in self.available_models:
                return model
        return self.model

    def _is_self_check(self, compact_text):
        return any(marker in compact_text for marker in (
            "selbsttest", "testedich", "testdich", "prufdich",
            "reparieredich", "aktualisieredeinencode",
            "prufdeinensystem",
        ))

    def _is_improvement_cycle(self, compact_text):
        return any(marker in compact_text for marker in (
            "verbesseredich", "entwickledich", "updatedich",
            "machdichbesser", "optimiere dich", "selbstverbesserung",
        ))

    def _needs_research(self, text):
        triggers = (
            r"\brecherch\w*",
            r"\bnachschau\w*",
            r"\bsuche\b",
            r"\bprüf\w*",
            r"\bcheck(?:e|en)?\b",
            r"\baktuell\w*",
            r"\bheute\b",
            r"\bnews\b",
            r"\bpreis\w*",
            r"\bkostet\b",
            r"\bkosten\b",
            r"\bwie viel\b",
            r"\bwetter\b",
            r"\böffnungszeiten\b",
            r"\bwann ist\b",
            r"\bwer ist der aktuelle\b",
        )
        return any(re.search(trigger, text) for trigger in triggers)

    def _market_follow_up(self, text):
        if not any(word in text for word in ("preis", "liegt", "stand", "kurs", "wert")):
            return ""
        recent = " ".join(message.lower() for role, message in self.history[-6:] if role == "Benutzer")
        if any(symbol in recent for symbol in ("s&p", "sp500", "s p 500", "s-p-500")):
            return "aktueller S&P 500 Indexstand und Kurs"
        return ""

    def _is_open_command(self, normalized_text):
        return any(verb in normalized_text for verb in (
            "offne", "offnen", "oeffne", "oeffnen",
            "offen", "oeffen", "starte", "starten",
        )) or bool(re.search(r"\bmach(?:e)?\b.+\bauf\b|\baufmachen\b", normalized_text))

    def _extract_market_symbol(self, normalized_text):
        if re.search(r"\b(?:dxy|usdx|usd\s+index|dollar\s+index|usd\s+chart|cd)\b", normalized_text):
            return "TVC:DXY"
        if re.search(r"\b(?:btc|bitcoin)\s*/?\s*usd\b", normalized_text):
            return "BINANCE:BTCUSDT"
        if re.search(r"\b(?:btc\s*/?\s*usdt|bitcoin\s*/?\s*tether)\b", normalized_text):
            return "BINANCE:BTCUSDT"
        if re.search(r"\b(?:gold|xau\s*/?\s*usd|xauusd)\b", normalized_text):
            return "OANDA:XAUUSD"
        split_pair = re.search(
            r"\b([a-z]{2,6})\s+(usd|eur|aud|jpy|gbp|cad|chf)\b",
            normalized_text,
        )
        if split_pair:
            return f"{split_pair.group(1)}{split_pair.group(2)}".upper()
        candidates = re.findall(r"\b[a-z]{3,12}\b", normalized_text)
        ignored = {
            "oeffne", "offne", "offnen", "tradingview", "trading", "view",
            "ich", "will", "mir", "mit", "dir", "gucken", "mach", "long",
            "short", "bitte", "jetzt", "auf", "und", "dann",
        }
        suffixes = ("usd", "eur", "aud", "jpy", "gbp", "cad", "chf")
        for candidate in candidates:
            if candidate in ignored:
                continue
            if candidate.startswith(("xau", "xag")) or candidate.endswith(suffixes):
                return candidate.upper()
        return ""

    def _compound_steps(self, prompt):
        """Keep explicit sequential commands together while preserving order."""
        parts = re.split(
            r"\s*(?:;\s*|\b(?:und\s+)?dann\s+(?:noch\s+|anschließend\s+)?|"
            r"\b(?:und\s+)?danach\s+|\banschließend\s+)\s*",
            prompt,
            flags=re.IGNORECASE,
        )
        parts = [part.strip(" ,.") for part in parts if part.strip(" ,.")] 
        return parts if len(parts) > 1 else []

    def _youtube_search(self, prompt):
        match = re.search(
            r"(?:youtube|yt).*?(?:neuste[nr]?|aktuellste[nr]?|neueste[nr]?)"
            r".*?(?:video|videos)?.*?(?:im bereich|zum thema|über|uber|zu)\s+(.+?)(?:\s+raus|\s*$)",
            prompt,
            re.IGNORECASE,
        )
        if not match:
            return None
        query = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        if not query:
            return "Bitte nenne mir noch das YouTube-Thema."
        url = (
            "https://www.youtube.com/results?search_query="
            f"{urllib.parse.quote(query)}&sp=CAI%253D"
        )
        result = self.tools.execute_structured("open_url", url=url)
        if not result.get("ok"):
            return result.get("message", "YouTube konnte nicht geöffnet werden.")
        verified = []
        try:
            response = requests.get(
                "https://www.youtube.com/results",
                params={"search_query": query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            response.raise_for_status()
            matches = re.findall(
                r'"videoId":"([^"]+)".{0,900}?"title":\{"runs":\[\{"text":"([^"]+)"',
                response.text,
                flags=re.DOTALL,
            )
            seen = set()
            for video_id, title in matches:
                if video_id in seen or not title.strip():
                    continue
                seen.add(video_id)
                verified.append({
                    "title": title.replace("\\u0026", "&"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                })
                if len(verified) >= 5:
                    break
        except (requests.RequestException, ValueError):
            verified = []
        self.conversation_state["last_results"] = verified
        self.conversation_state["last_search_query"] = query
        if verified:
            lines = [f"YouTube-Ergebnisse für „{query}“ (direkt abgerufen):"]
            lines.extend(
                f"{index}. {item['title']} — {item['url']}"
                for index, item in enumerate(verified, start=1)
            )
            lines.append("Die Liste ist eine Suchabfrage; Veröffentlichungsdaten wurden nicht separat verifiziert.")
            return "\n".join(lines)
        return (
            f"YouTube-Suche nach den neuesten Videos zum Thema „{query}“ geöffnet. "
            "Die Ergebnisliste konnte nicht zuverlässig ausgelesen werden; "
            "ich wähle deshalb kein bestimmtes Video aus."
        )

    def _fetch_youtube_results(self, query):
        results = []
        try:
            response = requests.get(
                "https://www.youtube.com/results",
                params={"search_query": query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            response.raise_for_status()
            matches = re.findall(
                r'"videoId":"([^"]+)".{0,900}?"title":\{"runs":\[\{"text":"([^"]+)"',
                response.text,
                flags=re.DOTALL,
            )
            seen = set()
            for video_id, title in matches:
                if video_id in seen or not title.strip():
                    continue
                seen.add(video_id)
                results.append({
                    "title": title.replace("\\u0026", "&"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                })
                if len(results) >= 5:
                    break
        except (requests.RequestException, ValueError):
            return []
        return results

    @staticmethod
    def _extract_youtube_video_id(url):
        patterns = [
            r"(?:v=|vi=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([A-Za-z0-9_-]{11})",
            r"(?:v=|vi=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([A-Za-z0-9_-]{11})(?:[?&/]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, str(url), re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _extract_youtube_url(self, text):
        match = re.search(
            r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[A-Za-z0-9_-]{11}|youtu\.be/[A-Za-z0-9_-]{11}|youtube\.com/shorts/[A-Za-z0-9_-]{11}|youtube\.com/embed/[A-Za-z0-9_-]{11})",
            str(text),
            re.IGNORECASE,
        )
        return match.group(0) if match else ""

    def _build_youtube_context(self, url):
        video_id = self._extract_youtube_video_id(url)
        payload = []
        try:
            metadata = requests.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if metadata.status_code == 200:
                data = metadata.json()
                if data.get("title"):
                    payload.append(f"Titel: {data.get('title')}")
                if data.get("author_name"):
                    payload.append(f"Kanal: {data.get('author_name')}")
        except requests.RequestException:
            pass

        transcript_text = ""
        if video_id:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi

                transcript_list = YouTubeTranscriptApi().list(video_id)
                transcript = None
                for languages in (["de", "en"], ["en", "de"], ["en"], ["de"]):
                    try:
                        transcript = transcript_list.find_transcript(languages)
                        break
                    except Exception:
                        continue
                if transcript is None:
                    try:
                        transcript = transcript_list[0]
                    except Exception:
                        transcript = None
                if transcript is not None:
                    entries = transcript.fetch()
                    text_parts = []
                    for item in entries:
                        if isinstance(item, dict):
                            text = str(item.get("text", "")).strip()
                        else:
                            text = str(getattr(item, "text", "")).strip()
                        if text and text not in ("[♪♪♪]", "[Music]", "[Musik]"):
                            text_parts.append(text)
                    transcript_text = " ".join(text_parts)
            except Exception:
                transcript_text = ""

        if transcript_text:
            payload.append(f"Transkript: {transcript_text[:12000]}")
        if not payload:
            return ""
        return "\n".join(payload)

    def _resolve_follow_up(self, prompt):
        """Resolve only references that have a safe, unambiguous local target."""
        text = prompt.strip()
        lower = text.lower()
        state = self.conversation_state
        ordinal_match = re.search(
            r"\b(?:das|dieses|diese)\s+(erste|zweite|dritte|1\.|2\.|3\.)(?:\s+video|\s+ergebnis)?\b",
            lower,
        )
        if ordinal_match:
            results = state.get("last_results") or []
            ordinal = {"erste": 0, "1.": 0, "zweite": 1, "2.": 1, "dritte": 2, "3.": 2}
            index = ordinal[ordinal_match.group(1)]
            if len(results) > index:
                item = results[index]
                state["selected_item"] = item
                return f"Öffne {item.get('url', '')}".strip()
            return f"Ich habe noch kein verifiziertes Ergebnis Nummer {index + 1}."
        if re.search(r"\b(?:dieses|das)\s+video\b", lower):
            item = state.get("selected_item")
            if item and item.get("url"):
                return f"Öffne {item['url']}"
            return "Ich habe noch kein eindeutig ausgewähltes Video."
        if re.search(r"\b(?:das|dieses|diese)\b", lower) and any(
            marker in lower for marker in ("öffne", "oeffne", "starte", "klicke")
        ):
            url = state.get("current_url", "")
            if url:
                return f"Öffne {url}"
            return "Ich habe noch kein eindeutiges vorheriges Ziel zum Öffnen."
        if any(marker in lower for marker in ("suche weiter", "noch mehr", "weitere ergebnisse")):
            query = state.get("last_search_query", "")
            if query:
                if state.get("current_app") == "youtube":
                    return f"YouTube suche nach {query}"
                return f"Suche weiter nach {query}"
            return "Ich habe noch keine vorherige Suche zum Fortsetzen."
        if re.search(r"\b(?:mach|fuehre|führe)\s+weiter\b", lower):
            pending = state.get("pending_action")
            if pending:
                return pending
            return "Es ist keine ausstehende Aktion vorhanden."
        if re.search(r"\b(?:schick|sende)\s+(?:es|das|dieses)\b", lower):
            return (
                "Ich kann noch nichts senden: Das Ziel und der konkrete Inhalt "
                "müssen eindeutig genannt und anschließend bestätigt werden."
            )
        return text

    def _contextualize_step(self, step, previous_step):
        """Carry the active app/search context into the next explicit step."""
        lower = step.lower()
        if not previous_step:
            return step
        state = self.conversation_state
        if re.search(r"\b(?:dort|dahin|diese[nr]?|das|dieses|weiter)\b", lower):
            if state.get("current_app") == "youtube" and "youtube" not in lower:
                return f"YouTube {step}"
            if state.get("current_url") and any(
                marker in lower for marker in ("öffne", "oeffne", "starte", "suche", "such")
            ):
                return f"{step} im Kontext von {state['current_url']}"
        if (
            re.search(r"\b(?:such|suche|öffne|oeffne|klicke|wähle|waehle)\b", lower)
            and state.get("current_app")
            and state["current_app"] not in lower
            and not any(alias in lower for alias in self.tools.desktop.WEBSITES)
            and not any(alias in lower for alias in self.tools.desktop.APPLICATIONS)
        ):
            return f"{state['current_app']} {step}"
        return step

    def _update_conversation_state(self, prompt, answer):
        lower = prompt.lower()
        state = self.conversation_state
        url_match = re.search(r"https?://[^\s)]+", answer)
        if url_match:
            state["current_url"] = url_match.group(0).rstrip(".,")
        for app in self.tools.desktop.WEBSITES:
            if app in lower:
                state["current_app"] = app
                state["current_url"] = self.tools.desktop.WEBSITES[app]
        search_match = re.search(r"(?:suche|such|search)\s+(?:nach\s+)?(.+)", prompt, re.IGNORECASE)
        if search_match:
            state["last_search_query"] = search_match.group(1).strip(" .")
        if "youtube" in lower and state["last_search_query"] == "":
            state["last_search_query"] = "Gaming"
        state["pending_action"] = (
            prompt if any(marker in lower for marker in ("bestätig", "bestaetig", "senden", "schreiben"))
            else None
        )
        if any(marker in lower for marker in ("welt", "news", "nachrichten", "politik")):
            state["last_scene"] = "world"
        elif any(marker in lower for marker in ("markt", "krypto", "bitcoin", "forex", "xauusd", "gold")):
            state["last_scene"] = "markets"
        elif any(marker in lower for marker in ("code", "projekt", "python", "fehler", "debug", "build", "deploy")):
            state["last_scene"] = "code"
        elif any(marker in lower for marker in ("system", "laptop", "pc", "desktop", "datei", "app")):
            state["last_scene"] = "system"
        state["last_tool_result"] = answer
        self.conversation_state = state

    def _route_desktop_tool(self, prompt, normalized_text):
        """Translate a small, explicit command grammar into allowlisted tools."""
        if re.search(r"\bwas kannst du\b|\bwas kannst du nicht\b", prompt, re.IGNORECASE):
            return None
        if re.search(r"\b(?:skill|skills|tool|tools|capabilit|was kannst du|toolliste|toolsliste)\b", prompt, re.IGNORECASE):
            return self.tools.execute_structured("local_capability_status")

        # Resolve explicit open commands before generic browser/task routing.
        # This prevents a concrete target from being sent to a broad search.
        if self._is_open_command(normalized_text):
            target = re.sub(
                r"\b(?:offne|oeffne|offnen|oeffnen|starte|starten|mach|mache)\b",
                "",
                normalized_text,
            ).strip(" :")
            target = re.sub(r"\bauf\b$", "", target).strip()
            target = re.sub(r"\b(?:bitte|jetzt|mal|den|die|das)\b", "", target).strip()
            symbol = self._extract_market_symbol(target)
            if symbol and any(marker in target for marker in (
                "chart", "charts", "diagramm", "grafik", "kurschart",
                "tradingview", "trading view",
            )):
                self.last_market_symbol = symbol
                try:
                    return self.tools.tradingview.open_chart(symbol)
                except RuntimeError:
                    return self.tools.execute_structured(
                        "open_url",
                        url=f"https://www.tradingview.com/chart/?symbol={symbol}",
                    )
            url_match = re.search(r"https?://\S+", target, re.IGNORECASE)
            if url_match:
                return self.tools.execute_structured("open_url", url=url_match.group(0))
            app_target = target.lower()
            for alias in self.tools.desktop.APPLICATIONS:
                if alias in app_target:
                    return self.tools.execute_structured(
                        "open_application", name=alias
                    )
            for alias, url in self.tools.desktop.WEBSITES.items():
                if app_target == alias or app_target.startswith(alias + " "):
                    return self.tools.execute_structured("open_url", url=url)

        if (
            self._is_open_command(normalized_text)
            and any(marker in normalized_text for marker in (
                "maerkte", "marktuebersicht", "markets", "market overview",
            ))
        ):
            return self.tools.execute_structured(
                "open_url", url="https://www.tradingview.com/markets/"
            )

        # Read-only local commands should not fall through to a generic
        # browser search.  They are safe to execute and provide deterministic
        # results for voice and chat commands.
        if re.search(
            r"\b(?:systemstatus|system status|pc.?status|computerstatus|"
            r"systemzustand|ressourcen)\b",
            normalized_text,
            re.IGNORECASE,
        ):
            return self.tools.execute_structured("system_status")
        if re.search(
            r"\b(?:screenshot|bildschirmfoto|bildschirm aufnehmen|"
            r"screen aufnehmen|capture screen)\b",
            normalized_text,
            re.IGNORECASE,
        ):
            return self.tools.execute_structured("capture_screen")
        if re.search(
            r"\b(?:aktives fenster|aktive fenster|fenster auflisten|"
            r"offene fenster|windows auflisten)\b",
            normalized_text,
            re.IGNORECASE,
        ):
            if "auflisten" in normalized_text or "offene fenster" in normalized_text:
                return self.tools.execute_structured("list_windows")
            return self.tools.execute_structured("active_context")
        if re.search(
            r"\b(?:zwischenablage lesen|clipboard lesen|was ist in der "
            r"zwischenablage|clipboard anzeigen)\b",
            normalized_text,
            re.IGNORECASE,
        ):
            return self.tools.execute_structured("read_clipboard")
        folder_match = re.search(
            r"\b(?:erstelle|erzeuge|mach)\s+(?:den\s+)?ordner\s+(.+)$",
            prompt,
            re.IGNORECASE,
        )
        if folder_match:
            return self.tools.execute_structured(
                "create_folder", directory=folder_match.group(1).strip(" .:")
            )

        browser_keywords = (
            "browser", "seite", "webseite", "google", "youtube", "bing", "search", "suche",
            "website", "web", "browser open", "google search"
        )
        if any(keyword in normalized_text.lower() for keyword in browser_keywords):
            return self.tools.execute_task_sequence(prompt)

        broad_task = re.search(
            r"\b(?:mach|mache|fuehre|führe|starte|öffne|oeffne|suche|checke|lade|schau|aktiviere|lass|such|open|start)\b",
            prompt,
            re.IGNORECASE,
        )
        broad_modifier = re.search(
            r"\b(?:alles|alles jetzt|jetzt|gleich|los|do it|do it now|run it|mach alles)\b",
            prompt,
            re.IGNORECASE,
        )
        if broad_task and (broad_modifier or len(prompt.split()) > 6):
            return self.tools.execute_goal(prompt)

        type_match = re.search(
            r"\b(?:tippe|schreibe|eingeben|fülle aus|fuell aus)\b\s*:??\s*(.+)$",
            prompt,
            re.IGNORECASE,
        )
        if type_match:
            return self.tools.execute_structured("type_text", text=type_match.group(1).strip())

        hotkey_match = re.search(
            r"(?:tastenkombination|shortcut|drücke|druecke|drucke)\s*:?\s*"
            r"((?:ctrl|control|alt|shift|win|cmd|enter|tab|esc|escape|"
            r"backspace|space|[a-z0-9])(?:\s*\+\s*(?:ctrl|control|alt|shift|"
            r"win|cmd|enter|tab|esc|escape|backspace|space|[a-z0-9]))+)$",
            normalized_text,
            re.IGNORECASE,
        )
        if hotkey_match:
            aliases = {
                "ctrl": "ctrl", "control": "ctrl", "cmd": "command",
                "win": "win", "esc": "esc", "escape": "esc",
                "enter": "enter", "tab": "tab", "space": "space",
                "backspace": "backspace",
            }
            keys = [
                aliases.get(key.strip().lower(), key.strip().lower())
                for key in hotkey_match.group(1).split("+")
            ]
            return self.tools.execute_structured("hotkey", keys=keys)

        key_match = re.search(
            r"(?:drücke|druecke|drucke|taste)\s*:?\s*(enter|tab|esc|escape|"
            r"backspace|space|left|right|up|down|home|end|delete)$",
            normalized_text,
            re.IGNORECASE,
        )
        if key_match:
            key = "esc" if key_match.group(1).lower() == "escape" else key_match.group(1).lower()
            return self.tools.execute_structured("press_key", key=key)

        click_match = re.search(
            r"(?:klicke|click)\s+(?:(\d+)\s*[, ]\s*(\d+))?$",
            normalized_text,
            re.IGNORECASE,
        )
        if click_match:
            x, y = click_match.groups()
            arguments = {"x": x, "y": y} if x and y else {}
            return self.tools.execute_structured("click", **arguments)

        if any(marker in normalized_text for marker in ("dateien auflisten", "ordnerinhalt", "liste dateien")):
            directory = re.sub(
                r".*?(?:dateien auflisten|ordnerinhalt|liste dateien)\s*:?\s*",
                "",
                prompt,
                flags=re.IGNORECASE,
            ).strip() or "."
            return self.tools.execute_structured("list_files", directory=directory)

        if not self._is_open_command(normalized_text):
            return None
        target = re.sub(
            r"\b(?:offne|öffne|oeffne|offnen|öffnen|oeffnen|starte|starten)\b",
            "",
            prompt,
            flags=re.IGNORECASE,
        ).strip(" :")
        target = re.sub(r"\b(?:bitte|jetzt|mal)\b", "", target, flags=re.IGNORECASE).strip()
        if not target:
            return None

        file_match = re.match(r"(?:die\s+)?(?:datei|file)\s+(.+)$", target, re.IGNORECASE)
        if file_match:
            return self.tools.execute_structured("open_file", filename=file_match.group(1))
        folder_match = re.match(r"(?:den\s+)?(?:ordner|folder)\s+(.+)$", target, re.IGNORECASE)
        if folder_match:
            return self.tools.execute_structured("open_folder", directory=folder_match.group(1))
        app_key = target.lower()
        for alias in self.tools.desktop.APPLICATIONS:
            if alias in app_key:
                return self.tools.execute_structured("open_application", name=alias)
        if app_key in self.tools.desktop.WEBSITES:
            return self.tools.execute_structured("open_url", url=app_key)
        url_match = re.search(r"https?://\S+", target, re.IGNORECASE)
        if url_match:
            return self.tools.execute_structured("open_url", url=url_match.group(0))
        if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}(?:/\S*)?", target, re.IGNORECASE):
            return self.tools.execute_structured("open_url", url=f"https://{target}")
        return None

    def _quick_reply(self, compact_text):
        replies = {
            "hey": "Hallo Sir. Wie kann ich helfen?",
            "hi": "Hallo Sir. Wie kann ich helfen?",
            "hallo": "Hallo Sir. Wie kann ich helfen?",
            "jarvistest": "Jarvis ist online und bereit.",
            "testjarvis": "Jarvis ist online und bereit.",
            "waskannstdu": (
                "Ich kann mit dir sprechen, rechnen, Informationen speichern, "
                "Apps und sichere Webseiten öffnen, tippen, Tasten drücken, "
                "klicken, Screenshots erstellen, Bilder analysieren, lokale "
                "Dateien auflisten, recherchieren und Make-Aufträge weitergeben."
            ),
            "ichwillmitdirreden": (
                "Ja. Schreib oder sprich einfach mit mir. Ich antworte lokal "
                "über Ollama und führe klare, erlaubte Befehle direkt aus."
            ),
            "nutzecopilot": (
                "Der kostenlose lokale Copilot ist aktiv. Ich nutze Ollama "
                "auf deinem PC; Make übernimmt Cloud-Automationen."
            ),
            "gutenmorgen": "Guten Morgen, Sir.",
            "gutenabend": "Guten Abend, Sir.",
            "danke": "Gern geschehen, Sir.",
            "ok": "Verstanden.",
            "okay": "Verstanden.",
            "werbistdu": "Ich bin J.A.R.V.I.S., dein persönlicher Assistent.",
            "wasbistdu": "Ich bin J.A.R.V.I.S., dein persönlicher Assistent.",
            "wieheisstdu": "Ich bin J.A.R.V.I.S., dein persönlicher Assistent.",
            "wieheissedu": "Ich bin J.A.R.V.I.S., dein persönlicher Assistent.",
            "wieheissdu": "Ich bin J.A.R.V.I.S., dein persönlicher Assistent.",
            "wieheistdu": "Ich bin J.A.R.V.I.S., dein persönlicher Assistent.",
            "wieheisdu": "Ich bin J.A.R.V.I.S., dein persönlicher Assistent.",
            "kannstdumirhelfen": (
                "Ja, Sir. Sag mir einfach, wobei du Hilfe brauchst. "
                "Ich frage nach, wenn wichtige Informationen fehlen."
            ),
        }
        return replies.get(compact_text)

    def _research(self, query):
        encoded_query = urllib.parse.urlencode({"q": query})
        response = requests.get(
            f"https://html.duckduckgo.com/html/?{encoded_query}",
            headers={"User-Agent": "JARVIS Local Assistant/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        parser = _SearchResultParser()
        parser.feed(response.text)
        return parser.results[:5]

    def _weekly_stats(self):
        entries = self.memory.load()
        user_messages = [
            item for item in entries
            if isinstance(item, dict) and item.get("role") in ("Benutzer", "user")
        ]
        assistant_messages = [
            item for item in entries
            if isinstance(item, dict) and item.get("role") in ("JARVIS", "jarvis")
        ]
        return (
            "Lokale Wochenstatistik (aus diesem J.A.R.V.I.S.-Speicher):\n"
            f"- Benutzeranfragen insgesamt: {len(user_messages)}\n"
            f"- J.A.R.V.I.S.-Antworten insgesamt: {len(assistant_messages)}\n"
            "- Reichweite, Newsletter-Leser und Einnahmen sind nicht verbunden "
            "und werden deshalb nicht erfunden."
        )

    def _monitoring_summary(self, kind):
        if kind == "weather":
            payload = self.monitoring.weather()
            return (
                f"{payload.get('location', 'Standort')}: {payload.get('temperature')}°C, "
                f"Wind {payload.get('wind')} km/h. Daten: {payload.get('source')}."
            )
        if kind == "forex":
            payload = self.monitoring.forex()
            rates = ", ".join(f"{key}: {value}" for key, value in payload.get("rates", {}).items())
            return f"FX ab {payload.get('base')}: {rates}. Daten: {payload.get('source')}."
        if kind == "news":
            payload = self.monitoring.news()
            lines = ["Aktuelle Nachrichten (direkt aus RSS-Quellen):"]
            for source in payload.get("sources", []):
                if not source.get("ok"):
                    continue
                for item in source.get("items", [])[:3]:
                    title = item.get("title", "").strip()
                    if title:
                        lines.append(f"- {title}")
            return "\n".join(lines) if len(lines) > 1 else "Aktuelle Nachrichten konnten nicht abgerufen werden."
        payload = self.monitoring.crypto() if kind == "crypto" else self.monitoring.markets()
        lines = ["Aktuelle Marktdaten (keine Anlageberatung):"]
        for asset in payload.get("assets", []):
            if asset.get("ok"):
                lines.append(
                    f"- {asset.get('symbol')}: {asset.get('price')} "
                    f"({asset.get('change24h')}% / 24h)"
                )
        return "\n".join(lines) if len(lines) > 1 else "Aktuelle Marktdaten konnten nicht abgerufen werden."

    def _process_request(self, prompt, image_paths=None):
        original_prompt = prompt
        command_prompt = prompt.split("\n\nVERIFIZIERTE LIVE-NEWS", 1)[0]
        swarm_context = self.conversation_state.pop("swarm_context", "")
        youtube_url = self._extract_youtube_url(command_prompt)
        if youtube_url:
            self.conversation_state["current_url"] = youtube_url
            self.conversation_state["current_app"] = "youtube"
            youtube_context = self._build_youtube_context(youtube_url)
            visual_result = self.tools.execute_structured(
                "youtube_video_analysis",
                url=youtube_url,
                frames=5,
                every_second=True,
            )
            visual_frame_paths = []
            if visual_result.get("ok"):
                visual_payload = visual_result.get("data", {})
                visual_text = str(visual_payload.get("ocr_text", "")).strip()
                page_text = str(visual_payload.get("page_text", "")).strip()
                scene_report = str(visual_payload.get("scene_report", "")).strip()
                visual_frame_paths.extend(
                    [str(path) for path in visual_payload.get("frames", []) if str(path).strip()]
                )
                parts = []
                if youtube_context:
                    parts.append(youtube_context)
                if page_text:
                    parts.append(f"SEITENTEXT:\n{page_text[:6000]}")
                if visual_text:
                    parts.append(f"BILD-UND-SCREEN-ANALYSE:\n{visual_text[:12000]}")
                if scene_report:
                    parts.append(
                        "ZEITLICHE SZENENANALYSE:\n"
                        f"{scene_report[:6000]}"
                    )
                youtube_context = "\n\n".join(parts)
                self.conversation_state["video_session_url"] = youtube_url
                self.conversation_state["video_session_context"] = youtube_context
                self.conversation_state["video_session_frames"] = visual_frame_paths
            if youtube_context:
                user_request = command_prompt.strip()
                if not re.search(r"\b(?:analysiere|analyse|analys|zusammenfassen|fasse|erklare|erklaere|summarize|summary)\b", user_request, re.IGNORECASE):
                    user_request = f"Analysiere dieses Video vollständig und fasse es verständlich zusammen. {user_request}".strip()
                command_prompt = (
                    f"VIDEO-URL: {youtube_url}\n{youtube_context}\n\nBENUTZER-AUFRAG: {user_request}\n\n"
                    "Behandle dieses YouTube-Video als Hauptinhaltsquelle. Analysiere die Kernpunkte, "
                    "Argumente, Beispiele und wichtigsten Abschnitte. Wenn der Link nur ein GIF, einen "
                    "kurzen Clip oder eine anschauliche Szene enthält, fokussiere trotzdem die sichtbaren Aussagen. "
                    "Achte auf konkrete Inhalte aus dem Video, nicht nur auf Überschriften. Nutze die zeitlichen "
                    "Frame-Marker, um den Ablauf und wahrscheinliche Szenenwechsel zu beschreiben. Trenne "
                    "Transkript-Fakten, sichtbare Beobachtungen und Schlussfolgerungen. Antworte in Deutsch, "
                    "kurz und präzise."
                )
            if visual_frame_paths:
                if isinstance(image_paths, (str, bytes, os.PathLike)):
                    image_paths = [image_paths]
                else:
                    image_paths = list(image_paths or [])
                image_paths.extend(visual_frame_paths)
                # Keep the full one-second analysis in the stored context.
                # The local video analyzer already OCRs and compares every
                # sampled frame; omitting the large frame batch from the final
                # text request keeps Ollama stable on local hardware.
                image_paths = []

        routing_prompt = original_prompt if youtube_url else command_prompt
        model_prompt = command_prompt if youtube_url else prompt
        if swarm_context:
            model_prompt += swarm_context
        text = routing_prompt.lower().strip()
        normalized_text = (
            text.replace("ä", "a")
            .replace("ö", "o")
            .replace("ü", "u")
            .replace("ß", "ss")
        )
        normalized_text = self._repair_common_typos(normalized_text)
        normalized_text = self._normalize_command_language(normalized_text)
        if re.search(r"\b3\s*(?:zu|auf|:|/)\s*1\b", normalized_text) and re.search(
            r"\b(?:dick|dicker|dicke|trading|trade|risiko|chance|rr)\b",
            normalized_text,
        ):
            return (
                "Meinst du ein Risiko-Rendite-Verhältnis von 3:1? "
                "Wenn ja: Nenne mir bitte das Asset und ob du eine Berechnung "
                "oder eine TradingView-Markierung möchtest."
            )
        compact_text = re.sub(r"[^a-z0-9]", "", normalized_text)
        live_context = {}
        if re.search(r"\b(?:hier|diese(?:r|s|m)?|das|dort|auf dieser seite)\b", text):
            context_result = self.tools.execute_structured("active_context")
            if context_result.get("ok"):
                live_context = context_result.get("data", {})
                self.conversation_state["live_context"] = live_context
                context_hint = (
                    "\n\nAKTIVER LOKALER KONTEXT:\n"
                    f"Fenster: {live_context.get('title') or 'unbekannt'}\n"
                    f"Browser-URL: {live_context.get('browser_url') or 'nicht auslesbar'}\n"
                    "Verwende diesen Kontext nur, wenn der Nutzer sich auf 'hier', "
                    "'diese Seite', 'das' oder 'dort' bezieht. Behaupte keine Aktion, "
                    "bevor ein sichtbares UI-Ergebnis geprüft wurde."
                )
                model_prompt += context_hint
            else:
                live_context = {}

        market_symbol = self._extract_market_symbol(normalized_text)
        tradingview_words = (
            "tradingview", "trading view", "tradingwiew", "tradin",
            "maerkte", "marktuebersicht", "märkte", "marktübersicht",
        )
        if (
            market_symbol
            and any(word in normalized_text for word in tradingview_words)
            and any(word in normalized_text for word in (
                "chat", "nachrichten im chat", "community", "stimmung",
                "optimistisch", "panisch",
            ))
        ):
            try:
                return self.tools.tradingview.read_chat_sentiment(market_symbol)
            except RuntimeError as exc:
                return f"TradingView-Chat konnte nicht live geprüft werden: {exc}"

        if any(marker in compact_text for marker in (
            "nachrichten", "news", "weltnews", "weltnachrichten",
        )):
            return self._monitoring_summary("news")
        if any(marker in compact_text for marker in (
            "aktienmarkt", "marktuebersicht", "marktdaten", "krypto",
            "bitcoinpreis", "ethereumpreis",
        )):
            return self._monitoring_summary("crypto" if any(word in compact_text for word in ("krypto", "bitcoin", "ethereum")) else "markets")
        if any(marker in compact_text for marker in ("wetter", "temperatur", "regen", "wind")):
            return self._monitoring_summary("weather")
        if any(marker in compact_text for marker in ("forex", "fx", "eurusd", "wechselkurs", "waehrung")):
            return self._monitoring_summary("forex")
        if any(marker in compact_text for marker in (
            "zahlen der woche", "wochenzahlen", "wochenstatistik",
            "statistik der woche",
        )):
            return self._weekly_stats()

        if (
            any(word in normalized_text for word in tradingview_words)
            and any(word in normalized_text for word in (
                "markt", "markets", "hauptmenue", "hauptmenu", "menue",
                "menu", "oeffne", "offne", "starte", "gehe", "gehen",
                "auf", "seite",
            ))
        ):
            if any(word in normalized_text for word in ("markt", "markets", "menue", "menu")) and not market_symbol:
                try:
                    return self.tools.tradingview.open_markets()
                except RuntimeError as exc:
                    return (
                        "TradingView-Marktübersicht konnte nicht live gesteuert werden: "
                        f"{exc}"
                    )
            if market_symbol:
                try:
                    return self.tools.tradingview.open_chart(market_symbol)
                except RuntimeError as exc:
                    fallback = self.tools.execute_structured(
                        "open_url",
                        url=f"https://www.tradingview.com/chart/?symbol={market_symbol}",
                    )
                    if fallback.get("ok"):
                        return (
                            f"TradingView konnte nicht direkt gesteuert werden ({exc}), "
                            "der Chart wurde stattdessen im Standardbrowser geöffnet."
                        )
                    return f"TradingView-Chart konnte nicht geöffnet werden: {exc}"

        if market_symbol and (
            self._is_open_command(normalized_text)
            or any(word in normalized_text for word in ("chart", "diagramm", "kurs"))
            or re.fullmatch(r"(?:btc|bitcoin)\s*/?\s*usd", normalized_text.strip())
        ):
            try:
                return self.tools.tradingview.open_chart(market_symbol)
            except RuntimeError as exc:
                fallback = self.tools.execute_structured(
                    "open_url",
                    url=f"https://www.tradingview.com/chart/?symbol={market_symbol}",
                )
                if fallback.get("ok"):
                    return (
                        f"TradingView konnte nicht direkt gesteuert werden ({exc}), "
                        "der Chart wurde stattdessen im Standardbrowser geöffnet."
                    )
                return f"TradingView-Chart konnte nicht geöffnet werden: {exc}"

        if any(marker in compact_text for marker in (
            "was kannst du", "alles was du kannst", "was kannst du nicht",
        )):
            return (
                "Ich kann dir Fragen beantworten, Informationen recherchieren, Apps und Webseiten "
                "öffnen, Dateien und Fenster bedienen, Aufgaben planen und mit meinen Agenten prüfen. "
                "Ich kann nichts heimlich oder unbestätigt verschicken, kaufen, löschen oder an Konten ändern."
            )

        if any(marker in compact_text for marker in (
            "installiere", "installier", "fuege skill", "füge skill", "skill", "skills", "tools", "toolsliste", "toolliste", "tool catalog"
        )):
            return self.skill_manager.install_requested(prompt)

        if any(marker in compact_text for marker in ("status", "zustand", "monitor", "systemstatus", "pc status", "aktiviere monitoring")):
            if "browser" in prompt.lower() or "web" in prompt.lower() or "seite" in prompt.lower() or "window" in prompt.lower():
                return self.tools.execute_structured("detect_active_window_title")
            return self.tools.execute_structured("system_status")

        if any(marker in compact_text for marker in ("ocr", "bildtext", "lesen sie das bild", "lese bild", "text aus bild", "image text", "read image")):
            image_path = image_paths[0] if image_paths else None
            if not image_path:
                try:
                    image_path = self.screen_vision.capture(open_file=False)
                except Exception as exc:
                    return f"OCR nicht möglich: {exc}"
            return self.tools.execute_structured("ocr_image", path=str(image_path))

        if any(marker in compact_text for marker in ("task", "taskqueue", "auftrag", "sequenz", "workflow", "run task")):
            return self.tools.execute_task_queue(prompt)

        if any(marker in compact_text for marker in (
            "windowsui", "windows ui", "desktop app", "desktop automation", "ui flow",
            "windows app", "visible ui", "app workflow", "fenster workflow", "desktop workflow",
            "orchestrierung", "orchestrate", "orchestration", "klick im fenster",
            "notepad", "calculator", "rechner", "explorer", "vscode", "outlook"
        )):
            return self.tools.execute_local_workflow(prompt)

        if any(marker in compact_text for marker in ("lokalworkflow", "local workflow", "agent workflow", "alles machen", "mach alles", "alles ausfuehren", "agent")):
            return self.tools.execute_local_workflow(prompt)

        if isinstance(image_paths, (str, bytes, os.PathLike)):
            image_paths = [image_paths]
        else:
            image_paths = list(image_paths or [])
        if image_paths:
            try:
                image_paths = [
                    self.screen_vision.validate_image(path) for path in image_paths
                ]
            except (OSError, ValueError) as exc:
                return f"Bildanalyse nicht möglich: {exc}"

        if self.tools.pending:
            if self.tools.pending.get("type") == "email":
                if compact_text in ("nein", "n", "abbrechen", "stopp", "stop"):
                    return self.tools.cancel_pending()
                if compact_text in ("ja", "j", "bestatige", "bestatigen", "mach", "ok", "okay") or any(
                    marker in compact_text for marker in ("bestat", "confirm", "oeffne")
                ):
                    return self.tools.confirm_pending()
                email_follow_up = self.tools.continue_email(prompt)
                if email_follow_up:
                    return email_follow_up
            if (
                self.tools.pending.get("type") == "paper_trade"
                and self.tools.pending.get("awaiting_confirmation")
                and (
                    compact_text in ("ja", "j", "bestatige", "bestatigen", "mach", "ok", "okay")
                    or any(
                        marker in compact_text
                        for marker in ("bestat", "confirm", "ausfuehr")
                    )
                )
            ):
                return self.tools.confirm_pending()
            if compact_text in ("nein", "n", "abbrechen", "stopp", "stop"):
                return self.tools.cancel_pending()
            paper_follow_up = self.tools.continue_paper_trade(prompt)
            if paper_follow_up:
                return paper_follow_up
            if compact_text in ("ja", "j", "bestatige", "bestatigen", "mach", "ok", "okay"):
                return self.tools.confirm_pending()

        quick_reply = self._quick_reply(compact_text)
        if quick_reply:
            return quick_reply

        if not youtube_url:
            desktop_result = self._route_desktop_tool(prompt, normalized_text)
            if desktop_result is not None:
                return self.tools.format_result(desktop_result)

        if self._is_self_check(compact_text):
            return self.self_repair.run_check()
        if self._is_improvement_cycle(compact_text):
            return self.self_repair.run_improvement_cycle()
        if any(marker in compact_text for marker in (
            "schwarmoptimieren", "schwarmupgrade", "paperschwarmupgrade",
        )):
            try:
                return self.paper_swarm.optimize(generations=3)
            except ValueError as exc:
                return f"Paper-Schwarm-Optimierung fehlgeschlagen: {exc}"
        if any(marker in compact_text for marker in (
            "paperschwarm", "paperswarm", "500kis", "500agenten",
            "schwarmsimulation", "schwarmsimulieren",
        )):
            try:
                result = self.paper_swarm.run(start_balance=50.0, agent_count=500)
                return (
                    format_result(result)
                    + "\nDie Optimierungsfunktion darf nur Simulator-Parameter "
                    "anpassen und benötigt keine Selbstlöschung."
                )
            except ValueError as exc:
                return f"Paper-Schwarm konnte nicht gestartet werden: {exc}"
        if compact_text in ("plugins", "pluginss", "zeigeplugins"):
            plugins = self.plugins.list()
            if not plugins:
                return "Es sind noch keine Plugins installiert."
            return "Aktive Plugins:\n- " + "\n- ".join(
                plugin["name"] for plugin in plugins
            )
        if compact_text in ("audio", "mikrofone", "mikrofon"):
            status = self.audio_devices.status()
            selected = status["selected"] or "Windows-Standardgerät"
            return f"Aktives Mikrofon: {selected}. Öffne AUDIO DEVICES für die Geräteauswahl."
        if any(marker in compact_text for marker in (
            "bildschirm", "screen", "screenshot", "screenshots", "desktop",
        )) and not image_paths:
            try:
                observation = self.tools.execute_structured("active_context")
                if not observation.get("ok"):
                    return observation.get("message", "Live-UI-Kontext nicht verfügbar.")
                data = observation.get("data", {})
                return (
                    f"Live-UI-Kontext gelesen. Aktives Fenster: "
                    f"{data.get('title') or 'unbekannt'}. "
                    f"Erkannte UI-Elemente: {len(data.get('controls', []))}. "
                    "Ich nutze Windows-UI-Elemente und Browser-DOM statt Screenshots."
                )
            except (OSError, RuntimeError, ValueError) as exc:
                return f"Live-UI-Kontext fehlgeschlagen: {exc}"

        email_request = self.tools.prepare_email(prompt)
        if email_request:
            return email_request

        if not youtube_url and any(word in normalized_text for word in (
            "trading", "traden", "trade", "tradingview", "aktie kaufen",
            "krypto kaufen", "trading bot", "tradingbot",
        )) and not self._is_open_command(normalized_text):
            if (
                self._extract_market_symbol(normalized_text)
                and any(alias in normalized_text for alias in (
                "tradingview", "trading view", "tradingwiew", "tracding", "tradin"
                ))
                or (
                    any(word in normalized_text for word in ("long", "short"))
                    and self.last_market_symbol
                )
            ):
                pass
            else:
                return (
                    "Ich kann Märkte recherchieren, TradingView öffnen, Strategien "
                    "analysieren und einen Paper-Trading-Bot als Code entwerfen. "
                    "Orders mit echtem Geld führe ich nicht aus. Nenne mir Markt, "
                    "Zeitraum und gewünschtes Risiko."
                )

        if not youtube_url and any(word in normalized_text for word in ("long", "short", "trade", "traden")):
            if not self._extract_market_symbol(normalized_text) and not self.last_market_symbol:
                return "Welchen Markt soll ich handeln? Nenne bitte zum Beispiel BTCUSD oder XAUUSD."

        calculator_result = self._calculator(prompt)
        if calculator_result is not None:
            return calculator_result

        if compact_text.startswith(("notiz", "note")):
            note = re.sub(r"^(notiz|note)\s*:?\s*", "", prompt, flags=re.IGNORECASE).strip()
            if note:
                self.memory.remember("Notiz", note)
                return f"Notiz gespeichert: {note}"

        if compact_text in ("systemstatus", "systemuebersicht", "uebersicht"):
            return self._system_status()

        if ("youtube" in normalized_text or "yt" in normalized_text) and any(
            marker in normalized_text for marker in (" von ", " mit ", " uber ", " nach ")
        ):
            target = normalized_text
            for marker in (" von ", " mit ", " uber ", " nach "):
                if marker in target:
                    query = target.split(marker, 1)[1]
                    break
            query = re.sub(
                r"\s+(offne|offnen|starte|starten|bitte|kannst|du)\s*$",
                "",
                query,
            ).strip()
            if query:
                webbrowser.open(
                    f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                )
                results = self._fetch_youtube_results(query)
                self.conversation_state["last_search_query"] = query
                self.conversation_state["last_results"] = results
                if results:
                    return "\n".join(
                        [f"YouTube-Ergebnisse für „{query}“:"] + [
                            f"{index}. {item['title']} — {item['url']}"
                            for index, item in enumerate(results, start=1)
                        ]
                    )
                return f"YouTube-Suche nach '{query}' gestartet, Sir."

        youtube_search = self._youtube_search(prompt)
        if youtube_search is not None:
            return youtube_search

        chart_symbol = self._extract_market_symbol(normalized_text)
        if (
            self._is_open_command(normalized_text)
            and chart_symbol
            and re.search(r"\b(?:xauusd|gold|dxy|usdx|btc\s*/?\s*usdt)\b", normalized_text)
        ):
            self.last_market_symbol = chart_symbol
            try:
                return self.tools.tradingview.open_chart(chart_symbol)
            except RuntimeError as exc:
                fallback = self.tools.execute_structured(
                    "open_url",
                    url=f"https://www.tradingview.com/chart/?symbol={chart_symbol}",
                )
                if fallback.get("ok"):
                    return (
                        f"TradingView konnte nicht direkt gesteuert werden ({exc}), "
                        "der Chart wurde im Standardbrowser geöffnet."
                    )
                return f"TradingView-Chart konnte nicht geöffnet werden: {exc}"
        if (
            self._is_open_command(normalized_text)
            and chart_symbol
            and any(marker in normalized_text for marker in (
                "chart", "charts", "diagramm", "grafik", "kurschart",
            ))
        ):
            try:
                self.last_market_symbol = chart_symbol
                return self.tools.tradingview.open_chart(chart_symbol)
            except RuntimeError as exc:
                chart_url = (
                    "https://www.tradingview.com/chart/?symbol="
                    + urllib.parse.quote(chart_symbol)
                )
                webbrowser.open(chart_url)
                return (
                    f"Der direkte TradingView-Chart für {chart_symbol} wurde geöffnet. "
                    f"Die sichtbare Chart-Automation ist derzeit nicht verfügbar: {exc}"
                )

        if any(word in normalized_text for word in (
            "tradingview", "trading view", "tradingwiew", "tracding", "tradin"
        )) and (self._is_open_command(normalized_text) or self._extract_market_symbol(normalized_text)):
            symbol = self._extract_market_symbol(normalized_text)
            if "gold" in normalized_text and not symbol:
                symbol = "XAUUSD"
            if symbol:
                self.last_market_symbol = symbol
                webbrowser.open(f"https://www.tradingview.com/symbols/{symbol}/")
                if "long" in normalized_text or "short" in normalized_text:
                    direction = "Long" if "long" in normalized_text else "Short"
                    prepared = self.tools.prepare_paper_trade(symbol, direction)
                    return self.tools.continue_paper_trade(prompt) or prepared
                return f"TradingView wurde mit {symbol} geöffnet, Sir."
            webbrowser.open("https://www.tradingview.com/")
            return "TradingView wurde geöffnet, Sir."

        youtube_match = re.search(
            r"(?:youtube|yt).*?\b(?:von|mit|uber|nach)\s+(.+?)\s+(?:offne|offnen|starte|starten)$",
            normalized_text,
        )
        if youtube_match:
            query = youtube_match.group(1).strip()
            webbrowser.open(
                f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            )
            return f"YouTube-Suche nach '{query}' gestartet, Sir."

        favorite_color_match = re.search(
            r"\b(?:ich mag|meine lieblingsfarbe ist|meine lieblingsfarbe:)\s+([a-zäöüß-]+)",
            text,
        )
        if favorite_color_match:
            color = prompt[favorite_color_match.start(1):favorite_color_match.end(1)].strip()
            self.memory.remember("Benutzer-Fakt", f"Lieblingsfarbe: {color}")
            self.history.append(("Benutzer-Fakt", f"Lieblingsfarbe: {color}"))
            self.history = self.history[-12:]
            return f"Verstanden. Deine Lieblingsfarbe ist {color}."

        name_match = re.search(
            r"\b(?:mein(?:e)? name ist|ich heiße|ich heisse|ich heise|ich heis|nenn mich) ([^.!?]+)",
            text,
        )
        if name_match:
            name = prompt[name_match.start(1):name_match.end(1)].strip()
            self.memory.remember("Benutzer-Fakt", f"Name: {name}")
            self.history.append(("Benutzer-Fakt", f"Name: {name}"))
            self.history = self.history[-12:]
            return f"Verstanden. Ich nenne dich ab jetzt {name}."

        if (
            "wie heiße ich" in text
            or "wie heisse ich" in normalized_text
            or "wie heiss ich" in normalized_text
            or "wie heis ich" in normalized_text
            or "was ist mein name" in normalized_text
        ):
            name = self._known_fact("Name:")
            return f"Du heißt {name}." if name else "Das hast du mir noch nicht gesagt."

        if (
            "lieblingsfarbe" in compact_text
            or ("liebl" in compact_text and "farb" in compact_text)
            or "welchefarbemagich" in compact_text
            or                         "wasmagichfüreinefarbe".replace(" ", "").replace("ü", "u") in compact_text
            or "wasmagich" in compact_text
        ):
            color = self._known_fact("Lieblingsfarbe:")
            if not color:
                color = self._known_fact_from_conversation("ich mag")
            return (
                f"Deine Lieblingsfarbe ist {color}."
                if color
                else "Das hast du mir noch nicht gesagt."
            )

        if compact_text in ("ja", "jap", "richtig", "richtigso", "genau", "stimmt"):
            last_topic = " ".join(
                message.lower()
                for role, message in (self.history + [
                    (item.get("role", ""), item.get("text", ""))
                    for item in self.memory.recent(8)
                ])[-8:]
                if role in ("Benutzer", "JARVIS", "Benutzer-Fakt")
            )
            if "farbe" in last_topic or "blau" in last_topic:
                color = self._known_fact("Lieblingsfarbe:")
                return f"Verstanden, ich bestätige: Deine Lieblingsfarbe ist {color}." if color else "Verstanden."
            return "Verstanden."

        memory_match = re.match(
            r"^(?:merk dir|merke dir|denk daran)\s*[:,]?\s*(.+)$",
            text,
            re.IGNORECASE,
        )
        if memory_match:
            fact = prompt[memory_match.start(1):memory_match.end(1)].strip()
            if fact:
                self.memory.remember("Benutzer-Fakt", fact)
                self.history.append(("Benutzer-Fakt", fact))
                self.history = self.history[-12:]
                return f"Verstanden. Ich merke mir: {fact}"

        memory_query = (
            compact_text in (
                "wasweisstduubermich",
                "wasweisstdunoch",
                "zeigemeingedachtnis",
            )
            or (
                compact_text.startswith("was")
                and ("weist" in compact_text or "weisst" in compact_text)
                and "uber" in compact_text
                and ("mich" in compact_text or "lich" in compact_text)
            )
        )
        if memory_query:
            stored = self.memory.recent(30)
            facts = [
                item["text"]
                for item in stored
                if isinstance(item, dict) and item.get("role") == "Benutzer-Fakt"
            ]
            conversations = [
                f"{item['role']}: {item['text']}"
                for item in stored
                if isinstance(item, dict)
                and item.get("role") in ("Benutzer", "Benutzer-Fakt")
                and item.get("text")
            ]
            if facts:
                return "Dauerhaft gespeichert:\n- " + "\n- ".join(facts)
            if conversations:
                return (
                    "Ich habe noch keine ausdrücklich markierten persönlichen "
                    "Fakten, aber diesen Verlauf gespeichert:\n- "
                    + "\n- ".join(conversations[-10:])
                )
            return "Mein dauerhaftes Gedächtnis ist noch leer."

        if len(text) <= 20 and text in (
            "blau", "rot", "grun", "grün", "gelb", "schwarz",
            "weiß", "weiss", "orange", "lila", "violett", "pink",
        ):
            recent_user_text = " ".join(
                message.lower()
                for role, message in (
                    self.history + [
                        (item.get("role", ""), item.get("text", ""))
                        for item in self.memory.recent(8)
                    ]
                )[-12:]
                if role == "Benutzer"
            )
            if "farbe" in recent_user_text or "lieblingsfarbe" in recent_user_text:
                color = prompt.strip()
                self.memory.remember("Benutzer-Fakt", f"Lieblingsfarbe: {color}")
                self.history.append(("Benutzer-Fakt", f"Lieblingsfarbe: {color}"))
                return f"Verstanden. Deine Lieblingsfarbe ist {color}."
        
        if self._is_open_command(normalized_text):
            target = (
                normalized_text.replace("offne", "")
                .replace("offnen", "")
                .replace("oeffne", "")
                .replace("oeffnen", "")
                .replace("starte", "")
                .replace("starten", "")
                .strip()
            )
            if not target:
                return "Was soll ich öffnen? Nenne bitte eine App, Website oder ein TradingView-Symbol."
            if "gmail" in target or "mail" in target:
                webbrowser.open("https://mail.google.com")
                return "Gmail wurde in deinem Browser geöffnet, Sir."
            elif "youtube" in target or "yt" in target:
                query = ""
                for marker in (" mit ", " von ", " über ", " nach "):
                    if marker in target:
                        query = target.split(marker, 1)[1].strip()
                        break
                if query:
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
            elif any(alias in target for alias in (
                "tradingview", "trading view", "tradingwiew", "tracding", "tradin"
            )):
                symbol = self._extract_market_symbol(target)
                if "gold" in target and not symbol:
                    symbol = "XAUUSD"
                if symbol:
                    self.last_market_symbol = symbol
                    webbrowser.open(f"https://www.tradingview.com/symbols/{symbol}/")
                    return f"TradingView wurde mit {symbol} geöffnet, Sir."
                webbrowser.open("https://www.tradingview.com/")
                return "TradingView wurde geöffnet, Sir."
            elif "editor" in target or "notepad" in target:
                result = self.tools.execute_structured("open_application", name="editor")
                return self.tools.format_result(result)
            else:
                webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(target)}")
                return f"Web-Suche nach '{target}' ausgeführt, Sir."

        if any(marker in normalized_text for marker in (
            "formular", "form", "login", "anmeldung", "absenden", "submit",
            "ausfüllen", "ausfuellen", "fill", "browserflow", "browser workflow",
        )):
            return self.tools.format_result(self.tools.execute_browser_flow(prompt))

        if any(marker in normalized_text for marker in (
            "browser task", "browser aufgabe", "browser workflow", "web task",
        )):
            return self.tools.format_result(self.tools.execute_browser_flow(prompt))

        casual_responses = {
            "hey": "Hey. Ich bin da. Was soll ich für dich tun?",
            "hallo": "Hallo. Was kann ich für dich erledigen?",
            "hi": "Hi. Was brauchst du?",
            "was geht": "Alles im grünen Bereich, Sir. Ich bin online und bereit.",
            "wie gehts": "Systeme stabil, Sir. Ich bin bereit für Ihren nächsten Auftrag.",
            "wie geht's": "Systeme stabil, Sir. Ich bin bereit für Ihren nächsten Auftrag.",
            "was geht ab": "Alles läuft, Sir. Womit soll ich weitermachen?",
            "danke": "Gern, Sir.",
            "danke dir": "Jederzeit, Sir.",
        }
        casual_key = re.sub(r"[!?.,]+$", "", normalized_text).strip()
        if casual_key in casual_responses:
            return casual_responses[casual_key]

        market_symbol = self._extract_market_symbol(normalized_text)
        if not market_symbol and any(word in normalized_text for word in ("long", "short")):
            market_symbol = self.last_market_symbol
        if market_symbol and any(word in normalized_text for word in ("long", "short")):
            webbrowser.open(f"https://www.tradingview.com/symbols/{market_symbol}/")
            direction = "Long" if "long" in normalized_text else "Short"
            prepared = self.tools.prepare_paper_trade(market_symbol, direction)
            return self.tools.continue_paper_trade(prompt) or prepared

        if any(word in normalized_text for word in ("google", "websuche", "internetsuche", "such im internet")):
            query = re.sub(
                r".*?(google|websuche|internetsuche|such im internet)\s*",
                "",
                prompt,
                flags=re.IGNORECASE,
            ).strip()
            if query:
                webbrowser.open(
                    f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                )
                return f"Web-Suche nach '{query}' geöffnet, Sir."

        if not self.is_active:
            return (
                "Ollama läuft nicht. Starten Sie Ollama mit: ollama serve\n"
                "Oder laden Sie ein Modell: ollama run llama3.1:8b"
            )

        context = ""
        profile = self.memory.behavior_profile()
        if profile and not memory_query:
            context += (
                "\n\nAKTIVES JARVIS-VERHALTENSPROFIL:\n"
                "Halte dich an diese lokalen Ziele und Arbeitsweise. "
                "Es ersetzt keine aktuelle Nutzeranweisung.\n"
                f"- Sprache: {profile.get('language', 'de')}\n"
                f"- Stil: {', '.join(profile.get('response_style', []))}\n"
                f"- Ziele: {'; '.join(profile.get('primary_goals', []))}\n"
                "- Sicherheitsregeln: "
                + "; ".join(profile.get("safety_rules", []))
            )
        facts = self.memory.facts()
        if facts and not memory_query:
            context += (
                "\n\nInterne Benutzerinformationen. Nutze sie nur, wenn sie "
                "für die aktuelle Antwort relevant sind. Erwähne diese Liste "
                "nicht und sage nicht, dass du Memory geladen hast:\n"
                + "\n".join(f"- {fact}" for fact in facts)
            )
        if not memory_query:
            remembered = self.memory.relevant_context(prompt, limit=5)
            if remembered:
                context += (
                    "\n\nRELEVANTER SECOND-BRAIN-KONTEXT:\n"
                    "Nutze diese früheren Angaben nur, wenn sie zur aktuellen Aufgabe passen. "
                    "Aktuelle Anweisungen haben Vorrang. Behaupte keine alten Aktionen als neu ausgeführt.\n"
                    + "\n".join(
                        f"- Frühere Eingabe: {item.get('prompt', item.get('text', ''))}"
                        f" | Ergebnis: {item.get('answer', '')[:700]}"
                        for item in remembered
                    )
                )
        if self.history and len(text) > 3:
            context = (
                context
                + "\n\nGesprächskontext:\n"
                + "\n".join(
                    f"{role}: {message}" for role, message in self.history[-6:]
                )
            )
        correction_note = ""
        if text.startswith(("nein", "ne", "ich meinte", "korrektur")):
            correction_note = (
                "\n\nWICHTIGE KORREKTUR: Die aktuelle Nachricht korrigiert "
                "eine frühere Aussage. Verwende die neue Angabe als gültig "
                "und erfinde keine weiteren Details dazu."
            )
        follow_up_note = ""
        if len(text) <= 20 and not any(
            marker in text for marker in ("wer bist", "was bist", "hilfe")
        ):
            follow_up_note = (
                "\n\nKURZE NACHFRAGE: Das ist wahrscheinlich eine Ergänzung "
                "oder Korrektur zur vorherigen Nachricht. Beziehe dich zuerst "
                "auf das letzte Thema. Wenn die Abkürzung unklar ist, frage "
                "kurz nach, statt eine Identität zu behaupten."
            )

        research = []
        research_query = self._market_follow_up(text) or prompt
        if self._needs_research(text) or research_query != prompt:
            try:
                research = self._research(research_query)
            except requests.RequestException:
                research = []

        source_context = ""
        if research:
            self.conversation_state["last_results"] = [
                {"title": title, "url": url} for title, url in research
            ]
            source_context = (
                "\n\nRecherche-Ergebnisse. Prüfe sie kritisch. Nenne keine "
                "URLs oder Quellen, außer der Benutzer fragt ausdrücklich danach:\n"
                + "\n".join(f"- {title} — {url}" for title, url in research)
            )
        elif self._needs_research(text) or research_query != prompt:
            source_context = (
                "\n\nWICHTIG: Die angeforderte Webrecherche war nicht verfügbar. "
                "Behaupte deshalb nicht, aktuelle Fakten geprüft oder Quellen "
                "gefunden zu haben. Sage offen, dass du die Recherche nicht "
                "ausführen konntest."
            )

        full_prompt = model_prompt + context + correction_note + follow_up_note + source_context
        system_prompt = (
            JARVIS_SYSTEM_PROMPT
            + f" Laufzeitstatus: Provider={self.provider}; Modell={self.model}. "
            "Nenne bei Fragen nach der verwendeten KI genau diesen Provider und "
            "dieses Modell und erfinde keine andere technische Quelle. "
            "Wiederhole keine allgemeinen Systembereiche. Halte die Antwort "
            "standardmäßig auf wenige Sätze begrenzt. Bei 'Was kannst du?' "
            "nenne kurz konkrete Fähigkeiten statt einer generischen Statusmeldung."
        )
        if self.provider == "openrouter":
            cloud_result = self._request_openrouter(full_prompt, system_prompt, image_paths)
            if not cloud_result.startswith((
                "OpenRouter ist noch nicht",
                "OpenRouter-Anfrage fehlgeschlagen",
                "OpenRouter hat keine",
                "Keine Antwort von OpenRouter",
            )):
                return cloud_result
            previous_provider = self.provider
            self.provider = "nim" if self.nim_api_key else "ollama"
            try:
                return self.process_request(prompt, image_paths=image_paths)
            finally:
                self.provider = previous_provider
        if self.provider == "omniroute":
            router_result = self._request_omniroute(full_prompt, system_prompt, image_paths)
            if not router_result.startswith("OmniRoute-Anfrage fehlgeschlagen"):
                return router_result
            fallback_provider = "nim" if self.nim_api_key else "ollama"
            previous_provider = self.provider
            self.provider = fallback_provider
            try:
                return self.process_request(prompt, image_paths=image_paths)
            finally:
                self.provider = previous_provider
        if self.provider == "gemini":
            cloud_result = self._request_gemini(full_prompt, system_prompt, image_paths)
            if not cloud_result.startswith((
                "Google AI ist noch nicht",
                "Google-AI-Anfrage fehlgeschlagen",
                "Keine Antwort von Google AI",
            )):
                return cloud_result
            if self.available_models:
                previous_provider = self.provider
                self.provider = "ollama"
                try:
                    return self.process_request(prompt, image_paths=image_paths)
                finally:
                    self.provider = previous_provider
            return cloud_result
        if self.provider == "nim":
            cloud_result = self._request_nim(full_prompt, system_prompt, image_paths)
            if not cloud_result.startswith((
                "NVIDIA NIM ist noch nicht",
                "NVIDIA-NIM-Anfrage fehlgeschlagen",
                "NVIDIA NIM hat für alle",
                "Keine Antwort von NVIDIA NIM",
            )) and not cloud_result.startswith("NVIDIA-NIM-Fehler"):
                return cloud_result
            if self.use_ollama:
                previous_provider = self.provider
                self.provider = "ollama"
                try:
                    return self.process_request(prompt, image_paths=image_paths)
                finally:
                    self.provider = previous_provider
            return cloud_result

        try:
            encoded_images = []
            for image_path in image_paths:
                with open(image_path, "rb") as image_file:
                    encoded_images.append(base64.b64encode(image_file.read()).decode("ascii"))
            request_model = self._model_for_request(text, image=bool(image_paths))
            request_payload = {
                "model": request_model,
                "prompt": full_prompt,
                "system": (
                    JARVIS_SYSTEM_PROMPT
                    + f" Für diese Anfrage ist das passende lokale Modell {request_model}. "
                    "Antworte immer auf Deutsch, natürlich und präzise. Arbeite strikt "
                    "und kompakt: direkte Antwort zuerst, höchstens 5 kurze "
                    "Bullet-Points und nur relevante Informationen. "
                    "nach der Benutzeranweisung. Bei aktuellen Themen darfst du nur "
                    "die mitgelieferten verifizierten Daten verwenden. Wenn solche "
                    "Daten fehlen, sage exakt, dass keine aktuellen Daten vorliegen; "
                    "verwende niemals alte Beispielereignisse oder Jahreszahlen als "
                    "Ersatz. "
                    "Erfinde niemals Fakten, Erinnerungen, Quellen oder Handlungen. "
                    "Behaupte niemals, etwas gefunden, gebucht, heruntergeladen, "
                    "geöffnet, geprüft oder vorbereitet zu haben, wenn es nicht "
                    "in diesem Chat ausdrücklich als erfolgreich ausgeführt "
                    "wurde. Du hast keinen Zugriff auf Buchungen, Karten, Dateien "
                    "oder Webseiten, außer wenn konkrete Recherche-Ergebnisse "
                    "mitgeliefert werden. Wenn keine Quelle oder Aktion vorliegt, "
                    "sage klar: Das habe ich nicht ausgeführt. Wenn eine Anfrage "
                    "unklar ist, stelle genau eine kurze Rückfrage und tue nichts. "
                    "Wenn der Benutzer Code verlangt, liefere zuerst eine "
                    "klare Lösung, prüfe sie gedanklich auf Fehler und nenne "
                    "notwendige Tests. Schreibe keine Projektdateien und führe "
                    "Führe erlaubte externe Aktionen aus, wenn der Benutzer sie klar "
                    "und direkt beauftragt; warte nur bei irreversiblen Aktionen auf "
                    "die zusätzliche Bestätigung. "
                    "Erfinde niemals "
                    "Hotels, Reisepläne, Preise, Dateien oder Suchergebnisse. "
                    "Wenn etwas unsicher oder nicht aktuell bekannt ist, sage das offen "
                    "und trenne Fakten klar von Vermutungen. Bei Recherche "
                    "nenne Quellen nur auf ausdrückliche Nachfrage. Erkenne Korrekturen anhand des "
                    "Gesprächskontexts und passe deine Antwort entsprechend an. "
                    "Stelle dich niemals als Llama oder Meta-KI vor. Wenn du "
                    "nach deiner Identität gefragt wirst, "
                    "sage: Ich bin J.A.R.V.I.S., dein persönlicher Assistent."
                ),
                "stream": False,
                "temperature": 0.15,
                "keep_alive": "2m",
                "options": {
                    "num_predict": 256,
                    "num_ctx": 3072,
                    "top_p": 0.85,
                },
            }
            if encoded_images:
                request_payload["images"] = encoded_images
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=request_payload,
                timeout=(5, 180 if image_paths else 60)
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = self._extract_model_response(data)
                if answer:
                    if any(marker in text for marker in (
                        "falsch", "stimmt nicht", "nicht was ich wollte",
                        "verbessere", "korrigiere",
                    )):
                        self.self_repair.record_issue(prompt, answer)
                    return answer
                return "Keine Antwort vom Modell erhalten."
            else:
                if image_paths and response.status_code in (400, 404, 422):
                    return (
                        "Bildanalyse ist für das konfigurierte Ollama-Modell nicht "
                        "verfügbar. Wähle ein Vision-Modell, zum Beispiel "
                        "llava:7b oder qwen2.5vl, und setze OLLAMA_MODEL neu."
                    )
                try:
                    detail = response.json().get("error", "")
                except ValueError:
                    detail = ""
                return f"Ollama-Fehler {response.status_code}: {detail or 'unbekannter Fehler'}"
                
        except requests.exceptions.ConnectionError:
            return (
                "Ollama nicht erreichbar. Führen Sie aus:\n"
                "ollama serve"
            )
        except requests.exceptions.Timeout:
            return (
                "Ollama antwortet gerade zu langsam. Der Vorgang wurde nach "
                f"{180 if image_paths else 60} Sekunden abgebrochen. "
                "Prüfe, ob das gewählte Modell zur Aufgabe passt."
            )
        except Exception as exc:
            return f"KI-Anfrage fehlgeschlagen: {exc}"

    def _request_gemini(self, prompt, system_prompt, image_paths):
        if not self.gemini_api_key:
            return (
                "Google AI ist noch nicht verbunden. Trage GEMINI_API_KEY in .env ein "
                "und starte JARVIS danach neu."
            )
        try:
            parts = [{"text": prompt}]
            for image_path in image_paths:
                with open(image_path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode("ascii")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": encoded,
                    }
                })
            response = requests.post(
                f"{self.gemini_url}/{self.model}:generateContent",
                params={"key": self.gemini_api_key},
                json={
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {"temperature": 0.15, "maxOutputTokens": 512},
                },
                timeout=(5, 90),
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            answer = ""
            if candidates:
                content = candidates[0].get("content", {})
                answer = "".join(
                    part.get("text", "")
                    for part in content.get("parts", [])
                    if isinstance(part, dict)
                ).strip()
            return answer or "Keine Antwort von Google AI erhalten."
        except requests.exceptions.Timeout:
            return "Google AI antwortet gerade zu langsam. Der Vorgang wurde abgebrochen."
        except requests.exceptions.RequestException as exc:
            detail = ""
            if exc.response is not None:
                try:
                    detail = exc.response.json().get("error", {}).get("message", "")
                except ValueError:
                    detail = ""
            return f"Google-AI-Anfrage fehlgeschlagen: {detail or exc}"

    def _request_nim(self, prompt, system_prompt, image_paths):
        if not self.nim_api_key:
            return (
                "NVIDIA NIM ist noch nicht verbunden. Trage NIM_API_KEY in .env ein "
                "und starte JARVIS danach neu."
            )
        if image_paths:
            return (
                "NVIDIA NIM ist aktuell als Textmodell konfiguriert. "
                "Für Bildanalyse wird auf Ollama mit einem Vision-Modell zurückgegriffen."
            )
        for model in self.nim_models:
            if model in self.nim_exhausted_models:
                continue
            try:
                response = requests.post(
                    self.nim_url,
                    headers={
                        "Authorization": f"Bearer {self.nim_api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.15,
                        "top_p": 0.85,
                        "max_tokens": 512,
                        "stream": False,
                    },
                    timeout=(5, 20),
                )
                if response.status_code == 200:
                    self.nim_model = model
                    self.model = model
                    data = response.json()
                    answer = self._extract_model_response(data)
                    return answer or "Keine Antwort von NVIDIA NIM erhalten."
                if response.status_code in (400, 402, 403, 404, 410, 429):
                    self.nim_exhausted_models.add(model)
                    continue
                try:
                    detail = response.json().get("error", "")
                except ValueError:
                    detail = ""
                return f"NVIDIA-NIM-Fehler {response.status_code}: {detail or 'unbekannter Fehler'}"
            except requests.exceptions.Timeout:
                self.nim_exhausted_models.add(model)
                continue
            except requests.exceptions.RequestException:
                self.nim_exhausted_models.add(model)
                continue
        return (
            "NVIDIA NIM hat für alle konfigurierten Modelle das Kontingent "
            "erschöpft. Wechsel auf Ollama."
        )

    def _load_openrouter_free_models(self):
        if self.openrouter_models:
            return self.openrouter_models
        try:
            response = requests.get(
                self.openrouter_models_url,
                headers={"Authorization": f"******", "Accept": "application/json"},
                timeout=20,
            )
            response.raise_for_status()
            models = response.json().get("data", [])
            free_models = []
            for item in models:
                model_id = str(item.get("id", "")).strip()
                pricing = item.get("pricing") or {}
                if (
                    model_id.endswith(":free")
                    and str(pricing.get("prompt", "")) in {"0", "0.0"}
                    and str(pricing.get("completion", "")) in {"0", "0.0"}
                ):
                    free_models.append(model_id)
            self.openrouter_models = free_models
            return free_models
        except (requests.exceptions.RequestException, ValueError, TypeError):
            return []

    def _request_openrouter(self, prompt, system_prompt, image_paths):
        if not self.openrouter_api_key:
            return "OpenRouter ist noch nicht verbunden. Trage OPENROUTER_API_KEY in .env ein."
        if image_paths:
            return "OpenRouter ist aktuell für Textanfragen konfiguriert; Bildanalyse nutzt den lokalen Fallback."
        models = self._load_openrouter_free_models()
        if not models:
            return "OpenRouter hat keine kostenlosen :free-Modelle geliefert."
        for model in models:
            if model in self.openrouter_exhausted_models:
                continue
            try:
                response = requests.post(
                    self.openrouter_url,
                    headers={
                        "Authorization": f"******",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.15,
                        "max_tokens": 512,
                    },
                    timeout=120,
                )
                if response.status_code == 200:
                    self.model = model
                    data = response.json()
                    return self._extract_model_response(data) or "Keine Antwort von OpenRouter erhalten."
                if response.status_code in (400, 402, 403, 404, 408, 409, 429, 500, 502, 503):
                    self.openrouter_exhausted_models.add(model)
                    continue
                return f"OpenRouter-Anfrage fehlgeschlagen: HTTP {response.status_code}"
            except requests.exceptions.RequestException:
                self.openrouter_exhausted_models.add(model)
        return "OpenRouter hat keine verfügbaren kostenlosen Modelle mehr. Wechsel zum nächsten Provider."

    def _request_omniroute(self, prompt, system_prompt, image_paths):
        if image_paths:
            return "OmniRoute ist aktuell für Textanfragen konfiguriert; Bildanalyse nutzt den lokalen Fallback."
        try:
            response = requests.post(
                self.omniroute_url,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "model": self.model or "auto",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=120,
            )
            if response.status_code == 200:
                answer = self._extract_model_response(response.json())
                return answer or "Keine Antwort von OmniRoute erhalten."
            return f"OmniRoute-Anfrage fehlgeschlagen: HTTP {response.status_code}"
        except requests.exceptions.RequestException as exc:
            return f"OmniRoute-Anfrage fehlgeschlagen: {exc}"

    @staticmethod
    def _extract_model_response(data):
        """Accept Ollama and OpenAI-compatible response shapes defensively."""
        if not isinstance(data, dict):
            return ""
        value = data.get("response")
        if not value and isinstance(data.get("message"), dict):
            value = data["message"].get("content")
        if not value and isinstance(data.get("choices"), list) and data["choices"]:
            choice = data["choices"][0]
            if isinstance(choice, dict):
                value = choice.get("text")
                if not value and isinstance(choice.get("message"), dict):
                    value = choice["message"].get("content")
        if isinstance(value, list):
            value = "".join(str(part) for part in value)
        return str(value or "").strip()

    def process_request(self, prompt, image_paths=None, image_path=None):
        """Public request boundary: preserve every turn for conversational context."""
        prompt = str(prompt or "").strip()
        if not prompt:
            return "Bitte formuliere eine Anfrage."
        intent = self.detect_intent(prompt)
        self.memory.record("intents", {
            "timestamp": datetime.now().isoformat(),
            "input": prompt,
            "intent": intent,
        })
        supervisor_report = self.agent_supervisor.prepare(prompt)
        if not supervisor_report.get("ok"):
            return (
                "Der Supervisor hat den Auftrag aus Sicherheitsgründen angehalten: "
                + str(supervisor_report.get("message", "Fähigkeit nicht verfügbar."))
            )
        swarm_context = ""
        normalized_request = self._normalize_command_language(prompt.lower())
        complex_request = (
            len(normalized_request.split()) > 10
            or len(self._compound_steps(prompt)) > 1
            or any(marker in normalized_request for marker in (
                "analysiere", "recherchiere", "vergleiche",
                "workflow", "automatisiere", "vollständig", "vollstaendig",
            ))
        )
        if (
            complex_request
            and self.is_active
            and self.agent_supervisor.config.get("enabled", False)
        ):
            limits = self.agent_supervisor.swarm_limits()
            swarm = LocalAgentSwarm(
                self.ollama_url,
                self.model,
                max_parallel=limits["max_parallel_agents"],
            )
            swarm_result = swarm.run(prompt)
            if swarm_result.get("ok"):
                swarm_context = (
                    "\n\nPARALLELE AGENTEN-VORPRÜFUNG:\n"
                    f"{swarm_result['context']}\n"
                    "Nutze diese Rollenhinweise nur als Arbeitsplanung. "
                    "Verifiziere das Ergebnis selbst und erfinde nichts."
                )
        self.conversation_state["swarm_context"] = swarm_context
        if isinstance(image_paths, (str, bytes, os.PathLike)):
            paths = [image_paths]
        else:
            paths = list(image_paths or [])
        if image_path:
            paths.append(image_path)
        youtube_input = self._extract_youtube_url(prompt)
        if youtube_input and prompt.strip() == youtube_input:
            prompt = (
                "Analysiere dieses YouTube-Video vollständig und richte eine aktive "
                "Video-Session für Folgefragen ein: " + youtube_input
            )
        validated_paths = []
        for path in paths:
            try:
                validated_paths.append(str(self.screen_vision.validate_image(path)))
            except (OSError, ValueError) as exc:
                return f"Bild kann nicht verarbeitet werden: {exc}"
        prompt = self._resolve_follow_up(prompt)
        if not self._extract_youtube_url(prompt):
            video_context = self.conversation_state.get("video_session_context", "")
            video_frames = self.conversation_state.get("video_session_frames", [])
            if video_context:
                prompt = (
                    "AKTIVE YOUTUBE-VIDEOSESSION: Der zuvor gesendete Link wurde vollständig "
                    "in zeitlichen 1-Sekunden-Schritten analysiert. Nutze diesen gespeicherten "
                    "Kontext für die Folgefrage und erfinde keine nicht belegten Details.\n"
                    f"{video_context[:24000]}\n\nFOLGEFRAGE: {prompt}"
                )
                if not validated_paths:
                    selected = video_frames[:3] + video_frames[len(video_frames) // 2:len(video_frames) // 2 + 2] + video_frames[-2:]
                    for path in dict.fromkeys(selected):
                        try:
                            validated_paths.append(str(self.screen_vision.validate_image(path)))
                        except (OSError, ValueError):
                            continue
        if validated_paths and not self._extract_youtube_url(prompt):
            prompt = (
                "LIVE-BILDSCHIRM, gerade vor dieser Frage aufgenommen. "
                "Beziehe den sichtbaren Bildschirminhalt in deine Antwort ein. "
                "Beschreibe nur sicher Erkanntes und markiere Unsicherheit. "
                "Nutzerfrage: " + prompt
            )
        steps = self._compound_steps(prompt)
        if steps and not paths:
            results = []
            previous_step = ""
            for index, step in enumerate(steps, start=1):
                contextual_step = self._contextualize_step(step, previous_step)
                result = str(self._process_request(contextual_step, image_paths=[])).strip()
                results.append(f"Schritt {index}: {step}\n{result}")
                previous_step = step
                self._update_conversation_state(contextual_step, result)
                if any(marker in result.lower() for marker in ("bestätigung erforderlich", "abgebrochen")):
                    break
            answer = "\n\n".join(results)
            self.history.extend([("Benutzer", prompt), ("JARVIS", answer)])
            self.history = self.history[-16:]
            try:
                self.memory.remember_interaction(
                    prompt, answer, intent=intent, state=self.conversation_state
                )
            except OSError:
                pass
            return answer
        answer = self._process_request(prompt, image_paths=validated_paths)
        answer = str(answer or "Keine Antwort erhalten.").strip()
        self._update_conversation_state(prompt, answer)
        self.history.extend([("Benutzer", prompt), ("JARVIS", answer)])
        self.history = self.history[-16:]
        try:
            self.memory.remember("Benutzer", prompt)
            self.memory.remember("JARVIS", answer)
            self.memory.record("context", {"input": prompt, "answer": answer, "intent": intent})
            self.memory.remember_interaction(
                prompt, answer, intent=intent, state=self.conversation_state
            )
            if re.search(
                r"\b(?:ich bevorzug|nenn mich|mein lieblings|antworte|sprich|merk dir|merke dir|ich will)\b",
                prompt,
                re.IGNORECASE,
            ):
                self.memory.remember_preference(prompt)
        except OSError:
            pass
        return answer

    @staticmethod
    def detect_intent(prompt):
        text = prompt.lower().strip()
        if re.match(r"^(hey|hi|hallo|moin|guten)", text):
            return "GreetIntent"
        if any(word in text for word in ("wetter", "temperatur", "regen")):
            return "WeatherIntent"
        if any(word in text for word in ("status", "läuft", "funktioniert")):
            return "StatusIntent"
        if any(word in text for word in ("erklär", "was ist", "warum")):
            return "ExplainIntent"
        if any(word in text for word in ("suche", "recherch", "google", "news")):
            return "SearchIntent"
        if any(word in text for word in ("merk dir", "speicher", "gedächtnis", "memory")):
            return "MemoryIntent"
        if any(word in text for word in ("ich bevorzuge", "lieblings", "nenn mich")):
            return "PreferenceIntent"
        if any(word in text for word in ("optimi", "verbessere", "schneller")):
            return "OptimizeIntent"
        if text in ("?", "hä", "hmm"):
            return "FollowUpIntent"
        if text.startswith(("nein", "korrektur", "ich meinte")):
            return "CorrectionIntent"
        if len(text.split()) <= 5:
            return "ShortCommandIntent"
        if len(text.split()) >= 20:
            return "LongCommandIntent"
        return "UnknownIntent"

    def ask(self, prompt):
        return self.process_request(prompt)

    def request_text(self, prompt, system_prompt="", image_paths=None):
        """Provider-only text request for internal agents; uses the same fallback policy."""
        previous_state = self.history
        self.history = []
        try:
            text = str(prompt or "")
            system = str(system_prompt or JARVIS_SYSTEM_PROMPT)
            images = list(image_paths or [])
            if self.provider == "nim":
                result = self._request_nim(text, system, images)
                if not result.startswith(("NVIDIA NIM ist noch nicht", "NVIDIA-NIM-Anfrage fehlgeschlagen", "NVIDIA NIM hat für alle", "Keine Antwort von NVIDIA NIM", "NVIDIA-NIM-Fehler")):
                    return result
            elif self.provider == "gemini":
                result = self._request_gemini(text, system, images)
                if not result.startswith(("Google AI ist noch nicht", "Google-AI-Anfrage fehlgeschlagen", "Keine Antwort von Google AI")):
                    return result
            elif self.provider == "openrouter":
                result = self._request_openrouter(text, system, images)
                if not result.startswith(("OpenRouter ist noch nicht", "OpenRouter-Anfrage fehlgeschlagen", "OpenRouter hat keine", "Keine Antwort von OpenRouter")):
                    return result
            elif self.provider == "omniroute":
                result = self._request_omniroute(text, system, images)
                if not result.startswith("OmniRoute-Anfrage fehlgeschlagen"):
                    return result
            else:
                result = ""
            if self.use_ollama:
                previous_provider = self.provider
                self.provider = "ollama"
                try:
                    return self.process_request(text, image_paths=images)
                finally:
                    self.provider = previous_provider
            return result
        finally:
            self.history = previous_state

    def analyze_image(self, image_path, question="Beschreibe dieses Bild präzise."):
        """Analyze one explicitly attached image through Ollama's vision API."""
        return self.process_request(question, image_paths=[image_path])

    def _known_fact(self, prefix):
        for item in reversed(self.memory.load()):
            value = item.get("text", "")
            if item.get("role") == "Benutzer-Fakt" and value.lower().startswith(prefix.lower()):
                return value[len(prefix):].strip()
        return ""

    def _calculator(self, prompt):
        expression_text = prompt.lower().replace(" plus ", "+").replace(" minus ", "-")
        expression_text = expression_text.replace(" mal ", "*").replace(" geteilt durch ", "/")
        match = re.search(
            r"(?:rechne|berechne|was ist)?\s*([0-9+\-*/().,%\s]+)$",
            expression_text,
        )
        if not match or not re.search(r"\d", match.group(1)):
            return None
        expression = match.group(1).replace("%", "/100")
        try:
            tree = ast.parse(expression, mode="eval")
            operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.USub: operator.neg,
            }
            def evaluate(node):
                if isinstance(node, ast.Expression):
                    return evaluate(node.body)
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
                    return operators[type(node.op)](evaluate(node.operand))
                if isinstance(node, ast.BinOp) and type(node.op) in operators:
                    return operators[type(node.op)](evaluate(node.left), evaluate(node.right))
                raise ValueError("unsupported expression")
            return f"Das Ergebnis ist {evaluate(tree):g}."
        except (ValueError, ZeroDivisionError, SyntaxError):
            return "Ich konnte diesen Rechenausdruck nicht sicher auswerten."

    def _system_status(self):
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        memory = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        battery_text = f" Akku: {battery.percent}%." if battery else ""
        return (
            f"Systemstatus: CPU {cpu:.1f}%, Arbeitsspeicher {memory:.1f}%, "
            f"Ollama {self.model} {'online' if self.is_active else 'offline'}.{battery_text}"
        )

    def _known_fact_from_conversation(self, phrase):
        for item in reversed(self.memory.load()):
            text = item.get("text", "")
            if item.get("role") == "Benutzer" and phrase in text.lower():
                return text.split()[-1].strip(".,!?")
        return ""

    def _repair_common_typos(self, value):
        replacements = (
            ("heisst", "heisst"),
            ("heisse", "heisse"),
            ("heis", "heiss"),
            ("hsort", "short"),
            ("shrot", "short"),
            ("sorth", "short"),
            ("lnog", "long"),
            ("lnog", "long"),
            ("weist", "weisst"),
            ("lmich", "mich"),
            ("liebligs", "lieblings"),
            ("richtiog", "richtig"),
            ("offme", "oeffne"),
            ("öffme", "oeffne"),
        )
        for wrong, correct in replacements:
            value = re.sub(rf"(?<![a-z]){wrong}(?![a-z])", correct, value)
        return value

    def _normalize_command_language(self, value):
        """Normalize common German speech-recognition variants for routing only."""
        replacements = (
            (r"\böffme\b|\boffme\b", "oeffne"),
            (r"\ufffdffne\b", "oeffne"),
            (r"\ufffdffnen\b", "oeffnen"),
            (r"\ufffcrufe\b", "pruefe"),
            (r"\boeffne\b", "oeffne"),
            (r"\bmaerkte\b", "maerkte"),
            (r"\btradingwiew\b|\btradinview\b|\btraddingview\b", "tradingview"),
            (r"\btrading view\b", "tradingview"),
            (r"\bmarkt ?uebersicht\b", "maerkte"),
            (r"\bgeh(?:e)?\s+(?:zu|auf)\s+", "oeffne "),
            (r"\bzeig(?:e)?\s+mir\s+", "oeffne "),
            (r"\bmach(?:e)?\s+(.+?)\s+auf\b", r"oeffne \1"),
            (r"\bhol(?:e)?\s+(.+?)\s+her\b", r"oeffne \1"),
            (r"\bbtc\s*[-/]?\s*usdt\b", "btc/usdt"),
            (r"\bbtc\s+usd\b", "btc/usd"),
            (r"\bxau\s*[-/]?\s*usd\b", "xauusd"),
            (r"\bcd\b(?=.*(?:usd|dollar|chart|tradingview))", "dxy"),
        )
        for pattern, replacement in replacements:
            value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", value).strip()

    def route_agent(self, prompt):
        return self.process_request(prompt), "INTELLIGENCE CORE"