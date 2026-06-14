"""
GHG Trend Analysis & Forecasting — Streamlit Dashboard
IDEAS TIH Summer Internship 2026

Week 6 Stretch Goal: Fill in the # TODO sections for each page.

Prerequisites:
  - data/ghg_features.csv          (generated in Week 2)
  - data/scenario_projections.csv  (generated in Week 5, optional)

Run with:
    streamlit run app.py
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px

# ── Constants ─────────────────────────────────────────────────────────────────
COUNTRIES = [
    "China", "United States", "India", "Russia", "Japan",
    "Germany", "Brazil", "United Kingdom", "South Africa", "Australia",
]

GAS_COLUMNS = {
    "CO₂":                 "co2",
    "Methane (CH₄)":       "methane",
    "Nitrous Oxide (N₂O)": "nitrous_oxide",
}

SCENARIO_COLORS = {
    "BAU":        "blue",
    "Moderate":   "orange",
    "Aggressive": "green",
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GHG Trend Analysis",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Data loaders ──────────────────────────────────────────────────────────────
@st.cache_data
def load_features():
    """Load the feature-engineered dataset produced in Week 2."""
    path = "data/ghg_features.csv"
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


@st.cache_data
def load_scenarios():
    """Load scenario projections produced in Week 5 (optional)."""
    path = "data/scenario_projections.csv"
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🌍 GHG Trend Analysis")
st.sidebar.markdown("**IDEAS TIH Summer Internship 2026**")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Historical Trends", "Country Profile", "Forecasts", "Scenario Comparison", "About"],
)

st.sidebar.divider()
st.sidebar.caption("Mentor: Sauparna Sarkar")

# ── Load data ─────────────────────────────────────────────────────────────────
df           = load_features()
df_scenarios = load_scenarios()

# ─────────────────────────────────────────────────────────────────────────────
# OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
if page == "Overview":
    st.title("Climate Change Trend Analysis and Forecasting")
    st.markdown(
        "An end-to-end analysis of greenhouse gas emissions for 10 major countries "
        "using the OWID CO₂ dataset, regression models, and ETS(A,Ad,N) forecasting.\n\n"
        "*IDEAS TIH Summer Internship 2026*"
    )
    st.divider()

    if df is not None:
        col1, col2, col3 = st.columns(3)

        latest_year = int(df["year"].max())

        with col1:
            # TODO: Compute sum of co2 across COUNTRIES for the latest_year
            # latest_co2 = df[(df["year"] == latest_year) & (df["country"].isin(COUNTRIES))]["co2"].sum()
            # st.metric(f"Global CO₂ ({latest_year}, 10 countries)", f"{latest_co2:,.0f} MtCO₂")
            st.metric(
                label=f"Global CO₂ ({latest_year}, 10 countries)",
                value="— MtCO₂",
                help="Sum of CO₂ across the 10 focus countries for the latest year. Fill in the TODO above."
            )

        with col2:
            # TODO: Compute % change from 1990 to latest_year for the same 10 countries
            # co2_1990   = df[(df["year"] == 1990) & (df["country"].isin(COUNTRIES))]["co2"].sum()
            # pct_change = (latest_co2 - co2_1990) / co2_1990 * 100
            # st.metric("% Change since 1990", f"{pct_change:+.1f}%")
            st.metric(label="% Change since 1990", value="—%")

        with col3:
            st.metric(label="Countries Analysed", value=len(COUNTRIES))

        st.divider()
        st.subheader("Focus Countries")
        st.markdown("  |  ".join(COUNTRIES))

    else:
        st.warning(
            "⚠️ `data/ghg_features.csv` not found.\n\n"
            "Complete **Week 2** of the notebook to generate this file, then restart the app."
        )

# ─────────────────────────────────────────────────────────────────────────────
# HISTORICAL TRENDS
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Historical Trends":
    st.title("Historical Emissions Trends")

    if df is None:
        st.warning("Complete Week 2 to enable this page.")
    else:
        selected_countries = st.multiselect(
            "Select countries",
            options=COUNTRIES,
            default=COUNTRIES[:5],
        )

        gas_label = st.selectbox("Emissions metric", options=list(GAS_COLUMNS.keys()))
        gas_col   = GAS_COLUMNS[gas_label]

        st.subheader(f"{gas_label} Emissions Over Time")
        if selected_countries:
            # TODO: Filter df to selected_countries and plot a Plotly line chart
            # df_plot = df[df["country"].isin(selected_countries)]
            # fig = px.line(
            #     df_plot, x="year", y=gas_col, color="country",
            #     title=f"{gas_label} Emissions by Country",
            #     labels={"year": "Year", gas_col: f"{gas_label} (MtCO₂e)"},
            # )
            # fig.update_layout(legend_title="Country")
            # st.plotly_chart(fig, use_container_width=True)
            st.info("📊 **TODO:** Add Plotly line chart here (see commented code above).")
        else:
            st.warning("Select at least one country.")

        st.divider()
        st.subheader("GHG Share by Gas Type per Decade")
        # TODO: Add decade column, group by decade, compute % share of each gas, stacked bar
        # decade_group = df.copy()
        # decade_group["decade"] = (decade_group["year"] // 10) * 10
        # gas_cols = list(GAS_COLUMNS.values())
        # agg = decade_group.groupby("decade")[gas_cols].sum()
        # agg_pct = agg.div(agg.sum(axis=1), axis=0) * 100
        # agg_pct_long = agg_pct.reset_index().melt(id_vars="decade", var_name="gas", value_name="share_%")
        # fig2 = px.bar(agg_pct_long, x="decade", y="share_%", color="gas", barmode="stack",
        #               title="GHG Composition by Decade (% share)",
        #               labels={"decade": "Decade", "share_%": "Share (%)", "gas": "Gas"})
        # st.plotly_chart(fig2, use_container_width=True)
        st.info("📊 **TODO:** Add stacked bar chart here (see commented code above).")

# ─────────────────────────────────────────────────────────────────────────────
# COUNTRY PROFILE
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Country Profile":
    st.title("Country Profile")

    if df is None:
        st.warning("Complete Week 2 to enable this page.")
    else:
        country    = st.selectbox("Select a country", options=COUNTRIES)
        df_country = df[df["country"] == country].sort_values("year")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"CO₂ Emissions")
            # TODO: px.line(df_country, x="year", y="co2", title=f"CO₂ Emissions — {country}",
            #               labels={"year": "Year", "co2": "CO₂ (MtCO₂)"})
            st.info("📊 **TODO:** CO₂ emissions trend chart.")

        with col2:
            st.subheader("CO₂ per Capita")
            # TODO: px.line(df_country, x="year", y="co2_per_capita", ...)
            st.info("📊 **TODO:** CO₂ per capita trend chart.")

        st.subheader("Year-on-Year Change (%)")
        # TODO: px.bar(df_country, x="year", y="co2_yoy_pct_change", ...)
        # Color bars: red if negative, blue if positive
        # df_country["color"] = df_country["co2_yoy_pct_change"].apply(lambda v: "decrease" if v < 0 else "increase")
        st.info("📊 **TODO:** Year-on-year % change bar chart.")

        st.subheader("Key Statistics")
        display_cols = ["year", "co2", "co2_per_capita", "co2_yoy_pct_change", "ghg_intensity"]
        available    = [c for c in display_cols if c in df_country.columns]
        # TODO: st.dataframe(df_country[available].set_index("year").round(2))
        st.info("📋 **TODO:** Add summary data table.")

# ─────────────────────────────────────────────────────────────────────────────
# FORECASTS
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Forecasts":
    st.title("ETS(A,Ad,N) Emissions Forecasts (2019–2043)")
    st.markdown(
        "Forecasts from Holt's Damped Trend ETS(A,Ad,N) trained on 1990–2018, "
        "with 95% confidence intervals extending to 2043."
    )

    country = st.selectbox("Select a country", options=COUNTRIES)

    st.subheader(f"Forecast — {country}")
    st.info(
        "📊 **TODO:** Add ETS(A,Ad,N) forecast chart here.\n\n"
        "**Hint:** In Week 4 of the notebook, save your per-country forecast results "
        "to a CSV (e.g. `data/ets_forecasts.csv`) with columns: "
        "`country, year, mean, ci_lower, ci_upper`. "
        "Then load and plot them here using `px.line` for the mean and `go.Scatter` "
        "with `fill='tonexty'` for the confidence band.\n\n"
        "The `forecasts` dict built in §4.3 contains `forecasts[country]['mean']`, "
        "`forecasts[country]['lower']`, and `forecasts[country]['upper']`."
    )

    st.divider()
    st.subheader("Forecast Summary — All 10 Countries")
    st.info(
        "📋 **TODO:** Load and display the forecast summary table from Week 4 §4.5.\n\n"
        "Columns: Country | 2030 Forecast | 2035 Forecast | 2040 Forecast | 2020 Actual | % Change 2020–2040"
    )

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO COMPARISON
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Scenario Comparison":
    st.title("Scenario Comparison (2025–2040)")
    st.markdown(
        "Compare **Business as Usual (BAU)**, **Moderate Mitigation (−2%/yr)**, "
        "and **Aggressive Mitigation (−5%/yr)** starting from 2025."
    )

    if df_scenarios is None:
        st.warning(
            "⚠️ `data/scenario_projections.csv` not found.\n\n"
            "Complete **Week 5** of the notebook (optional) to generate this file."
        )
    else:
        country_option  = st.selectbox("Country", options=["All 10 countries"] + COUNTRIES)
        scenario_filter = st.radio(
            "Show scenarios", options=["All", "BAU", "Moderate", "Aggressive"], horizontal=True
        )

        # TODO: Filter df_scenarios, overlay line chart with SCENARIO_COLORS
        # Also overlay historical actuals from df as a grey line
        # Example:
        # df_plot = df_scenarios.copy()
        # if country_option != "All 10 countries":
        #     df_plot = df_plot[df_plot["country"] == country_option]
        # if scenario_filter != "All":
        #     df_plot = df_plot[df_plot["scenario"] == scenario_filter]
        # fig = px.line(df_plot, x="year", y="co2_projected", color="scenario",
        #               color_discrete_map=SCENARIO_COLORS, ...)
        # st.plotly_chart(fig, use_container_width=True)
        st.info("📊 **TODO:** Add scenario overlay chart (see SCENARIO_COLORS and commented code above).")

        st.divider()
        st.subheader("Cumulative CO₂ Emissions 2025–2040")
        # TODO: Compute df_scenarios.groupby(["country","scenario"])["co2_projected"].sum()
        # Then px.bar(..., barmode="group")
        st.info("📊 **TODO:** Add cumulative emissions grouped bar chart.")

# ─────────────────────────────────────────────────────────────────────────────
# ABOUT
# ─────────────────────────────────────────────────────────────────────────────
elif page == "About":
    st.title("About This Project")
    st.markdown("""
## Climate Change Trend Analysis and Forecasting

This dashboard presents findings from a 7-week data science project conducted as part of the
**IDEAS TIH Summer Internship 2026**, mentored by Sauparna Sarkar.

---

### Methodology Summary

| Step | Detail |
|------|--------|
| Dataset | OWID CO₂ dataset, filtered to sovereign nations from 1990 onwards |
| Countries | China, United States, India, Russia, Japan, Germany, Brazil, United Kingdom, South Africa, Australia |
| Feature Engineering | Lag features (1–3 yrs), 5-yr rolling mean, YoY % change, GHG intensity |
| Train / Test Split | Temporal — train 1990–2018, test 2019–2023 |
| Models | Naive Baseline · Linear Regression · Random Forest · ETS(A,Ad,N) |
| Forecasting | Holt's Damped Trend ETS(A,Ad,N) trained on 1990–2018, forecast to 2043 with 95% CI |
| Scenarios | BAU · Moderate (−2%/yr) · Aggressive (−5%/yr) from 2025 |

---

### Data Sources

| Dataset | URL |
|---------|-----|
| OWID CO₂ and GHG Emissions | https://github.com/owid/co2-data |
| Climate Watch Historical Emissions | https://climatewatchdata.org |

---

### Team

| Name | Institute |
|------|-----------|
| [YOUR NAME] | [YOUR INSTITUTE] |
| [YOUR NAME] | [YOUR INSTITUTE] |
| [YOUR NAME] | [YOUR INSTITUTE] |
| [YOUR NAME] | [YOUR INSTITUTE] |
| [YOUR NAME] | [YOUR INSTITUTE] |
| [YOUR NAME] | [YOUR INSTITUTE] |
| [YOUR NAME] | [YOUR INSTITUTE] |

---

*IDEAS TIH Summer Internship 2026 · Mentor: Sauparna Sarkar*
""")
