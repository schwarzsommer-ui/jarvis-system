from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4


QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
QDRANT_COLLECTION = os.getenv("JARVIS_QDRANT_COLLECTION", "jarvis_memory")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def _json_request(url: str, method: str = "GET", payload: Any = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def embed_text(text: str) -> list[float]:
    result = _json_request(
        f"{OLLAMA_URL}/api/embeddings",
        "POST",
        {"model": OLLAMA_EMBED_MODEL, "prompt": text},
    )
    embedding = result.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError("Ollama returned no embedding.")
    return [float(value) for value in embedding]


def ensure_qdrant_collection(vector_size: int) -> dict[str, Any]:
    try:
        current = _json_request(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
        return {"ok": True, "created": False, "collection": current.get("result", {})}
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    _json_request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
        "PUT",
        {"vectors": {"size": vector_size, "distance": "Cosine"}},
    )
    return {"ok": True, "created": True, "collection": QDRANT_COLLECTION}


def upsert_memory(text: str, payload: dict[str, Any]) -> dict[str, Any]:
    vector = embed_text(text)
    ensure_qdrant_collection(len(vector))
    point_id = str(uuid4())
    _json_request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points?wait=true",
        "PUT",
        {"points": [{"id": point_id, "vector": vector, "payload": {"text": text, **payload}}]},
    )
    return {"ok": True, "id": point_id, "collection": QDRANT_COLLECTION}


def search_memory(query: str, limit: int = 5) -> dict[str, Any]:
    vector = embed_text(query)
    ensure_qdrant_collection(len(vector))
    result = _json_request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
        "POST",
        {"vector": vector, "limit": max(1, min(limit, 20)), "with_payload": True},
    )
    return {"ok": True, "query": query, "results": result.get("result", [])}


async def crawl_url(url: str) -> dict[str, Any]:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise RuntimeError("crawl4ai is not installed in the active runtime.") from exc

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
    if not getattr(result, "success", False):
        raise RuntimeError(getattr(result, "error_message", "Crawl4AI crawl failed."))
    return {
        "ok": True,
        "url": url,
        "title": getattr(result, "title", None),
        "markdown": (getattr(result, "markdown", "") or "")[:30000],
    }


def plan_with_langgraph(prompt: str) -> dict[str, Any]:
    try:
        from langgraph.graph import END, START, StateGraph
        from typing_extensions import TypedDict
    except ImportError as exc:
        raise RuntimeError("langgraph is not installed in the active runtime.") from exc

    class State(TypedDict):
        prompt: str
        steps: list[str]

    def understand(state: State) -> State:
        return {**state, "steps": ["understand request", "check capabilities", "execute verified action", "verify result"]}

    graph = StateGraph(State)
    graph.add_node("understand", understand)
    graph.add_edge(START, "understand")
    graph.add_edge("understand", END)
    result = graph.compile().invoke({"prompt": prompt, "steps": []})
    return {"ok": True, "prompt": prompt, "steps": result["steps"]}
