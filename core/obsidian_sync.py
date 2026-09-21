from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class ObsidianSync:
    """Write local, redacted J.A.R.V.I.S. notes into an Obsidian vault."""

    def __init__(self, vault_path: Optional[str] = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        configured = vault_path or os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
        self.vault = self._resolve_vault(project_root, configured)
        self.enabled = self.vault is not None
        if self.vault:
            for folder in ("JARVIS", "JARVIS/Conversations", "JARVIS/Audit", "JARVIS/Knowledge"):
                (self.vault / folder).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_vault(project_root: Path, configured: str) -> Optional[Path]:
        candidates = []
        if configured:
            candidates.append(Path(configured).expanduser())
        candidates.extend((
            Path.home() / "Documents" / "Obsidian Vault",
            Path.home() / "Documents" / "Obsidian",
            project_root / "Obsidian",
        ))
        for candidate in candidates:
            if candidate.is_dir() and (
                (candidate / ".obsidian").is_dir()
                or candidate.name.lower() in {"obsidian", "obsidian vault"}
            ):
                return candidate.resolve()
        fallback = project_root / "Obsidian"
        fallback.mkdir(parents=True, exist_ok=True)
        (fallback / ".obsidian").mkdir(exist_ok=True)
        app_config = fallback / ".obsidian" / "app.json"
        if not app_config.exists():
            app_config.write_text(
                json.dumps({"showLineNumber": False, "livePreview": True}, indent=2),
                encoding="utf-8",
            )
        return fallback.resolve()

    @staticmethod
    def redact(value: Any) -> str:
        text = str(value or "")
        text = re.sub(
            r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            text,
        )
        return text[:12000]

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "vault_present": bool(self.vault),
            "vault_path": str(self.vault) if self.vault else None,
            "mode": "local_markdown_only",
            "rag_enabled": False,
        }

    def sync_interaction(
        self,
        prompt: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.vault:
            return None
        now = datetime.now()
        day_path = self.vault / "JARVIS" / "Conversations" / f"{now:%Y-%m-%d}.md"
        meta = metadata or {}
        block = (
            f"\n## {now:%H:%M:%S} — J.A.R.V.I.S.\n"
            f"**Intent:** `{self.redact(meta.get('intent', ''))}`  \n"
            f"**Agent:** `{self.redact(meta.get('lead_agent', ''))}`  \n\n"
            f"**Auftrag**\n{self.redact(prompt)}\n\n"
            f"**Antwort**\n{self.redact(response)}\n"
        )
        with day_path.open("a", encoding="utf-8") as handle:
            handle.write(block)
        return str(day_path)

    def sync_user_input(self, prompt: str, source: str = "user") -> Optional[str]:
        if not self.vault:
            return None
        now = datetime.now()
        day_path = self.vault / "JARVIS" / "Conversations" / f"{now:%Y-%m-%d}.md"
        block = (
            f"\n## {now:%H:%M:%S} — Eingang\n"
            f"**Quelle:** `{self.redact(source)}`  \n\n"
            f"**Auftrag**\n{self.redact(prompt)}\n"
        )
        with day_path.open("a", encoding="utf-8") as handle:
            handle.write(block)
        return str(day_path)

    def sync_graph(self, graph: Dict[str, Any]) -> Optional[str]:
        if not self.vault:
            return None
        target = self.vault / "JARVIS" / "Knowledge" / "memory-graph.json"
        target.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def write_nightly_review(self, memory: Dict[str, Any]) -> Optional[str]:
        """Persist a bounded reflection without taking actions or changing permissions."""
        if not self.vault:
            return None
        now = datetime.now()
        target = self.vault / "JARVIS" / "Knowledge" / f"{now:%Y-%m-%d}-nightly-review.md"
        conversations = memory.get("conversation", [])
        preferences = memory.get("preferences", [])
        lines = [
            f"# Nightly review — {now:%Y-%m-%d}",
            "",
            "Diese Notiz ist eine Beobachtung des lokalen Verlaufs. "
            "Sie erteilt keine neuen Berechtigungen und führt keine externen Aktionen aus.",
            "",
            f"- Gespräche gespeichert: {len(conversations) if isinstance(conversations, list) else 0}",
            f"- Präferenzen gespeichert: {len(preferences) if isinstance(preferences, list) else 0}",
            "",
            "## Hinweise für morgen",
            "- Offene Aufgaben und Präferenzen im Dashboard prüfen.",
            "- Externe Aktionen weiterhin ausdrücklich bestätigen.",
        ]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(target)

    def audit(self, event: Dict[str, Any]) -> Optional[str]:
        if not self.vault:
            return None
        now = datetime.now()
        target = self.vault / "JARVIS" / "Audit" / f"{now:%Y-%m-%d}.md"
        safe = {key: self.redact(value) for key, value in event.items()}
        lines = [f"\n### {now:%H:%M:%S}", *[f"- **{key}:** {value}" for key, value in safe.items()]]
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        return str(target)
