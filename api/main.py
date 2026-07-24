import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import country_profile, countries, explorer, forecasts, historical, overview, scenarios
from .schemas import HealthResponse


def _normalize_deploy_prefix(raw: str | None) -> str:
    """Mirrors vite.config.ts's normalizeBase — reads the *same* DEPLOY_BASE_PATH env
    var the frontend build uses, so the two can't drift out of sync on what prefix is
    being stripped. Returned with no trailing slash (this strips a leading path
    segment, unlike the frontend's use of it as a base URL)."""
    if not raw or raw == "/":
        return ""
    return "/" + raw.strip("/")


DEPLOY_PATH_PREFIX = _normalize_deploy_prefix(os.environ.get("DEPLOY_BASE_PATH"))
DEPLOY_PATH_PREFIX_BYTES = DEPLOY_PATH_PREFIX.encode("utf-8")


class StripDeployPrefixMiddleware:
    """Cloudflare Tunnel forwards the full request path (e.g.
    /ghg-emissions-analysis/api/overview) with no prefix-stripping, but our routes
    are mounted at plain /api/... — strip the deploy prefix before routing, so the
    same app works both directly (Tailscale/local, no prefix) and behind the tunnel.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and DEPLOY_PATH_PREFIX:
            path = scope["path"]
            # Path-boundary check — a plain startswith() would also match e.g.
            # /ghg-emissions-analysis-foo, which isn't actually under this prefix.
            if path == DEPLOY_PATH_PREFIX or path.startswith(DEPLOY_PATH_PREFIX + "/"):
                scope["path"] = path[len(DEPLOY_PATH_PREFIX):] or "/"
                raw_path = scope.get("raw_path")
                if raw_path is not None and raw_path.startswith(DEPLOY_PATH_PREFIX_BYTES):
                    scope["raw_path"] = raw_path[len(DEPLOY_PATH_PREFIX_BYTES):] or b"/"
        await self.app(scope, receive, send)


# root_path=DEPLOY_PATH_PREFIX makes FastAPI/Starlette's own URL generation
# prefix-aware — notably /docs and /redoc compute their openapi.json URL from
# scope["root_path"] (see FastAPI.setup()'s swagger_ui_html/redoc_html closures),
# and openapi.json's "servers" entry is populated from it too. Confirmed empirically
# (constructed ASGI scopes directly) that this combination — root_path set here,
# StripDeployPrefixMiddleware still doing the actual path-stripping below — produces
# a correctly-prefixed openapi.json reference without any double-stripping: once our
# middleware strips DEPLOY_PATH_PREFIX from scope["path"], Starlette's own
# root_path-aware route matching (starlette._utils.get_route_path) is a no-op since
# path no longer starts with root_path by the time it runs.
#
# redirect_slashes (Starlette's default-on trailing-slash 307) is a separate matter:
# it builds its Location header from scope["path"] alone and is NOT root_path-aware
# regardless of the above — confirmed via direct source reading of
# starlette/routing.py — so it still redirects to a broken, prefix-less URL. None of
# our routes need slash-forgiving matching, so it stays disabled outright.
app = FastAPI(
    title="GHG Emissions Analysis API",
    redirect_slashes=False,
    root_path=DEPLOY_PATH_PREFIX,
)

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
app.include_router(explorer.router, prefix="/api")
app.include_router(countries.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")
