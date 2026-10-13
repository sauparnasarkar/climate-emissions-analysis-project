"""Mirrors the constants block in app.py — single source of truth for the API."""

FEATURED_COUNTRIES = [
    "China", "United States", "India", "Russia", "Japan",
    "Germany", "Brazil", "United Kingdom", "South Africa", "Australia",
]
COUNTRIES = FEATURED_COUNTRIES  # back-compat alias — nothing new should reference this name

MAX_SELECTED_COUNTRIES = 10

# The animated choropleth's year range (SPEC.md §5.17). Kept separate from
# PCT_CHANGE_BASELINE_YEAR below even though both are 1990 today -- one is the animation's
# range start, the other is the "% change since" baseline year; they're conceptually distinct
# and shouldn't be silently coupled by sharing a constant.
WORLD_MAP_YEAR_START = 1990
WORLD_MAP_YEAR_END = 2024
# The earliest `start_year` /overview/world-map-series accepts (the loader reads the OWID file once and slices it per request).
WORLD_MAP_YEAR_EARLIEST = 1900

# First year of the cumulative-CO2 views (SPEC.md §5.28). A display window only: OWID's `cumulative_co2` counts from
# each country's first record, so rows from this year on still carry the true running total.
CUMULATIVE_YEAR_START = 1970
# One year earlier, kept in the cumulative loader as the BASE of "counting from a year" (`from_year`): emissions from year X are the cumulative total at the end
# minus the total at X-1, so counting from 1970 needs 1969. Never shown: the default views start at CUMULATIVE_YEAR_START.
CUMULATIVE_BASE_YEAR = CUMULATIVE_YEAR_START - 1

# The year every tier's "% change since 1990" figure is computed against (overview.py's
# _tier_metrics) -- previously a bare literal.
PCT_CHANGE_BASELINE_YEAR = 1990

# How many top-emitting sovereign countries the Overview headline sentence covers (SPEC.md
# §5.18.5) -- a fixed set independent of the country picker's `selected`/`countries`, unlike
# MAX_SELECTED_COUNTRIES above which caps the *picker's* own selection.
TOP_N_HEADLINE = 10

# Mirrors notebook/constants.py's NON_SOVEREIGN verbatim — kept in sync by hand, same
# three-way-mirror convention as FEATURED_COUNTRIES across notebook/, api/, and app.py.
NON_SOVEREIGN = [
    # Continental / regional aggregates (OWID)
    "World", "Asia", "Europe", "Africa", "North America", "South America",
    "Oceania",
    # Continental / regional aggregates (GCP variants)
    "Africa (GCP)", "Asia (GCP)", "Europe (GCP)",
    "North America (GCP)", "South America (GCP)", "Oceania (GCP)",
    "Central America (GCP)", "Middle East (GCP)",
    # Sub-regional exclusion variants
    "Asia (excl. China and India)",
    "Europe (excl. EU-27)", "Europe (excl. EU-28)",
    "North America (excl. USA)",
    # European Union aggregates
    "European Union (27)", "European Union (28)",
    # Income / development groupings
    "High-income countries", "Low-income countries",
    "Upper-middle-income countries", "Lower-middle-income countries",
    "Least developed countries (Jones et al.)",
    # OECD / Non-OECD groupings
    "OECD (GCP)", "OECD (Jones et al.)", "Non-OECD (GCP)",
    # International transport (components — "International transport" does not exist in OWID)
    "International aviation", "International shipping",
    # Special / historical entries
    "Kuwaiti Oil Fires", "Kuwaiti Oil Fires (GCP)",
    "Ryukyu Islands (GCP)",
]

GAS_COLUMNS = {
    "co2": "CO₂",
    "methane": "Methane (CH₄)",
    "nitrous_oxide": "Nitrous Oxide (N₂O)",
}

SCENARIO_COLORS = {
    "BAU": "blue",
    "Moderate": "orange",
    "Aggressive": "green",
}
