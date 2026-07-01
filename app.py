"""
GHG Trend Analysis & Forecasting — Streamlit Dashboard
IDEAS TIH Summer Internship 2026

Week 6 Stretch Goal: Fill in the # TODO sections for each page.

Prerequisites:
  - data/ghg_features.csv          (generated in Week 2)
  - data/ets_forecasts.csv         (generated in Week 4, for Forecasts page)
  - data/scenario_projections.csv  (generated in Week 5, optional)

Run with:
    streamlit run app.py
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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
def load_forecasts():
    """Load ETS(A,Ad,N) forecast results produced in Week 4."""
    path = "data/ets_forecasts.csv"
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


@st.cache_data
def load_raw():
    """OWID raw data for methane/N₂O columns, filtered to 10 countries 1990+."""
    path = "data/owid-co2-data.csv"
    if not os.path.exists(path):
        return None
    cols = ["country", "year", "co2", "methane", "nitrous_oxide"]
    df_r = pd.read_csv(path, usecols=cols)
    return df_r[(df_r["country"].isin(COUNTRIES)) & (df_r["year"] >= 1990)].copy()


@st.cache_data
def load_model_comparison():
    """Load five-model MAE/RMSE comparison table produced in Week 4 §4.6."""
    path = "data/model_comparison.csv"
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
df_forecasts = load_forecasts()
df_scenarios = load_scenarios()
df_raw       = load_raw()
df_model_cmp = load_model_comparison()

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

        latest_co2 = df[(df["year"] == latest_year) & (df["country"].isin(COUNTRIES))]["co2"].sum()
        co2_1990   = df[(df["year"] == 1990)        & (df["country"].isin(COUNTRIES))]["co2"].sum()
        pct_change = (latest_co2 - co2_1990) / co2_1990 * 100

        with col1:
            st.metric(f"10-Country CO₂ ({latest_year})", f"{latest_co2:,.0f} MtCO₂")

        with col2:
            st.metric("% Change since 1990", f"{pct_change:+.1f}%")

        with col3:
            st.metric(label="Countries Analysed", value=len(COUNTRIES))

        st.divider()
        st.subheader("Focus Countries")
        st.markdown("  |  ".join(COUNTRIES))

        df_bar = (df[df["year"] == latest_year][["country", "co2"]]
                  .sort_values("co2", ascending=False))
        fig = px.bar(df_bar, x="country", y="co2",
                     labels={"co2": "CO₂ (MtCO₂)", "country": "Country"},
                     title=f"CO₂ Emissions by Country ({latest_year})")
        st.plotly_chart(fig, use_container_width=True)

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
            if df_raw is not None:
                df_plot = (df_raw[df_raw["country"].isin(selected_countries)]
                           .dropna(subset=[gas_col]))
                fig = px.line(df_plot, x="year", y=gas_col, color="country",
                              title=f"{gas_label} Emissions by Country",
                              labels={"year": "Year", gas_col: f"{gas_label} (MtCO₂e)"})
                fig.update_layout(legend_title="Country")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("⚠️ `data/owid-co2-data.csv` not found.")
        else:
            st.warning("Select at least one country.")

        st.divider()
        st.subheader("GHG Share by Gas Type per Decade")
        if df_raw is not None:
            gas_cols_list = list(GAS_COLUMNS.values())
            dg = df_raw.copy()
            dg["decade"] = (dg["year"] // 10) * 10
            agg = dg.groupby("decade")[gas_cols_list].sum()
            agg_pct = agg.div(agg.sum(axis=1), axis=0) * 100
            gas_labels_inv = {v: k for k, v in GAS_COLUMNS.items()}
            agg_long = (agg_pct.reset_index()
                        .melt(id_vars="decade", var_name="gas", value_name="share"))
            agg_long["gas"] = agg_long["gas"].map(gas_labels_inv)
            fig2 = px.bar(agg_long, x="decade", y="share", color="gas", barmode="stack",
                          title="GHG Composition by Decade — 10 Countries (% share)",
                          labels={"decade": "Decade", "share": "Share (%)", "gas": "Gas"})
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("⚠️ `data/owid-co2-data.csv` not found.")

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
            fig = px.line(df_country, x="year", y="co2",
                          title=f"CO₂ Emissions — {country}",
                          labels={"year": "Year", "co2": "CO₂ (MtCO₂)"})
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("CO₂ per Capita")
            fig = px.line(df_country, x="year", y="co2_per_capita",
                          title=f"CO₂ per Capita — {country}",
                          labels={"year": "Year", "co2_per_capita": "tCO₂/person"})
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Year-on-Year Change (%)")
        df_yoy = df_country.dropna(subset=["co2_yoy_pct_change"]).copy()
        df_yoy["direction"] = df_yoy["co2_yoy_pct_change"].apply(
            lambda v: "Decrease" if v < 0 else "Increase")
        fig = px.bar(df_yoy, x="year", y="co2_yoy_pct_change", color="direction",
                     color_discrete_map={"Increase": "steelblue", "Decrease": "crimson"},
                     title=f"Year-on-Year CO₂ Change — {country}",
                     labels={"year": "Year", "co2_yoy_pct_change": "YoY % Change"})
        fig.update_layout(showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Key Statistics")
        display_cols = ["year", "co2", "co2_per_capita", "co2_yoy_pct_change", "ghg_intensity"]
        available    = [c for c in display_cols if c in df_country.columns]
        st.dataframe(df_country[available].set_index("year").round(2), use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# FORECASTS
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Forecasts":
    st.title("ETS(A,Ad,N) Emissions Forecasts (2019–2043)")
    st.markdown(
        "Forecasts from Holt's Damped Trend ETS(A,Ad,N) trained on 1990–2018, "
        "with 95% confidence intervals extending to 2043."
    )

    if df_forecasts is None:
        st.warning(
            "⚠️ `data/ets_forecasts.csv` not found.\n\n"
            "Complete **Week 4** of the notebook and save your forecast results, "
            "then restart the app."
        )
    else:
        country = st.selectbox("Select a country", options=COUNTRIES)

        st.subheader(f"Forecast — {country}")
        fc_c   = df_forecasts[df_forecasts["country"] == country].sort_values("year")
        hist_c = df[(df["country"] == country) & (df["year"] <= 2018)].sort_values("year")
        hold_c = df[(df["country"] == country) & (df["year"] >  2018)].sort_values("year")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist_c["year"], y=hist_c["co2"],
            name="Historical (1990–2018)", line=dict(color="steelblue", width=2)))
        fig.add_trace(go.Scatter(
            x=hold_c["year"], y=hold_c["co2"],
            name="Holdout actuals (2019–2023)", line=dict(color="darkorange", width=2)))
        fig.add_trace(go.Scatter(
            x=fc_c["year"], y=fc_c["mean"],
            name="ETS Forecast", line=dict(color="green", width=2)))
        fig.add_trace(go.Scatter(
            x=pd.concat([fc_c["year"], fc_c["year"].iloc[::-1]]),
            y=pd.concat([fc_c["ci_upper"], fc_c["ci_lower"].iloc[::-1]]),
            fill="toself", fillcolor="rgba(0,128,0,0.15)",
            line=dict(color="rgba(255,255,255,0)"), name="95% CI"))
        fig.update_layout(
            title=f"ETS(A,Ad,N) Forecast — {country}",
            xaxis_title="Year", yaxis_title="CO₂ (MtCO₂)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("Forecast Summary — All 10 Countries")
        rows = []
        for c in COUNTRIES:
            fc = df_forecasts[df_forecasts["country"] == c].set_index("year")["mean"]
            actual_2020 = df[(df["country"] == c) & (df["year"] == 2020)]["co2"].values
            if len(actual_2020) == 0:
                continue
            a2020 = actual_2020[0]
            f2040 = fc.get(2040, float("nan"))
            rows.append({
                "Country":               c,
                "2030 Forecast (MtCO₂)": round(fc.get(2030, float("nan")), 1),
                "2035 Forecast":         round(fc.get(2035, float("nan")), 1),
                "2040 Forecast":         round(f2040, 1),
                "2020 Actual":           round(a2020, 1),
                "% Change 2020→2040":    round((f2040 - a2020) / a2020 * 100, 1),
            })
        df_fc_summary = (pd.DataFrame(rows)
                         .set_index("Country")
                         .sort_values("2040 Forecast", ascending=False))
        st.dataframe(df_fc_summary, use_container_width=True)

        if df_model_cmp is not None:
            with st.expander("Five-Model Comparison Table (MAE / RMSE)"):
                st.dataframe(df_model_cmp.set_index("country"), use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO COMPARISON
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Scenario Comparison":
    st.title("Scenario Comparison (2025–2040)")
    st.markdown(
        "Compare **Business as Usual (BAU)**, **Moderate Mitigation (−2%/yr)**, "
        "and **Aggressive Mitigation (−5%/yr)** starting from 2025."
    )

    st.info(
        "**Scenario Analysis — Coming Soon**\n\n"
        "This page will show Business-as-Usual, Moderate Mitigation (−2%/yr), "
        "and Aggressive Mitigation (−5%/yr) projections from 2025 to 2040.\n\n"
        "Week 5 scenario analysis has not been completed yet. "
        "Rerun `streamlit run app.py` after completing Week 5 in the notebook."
    )

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
