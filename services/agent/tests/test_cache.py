from agent.cache import cache_key


def test_cache_key_deterministic_for_same_args():
    assert cache_key("get_historical_emissions", {"countries": ["China", "India"], "scope": "featured"}) == cache_key(
        "get_historical_emissions", {"countries": ["China", "India"], "scope": "featured"}
    )


def test_cache_key_ignores_list_arg_order():
    key_a = cache_key("get_historical_emissions", {"countries": ["China", "India"]})
    key_b = cache_key("get_historical_emissions", {"countries": ["India", "China"]})
    assert key_a == key_b


def test_cache_key_differs_for_different_tool_or_args():
    base = cache_key("get_historical_emissions", {"countries": ["China"]})
    assert base != cache_key("get_forecast", {"countries": ["China"]})
    assert base != cache_key("get_historical_emissions", {"countries": ["India"]})
