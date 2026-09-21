from __future__ import annotations

from typing import Any, Dict, List, Optional


class WorkflowRegistry:
    def __init__(
        self,
        *,
        desktop: Any = None,
        browser_executor: Any = None,
        research_handler: Any = None,
        monitoring: Any = None,
    ) -> None:
        self.desktop = desktop
        self.browser_executor = browser_executor
        self.research_handler = research_handler
        self.monitoring = monitoring
        self._workflows: Dict[str, Dict[str, Any]] = {}
        self.register(
            'monitoring',
            {
                'name': 'monitoring',
                'description': 'Monitor local status and collect live read-only findings.',
                'steps': ['collect context', 'analyze drift', 'report findings'],
                'safe_mode': True,
                'simulated': False,
                'execution': 'live',
            },
        )
        self.register(
            'desktop',
            {
                'name': 'desktop',
                'description': 'Operate the local desktop with explicit safety gates.',
                'steps': ['open app', 'read window', 'click target'],
                'safe_mode': True,
                'simulated': False,
                'execution': 'live',
            },
        )
        self.register(
            'research',
            {
                'name': 'research',
                'description': 'Gather local evidence and provide structured findings.',
                'steps': ['scope question', 'collect evidence', 'summarize'],
                'safe_mode': True,
                'simulated': False,
                'execution': 'live',
            },
        )
        self.register(
            'browser',
            {
                'name': 'browser',
                'description': 'Run explicit browser steps through the verified live browser handler.',
                'steps': ['navigate', 'inspect', 'act'],
                'safe_mode': True,
                'simulated': False,
                'execution': 'live',
            },
        )

    def register(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._workflows[name] = payload
        return payload

    def list(self) -> List[Dict[str, Any]]:
        return [value for value in self._workflows.values()]

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self._workflows.get(name)

    def execute(self, name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        workflow = self._workflows.get(name)
        if workflow is None:
            raise KeyError(f'Unknown workflow: {name}')
        data = dict(payload or {})
        if name == 'monitoring':
            return self._execute_monitoring(data)
        if name == 'desktop':
            return self._execute_desktop(data)
        if name == 'research':
            if not self.research_handler:
                return self._unavailable(name, data)
            query = str(data.get('query', '')).strip()
            if not query:
                return self._failed(name, data, 'query_required')
            return self._live(name, data, self.research_handler(query))
        if name == 'browser':
            if not self.browser_executor:
                return self._unavailable(name, data)
            steps = data.get('steps')
            if not isinstance(steps, list) or not steps:
                return self._failed(name, data, 'steps_required')
            return self._live(
                name,
                data,
                self.browser_executor(
                    'browser_execute_steps',
                    steps=steps,
                    timeout=data.get('timeout', 20000),
                    confirmed=bool(data.get('confirmed', False)),
                ),
            )
        return self._unavailable(name, data)

    def _execute_monitoring(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.monitoring:
            return self._unavailable('monitoring', payload)
        operation = str(payload.get('operation', 'news')).strip().lower()
        handler = getattr(self.monitoring, operation, None)
        if not callable(handler):
            return self._failed('monitoring', payload, 'unsupported_operation')
        return self._live('monitoring', payload, handler())

    def _execute_desktop(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.desktop:
            return {
                'workflow': 'desktop',
                'status': 'simulated',
                'safe_mode': True,
                'simulated': True,
                'input': payload,
                'result': {
                    'ok': True,
                    'message': 'Kein Live-Desktop-Handler angeschlossen; Ablauf wurde nur simuliert.',
                },
            }
        action = str(payload.get('action', 'status')).strip().lower()
        if action in {'click', 'type_text'} and not bool(payload.get('confirmed', False)):
            return {
                'workflow': 'desktop',
                'status': 'confirmation_required',
                'safe_mode': True,
                'simulated': False,
                'input': payload,
                'action': action,
                'error_code': 'confirmation_required',
                'ok': False,
            }
        try:
            if action == 'open_app':
                result = self.desktop.open_app(str(payload.get('target', '')))
            elif action == 'open_url':
                result = self.desktop.open_url(str(payload.get('url', '')))
            elif action == 'screenshot':
                result = self.desktop.screenshot(payload.get('path'))
            elif action == 'click':
                result = self.desktop.click(int(payload['x']), int(payload['y']))
            elif action == 'type_text':
                result = self.desktop.type_text(str(payload.get('text', '')))
            elif action == 'status':
                result = self.desktop.status()
            else:
                return self._failed('desktop', payload, 'unsupported_action')
        except (KeyError, TypeError, ValueError) as exc:
            return self._failed('desktop', payload, str(exc))
        return self._live('desktop', payload, result)

    @staticmethod
    def _live(name: str, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return {
                'workflow': name,
                'status': 'failed',
                'safe_mode': True,
                'simulated': False,
                'input': payload,
                'error': 'unverified_result',
            }
        if result.get('error_code') == 'confirmation_required':
            status = 'confirmation_required'
        elif result.get('ok') is True:
            status = 'executed'
        else:
            status = 'failed'
        return {
            'workflow': name,
            'status': status,
            'safe_mode': True,
            'simulated': False,
            'input': payload,
            'result': result,
        }

    @staticmethod
    def _unavailable(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return WorkflowRegistry._failed(name, payload, 'handler_unavailable')

    @staticmethod
    def _failed(name: str, payload: Dict[str, Any], error: str) -> Dict[str, Any]:
        return {
            'workflow': name,
            'status': 'failed',
            'safe_mode': True,
            'simulated': False,
            'input': payload,
            'error': error,
        }
