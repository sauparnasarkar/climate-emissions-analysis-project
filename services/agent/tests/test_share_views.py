"""Release 24.4: the cumulative-share tool's views, titles, caveats, lint, model payload and follow-up links."""

import json
import re
from pathlib import Path

import pytest

from agent.area2_lint import check_response
from agent.caveats import SHARE_BASIS_OWID, SHARE_BASIS_OWID_COUNTRY_SUM, SHARE_BASIS_PRIMAP, SHARE_COUNTED_FROM, mandatory_notes
from agent.follow_ups import follow_up_links
from agent.payload_cap import cap_for_model
from agent.prompts import AGENT_SYSTEM_PROMPT, COMPOSE_RESPONSE_SYSTEM_PROMPT
from agent.state import ToolCallRecord, WidgetSpec
from agent.ui_selection import build_widget, select_share_view

TOOL = "get_country_cumulative_share"


def rec(result, args=None):
    return ToolCallRecord(tool_name=TOOL, args=args or {}, result=result, progress_label="x")


def country(name, expanded=True, annual=31.8):
    return {"country": name[:3].upper(), "name": name, "in_expanded_scope": expanded, "first_year": 1850, "last_year": 2024, "last_share_pct": 15.4, "last_annual_share_pct": annual,
            "share_trend": "rising", "rank": 2, "rank_of": 215}


def series_result(names=("China",), source="owid_co2", rest=True, expanded=True, annual=31.8):
    summary = {"mode": "series", "countries": [country(n, expanded, annual) for n in names], "trend_window": [1850, 2024]}
    if rest:
        summary["rest_of_world"] = {"year": 2024, "cumulative_gt": 1100.0, "share_pct": 60.0}
    return {"source": source, "gas_scope": "co2", "mode": "series", "summary": summary, "interpretation_note": "not warming",
            "series": [{"country": c["country"], "name": c["name"], "points": [], "in_expanded_scope": expanded} for c in summary["countries"]],
            "remainder_series": [{"year": 1850 + i, "world_cumulative_mt": 1.0, "world_annual_mt": 1.0} for i in range(175)] if rest else []}


def ranking_result():
    return {"source": "owid_co2", "mode": "ranking", "summary": {"mode": "ranking", "year": 2024, "n_rows": 15}, "rows": [], "interpretation_note": "n"}


# --- which view a question gets -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,names,expected",
    [
        ("How much CO₂ has China emitted in total?", ("China",), "cumulative_area"),
        ("Show cumulative emissions for the top emitters since 1970.", ("China", "United States"), "cumulative_area"),
        ("Is India's share of the world's cumulative CO₂ rising or falling?", ("India",), "share_vs_annual"),
        ("How do China and the US compare on cumulative share?", ("China", "United States"), "share_lines"),
        ("What share of historical emissions comes from China?", ("China",), "share_lines"),  # a share ask with no movement: lines
        ("Are the shares of China and India rising?", ("China", "India"), "share_lines"),  # movement over two countries: lines, not the single-country view
        ("What share of the total has China emitted so far?", ("China",), "share_lines"),  # "share" wins over an amount word
        ("tell me about China", ("China",), "share_lines"),  # nothing decisive: the existing default
    ],
)
def test_the_view_follows_the_question(query, names, expected):
    assert select_share_view(query, series_result(names)["summary"], "owid_co2") == expected


def test_the_stacked_area_needs_a_world_total_and_a_ranking_has_no_view():
    amount = "How much has China emitted in total?"
    assert select_share_view(amount, series_result(source="primap_hist", rest=False)["summary"], "primap_hist") == "share_lines"  # no World total to leave a rest of
    assert select_share_view(amount, series_result(rest=False)["summary"], "owid_co2") == "share_lines"
    assert select_share_view(amount, ranking_result()["summary"], "owid_co2") is None


def test_the_single_country_comparison_needs_an_annual_share_to_draw():
    q = "Is China's share rising?"
    assert select_share_view(q, series_result(annual=None)["summary"], "owid_co2") == "share_lines"


# --- the widget and its title ----------------------------------------------------------------------------------------------


def test_the_widget_carries_the_view_and_a_title_that_names_it_and_the_result_is_untouched():
    result = series_result(("China", "India"))
    before = json.dumps(result, sort_keys=True)
    area = build_widget(rec(result), "How much CO₂ have China and India emitted in total?")
    assert area.view == "cumulative_area" and area.title == "Cumulative CO₂ since records began, shown from 1850 – China, India"
    one = build_widget(rec(series_result(("India",))), "Is India's share rising or falling?")
    assert one.view == "share_vs_annual" and one.title == "Share of cumulative CO₂ against share of each year's emissions – India"
    lines = build_widget(rec(result), "compare China and India on share")
    assert lines.view == "share_lines" and lines.title == "Cumulative share of emissions – China, India"  # the existing title, unchanged
    assert json.dumps(result, sort_keys=True) == before and "view" not in result  # the view is per question: never written into the (cached) result
    for w in (area, one, lines):
        assert "--" not in w.title and "CO2" not in w.title and w.chart_kind == "line"


def test_a_ranking_widget_has_no_view():
    w = build_widget(rec(ranking_result()), "which countries have emitted the most since records began?")
    assert w.view is None and w.chart_kind == "bar"
    assert WidgetSpec(intent="chart", title="t", source_tool_call="s", props={}).view is None  # every other widget is unaffected


# --- caveats ------------------------------------------------------------------------------------------------------------------


def test_share_notes_are_one_note_with_the_basis_and_where_totals_count_from():
    notes = mandatory_notes([rec(series_result())])
    assert notes == ["not warming", f"{SHARE_BASIS_OWID} {SHARE_COUNTED_FROM}"]  # two banners, not four
    primap = mandatory_notes([rec(series_result(source="primap_hist", rest=False))])
    assert primap == ["not warming", f"{SHARE_BASIS_PRIMAP} {SHARE_COUNTED_FROM}"]
    ranking = mandatory_notes([rec(ranking_result())])
    assert SHARE_BASIS_OWID in ranking and not any(SHARE_COUNTED_FROM in n for n in ranking)  # a ranking has no chart start year
    assert "Rest of world" not in " ".join(notes)  # explained by the chart that draws it, not by every answer
    assert mandatory_notes([rec(series_result()), rec(series_result(("India",)))]).count(f"{SHARE_BASIS_OWID} {SHARE_COUNTED_FROM}") == 1  # de-duplicated
    for n in (SHARE_BASIS_OWID, SHARE_BASIS_PRIMAP, SHARE_COUNTED_FROM):
        assert "--" not in n and not re.search(r"\bCO2\b", n)


# --- lint ---------------------------------------------------------------------------------------------------------------------


def test_a_share_quoted_without_what_it_is_of_is_flagged_only_for_share_answers():
    bare = "China's cumulative share is 15.4%."
    assert any("without its basis" in v for v in check_response(bare, [], share_answer=True))
    assert check_response(bare, []) == []  # other answers are not judged on it
    for ok in ("China holds 15.4% of the world's cumulative CO₂.", "China's share of the World total is 15.4%.", "Its share of PRIMAP-hist's total is 15.9%.", "China emitted 285 Gt."):
        assert check_response(ok, [], share_answer=True) == [], ok
    # the scope notes always carry the basis, so they must not excuse a bare sentence
    assert check_response(bare, [SHARE_BASIS_OWID], share_answer=True)


# --- the model's copy ------------------------------------------------------------------------------------------------------------


def test_the_model_does_not_get_the_yearly_world_totals_and_the_widget_keeps_them():
    result = series_result()
    full = json.dumps(result)
    view, trimmed = cap_for_model(TOOL, result)
    assert trimmed and isinstance(view["remainder_series"], str) and "summary.rest_of_world" in view["remainder_series"]
    assert view["summary"] == result["summary"] and len(result["remainder_series"]) == 175 and json.dumps(result) == full  # the original is never mutated
    assert len(json.dumps(view)) < 0.5 * len(full)  # about 175 entries gone
    untouched, trimmed2 = cap_for_model(TOOL, series_result(source="primap_hist", rest=False))
    assert not trimmed2  # nothing to trim: PRIMAP has no remainder


# --- follow-up links -------------------------------------------------------------------------------------------------------------


def routes(result, query=""):
    return [(l.label, l.route) for l in follow_up_links([rec(result)], query)]


def test_one_expanded_country_links_to_historical_trends_and_its_profile_cumulative_section():
    out = routes(series_result(("China",)), "Is China's share rising?")
    assert out[0] == ("Open in Historical Trends", "/historical?view=share&countries=China")
    assert out[1] == ("Open China in Country Profile", "/country-profile?country=China#cumulative")
    assert len(out) == 3 and out[2][1] == "/climate-correlation#country-view"


def test_the_historical_link_opens_the_view_the_answer_drew():
    assert routes(series_result(("China", "United States")), "How much have they emitted in total?")[0][1] == "/historical?view=cumulative&countries=China&countries=United+States"
    assert routes(series_result(("China", "United States")), "compare their share")[0][1].startswith("/historical?view=share&")


def test_only_countries_the_page_can_show_are_carried():
    result = series_result(("China", "Zedland"))
    result["summary"]["countries"][1]["in_expanded_scope"] = False
    out = routes(result, "share")
    assert out[0][1] == "/historical?view=share&countries=China" and "Zedland" not in json.dumps(out)
    none = routes(series_result(("Zedland",), expanded=False), "share")
    assert none == [("Open in Climate Correlation", "/climate-correlation#country-view"), ("Open in Overview", "/overview#top-emitters")]  # nothing the page can show: the fixed links


def test_a_ranking_and_a_primap_share_keep_the_fixed_links():
    fixed = [("Open in Climate Correlation", "/climate-correlation#country-view"), ("Open in Overview", "/overview#top-emitters")]
    assert routes(ranking_result()) == fixed
    assert routes(series_result(source="primap_hist", rest=False)) == fixed  # the dashboard's views are OWID's


def test_every_share_link_points_at_a_real_page_anchor_and_view():
    """Read from the dashboard's own source (like test_area2_widgets): the pages, the `*_ANCHOR` constants and Historical Trends' `?view=` values."""
    src = Path(__file__).resolve().parents[3] / "climate-dashboard-react" / "src"
    if not src.exists():
        pytest.skip("climate-dashboard-react/src not present")
    pages = set(re.findall(r'path="(/[^"]*)"', (src / "App.tsx").read_text()))
    anchors = {m for f in src.rglob("*.ts*") for m in re.findall(r"_ANCHOR = '([a-z-]+)'", f.read_text())}
    views = set(re.findall(r"value: '([a-z]+)'", (src / "pages" / "HistoricalTrendsPage.tsx").read_text().split("const VIEW_ITEMS")[1].split("];")[0]))
    assert {"/historical", "/country-profile"} <= pages and "cumulative" in anchors and {"annual", "cumulative", "share"} <= views
    for query in ("How much has China emitted?", "Is China's share rising?"):
        for _, route in routes(series_result(("China",)), query):
            path, _, anchor = route.partition("#")
            base, _, qs = path.partition("?")
            assert base in pages and (not anchor or anchor in anchors), route
            if base == "/historical":
                assert re.search(r"view=([a-z]+)", qs).group(1) in views, route


# --- prompts -----------------------------------------------------------------------------------------------------------------------


def test_the_prompts_route_cumulative_questions_and_say_what_is_not_available():
    p = " ".join(AGENT_SYSTEM_PROMPT.split())
    for needle in ("share_trend", "trend_window", "rank_of", "not available", "methane, nitrous oxide", "the World total including international aviation and shipping", "no countries, no year", "start_year=1970 unless the user names another window"):
        assert needle in p, needle
    assert "say what a share is of" in " ".join(COMPOSE_RESPONSE_SYSTEM_PROMPT.split())


# --- units: the slip a live answer made ---------------------------------------------------------------------------------------------------------------------------------


def test_a_gt_figure_from_the_summary_written_with_mt_is_flagged():
    from agent.area2_lint import check_units

    summary = {"top": [{"name": "United States", "cumulative_gt": 434.9}], "world_cumulative_gt": 1849.1, "countries": [{"last_cumulative_gt": 285.1}]}
    bad = "The United States leads with 434.9 Mt CO₂ (23.52%) out of a World cumulative total of 1,849.1 Mt CO₂."
    out = check_units(bad, [summary])
    assert len(out) == 2 and any("434.9" in v for v in out) and any("1,849.1" in v for v in out)
    assert check_units("The United States leads with 434.9 MtCO₂.", [summary])
    assert check_units("The United States leads with 434.9 MtCO2.", [summary])
    assert check_units("The United States leads with 434.9 MtCO₂e.", [summary])
    assert check_units("The United States leads with 434.9 MtCO2e.", [summary])
    assert check_units("The United States leads with 434.9 MtCO₂eq.", [summary])
    assert check_units("The United States leads with 434.9 MtCO2eq.", [summary])
    assert check_units("The United States leads with 434.9 Gt CO₂ of a World total of 1,849.1 Gt.", [summary]) == []
    assert check_units("China emitted 285.1 GtCO₂ and 12,289 MtCO2eq in 2024.", [summary]) == []  # a real Mt CO₂e figure, and a Gt one with its Gt
    assert check_units("It emitted 7.5 Mt of methane.", [{"x_gt": 7.5}]) == []  # small values collide with ordinary Mt figures: ignored
    assert check_units("anything", []) == []


# --- "since YYYY": emissions in a period (Release 24.7, D7) -------------------------------------------------------------------------------------------------------------


def since_series(names=("China",), source="owid_co2", rest=True):
    r = series_result(names, source=source, rest=False)
    r["summary"]["since"] = {"year": 1990, "end_year": 2024, "period": "1990–2024", "rank_of": 215, "world_emitted_text": "1,064.8 GtCO₂",
                             "countries": [{"name": n, "emitted_text": "244.2 GtCO₂", "share_of_period_pct": 22.93, "rank": 2, "base_cumulative_mt": 40000.0} for n in names]}
    if rest:
        r["summary"]["since"]["rest_of_world"] = {"emitted_text": "820.6 GtCO₂", "share_pct": 77.07}
    return r


def since_ranking():
    return {"source": "owid_co2", "mode": "ranking", "rows": [], "since_rows": [{"rank": 1, "name": "United States"}], "since_year": 1970, "interpretation_note": "n",
            "summary": {"mode": "ranking", "year": 2024, "n_rows": 15, "since": {"year": 1970, "end_year": 2024, "period": "1970–2024"}}}


def test_a_since_series_is_an_amount_question_drawn_as_the_rebased_area_with_a_title_naming_the_period():
    r = since_series()
    assert select_share_view("What is China's cumulative CO₂ since 1990?", r["summary"], "owid_co2") == "cumulative_area"
    w = build_widget(rec(r), "What is China's cumulative CO₂ since 1990?")
    assert w.view == "cumulative_area" and w.title == "Emitted 1990–2024, GtCO₂ – China"
    assert "since records began" not in w.title  # the period figures are not the total from the first record


def test_a_since_series_is_never_drawn_as_a_lifetime_share_chart_whatever_the_wording():
    """The share views plot the cumulative share since records began: a different quantity from the since answer's period figures, so they would contradict it."""
    for q in ("How much since 1990?", "Is China's share rising since 1990?", "compare their share since 1990", "What share has China emitted since 1990?", "tell me about China since 1990"):
        assert select_share_view(q, since_series()["summary"], "owid_co2") == "cumulative_area", q  # OWID: the rebased stacked area
        assert select_share_view(q, since_series(source="primap_hist", rest=False)["summary"], "primap_hist") == "emitted_lines", q  # PRIMAP-hist: no World total, so lines of emissions
    # and the same wording WITHOUT a since keeps the lifetime views (they are right for a question about the total since records began)
    assert select_share_view("Is China's share rising?", series_result()["summary"], "owid_co2") == "share_vs_annual"
    assert select_share_view("compare China and India on share", series_result(("China", "India"))["summary"], "owid_co2") == "share_lines"


def test_the_primap_since_widget_is_emitted_lines_with_a_period_title_in_the_right_unit():
    r = since_series(source="primap_hist", rest=False)
    w = build_widget(rec(r), "How much since 1990?")
    assert w.view == "emitted_lines" and w.title == "Emitted 1990–2024, GtCO₂ – China"
    r["gas_scope"] = "total_ghg"
    assert build_widget(rec(r), "How much since 1990?").title == "Emitted 1990–2024, GtCO₂e – China"


def test_a_since_ranking_has_no_view_and_a_title_naming_the_period():
    w = build_widget(rec(since_ranking()), "Which countries have emitted the most since 1970?")
    assert w.view is None and w.chart_kind == "bar" and w.title == "Top 15 emitters, 1970–2024, GtCO₂"


def test_a_since_answer_states_what_the_period_figures_are_not_where_totals_count_from():
    notes = mandatory_notes([rec(since_series())])
    assert len(notes) == 2 and "emissions of those years" in notes[1] and "cumulative total at the end year minus its total the year before 1990" in notes[1]
    assert "World's emissions in the period" in notes[1] and SHARE_COUNTED_FROM not in notes[1]
    assert "source's own total in the period" in mandatory_notes([rec(since_series(source="primap_hist", rest=False))])[1]
    ranking = mandatory_notes([rec(since_ranking())])
    assert len(ranking) == 2 and "emissions of those years" in ranking[1]


def test_a_since_answer_links_to_the_pages_counting_from_that_year_so_they_show_the_answers_numbers():
    out = dict(routes(since_series(), "since 1990"))
    assert out["Open in Historical Trends"] == "/historical?view=cumulative&from=1990&countries=China"
    assert out["Open China in Country Profile"] == "/country-profile?country=China&from=1990#cumulative"
    # a plain total keeps the pages' default (since records began): no parameter
    plain = dict(routes(series_result(("China",)), "How much has China emitted?"))
    assert plain["Open in Historical Trends"] == "/historical?view=cumulative&countries=China" and "from=" not in plain["Open China in Country Profile"]
    # a share question about a since answer opens the share view from that year
    assert dict(routes(since_series(), "Is China's share rising since 1990?"))["Open in Historical Trends"] == "/historical?view=share&from=1990&countries=China"


def test_a_since_period_that_ends_before_the_latest_year_keeps_the_fixed_links_because_a_page_cannot_end_there():
    fixed = ["/climate-correlation#country-view", "/overview#top-emitters"]
    bounded = since_series()
    bounded["summary"]["since"].update(end_year=2010, latest_year=2024, period="1990–2010")
    assert [r for _, r in routes(bounded, "since 1990 until 2010")] == fixed  # the page would run to 2024 and show other totals
    open_ended = since_series()
    open_ended["summary"]["since"].update(end_year=2024, latest_year=2024)
    assert dict(routes(open_ended, "since 1990"))["Open in Historical Trends"] == "/historical?view=cumulative&from=1990&countries=China"
    unknown = since_series()
    unknown["summary"]["since"].pop("end_year", None)
    assert "Open in Historical Trends" in dict(routes(unknown, "since 1990"))  # no latest year reported: cannot tell, links as before


def test_a_since_year_before_the_pages_window_keeps_the_fixed_links_instead_of_a_link_that_opens_other_numbers():
    fixed = ["/climate-correlation#country-view", "/overview#top-emitters"]
    old = since_series()
    old["summary"]["since"].update(year=1950, period="1950–2024")
    assert [r for _, r in routes(old, "since 1950")] == fixed  # the tool accepts 1851+, the pages' choice starts in 1970
    edge = since_series()
    edge["summary"]["since"].update(year=1970, period="1970–2024")
    assert dict(routes(edge, "since 1970"))["Open in Historical Trends"] == "/historical?view=cumulative&from=1970&countries=China"  # 1970 itself is fine


def test_a_since_ranking_and_a_primap_since_keep_the_fixed_links():
    fixed = ["/climate-correlation#country-view", "/overview#top-emitters"]
    assert [r for _, r in routes(since_ranking(), "which countries emitted the most since 1970")] == fixed
    assert [r for _, r in routes(since_series(source="primap_hist", rest=False), "since 1990")] == fixed  # the dashboard's views are OWID's


def test_the_dashboard_really_reads_the_from_parameter_on_both_pages():
    """Pinned against the dashboard's source like the `?view=` values: a rename there must fail here, not leave a link that opens the wrong numbers."""
    src = Path(__file__).resolve().parents[3] / "climate-dashboard-react" / "src"
    if not src.exists():
        pytest.skip("climate-dashboard-react/src not present")
    hook = (src / "hooks" / "useCountingFrom.ts").read_text()
    assert "useUrlChoice('from'" in hook and "COUNTING_FROM_MIN_YEAR = 1970" in hook
    from agent.follow_ups import COUNTING_FROM_MIN_YEAR

    assert COUNTING_FROM_MIN_YEAR == int(re.search(r"COUNTING_FROM_MIN_YEAR = (\d+)", hook).group(1))  # the agent's copy cannot drift from the dashboard's
    assert "useCountingFrom()" in (src / "pages" / "HistoricalTrendsPage.tsx").read_text() and "useCountingFrom()" in (src / "pages" / "CountryProfilePage.tsx").read_text()
    for _, route in routes(since_series(), "since 1990"):
        qs = route.partition("#")[0].partition("?")[2]
        if "from=" in qs:
            assert 1970 <= int(re.search(r"from=(\d+)", qs).group(1)) <= 2100  # a year the hook accepts


def test_the_prompt_sends_since_questions_to_since_year_and_no_longer_says_they_are_unavailable():
    p = " ".join(AGENT_SYSTEM_PROMPT.split())
    assert "pass since_year (never start_year, and never both)" in p and "quote `summary.since`" in p
    assert "a cumulative since a chosen year" not in p and "(methane, nitrous oxide) is not available" in p  # only the other-gas limit remains


def test_titles_say_gtco2e_for_total_greenhouse_gases():
    r = since_series(source="primap_hist", rest=False)
    r["gas_scope"] = "total_ghg"
    assert build_widget(rec(r), "What is China's cumulative CO₂ since 1990?").title == "Emitted 1990–2024, GtCO₂e – China"  # PRIMAP has no area view: emitted_lines, titled with the period
    rk = since_ranking()
    rk["gas_scope"] = "total_ghg"
    assert build_widget(rec(rk), "since 1970").title == "Top 15 emitters, 1970–2024, GtCO₂e"
    assert build_widget(rec(since_ranking()), "since 1970").title == "Top 15 emitters, 1970–2024, GtCO₂"


def test_the_share_against_annual_title_names_the_gas_for_total_greenhouse_gases():
    r = series_result(("India",), source="primap_hist", rest=False)
    r["gas_scope"] = "total_ghg"
    assert build_widget(rec(r), "Is India's share rising?").title == "Share of cumulative greenhouse gases (CO₂e) against share of each year's emissions – India"
    assert build_widget(rec(series_result(("India",))), "Is India's share rising?").title == "Share of cumulative CO₂ against share of each year's emissions – India"


def test_the_share_notes_follow_the_data_basis_an_older_owid_output_is_of_the_country_sum_not_the_world():
    # the current pipeline: a World denominator
    cur = since_series()
    cur["summary"]["since"]["basis"] = "share of the World's emissions in the period (international aviation and shipping included)"
    cur["denominator"] = {"kind": "world"}
    assert "World's emissions in the period" in mandatory_notes([rec(cur)])[1] and SHARE_BASIS_OWID in mandatory_notes([rec(cur)])[1]
    # an older OWID output (no World remainder) is still served: shares of the country sum, which the summary's own basis says
    old = since_series(rest=False)
    old["summary"]["since"]["basis"] = "share of the source's own total emissions in the period"
    old["denominator"] = {"kind": "country_sum"}
    note = mandatory_notes([rec(old)])[1]
    assert SHARE_BASIS_OWID_COUNTRY_SUM in note and "source's own total in the period" in note
    assert SHARE_BASIS_OWID not in note and "World's emissions" not in note  # the older output must not be told it is a share of the World
    # without a period: the response's denominator kind decides
    legacy_total = series_result()
    legacy_total["denominator"] = {"kind": "country_sum"}
    assert SHARE_BASIS_OWID_COUNTRY_SUM in mandatory_notes([rec(legacy_total)])[1]
    legacy_total["denominator"] = {}  # an older file: a denominator object without a kind is the country sum too
    assert SHARE_BASIS_OWID_COUNTRY_SUM in mandatory_notes([rec(legacy_total)])[1]
    # PRIMAP-hist is never a World total, whatever the basis string says
    assert SHARE_BASIS_PRIMAP in mandatory_notes([rec(since_series(source="primap_hist", rest=False))])[1]
