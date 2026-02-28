"""FastAPI application factory for Viral Clipper Web UI."""

import base64
import os
import mimetypes
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Ensure correct MIME types are registered regardless of OS/registry state.
# On some Windows systems the registry maps .css to text/plain, which causes
# browsers to reject the stylesheet. Explicitly registering here takes priority.
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/javascript", ".js")

from fastapi.responses import Response as FastAPIResponse
from web.database import init_db

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
PROJECT_ROOT = WEB_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# Routes that don't require authentication (static assets)
_PUBLIC_PREFIXES = ("/app.css", "/app.js", "/static/", "/clips/", "/source/")


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Auth gate for the web UI."""

    def __init__(self, app, username: str, password: str):
        super().__init__(app)
        self._username = username
        self._password = password

    async def dispatch(self, request: Request, call_next):
        # Skip auth for static assets
        path = request.url.path
        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                supplied_user, supplied_pass = decoded.split(":", 1)
                if supplied_user == self._username and supplied_pass == self._password:
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Viral Clipper"'},
            content="Unauthorized",
        )


def create_app() -> FastAPI:
    app = FastAPI(title="Viral Clipper", docs_url="/docs")

    username = os.environ.get("CLIPPER_USER", "admin")
    password = os.environ.get("CLIPPER_PASS", "clipper")
    app.add_middleware(BasicAuthMiddleware, username=username, password=password)

    @app.get("/app.css")
    async def serve_css():
        return FastAPIResponse(
            content=(STATIC_DIR / "style.css").read_bytes(),
            media_type="text/css; charset=utf-8",
        )

    @app.get("/app.js")
    async def serve_js():
        return FastAPIResponse(
            content=(STATIC_DIR / "app.js").read_bytes(),
            media_type="text/javascript; charset=utf-8",
        )

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    # Mount static assets
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Mount output directories so clips/source videos are servable
    clips_dir = OUTPUT_DIR / "clips"
    source_dir = OUTPUT_DIR / "source"
    clips_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/clips", StaticFiles(directory=str(clips_dir)), name="clips")
    app.mount("/source", StaticFiles(directory=str(source_dir)), name="source")

    @app.on_event("startup")
    async def startup():
        await init_db()
        from web.scheduler import start_scheduler
        start_scheduler()

    @app.on_event("shutdown")
    async def shutdown():
        from web.scheduler import stop_scheduler
        stop_scheduler()

    # Register routes
    from web.routes.pages import router as pages_router
    from web.routes.jobs import router as jobs_router
    from web.routes.clips import router as clips_router
    from web.routes.config import router as config_router
    from web.routes.watchlist import router as watchlist_router

    app.include_router(pages_router)
    app.include_router(jobs_router, prefix="/api")
    app.include_router(clips_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(watchlist_router, prefix="/api")

    return app
