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


def test_progress_label_emissions_change_summary_interpolates_scope():
    assert progress_label("get_emissions_change_summary", {"scope": "expanded"}) == (
        "Counting emissions changes since 1990 (expanded)"
    )
    # scope defaults to "sovereign" server-side -- must not KeyError or render "None" when
    # omitted, same convention as every other optional-argument builder in this file.
    assert progress_label("get_emissions_change_summary", {}) == (
        "Counting emissions changes since 1990 (sovereign)"
    )


def test_progress_label_truncates_long_country_lists():
    # Reported live: a 209-country explicit list rendered as one unreadable wall of text in
    # both the streamed SSE progress bar and (via ui_selection.py's _title_for) the widget's
    # permanent title. join_countries caps at 5 names + "and N more".
    countries = [f"Country{i}" for i in range(1, 210)]
    label = progress_label("get_historical_emissions", {"countries": countries})
    assert label == (
        "Fetching historical emissions for Country1, Country2, Country3, Country4, "
        "Country5, and 204 more"
    )


def test_progress_label_country_join_boundary_not_truncated():
    # Exactly at the limit (5) must not append "and 0 more".
    countries = [f"Country{i}" for i in range(1, 6)]
    label = progress_label("get_historical_emissions", {"countries": countries})
    assert label == "Fetching historical emissions for Country1, Country2, Country3, Country4, Country5"
    assert "more" not in label


def test_progress_label_country_join_boundary_truncated_by_one():
    # One over the limit (6) must truncate and say "and 1 more" (singular count, still
    # correct even though the word itself doesn't change -- guards off-by-one).
    countries = [f"Country{i}" for i in range(1, 7)]
    label = progress_label("get_historical_emissions", {"countries": countries})
    assert label.endswith("and 1 more")


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
