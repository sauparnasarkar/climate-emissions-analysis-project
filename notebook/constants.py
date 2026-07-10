# ── Project constants — shared across all week notebooks ──────────────────
#
# Imported by week1_eda.ipynb through week5_scenarios.ipynb via
# `from constants import *`. Single source of truth: do not redefine
# COUNTRIES, NON_SOVEREIGN, FEATURES, TARGET, etc. inside any notebook.

OWID_URL = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"

COUNTRIES = [
    "China", "United States", "India", "Russia", "Japan",
    "Germany", "Brazil", "United Kingdom", "South Africa", "Australia",
]
# Note: OWID uses "United States" (not "USA") and "United Kingdom" (not "UK")

TRAIN_CUTOFF = 2018   # train: 1990–2018  |  test: 2019–2023
FORECAST_END = 2043   # 20 years beyond 2023

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
    "CO₂":                "co2",
    "Methane (CH₄)":      "methane",
    "Nitrous Oxide (N₂O)": "nitrous_oxide",
}

FEATURES = [
    'years_since_1990', 'co2_5yr_rolling_mean',
    'co2_lag1', 'co2_lag2', 'co2_lag3', 'co2_yoy_pct_change',
]
TARGET = 'co2'
