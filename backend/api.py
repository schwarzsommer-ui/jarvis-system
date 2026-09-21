from __future__ import annotations

import asyncio
import ast
import json
import os
import psutil
import re
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from .agent_manager import AgentManager
from .desktop_executor import DesktopExecutor
from .live_publisher import LiveEventPublisher
from .skill_loader import SkillLoader
from core.skill_manager import SkillManager
from .supervisor import Supervisor
from .task_queue import TaskQueue
from .telegram_queue_sync import TelegramQueueSync
from .scheduler_registry import SchedulerRegistry
from .scheduler_runner import SchedulerRunner
from .workflow_registry import WorkflowRegistry
from .executor_bridge.auto_confirm import create_request
from .executor_bridge.request_store import RequestStore
from .executor_bridge.safety import send_safety_event
from core.brain import JarvisBrain
from core.audit_log import AuditLog
from .permission_registry import PermissionRegistry
from core.obsidian_sync import ObsidianSync
from core.project_runner import ProjectRunner
from core.github_importer import GitHubImporter, GitHubImportError
from core.integration_runtime import IntegrationRuntime
from .live_integrations import (
    crawl_url,
    plan_with_langgraph,
    search_memory as qdrant_search_memory,
    upsert_memory as qdrant_upsert_memory,
)


def _human_response(value: Any) -> str:
    """Return the user-facing sentence, never the internal tool envelope."""
    if isinstance(value, dict):
        for key in ('response', 'message', 'summary', 'text'):
            if value.get(key):
                return _human_response(value[key])
        results = value.get('results')
        if isinstance(results, list) and results:
            last = results[-1]
            if isinstance(last, dict):
                return _human_response(last.get('result', last))
        return 'Die Aufgabe wurde verarbeitet.'
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(('{', '[')):
            try:
                return _human_response(ast.literal_eval(text))
            except (ValueError, SyntaxError):
                pass
        return text
    return str(value)


def _response_status(prompt: str, response: str) -> str:
    """Map execution evidence to an honest API status."""
    lowered = str(response or "").casefold()
    if any(marker in lowered for marker in (
        "action_failed", "aktion fehlgeschlagen", "fehlgeschlagen",
        "konnte nicht", "nicht verifiziert", "nicht ausgefÃ¼hrt",
        "nicht ausgefuehrt", "simulation", "simuliert", "demo",
    )):
        return "failed"
    if any(marker in lowered for marker in (
        "bestÃ¤tigung", "bestaetigung", "confirmation_required",
    )):
        return "confirmation_required"
    return "completed"


INTEGRATION_SETUP = {
    'nvidia': {
        'name': 'NVIDIA NIM',
        'login_url': 'https://build.nvidia.com/',
        'required_env': ['NIM_API_KEY'],
        'mode': 'api_key',
    },
    'make': {
        'name': 'Make.com',
        'login_url': 'https://www.make.com/en/login',
        'required_env': ['MAKE_WEBHOOK_URL'],
        'mode': 'webhook',
    },
    'telegram': {
        'name': 'Telegram',
        'login_url': 'https://web.telegram.org/',
        'required_env': ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'],
        'mode': 'bot_token',
    },
    'google_calendar': {
        'name': 'Google Calendar',
        'login_url': 'https://calendar.google.com/',
        'required_env': ['GOOGLE_CALENDAR_CREDENTIALS'],
        'mode': 'oauth_or_browser_session',
    },
    'outlook': {
        'name': 'Outlook',
        'login_url': 'https://outlook.live.com/calendar/',
        'required_env': ['MICROSOFT_GRAPH_TOKEN'],
        'mode': 'oauth_or_browser_session',
    },
    'discord': {
        'name': 'Discord',
        'login_url': 'https://discord.com/login',
        'required_env': ['DISCORD_WEBHOOK_URL'],
        'mode': 'webhook',
    },
    'slack': {
        'name': 'Slack',
        'login_url': 'https://app.slack.com/signin',
        'required_env': ['SLACK_WEBHOOK_URL'],
        'mode': 'webhook',
    },
    'elevenlabs': {
        'name': 'ElevenLabs',
        'login_url': 'https://elevenlabs.io/app/sign-in',
        'required_env': ['ELEVENLABS_API_KEY', 'ELEVENLABS_VOICE_ID'],
        'mode': 'api_key',
    },
}


def create_app() -> FastAPI:
    app = FastAPI(title='Jarvis V2', version='0.1.0', description='Bounded safe Jarvis foundation')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.publisher = LiveEventPublisher()
    app.state.memory = None
    app.state.pending_confirmations = {}
    app.state.pending_capability_repairs = {}
    app.state.project_runner = ProjectRunner(workspace=Path(__file__).resolve().parent.parent)
    app.state.project_plans = {}
    app.state.github_importer = GitHubImporter(
        workspace=Path(__file__).resolve().parent.parent,
    )
    app.state.github_import_plans = {}
    app.state.skill_loader = SkillLoader()
    app.state.skill_manager = SkillManager()
    app.state.agent_manager = AgentManager()
    app.state.task_queue = TaskQueue()
    app.state.telegram_queue = None
    app.state.scheduler = SchedulerRegistry()
    app.state.supervisor = Supervisor()
    app.state.desktop = DesktopExecutor()
    from core.monitoring import LocalMonitoring
    app.state.live_monitoring = LocalMonitoring(timeout=8)
    app.state.request_store = RequestStore()
    from .performance_mode import PerformanceMode
    app.state.performance = PerformanceMode()
    app.state.brain = JarvisBrain()
    app.state.integrations = IntegrationRuntime()
    # All runtime memory writes go through the same Second Brain instance.
    app.state.memory = app.state.brain.memory
    app.state.workflow_registry = WorkflowRegistry(
        desktop=app.state.desktop,
        browser_executor=app.state.brain.tools.execute_structured,
        research_handler=lambda query: app.state.brain.tools.execute_structured(
            'search_web', query=query
        ),
        monitoring=app.state.live_monitoring,
    )
    app.state.audit = AuditLog()
    app.state.permissions = PermissionRegistry(audit=app.state.audit)
    app.state.obsidian = ObsidianSync()
    app.state.audit.set_sink(app.state.obsidian.audit)
    app.state.telegram_queue = TelegramQueueSync(
        app.state.task_queue,
        app.state.audit,
        app.state.publisher,
    )
    app.state.scheduler_runner = SchedulerRunner(
        app.state.scheduler,
        app.state.audit,
        app.state.obsidian,
        app.state.brain.memory,
        should_defer_heavy_work=app.state.performance.should_defer_heavy_work,
    )
    app.state.team_roles = {
        'planner': 'Zerlege die Aufgabe in klare, sichere Schritte.',
        'researcher': 'PrÃ¼fe notwendige aktuelle Informationen und nenne Unsicherheiten.',
        'operator': 'FÃ¼hre nur erlaubte Browser- und Desktop-Aktionen mit Verifikation aus.',
        'coder': 'Entwirf eine technisch belastbare Umsetzung und weise auf Tests hin.',
        'memory': 'Speichere nur ausdrÃ¼cklich mitgeteilte Fakten und Routinen lokal.',
        'verifier': 'Suche Fehler, Risiken und fehlende Voraussetzungen in der Aufgabe.',
    }
    app.state.team_active = False
    if not app.state.scheduler_runner._thread or not app.state.scheduler_runner._thread.is_alive():
        app.state.scheduler_runner.start()

    @app.on_event("startup")
    async def start_telegram_queue_sync() -> None:
        app.state.telegram_queue.start()
        app.state.audit.append("telegram_queue.started", {
            "enabled": app.state.telegram_queue.enabled,
            "interval_seconds": app.state.telegram_queue.interval,
        })

    @app.on_event("shutdown")
    async def stop_telegram_queue_sync() -> None:
        app.state.telegram_queue.stop()

    def rag_status() -> Dict[str, Any]:
        services = {
            'rag_server': 'http://127.0.0.1:8081/v1/health',
            'ingestor': 'http://127.0.0.1:8082/v1/health',
            'ui': 'http://127.0.0.1:8090',
        }
        checks: Dict[str, Any] = {}
        for name, url in services.items():
            try:
                with urllib.request.urlopen(url, timeout=1.5) as response:
                    checks[name] = {
                        'status': 'online',
                        'http_status': response.status,
                    }
            except urllib.error.HTTPError as exc:
                checks[name] = {
                    'status': 'error',
                    'http_status': exc.code,
                    'error': 'http_error',
                }
            except (urllib.error.URLError, TimeoutError, OSError):
                checks[name] = {
                    'status': 'offline',
                    'http_status': None,
                    'error': 'unreachable',
                }
        online = sum(1 for item in checks.values() if item['status'] == 'online')
        state = 'online' if online == len(checks) else 'degraded' if online else 'offline'
        return {'status': state, 'services': checks}

    def run_team(prompt: str) -> Dict[str, Any]:
        app.state.team_active = True
        results: Dict[str, Dict[str, Any]] = {}
        for role in app.state.team_roles:
            app.state.agent_manager.set_status(role, 'busy')
        app.state.publisher.publish('agents', {'agents': app.state.agent_manager.list_agents()})

        def run_role(role: str, instruction: str) -> tuple[str, Dict[str, Any]]:
            try:
                role_brain = JarvisBrain()
                agent = app.state.agent_manager.get_agent(role)
                metadata = agent.metadata if agent is not None else {}
                models = metadata.get('preferred_nvidia_models', [])
                skills = metadata.get('skills', [])
                role_prompt = (
                    f"Du bist die Rolle {role} im J.A.R.V.I.S.-Team. {instruction}\n\n"
                    f"Nutze diese passenden Skills als Arbeitsrahmen: {', '.join(skills)}.\n"
                    f"Bevorzugte NVIDIA-Modelle fÃ¼r diese Rolle: {', '.join(models)}.\n\n"
                    f"Aufgabe des Benutzers:\n{prompt}\n\n"
                    "Liefere ausschlieÃŸlich eine schriftliche Analyse. Nutze keine Tools, "
                    "Browser- oder Desktop-Aktionen und behaupte keine ausgefÃ¼hrten Aktionen."
                )
                content = str(role_brain.request_text(
                    role_prompt,
                    "Du bist ein interner Analyse-Agent. Keine Tools, keine externen Aktionen.",
                    [],
                ))
                failed = content.startswith(("NVIDIA", "Ollama", "Google AI", "OpenRouter", "OmniRoute"))
                return role, {'ok': not failed, 'content': content, 'provider': role_brain.provider}
            except Exception as exc:
                return role, {'ok': False, 'content': '', 'error': str(exc), 'provider': 'unavailable'}

        try:
            with ThreadPoolExecutor(max_workers=len(app.state.team_roles)) as pool:
                futures = [
                    pool.submit(run_role, role, instruction)
                    for role, instruction in app.state.team_roles.items()
                ]
                for future in as_completed(futures):
                    role, result = future.result()
                    results[role] = result

            successful = [item for item in results.values() if item.get('ok')]
            if not successful:
                return {
                    'status': 'failed',
                    'response': 'Kein Team-Agent konnte eine verlÃ¤ssliche Antwort liefern.',
                    'roles': results,
                }
            dossier = '\n\n'.join(
                f"[{role.upper()}]\n{results[role].get('content', '')}"
                for role in app.state.team_roles
                if role in results
            )
            synthesis = app.state.brain.request_text(
                "Du bist der Teamleiter von J.A.R.V.I.S. Fasse die folgenden parallelen "
                "BeitrÃ¤ge zu einer klaren Antwort zusammen. Erfinde nichts, markiere "
                "Unsicherheiten und fÃ¼hre keine externen Aktionen ohne BestÃ¤tigung aus.\n\n"
                f"Originalaufgabe:\n{prompt}\n\nTeambeitrÃ¤ge:\n{dossier}",
                "Du bist ein interner Team-Synthese-Agent. Keine Tools und keine externen Aktionen.",
                [],
            )
            app.state.publisher.publish('agents', {'agents': app.state.agent_manager.list_agents()})
            return {
                'status': 'completed' if len(successful) == len(results) else 'degraded',
                'response': str(synthesis),
                'roles': results,
            }
        finally:
            for role in app.state.team_roles:
                app.state.agent_manager.set_status(role, 'online')
            app.state.team_active = False
            app.state.publisher.publish('agents', {'agents': app.state.agent_manager.list_agents()})

    def agent_fallback_order(routing: Dict[str, Any]) -> List[str]:
        ordered: List[str] = []
        seen: set[str] = set()
        for name in [routing.get('lead'), *routing.get('specialists', [])]:
            if name and isinstance(name, str) and name not in seen:
                ordered.append(name)
                seen.add(name)
        for name in [
            'recovery', 'planner', 'researcher', 'operator', 'coder', 'memory',
            'verifier', 'workflow', 'monitor', 'integrations', 'voice', 'scheduler',
            'documents', 'security', 'deployment', 'calendar', 'email', 'messaging',
            'rag', 'trading', 'infrastructure', 'media',
        ]:
            if name not in seen:
                ordered.append(name)
                seen.add(name)
        return ordered

    async def resolve_agent_response(prompt: str, routing: Dict[str, Any]) -> tuple[str, str]:
        last_error = 'no_agent_response'

        def is_skill_dump(value: str) -> bool:
            lowered = value.casefold()
            return (
                'verfÃ¼gbare starke lokale skills:' in lowered
                or 'verfï¿½gbare starke lokale skills:' in lowered
            )

        def is_action_request(value: str) -> bool:
            lowered = re.sub(r'\s+', ' ', str(value or '')).casefold()
            return any(marker in lowered for marker in (
                'Ã¶ffne', 'oeffne', 'offne', 'starte', 'start', 'klick', 'click',
                'tippe', 'schicke', 'sende', 'speichere', 'save', 'lÃ¶sche', 'loesche',
                'delete', 'erstelle', 'create', 'installiere', 'installier', 'mache',
                'mach', 'aktiviere', 'Ã¶ffne', 'open', 'run', 'trigger', 'verarbeite'
            ))

        def is_unverified_action_claim(value: str, user_prompt: str) -> bool:
            cleaned = str(value or '').casefold().strip()
            if not cleaned or not is_action_request(user_prompt):
                return False
            if any(marker in cleaned for marker in (
                'erfolgreich ausgefÃ¼hrt', 'erfolgreich ausgefuehrt',
                'wurde geÃ¶ffnet', 'wurde geoeffnet', 'wurde gestartet',
                'wurde erstellt', 'wurde gespeichert', 'browser-sequenz erfolgreich',
                'ausgefÃ¼hrt wurde', 'ausgefuehrt wurde', 'ich habe es geÃ¶ffnet',
                'ich habe es gestartet'
            )):
                return True
            if re.search(r'\b(?:wurde|ist|sind)\s+(?:geÃ¶ffnet|geoeffnet|gestartet|erzeugt|gespeichert|gesendet)\b', cleaned):
                return True
            return False

        for agent_name in agent_fallback_order(routing):
            agent = app.state.agent_manager.get_agent(agent_name)
            if agent is None:
                continue
            app.state.agent_manager.set_status(agent_name, 'busy')
            try:
                role_prompt = (
                    f"Du bist der J.A.R.V.I.S.-Agent '{agent_name}'. "
                    "Nimm die Aufgabe mit deiner Spezialrolle und prÃ¼fe die sichere, "
                    "nÃ¤chste umsetzbare LÃ¶sung. Wenn der erste Pfad nicht verifizierbar ist, "
                    "springe zum nÃ¤chsten passenden Agenten. Keine Meta-ErklÃ¤rungen, keine "
                    "falschen Behauptungen Ã¼ber ausgefÃ¼hrte Aktionen.\n\n"
                    f"Aufgabe:\n{prompt}\n\n"
                    "Antworte direkt wie ein menschlicher Assistent: zuerst die wichtigste Aussage, "
                    "hÃ¶chstens drei kurze SÃ¤tze. Keine internen Rollen, Tools, JSON-Daten, URLs, "
                    "Verifikationsprotokolle oder technischen Metadaten."
                )
                response = await asyncio.to_thread(app.state.brain.ask, role_prompt)
                cleaned = str(response).strip()
                if is_skill_dump(cleaned):
                    direct = await asyncio.to_thread(
                        app.state.brain._process_request,
                        prompt,
                    )
                    direct_text = _human_response(direct)
                    if direct_text and not is_skill_dump(direct_text):
                        app.state.agent_manager.set_status(agent_name, 'online')
                        return direct_text, agent_name
                    cleaned = (
                        'Die Anfrage konnte nicht verlÃ¤sslich ausgefÃ¼hrt werden. '
                        'Ich habe deshalb keine Aktion als erfolgreich gemeldet.'
                    )
                if is_unverified_action_claim(cleaned, prompt):
                    cleaned = (
                        'Ich kann das lokal ausfÃ¼hren, aber ich behaupte keine Aktion ohne sichtbare Verifikation. '
                        'Bitte nenne das genaue Ziel oder den exakten Befehl.'
                    )
                if cleaned and not re.match(
                    r"^(ich kann|ich kann|kann ich|fehler|error|unable|nicht mÃ¶glich|nicht moeglich)",
                    cleaned.lower(),
                ):
                    app.state.agent_manager.set_status(agent_name, 'online')
                    return cleaned, agent_name
                last_error = cleaned or 'empty_response'
            except Exception as exc:  # pragma: no cover - defensive fallback path
                last_error = str(exc)
            finally:
                app.state.agent_manager.set_status(agent_name, 'online')
        fallback = (
            'Mehrere passende Agentenpfade wurden geprÃ¼ft, aber keiner konnte die AusfÃ¼hrung verlÃ¤sslich belegen. '
            'Bitte nenne die genauere App, den Zielpfad oder den gewÃ¼nschten Schritt; dann wechsle ich sofort auf den passenden Agenten.'
        )
        app.state.audit.append('agent_fallback', {'prompt': prompt[:500], 'last_error': last_error})
        return fallback, 'recovery'

    @app.get('/health')
    def health() -> Dict[str, Any]:
        return {
            'status': 'ok',
            'service': 'jarvis-v2',
            'safe_mode': True,
            'external_actions_simulated': False,
            'local_actions_live': True,
            'external_actions_live': False,
            'external_actions_require_confirmation': True,
            'telegram_queue': {
                'enabled': app.state.telegram_queue.enabled,
                'poll_seconds': app.state.telegram_queue.interval,
            },
            'rag': rag_status(),
        }

    @app.get('/telegram/queue/status')
    def telegram_queue_status() -> Dict[str, Any]:
        return {
            'enabled': app.state.telegram_queue.enabled,
            'poll_seconds': app.state.telegram_queue.interval,
            'configured': bool(app.state.telegram_queue.url),
        }

    @app.get('/performance')
    def performance() -> Dict[str, Any]:
        """Expose the low-overhead resource policy without process control."""
        return {'status': 'ok', **app.state.performance.snapshot()}

    @app.post('/performance/mode')
    def set_performance_mode(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Set automatic game detection or force performance mode on/off."""
        try:
            snapshot = app.state.performance.set_mode(str(payload.get('mode', 'auto')))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {'status': 'ok', **snapshot}

    @app.post('/telegram/queue/poll')
    def poll_telegram_queue() -> Dict[str, Any]:
        """Explicitly poll without executing any imported command."""
        return app.state.telegram_queue.poll_once()

    @app.post('/chat')
    async def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get('prompt', '')).strip()
        if not prompt:
            return {'status': 'rejected', 'error': 'prompt_required'}
        github_match = re.search(
            r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?',
            prompt,
            re.IGNORECASE,
        )
        if github_match:
            try:
                analysis = await asyncio.to_thread(
                    app.state.github_importer.analyze,
                    github_match.group(0),
                )
            except (GitHubImportError, OSError, ValueError, KeyError) as exc:
                return {
                    'status': 'failed',
                    'response': f'GitHub-Repository konnte nicht geprÃ¼ft werden: {exc}',
                    'provider': 'local-safety',
                    'model': 'rules',
                    'team': False,
                    'team_roles': [],
                }
            plan_id = uuid4().hex
            app.state.github_import_plans[plan_id] = {
                'url': analysis['source'],
                'created_at': datetime.now().isoformat(),
            }
            return {
                'status': 'github_confirmation_required',
                'response': (
                    f"Repository {analysis['owner']}/{analysis['repository']} wurde analysiert. "
                    'Soll ich die erlaubten Dateien isoliert in imports/ Ã¼bernehmen?'
                ),
                'plan_id': plan_id,
                'analysis': analysis,
                'requires_confirmation': True,
                'provider': 'local-safety',
                'model': 'rules',
                'team': False,
                'team_roles': [],
            }
        source = str(payload.get('source', 'user')).strip() or 'user'
        confirmation_id = str(payload.get('confirmation_id', '')).strip()
        confirmed_request = None
        if confirmation_id:
            confirmed_request = app.state.pending_confirmations.get(confirmation_id)
            if not confirmed_request:
                return {
                    'status': 'confirmation_expired',
                    'response': 'Diese BestÃ¤tigung ist abgelaufen. Bitte wiederhole die Aktion.',
                }
            if not bool(payload.get('confirmed', False)):
                return {
                    'status': 'cancelled',
                    'response': 'Abgebrochen. Ich habe nichts ausgefÃ¼hrt.',
                }
            prompt = confirmed_request['prompt']
            app.state.pending_confirmations.pop(confirmation_id, None)
        app.state.brain.memory.remember_user_input(prompt, source=source)
        app.state.obsidian.sync_user_input(prompt, source=source)
        routing_hint = app.state.agent_manager.route_prompt(prompt)
        analysis = routing_hint.get('analysis', {})
        app.state.memory.append('brain_analysis', {
            'prompt': prompt[:500],
            'source': source,
            'analysis': analysis,
            'lead': routing_hint.get('lead'),
            'specialists': routing_hint.get('specialists', []),
            'ts': datetime.now().isoformat(),
        })
        app.state.publisher.publish('brain.analyzed', {
            'intent': analysis.get('primary_intent', 'general'),
            'confidence': analysis.get('confidence', 'low'),
            'lead': routing_hint.get('lead'),
            'specialists': routing_hint.get('specialists', []),
        })
        casual = re.sub(r'[!?.,]+$', '', prompt.casefold()).strip()
        conversational_prompt = re.sub(
            r'^(?:(?:hey|hi|hallo|moin|guten morgen|guten tag|guten abend)'
            r'(?:\s+jarvis)?[\s,:-]*)+',
            '',
            casual,
        ).strip()
        is_knowledge_question = bool(re.search(
            r'^(?:was ist|was sind|wie funktioniert|wie funktioniert|warum|'
            r'wieso|wer ist|wer sind|erkl\w*|erklaere|erklaer|erklaer|'
            r'kannst du erklaeren|kannst du erklaeren|wie kann ich)\b',
            conversational_prompt,
        )) or prompt.rstrip().endswith('?')
        if is_knowledge_question:
            analysis['recovery_required'] = False
        if 'was kannst du' in conversational_prompt:
            response = (
                'Ich kann Fragen beantworten, aktuelle Informationen recherchieren, '
                'Aufgaben planen, Dateien und Projekte bearbeiten sowie erlaubte '
                'Browser- und Desktop-Aktionen ausfÃ¼hren. Bei Unklarheit frage ich '
                'nach; riskante externe Aktionen bestÃ¤tigst du direkt vor der AusfÃ¼hrung.'
            )
            app.state.memory.append('conversation', {
                'prompt': prompt,
                'response': response,
                'intent': 'capability_query',
                'provider': 'local',
                'model': 'rules',
            })
            return {
                'status': 'completed',
                'response': response,
                'provider': 'local',
                'model': 'rules',
                'team': False,
                'team_roles': [],
            }
        if (
            analysis.get('confidence') == 'low'
            and not analysis.get('missing_capabilities')
            and not is_knowledge_question
            and conversational_prompt not in {'', 'hey', 'hallo', 'hi', 'moin', 'guten morgen', 'guten tag', 'guten abend'}
        ):
            response = (
                'Ich verstehe das Ziel noch nicht eindeutig. '
                'Sag mir bitte kurz, was ich tun soll und in welcher App, Datei oder Webseite.'
            )
            app.state.publisher.publish('chat.clarification_required', {
                'prompt': prompt[:500],
                'reason': 'low_confidence',
            })
            app.state.memory.append('conversation', {
                'prompt': prompt,
                'response': response,
                'intent': 'clarification',
                'provider': 'local-safety',
                'model': 'rules',
            })
            return {
                'status': 'needs_clarification',
                'response': response,
                'provider': 'local-safety',
                'model': 'rules',
                'analysis': analysis,
            }
        if conversational_prompt in {'', 'hey', 'hallo', 'hi', 'moin', 'guten morgen', 'guten tag', 'guten abend'}:
            response = {
                'hey': 'Hey. Ich bin da. Was soll ich fÃ¼r dich tun?',
                '': 'Hallo. Ich bin da. Was soll ich fÃ¼r dich tun?',
                'hallo': 'Hallo. Was kann ich fÃ¼r dich erledigen?',
                'hi': 'Hi. Was brauchst du?',
                'moin': 'Moin. Was kann ich fÃ¼r dich tun?',
                'guten morgen': 'Guten Morgen. Was steht an?',
                'guten tag': 'Guten Tag. Was kann ich fÃ¼r dich erledigen?',
                'guten abend': 'Guten Abend. Was soll ich fÃ¼r dich tun?',
            }[conversational_prompt]
            app.state.memory.append('conversation', {
                'prompt': prompt,
                'response': response,
                'intent': 'casual',
                'provider': 'local',
                'model': 'rules',
            })
            return {
                'status': 'completed',
                'response': response,
                'provider': 'local',
                'model': 'rules',
                'team': False,
                'team_roles': [],
            }
        normalized_prompt = re.sub(r'\s+', ' ', prompt.casefold()).strip()
        if (
            re.search(r'\b(?:youtube|video)\b', normalized_prompt)
            and not re.search(
                r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+',
                normalized_prompt,
            )
        ):
            return {
                'status': 'needs_clarification',
                'response': (
                    'Welches Video soll ich analysieren? Bitte sende den vollstÃ¤ndigen '
                    'YouTube-Link oder nenne die genaue Datei.'
                ),
                'provider': 'local-safety',
                'model': 'rules',
                'team': False,
                'team_roles': [],
            }
        if re.search(
            r'\b(?:was ist der |wie ist der |zeige mir den |zeige den )?'
            r'(?:systemstatus|system status|pc-status|pc status|computerstatus|'
            r'systemzustand|status meines pcs)\b',
            normalized_prompt,
        ):
            result = await asyncio.to_thread(
                app.state.brain.tools.execute_structured,
                'system_status',
            )
            data = result.get('data', {}) if isinstance(result, dict) else {}
            if isinstance(result, dict) and result.get('ok'):
                response = (
                    f"Der Rechner ist online. CPU {data.get('cpu_percent', 'unbekannt')} Prozent, "
                    f"Arbeitsspeicher {data.get('memory_percent', 'unbekannt')} Prozent belegt, "
                    f"Festplatte {data.get('disk_percent', 'unbekannt')} Prozent belegt."
                )
            else:
                response = _human_response(result)
            return {
                'status': 'completed' if isinstance(result, dict) and result.get('ok') else 'failed',
                'response': response,
                'provider': 'local-desktop',
                'model': 'allowlist',
                'team': False,
                'team_roles': [],
            }
        if not payload.get('team'):
            fast_action = _fast_desktop_command(prompt)
            if fast_action is not None:
                return {
                    'status': _response_status(prompt, fast_action),
                    'response': fast_action,
                    'provider': 'local-desktop',
                    'model': 'allowlist',
                    'team': False,
                    'team_roles': [],
                }
        if (
            'second brain' in normalized_prompt
            or 'secondbrain' in normalized_prompt
        ) and (
            'automatisch' in normalized_prompt
            or 'alles was ich' in normalized_prompt
            or 'mach das' in normalized_prompt
            or 'beste' in normalized_prompt
        ):
            response = (
                'Erledigt. Ab jetzt speichere ich jede deiner Eingaben lokal im Second Brain, '
                'inklusive Zeit, Quelle und Zusammenhang. Zugangsdaten werden vorher ausgeblendet.'
            )
            app.state.obsidian.sync_interaction(
                prompt,
                response,
                {'intent': 'MemoryIntent', 'lead_agent': 'memory'},
            )
            return {
                'status': _response_status(prompt, response),
                'response': response,
                'provider': 'local-memory',
                'model': 'local',
                'team': False,
                'team_roles': [],
            }
        if normalized_prompt in {'mach das was am besten ist', 'mach das beste'}:
            response = (
                'Erledigt. Ich verwende dafÃ¼r die lokale Speicherung im Second Brain '
                'und sichere jede neue Eingabe automatisch.'
            )
            app.state.obsidian.sync_interaction(
                prompt,
                response,
                {'intent': 'MemoryIntent', 'lead_agent': 'memory'},
            )
            return {
                'status': 'completed',
                'response': response,
                'provider': 'local-memory',
                'model': 'local',
                'team': False,
                'team_roles': [],
            }
        if re.search(r'\b(?:Ã¶ffne|oeffne|Ã¶ffme|offme)\s+trading\s*view\b', normalized_prompt):
            result = await asyncio.to_thread(
                app.state.brain.tools.execute_structured,
                'open_url',
                url='https://www.tradingview.com/',
            )
            return {
                'status': 'completed' if result.get('ok') else 'failed',
                'response': (
                    'TradingView wurde geÃ¶ffnet.'
                    if result.get('ok')
                    else _human_response(result)
                ),
                'provider': 'local-desktop',
                'model': 'allowlist',
                'team': False,
                'team_roles': [],
            }
        if (
            'chart' in normalized_prompt
            and not re.search(r'\b(?:btc|bitcoin|eth|ethereum|xau|gold|dxy|eurusd|usd)\b', normalized_prompt)
        ):
            return {
                'status': 'needs_clarification',
                'response': 'Welchen Markt soll ich als Chart Ã¶ffnen? Zum Beispiel BTC/USD, ETH/USD oder Gold.',
                'provider': 'local',
                'model': 'rules',
                'team': False,
                'team_roles': [],
            }
        if 'was kannst du' in conversational_prompt or 'was kannst du nicht' in conversational_prompt:
            response = (
                'Ich kann Fragen beantworten, recherchieren, Apps und Webseiten Ã¶ffnen, '
                'Dateien und Fenster bedienen sowie Aufgaben planen und prÃ¼fen. '
                'Ich verschicke, kaufe, lÃ¶sche oder Ã¤ndere nichts an Konten ohne klare Freigabe.'
            )
            return {
                'status': 'completed',
                'response': response,
                'provider': 'local',
                'model': 'rules',
                'team': False,
                'team_roles': [],
            }
        app.state.memory.append('brain_live', {
            'kind': 'voice' if str(payload.get('source', '')).lower() == 'voice' else 'command',
            'text': prompt[:500],
            'ts': datetime.now().isoformat(),
        })
        team = bool(payload.get('team', False))
        preflight = await asyncio.to_thread(
            app.state.brain.agent_supervisor.diagnose_request,
            prompt,
        )
        app.state.publisher.publish('preflight.completed', {
            'ok': preflight.get('ok', False),
            'required': preflight.get('required', []),
            'installed': preflight.get('installed', []),
            'missing': preflight.get('missing', []),
        })
        recovery_required = bool(analysis.get('recovery_required'))
        if recovery_required:
            app.state.publisher.publish('recovery.started', {
                'prompt': prompt[:500],
                'reason': analysis.get('ambiguities', []),
                'missing_capabilities': analysis.get('missing_capabilities', []),
                'lead': routing_hint.get('lead'),
            })
        if not preflight.get('ok', False):
            repair_id = uuid4().hex
            app.state.pending_capability_repairs[repair_id] = {
                'prompt': prompt,
                'created_at': datetime.now().isoformat(),
                'preflight': preflight,
                'source': source,
                'team': team,
            }
            response = (
                'FÃ¼r diese Aufgabe fehlt noch eine freigegebene Komponente: '
                f'{", ".join(preflight.get("missing", []))}. '
                'Soll ich den geprÃ¼ften Adapter jetzt installieren?'
            )
            return {
                'status': 'adapter_confirmation_required',
                'response': response,
                'repair_id': repair_id,
                'preflight': preflight,
                'requires_confirmation': True,
            }
        if analysis.get('requires_confirmation') and not confirmed_request:
            confirmation_id = uuid4().hex
            app.state.pending_confirmations[confirmation_id] = {
                'prompt': prompt,
                'source': source,
                'created_at': datetime.now().isoformat(),
            }
            response = (
                'DafÃ¼r brauche ich deine ausdrÃ¼ckliche BestÃ¤tigung. '
                'Ich habe noch nichts gelÃ¶scht, gekauft, gesendet oder an einem Konto geÃ¤ndert.'
            )
            app.state.publisher.publish('chat.confirmation_required', {
                'prompt': prompt[:500],
                'risk_level': analysis.get('risk_level', 'high'),
                'intent': analysis.get('primary_intent', 'security'),
            })
            app.state.memory.append('conversation', {
                'prompt': prompt,
                'response': response,
                'intent': analysis.get('primary_intent', 'security'),
                'provider': 'local-safety',
                'model': 'rules',
            })
            return {
                'status': 'confirmation_required',
                'response': response,
                'provider': 'local-safety',
                'model': 'rules',
                'confirmation_required': True,
                'confirmation_id': confirmation_id,
                'pending_prompt': prompt,
                'analysis': analysis,
            }
        if confirmed_request and analysis.get('requires_confirmation'):
            delete_match = re.search(
                r'\b(?:lÃ¶sche|loesche|delete)\s+(?:die\s+datei\s+|die\s+datei:\s*|den\s+ordner\s+|den\s+pfad\s+)?["\']?([^"\']+?)["\']?$',
                prompt.strip(),
                re.IGNORECASE,
            )
            if delete_match:
                target = delete_match.group(1).strip().rstrip(' .,!?')
                result = await asyncio.to_thread(
                    app.state.brain.tools.execute_structured,
                    'delete_path',
                    path=target,
                    confirmed=True,
                )
                response = _human_response(result)
                return {
                    'status': 'completed' if result.get('ok') else 'failed',
                    'response': response,
                    'provider': 'local-desktop',
                    'model': 'allowlist',
                    'confirmed': True,
                    'verified': bool(result.get('ok')),
                }
        app.state.publisher.publish('chat.started', {
            'prompt': prompt[:500],
            'team': team,
        })
        app.state.audit.append('chat.started', {'prompt': prompt[:500], 'team': team})
        routing = routing_hint
        task_id = f'chat-{uuid4().hex}'
        hired_subagents = []
        if routing.get('missing_capabilities'):
            try:
                hired_subagents = app.state.agent_manager.hire_for_missing_capabilities(
                    routing['lead'],
                    task_id,
                    routing['missing_capabilities'],
                )
            except (KeyError, ValueError) as exc:
                app.state.publisher.publish('agents.auto_hire_failed', {
                    'task_id': task_id,
                    'lead': routing['lead'],
                    'missing_capabilities': routing['missing_capabilities'],
                    'error': str(exc),
                })
                return {
                    'status': 'blocked',
                    'error': 'subagent_capacity_or_policy',
                    'response': f'Unteragenten konnten nicht sicher bereitgestellt werden: {exc}',
                    'routing': routing,
                }
        routing['hired_subagents'] = [agent['name'] for agent in hired_subagents]
        app.state.agent_manager.set_status(routing['lead'], 'busy')
        app.state.publisher.publish('agent.routed', {
            'prompt': prompt[:500],
            'lead': routing['lead'],
            'specialists': routing['specialists'],
            'missing_capabilities': routing.get('missing_capabilities', []),
            'hired_subagents': routing['hired_subagents'],
        })
        if not team:
            fast_action = _fast_desktop_command(prompt)
            if fast_action is not None:
                response = fast_action
                app.state.agent_manager.release_task_subagents(task_id)
                app.state.agent_manager.release(routing['lead'])
                app.state.publisher.publish('agents.task_completed', {
                    'task_id': task_id,
                    'lead': routing['lead'],
                    'hired_subagents': routing['hired_subagents'],
                    'verifier': 'verifier',
                })
                app.state.publisher.publish('chat.completed', {
                    'prompt': prompt[:500],
                    'team': False,
                    'provider': 'local-desktop',
                    'model': 'allowlist',
                })
                app.state.memory.append('conversation', {
                    'prompt': prompt,
                    'response': _human_response(response),
                    'intent': 'DesktopActionIntent',
                    'provider': 'local-desktop',
                    'model': 'allowlist',
                })
                app.state.obsidian.sync_interaction(
                    prompt,
                    response,
                    {'intent': 'DesktopActionIntent', 'lead_agent': routing['lead']},
                )
                app.state.audit.append('chat.completed', {
                    'task_id': task_id,
                    'lead_agent': routing['lead'],
                    'provider': 'local-desktop',
                })
                return {
                    'status': 'completed',
                    'response': _human_response(response),
                    'provider': 'local-desktop',
                    'model': 'allowlist',
                    'team': False,
                    'team_roles': [],
                    'lead_agent': routing['lead'],
                    'specialist_agents': routing['specialists'],
                    'hired_subagents': routing['hired_subagents'],
                }
        try:
            if team:
                team_result = await asyncio.to_thread(run_team, prompt)
            else:
                team_result = None
            if team_result:
                response = team_result['response']
                active_agent = routing['lead']
            else:
                recovery_prompt = prompt
                if recovery_required:
                    recovery_prompt = (
                        "PrÃ¼fe diese Anfrage zuerst auf fehlende FÃ¤higkeiten oder Unklarheiten. "
                        "Suche den sichersten lokalen LÃ¶sungsweg, nutze bekannte freigegebene "
                        "Werkzeuge, und behaupte keine AusfÃ¼hrung ohne Ã¼berprÃ¼fbares Ergebnis. "
                        "Wenn ein freigegebenes lokales Werkzeug fehlt, richte es Ã¼ber den "
                        "bestehenden Projekt-Preflight ein. Wenn die Aufgabe riskant oder "
                        "mehrdeutig ist, stelle genau eine kurze RÃ¼ckfrage.\n\n"
                        f"Originalanfrage:\n{prompt}"
                    )
                response, active_agent = await resolve_agent_response(recovery_prompt, routing)
        except Exception:
            app.state.agent_manager.release_task_subagents(task_id)
            app.state.agent_manager.release(routing['lead'])
            raise
        app.state.agent_manager.release_task_subagents(task_id)
        app.state.agent_manager.release(routing['lead'])
        if active_agent and active_agent != routing['lead']:
            app.state.agent_manager.release(active_agent)
        response = _human_response(response)
        if recovery_required and re.search(
            r'\b(?:erfolgreich ausgefÃ¼hrt|erfolgreich ausgefuehrt|wurde geÃ¶ffnet|wurde geoeffnet|'
            r'wurde erstellt|wurde gespeichert|browser-sequenz)\b',
            response.casefold(),
        ):
            response = (
                'Ich konnte dein Ziel noch nicht eindeutig erkennen und melde deshalb keine '
                'Aktion als ausgefÃ¼hrt. Was genau soll ich mit â€žneuen Dingâ€œ tun?'
            )
        app.state.memory.append('conversation', {
            'prompt': prompt,
            'response': response,
            'intent': app.state.brain.detect_intent(prompt),
            'provider': app.state.brain.provider,
            'model': app.state.brain.model,
        })
        app.state.obsidian.sync_interaction(
            prompt,
            response,
            {
                'intent': app.state.brain.detect_intent(prompt),
                'lead_agent': active_agent,
            },
        )
        app.state.audit.append('chat.completed', {
            'task_id': task_id,
            'lead_agent': active_agent,
            'hired_subagents': routing['hired_subagents'],
            'provider': app.state.brain.provider,
        })
        app.state.publisher.publish('brain.response', {
            'provider': app.state.brain.provider,
            'model': app.state.brain.model,
            'memory_entries': len(app.state.brain.memory.load()),
        })
        app.state.publisher.publish('chat.completed', {
            'prompt': prompt[:500],
            'team': team,
            'provider': app.state.brain.provider,
            'model': app.state.brain.model,
        })
        if recovery_required:
            app.state.publisher.publish('recovery.completed', {
                'prompt': prompt[:500],
                'agent': active_agent,
                'verified_response': bool(response.strip()),
            })
        return {
            'status': 'completed',
            'response': response,
            'provider': app.state.brain.provider,
            'model': app.state.brain.model,
            'team': team,
            'team_roles': list(team_result['roles']) if team_result else [],
            'lead_agent': active_agent,
            'specialist_agents': routing['specialists'],
            'hired_subagents': routing['hired_subagents'],
        }

    def _fast_desktop_command(prompt: str) -> str | None:
        """Run simple allowlisted open commands without waiting for an LLM."""
        parts = [
            part.strip(" ,.")
            for part in re.split(
                r"\s*(?:;\s*|\b(?:und\s+)?dann\s+|\b(?:und\s+)?danach\s+)\s*",
                prompt,
                flags=re.IGNORECASE,
            )
            if part.strip(" ,.")
        ]
        if not parts:
            return None
        results = []
        for part in parts:
            match = re.match(
                r"^(?:bitte\s+)?(?:Ã¶ffne|oeffne|starte|open|start)\s+(.+?)\s*$",
                part,
                flags=re.IGNORECASE,
            )
            if not match:
                return None
            target = match.group(1).strip()
            url = re.fullmatch(r"https?://\S+", target, flags=re.IGNORECASE)
            try:
                if url:
                    result = app.state.brain.tools.desktop.open_url(url.group(0))
                else:
                    result = app.state.brain.tools.desktop.open_application(target)
            except (OSError, RuntimeError, ValueError):
                return None
            if not result.get('ok'):
                return None
            results.append({
                'target': target,
                'url': url.group(0) if url else None,
            })
        return " ".join(
            f"{item.get('target') or item.get('url')} wurde geÃ¶ffnet."
            for item in results
        )

    @app.post('/orchestrate')
    def orchestrate(payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get('prompt', '')).strip()
        if not prompt:
            return {'status': 'rejected', 'error': 'prompt_required'}
        result = run_team(prompt)
        app.state.memory.append('team_conversation', {
            'prompt': prompt,
            'response': result['response'],
            'roles': result['roles'],
        })
        return {
            'status': 'completed',
            'response': result['response'],
            'roles': result['roles'],
            'provider': app.state.brain.provider,
            'model': app.state.brain.model,
        }

    @app.get('/status')
    def status() -> Dict[str, Any]:
        queue = app.state.task_queue.list()
        brain_memory = app.state.brain.memory.load()
        return {
            'status': 'ready',
            'safe_mode': True,
            'brain': {
                'provider': app.state.brain.provider,
                'model': app.state.brain.model,
                'nim_models_configured': len(app.state.brain.nim_models),
                'nim_models_exhausted': len(app.state.brain.nim_exhausted_models),
                'openrouter_models_configured': len(app.state.brain.openrouter_models),
                'openrouter_models_exhausted': len(app.state.brain.openrouter_exhausted_models),
                'omniroute_url': app.state.brain.omniroute_url,
                'persistent_memory_entries': len(brain_memory),
                'live': True,
                'team_active': app.state.team_active,
                'team_roles': list(app.state.team_roles),
            },
            'agents': app.state.agent_manager.list_agents(),
            'skills': app.state.skill_loader.load(),
            'workflows': app.state.workflow_registry.list(),
            'queue': {'total': len(queue), 'tasks': queue},
            'memory_entries': len(app.state.memory.snapshot()),
            'desktop': app.state.desktop.status(),
            'tts': {
                'provider': 'elevenlabs',
                'configured': bool(
                    os.getenv('JARVIS_USE_ELEVENLABS', '0').strip().lower()
                    in {'1', 'true', 'yes', 'on'}
                    and
                    os.getenv('ELEVENLABS_API_KEY', '').strip()
                    and os.getenv('ELEVENLABS_VOICE_ID', '').strip()
                ),
                'local_fallback': True,
            },
            'performance': app.state.performance.snapshot(),
            'rag': rag_status(),
            'executor_queue': app.state.request_store.load_pending(),
            'audit': app.state.publisher.snapshot(25),
        }

    @app.get('/audit')
    def audit(limit: int = 50) -> Dict[str, Any]:
        safe_limit = max(1, min(int(limit), 200))
        return {
            'status': 'ok',
            'events': app.state.audit.recent(safe_limit),
            'live_events': app.state.publisher.snapshot(safe_limit),
        }

    @app.get('/capabilities')
    def capabilities() -> Dict[str, Any]:
        return {
            'status': 'ok',
            'safe_mode': True,
            'capabilities': app.state.skill_manager.capability_report(),
            'readiness': app.state.brain.agent_supervisor.readiness(),
            'dependency_policy': 'allowlisted_project_packages_only',
        }

    @app.post('/capabilities/repair')
    async def repair_capability(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Install only the allowlisted adapter packages for a confirmed request."""
        repair_id = str(payload.get('repair_id', '')).strip()
        record = app.state.pending_capability_repairs.get(repair_id)
        if not record:
            raise HTTPException(status_code=404, detail='repair_not_found_or_expired')
        if not bool(payload.get('confirmed', False)):
            app.state.pending_capability_repairs.pop(repair_id, None)
            return {'status': 'cancelled', 'response': 'Abgebrochen. Es wurde nichts installiert.'}
        app.state.pending_capability_repairs.pop(repair_id, None)
        request = record['prompt']
        result = await asyncio.to_thread(
            app.state.brain.agent_supervisor.prepare,
            request,
        )
        app.state.publisher.publish('capability.repaired', {
            'repair_id': repair_id,
            'capability': result.get('capability'),
            'ok': result.get('ok', False),
            'installed': result.get('installed', False),
        })
        response = {
            'status': 'completed' if result.get('ok') else 'failed',
            'response': (
                'Adapter installiert und geprÃ¼ft. Der ursprÃ¼ngliche Auftrag wird jetzt erneut geprÃ¼ft.'
                if result.get('ok')
                else 'Adapter konnte nicht vollstÃ¤ndig installiert oder geprÃ¼ft werden.'
            ),
            'repair_id': repair_id,
            'result': result,
            'verified': bool(result.get('verified')),
        }
        if result.get('ok'):
            retry_result = await chat({
                'prompt': request,
                'source': record.get('source', 'repair-retry'),
                'team': bool(record.get('team', False)),
            })
            response['retry'] = retry_result
            response['retry_status'] = retry_result.get('status')
            response['response'] = (
                'Adapter installiert und geprÃ¼ft. Der ursprÃ¼ngliche Auftrag wurde erneut '
                'analysiert und verarbeitet.'
            )
        return response

    @app.get('/actions')
    def actions() -> Dict[str, Any]:
        """Expose the reviewed action catalog without exposing credentials."""
        catalog_path = Path(__file__).resolve().parents[1] / 'config' / 'action_catalog.json'
        try:
            catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail='Aktionskatalog konnte nicht geladen werden') from exc
        return {'status': 'ok', 'catalog': catalog}

    @app.get('/runtime')
    def runtime() -> Dict[str, Any]:
        """Report local execution surfaces without exposing credentials."""
        project_root = Path(__file__).resolve().parents[1]
        cdp: Dict[str, Any] = {}
        for port in (9222, 9223):
            url = f'http://127.0.0.1:{port}/json/version'
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    cdp[str(port)] = {'status': 'online', 'http_status': response.status}
            except (urllib.error.URLError, TimeoutError, OSError):
                cdp[str(port)] = {'status': 'offline'}
        voice_model = project_root / 'models' / 'voices' / 'de_DE-thorsten-medium.onnx'
        return {
            'status': 'ok',
            'browser_session': {
                'cdp': cdp,
                'profile_present': (project_root / 'data' / 'jarvis_edge_cdp_profile').is_dir(),
                'bridge_script': (project_root / 'start_edge_jarvis.bat').is_file(),
            },
            'voice': {
                'local_piper_model_present': voice_model.is_file(),
                'elevenlabs_configured': bool(
                    os.getenv('ELEVENLABS_API_KEY', '').strip()
                    and os.getenv('ELEVENLABS_VOICE_ID', '').strip()
                ),
            },
            'integrations': {
                'make_webhook_configured': bool(os.getenv('MAKE_WEBHOOK_URL', '').strip()),
                'telegram_configured': bool(os.getenv('TELEGRAM_BOT_TOKEN', '').strip()),
                'telegram_chat_configured': bool(os.getenv('TELEGRAM_CHAT_ID', '').strip()),
                'google_calendar_configured': bool(
                    os.getenv('GOOGLE_CALENDAR_CREDENTIALS', '').strip()
                ),
                'outlook_configured': bool(
                    os.getenv('MICROSOFT_GRAPH_TOKEN', '').strip()
                ),
                'email_configured': bool(
                    os.getenv('SMTP_HOST', '').strip()
                    and os.getenv('SMTP_USER', '').strip()
                ),
                'discord_configured': bool(os.getenv('DISCORD_WEBHOOK_URL', '').strip()),
                'slack_configured': bool(os.getenv('SLACK_WEBHOOK_URL', '').strip()),
                'external_actions_require_confirmation': True,
            },
            'rag': rag_status(),
            'obsidian': app.state.obsidian.status(),
        }

    @app.get('/agents/capabilities')
    def agent_capabilities() -> Dict[str, Any]:
        """Expose agent coverage and configuration without leaking credentials."""
        configured = {
            'calendar': bool(
                os.getenv('GOOGLE_CALENDAR_CREDENTIALS', '').strip()
                or os.getenv('MICROSOFT_GRAPH_TOKEN', '').strip()
            ),
            'email': bool(
                os.getenv('SMTP_HOST', '').strip()
                and os.getenv('SMTP_USER', '').strip()
            ),
            'messaging': bool(
                os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
                or os.getenv('DISCORD_WEBHOOK_URL', '').strip()
                or os.getenv('SLACK_WEBHOOK_URL', '').strip()
            ),
            'rag': rag_status()['status'] == 'online',
            'trading': True,
            'infrastructure': True,
            'media': True,
        }
        return {
            'status': 'ok',
            'agents': app.state.agent_manager.list_agents(),
            'configured_integrations': configured,
            'requires_user_credentials': [
                name for name, ready in configured.items() if not ready
            ],
            'policy': {
                'external_actions_require_confirmation': True,
                'financial_actions_require_confirmation': True,
                'unknown_actions_rejected': True,
            },
            'readiness': app.state.brain.agent_supervisor.readiness(),
        }

    @app.get('/obsidian/status')
    def obsidian_status() -> Dict[str, Any]:
        return {'status': 'ok', 'obsidian': app.state.obsidian.status()}

    @app.get('/scheduler')
    def scheduler_status() -> Dict[str, Any]:
        return {
            'status': 'ok',
            'jobs': app.state.scheduler.list(),
            'runner': app.state.scheduler_runner.status(),
            'mode': 'local_safe_jobs_live',
            'external_actions_require_confirmation': True,
        }

    @app.post('/scheduler/{job_id}/enabled')
    def scheduler_enabled(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            job = app.state.scheduler.set_enabled(job_id, bool(payload.get('enabled', False)))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        app.state.audit.append('scheduler.updated', {
            'job_id': job_id,
            'enabled': job['enabled'],
        })
        return {'status': 'updated', 'job': job}

    @app.post('/obsidian/sync')
    def obsidian_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get('action', 'status')).lower()
        if action == 'graph':
            graph = app.state.brain.memory.graph_snapshot()
            path = app.state.obsidian.sync_graph(graph)
            return {'status': 'synced' if path else 'disabled', 'path': path}
        if action == 'audit':
            path = app.state.obsidian.audit({
                'event': 'manual_sync',
                'source': 'api',
                'note': 'Audit synchronization requested',
            })
            return {'status': 'synced' if path else 'disabled', 'path': path}
        raise HTTPException(status_code=400, detail='unknown_obsidian_sync_action')

    @app.get('/obsidian/graph')
    def obsidian_graph() -> Dict[str, Any]:
        graph = app.state.brain.memory.graph_snapshot()
        return {
            'status': 'ok',
            'obsidian': app.state.obsidian.status(),
            'graph': graph,
            'connections': {
                'brain_to_obsidian': app.state.obsidian.enabled,
                'chat_to_obsidian': True,
                'audit_to_obsidian': app.state.obsidian.enabled,
                'agents_to_audit': True,
                'scheduler_to_obsidian': True,
                'rag': False,
            },
        }

    @app.get('/setup/integrations')
    def setup_integrations() -> Dict[str, Any]:
        """Return a login-first checklist without exposing or accepting secrets."""
        checklist = []
        for key, item in INTEGRATION_SETUP.items():
            missing = [
                env_name for env_name in item['required_env']
                if not os.getenv(env_name, '').strip()
            ]
            checklist.append({
                'id': key,
                'name': item['name'],
                'login_url': item['login_url'],
                'mode': item['mode'],
                'status': 'ready' if not missing else 'login_required',
                'missing_configuration': missing,
                'secret_input': 'local_env_only',
            })
        return {
            'status': 'ok',
            'message': 'Ã–ffne den Link, melde dich an und trage nur die benÃ¶tigte lokale Konfiguration ein.',
            'integrations': checklist,
            'security': {
                'credentials_never_returned': True,
                'credentials_never_logged': True,
                'external_actions_require_confirmation': True,
            },
        }

    @app.post('/setup/integrations/{integration_id}/open')
    def open_integration_login(integration_id: str) -> Dict[str, Any]:
        """Open only an allowlisted provider login page in the local browser."""
        item = INTEGRATION_SETUP.get(integration_id)
        if item is None:
            raise HTTPException(status_code=404, detail='unknown_integration')
        result = app.state.brain.tools.desktop.open_url(item['login_url'])
        if not result.get('ok'):
            raise HTTPException(status_code=502, detail='login_page_could_not_be_opened')
        return {
            'status': 'opened',
            'integration': integration_id,
            'login_url': item['login_url'],
            'next_step': 'login_in_the_browser_and_configure_local_env',
        }

    @app.get('/learning')
    def learning() -> Dict[str, Any]:
        profile = app.state.brain.memory.behavior_profile()
        graph = app.state.brain.memory.graph_snapshot()
        return {
            'status': 'ok',
            'profile': profile,
            'persistent_memory_entries': len(app.state.brain.memory.load()),
            'learned_patterns': len(
                app.state.brain.memory.relevant_context('tradingview desktop browser', limit=500)
            ),
            'knowledge_graph': {
                'node_count': graph['node_count'],
                'edge_count': graph['edge_count'],
                'updated_at': graph['updated_at'],
            },
            'policy': 'local_profile_plus_verified_interactions',
        }

    @app.get('/learning/graph')
    def learning_graph() -> Dict[str, Any]:
        """Return the local, redacted knowledge graph for the memory view."""
        return {'status': 'ok', 'graph': app.state.brain.memory.graph_snapshot()}

    @app.post('/learning/train')
    def train_learning() -> Dict[str, Any]:
        result = app.state.brain.memory.train_from_history()
        app.state.publisher.publish('learning.trained', result)
        return {
            'status': 'trained',
            'result': result,
            'message': 'Lokale Routinen wurden aus dem vorhandenen Verlauf erstellt.',
        }

    @app.post('/plan')
    async def plan(payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get('prompt', '')).strip()
        if not prompt:
            return {'status': 'rejected', 'error': 'prompt_required'}
        preflight = await asyncio.to_thread(
            app.state.brain.agent_supervisor.diagnose_request,
            prompt,
        )
        goal_plan = app.state.brain.tools.inspect_goal(prompt)
        needs_context = any(
            step.get("tool") in {
                "active_context",
                "detect_active_window_title",
                "open_application",
                "open_url",
                "browser_get_text",
            }
            for part in goal_plan.get("parts", [])
            for step in part.get("steps", [])
        )
        context = (
            app.state.brain.tools.desktop.active_context()
            if needs_context
            else {"ok": True, "data": {"available": False, "message": "FÃ¼r diesen Plan nicht erforderlich."}}
        )
        result = {
            'status': 'ready' if goal_plan.get('ok') else 'needs_clarification',
            'prompt': prompt,
            'preflight': preflight,
            'plan': goal_plan,
            'active_context': context.get('data', {}) if context.get('ok') else {
                'available': False,
                'message': context.get('message', 'UI-Kontext nicht verfÃ¼gbar.'),
            },
        }
        app.state.publisher.publish('plan.created', {
            'status': result['status'],
            'prompt': prompt[:500],
            'parts': len(goal_plan.get('parts', [])),
        })
        return result

    @app.post('/plan/execute')
    async def execute_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get('prompt', '')).strip()
        if not prompt:
            return {'status': 'rejected', 'error': 'prompt_required'}
        app.state.memory.append('brain_live', {
            'kind': 'voice' if str(payload.get('source', '')).lower() == 'voice' else 'plan',
            'text': prompt[:500],
            'ts': datetime.now().isoformat(),
        })
        source = str(payload.get('source', '')).strip().lower()
        voice_confirmed = source == 'voice' and bool(payload.get('voice_confirmed', False))
        confirmed = bool(payload.get('confirmed', False) or voice_confirmed)
        preflight = await asyncio.to_thread(
            app.state.brain.agent_supervisor.diagnose_request,
            prompt,
        )
        if not preflight.get('ok', False):
            repair_id = uuid4().hex
            app.state.pending_capability_repairs[repair_id] = {
                'prompt': prompt,
                'created_at': datetime.now().isoformat(),
                'preflight': preflight,
                'source': source,
                'team': team,
                'retry_payload': dict(payload),
            }
            return {
                'status': 'adapter_confirmation_required',
                'error': 'required_project_tools_unavailable',
                'repair_id': repair_id,
                'requires_confirmation': True,
                'response': (
                    'FÃ¼r diesen Ablauf fehlt eine freigegebene Komponente: '
                    f"{', '.join(preflight.get('missing', []))}. "
                    'Soll ich sie nach deiner BestÃ¤tigung installieren?'
                ),
                'preflight': preflight,
            }
        goal_plan = app.state.brain.tools.inspect_goal(prompt)
        if not goal_plan.get('ok'):
            return {
                'status': 'needs_clarification',
                'prompt': prompt,
                'plan': goal_plan,
                'message': 'Der Auftrag enthÃ¤lt keinen vollstÃ¤ndig verstÃ¤ndlichen AusfÃ¼hrungsplan.',
            }
        if bool(payload.get('dry_run', False)):
            return {
                'status': 'planned',
                'prompt': prompt,
                'plan': goal_plan,
                'preflight': preflight,
            }

        confirmation_steps = []
        text_action_tools = {
            'open_application',
            'open_url',
            'browser_get_text',
            'browser_flow',
            'click',
            'type_text',
            'screenshot',
        }
        for part in goal_plan.get('parts', []):
            for step in part.get('steps', []):
                tool_name = str(step.get('tool') or '').strip()
                arguments = dict(step.get('arguments') or {})
                action_plan = app.state.brain.tools.plan_action(
                    tool_name,
                    **arguments,
                )
                if action_plan.get('confirmation_required'):
                    confirmation_steps.append({
                        'part': part.get('part'),
                        'request': part.get('request'),
                        'plan': action_plan,
                    })
                elif source != 'voice' and tool_name in text_action_tools:
                    confirmation_steps.append({
                        'part': part.get('part'),
                        'request': part.get('request'),
                        'plan': {
                            **action_plan,
                            'confirmation_required': True,
                            'reason': 'Textbefehle fÃ¼r Desktop- und Browser-Aktionen benÃ¶tigen eine BestÃ¤tigung.',
                        },
                    })
        if confirmation_steps and not confirmed:
            app.state.publisher.publish('plan.confirmation_required', {
                'prompt': prompt[:500],
                'steps': len(confirmation_steps),
            })
            return {
                'status': 'confirmation_required',
                'prompt': prompt,
                'preflight': preflight,
                'plan': goal_plan,
                'confirmation': {
                    'message': (
                        'Der vorbereitete Ablauf enthÃ¤lt potenziell irreversible '
                        'Aktionen. Eine BestÃ¤tigung genÃ¼gt fÃ¼r den gesamten Plan.'
                    ),
                    'steps': confirmation_steps,
                },
            }

        app.state.publisher.publish('plan.execution_started', {
            'prompt': prompt[:500],
            'parts': len(goal_plan.get('parts', [])),
            'confirmation_source': 'voice' if voice_confirmed else ('ui' if confirmed else 'none'),
        })
        executions = []
        for part in goal_plan['parts']:
            execution = await asyncio.to_thread(
                app.state.brain.tools.execute_multi_agent,
                part['steps'],
                prompt,
                confirmed,
                {'part': part['part'], 'request': part['request']},
            )
            executions.append({
                'part': part['part'],
                'request': part['request'],
                'execution': execution,
            })
            app.state.publisher.publish('plan.step', {
                'part': part['part'],
                'ok': execution.get('ok', False),
                'request': part['request'][:300],
            })
            if not execution.get('ok', False):
                recovery_prompt = (
                    f"Ein frÃ¼herer Agentenpfad fÃ¼r '{prompt}' ist fehlgeschlagen. "
                    "Wechsle sofort auf den nÃ¤chsten sicheren Spezialisten, prÃ¼fe die Ursache "
                    "und liefere die nÃ¤chste verifizierbare Alternative."
                )
                fallback_response, fallback_agent = await resolve_agent_response(
                    recovery_prompt,
                    {'lead': 'recovery', 'specialists': ['planner', 'verifier', 'researcher', 'operator']},
                )
                app.state.publisher.publish('plan.execution_failed', {
                    'part': part['part'],
                    'message': execution.get('message', 'Schritt fehlgeschlagen.'),
                    'fallback_agent': fallback_agent,
                })
                return {
                    'status': 'failed',
                    'prompt': prompt,
                    'preflight': preflight,
                    'plan': goal_plan,
                    'executions': executions,
                    'message': fallback_response,
                    'fallback_agent': fallback_agent,
                }
        app.state.publisher.publish('plan.execution_completed', {
            'prompt': prompt[:500],
            'parts': len(executions),
        })
        return {
            'status': 'completed',
            'prompt': prompt,
            'preflight': preflight,
            'plan': goal_plan,
            'executions': executions,
        }

    @app.get('/project/status')
    def project_status() -> Dict[str, Any]:
        return {'status': 'ok', 'runner': app.state.project_runner.status()}

    @app.post('/project/plan')
    def project_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
        operation = str(payload.get('operation', '')).strip().lower()
        path = str(payload.get('path', '')).strip()
        content = payload.get('content', '')
        try:
            if operation == 'read':
                plan = app.state.project_runner.read_file(path)
            elif operation == 'write':
                plan = app.state.project_runner.plan_write(path, content)
            elif operation == 'repair':
                plan = app.state.project_runner.plan_repair(
                    path,
                    content,
                    reason=str(payload.get('reason', ''))[:500],
                )
            elif operation == 'test':
                command = str(payload.get('command', '')).strip()
                if command not in app.state.project_runner.COMMANDS:
                    raise ValueError('Dieser Test ist nicht freigegeben.')
                plan = {
                    'operation': 'run_command',
                    'command': command,
                    'timeout': min(max(int(payload.get('timeout', 120)), 1), 120),
                }
            else:
                raise ValueError('Erlaubt sind read, write, repair und test.')
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        plan_id = uuid4().hex
        app.state.project_plans[plan_id] = {
            'operation': operation,
            'path': path,
            'content': content,
            'reason': str(payload.get('reason', ''))[:500],
            'plan': plan,
            'created_at': datetime.now().isoformat(),
        }
        app.state.publisher.publish('project.plan_created', {
            'plan_id': plan_id,
            'operation': operation,
            'path': plan.get('path', path),
        })
        return {
            'status': 'planned',
            'plan_id': plan_id,
            'requires_confirmation': operation in {'write', 'repair', 'test'},
            'plan': plan,
        }

    @app.post('/project/confirm')
    def project_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = str(payload.get('plan_id', '')).strip()
        record = app.state.project_plans.pop(plan_id, None)
        if not record:
            raise HTTPException(status_code=404, detail='plan_not_found_or_expired')
        if not bool(payload.get('confirmed', False)):
            app.state.publisher.publish('project.plan_cancelled', {'plan_id': plan_id})
            return {'status': 'cancelled', 'message': 'Abgebrochen. Es wurde nichts geÃ¤ndert.'}
        operation = record['operation']
        try:
            if operation == 'write':
                result = app.state.project_runner.execute_write(
                    record['path'],
                    record['content'],
                    confirmed=True,
                    expected_old_sha256=record['plan'].get('old_sha256'),
                )
            elif operation == 'repair':
                result = app.state.project_runner.execute_repair(
                    record['path'],
                    record['content'],
                    confirmed=True,
                    expected_old_sha256=record['plan'].get('old_sha256'),
                    reason=record['reason'],
                )
            elif operation == 'test':
                result = app.state.project_runner.run_command(
                    record['plan']['command'],
                    confirmed=True,
                    timeout=record['plan']['timeout'],
                )
            elif operation == 'read':
                result = app.state.project_runner.read_file(record['path'])
            else:
                raise ValueError('Unbekannte Planoperation.')
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        app.state.publisher.publish('project.plan_finished', {
            'plan_id': plan_id,
            'operation': operation,
            'ok': bool(result.get('ok', True)),
        })
        return {
            'status': 'completed' if result.get('ok', True) else 'failed',
            'plan_id': plan_id,
            'result': result,
            'verified': bool(result.get('ok', True)),
        }

    @app.get('/telemetry')
    def telemetry() -> Dict[str, Any]:
        memory = psutil.virtual_memory()
        return {
            'ok': True,
            'cpu_percent': psutil.cpu_percent(interval=0.15),
            'memory_percent': memory.percent,
            'memory_used_gb': round(memory.used / (1024 ** 3), 2),
            'memory_total_gb': round(memory.total / (1024 ** 3), 2),
            'disk_percent': psutil.disk_usage(os.getcwd()).percent,
        }

    @app.get('/desktop/observe')
    def observe_desktop() -> Dict[str, Any]:
        """Expose live UI/accessibility context without taking screenshots."""
        result = app.state.brain.tools.execute_structured('active_context')
        if not result.get('ok'):
            raise HTTPException(status_code=503, detail=result.get('message', 'Desktop-Kontext nicht verfÃ¼gbar'))
        return {'status': 'ok', 'local_only': True, 'mode': 'ui_accessibility', **result.get('data', {})}

    @app.get('/desktop/context')
    def desktop_context() -> Dict[str, Any]:
        """Return active-window/UI context for intent resolution, locally only."""
        result = app.state.brain.tools.execute_structured('active_context')
        if not result.get('ok'):
            raise HTTPException(status_code=503, detail=result.get('message', 'Desktop-Kontext nicht verfÃ¼gbar'))
        return {'status': 'ok', 'local_only': True, **result.get('data', {})}

    @app.get('/live/weather')
    def live_weather() -> Dict[str, Any]:
        return app.state.live_monitoring.weather()

    @app.get('/live/news')
    def live_news() -> Dict[str, Any]:
        from core.monitoring import LocalMonitoring
        return app.state.live_monitoring.news()

    @app.get('/live/markets')
    def live_markets() -> Dict[str, Any]:
        from core.monitoring import LocalMonitoring
        try:
            return app.state.live_monitoring.markets()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "source": "CoinGecko",
                "assets": [],
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
                "financialAdvice": False,
            }

    @app.get('/live/crypto')
    def live_crypto() -> Dict[str, Any]:
        return app.state.live_monitoring.crypto()

    @app.get('/live/forex')
    def live_forex() -> Dict[str, Any]:
        return app.state.live_monitoring.forex()

    @app.get('/live/macro')
    def live_macro() -> Dict[str, Any]:
        return {
            "ok": True,
            "source": "Frankfurter/EZB",
            "fx": app.state.live_monitoring.forex(),
            "financialAdvice": False,
        }

    @app.post('/settings/elevenlabs')
    def save_elevenlabs_key(payload: Dict[str, Any]) -> Dict[str, Any]:
        key = str(payload.get('api_key', '')).strip()
        if not key or len(key) < 10 or any(char.isspace() for char in key):
            raise HTTPException(status_code=400, detail='UngÃ¼ltiger ElevenLabs-Key')
        env_path = Path(__file__).resolve().parents[1] / '.env'
        lines = env_path.read_text(encoding='utf-8').splitlines() if env_path.exists() else []
        replaced = False
        updated = []
        for line in lines:
            if line.startswith('ELEVENLABS_API_KEY='):
                updated.append(f'ELEVENLABS_API_KEY={key}')
                replaced = True
            else:
                updated.append(line)
        if not replaced:
            updated.append(f'ELEVENLABS_API_KEY={key}')
        env_path.write_text('\n'.join(updated) + '\n', encoding='utf-8')
        return {'status': 'saved', 'provider': 'elevenlabs', 'configured': True}

    @app.post('/settings/elevenlabs/voice')
    def save_elevenlabs_voice(payload: Dict[str, Any]) -> Dict[str, Any]:
        voice_id = str(payload.get('voice_id', '')).strip()
        if not voice_id or len(voice_id) > 128 or any(char.isspace() for char in voice_id):
            raise HTTPException(status_code=400, detail='UngÃ¼ltige ElevenLabs-Voice-ID')
        env_path = Path(__file__).resolve().parents[1] / '.env'
        lines = env_path.read_text(encoding='utf-8').splitlines() if env_path.exists() else []
        updated = []
        replaced = False
        for line in lines:
            if line.startswith('ELEVENLABS_VOICE_ID='):
                updated.append(f'ELEVENLABS_VOICE_ID={voice_id}')
                replaced = True
            else:
                updated.append(line)
        if not replaced:
            updated.append(f'ELEVENLABS_VOICE_ID={voice_id}')
        env_path.write_text('\n'.join(updated) + '\n', encoding='utf-8')
        return {'status': 'saved', 'provider': 'elevenlabs', 'voice_configured': True}

    @app.post('/tts')
    def elevenlabs_tts(payload: Dict[str, Any]):
        if os.getenv('JARVIS_USE_ELEVENLABS', '0').strip().lower() not in {'1', 'true', 'yes', 'on'}:
            raise HTTPException(status_code=503, detail='Lokale Microsoft-Stimme ist aktiv')
        key = os.getenv('ELEVENLABS_API_KEY', '').strip()
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', '').strip()
        text = str(payload.get('text', '')).strip()
        if not key or not voice_id:
            raise HTTPException(status_code=503, detail='ElevenLabs ist nicht vollstÃ¤ndig konfiguriert')
        if not text or len(text) > 5000:
            raise HTTPException(status_code=400, detail='UngÃ¼ltiger Text')
        request = urllib.request.Request(
            f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
            data=json.dumps({
                'text': text,
                'model_id': os.getenv('ELEVENLABS_MODEL', 'eleven_flash_v2_5').strip(),
                'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75},
            }).encode('utf-8'),
            headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                audio = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise HTTPException(
                    status_code=502,
                    detail='ElevenLabs nicht verfÃ¼gbar; lokale Microsoft-Stimme verwenden',
                ) from exc
            raise HTTPException(
                status_code=502,
                detail=f'ElevenLabs-TTS antwortete mit HTTP {exc.code}',
            ) from exc
        except urllib.error.URLError as exc:
            raise HTTPException(
                status_code=502,
                detail='ElevenLabs-TTS-Netzwerkverbindung fehlgeschlagen',
            ) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=502,
                detail='ElevenLabs-TTS konnte lokal nicht verarbeitet werden',
            ) from exc
        return Response(content=audio, media_type='audio/mpeg')

    @app.get('/events')
    async def events() -> StreamingResponse:
        channel = app.state.publisher.subscribe()

        async def generator():
            try:
                while True:
                    data = await asyncio.wait_for(channel.get(), timeout=30)
                    yield f'data: {json.dumps(data)}\n\n'
            except asyncio.TimeoutError:
                yield 'event: heartbeat\ndata: {"type":"heartbeat","payload":{"safe_mode":true}}\n\n'

        return StreamingResponse(generator(), media_type='text/event-stream')

    @app.get('/skills')
    def list_skills() -> Dict[str, Any]:
        return {'skills': app.state.skill_loader.load()}

    @app.get('/agents')
    def list_agents() -> Dict[str, Any]:
        specialist_path = Path(__file__).resolve().parents[1] / 'config' / 'specialist_agents.json'
        try:
            specialist_catalog = json.loads(specialist_path.read_text(encoding='utf-8-sig'))
        except (OSError, json.JSONDecodeError):
            specialist_catalog = {'policy': {}, 'specialists': []}
        return {
            'agents': app.state.agent_manager.list_agents(),
            'specialist_catalog': specialist_catalog,
            'provider_policy': 'nvidia_nim_with_local_fallback',
            'nvidia_catalog': 'config/nvidia_model_catalog.json',
            'nvidia_skills': 'config/nvidia_skill_catalog.json',
        }

    @app.post('/capabilities/diagnose')
    def diagnose_capabilities(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect a request and return a bounded recovery plan before execution."""
        prompt = str(payload.get('prompt', '')).strip()
        if not prompt:
            raise HTTPException(status_code=400, detail='prompt_required')
        routing = app.state.agent_manager.route_prompt(prompt)
        analysis = routing.get('analysis', {})
        missing = list(analysis.get('missing_capabilities', []))
        return {
            'status': 'recovery_required' if missing else 'ready_for_routing',
            'routing': routing,
            'diagnosis': {
                'supported': not missing,
                'missing_capabilities': missing,
                'recovery_plan': analysis.get('recovery_plan', []),
                'will_claim_success_without_verification': False,
            },
        }

    @app.get('/integrations')
    def integrations() -> Dict[str, Any]:
        return {'status': 'ok', **app.state.integrations.status()}

    @app.post('/orchestration/plan')
    def orchestration_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get('prompt', '')).strip()
        if not prompt:
            raise HTTPException(status_code=400, detail='prompt_required')
        try:
            return plan_with_langgraph(prompt)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post('/memory/vector/upsert')
    def vector_memory_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
        text = str(payload.get('text', '')).strip()
        if not text:
            raise HTTPException(status_code=400, detail='text_required')
        try:
            return qdrant_upsert_memory(text, dict(payload.get('metadata') or {}))
        except (OSError, urllib.error.URLError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get('/memory/vector/search')
    def vector_memory_search(query: str = '', limit: int = 5) -> Dict[str, Any]:
        query = query.strip()
        if not query:
            raise HTTPException(status_code=400, detail='query_required')
        try:
            return qdrant_search_memory(query, limit)
        except (OSError, urllib.error.URLError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post('/crawl4ai/crawl')
    async def crawl4ai_crawl(payload: Dict[str, Any]) -> Dict[str, Any]:
        url = str(payload.get('url', '')).strip()
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail='valid_http_url_required')
        try:
            return await crawl_url(url)
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get('/diagnostics')
    def diagnostics() -> Dict[str, Any]:
        """Report concrete local consistency checks instead of a generic health flag."""
        workspace = Path(__file__).resolve().parent.parent
        checks = []
        canonical_memory = app.state.memory is app.state.brain.memory
        checks.append({
            'name': 'canonical_memory',
            'ok': canonical_memory,
            'issue': None if canonical_memory else 'Mehrere aktive Memory-Instanzen.',
            'next_step': None if canonical_memory else 'Runtime-Memory auf brain.memory umstellen.',
        })
        checks.append({
            'name': 'project_runner',
            'ok': app.state.project_runner.workspace == workspace.resolve(),
            'issue': None if app.state.project_runner.workspace == workspace.resolve()
            else 'ProjectRunner zeigt auf einen anderen Workspace.',
            'next_step': None if app.state.project_runner.workspace == workspace.resolve()
            else 'Workspace-Konfiguration prÃ¼fen.',
        })
        checks.append({
            'name': 'provider',
            'ok': bool(getattr(app.state.brain, 'provider', '')),
            'issue': None if getattr(app.state.brain, 'provider', '') else 'Kein Provider ausgewÃ¤hlt.',
            'next_step': None if getattr(app.state.brain, 'provider', '') else 'Provider-Konfiguration prÃ¼fen.',
        })
        return {
            'status': 'ok' if all(item['ok'] for item in checks) else 'action_required',
            'checks': checks,
            'integrations': app.state.integrations.status(),
            'repair_policy': [
                'erst Diagnose',
                'dann begrenzte lokale LÃ¶sung',
                'danach echte Verifikation',
                'bei fehlender BestÃ¤tigung keine Erfolgsbehauptung',
            ],
        }

    @app.post('/agents/route')
    def route_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get('prompt', '')).strip()
        if not prompt:
            raise HTTPException(status_code=400, detail='prompt_required')
        routing = app.state.agent_manager.route_prompt(prompt)
        return {'status': 'routed', 'routing': routing}

    @app.post('/agents/{parent_name}/subagents')
    def hire_subagents(parent_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(payload.get('task_id', '')).strip()
        requests = payload.get('requests', [])
        if not task_id:
            raise HTTPException(status_code=400, detail='task_id_required')
        if not isinstance(requests, list):
            raise HTTPException(status_code=400, detail='requests_must_be_list')
        try:
            hired = app.state.agent_manager.hire_subagents(parent_name, task_id, requests)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        app.state.publisher.publish('agents.hired', {
            'parent': parent_name,
            'task_id': task_id,
            'agents': hired,
            'policy': 'bounded_task_scoped_subagents',
        })
        return {
            'status': 'hired',
            'parent': parent_name,
            'task_id': task_id,
            'agents': hired,
            'limits': {
                'max_per_parent': app.state.agent_manager.MAX_SUBAGENTS_PER_PARENT,
                'max_dynamic_total': app.state.agent_manager.MAX_DYNAMIC_AGENTS,
                'max_depth': 1,
                'verifier_required': True,
            },
        }

    @app.post('/agents/{parent_name}/subagents/auto')
    def auto_hire_subagents(parent_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(payload.get('task_id', '')).strip()
        missing = payload.get('missing_capabilities', [])
        if not task_id:
            raise HTTPException(status_code=400, detail='task_id_required')
        if not isinstance(missing, list):
            raise HTTPException(status_code=400, detail='missing_capabilities_must_be_list')
        try:
            hired = app.state.agent_manager.hire_for_missing_capabilities(
                parent_name,
                task_id,
                missing,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        app.state.publisher.publish('agents.auto_hired', {
            'parent': parent_name,
            'task_id': task_id,
            'missing_capabilities': missing,
            'agents': hired,
            'policy': 'adaptive_capability_gap_hiring',
        })
        return {
            'status': 'hired',
            'parent': parent_name,
            'task_id': task_id,
            'reason': 'missing_capabilities',
            'agents': hired,
            'limits': {
                'max_per_parent': app.state.agent_manager.MAX_SUBAGENTS_PER_PARENT,
                'max_dynamic_total': app.state.agent_manager.MAX_DYNAMIC_AGENTS,
                'max_depth': 1,
                'verifier_required': True,
            },
        }

    @app.post('/agents/subagents/release')
    def release_subagents(payload: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(payload.get('task_id', '')).strip()
        if not task_id:
            raise HTTPException(status_code=400, detail='task_id_required')
        retired = app.state.agent_manager.release_task_subagents(task_id)
        app.state.publisher.publish('agents.released', {
            'task_id': task_id,
            'agents': retired,
        })
        return {'status': 'released', 'task_id': task_id, 'agents': retired}

    @app.get('/workflows')
    def list_workflows() -> Dict[str, Any]:
        return {'workflows': app.state.workflow_registry.list()}

    @app.post('/workflows/{workflow_name}/execute')
    def execute_workflow(workflow_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a registered workflow through its live, safety-aware handler."""
        try:
            result = app.state.workflow_registry.execute(workflow_name, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        app.state.audit.append('workflow.executed', {
            'workflow': workflow_name,
            'status': result.get('status'),
            'simulated': result.get('simulated', False),
        })
        app.state.publisher.publish('workflow.executed', {
            'workflow': workflow_name,
            'status': result.get('status'),
            'simulated': result.get('simulated', False),
        })
        return result

    @app.post('/tasks')
    def enqueue_task(payload: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(payload.get('kind') or payload.get('type', 'generic')).lower()
        task = app.state.task_queue.enqueue(kind, payload.get('payload') or payload)
        decision = app.state.supervisor.evaluate(payload)
        app.state.publisher.publish('task.enqueued', {'task_id': task.task_id, 'kind': kind, 'decision': decision})
        if decision['status'] == 'pending_confirmation':
            app.state.task_queue.set_status(task.task_id, 'pending_confirmation')
            return {'status': 'pending_confirmation', 'task_id': task.task_id, 'decision': decision}
        app.state.agent_manager.assign_task(task.task_id, kind)
        return {'status': 'queued', 'task_id': task.task_id, 'task': task.to_dict()}

    @app.post('/executor')
    def create_executor_request(payload: Dict[str, Any]) -> Dict[str, Any]:
        command = str(payload.get("command", "")).strip()
        action_type = str(payload.get("type", payload.get("action", ""))).strip().lower()
        if not command or not action_type:
            return {"status": "rejected", "error": "command und type sind erforderlich"}
        safety = send_safety_event(
            app.state.publisher.publish,
            action_type,
            payload.get("payload") or payload,
        )
        request = create_request(
            command,
            action_type,
            payload.get("payload") or payload,
            publisher=app.state.publisher.publish,
            permission_registry=app.state.permissions,
        )
        path = app.state.request_store.save_request(request)
        app.state.memory.append("executor_requests", request.to_dict())
        app.state.publisher.publish(
            "executor.request",
            {"request": request.to_dict(), "path": str(path)},
        )
        return {
            "status": "queued" if request.confirmed else "blocked",
            "allowlisted": request.context["allowlisted"],
            "safety": safety,
            "request": request.to_dict(),
        }

    @app.get('/permissions')
    def list_permissions() -> Dict[str, Any]:
        return {"grants": app.state.permissions.list()}

    @app.post('/permissions/grant')
    def grant_permission(payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action") or payload.get("type") or "").strip()
        if not action:
            raise HTTPException(status_code=400, detail="action is required")
        return {
            "grant": app.state.permissions.grant(
                action,
                payload.get("target"),
                payload.get("actor", "local"),
            )
        }

    @app.post('/permissions/revoke')
    def revoke_permission(payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action") or payload.get("type") or "").strip()
        if not action:
            raise HTTPException(status_code=400, detail="action is required")
        return {
            "revoked": app.state.permissions.revoke(
                action,
                payload.get("target"),
                payload.get("actor", "local"),
            )
        }

    @app.get('/executor/queue')
    def executor_queue() -> Dict[str, Any]:
        return {"requests": app.state.request_store.load_pending()}

    @app.get('/memory/search')
    def search_memory(query: str = "") -> Dict[str, Any]:
        needle = query.casefold().strip()
        results = []
        if needle:
            snapshot = app.state.memory.snapshot()
            for category, entries in snapshot.items():
                if not isinstance(entries, list):
                    entries = [entries]
                for entry in entries:
                    serialized = json.dumps(entry, ensure_ascii=False)
                    if needle in serialized.casefold():
                        results.append({
                            "store": "jarvis_v2_memory",
                            "category": category,
                            "entry": entry,
                        })
        return {"query": query, "results": results}

    @app.post('/tasks/{task_id}/confirm')
    def confirm_task(task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        approved = bool(payload.get('approved', False))
        task = app.state.task_queue.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail='task_not_found')
        if task.status != 'pending_confirmation':
            return {'status': 'not_pending', 'task_id': task_id, 'task_status': task.status}
        decision = app.state.supervisor.confirm(task_id, approved)
        if not approved:
            app.state.task_queue.set_status(task_id, 'rejected', {'error': 'user_rejected'})
            app.state.publisher.publish('task.confirmed', {'task_id': task_id, 'approved': False})
            return decision
        workflow_name = {
            'desktop': 'desktop',
            'browser': 'browser',
            'research': 'research',
            'monitoring': 'monitoring',
        }.get(task.kind)
        if workflow_name is None:
            result = {'ok': False, 'error': 'unsupported_task_kind'}
            app.state.task_queue.set_status(task_id, 'failed', result)
            return {'status': 'failed', 'task_id': task_id, 'result': result}
        result = app.state.workflow_registry.execute(
            workflow_name,
            {**task.payload, 'confirmed': True},
        )
        if result.get('status') == 'executed':
            app.state.task_queue.complete(task_id, result)
            final_status = 'completed'
        else:
            app.state.task_queue.set_status(task_id, 'failed', result)
            final_status = 'failed'
        app.state.publisher.publish('task.confirmed', {'task_id': task_id, 'approved': approved})
        return {
            'status': final_status,
            'task_id': task_id,
            'decision': decision,
            'result': result,
        }

    @app.post('/github/analyze')
    def github_analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            analysis = app.state.github_importer.analyze(payload.get('url', ''))
        except (GitHubImportError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        plan_id = uuid4().hex
        app.state.github_import_plans[plan_id] = {
            'url': analysis['source'],
            'created_at': datetime.now().isoformat(),
        }
        return {'status': 'planned', 'plan_id': plan_id, 'analysis': analysis}

    @app.post('/github/confirm')
    def github_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = str(payload.get('plan_id', '')).strip()
        record = app.state.github_import_plans.pop(plan_id, None)
        if not record:
            raise HTTPException(status_code=404, detail='github_plan_not_found_or_expired')
        if not bool(payload.get('confirmed', False)):
            return {'status': 'cancelled', 'message': 'Abgebrochen. Es wurde nichts importiert.'}
        try:
            result = app.state.github_importer.import_repository(
                record['url'],
                confirmed=True,
            )
        except (GitHubImportError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        app.state.publisher.publish('github.import_completed', {
            'source': record['url'],
            'verified': result.get('verified', False),
        })
        return result

    @app.get('/memory')
    def get_memory() -> Dict[str, Any]:
        return {'memory': app.state.memory.snapshot()}

    @app.post('/memory')
    def set_memory(payload: Dict[str, Any]) -> Dict[str, Any]:
        key = str(payload['key'])
        value = payload.get('value')
        saved = app.state.memory.set(key, value)
        app.state.publisher.publish('memory.updated', {'key': key, 'value': saved})
        return {'status': 'saved', 'key': key, 'value': saved}

    @app.post('/desktop/execute')
    def execute_desktop_action(payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get('action', '')).lower().strip()
        if action in {'click', 'type_text'} and not bool(payload.get('confirmed', False)):
            return {'status': 'confirmation_required', 'action': action}
        try:
            if action == 'open_app':
                result = app.state.desktop.open_app(str(payload.get('target', '')))
            elif action == 'open_url':
                result = app.state.desktop.open_url(str(payload.get('url', '')))
            elif action == 'screenshot':
                result = app.state.desktop.screenshot(payload.get('path'))
            elif action == 'click':
                result = app.state.desktop.click(int(payload['x']), int(payload['y']))
            elif action == 'type_text':
                result = app.state.desktop.type_text(str(payload.get('text', '')))
            else:
                return {'status': 'rejected', 'error': 'Aktion nicht erlaubt'}
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        app.state.publisher.publish('desktop.action', result)
        app.state.memory.append('desktop_actions', result)
        return result

    @app.post('/browser/flow')
    def execute_browser_flow(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run an explicit, verified browser flow without exposing credentials."""
        steps = payload.get('steps')
        if not isinstance(steps, list) or not steps:
            raise HTTPException(status_code=400, detail='steps muss eine nicht-leere Liste sein')
        confirmed = bool(payload.get('confirmed', False))
        result = app.state.workflow_registry.execute('browser', {
            'steps': steps,
            'timeout': payload.get('timeout', 20000),
            'confirmed': confirmed,
        })
        app.state.publisher.publish('browser.flow', {
            'ok': result.get('status') == 'executed',
            'error_code': result.get('error_code'),
            'step_count': len(steps),
        })
        return result

    return app


app = create_app()

