"""Runtime bridge for optional integrations installed outside Jarvis' main venv."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class IntegrationRuntime:
    """Discover and health-check optional adapters without importing them in-process."""

    MODULES = {
        "crewai": "crewai",
        "autogen": "autogen",
        "langgraph": "langgraph",
        "langchain": "langchain",
        "browser_use": "browser_use",
        "playwright": "playwright",
        "crawl4ai": "crawl4ai",
        "mem0": "mem0",
        "graphiti": "graphiti_core",
        "supabase": "supabase",
        "qdrant": "qdrant_client",
        "openai": "openai",
        "anthropic": "anthropic",
        "faster_whisper": "faster_whisper",
        "livekit": "livekit",
        "groq": "groq",
    }

    SERVICES = {
        "ollama": "http://127.0.0.1:11434",
        "jarvis_backend": "http://127.0.0.1:8787",
        "jarvis_dashboard": "http://127.0.0.1:8000",
        "open_webui": "http://127.0.0.1:3000",
        "langflow": "http://127.0.0.1:7860",
        "n8n": "http://127.0.0.1:5678",
        "qdrant": "http://127.0.0.1:6333",
        "supabase": "http://127.0.0.1:54321",
    }

    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[1]
        configured = os.getenv("JARVIS_INTEGRATION_PYTHON", "C:\\jv-integrations\\Scripts\\python.exe")
        self.python = Path(configured)

    def _external_modules(self) -> dict[str, bool]:
        if not self.python.exists():
            return {name: False for name in self.MODULES}
        script = (
            "import importlib.util, json; names="
            + repr(list(self.MODULES.values()))
            + "; print(json.dumps({n: bool(importlib.util.find_spec(n)) for n in names}))"
        )
        try:
            result = subprocess.run(
                [str(self.python), "-c", script],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            values = json.loads(result.stdout.strip()) if result.returncode == 0 else {}
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            values = {}
        return {name: bool(values.get(module)) for name, module in self.MODULES.items()}

    def status(self) -> dict[str, Any]:
        modules = {
            name: bool(importlib.util.find_spec(module))
            for name, module in self.MODULES.items()
        }
        external = self._external_modules()
        merged = {name: modules[name] or external[name] for name in self.MODULES}
        service_checks = {
            "ollama": self._reachable(self.SERVICES["ollama"] + "/api/tags"),
            "jarvis_backend": self._reachable(self.SERVICES["jarvis_backend"] + "/health"),
            "jarvis_dashboard": self._reachable(self.SERVICES["jarvis_dashboard"]),
            "open_webui": self._reachable(self.SERVICES["open_webui"]),
            "langflow": self._reachable(self.SERVICES["langflow"]),
            "n8n": self._reachable(self.SERVICES["n8n"] + "/healthz"),
            "qdrant": self._reachable(self.SERVICES["qdrant"] + "/collections"),
            "supabase": bool(os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")),
        }
        return {
            "python": str(self.python),
            "python_available": self.python.exists(),
            "modules": merged,
            "services": dict(self.SERVICES),
            "service_checks": service_checks,
        }

    @staticmethod
    def _reachable(url: str) -> bool:
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=2):
                return True
        except (OSError, urllib.error.URLError):
            return False

    def available_capabilities(self) -> list[str]:
        return [name for name, available in self.status()["modules"].items() if available]
