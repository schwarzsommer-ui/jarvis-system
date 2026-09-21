import importlib.util
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Plugin:
    name: str
    description: str
    run: object
    path: str


class PluginRegistry:
    """Loads optional local skills without allowing one bad plugin to stop startup."""

    def __init__(self, directory=None):
        self.directory = Path(directory or Path(__file__).resolve().parents[1] / "plugins")
        self.plugins = {}
        self.reload()

    def reload(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.plugins.clear()
        for path in sorted(self.directory.glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"jarvis_plugin_{path.stem}", path
                )
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                name = getattr(module, "NAME", path.stem)
                run = getattr(module, "run", None)
                if callable(run):
                    self.plugins[name] = Plugin(
                        name=name,
                        description=getattr(module, "DESCRIPTION", ""),
                        run=run,
                        path=str(path),
                    )
            except Exception:
                continue

    def list(self):
        return [
            {"name": plugin.name, "description": plugin.description, "path": plugin.path}
            for plugin in self.plugins.values()
        ]

    def run(self, name, payload):
        plugin = self.plugins.get(name)
        if not plugin:
            return f"Plugin nicht gefunden: {name}"
        return str(plugin.run(payload))
