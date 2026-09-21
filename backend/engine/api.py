from backend.api import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.engine.api:app", host="127.0.0.1", port=8787, reload=False)
