from backend.api import app

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.live.live_server:app", host="127.0.0.1", port=8787, reload=False)
