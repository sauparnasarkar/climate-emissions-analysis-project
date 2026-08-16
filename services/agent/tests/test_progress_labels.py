from agent.progress_labels import progress_label


def test_progress_label_with_countries():
    assert progress_label("get_historical_emissions", {"countries": ["China", "India"]}) == (
        "Fetching historical emissions for China, India"
    )


def test_progress_label_handles_omitted_countries():
    # countries is optional (defaults to None server-side) -- must not KeyError or render "None".
    label = progress_label("get_historical_emissions", {})
    assert "None" not in label
    assert "the selected countries" in label


def test_progress_label_scenario_projection_country_vs_global():
    assert progress_label("get_scenario_projection", {"country": "China"}) == "Fetching scenario projection for China"
    assert "global" in progress_label("get_scenario_projection", {"scope": "featured"})


def test_progress_label_unknown_tool_falls_back():
    assert progress_label("some_future_tool", {}) == "Calling some_future_tool"


def test_progress_label_scenario_cumulative_interpolates_sort_by():
    # Reported live: three get_scenario_cumulative_impact calls with different sort_by all
    # rendered the identical title "Fetching cumulative scenario impact", making three
    # (already largely redundant, see scenarios.py's docstring fix) grids indistinguishable.
    # Every sibling builder in this dict interpolates its own distinguishing argument; this one
    # didn't.
    assert progress_label("get_scenario_cumulative_impact", {"sort_by": "Moderate"}) == (
        "Fetching cumulative scenario impact (sorted by Moderate)"
    )
    # sort_by defaults to "BAU" server-side (scenarios.py's own get_scenario_cumulative_impact
    # signature) -- must not KeyError or render "None" when omitted, same convention as every
    # other optional-argument builder in this file.
    assert progress_label("get_scenario_cumulative_impact", {}) == (
        "Fetching cumulative scenario impact (sorted by BAU)"
    )
