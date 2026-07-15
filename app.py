"""
GHG Emissions Trend Analysis & Forecasting — Streamlit Dashboard
IDEAS TIH Summer Internship 2026

Week 6 Stretch Goal: Fill in the # TODO sections for each page.

Prerequisites:
  - data/ghg_features.csv          (generated in Week 2)
  - data/ets_forecasts.csv         (generated in Week 4, for Forecasts page)
  - data/scenario_projections.csv  (generated in Week 5, optional)
  - data/ets_parameters.csv        (generated in Week 4, optional — Forecasts page insights)
  - data/feature_importance.csv    (generated in Week 3, optional — Forecasts page insights)

Run with:
    streamlit run app.py
"""

import os

# Work around a segfault in pyarrow's bundled mimalloc allocator, hit when Streamlit
# converts a DataFrame containing NaNs to Arrow for st.dataframe() (observed crashing in
# arrow::py::NumPyNullsConverter::Convert on macOS 26 / Python 3.14 / pyarrow 25.0.0).
# Must be set before pyarrow is imported / initializes its default memory pool.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

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
    page_title="GHG Emissions Analysis",
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


@st.cache_data
def load_ets_parameters():
    """Load ETS(A,Ad,N) fitted smoothing parameters (α, β*, φ) for all 10 countries — Week 4."""
    path = "data/ets_parameters.csv"
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


@st.cache_data
def load_feature_importance():
    """Load pooled Random Forest feature importances produced in Week 3 §3.6."""
    path = "data/feature_importance.csv"
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🌍 GHG Emissions Analysis")
st.sidebar.markdown("**IDEAS TIH Summer Internship 2026**")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Historical Trends", "Country Profile", "Forecasts", "Scenario Comparison", "About"],
)

st.sidebar.divider()
st.sidebar.caption("Mentor: Sauparna Sarkar")

# ── Load data ─────────────────────────────────────────────────────────────────
df            = load_features()
df_forecasts  = load_forecasts()
df_scenarios  = load_scenarios()
df_raw        = load_raw()
df_model_cmp  = load_model_comparison()
df_ets_params = load_ets_parameters()
df_feat_imp   = load_feature_importance()

# ─────────────────────────────────────────────────────────────────────────────
# OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
if page == "Overview":
    st.title("GHG Emissions Trend Analysis and Forecasting")
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

        st.divider()
        st.subheader("Top Movers Since 1990 (10 Focus Countries)")
        st.caption(
            "Fastest growth and largest reduction in CO₂ emissions, 1990 → "
            f"{latest_year}, among the 10 focus countries."
        )

        co2_1990_by_country   = df[(df["year"] == 1990) & (df["country"].isin(COUNTRIES))].set_index("country")["co2"]
        co2_latest_by_country = df[(df["year"] == latest_year) & (df["country"].isin(COUNTRIES))].set_index("country")["co2"]
        absolute_change = co2_latest_by_country - co2_1990_by_country
        pct_change_by_country = absolute_change / co2_1990_by_country * 100

        movers = pd.DataFrame({
            "1990 (MtCO₂)": co2_1990_by_country,
            f"{latest_year} (MtCO₂)": co2_latest_by_country,
            "Absolute Change (MtCO₂)": absolute_change,
            "% Change": pct_change_by_country,
        }).dropna().sort_values("% Change", ascending=False)

        col_growth, col_reduction = st.columns(2)
        with col_growth:
            top_growth = movers.iloc[0]
            st.metric(
                f"Fastest Growth — {movers.index[0]}",
                f"{top_growth['% Change']:+.1f}%",
                f"{top_growth['Absolute Change (MtCO₂)']:+,.0f} MtCO₂",
            )
        with col_reduction:
            top_reduction = movers.iloc[-1]
            st.metric(
                f"Largest Reduction — {movers.index[-1]}",
                f"{top_reduction['% Change']:+.1f}%",
                f"{top_reduction['Absolute Change (MtCO₂)']:+,.0f} MtCO₂",
            )

        fig_movers = px.bar(
            movers.reset_index(), x="country", y="% Change",
            labels={"country": "Country", "% Change": f"% Change in CO₂ (1990→{latest_year})"},
            title=f"CO₂ % Change by Country, 1990–{latest_year}",
            color="% Change", color_continuous_scale=["green", "lightgrey", "crimson"],
        )
        st.plotly_chart(fig_movers, use_container_width=True)

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
            dg = df_raw.assign(decade=(df_raw["year"] // 10) * 10)
            agg = dg.groupby("decade")[gas_cols_list].sum()
            agg_pct = agg.div(agg.sum(axis=1), axis=0) * 100
            gas_labels_inv = {v: k for k, v in GAS_COLUMNS.items()}
            agg_long = (agg_pct.reset_index()
                        .melt(id_vars="decade", var_name="gas", value_name="share"))
            agg_long = agg_long.assign(gas=agg_long["gas"].map(gas_labels_inv))
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
        df_country = df[df["country"] == country].sort_values("year").copy()

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
        df_yoy.loc[:, "direction"] = df_yoy["co2_yoy_pct_change"].apply(
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
        df_display = df_country[available].set_index("year").round(2).rename(
            columns={"ghg_intensity": "ghg_intensity (kg CO₂e/$ GDP)"}
        )
        st.dataframe(df_display, use_container_width=True)

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

        if df_ets_params is not None:
            with st.expander("ETS(A,Ad,N) Fitted Parameters — All 10 Countries"):
                st.markdown(
                    "**α** (level smoothing), **β\\*** (trend smoothing), and **φ** (damping) "
                    "for each country's Holt's Damped Trend model, fit on 1990–2018."
                )
                df_params_display = df_ets_params.rename(columns={
                    "alpha": "α (level)", "beta_star": "β* (trend)", "phi": "φ (damping)",
                }).set_index("country")
                st.dataframe(df_params_display.round(4), use_container_width=True)

        if df_feat_imp is not None:
            with st.expander("Random Forest Feature Importance (Pooled Model)"):
                fig = px.bar(
                    df_feat_imp.sort_values("importance"),
                    x="importance", y="feature", orientation="h",
                    labels={"importance": "Importance (mean decrease in impurity)", "feature": "Feature"},
                    title="RF Pooled Feature Importances — All 10 Countries",
                )
                st.plotly_chart(fig, use_container_width=True)

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
            "Complete **Week 5** of the notebook to generate this file, then restart the app."
        )
    else:
        def bau_segment(country_filter, start, end):
            """BAU (ETS mean), summed across the given countries, restricted to a year range."""
            if df_forecasts is None:
                return pd.Series(dtype=float)
            fc = df_forecasts[df_forecasts["country"].isin(country_filter)]
            fc = fc[(fc["year"] >= start) & (fc["year"] <= end)]
            return fc.groupby("year")["mean"].sum()

        view_mode = st.radio("View", ["Single Country", "Global Aggregate"], horizontal=True)

        if view_mode == "Single Country":
            country = st.selectbox("Select a country", options=COUNTRIES)
            countries_in_view = [country]
            title_suffix = country
        else:
            countries_in_view = COUNTRIES
            title_suffix = "All 10 Countries"

        hist = (
            df[(df["country"].isin(countries_in_view)) & (df["year"] <= 2024)]
            .groupby("year")["co2"].sum()
            if df is not None else pd.Series(dtype=float)
        )
        level_1990 = hist.loc[1990] if 1990 in hist.index else None
        bau_2020_2024 = bau_segment(countries_in_view, 2020, 2024)

        fig = go.Figure()
        if not hist.empty:
            fig.add_trace(go.Scatter(
                x=hist.index, y=hist.values,
                name="Historical (1990–2024)", line=dict(color="grey", width=2)))
        for scenario, color in SCENARIO_COLORS.items():
            if scenario == "BAU":
                series = bau_segment(countries_in_view, 2020, 2040)
            else:
                future = (
                    df_scenarios[
                        (df_scenarios["country"].isin(countries_in_view)) &
                        (df_scenarios["scenario"] == scenario)
                    ].groupby("year")["co2_projected"].sum()
                )
                series = pd.concat([bau_2020_2024, future])
            fig.add_trace(go.Scatter(
                x=series.index, y=series.values,
                name=scenario, line=dict(color=color, width=2)))
        if level_1990 is not None:
            fig.add_hline(
                y=level_1990, line_dash="dot", line_color="gray",
                annotation_text="1990 level", annotation_position="bottom right")
        fig.update_layout(
            title=f"CO₂ Emissions Scenarios — {title_suffix}",
            xaxis_title="Year", yaxis_title="CO₂ (MtCO₂)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("Cumulative Emissions Impact, 2025–2040")
        sort_scenario = st.radio(
            "Sort by cumulative emissions under scenario",
            list(SCENARIO_COLORS.keys()), horizontal=True,
        )
        cumulative = (
            df_scenarios.groupby(["country", "scenario"])["co2_projected"].sum()
            .reset_index().rename(columns={"co2_projected": "cumulative_co2"})
        )
        order = (
            cumulative[cumulative["scenario"] == sort_scenario]
            .sort_values("cumulative_co2", ascending=False)["country"].tolist()
        )
        fig2 = px.bar(
            cumulative, x="country", y="cumulative_co2", color="scenario", barmode="group",
            category_orders={"country": order, "scenario": list(SCENARIO_COLORS.keys())},
            color_discrete_map=SCENARIO_COLORS,
            labels={"country": "Country", "cumulative_co2": "Cumulative CO₂, 2025–2040 (MtCO₂)",
                    "scenario": "Scenario"},
            title=f"Cumulative CO₂ Emissions by Scenario, 2025–2040 (sorted by {sort_scenario})",
        )
        st.plotly_chart(fig2, use_container_width=True)

        table = cumulative.pivot(index="country", columns="scenario", values="cumulative_co2")
        table = table[list(SCENARIO_COLORS.keys())].loc[order].round(0)
        st.dataframe(table, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# ABOUT
# ─────────────────────────────────────────────────────────────────────────────
elif page == "About":
    st.title("About This Project")
    st.markdown("""
## GHG Emissions Trend Analysis and Forecasting

This dashboard presents findings from a 7-week data science project conducted as part of the
**IDEAS TIH Summer Internship 2026**.

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

*IDEAS TIH Summer Internship 2026 · Mentor: Sauparna Sarkar*
""")
