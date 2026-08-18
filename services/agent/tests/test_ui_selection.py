from agent.state import ToolCallRecord
from agent.ui_selection import (
    build_country_profile_widgets,
    build_widget,
    is_error_result,
    select_top_emitters_chart_kind,
)

# SPEC.md §4's own starter prompts -- the heuristic must classify these correctly, since they're
# the concrete cases the spec was written against.
STARTER_PROMPT_RANKED = "What are the top 10 forecasted emitters in 2040?"
STARTER_PROMPT_COMPARATIVE = (
    "Considering the top 10 emitters now and the forecasted ones in 2040, "
    "show the comparative trend for the countries."
)


def test_select_top_emitters_chart_kind_defaults_to_bar():
    assert select_top_emitters_chart_kind("who are the top 10 emitters?") == "bar"


def test_select_top_emitters_chart_kind_ranked_forecast_alone_stays_bar():
    # A single forecasted metric, ranked -- still one metric, not "now vs. forecast".
    assert select_top_emitters_chart_kind(STARTER_PROMPT_RANKED) == "bar"


def test_select_top_emitters_chart_kind_geographic_is_choropleth():
    assert select_top_emitters_chart_kind("where are emissions highest?") == "choropleth"


def test_select_top_emitters_chart_kind_current_and_forecast_still_bar():
    # Step 4 correction (SPEC.md "Corrections applied" #17): get_top_emitters carries one metric,
    # so a "now vs. forecast" query no longer gets a treemap -- there's no second metric to color
    # tiles by. Falls back to bar like any other non-geographic query.
    assert select_top_emitters_chart_kind(STARTER_PROMPT_COMPARATIVE) == "bar"


def test_is_error_result():
    assert is_error_result({"error": "boom"}) is True
    assert is_error_result({"data": [1, 2, 3]}) is False
    assert is_error_result(["a", "list"]) is False
    assert is_error_result(None) is False


def test_build_widget_skips_error_and_list_countries():
    error_record = ToolCallRecord(
        tool_name="get_historical_emissions", args={}, result={"error": "boom"}, progress_label="x"
    )
    assert build_widget(error_record, "any query") is None

    list_countries_record = ToolCallRecord(tool_name="list_countries", args={}, result={"featured": []}, progress_label="x")
    assert build_widget(list_countries_record, "any query") is None


def test_build_widget_maps_known_tool_to_fixed_intent():
    record = ToolCallRecord(
        tool_name="get_historical_emissions",
        args={"countries": ["China"]},
        result={"series": []},
        progress_label="Fetching historical emissions for China",
    )
    widget = build_widget(record, "how has China's trend changed?")
    assert widget is not None
    assert widget.intent == "chart"
    assert widget.chart_kind == "line"
    assert widget.props == {"series": []}


_PROGRESS_VERBS = ("Fetching", "Running", "Comparing", "Ranking", "Loading", "Calling")


def test_build_widget_title_is_not_progress_phrased():
    # Reported live: a widget's title reused progress_labels.py's verb-phrased text verbatim
    # ("Fetching historical emissions for Afghanistan, Albania, ...") and, since titles are
    # rendered as a permanent card/chart header (not tied to loading state), stayed visible
    # forever, reading as leftover progress text intermingled with the finished response.
    # Every tool that gets a widget must have a noun-phrase title instead.
    cases = [
        ("get_historical_emissions", {"countries": ["China", "India"]}),
        ("get_gas_composition_by_decade", {"countries": ["China"]}),
        ("get_forecast", {"country": "China"}),
        ("get_forecast_summary", {"scope": "featured"}),
        ("get_forecast_comparison", {"countries": ["China", "India"]}),
        ("get_model_comparison", {}),
        ("get_scenario_projection", {"country": "China"}),
        ("get_scenario_projection", {"scope": "featured"}),
        ("get_scenario_cumulative_impact", {"sort_by": "Moderate"}),
        ("compare_scenarios_across_countries", {"countries": ["China", "India"]}),
        ("get_methodology_notes", {}),
        ("get_top_emitters", {"n": 10, "year": 2020}),
        ("get_country_profile", {"country": "China"}),
    ]
    for tool_name, args in cases:
        record = ToolCallRecord(tool_name=tool_name, args=args, result={"data": []}, progress_label="x")
        widget = build_widget(record, "any query")
        assert widget is not None
        assert not widget.title.startswith(_PROGRESS_VERBS), f"{tool_name} title still progress-phrased: {widget.title!r}"


def test_build_widget_historical_emissions_title_uses_truncated_country_join():
    record = ToolCallRecord(
        tool_name="get_historical_emissions",
        args={"countries": [f"Country{i}" for i in range(1, 210)]},
        result={"series": []},
        progress_label="x",
    )
    widget = build_widget(record, "how many countries increased or decreased?")
    assert widget is not None
    assert widget.title == (
        "Historical emissions -- Country1, Country2, Country3, Country4, Country5, and 204 more"
    )


def test_build_widget_historical_emissions_title_falls_back_to_scope_when_countries_omitted():
    # Copilot review, PR #165: when `countries` is omitted (a valid call shape -- the tool
    # resolves the whole `scope` pool itself), the title must say which scope was used, not
    # the generic "the selected countries" join_countries(None) alone would produce.
    record = ToolCallRecord(
        tool_name="get_historical_emissions",
        args={"scope": "sovereign"},
        result={"series": []},
        progress_label="x",
    )
    widget = build_widget(record, "how many countries increased or decreased?")
    assert widget is not None
    assert widget.title == "Historical emissions -- sovereign scope"
    assert "selected countries" not in widget.title


def test_build_widget_emissions_change_summary_title_carries_real_counts():
    # The one widget whose title is built from record.result, not record.args -- the only
    # way the real increased/decreased counts reach compose_response_node, which never sees
    # props for any widget (SPEC.md "Corrections applied" #33).
    record = ToolCallRecord(
        tool_name="get_emissions_change_summary",
        args={"scope": "sovereign", "top_n": 10},
        result={
            "scope": "sovereign",
            "baseline_year": 1990,
            "countries_with_data": 209,
            "increased_count": 154,
            "decreased_count": 55,
            "top_increases": [],
            "top_decreases": [],
        },
        progress_label="x",
    )
    widget = build_widget(record, "how many countries increased or decreased?")
    assert widget is not None
    assert widget.intent == "grid"
    assert widget.title == "Emissions change since 1990: 154 up, 55 down of 209 countries (sovereign)"
    assert widget.props["increased_count"] == 154


def test_build_widget_forecast_comparison_is_chart_not_text():
    # get_forecast_comparison is the multi-country equivalent of get_forecast and must resolve to
    # chart/line, not fall through to the ("text", None) default.
    record = ToolCallRecord(
        tool_name="get_forecast_comparison",
        args={"countries": ["China", "India"]},
        result={"series": []},
        progress_label="Comparing forecasts for China, India",
    )
    widget = build_widget(record, "compare forecasts for China and India")
    assert widget is not None
    assert widget.intent == "chart"
    assert widget.chart_kind == "line"


def test_build_country_profile_widgets_card_only():
    record = ToolCallRecord(
        tool_name="get_country_profile", args={"country": "China"}, result={"co2": []}, progress_label="x"
    )
    widgets = build_country_profile_widgets(record, include_chart=False)
    assert len(widgets) == 1
    assert widgets[0].intent == "card"


def test_build_country_profile_widgets_card_and_chart():
    record = ToolCallRecord(
        tool_name="get_country_profile", args={"country": "China"}, result={"co2": []}, progress_label="x"
    )
    widgets = build_country_profile_widgets(record, include_chart=True)
    assert [w.intent for w in widgets] == ["card", "chart"]
    assert widgets[0].source_tool_call == widgets[1].source_tool_call


def test_build_country_profile_widgets_error_returns_empty():
    record = ToolCallRecord(
        tool_name="get_country_profile", args={"country": "Atlantis"}, result={"error": "no match"}, progress_label="x"
    )
    assert build_country_profile_widgets(record, include_chart=True) == []
