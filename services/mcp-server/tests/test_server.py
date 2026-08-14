from mcp_server.resolution import CountryLists, fetch_country_lists
from mcp_server.server import _normalize_deploy_prefix, _streamable_http_settings, list_countries


async def test_list_countries_tool_returns_the_three_scopes(api_client):
    body = await list_countries()
    assert set(body.keys()) == {"featured", "expanded", "sovereign"}
    assert isinstance(body["sovereign"], list)


async def test_fetch_country_lists_wraps_the_same_data(api_client):
    lists = await fetch_country_lists()
    assert isinstance(lists, CountryLists)
    assert lists.featured
    assert lists.sovereign


def test_normalize_deploy_prefix():
    # Mirrors api/tests/test_main.py's own test_normalize_deploy_prefix exactly -- the two
    # functions must behave identically since both derive from the same DEPLOY_BASE_PATH env
    # var (ARCHITECTURE.md §5/§6), even though they're separate, hand-mirrored copies.
    assert _normalize_deploy_prefix(None) == ""
    assert _normalize_deploy_prefix("/") == ""
    assert _normalize_deploy_prefix("prefix") == "/prefix"
    assert _normalize_deploy_prefix("/prefix/") == "/prefix"
    assert _normalize_deploy_prefix("prefix/") == "/prefix"


def test_streamable_http_settings_unset_is_permissive_default():
    path, security = _streamable_http_settings(None)
    assert path == "/mcp"
    # None, not an empty TransportSecuritySettings -- the latter's allowed_hosts/allowed_origins
    # default to [], which would reject every request rather than preserving local-dev access.
    assert security is None


def test_streamable_http_settings_set_locks_to_the_tunnel_hostname():
    path, security = _streamable_http_settings("/ghg-emissions-analysis/")
    assert path == "/ghg-emissions-analysis/mcp"
    assert security is not None
    assert security.allowed_hosts == ["labs.syena.io", "127.0.0.1:8765", "localhost:8765"]
    assert security.allowed_origins == ["https://labs.syena.io"]


def test_streamable_http_settings_allows_the_colocated_agent_over_loopback():
    # services/agent's MCP connection (SPEC.md §8, services/agent/CLAUDE.md's B3 boundary) never
    # goes through the Cloudflare Tunnel -- it's a direct loopback request, so its Host header is
    # always 127.0.0.1:8765 or localhost:8765, never labs.syena.io. A real deploy dry-run got
    # 421 Misdirected Request before this fix (allowed_hosts locked to labs.syena.io only).
    _, security = _streamable_http_settings("/ghg-emissions-analysis/")
    assert "127.0.0.1:8765" in security.allowed_hosts
    assert "localhost:8765" in security.allowed_hosts


def test_streamable_http_settings_deployed_at_root_still_enables_security():
    # DEPLOY_BASE_PATH="/" is a legitimate "deployed at root" value -- it normalizes to an
    # empty, falsy prefix (matching api/main.py's own _normalize_deploy_prefix("/") == ""),
    # but that must not be mistaken for "not deployed." Keying the security toggle off the
    # normalized prefix instead of the raw env var would silently drop DNS-rebinding
    # protection for this real deploy configuration -- caught in PR #140 review.
    path, security = _streamable_http_settings("/")
    assert path == "/mcp"
    assert security is not None
    assert security.allowed_hosts == ["labs.syena.io", "127.0.0.1:8765", "localhost:8765"]
