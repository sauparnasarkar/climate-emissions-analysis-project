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


def test_select_top_emitters_chart_kind_current_and_forecast_is_treemap():
    assert select_top_emitters_chart_kind(STARTER_PROMPT_COMPARATIVE) == "treemap"


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
