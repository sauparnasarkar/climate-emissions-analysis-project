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
