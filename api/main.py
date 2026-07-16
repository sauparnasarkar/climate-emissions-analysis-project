from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import country_profile, forecasts, historical, overview, scenarios
from .schemas import HealthResponse

DEPLOY_PATH_PREFIX = "/ghg-emissions-analysis"


class StripDeployPrefixMiddleware:
    """Cloudflare Tunnel forwards the full request path (e.g.
    /ghg-emissions-analysis/api/overview) with no prefix-stripping, but our routes
    are mounted at plain /api/... — strip the deploy prefix before routing, so the
    same app works both directly (Tailscale/local, no prefix) and behind the tunnel.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]
            # Path-boundary check — a plain startswith() would also match e.g.
            # /ghg-emissions-analysis-foo, which isn't actually under this prefix.
            if path == DEPLOY_PATH_PREFIX or path.startswith(DEPLOY_PATH_PREFIX + "/"):
                scope["path"] = path[len(DEPLOY_PATH_PREFIX):] or "/"
                raw_path = scope.get("raw_path")
                if raw_path is not None:
                    prefix_bytes = DEPLOY_PATH_PREFIX.encode("utf-8")
                    if raw_path.startswith(prefix_bytes):
                        scope["raw_path"] = raw_path[len(prefix_bytes):] or b"/"
        await self.app(scope, receive, send)


app = FastAPI(title="GHG Emissions Analysis API")

app.add_middleware(StripDeployPrefixMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(overview.router, prefix="/api")
app.include_router(historical.router, prefix="/api")
app.include_router(country_profile.router, prefix="/api")
app.include_router(forecasts.router, prefix="/api")
app.include_router(scenarios.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")
