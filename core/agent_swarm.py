"""Bounded parallel local agent swarm for J.A.R.V.I.S."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import requests


class LocalAgentSwarm:
    """Run specialist prompts concurrently against the local Ollama server."""

    ROLE_PROMPTS = {
        "planner": "Zerlege den Auftrag in höchstens drei konkrete Schritte. Keine Ausführung.",
        "researcher": "Bestimme, welche Fakten oder Quellen für den Auftrag benötigt werden. Keine erfundenen aktuellen Daten.",
        "operator": "Bestimme sichere, sichtbare Browser- oder Desktop-Aktionen. Keine irreversiblen Aktionen.",
        "coder": "Prüfe, ob Code, Tests oder technische Reparaturen nötig sind. Nenne Risiken.",
        "memory": "Bestimme, ob der Nutzer ausdrücklich etwas speichern möchte. Sonst antworte: nichts speichern.",
        "verifier": "Definiere zwei kurze Prüfungen, mit denen das Ergebnis verifiziert werden kann.",
    }

    def __init__(self, url, model, max_parallel=4, timeout=45):
        self.url = str(url).rstrip("/")
        self.model = model
        self.max_parallel = max(1, int(max_parallel))
        self.timeout = timeout

    def _run_role(self, role, request):
        prompt = (
            f"Rolle: {role}\n"
            f"Auftrag: {request}\n"
            f"Aufgabe: {self.ROLE_PROMPTS[role]}\n"
            "Antworte auf Deutsch in maximal zwei kurzen Sätzen. "
            "Führe keine Tools aus und behaupte keine ausgeführten Aktionen."
        )
        response = requests.post(
            f"{self.url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "2m",
                "options": {"num_predict": 96, "num_ctx": 1024, "temperature": 0.1},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        answer = str(data.get("response", "")).strip()
        return answer or "Keine Rollenbewertung erhalten."

    def run(self, request):
        roles = list(self.ROLE_PROMPTS)
        results = {}
        errors = {}
        with ThreadPoolExecutor(max_workers=self.max_parallel, thread_name_prefix="jarvis-agent") as pool:
            futures = {pool.submit(self._run_role, role, request): role for role in roles}
            for future in as_completed(futures):
                role = futures[future]
                try:
                    results[role] = future.result()
                except (OSError, requests.RequestException, ValueError) as exc:
                    errors[role] = str(exc)
        ordered = [f"- {role}: {results[role]}" for role in roles if role in results]
        if errors:
            ordered.extend(f"- {role}: nicht verfügbar ({error})" for role, error in errors.items())
        return {
            "ok": len(results) > 0,
            "roles": roles,
            "completed": list(results),
            "errors": errors,
            "context": "\n".join(ordered),
        }
