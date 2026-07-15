"""Mirrors the constants block in app.py — single source of truth for the API."""

COUNTRIES = [
    "China", "United States", "India", "Russia", "Japan",
    "Germany", "Brazil", "United Kingdom", "South Africa", "Australia",
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
