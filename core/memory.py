import json
import os
import re
from threading import RLock
from datetime import datetime
from pathlib import Path

class JarvisMemory:
    def __init__(self, filepath=None):
        project_root = Path(__file__).resolve().parents[1]
        self.filepath = Path(filepath) if filepath else project_root / "core" / "memory.json"
        self.second_brain = self.filepath.parent.parent / "SecondBrain"
        self.collections = (
            "patterns", "preferences", "context", "improvements", "intents",
            "shortcuts", "projects", "history", "summaries", "style",
            "persona", "predict", "knowledge",
        )
        self.graph_path = self.second_brain / "knowledge" / "memory_graph.json"
        self.system_store_path = self.second_brain / "system_memory.json"
        self._lock = RLock()
        self.ensure_storage()

    def ensure_storage(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self.filepath.exists():
            with self.filepath.open("w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=4)
        self.second_brain.mkdir(parents=True, exist_ok=True)
        for name in self.collections:
            target = self.second_brain / name
            target.mkdir(parents=True, exist_ok=True) if name in ("knowledge", "history", "summaries") else None
            if name not in ("knowledge", "history", "summaries") and not target.exists():
                target.write_text("[]", encoding="utf-8")
        persona = self.second_brain / "persona.json"
        if not persona.exists():
            persona.write_text(json.dumps({
                "owner": "Sommer",
                "style": ["direkt", "kurz", "souverän", "futuristisch"],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        if not self.graph_path.exists():
            self.graph_path.write_text(json.dumps({
                "version": 1,
                "updated_at": None,
                "nodes": [],
                "edges": [],
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_system_store(self):
        try:
            value = json.loads(self.system_store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        return value if isinstance(value, dict) else {}

    def _save_system_store(self, value):
        self.system_store_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.system_store_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.system_store_path)

    # Compatibility API used by the backend. Keeping it here makes this
    # implementation the single runtime memory authority.
    def set(self, key, value):
        with self._lock:
            store = self._load_system_store()
            store[str(key)] = value
            self._save_system_store(store)
        return value

    def get(self, key, default=None):
        with self._lock:
            return self._load_system_store().get(str(key), default)

    def delete(self, key):
        with self._lock:
            store = self._load_system_store()
            store.pop(str(key), None)
            self._save_system_store(store)

    def append(self, key, value):
        with self._lock:
            store = self._load_system_store()
            values = store.get(str(key), [])
            if not isinstance(values, list):
                values = [values]
            values.append(value)
            store[str(key)] = values
            self._save_system_store(store)
            return list(values)

    def snapshot(self):
        with self._lock:
            return self._load_system_store()

    def behavior_profile(self):
        profile_path = self.filepath.parent.parent / "config" / "jarvis_behavior_profile.json"
        try:
            value = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def load(self):
        try:
            with self.filepath.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def remember(self, role, text):
        data = self.load()

        data.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "role": role,
            "text": text
        })

        with self.filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        self.record("history", {"role": role, "text": text, "timestamp": datetime.now().isoformat()})

    @staticmethod
    def _redact(text):
        value = str(text or "")
        value = re.sub(r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
        value = re.sub(r"\b(?:sk|gsk|xai)-[A-Za-z0-9_-]{16,}\b", "[REDACTED_KEY]", value)
        return value[:12000]

    def remember_interaction(self, prompt, answer, intent="", state=None):
        """Persist a local, redacted interaction and its reusable execution pattern."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": self._redact(prompt),
            "answer": self._redact(answer),
            "intent": str(intent or ""),
            "state": {
                key: value for key, value in (state or {}).items()
                if key in {"current_app", "current_url", "last_scene", "last_search_query"}
            },
        }
        self.record("patterns", entry)
        self._update_graph(
            prompt,
            metadata={"kind": "interaction", "intent": str(intent or "")},
        )

    def remember_user_input(self, prompt, source="user"):
        """Persist every incoming request before routing or execution."""
        value = self._redact(prompt).strip()
        if not value:
            return
        self.record("patterns", {
            "timestamp": datetime.now().isoformat(),
            "prompt": value,
            "answer": "",
            "intent": "incoming_request",
            "source": str(source or "user"),
        })
        self._update_graph(value, metadata={"kind": "incoming_request", "source": source})

    def remember_preference(self, text, source="user"):
        value = self._redact(text).strip()
        if value:
            self.record("preferences", {
                "timestamp": datetime.now().isoformat(),
                "text": value,
                "source": source,
            })
            self._update_graph(value, metadata={"kind": "preference", "source": source})

    @staticmethod
    def _graph_key(value):
        value = re.sub(r"\s+", " ", str(value or "").strip().lower())
        value = re.sub(r"[^a-z0-9äöüß:_./ -]", "", value)
        return value[:100]

    @classmethod
    def _graph_entities(cls, text):
        value = cls._redact(text).lower()
        aliases = {
            "xauusd": ("market", "XAUUSD"),
            "gold": ("market", "XAUUSD"),
            "dxy": ("market", "DXY"),
            "btc": ("market", "BTCUSDT"),
            "bitcoin": ("market", "BTCUSDT"),
            "tradingview": ("app", "TradingView"),
            "zoey": ("app", "Zoey OS"),
            "browser": ("app", "Browser"),
            "jarvis": ("system", "J.A.R.V.I.S."),
            "voice": ("capability", "Voice"),
            "stimme": ("capability", "Voice"),
            "second brain": ("concept", "Second Brain"),
            "memory": ("concept", "Second Brain"),
        }
        found = {}
        for alias, (kind, label) in aliases.items():
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", value):
                found[cls._graph_key(f"{kind}:{label}")] = {
                    "id": cls._graph_key(f"{kind}:{label}"),
                    "label": label,
                    "kind": kind,
                }
        for phrase in re.findall(r"\b(?:ziel|projekt|routine|workflow|aufgabe|präferenz)\s*[:=]\s*[^,.!?]{3,80}", value):
            label = re.sub(r"\s+", " ", phrase).strip()
            node_id = cls._graph_key(f"topic:{label}")
            found[node_id] = {"id": node_id, "label": label, "kind": "topic"}
        return list(found.values())

    def _load_graph(self):
        try:
            data = json.loads(self.graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("version", 1)
        data.setdefault("updated_at", None)
        data.setdefault("nodes", [])
        data.setdefault("edges", [])
        return data

    def _update_graph(self, text, metadata=None):
        entities = self._graph_entities(text)
        if not entities:
            return {"nodes_added": 0, "edges_added": 0}
        graph = self._load_graph()
        nodes = {item.get("id"): item for item in graph["nodes"] if isinstance(item, dict) and item.get("id")}
        for entity in entities:
            node = nodes.setdefault(entity["id"], {
                **entity,
                "count": 0,
                "last_seen": None,
                "metadata": {},
            })
            node["count"] = int(node.get("count", 0)) + 1
            node["last_seen"] = datetime.now().isoformat()
            if metadata:
                node["metadata"].update(metadata)
        edges = {
            (item.get("source"), item.get("target")): item
            for item in graph["edges"]
            if isinstance(item, dict) and item.get("source") and item.get("target")
        }
        for left_index, left in enumerate(entities):
            for right in entities[left_index + 1:]:
                key = (left["id"], right["id"])
                reverse = (right["id"], left["id"])
                edge = edges.get(key) or edges.get(reverse)
                if edge is None:
                    edge = {
                        "source": left["id"],
                        "target": right["id"],
                        "relation": "co_occurs",
                        "weight": 0,
                    }
                    edges[key] = edge
                edge["weight"] = int(edge.get("weight", 0)) + 1
                edge["last_seen"] = datetime.now().isoformat()
        graph["nodes"] = sorted(nodes.values(), key=lambda item: item.get("count", 0), reverse=True)[:1000]
        graph["edges"] = sorted(edges.values(), key=lambda item: item.get("weight", 0), reverse=True)[:3000]
        graph["updated_at"] = datetime.now().isoformat()
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "nodes_added": len(entities),
            "edges_added": max(0, len(entities) * (len(entities) - 1) // 2),
        }

    def graph_context(self, query, limit=8):
        entities = self._graph_entities(query)
        if not entities:
            return []
        graph = self._load_graph()
        ids = {item["id"] for item in entities}
        neighbours = {}
        for edge in graph.get("edges", []):
            if edge.get("source") in ids:
                neighbours.setdefault(edge.get("target"), 0)
                neighbours[edge.get("target")] += int(edge.get("weight", 1))
            if edge.get("target") in ids:
                neighbours.setdefault(edge.get("source"), 0)
                neighbours[edge.get("source")] += int(edge.get("weight", 1))
        nodes = {item.get("id"): item for item in graph.get("nodes", [])}
        return [
            nodes[node_id] for node_id, _ in sorted(
                neighbours.items(), key=lambda item: item[1], reverse=True
            )[:limit] if node_id in nodes
        ]

    def graph_snapshot(self):
        graph = self._load_graph()
        return {
            "updated_at": graph.get("updated_at"),
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
        }

    def train_from_history(self):
        """Build a bounded, local routine index from prior conversations."""
        history = self.load()
        pattern_path = self.second_brain / "patterns"
        try:
            patterns = json.loads(pattern_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            patterns = []
        if isinstance(patterns, list):
            history = history + [
                {"role": "Benutzer", "text": item.get("prompt", "")}
                for item in patterns
                if isinstance(item, dict) and item.get("prompt")
            ]
        routines = {}
        graph_updates = 0
        for item in history:
            if not isinstance(item, dict) or item.get("role") != "Benutzer":
                continue
            prompt = self._redact(item.get("text", "")).strip()
            if len(prompt) < 4:
                continue
            if self._update_graph(prompt).get("nodes_added"):
                graph_updates += 1
            answer = ""
            for candidate in reversed(history):
                if candidate.get("role") == "JARVIS":
                    answer = str(candidate.get("text", ""))
                    break
            lowered = prompt.lower()
            if any(word in lowered for word in ("tradingview", "btc", "xauusd", "dxy", "markt")):
                category = "markets"
            elif any(word in lowered for word in ("öffne", "oeffne", "browser", "app", "desktop", "fenster")):
                category = "desktop"
            elif any(word in lowered for word in ("suche", "news", "nachrichten", "recherch")):
                category = "research"
            elif any(word in lowered for word in ("speicher", "merk dir", "präferenz", "bevorzuge")):
                category = "preferences"
            else:
                category = "general"
            key = re.sub(r"[^a-z0-9äöüß]+", " ", lowered).strip()
            entry = routines.setdefault(key, {
                "category": category,
                "examples": [],
                "count": 0,
            })
            entry["count"] += 1
            if len(entry["examples"]) < 3:
                entry["examples"].append({
                    "prompt": prompt,
                    "answer_preview": self._redact(answer)[:500],
                })
        learned = sorted(
            routines.values(),
            key=lambda value: value["count"],
            reverse=True,
        )[:500]
        target = self.second_brain / "knowledge" / "learned_routines.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({
                "trained_at": datetime.now().isoformat(),
                "source_entries": len(history),
                "routine_count": len(learned),
                "routines": learned,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.record("improvements", {
            "timestamp": datetime.now().isoformat(),
            "type": "history_training",
            "source_entries": len(history),
            "routine_count": len(learned),
        })
        return {
            "source_entries": len(history),
            "routine_count": len(learned),
            "categories": sorted({item["category"] for item in learned}),
            "graph_updates": graph_updates,
            "graph": self.graph_snapshot(),
        }

    def relevant_context(self, query, limit=5):
        """Return recent matching patterns/facts for the next request."""
        tokens = {
            token for token in re.findall(r"[a-z0-9äöüß]{4,}", str(query or "").lower())
            if token not in {"öffne", "oeffne", "bitte", "mach", "dann", "dieser", "diese"}
        }
        candidates = []
        for item in self.load():
            if isinstance(item, dict) and item.get("role") == "Benutzer-Fakt":
                candidates.append(("fact", item.get("text", ""), item))
        patterns = self.second_brain / "patterns"
        if patterns.exists() and patterns.is_file():
            try:
                stored = json.loads(patterns.read_text(encoding="utf-8"))
                if not isinstance(stored, list):
                    stored = []
                for item in stored[-100:]:
                    if not isinstance(item, dict):
                        continue
                    candidates.append(("pattern", item.get("prompt", ""), item))
            except OSError:
                pass
            except json.JSONDecodeError:
                pass
        learned = self.second_brain / "knowledge" / "learned_routines.json"
        if learned.exists():
            try:
                data = json.loads(learned.read_text(encoding="utf-8"))
                for routine in data.get("routines", []) if isinstance(data, dict) else []:
                    for example in routine.get("examples", []):
                        candidates.append(("routine", example.get("prompt", ""), example))
            except (OSError, json.JSONDecodeError):
                pass
        scored = []
        for kind, text, item in candidates:
            haystack = str(text).lower()
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, kind, item))
        scored.sort(key=lambda value: (value[0], value[2].get("timestamp", "")), reverse=True)
        results = [item for _, _, item in scored[:limit]]
        connected = self.graph_context(query, limit=max(2, limit))
        for node in connected:
            results.append({
                "memory_type": "connected_entity",
                "entity": node.get("label"),
                "kind": node.get("kind"),
                "count": node.get("count", 0),
            })
        return results[:limit + len(connected)]

    def record(self, collection, value):
        target = self.second_brain / collection
        if collection in ("knowledge", "history", "summaries"):
            target.mkdir(parents=True, exist_ok=True)
            filename = target / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
            filename.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            return
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
        if not isinstance(data, list):
            data = []
        data.append(value)
        target.write_text(json.dumps(data[-500:], ensure_ascii=False, indent=2), encoding="utf-8")

    def recent(self, limit=8):
        return self.load()[-limit:]

    def facts(self):
        return [
            item["text"]
            for item in self.load()
            if isinstance(item, dict)
            and item.get("role") == "Benutzer-Fakt"
            and item.get("text")
        ][-20:]
