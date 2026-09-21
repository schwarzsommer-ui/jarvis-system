"""Start the bounded V2 API for the local dashboard."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("backend.api:app", host="127.0.0.1", port=8787, reload=False)
