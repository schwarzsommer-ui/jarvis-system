def plan(query: str = "world news") -> dict:
    return {"workflow": "news_monitor", "status": "planned", "query": query, "external_fetch": False}
