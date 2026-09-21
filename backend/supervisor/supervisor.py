from __future__ import annotations

from typing import Any, Dict

IRREVERSIBLE_ACTIONS = {
    'delete_file',
    'delete_folder',
    'shutdown',
    'restart',
    'send_message',
    'send_email',
    'purchase',
    'trade',
    'external_call',
    'install_dependency',
    'execute_shell',
    'write_system_file',
}


class Supervisor:
    def __init__(self) -> None:
        self.confirmations: Dict[str, bool] = {}

    def evaluate(self, action: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(action.get('kind') or action.get('type', 'safe')).lower()
        requires_confirmation = bool(action.get('requires_confirmation')) or kind in IRREVERSIBLE_ACTIONS
        if requires_confirmation:
            return {
                'status': 'pending_confirmation',
                'requires_confirmation': True,
                'kind': kind,
                'message': 'This action is irreversible and requires explicit user confirmation.',
            }
        return {'status': 'approved', 'requires_confirmation': False, 'kind': kind}

    def confirm(self, task_id: str, approved: bool = True) -> Dict[str, Any]:
        self.confirmations[task_id] = bool(approved)
        if not approved:
            return {'status': 'rejected', 'task_id': task_id}
        return {'status': 'confirmed', 'task_id': task_id}

    def is_confirmed(self, task_id: str) -> bool:
        return bool(self.confirmations.get(task_id, False))
