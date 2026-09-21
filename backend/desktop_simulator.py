from __future__ import annotations

from typing import Any, Dict


class DesktopSimulator:
    def __init__(self) -> None:
        self.enabled = True

    def open_app(self, app_name: str) -> Dict[str, Any]:
        return {'status': 'simulated', 'action': 'open_app', 'app': app_name, 'safe_mode': True}

    def click(self, target: str) -> Dict[str, Any]:
        return {'status': 'simulated', 'action': 'click', 'target': target, 'safe_mode': True}

    def type_text(self, text: str) -> Dict[str, Any]:
        return {'status': 'simulated', 'action': 'type_text', 'text': text, 'safe_mode': True}

    def take_screenshot(self, name: str = 'jarvis-screen') -> Dict[str, Any]:
        return {'status': 'simulated', 'action': 'take_screenshot', 'name': name, 'safe_mode': True}

    def status(self) -> Dict[str, Any]:
        return {'desktop': 'simulation_only', 'enabled': self.enabled}
