"""Country identifier resolution guard (SPEC.md §3.1).

The wrapped API takes plain OWID-canonical country-name strings and silently drops anything
that doesn't match -- fine for a chart with an empty series, worse for an LLM agent that has
no way to notice the drop. This module gives every tool that accepts a country/countries
argument a chance to self-correct instead: exact match, then a confident fuzzy match, then an
explicit error with a suggestion, then (distinct from all three) a "real country, wrong scope"
error once a resolved name turns out to sit outside the tool's scope.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .client import get_client

# Score (0-100) above which a fuzzy match is confident enough to auto-resolve without asking.
# Below this, the same best match is surfaced only as a suggestion inside the error message.
AUTO_RESOLVE_THRESHOLD = 90


class CountryResolutionError(Exception):
    """Raised when a country argument can't be confidently resolved, or resolves to a real
    country outside the requested/tool's scope. The message is meant to be read directly by
    the calling agent, per SPEC.md §3.1 -- it should always suggest a next step."""


@dataclass(frozen=True)
class CountryLists:
    """The three scopes list_countries returns (SPEC.md §5), wrapped for resolution use."""

    featured: list[str]
    expanded: list[str]
    sovereign: list[str]

    def pool(self, scope: str) -> list[str]:
        try:
            return {"featured": self.featured, "expanded": self.expanded, "sovereign": self.sovereign}[scope]
        except KeyError:
            raise ValueError(f"Unknown scope '{scope}'") from None


def resolve_countries(names: list[str], lists: CountryLists, scope: str | None = None) -> list[str]:
    """resolve_country applied to each item of an explicit countries list. The wrapped API
    silently drops any country outside its scoped pool (e.g. a real, out-of-scope country
    filtered out before it ever reaches the response) -- resolving with `scope` set catches
    that case as an explicit case-4 error instead of a silently empty result for that
    country (SPEC.md §3.1, §3.2's "explicit list is never silently trimmed" rule)."""
    return [resolve_country(name, lists, scope=scope) for name in names]


async def fetch_country_lists() -> CountryLists:
    """Fetch the current country lists (list_countries' own data source) for tools that
    need to resolve a country argument. No caching -- one HTTP round trip per call, matching
    this server's stateless V1 design (SPEC.md §6.2)."""
    client = get_client()
    data = await client.get("/countries")
    return CountryLists(
        featured=data["featured"],
        expanded=data["expanded"],
        sovereign=data["sovereign"],
    )


def resolve_country(name: str, lists: CountryLists, scope: str | None = None) -> str:
    """Resolve a user-provided country name against the canonical lists.

    Always matches against the full sovereign list first (the widest pool), so a real but
    out-of-scope country reaches the case-4 error below instead of a plain "not found" --
    even for tools with no `scope` argument at all (they still pass one here, fixed to
    whichever pool they search; see get_country_profile/get_forecast in tools/countries.py
    and tools/forecasts.py).
    """
    universe = lists.sovereign or sorted({*lists.expanded, *lists.featured})

    if name in universe:
        resolved = name
    else:
        match = process.extractOne(name, universe, scorer=fuzz.WRatio)
        if match is None:
            raise CountryResolutionError(f"No match for '{name}' in the known country list.")
        candidate, score, _ = match
        if score < AUTO_RESOLVE_THRESHOLD:
            raise CountryResolutionError(f"No match for '{name}' — did you mean: {candidate}?")
        resolved = candidate

    if scope is not None:
        pool = lists.pool(scope)
        if resolved not in pool:
            raise CountryResolutionError(
                f"'{resolved}' exists but is outside '{scope}' scope — retry with a broader scope."
            )

    return resolved
