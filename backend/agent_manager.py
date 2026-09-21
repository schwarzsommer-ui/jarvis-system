from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from threading import RLock
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class AgentState:
    name: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    status: str = 'online'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'role': self.role,
            'capabilities': list(self.capabilities),
            'status': self.status,
            'metadata': dict(self.metadata),
        }


class AgentManager:
    MAX_SUBAGENTS_PER_PARENT = 16
    MAX_DYNAMIC_AGENTS = 48

    def __init__(self) -> None:
        self._agents: Dict[str, AgentState] = {}
        self._lock = RLock()
        self._role_config = self._load_role_config()
        self.register('planner', 'planner', ['plan', 'prioritize', 'summarize'])
        self.register('researcher', 'researcher', ['search', 'read', 'filter'])
        self.register('operator', 'operator', ['desktop', 'navigate', 'simulate'])
        self.register('coder', 'coder', ['edit', 'test', 'patch'])
        self.register('memory', 'memory', ['store', 'recall', 'persist'])
        self.register('verifier', 'verifier', ['verify', 'validate', 'check'])
        self.register('vision', 'vision', ['screen', 'ocr', 'ui'])
        self.register('integrations', 'integrations', ['webhook', 'api', 'services'])
        self.register('workflow', 'workflow', ['compose', 'sequence', 'state'])
        self.register('monitor', 'monitor', ['health', 'changes', 'alerts'])
        self.register('recovery', 'recovery', ['retry', 'fallback', 'diagnose'])
        self.register('security', 'security', ['risk', 'permissions', 'confirm'])
        self.register('scheduler', 'scheduler', ['schedule', 'reminder', 'routine'])
        self.register('documents', 'documents', ['pdf', 'docx', 'xlsx', 'ocr'])
        self.register('voice', 'voice', ['speech', 'transcribe', 'speak'])
        self.register('deployment', 'deployment', ['syntax', 'tests', 'logs', 'service'])
        self.register('calendar', 'calendar', ['calendar', 'events', 'availability'])
        self.register('email', 'email', ['email', 'draft', 'attachments'])
        self.register('messaging', 'messaging', ['telegram', 'discord', 'slack', 'messages'])
        self.register('rag', 'rag', ['retrieval', 'indexing', 'citations'])
        self.register('trading', 'trading', ['market_readonly', 'watchlist', 'risk_analysis'])
        self.register('infrastructure', 'infrastructure', ['dependencies', 'runtime', 'health'])
        self.register('media', 'media', ['video', 'audio', 'transcription'])
        self._apply_role_config()

    @staticmethod
    def _load_role_config() -> Dict[str, Any]:
        path = Path(__file__).resolve().parent.parent / 'config' / 'agent_roles.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            return {}
        roles = data.get('roles', {})
        return roles if isinstance(roles, dict) else {}

    def _apply_role_config(self) -> None:
        for name, config in self._role_config.items():
            agent = self._agents.get(name)
            if agent is None or not isinstance(config, dict):
                continue
            agent.metadata.update({
                'purpose': config.get('purpose', ''),
                'preferred_nvidia_models': list(
                    config.get('preferred_nvidia_models', [])
                ),
                'skills': list(config.get('skills', [])),
                'provider': 'nvidia_nim_with_local_fallback',
            })

    def register(self, name: str, role: str, capabilities: Optional[Iterable[str]] = None, **metadata: Any) -> AgentState:
        if not name or name in self._agents:
            raise ValueError(f'Agent name is unavailable: {name}')
        state = AgentState(name=name, role=role, capabilities=list(capabilities or []), metadata=dict(metadata))
        self._agents[name] = state
        return state

    def hire_subagents(
        self,
        parent_name: str,
        task_id: str,
        requests: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Create bounded, task-scoped child agents for a registered parent."""
        with self._lock:
            parent = self._agents.get(parent_name)
            if parent is None:
                raise KeyError(f'Unknown parent agent: {parent_name}')
            if parent.metadata.get('parent_agent'):
                raise ValueError('Subagents may not hire another generation')

            requested = list(requests)
            if not requested or len(requested) > self.MAX_SUBAGENTS_PER_PARENT:
                raise ValueError(
                    f'At most {self.MAX_SUBAGENTS_PER_PARENT} subagents may be hired per request'
                )
            dynamic_count = sum(
                1 for agent in self._agents.values()
                if agent.metadata.get('dynamic_subagent')
            )
            if dynamic_count + len(requested) > self.MAX_DYNAMIC_AGENTS:
                raise ValueError('Dynamic agent capacity is exhausted')

            hired: List[Dict[str, Any]] = []
            existing_capabilities = {
                capability
                for agent in self._agents.values()
                for capability in agent.capabilities
            }
            for index, request in enumerate(requested, start=1):
                if not isinstance(request, dict):
                    raise ValueError('Each subagent request must be an object')
                role = str(request.get('role', '')).strip().lower()
                capabilities = list(dict.fromkeys(
                    str(item).strip().lower()
                    for item in request.get('capabilities', [])
                    if str(item).strip()
                ))
                if not role or not capabilities:
                    raise ValueError('Each subagent needs a role and capabilities')
                if any(len(item) > 80 for item in capabilities):
                    raise ValueError('A capability name is too long')
                existing = next(
                    (
                        agent for agent in self._agents.values()
                        if agent.metadata.get('dynamic_subagent')
                        and agent.metadata.get('task_id') == str(task_id)
                        and set(capabilities).issubset(set(agent.capabilities))
                    ),
                    None,
                )
                if existing is not None:
                    hired.append(existing.to_dict())
                    continue
                name_hint = str(request.get('name', '')).strip().lower()
                suffix = re.sub(r'[^a-z0-9_-]+', '-', name_hint).strip('-') if name_hint else role
                name = f'{parent_name}.subagent.{suffix or index}'
                if name in self._agents:
                    name = f'{name}-{index}'
                state = self.register(
                    name,
                    role,
                    capabilities,
                    dynamic_subagent=True,
                    parent_agent=parent_name,
                    task_id=str(task_id),
                    depth=1,
                    purpose=str(request.get('purpose', '')).strip(),
                    expires_with_task=True,
                    capability_gap=not all(item in existing_capabilities for item in capabilities),
                )
                state.status = 'busy'
                hired.append(state.to_dict())
            return hired

    def hire_for_missing_capabilities(
        self,
        parent_name: str,
        task_id: str,
        missing_capabilities: Iterable[str],
    ) -> List[Dict[str, Any]]:
        """Translate detected capability gaps into task-scoped specialist bots."""
        capabilities = list(dict.fromkeys(
            str(item).strip().lower()
            for item in missing_capabilities
            if str(item).strip()
        ))
        requests = [
            {
                'name': capability.replace(' ', '-'),
                'role': f'{capability}-specialist',
                'capabilities': [capability],
                'purpose': f'Handle the missing capability: {capability}',
            }
            for capability in capabilities[: self.MAX_SUBAGENTS_PER_PARENT]
        ]
        return self.hire_subagents(parent_name, task_id, requests)

    def release_task_subagents(self, task_id: str) -> List[str]:
        """Retire temporary child agents when their parent task is complete."""
        with self._lock:
            retired: List[str] = []
            for name, agent in list(self._agents.items()):
                if agent.metadata.get('dynamic_subagent') and agent.metadata.get('task_id') == str(task_id):
                    retired.append(name)
                    del self._agents[name]
            return retired

    def list_agents(self) -> List[Dict[str, Any]]:
        return [agent.to_dict() for agent in self._agents.values()]

    def get_agent(self, name: str) -> Optional[AgentState]:
        return self._agents.get(name)

    def set_status(self, name: str, status: str) -> Optional[AgentState]:
        agent = self._agents.get(name)
        if agent is not None:
            agent.status = str(status)
        return agent

    def assign_task(self, task_id: str, task_kind: str, agent_name: Optional[str] = None) -> Dict[str, Any]:
        name = agent_name or self._select_agent(task_kind)
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f'Unknown agent: {name}')
        agent.status = 'busy'
        return {'task_id': task_id, 'agent': agent.to_dict(), 'status': 'assigned'}

    def _select_agent(self, task_kind: str) -> str:
        role_map = {
            'research': 'researcher',
            'desktop': 'operator',
            'code': 'coder',
            'memory': 'memory',
            'verify': 'verifier',
            'verification': 'verifier',
        }
        return role_map.get(task_kind, 'planner')

    def route_prompt(self, prompt: str) -> Dict[str, Any]:
        """Select one accountable lead and bounded specialists for a request."""
        text = str(prompt or "").lower()
        signals = {
            "researcher": ("suche", "recherche", "aktuell", "news", "quelle", "preis"),
            "operator": ("öffne", "oeffne", "offne", "öffme", "offme", "klick", "tippe", "browser", "app", "fenster", "desktop"),
            "coder": ("code", "python", "projekt", "debug", "fehler", "testen", "reparier", "build"),
            "memory": ("merk dir", "merke", "speicher", "präferenz", "routine", "zweites gehirn"),
            "vision": ("bildschirm", "screenshot", "ocr", "button erkennen", "sichtbar"),
            "integrations": ("make", "webhook", "api", "telegram", "netlify", "kalender"),
            "workflow": ("workflow", "mehrschritt", "und dann", "danach", "automatis"),
            "monitor": ("überwach", "monitor", "alarm", "status prüfen", "änderung"),
            "recovery": ("fehlgeschlagen", "wiederholen", "reparier", "fallback", "geht nicht"),
            "security": ("sicher", "berechtigung", "passwort", "risiko", "bestätigung", "loesche", "lösche", "kaufen", "verkaufen"),
            "scheduler": ("später", "täglich", "wöchentlich", "erinner", "zeitplan"),
            "documents": ("pdf", "word", "docx", "tabelle", "xlsx", "präsentation", "ocr"),
            "voice": ("sprache", "stimme", "vorlesen", "wakeword", "voice"),
            "deployment": ("deploy", "starten", "service", "logs", "syntax", "build"),
            "calendar": ("kalender", "termin", "meeting", "calendar", "zeitfenster"),
            "email": ("email", "e-mail", "mail", "anhang", "postfach"),
            "messaging": ("telegram", "discord", "slack", "nachricht", "messenger"),
            "rag": ("rag", "wissen", "dokumenten-suche", "semantisch", "quellenbeleg"),
            "trading": ("tradingview", "watchlist", "aktie", "markt", "portfolio"),
            "infrastructure": ("abhängigkeit", "paket", "installier", "dienst", "runtime"),
            "media": ("youtube", "video", "audio", "transkrib", "podcast"),
        }
        scores = {role: 0 for role in signals}
        scores.update({"planner": 1, "verifier": 1})
        for role, keywords in signals.items():
            scores[role] += sum(1 for keyword in keywords if keyword in text)
        if any(marker in text for marker in ("second brain", "secondbrain", "merk dir", "merke", "speicher")):
            scores["memory"] = max(scores["memory"], max(scores.values()) + 1)
        domain_roles = tuple(role for role in scores if role not in {"planner", "verifier"})
        domain_lead = max(domain_roles, key=lambda role: scores[role])
        lead = domain_lead if scores[domain_lead] > 0 else "recovery"
        specialists = [lead]
        if len(text.split()) > 10 or any(marker in text for marker in ("und dann", "workflow", "automatis", "vollständig")):
            specialists.extend(
                role for role in scores
                if role not in {lead, "planner", "verifier"} and scores[role] > 0
            )
        if lead == "recovery" or not any(scores[role] > 0 for role in domain_roles):
            specialists.extend(["planner", "researcher", "verifier"])
        elif lead != "planner":
            specialists.append("planner")
        specialists.append("verifier")
        specialists = list(dict.fromkeys(specialists))[:4]
        missing = self.detect_missing_capabilities(text)
        analysis = self.analyze_prompt(prompt, scores=scores, missing_capabilities=missing)
        if analysis["confidence"] == "low" and "recovery" not in specialists:
            specialists.insert(0, "recovery")
            specialists = list(dict.fromkeys(specialists))[:4]
        return {
            "lead": lead,
            "specialists": specialists,
            "scores": scores,
            "missing_capabilities": missing,
            "analysis": analysis,
            "policy": "adaptive_specialists_with_verifier",
        }

    def analyze_prompt(
        self,
        prompt: str,
        scores: Optional[Dict[str, int]] = None,
        missing_capabilities: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """Create a small, inspectable intent record before an agent acts."""
        text = re.sub(r"\s+", " ", str(prompt or "").strip().casefold())
        normalized = (
            text.replace("ä", "a")
            .replace("ö", "o")
            .replace("ü", "u")
            .replace("ß", "ss")
        )
        intent_rules = (
            ("memory", ("second brain", "secondbrain", "merk dir", "speicher", "merke")),
            ("desktop", ("öffne", "oeffne", "offne", "öffme", "offme", "starte", "klick", "fenster")),
            ("research", ("suche", "recherche", "aktuell", "news", "quelle", "preis")),
            ("trading", ("tradingview", "btc", "eth", "xau", "gold", "markt", "chart")),
            ("code", ("code", "python", "debug", "reparier", "testen")),
            ("voice", ("sprache", "stimme", "vorlesen", "wake word", "wakeword")),
            ("security", ("lösche", "loesche", "kaufen", "verkaufen", "senden", "passwort", "konto")),
            ("status", ("status", "zustand", "funktioniert")),
        )
        matches = [
            kind for kind, keywords in intent_rules
            if any(keyword in normalized for keyword in keywords)
        ]
        intent = matches[0] if matches else "general"
        score_map = scores or {}
        domain_scores = {
            key: value for key, value in score_map.items()
            if key not in {"planner", "verifier"}
        }
        ordered = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
        domain_ordered = sorted(domain_scores.items(), key=lambda item: item[1], reverse=True)
        top_score = domain_ordered[0][1] if domain_ordered else 0
        second_score = domain_ordered[1][1] if len(domain_ordered) > 1 else 0
        confidence = "high" if top_score >= 2 and top_score > second_score else (
            "medium" if top_score > 0 else "low"
        )
        missing = list(dict.fromkeys(str(item) for item in (missing_capabilities or [])))
        entities = {
            "urls": re.findall(r"https?://\S+", text),
            "markets": re.findall(
                r"\b(?:btc(?:\s*/?\s*(?:usd|usdt))?|eth(?:\s*/?\s*(?:usd|usdt))?|"
                r"xau(?:\s*/?\s*usd)?|gold|dxy)\b",
                normalized,
            ),
        }
        return {
            "intent": intent,
            "primary_intent": intent,
            "secondary_intents": matches[1:],
            "confidence": confidence,
            "normalized_text": normalized[:500],
            "entities": entities,
            "requested_action": (
                "execute" if any(word in normalized for word in (
                    "oeffne", "öffne", "offne", "starte", "klick", "speicher", "suche",
                )) else "answer"
            ),
            "risk_level": (
                "high" if any(word in normalized for word in (
                    "lösche", "loesche", "kaufen", "verkaufen", "senden",
                    "passwort", "konto",
                )) else "normal"
            ),
            "requires_confirmation": any(word in normalized for word in (
                "lösche", "loesche", "kaufen", "verkaufen", "senden",
                "passwort", "konto",
            )),
            "ambiguities": (["missing_capability"] if missing else [])
                + ([] if matches else ["intent_not_explicit"]),
            "recovery_required": bool(missing or confidence == "low"),
            "recovery_plan": (
                [
                    "inspect_registered_agents",
                    "search_local_skills",
                    "propose_bounded_extension",
                    "verify_before_execution",
                ]
                if missing else (
                    ["ask_clarifying_question"]
                    if confidence == "low" else []
                )
            ),
            "missing_capabilities": missing,
            "candidate_agents": [item[0] for item in ordered[:4] if item[1] > 0],
        }

    def detect_missing_capabilities(self, prompt: str) -> List[str]:
        """Detect explicit capability gaps before an agent starts work."""
        text = str(prompt or '').lower()
        hints = {
            'kalender': 'calendar',
            'calendar': 'calendar',
            'excel': 'spreadsheet',
            'xlsx': 'spreadsheet',
            'youtube': 'video-analysis',
            'tradingview': 'market-dashboard',
            'email': 'email',
            'e-mail': 'email',
            'telegram': 'telegram',
            'übersetzen': 'translation',
            'translate': 'translation',
        }
        capability_aliases = {
            'spreadsheet': 'documents',
            'video-analysis': 'media',
            'market-dashboard': 'trading',
            'translation': 'researcher',
        }
        known = {
            capability
            for agent in self._agents.values()
            if not agent.metadata.get('dynamic_subagent')
            for capability in (*agent.capabilities, agent.name)
        }
        return list(dict.fromkeys(
            capability for keyword, capability in hints.items()
            if keyword in text
            and capability not in known
            and capability_aliases.get(capability, capability) not in known
        ))

    def release(self, agent_name: str) -> None:
        agent = self._agents.get(agent_name)
        if agent is not None:
            agent.status = 'online'
