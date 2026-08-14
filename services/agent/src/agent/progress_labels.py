"""Per-tool progress labels -- SPEC.md §5.

Builder functions rather than plain `.format(**args)` templates (a deliberate deviation from
SPEC.md §5's illustrative pseudocode): every tool here has at least one optional argument
(`countries`, `scope`, `country`), and a bare `.format(**args)` either raises `KeyError` on an
omitted key or renders a literal "None" when a key is present but `null` -- neither is
acceptable for user-visible progress text. One entry per tool in the real 13-tool catalog
confirmed in Step 1 (`services/mcp-server`'s `tools/*.py` + `server.py`), not the 3-entry
excerpt SPEC.md's own pseudocode showed.
"""

from collections.abc import Callable


def _join_countries(countries: list[str] | None) -> str:
    return ", ".join(countries) if countries else "the selected countries"


_BUILDERS: dict[str, Callable[[dict], str]] = {
    "list_countries": lambda args: "Loading country scopes",
    "get_country_profile": lambda args: f"Fetching {args.get('country', 'the country')}'s emissions profile",
    "get_historical_emissions": lambda args: f"Fetching historical emissions for {_join_countries(args.get('countries'))}",
    "get_gas_composition_by_decade": lambda args: f"Fetching gas composition by decade for {_join_countries(args.get('countries'))}",
    "get_forecast": lambda args: f"Running the ETS forecast for {args.get('country', 'the country')}",
    "get_forecast_summary": lambda args: f"Fetching forecast summary ({args.get('scope', 'featured')})",
    "get_forecast_comparison": lambda args: f"Comparing forecasts for {_join_countries(args.get('countries'))}",
    "get_model_comparison": lambda args: "Fetching model comparison",
    "get_top_emitters": lambda args: f"Ranking top {args.get('n', 10)} emitters for {args.get('year', 'the selected year')}",
    "get_scenario_projection": lambda args: (
        f"Fetching scenario projection for {args['country']}"
        if args.get("country")
        else f"Fetching global scenario projection ({args.get('scope', 'featured')})"
    ),
    "get_scenario_cumulative_impact": lambda args: "Fetching cumulative scenario impact",
    "compare_scenarios_across_countries": lambda args: f"Comparing scenarios across {_join_countries(args.get('countries'))}",
    "get_methodology_notes": lambda args: "Fetching methodology notes",
}


def progress_label(tool_name: str, args: dict) -> str:
    builder = _BUILDERS.get(tool_name)
    if builder is None:
        return f"Calling {tool_name}"
    return builder(args)
