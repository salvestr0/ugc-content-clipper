"""Entry point for Viral Clipper Web UI."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("web.app:create_app", factory=True, host="127.0.0.1", port=8000, reload=True)
