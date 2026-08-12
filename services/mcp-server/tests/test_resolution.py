import pytest

from mcp_server.resolution import CountryLists, CountryResolutionError, resolve_country

LISTS = CountryLists(
    featured=["China", "United States"],
    expanded=["China", "United States", "Germany"],
    sovereign=["China", "United States", "Germany", "Congo", "Democratic Republic of Congo"],
)


def test_exact_match_resolves_unchanged():
    assert resolve_country("China", LISTS) == "China"


def test_close_typo_auto_resolves():
    assert resolve_country("Chinaa", LISTS) == "China"


def test_low_confidence_match_raises_with_suggestion():
    with pytest.raises(CountryResolutionError, match="did you mean"):
        resolve_country("Freedonia", LISTS)


def test_known_country_outside_requested_scope_raises_case_four():
    # Germany is a real, resolvable country, but not in "featured" scope.
    with pytest.raises(CountryResolutionError, match="outside 'featured' scope"):
        resolve_country("Germany", LISTS, scope="featured")


def test_within_scope_passes():
    assert resolve_country("Germany", LISTS, scope="expanded") == "Germany"


def test_unknown_scope_raises_value_error():
    with pytest.raises(ValueError):
        resolve_country("China", LISTS, scope="bogus")
