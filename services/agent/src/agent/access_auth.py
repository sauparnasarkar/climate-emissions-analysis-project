"""Defence in depth for the admin endpoints: verify the Cloudflare Access JWT in the app.

`/admin/llm` is gated by a Cloudflare Access path rule at the edge. That rule is the only thing
standing between the public internet and the model switch, so this module makes the app check
what Access already asserts: every request Access lets through carries a signed
`Cf-Access-Jwt-Assertion` header. With `CF_ACCESS_TEAM_DOMAIN` (e.g. `myteam.cloudflareaccess.com`)
and `CF_ACCESS_AUD` (the application's audience tag, from the Access application's overview page)
set, a request without a valid token for this application is refused with 403, so a dropped or
misordered edge rule no longer exposes the endpoint.

Unset, the check is skipped with a warning at first use, so local development and a deploy that has
not configured it yet behave exactly as before.
"""

from __future__ import annotations

import logging
import os

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

ACCESS_JWT_HEADER = "cf-access-jwt-assertion"
_warned_unconfigured = False
_jwk_clients: dict[str, PyJWKClient] = {}


def _config() -> tuple[str, str] | None:
    team = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").strip().removeprefix("https://").strip("/")
    audience = os.environ.get("CF_ACCESS_AUD", "").strip()
    return (team, audience) if team and audience else None


def _jwk_client(team: str) -> PyJWKClient:
    if team not in _jwk_clients:
        _jwk_clients[team] = PyJWKClient(f"https://{team}/cdn-cgi/access/certs", cache_keys=True, timeout=5)
    return _jwk_clients[team]


def require_admin_access(request: Request) -> None:
    global _warned_unconfigured
    config = _config()
    if config is None:
        if not _warned_unconfigured:
            _warned_unconfigured = True
            logger.warning("CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUD are not set -- admin endpoints rely on the Cloudflare edge rule alone")
        return
    team, audience = config
    token = request.headers.get(ACCESS_JWT_HEADER)
    if not token:
        raise HTTPException(status_code=403, detail="Admin access requires a Cloudflare Access login.")
    try:
        key = _jwk_client(team).get_signing_key_from_jwt(token).key
        jwt.decode(token, key, algorithms=["RS256"], audience=audience, issuer=f"https://{team}", options={"require": ["exp", "iat", "aud", "iss"]})
    except Exception:
        # Invalid, expired, wrong-audience and key-fetch failures all refuse the request; the reason stays in the log.
        logger.warning("admin request refused: Cloudflare Access token did not verify", exc_info=True)
        raise HTTPException(status_code=403, detail="Admin access requires a Cloudflare Access login.") from None
