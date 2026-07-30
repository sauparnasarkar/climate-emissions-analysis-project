# Enhancements

Tracks planned and shipped enhancements to the GHG Emissions Trend Analysis and
Forecasting project, beyond the core weekly `SPEC.md` deliverables.

---

## Release 2.1 — Expand to ≥100 Mt Emitters, Persisted Selection, Dynamic UI Counts

**Status: Shipped** (Jul 2026, seven sequential PRs — one per phase below, each reviewed
and merged individually). See `SPEC.md` §5.6 and `CLAUDE.md`'s "Two-tier country pattern"
bullet for the durable reference; this section is kept as the historical planning record.

**Goal:** Grow the analysis beyond the original 10 hardcoded countries to a data-driven
set of ~40 major emitters, selected by data-quality coverage and emissions materiality,
while keeping the original 10 as the default/featured selection in chart views. Users
can search and switch to any of the expanded countries via a type-ahead dropdown. The
expanded country list is computed in Week 1 and persisted, not hardcoded, and every UI
surface that currently states a country count or lists countries does so dynamically.

**Corrections made during implementation** (this draft's original sketches undersold or
missed these — noted here so the record stays accurate):
- **2.1.7** originally proposed a bespoke `CountrySelect` combobox. Shipped instead by
  porting `MultiSelect`'s existing search-in-menu pattern directly onto `design-system`'s
  `Select` component — no new component.
- The two hardcoded 5×2 subplot grids (`week3_regression.ipynb` §3.8,
  `week4_ets_forecasting.ipynb` §4.3) do **not** scale to the expanded set — they stay on
  `FEATURED_COUNTRIES` (10) with dynamic titles. This was generalized project-wide: every
  multi-country chart caps simultaneous selections at 10 (`maxSelected` / `max_selections`),
  even though the *pool* to choose from is the full expanded list.
- `MultiSelect` gained a new `maxSelected` prop (not in the original draft) to enforce the
  cap above; used by `HistoricalTrendsPage.tsx` and `app.py`'s Historical Trends page.
- **2.1.3**'s `.gitignore` snippet assumed `data/*` was the ignore rule; the actual rule is
  `data/*.csv` only, so `selected_countries.json` needed **no** `.gitignore` change at all —
  applying the snippet literally would have incorrectly widened the ignore rule.

### 2.1.1 — Coverage-based filter logic (Week 1 §1.2)

Replace the exploratory, print-only coverage cell with a filter that is actually used
downstream. For each sovereign country (`year >= 1990`, `NON_SOVEREIGN` excluded):

```python
key_cols = ['co2', 'co2_per_capita', 'total_ghg', 'methane', 'nitrous_oxide', 'gdp', 'population']

coverage = (
    df_filtered[key_cols].notna()
    .groupby(df_filtered['country'])
    .mean() * 100
)
passes_coverage = coverage.min(axis=1) > 90   # every key column individually clears 90% — not just the average
```

- Use `min(axis=1)`, not `mean(axis=1)`: a country should not pass on the strength of
  five perfect columns while one key column (e.g. `gdp`) is badly incomplete.
- Empirically (live OWID pull): 162 of ~220 sovereign countries pass at this threshold,
  one fewer than the `mean`-based version (UAE fails on `min` due to 88.6% GDP coverage).
- The 90% threshold sits in a natural gap in the coverage-score distribution (zero
  countries score between 90–95%, so any threshold in that range is equivalent) —
  document this in a markdown cell as the justification for the specific number.

### 2.1.2 — Materiality floor: ≥100 Mt latest-year CO₂

Coverage alone is not a useful country filter on its own — 162 countries pass coverage,
including sub-1-Mt emitters (Sao Tome and Principe, Dominica, Guinea-Bissau). Apply an
emissions floor on top of the coverage-passing set:

```python
latest_year = df_filtered['year'].max()
latest_co2 = df_filtered[df_filtered['year'] == latest_year].set_index('country')['co2']
global_latest_total = df_filtered[df_filtered['year'] == latest_year]['co2'].sum()

EXPANDED_COUNTRIES = sorted(
    c for c in coverage.index[passes_coverage]
    if latest_co2.get(c, 0) >= 100
)
expanded_global_share_pct = round(latest_co2.loc[EXPANDED_COUNTRIES].sum() / global_latest_total * 100, 1)
```

- Result: **40 countries**, capturing **~92% of latest-year global CO₂** and **~91% of
  1990–latest cumulative CO₂** (live-data figures at time of writing; will shift
  slightly on re-run as OWID data refreshes).
- Floor sweep for reference (coverage-passing countries only): ≥10 Mt → 107 countries /
  98.5% of latest-year emissions; ≥25 Mt → 79 / 97.3%; ≥50 Mt → 56 / 95.1%; ≥100 Mt → 40
  / 92.2%. The 100 Mt cutoff was chosen as the point where the count meaningfully
  shrinks (56→40) while still retaining over 9 in 10 tonnes of global emissions.
- Coverage and materiality are deliberately two separate, sequential checks (not one
  blended score): coverage answers "is the data trustworthy," materiality answers "is
  the country worth featuring." Keeping them separate keeps each threshold legible on
  its own.

### 2.1.3 — Persist the selection instead of hardcoding it

Week 1 writes the computed list to `data/selected_countries.json` rather than the
result being hand-copied into `constants.py` as a literal:

```python
import json
from datetime import date

selection = {
    "generated": date.today().isoformat(),
    "source_year": int(latest_year),
    "coverage_threshold_pct": 90,
    "mt_floor": 100,
    "expanded": EXPANDED_COUNTRIES,
    "expanded_count": len(EXPANDED_COUNTRIES),
    "expanded_global_share_pct": expanded_global_share_pct,
}

if os.path.exists(_SELECTED_PATH := "../data/selected_countries.json"):
    with open(_SELECTED_PATH) as f:
        previous = json.load(f)
    added = set(EXPANDED_COUNTRIES) - set(previous["expanded"])
    dropped = set(previous["expanded"]) - set(EXPANDED_COUNTRIES)
    if added or dropped:
        print(f"⚠ EXPANDED_COUNTRIES changed since {previous['generated']}: "
              f"+{sorted(added)} -{sorted(dropped)}")
        print("  Weeks 3-5 outputs will be stale for changed countries until re-run.")

with open(_SELECTED_PATH, "w") as f:
    json.dump(selection, f, indent=2)
```

- `data/` is otherwise gitignored (large, regenerable byproducts). Carve out an
  exception for this one small file, since the country selection is a reviewable
  decision, not raw data:
  ```gitignore
  data/*
  !data/.gitkeep
  !data/selected_countries.json
  ```
- The drift check (added/dropped vs. the previously committed version) exists because
  an OWID data refresh can nudge a country across the coverage or 100 Mt line in either
  direction. Flagging this loudly on re-run prevents a stale `ghg_features.csv` /
  `ets_forecasts.csv` / etc. from silently going out of sync with the country list the
  API and frontend now serve.

### 2.1.4 — Resolve the constants.py / Week 1 circular dependency

`week1_eda.ipynb` runs `from constants import *` (cell 5) before its own coverage
computation (cell 14) executes. If `EXPANDED_COUNTRIES` were loaded eagerly at
`constants.py`'s module level, a fresh clone would fail at cell 5 — before Week 1 has
produced the file `constants.py` needs to read. Week 1 is simultaneously the consumer
of `constants.py` and the producer of the artifact `constants.py` depends on.

**Fix:** make the load lazy — a function, not a module-level name, so nothing in
`constants.py`'s module body touches the filesystem on import:

```python
# notebook/constants.py
import json, os

_SELECTED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "selected_countries.json")

FEATURED_COUNTRIES = [   # curatorial choice, not data-derived — stays a literal
    "China", "United States", "India", "Russia", "Japan",
    "Germany", "Brazil", "United Kingdom", "South Africa", "Australia",
]
COUNTRIES = FEATURED_COUNTRIES  # back-compat alias — nothing new should reference this name

def get_expanded_countries():
    """Loads data/selected_countries.json, produced by week1_eda.ipynb §1.2.
    Raises FileNotFoundError if Week 1 hasn't been run yet — by design: Weeks 2-5
    genuinely cannot proceed without it, so failing loudly here is correct."""
    if not os.path.exists(_SELECTED_PATH):
        raise FileNotFoundError(
            "data/selected_countries.json not found. Run week1_eda.ipynb §1.2 first."
        )
    with open(_SELECTED_PATH) as f:
        return json.load(f)["expanded"]
```

- Week 1's own coverage cell does **not** call `get_expanded_countries()` — it computes
  `EXPANDED_COUNTRIES` locally (2.1.1–2.1.2) and is the *producer* of the file.
- `from constants import *` now always succeeds regardless of pipeline state.
- `notebook/constants.py` lets `FileNotFoundError` propagate uncaught (correct — Weeks
  2–5 cannot proceed without it, so failing loudly is the right behavior there).
- `api/constants.py` wraps the same call in a try/fallback instead, since a crash at
  API *startup* is worse than at notebook-import time — see 2.1.6.

### 2.1.5 — Notebook changes, Weeks 2–5

- **Week 2 §2.5:** `df[df['country'].isin(COUNTRIES)]` →
  `df[df['country'].isin(get_expanded_countries())]`. This is the line that widens
  `ghg_features.csv` from ~350 rows (10 countries × 35 years) to ~1,400 rows (40 × 35).
  Update the "Expected shape" note in the notebook accordingly.
- **Week 3 (`week3_regression.ipynb`):** every `for country in COUNTRIES:` loop
  (baseline, Linear Regression, Random Forest, label-encoder fitting) →
  `for country in get_expanded_countries():`. Read the list once into a local at the
  top of the notebook rather than re-reading the file per loop. `PLOT_COUNTRIES`
  (illustrative plots only) stays untouched. Update the `LabelEncoder` comment from
  "all 10" to "all 40."
- **Week 4 (`week4_ets_forecasting.ipynb`):** same swap in the ETS parameter export,
  2020 holdout check, test-set evaluation, and forecast export loops.
  `PLOT_COUNTRIES_ETS` stays illustrative. Compute cost note: ETS fit on 35 annual
  points is sub-second per country; 40 fits vs. 10 is still trivial wall-clock time.
- **Week 5 (`week5_scenarios.ipynb`):** same swap in the BAU / Moderate / Aggressive
  scenario loop.
- **Net effect:** `ghg_features.csv`, `model_comparison_regression.csv`,
  `feature_importance.csv`, `ets_forecasts.csv`, `ets_parameters.csv`,
  `model_comparison.csv`, `scenario_projections.csv` all grow to ~40-country coverage.
  No schema changes — only row counts — so downstream consumers only need to read the
  `country` column correctly, which they already do.

### 2.1.6 — API changes

- **`api/constants.py`:** mirror `FEATURED_COUNTRIES` and `get_expanded_countries()`
  from `notebook/constants.py`, but wrap the file read in a try/fallback rather than
  letting it raise, since an unhandled exception here would crash the API at startup:
  ```python
  def get_expanded_countries():
      try:
          return _load_expanded_countries()
      except FileNotFoundError as e:
          warnings.warn(f"{e} Falling back to FEATURED_COUNTRIES only.")
          return FEATURED_COUNTRIES
  ```
  Optionally cache behind `@lru_cache(maxsize=1)` in `data_loaders.py`, matching the
  existing loader pattern — note this means a `selected_countries.json` update needs a
  process restart to take effect, consistent with how `load_features()` etc. already
  behave.
- **`api/data_loaders.py`:** `load_raw()`'s hardcoded `.isin(COUNTRIES)` filter →
  `.isin(get_expanded_countries())`, so the raw loader doesn't silently drop the 30
  newly-added countries before any router sees them.
- **`api/routers/country_profile.py`:** the 404 gate — `if country not in COUNTRIES` →
  `if country not in get_expanded_countries()`. This is the line that actually unlocks
  per-country switching for the frontend dropdown.
- **`api/routers/overview.py`, `historical.py`, `forecasts.py`, `scenarios.py`:**
  default scope stays `FEATURED_COUNTRIES` (preserves each page's existing curated
  narrative). Add an optional `scope` (`"featured"` | `"expanded"`) or explicit
  `countries` query param, validated against `get_expanded_countries()`, 404ing per
  existing convention on an unknown country.
- **New `api/routers/countries.py`:**
  ```python
  @router.get("/countries", response_model=CountriesResponse)
  def list_countries():
      return CountriesResponse(featured=FEATURED_COUNTRIES, expanded=get_expanded_countries())
  ```
  New `CountriesResponse(BaseModel)` in `schemas.py` (`featured: list[str]`,
  `expanded: list[str]`). Register the router in `api/main.py`.
- **`OverviewResponse` — new field:** add `total_countries_analyzed: int`, always equal
  to `len(get_expanded_countries())` regardless of the response's active `scope`. This
  lets the UI state "40 countries analyzed" as a standing fact independent of which
  scope a given chart is currently rendering (see 2.1.7).
- **Tests (`api/tests`):** fixture CSV mixing featured and non-featured-but-expanded
  countries; test that `country_profile` now succeeds for an expanded-but-not-featured
  country and still 404s outside both lists; test for the new `/countries` endpoint;
  test that `get_expanded_countries()` falls back to `FEATURED_COUNTRIES` with a
  warning when `selected_countries.json` is absent; test that `/overview?scope=expanded`
  widens the response correctly.

### 2.1.7 — Frontend: searchable country selector

- **`src/api/types.ts`:** add `CountriesResponse`; add `total_countries_analyzed:
  number` to `OverviewResponse`, mirroring the API.
- **`src/api/client.ts`:** add `listCountries()`.
- **New `CountrySelect` component:** searchable/type-ahead combobox (not a native
  `<select>`, given 40 options), sourced from `GET /api/countries`. Check whether the
  Syena Analytics Theme design system already has a headless combobox pattern before
  building from scratch. Behavior:
  - Initializes to `FEATURED_COUNTRIES` (multi-select context) or the first featured
    country (single-select context), depending on the page.
  - Filters the `expanded` list as the user types.
  - On multi-country chart pages, selection is **additive** — users add countries
    beyond the default 10 without the defaults being removed automatically.
- **`HistoricalTrendsPage.tsx`:** swap the hardcoded country list feeding the
  multi-line chart for `CountrySelect` in multi-select mode, seeded with
  `FEATURED_COUNTRIES`.
- **`CountryProfilePage.tsx`:** swap the single-country selector to source its options
  from `expanded` instead of `featured` — the page that most directly benefits, since
  the API gate (2.1.6) is now open for all 40.
- **`ForecastsPage.tsx` / `ScenarioComparisonPage.tsx`:** same `CountrySelect` treatment
  if per-country or multi-country.
- **Tests:** per-page smoke tests verifying the dropdown seeds with featured defaults
  and that selecting a non-featured country triggers the expected API call / route
  change, matching the existing loading/data/error test pattern.

### 2.1.8 — Frontend: dynamic Overview page text (remove hardcoded "10")

Replace every literal `10` and hardcoded country count on `OverviewPage.tsx` with
values derived from the API response:

| Current (hardcoded) | Replacement |
|---|---|
| `"...for 10 major countries using..."` | `` `...for ${data.total_countries_analyzed} major countries using...` `` |
| `` `10-Country CO₂ (${data.latest_year})` `` | `` `${data.countries_count}-Country CO₂ (${data.latest_year})` `` |
| `"Countries Analysed"` value | `data.countries_count` (already dynamic once the API stops hardcoding it) |
| `"...(10 Focus Countries)"` | `` `...(${data.focus_countries.length} Focus Countries)` `` |
| `"...among the 10 focus countries."` | `` `...among the ${data.focus_countries.length} focus countries.` `` |

If a scope toggle is added to this page, all five derive correctly from the response
for either scope automatically, with no further page changes needed.

### 2.1.9 — Frontend: dynamic About page (convert from static to data-driven)

`AboutPage.tsx` is currently a fully static component — hardcoded `METHODOLOGY_ROWS`
array, no data fetch. Convert it to fetch `/api/countries` on mount and interpolate the
country count/list into the methodology table, following the loading/data/error
pattern already used by the other pages:

```tsx
export default function AboutPage() {
  const [countries, setCountries] = useState<CountriesResponse | null>(null);
  useEffect(() => { listCountries().then(setCountries); }, []);

  const methodologyRows = [
    { step: 'Dataset', detail: 'OWID CO₂ dataset, filtered to sovereign nations from 1990 onwards' },
    {
      step: 'Countries',
      detail: countries
        ? `${countries.expanded.length} countries analyzed (≥90% key-column coverage, `
          + `≥100 Mt latest-year CO₂). Featured for comparison: ${countries.featured.join(', ')}.`
        : 'Loading…',
    },
    // ...remaining rows unchanged
  ];
  // ...
}
```

Add loading-state and error-state tests to `AboutPage.test.tsx`, since the page
currently has neither — it has never fetched anything before this change.

### 2.1.10 — Streamlit (`app.py`): same fix, both pages

- **Overview section:** replace the hardcoded `"10 major countries"` intro string,
  the `"10-Country CO₂"` metric label, and the `"Top Movers Since 1990 (10 Focus
  Countries)"` subheader / caption with f-strings driven by `len(COUNTRIES)` (featured
  scope) and `len(get_expanded_countries())` (total analyzed), matching the API's
  `countries_count` / `total_countries_analyzed` split. Optionally add an `st.radio`
  scope toggle ("Featured" / "All") mirroring the API's `scope` query param, for parity
  with the React dashboard.
- **About section:** currently a single hardcoded `st.markdown(f"""...""")` block,
  including the literal 10-country string in the methodology table. Replace the
  `Countries` row with an f-string built from `get_expanded_countries()` and
  `COUNTRIES`, same content as the React version in 2.1.9.

### 2.1.11 — Rollout sequencing

1. **Week 1** (2.1.1–2.1.3) — implement and run once to produce and commit
   `data/selected_countries.json`.
2. **`notebook/constants.py`** (2.1.4) — land the lazy `get_expanded_countries()`
   function; safe to land before or after step 1, since it only fails at call time.
3. **Weeks 2–5** (2.1.5) — mechanical `COUNTRIES` → `get_expanded_countries()` swaps;
   re-run in order to regenerate all downstream artifacts at 40-country scale.
4. **API** (2.1.6) — constants, data loader, country-profile gate, new `/countries`
   endpoint, `total_countries_analyzed` field.
5. **Frontend** (2.1.7–2.1.9) — `CountrySelect`, Overview literal removal, About page
   conversion. Can proceed in parallel with step 6.
6. **Streamlit** (2.1.10) — independent codebase reading the same `data/` artifacts;
   can happen in parallel with step 5.

**Note:** a committed `data/selected_countries.json` (step 1) must exist before steps
4–6 are meaningfully testable — otherwise every fallback path (API's
`warnings.warn` → `FEATURED_COUNTRIES`) is what gets exercised in testing, which can
mask bugs in the expanded-scope code paths until the real file is present. Run the full
pipeline end-to-end at least once before considering this release complete.

**Shipped as:** seven sequential PRs, one per phase, each individually reviewed
(Copilot review loop) and merged before the next began — Phase 1 (Week 1 + `constants.py`,
steps 1–2 above), Phase 2 (Weeks 2–5, step 3), Phase 3 (API, step 4), Phase 4
(`design-system`'s `Select` search + `MultiSelect` `maxSelected`, a prerequisite for step 5
not originally broken out as its own phase), Phase 5 (React frontend, step 5), Phase 6
(Streamlit, step 6, run in parallel with Phase 5 per this plan), Phase 7 (this
documentation pass). All notebooks were executed end-to-end against live OWID data after
Phases 1–2, confirming the real `data/selected_countries.json` (40 countries, ~92% of
latest-year global CO₂) before API/frontend work began.

---

## Release 2.2 — Three-Tier Overview: All Countries, Coverage-Filtered, User-Selected

**Status: Shipped** (Jul 2026, three sequential PRs — API, React, Streamlit — each
individually reviewed and merged before the next began). See `SPEC.md` §5.7 for the durable
reference; this section is kept as the historical planning record.

**Goal:** Restructure the Overview page from a single 10-country KPI row into three
simultaneous, always-visible tiers of increasing specificity — the true global total, the
Release 2.1 coverage(≥90%)+materiality(≥100 Mt)-filtered set (`get_expanded_countries()`,
currently ~40), and a user-controlled selection capped at 10 countries (defaulted to
`FEATURED_COUNTRIES`) — with the bar chart, % change chart, and Top Movers section reactive
to the third tier only. Depends on the shipped Release 2.1 above
(`get_expanded_countries()`/`load_expanded_countries()`, `FEATURED_COUNTRIES`,
`useCountries()`, `GET /api/countries`).

**Working definitions:**
- **All Countries** — every sovereign country in the raw dataset (`NON_SOVEREIGN` aggregates
  excluded), unfiltered by coverage or Mt. The true global total.
- **Expanded** — the coverage+materiality-filtered set from Release 2.1
  (`get_expanded_countries()`/`load_expanded_countries()`, currently 40 countries).
- **Selected** — a user-chosen subset of at most 10 countries, defaulted to
  `FEATURED_COUNTRIES`, chosen via a capped `MultiSelect`/`st.multiselect` (reusing the
  `maxSelected`/`max_selections` cap Release 2.1 already added for Historical Trends). Drives
  the bar chart, % change chart, and Top Movers section.

Verified against the shipped 2.1 codebase before finalizing this plan (not just the original
draft assumptions): there is no bespoke `CountrySelect` component (2.1 shipped by extending
`Select`/`MultiSelect` with search + `maxSelected` directly); `NON_SOVEREIGN` exists in
`notebook/constants.py` but was never mirrored to `api/constants.py` — a genuine gap, since no
API code previously needed an unfiltered "all countries" view; `api/routers/overview.py`'s
current `load_features()` (`ghg_features.csv`) already only contains the ~40 expanded
countries (Week 2 computes features for `get_expanded_countries()`, not the original 10). A
live sanity check (summing raw OWID `co2` for the latest year with the full `NON_SOVEREIGN`
list excluded) landed within ~3% of OWID's own "World" row — confirming the exclusion list is
complete and the "All Countries" tier concept is sound. (A partial exclusion — continents
only — overcounts by ~4x from double-counted income/OECD/EU groupings, which is exactly why
the full list matters.)

Three design decisions made before implementation:
1. **Expanded/Selected tiers keep reading `ghg_features.csv`** (today's `load_features()`),
   not a new raw-OWID loader — only the new "All Countries" tier reads raw data via a new
   `load_raw_sovereign()`. This keeps the existing `ghg_features.csv`-missing 503/Week-2-message
   test valid as-is; a new prerequisite (the raw OWID file) is added only for the new tier.
2. **Empty selection**: the fetch still fires even when the user's selection is empty
   (`selected = countries or FEATURED_COUNTRIES` — an empty list is falsy in Python, so the API
   defaults it server-side) — the frontend gates only the *rendering* of the Selected tier +
   charts + Top Movers behind `selected.length > 0`, matching `HistoricalTrendsPage`'s existing
   pattern, showing an inline "select at least one" warning there instead. Since All
   Countries/Expanded don't depend on the selection at all, they stay visible throughout. A
   "Reset to default" button next to the picker restores `FEATURED_COUNTRIES` in one click.
3. **Label wording**: `"(N available)"` on the three single-select pickers (Country Profile,
   Forecasts, Scenario Comparison — a cap of 1 is implicit in a single-value control),
   `"(up to N/total)"` on multi-select pickers (Historical Trends, the new Overview picker).

### 2.2.1 — `NON_SOVEREIGN` mirror + `MAX_SELECTED_COUNTRIES`

`api/constants.py` gains `NON_SOVEREIGN` (verbatim copy from `notebook/constants.py`, kept in
sync by hand — same three-way-mirror convention already established for `FEATURED_COUNTRIES`
across `notebook/`, `api/`, and `app.py`) and `MAX_SELECTED_COUNTRIES = 10`. Without the
`NON_SOVEREIGN` exclusion, summing raw per-country rows plus an unexcluded aggregate row would
silently double- or quadruple-count — a correctness bug, not a style issue, so this is a
blocking prerequisite for everything below.

### 2.2.2 — New loader: all sovereign countries, unfiltered by coverage or Mt

`load_raw()` stays scoped to `load_expanded_countries()` — it backs Historical Trends, which
has no reason to widen. A new `load_raw_sovereign()` in `api/data_loaders.py` reads
`owid-co2-data.csv` directly (`country`, `year`, `co2` only), filtered to
`~isin(NON_SOVEREIGN) & year >= 1990`, `@lru_cache`d, raising `DataNotFoundError` like every
other hard-required loader. Backs only the new "All Countries" tier — Expanded/Selected keep
reading `ghg_features.csv` (decision #1 above).

### 2.2.3 — `OverviewResponse` schema restructure (breaking change)

Replaces the current flat shape with a nested per-tier one: `OverviewTierMetrics` (`label`,
`countries_count`, `latest_year`, `latest_co2_total`, `co2_1990_total`,
`pct_change_since_1990`), and `OverviewResponse` = `all_countries` / `expanded_countries` /
`selected` (each an `OverviewTierMetrics`) + `selected_country_list` +
`latest_year_bar`/`top_movers`/`fastest_growth`/`largest_reduction` (unchanged types, now
unconditionally scoped to `selected`). Old flat fields (`latest_year`, `latest_co2_total`,
`co2_1990_total`, `pct_change_since_1990`, `countries_count`, `focus_countries`,
`total_countries_analyzed`) are removed, each folding into the tier it describes. `OverviewPage.tsx`
and `app.py`'s Overview section both need a matching rewrite, not just a field addition.

### 2.2.4 — `/overview` endpoint: tier computation + capped `countries` query param

Drops `scope=featured|expanded` entirely, replaced by `countries: list[str] | None =
Query(None)` (repeated `?countries=China&countries=India&...`, same pattern already used by
`historical.py`/explorer endpoints). Server-side validation is the enforcement boundary, not
the frontend's `maxSelected` (UX convenience only): `len(selected) > MAX_SELECTED_COUNTRIES` →
422; any country not in `load_expanded_countries()` → 404. Default
`selected = countries or FEATURED_COUNTRIES`. Bar chart, % change chart, and Top
Movers/fastest-growth/largest-reduction are unconditionally computed on the `selected`-scoped
dataframe — the two summary tiers above are context, not chart inputs.

### 2.2.5 — Frontend: Overview's country picker, reusing 2.1's shipped pattern

Not a new component — the exact pattern already established by `HistoricalTrendsPage.tsx`:
`design-system`'s `MultiSelect`, sourced via `useCountries()`, capped with `maxSelected`,
defaulting to `featured` once `useCountries()` resolves. `MAX_SELECTED_COUNTRIES` moves to a
shared `src/constants.ts` (mirroring `api/constants.py`) rather than staying duplicated in
`HistoricalTrendsPage.tsx` alone, since a second page now needs the same number.

### 2.2.6 — Frontend: three tiers in one compact table

Replaces the single KPI row with all three tiers (`All Countries` / `Expanded (Coverage +
≥100 Mt)` / `Selected`) in one bordered `Table` — Tier / Countries / CO₂ / % Change since
1990 — instead of three separate headed rows of `KpiStat` cards. **Revised post-launch**: the
original shipped design used three stacked KPI-card rows (one heading + three `KpiStat` cards
each, nine cards total); user feedback that this took up too much vertical space led to
condensing it into the single table described here, in a follow-up PR. `% Change since 1990`
keeps its color-coded up/down styling (green/red) via a custom column `render`, reusing
`KpiStat`'s own color tokens rather than introducing new ones.

### 2.2.7 — Frontend: picker + chart/Top-Movers wiring, empty-selection behavior

Below the three KPI rows: the `MultiSelect` from 2.2.5, a "Reset to default" button restoring
`FEATURED_COUNTRIES`, and a pipe-separated `selected_country_list` line (same style as the
existing `focus_countries` line). The bar chart, % change chart, and Top Movers/Fastest
Growth/Largest Reduction cards read `data.latest_year_bar`/`data.top_movers`/etc. directly — no
page-level filtering, since the API already scopes these to `selected`. Refetches `/overview`
on every `MultiSelect` change. When `selected.length === 0`: the All Countries/Expanded KPI
rows stay visible (they don't depend on the selection); only the Selected KPI row + charts +
Top Movers are replaced with an inline "select at least one country" warning.

### 2.2.8 — Streamlit (`app.py`) mirror

Same restructure in the `if page == "Overview"` block: three `st.columns(3)` metric rows via a
new `overview_tier_metrics(df, countries, label)` helper mirroring `_tier_metrics` (2.2.4);
`st.multiselect(options=get_expanded_countries(), default=FEATURED_COUNTRIES,
max_selections=MAX_SELECTED_COUNTRIES)` (native cap, consistent with how Release 2.1 Phase 6
already used `max_selections` for Historical Trends); a `st.button("Reset to default
countries")` resetting the multiselect's `st.session_state` value; bar chart/% change
chart/Top Movers re-filtered to the selection — this also fixes a latent pre-existing bug
where today's bar chart isn't filtered by `FEATURED_COUNTRIES` at all (only the KPI/movers
calculations are), the same class of bug already fixed API-side in Release 2.1 Phase 3 but
missed in the `app.py` port.

### 2.2.9 — Tests

API: each tier's metrics independently (`all_countries` reflects the full
`NON_SOVEREIGN`-excluded universe; `expanded` matches `load_expanded_countries()`'s count;
`selected` matches whatever `countries` param was passed); 422 at 11 countries; 404 on an
unknown country; default to `FEATURED_COUNTRIES` when `countries` is omitted;
`latest_year_bar`/`top_movers` change with `countries`, unaffected by tier 1/2 values.
Frontend: default render shows `FEATURED_COUNTRIES` selected and all three KPI rows populated;
an 11th selection is blocked; changing selection triggers a refetch and updates chart/Top
Movers; deselecting to 0 shows the warning while the top two tiers remain visible; "Reset to
default" restores the selection and refetches.

### 2.2.10 — Rollout sequencing

1. **API** (2.2.1–2.2.4, 2.2.9's API tests) — breaking change to `/overview`; one PR, since
   schema/endpoint/loader all change together.
2. **React** (2.2.5–2.2.7, plus 2.2.11 below bundled in) and **Streamlit** (2.2.8) — parallel
   once the API PR is merged, same precedent as Release 2.1 Phases 5/6.
3. **Documentation** — this section, drafted before implementation starts and revised again
   once shipped (see Status above).

**Shipped as:** three sequential PRs — API (#80), React (#81), Streamlit (#82) — each
reviewed (Copilot review loop) and merged before the next began. Corrections found during
implementation, beyond this section's original draft:
- **`top_movers[0]`/`[-1]` `IndexError` risk.** `countries=` lets a caller select any subset
  of the expanded set; if every selected country lacked a complete 1990-to-latest-year pair,
  `movers.dropna()` would empty the list before the indexed access. Verified this can't
  happen with today's real 40-country data (every one, including post-Soviet states like
  Kazakhstan/Uzbekistan, has both rows) — but it's arbitrary user input, so both the API
  (falls back to an `"N/A"` sentinel `MoverRow`) and `app.py` (falls back to `st.info()`,
  since it re-derives movers independently rather than calling the API) now guard against it.
- **Unknown-country validation was wrongly applied to the `FEATURED_COUNTRIES` default
  itself**, not just an explicitly-supplied `countries` param — broke whenever a narrower
  expanded set (only possible in test fixtures; production's is always a superset of
  `FEATURED_COUNTRIES` by construction) didn't fully contain the default. Fixed to only
  validate what the caller actually supplies.
- **`OverviewTierMetrics.label`** tightened from `str` to
  `Literal["All Countries", "Expanded", "Selected"]` (and the matching TS union type),
  catching a label/call-site mismatch as a type/validation error instead of silent drift.
- **React's `OverviewContent` was unmounting its own `MultiSelect` on every refetch** — a
  top-level `if (loading) return <Spinner />` replaced the whole component (picker included)
  each time the selection changed, since `useAsync` preserves the previous `data` during a
  refetch and only flips `loading`. Fixed to only block on a spinner before any data has ever
  loaded, matching every other page's pattern of gating just the data-dependent section.

### 2.2.11 — "(up to N/total)" / "(N available)" label on every country dropdown

Adds the live expanded-count to every existing country picker's label — no component change
needed, since every picker already sources options from `useCountries()`. Single-select pages
(Country Profile, Forecasts, Scenario Comparison) get `"(N available)"`; multi-select pickers
(Historical Trends, the new Overview picker) get `"(up to N/total)"`, reusing the shared
`MAX_SELECTED_COUNTRIES` from 2.2.5. Streamlit's `st.selectbox`/`st.multiselect` calls get the
equivalent treatment for parity. Falls back to today's static label text before
`useCountries()` resolves, rather than rendering "(undefined available)" for a frame. Bundled
into the React/Streamlit PRs above rather than a separate follow-up PR, since it touches the
same files those phases already modify.

---

## Release 3 — UX Review Fixes, World Map, Scenario Redesign, Visual Polish

**Status: Shipped.** React-only for this release (Streamlit/`app.py` untouched) — a full UX review
(code-level pass + live-screenshot pass against `labs.syena.io/ghg-emissions-analysis`) surfaced
real bugs, a scope-expanding pair of new visualizations (world map, scenario comparison redesign),
and a visual-polish wishlist. Four `design-system` components (`KpiStat`, `MultiSelect`,
`SidebarNav`, `SyChart`) needed their own fixes first, tracked in that repo's
`CONSUMER-REQUESTS-ghg-dashboard.md` and implemented as prerequisite PRs there before the app-side
phases that consume them. All 5 `design-system` PRs and all 7 app-side PRs merged to `main` in both
repos and deployed.

**Implementation-time findings, beyond what verification against live code caught during
planning:**
- Copilot's review caught (and, via its coding-agent mode, directly fixed) two real `design-system`
  bugs: `MultiSelect`'s new clear-all spacing was unconditional even with zero tags selected
  (asymmetric padding on an empty control), and `SidebarNav`'s new `groups` prop rendered multiple
  `role="menu"` elements with no distinguishing `aria-label` (a real a11y regression for screen
  reader users). It also caught one pre-existing app bug while reviewing 3.5: the Overview tier
  table's own `% Change since 1990` column had `POSITIVE_COLOR`/`NEGATIVE_COLOR` backwards (an
  emissions *increase* rendered green) — not introduced by this release, but directly contradicted
  the color-semantics convention 3.5 establishes, so fixed alongside it.
- A real `SyChart` color-handling gap surfaced during 3.5's own manual verification (not caught by
  any review): `pointColors`/`color` are passed straight into Plotly's own color parser, which
  cannot resolve CSS custom properties (`var(--foo, #fallback)`) the way a plain DOM `style` prop
  can — it silently renders black instead of falling back to the intended hex. Fixed by adding
  literal-hex variants (`POSITIVE_COLOR_HEX`/`NEGATIVE_COLOR_HEX`) alongside the `var(...)` forms
  for any color value bound into a Plotly trace; the `var(...)` forms stay correct for genuine DOM
  `style` props.
- Merging all 12 PRs surfaced the expected consequence of building every phase off `main`
  independently rather than stacking branches: `OverviewPage.tsx` (touched by 3.1's caption removal,
  3.5, 3.4, and 3.12) needed manual conflict resolution three times as earlier phases merged first;
  `design-system`'s `SyChart.stories.tsx` needed one similar resolution between the choropleth/
  treemap PR and the `fillOpacity` PR. All were non-overlapping additions resolved by keeping both
  sides; full `tsc`/test/build verification re-run after each resolution before merging.
- **The world map (3.4) needs a production CSP update that isn't part of either repo.** Plotly's
  choropleth fetches its world-shapes topojson from `cdn.plot.ly` at runtime; the production site's
  CSP (`connect-src 'self' https://cloudflareinsights.com`) doesn't allow that host, so the map
  silently fails to render in production despite working correctly in local dev/build. Confirmed
  via a live Playwright check post-deploy (`PAGEERROR` fetching the topojson, 0 country shapes
  drawn vs. 220 locally). Needs `https://cdn.plot.ly` added to `connect-src` wherever that CSP is
  set (Cloudflare Transform Rules for the zone, not in either git repo) — flagged for the user to
  action; not a code defect in this release.

Corrections found verifying the original draft against live code before finalizing the plan:
`total_ghg` doesn't exist in `ghg_features.csv` (only in raw `owid-co2-data.csv`/`ghg_filtered.csv`)
— moot since Total GHG is deferred out of this release entirely; the claim that app-side work
"can't land until `design-system` is published and version-bumped" is false — `vite.config.ts`
aliases straight to `../../design-system/src`, not an npm dependency, so a `design-system` PR only
needs to merge; the Scenario Comparison treemap needs no new endpoint (`/scenarios/cumulative`
already returns every country's cumulative totals unconditionally) — only the new three-panel
comparison view needs a new endpoint.

Decisions made before implementation: Forecast Summary always shows all 40 countries (no new
toggle); Historical Trends' GHG Composition chart matches the line chart's own empty-selection
warning rather than falling back to an all-40 aggregate; Total GHG (CO₂e) is deferred, not part of
this release.

### 3.1 — Fix Forecast Summary silently stuck at 10 countries

`api/client.ts`'s `forecastSummary()` took no arguments despite `/forecasts/summary` already
supporting `scope=featured|expanded` server-side. `ForecastsPage.tsx` now calls
`api.forecastSummary('expanded')` — always all 40.

### 3.2 — Scenario Comparison: treemap + multi-country 3-panel comparison

Replaces the ungated 40-country grouped bar chart. Treemap (unfiltered, always all ~40; tile size
= cumulative BAU 2025–2040, color = % reduction under Aggressive vs. BAU, sequential green scale)
sits above a `MultiSelect` country picker (same pattern as Overview/Historical Trends), which
drives three side-by-side per-scenario panels (BAU/Moderate/Aggressive), each plotting all
selected countries with an identical, jointly-computed y-axis range and one shared legend. New
`GET /scenarios/compare` endpoint for the per-country breakdown; the treemap reuses the existing
`/scenarios/cumulative` response as-is.

### 3.3 — Total GHG (deferred)

Not part of this release — flagged during planning that `total_ghg` isn't in `ghg_features.csv`
and would need either a Week 2 notebook change or an API-side re-derivation from raw data if
picked up later.

### 3.4 — World map choropleth on Overview

New choropleth at the top of the Overview page (above the tier table) — the "All Countries" tier's
first chart of its own. Log-scaled color axis (linear would wash out every mid-tier emitter
against China/US), sequential light→amber→deep-red scale, CO₂-only (no metric toggle, since 3.3 is
deferred). `iso_code` added to `load_raw_sovereign()`'s columns for the map's country-boundary
join — real ISO-3 codes already present in the raw data, no fuzzy matching needed.

### 3.5 — Standardize increase/decrease color semantics

Green = decrease/good, crimson = increase/bad, applied consistently everywhere. Required a
`design-system` fix first: `KpiStat`'s `deltaDirection` only supported `up`/`down` (colored by
numeric sign, not outcome) — Overview's Fastest Growth/Largest Reduction cards were wired
backwards as a result (an emissions *increase* rendered green). `KpiStat` gains `good`/`bad`,
mapped directly to sentiment colors regardless of sign. `POSITIVE_COLOR`/`NEGATIVE_COLOR` promoted
from `OverviewPage.tsx`-local to shared `constants.ts`; Country Profile's YoY chart's ad hoc
red/blue pair replaced with the shared colors.

### 3.6 — Suppress "Invalid Number" in Data Explorer's Summary Statistics

AG Grid infers one type per column from all its values; the transposed Summary Statistics table
mixes categorical (`top`/`unique`/`freq`) and numeric (`mean`/`std`) rows in the same column, which
its inference doesn't expect. Fixed with `cellDataType: 'text'` on `summaryColumns` specifically —
the main Dataset Preview table's columns are genuinely homogeneous and keep normal inference.

### 3.7 — Remove redundant country-list caption

Overview showed the same country names twice (MultiSelect chips + a pipe-separated caption line
immediately below). Caption removed.

### 3.8 — MultiSelect clear-all/remove-× visual collision

Real root cause (found auditing `MultiSelect.tsx` directly rather than assuming from the app-side
symptom): the component already has a correctly `aria-label`ed clear-all button, separate from
each tag's own remove-×, but with no visual separation between them in the always-visible control
row. Fixed at the component level with a small gap/divider — benefits every `MultiSelect` consumer,
not just this app. The icon-swap half of the original proposal (a distinct "x-circle" icon) was
skipped — no such icon exists in `design-system`'s `Icon` component today, and adding one just for
this was disproportionate to the fix.

### 3.9 — GHG Composition chart should follow the Historical Trends selection

`/historical/decade-composition` took no country parameter, always aggregating over the full
expanded set regardless of the page's own country picker. Now accepts the same `countries` param
`/historical/timeseries` already does; empty selection shows the same "select at least one
country" warning as the line chart above it (not an independent all-40 fallback).

### 3.10 — Tone down the forecast confidence interval band

By 2040 the 95% CI band had widened enough to visually dominate the chart. Fixed with a new
`SyChart` `fillOpacity` prop (defaults to today's `0.25` for every other consumer), set lower for
this one chart, rather than a dashed-outline treatment or an explanatory caption.

### 3.11 — Sidebar navigation grouping: Exploration / Projection

Required a `design-system` fix first: `SidebarNav` had no concept of labeled sections, just one
flat `items` list. Added an additive `groups` prop (existing `items` consumers unaffected). App
groups: Exploration (Overview, Historical Trends, Country Profile, Data Explorer), Projection
(Forecasts, Scenario Comparison); About stays in the existing `footerItems` slot rather than a
third grouping mechanism.

### 3.12 — "Catchy" visual/UX polish pass

Three changes: animated count-up on Overview's KPI numbers (`useCountUp` hook, no `design-system`
change needed — `KpiStat.value` already accepts any `ReactNode`); at least one chart annotation
(2020 "Global lockdowns" marker on Historical Trends, using `SyChart`'s new `annotations` prop);
category-based chart palette (Forecasts/Scenario Comparison get an amber/violet hue distinct from
the rest of the app's teal, via a `data-chart-category` CSS-scoping wrapper — zero `SyChart`
changes needed, since its categorical palette already resolves through CSS custom properties
against the chart's own DOM ancestry).

### 3.13 — Rollout sequencing

`design-system` phases (KpiStat, MultiSelect, SidebarNav, SyChart) each land as their own PR first;
app-side phases that depend on one proceed only after that PR merges (no publish/version-bump step
— `climate-dashboard-react` aliases straight to `design-system/src`). Independent low-risk fixes
(3.6, 3.7, 3.10) and the scope-param wiring (3.1, 3.9) need no `design-system` change and can
proceed immediately. 3.5 needs `KpiStat`'s fix; 3.11 needs `SidebarNav`'s; 3.2 and 3.4 both need
`SyChart`'s. 3.12 sequenced last (3.12.3 needs 3.5's shared color constants as its source of
truth).

## Release 3.1 — Post-Release-3 Layout, Map, and Contrast Fixes

**Status: Shipped.** React-only (Streamlit/`app.py` untouched). One `design-system` PR and two
app-side PRs merged to `main` in both repos and deployed.

**Implementation-time findings:**
- The plan assumed `DEFAULT_CONTINUOUS_SCALE` was already exported from `SyChart.tsx` for the
  treemap's recolor to reuse directly — checking the actual source found it's a private
  module-level constant, not exported. Rather than adding a `design-system` export for a single
  three-stop scale, the treemap simply omits `colorScale` entirely (`SyChart`'s own choropleth/
  treemap/bar branches all already fall back to this same default when the prop is undefined) —
  zero `design-system` change needed, simpler than the plan's assumption.
- Copilot's coding-agent mode again pushed a fix commit directly to a PR (`940ccb9` on the Overview
  layout PR): removed a now-stale `extends Record<string, unknown>` from `TierRow` (a leftover
  constraint from the old `Table<TierRow>` usage, dead now that `TierSummaryPanel` has no such
  generic requirement), and tightened two `getAllByText(...).length > 0` test assertions to exact
  `toHaveLength` counts. Both verified correct against the actual component structure before
  trusting them.
- Verified live in production (Playwright, both desktop and mobile viewports) post-deploy: the map
  hover now shows real MtCO₂ values, the colorbar sits below the map at both sizes, the Overview
  KPI panel sits alongside the map in one row, and the Scenario Comparison treemap shows a genuine
  red/green split per scenario (confirmed China green / most of Asia-Pacific red under Aggressive)
  rather than the all-green result the old formula was structurally stuck with.

A follow-up review — code-level
plus a live pass against `labs.syena.io/ghg-emissions-analysis` at desktop and mobile viewports —
found three problems left over from Release 3: the Overview map+tier-table layout runs too tall
(pushing the country selector and bar chart below the fold), the world map choropleth has two real
bugs (hover shows the log10-transformed value instead of the real MtCO₂ figure; the colorbar is
visibly taller than the map, worse on mobile), and Scenario Comparison's treemap always reads as
"everything green" because its color formula only ever compares against Aggressive on a green-only
scale with no red stop. Every claim below was re-verified directly against current source (not
just the write-up) before planning began.

Scope split: only the hover/colorbar fix needs a `design-system` change (both live in the same
`SyChart.tsx` choropleth branch, bundled into one PR). The layout redesign, the treemap redesign,
the palette contrast fix, and dropping the now-redundant grouped bar chart are all app-side only —
no new `design-system` capability needed.

Decision made before implementation: the original 40-country grouped bar chart on Scenario
Comparison (superseded by the treemap + 3-panel view, its only remaining unique value being the
`DataTable`'s precise-number lookup) is dropped; the `DataTable` stays standalone.

### 3.1.1 — Overview: 2/3 map + 1/3 KPI summary layout

Today's choropleth and tier table stack as two separate full-width blocks, pushing the selector and
bar chart below the fold with nothing signaling more content follows. Restructured into one grid
row — map ~66% width, a new `TierSummaryPanel` (three stacked mini cards, one per tier, replacing
`TierTable`'s 4-column layout) ~33% width — collapsing to a single column on mobile. This is a
deliberate hierarchy shift (map-as-hero, selection-as-secondary), not just a reflow.

### 3.1.2 — World map: hover tooltip shows the wrong value entirely

`SyChart.tsx`'s choropleth branch log10-transforms `colorValues` into `z` when `zLog` is set, but
never set `hovertemplate`/`customdata` — Plotly's default hover fell back to raw `z`, showing the
log10 number instead of the real value. Fixed with `customdata` (untransformed) plus an explicit
`hovertemplate`, and a new `hoverUnit` prop (e.g. `"MtCO₂"`).

### 3.1.3 — World map: colorbar taller than the map itself

The resize `ResizeObserver` only ever adjusted `layout.height`, never the colorbar's own sizing.
The `natural earth` projection aspect-fits within its domain box (letterboxed at some widths); the
colorbar isn't projection-constrained, so it spans the full box regardless — worse at narrower
(mobile) widths. Fixed by moving the colorbar to a horizontal orientation below the map rather than
tuning a second heuristic to compensate.

### 3.1.4 — Scenario Comparison: treemap redesigned to a scenario-selectable up/down indicator

The treemap's color was always `(BAU − Aggressive) / BAU`, rendered on a green-only scale —
structurally incapable of showing red. Redesigned to a BAU/Moderate/Aggressive radio (reusing the
same set driving the 3-panel view) coloring each tile by whether the selected scenario's 2040 level
is above or below the country's current level — green = down, red = up, using the same diverging
scale standardized everywhere else on the site. Required extending `GET /scenarios/cumulative`
(`ScenarioCumulativeRow` gains `year_2040`/`current_level`) since the existing response only ever
returned a 2025–2040 sum, no single-year or baseline value.

### 3.1.5 — Scenario Comparison: "projection" category palette contrast fix

The `projection` category's chart palette (from Release 3's 3.12.3) is two narrow hue families —
5 ambers, 4 violets — tight enough in hue and lightness that two of the same family become hard to
distinguish at up to 10 selected countries. Widened perceptual separation within `styles.css`'s
palette definition; CSS-only, no `SyChart` change.

### 3.1.6 — Drop the redundant grouped bar chart

The original 40-country grouped bar chart + sort-by radios, the finding that originally motivated
building the treemap/3-panel views, was still on the page below them. Removed; the `DataTable`
underneath stays standalone for precise-number lookups.

### 3.1.7 — Rollout sequencing

One `design-system` PR (3.1.2 + 3.1.3, both in `SyChart.tsx`'s choropleth branch) lands first;
both app-side PRs (3.1.1; 3.1.4+3.1.5+3.1.6 bundled since they share `ScenarioComparisonPage.tsx`)
follow, sequenced after it per established convention though neither has a real code dependency on
it.

### 3.1.8 — Post-ship follow-up: KPI panel iteration, two real chart bugs, treemap hover

More user feedback after 3.1.1–3.1.7 shipped and were checked live, in small individually-merged
PRs rather than a second planned phase (mirroring how the original map-sizing fix after Release 3
was handled) — no new `ENHANCEMENTS.md` section per PR, consolidated here instead once everything
settled.

**KPI panel — iterated three times before landing.** First pass bumped the tier title
(`label2`→`label1`) and metric values (`body3-short`→`body2`, manual `fontWeight: 600`), plus added
one icon (`grid`/`document`/`check`) per tier next to its label. Feedback that it still read small
on desktop led to a second pass: title bumped again to `headline5`, values switched to `headline4`
(a real bold headline size, dropping the manual `fontWeight` override since headlines are already
weight 600 natively). A third pass moved the icon from beside the tier label to the right side of
the header row — aligned above the metric values' own right-aligned column below it — and recolored
it from the same muted `--__s9cmpx-static-text-weak` as the label text to
`--__s9cmpx-interactive-fill-link-default` (the existing blue accent already used for links/"Reset
to default"/sidebar active state), so it reads as a distinct decorative element instead of blending
into the label.

**Site-wide font-size bumps, two rounds.** The intro paragraph below each page's headline
(Overview/Forecasts/Scenario Comparison/Data Explorer) went `body3-short`→`body2`→`body1` across two
feedback rounds. `MultiSelect`'s "Select countries..." label and the "Reset to default" button
(Overview/Historical Trends/Scenario Comparison) also read a size larger: a scoped
`.country-picker-row` CSS override for `MultiSelect`'s own hardcoded `label3` class (not a global
override — `label3` is shared by every other `MultiSelect`/`Select` consumer in `design-system`),
and the `Button`'s `size="s"` dropped to its `m` default. Scenario Comparison's own treemap caption
("Tile size is...") went `body4`→`body3-short`→`body2` across the same two rounds.

**Real bug: mobile chart legend rendering as a bare scrollbar over the plot.** Reported as an
unexplained gray bar cutting across Historical Trends' and Scenario Comparison's line charts on
mobile. Root cause, confirmed via direct DOM inspection (`rect.scrollbar`'s `height` attribute):
Plotly reserves only a fixed share of a chart's own `height` for its legend regardless of how many
rows the legend wraps to on a narrow container; once wrapped content exceeds that share, the legend
becomes internally scrollable rather than growing, and with no `bgcolor` set, the scrollbar thumb
rendered as an unstyled gray bar directly over the chart data. Fixed in `SyChart.tsx` by reusing the
same `ResizeObserver`+`Plotly.relayout` pattern already established for choropleth resizing: for
`showLegend` charts with more than 3 series, estimate wrapped rows from the observed container
width and grow `height` to fit them. Wide/desktop containers that already fit the legend in one row
compute 1 row and get no change — verified no visible difference on desktop.

**Real bug: diverging colorscale auto-ranging away from a true zero midpoint.** Reported as "BAU
showing more green than Aggressive on the treemap, backwards from expected." Plotly scales a
continuous colorscale to the actual min/max of the values array, not to a fixed zero-centered
range — with the default green/lightgrey/crimson scale (no `colorScale` override), that silently
breaks the "below/above a reference point" convention whenever the data is skewed: under BAU,
China's outsized rise dragged the auto-computed "crimson" end so far out that every merely-modest
riser landed near the "green" end of that skewed range; under Aggressive (where nearly every
country actually declines), the *least*-declining country became the array's own numeric maximum
and was colored crimson despite still being a decline. Confirmed against the real API data before
fixing: BAU is actually 35 of 40 countries rising and only 5 declining, the inverse of what the
unfixed chart displayed. Fixed by pinning `marker.cmid: 0` in `SyChart.tsx`'s `bar`/`treemap`
branches whenever the default (uncustomized) colorscale is used, so lightgrey always represents "no
change" regardless of skew; left alone for a custom `colorScale` (e.g. the world map's one-sided
magnitude scale), which may have no meaningful zero crossing at all.

**Treemap hover now shows both the size and color metrics.** Plotly's default treemap hover only
ever showed the tile's label and its size (`values` — cumulative BAU total) — it silently dropped
whatever `colorValues` encoded, even though that's exactly the number a viewer wants after reading
the color legend (the actual scenario-vs-current delta). Added an explicit `hovertemplate` carrying
`colorValues` through as `customdata`, labeled via a new `valueLabel` prop (for the size metric) and
the existing `colorbarTitle` (for the color metric, reused rather than adding a second title prop
for the same concept). Discovered along the way: Plotly's hovertemplate silently drops the `+` sign
flag on `customdata` (`%{customdata:+,.0f}` prints an unformatted raw float instead of a signed
integer) — worked around by pre-formatting the sign in JS before handing values to Plotly, rather
than relying on its own number formatting for that one case.

---

## Release 4 — Regression Target Leakage & Sovereignty Filter Fixes

**Status: Shipped.** Notebook + `api`/`app.py` only — no `design-system` or
`climate-dashboard-react` change. This is a **curriculum correction** (Weeks 1 and 3 of the
internship notebooks), not a post-internship addendum item like Releases 2.x/3.x — tracked in
`SPEC.md` §6.1, a new top-level section distinct from §5's addendum for exactly that reason.

**Shipped:** #98 (Week 1 sovereignty filter), #99 (Week 3 regression target leakage), #100
(`api`/`app.py` sovereignty filter) — all merged, all reviewed clean by Copilot with no
findings. Deployed to the Mac Mini: `uvicorn` restarted for the `api` change and verified live
(`countries_count: 218` on the Overview "All Countries" tier at
`labs.syena.io/ghg-emissions-analysis`); the two notebook PRs required first discarding
uncommitted re-execution diffs on the Mac Mini's checkout (left over from the weekly
`ghg-data-refresh` job, which never commits its own output) before a clean fast-forward merge,
then an on-demand refresh run to verify end-to-end in that job's exact environment — logged
`clean`, no hard-fail or soft-flag on the 220→218 country-count shift.

Found by comparing this repo's Week 1/3 notebooks against a separate intern's independent
implementation of the same curriculum (`Maulik-17/climate-ghg-trend-analysis`). Two of that
project's design choices are genuinely more correct than this repo's current implementation —
both verified directly against this repo's own code and real data before being adopted, not
taken on the other project's word.

### 4.1 — Regression target leakage (`week3_regression.ipynb`)

`FEATURES` includes `co2_yoy_pct_change` (`groupby('country')['co2'].pct_change() * 100`,
computed same-row), while `TARGET = 'co2'` was that same row's value, unshifted. Confirmed
algebraically: `co2_yoy_pct_change` and `co2_lag1` together determine `co2` exactly
(`co2 = co2_lag1 * (1 + co2_yoy_pct_change/100)`) — a same-row feature deterministically
reconstructs the target. Present in every version of this notebook's git history.

Fixed by introducing `REGRESSION_TARGET = 'target_co2_next'` (`co2` shifted forward one year per
country) in `notebook/constants.py`, **alongside**, not replacing, the existing `TARGET = 'co2'`
— `week4_ets_forecasting.ipynb` also imports `TARGET` for genuinely same-year ETS evaluation, and
repurposing the shared symbol would have silently broken it. `FEATURES` itself is unchanged;
under the new framing `co2_yoy_pct_change` becomes a legitimate "known as of year Y" input to a
Y+1 target rather than a leak.

Downstream effects handled: each country's most recent year loses its row (no next-year actual to
shift into, in both the standard `train`/`test` split and §3.6's extended `_train_ext` window);
the naive baseline (§3.3) and Linear Regression (§3.4) actual-vs-predicted plots needed a
year-offset fix so predictions plot at the year they're actually about (`year + 1`), not the
feature row's year; §3.7's MAE/RMSE now measure a genuinely harder "predict next year" task, not
directly comparable to the pre-fix table.

§3.8's recursive forecaster required the most restructuring: it assumed "features describing
year `yr`" predict "year `yr`" (old framing); under the new framing a call describes "known year
`yr`" and predicts `yr+1`, so the loop was rewritten around a `current_year` pointer advancing one
step at a time. Along the way, found that `build_forecast_features` had already been silently
approximating around this exact leak — it couldn't use the real same-row `co2_yoy_pct_change`
definition when generating a forecast year (the target wasn't known yet), so it used the *prior*
period's change instead, one year stale relative to what training used; and separately, its
5-year rolling mean excluded the year `yr` itself, an off-by-one relative to Week 2's actual
`rolling(5).mean()` definition (inclusive of the current row). Both were forced approximations
under the old framing and become exact once the target reframe removes the circularity: under
the new framing, `history[yr]` is genuinely known when predicting `yr+1`, so both calculations
now use it directly.

### 4.2 — Sovereignty filter gap, three hand-synced copies (`notebook/constants.py`, `api/constants.py`, `app.py`)

`NON_SOVEREIGN` (a hand-maintained exclusion list for OWID aggregate rows — World, continents, EU
groupings, income tiers, etc., mirrored verbatim across all three files) never wrongly excludes a
real country, but is missing two null-`iso_code` entities: `Kosovo` and bare `Ryukyu Islands`
(only `"Ryukyu Islands (GCP)"` is listed). Confirmed empirically against the raw CSV:

```
old filter (~country.isin(NON_SOVEREIGN)): 220 countries, 7700 rows (year>=1990)
new filter (iso_code.notna()):             218 countries, 7630 rows
difference: exactly {Kosovo, Ryukyu Islands}
```

Neither is material (Kosovo's max annual `co2` is 8.8 Mt, far under the 100 Mt materiality floor;
Ryukyu Islands has no `co2` data at all) and neither is in the current
`data/selected_countries.json` expanded set (40 countries) — the fix leaves `EXPANDED_COUNTRIES`
unchanged, verified by re-running Week 1 and diffing against the pre-fix committed file.

Fixed in `week1_eda.ipynb` by switching the operative filter to `df_raw['iso_code'].notna()`.
`NON_SOVEREIGN` itself is kept, unchanged, as a reviewable audit record rather than deleted — a
runtime drift-check (mirroring the existing `selected_countries.json` added/dropped pattern) logs
any divergence between the two filters, so a future OWID refresh introducing a new null-`iso_code`
aggregate doesn't silently slip through unnoticed.

### 4.3 — Same fix applied to `api/data_loaders.py` and `app.py`

`api/data_loaders.py`'s `load_raw_sovereign()` and `app.py`'s `load_raw_sovereign()` each do their
own independent `NON_SOVEREIGN`-based filtering straight off the raw CSV (for the Overview "All
Countries" tier and the world map) — the identical gap exists in both, entirely independent of the
notebook fix above since neither reads Week 1's output CSV. `api/data_loaders.py`'s version
already loaded `iso_code` for the choropleth, and its own docstring already named this exact gap
as a map-rendering footnote ("Plotly simply omits [Kosovo/Ryukyu Islands] from the map, no
crash") — it just never extended that awareness to the tier's own country-count/totals. `app.py`'s
version didn't load `iso_code` at all yet. Both switched to the same `df_r["iso_code"].notna()`
filter for consistency across all three now-fixed copies. `api/tests/conftest.py`'s fixture
already gives the `"World"` aggregate row `iso_code=None`, so `test_overview.py`'s existing
assertions hold unchanged under the new filter.

### 4.4 — Rollout sequencing

Three independent PRs, one feature branch each per this project's Claude-authored-notebook-work
convention: `feature/6.1-sovereignty-filter` (Week 1) → `feature/6.1-regression-target-leakage`
(Week 3, sequenced after) → `feature/6.1-api-sovereignty-filter` (`api`/`app.py`, independent
files, sequenced last per convention). The `api`/`app.py` PR needs the standard Mac Mini
deploy-after-merge (uvicorn restart only — `climate-dashboard-react` untouched). The two notebook
PRs need a different kind of Mac Mini sync: the weekly `ghg-data-refresh` job re-executes these
same two notebooks in place on the Mac Mini every Sunday without committing the output, so that
checkout's working tree for these files is routinely dirty at merge time — handled by checking
`git status` there and resetting the regenerated-output diffs before `git fetch && git merge
--ff-only`, then triggering an on-demand refresh run to verify end-to-end in the exact environment
the weekly job uses.

---

## Release 5 — Tablet/Mobile Interaction, PWA, and Accessibility Fixes

**Status: Shipped.** `climate-dashboard-react` + `design-system` only — no Streamlit/`app.py`,
no `api/` change. Tracked in `SPEC.md` §5.10.

Sources: four interaction issues reported from real iPad/iPhone use, plus a full accessibility/
PWA/mobile audit against shipped source (both repos at `c23f74b`), then verified live against
`labs.syena.io/ghg-emissions-analysis` via DOM/Plotly-state inspection (an `axe-core` scan wasn't
possible — the production CSP blocks external scripts — so checks were written directly against
the DOM: target size, accessible names, heading order, landmarks, SPA-navigation behavior; not a
substitute for a full automated ruleset).

**Independently re-verified before planning** (two parallel investigations, one per repo, plus a
direct contrast-ratio computation) — confirmed the great majority of findings exactly, and
corrected four things worth flagging since they change scope or sequencing:
- `SidebarNav.tsx:136` already does `href={item.href ?? '#'}` — the component supports a real
  `href` per item. The actual bug is `climate-dashboard-react/src/App.tsx`'s `toItem` mapper
  (`:29-32`), which destructures out `path` and never carries it into the item it builds. Pure
  app-side fix, no `design-system` PR needed for this item.
- Only one treemap caller exists (`ScenarioComparisonPage.tsx:99`), not two.
- The originally-suggested ~1200px breakpoint wouldn't fix the reported case — iPad landscape is
  1366px wide, so 1200px leaves it exactly as broken as today. 1400px is what actually covers
  both reported orientations (portrait 1024, landscape 1366).
- `height={420}` dead code confirmed real at `OverviewPage.tsx:125` specifically (not just a
  Storybook artifact) — `SyChart`'s choropleth `ResizeObserver` (`SyChart.tsx:448-453`) overwrites
  it via `Plotly.relayout` on first `observe()`, using only container width
  (`Math.max(220, width / CHOROPLETH_ASPECT_RATIO)`), never height.

### 5.1 — Treemap tap-to-drill with no way back

Tapping a tile triggers Plotly's default click-to-zoom (`level` changes to the tapped tile's id);
since `pathbar` isn't configured and `parents` is always `''` (a flat, non-hierarchical 40-tile
treemap — confirmed safe to cancel, there's nothing to legitimately drill into), there is no
breadcrumb and no second-tap return to root. Touch also never produces the hover the existing
(already-correct, both-metrics) tooltip is bound to, so a tap both fails to show info and traps
the view. Fixed in `SyChart.tsx` with a `plotly_treemapclick` handler that returns `false` to
cancel the default zoom, plus a new `onTileClick?: (index: number, label: string) => void` prop.
`ScenarioComparisonPage.tsx` wires this to a small detail area beneath the treemap showing the
tapped tile's size + color values — the touch-equivalent surface for the same information the
hover already carries, not new information.

### 5.2 — World map pinch/scroll-zoom with no reset

Confirmed live: `scrollZoom` is never set (Plotly's own default — zoom enabled — applies to the
geo subplot), while `displayModeBar: false` removes the only built-in "Reset axes" control, for
every chart kind. Fixed with a small internal "Reset view" control, rendered only for
`kind === 'choropleth'`, calling `Plotly.relayout(el, { 'geo.projection.scale': 1, 'geo.center':
... })` — self-contained, no new prop, no change to the desktop-styled modebar. `geo.dragmode:
false` on `matchMedia('(pointer: coarse)')` devices (so panning only happens via explicit
controls, never competing with page scroll) is treated as a follow-up to prototype and evaluate
hands-on post-ship, not committed blind — it trades away real interactivity.

### 5.3 — iPad: tiny map, dead space below it

Three compounding, independently-confirmed causes: `OverviewPage`'s hero grid uses
`alignItems: 'stretch'` (map card forced to match the taller `TierSummaryPanel` — both measured
at exactly 540px); the choropleth's resize logic sizes purely from container width, never height
(measured: 231px of dead space inside that 540px card); and the only breakpoint (900px) doesn't
trip at either reported iPad width (portrait 1024, landscape 1366). Fixed by raising the
breakpoint to 1400px and removing the `height={420}` dead prop from the choropleth call.
`alignItems: 'stretch'` is left as-is above the new breakpoint — that's genuine desktop width,
not the reported problem.

### 5.4 — iOS PWA installability + stale copy

`index.html` gains `apple-mobile-web-app-capable`/`-status-bar-style`/`-title` meta tags (iOS
Safari ignores the manifest's `display: standalone` and keys off these instead — the actual fix
for "Add to Home Screen" opening a normal browser tab) and `viewport-fit=cover`; the app shell
gains `env(safe-area-inset-*)` padding, sequenced after the standalone fix since it's irrelevant
in a plain browser tab. Both `index.html`'s meta description and `vite.config.ts`'s PWA manifest
description are reworded off the stale "for 10 major countries" copy (real count: ~40, confirmed
against `data/selected_countries.json`) to not hardcode a count at all — this is the second
review to catch the same drift.

### 5.5 — Accessibility fixes

`design-system`: `MultiSelect`/`Tag`'s per-country remove button padded from 20×20 to ≥24px
(ideally ≥44px) without changing the rendered icon size, closing a real WCAG 2.2 target-size gap;
`KpiStat` gains a cheap non-color cue for `'good'`/`'bad'` values (borderline against WCAG 1.4.1,
partially mitigated already by the existing +/− sign).

App-side: `useCountUp` gains a `prefers-reduced-motion` check (skips straight to the final value
— the same media query `SidebarNav.tsx:156` already uses in this codebase, for a different
purpose); `CountUpText` gets `aria-hidden` on the animating text plus a visually-hidden span
exposing the final value; `App.tsx`'s `toItem` maps `path` into `href` (closes the sidebar-nav-
href finding entirely app-side); route changes get a per-route `document.title` and focus moved
to the new page's `<h1>`; a skip-to-main-content link is added (confirmed genuinely absent — an
earlier automated check's "skip link" finding was a false positive matching the seven `href="#"`
nav items instead); and all 5 pages using `ChartCard` (`OverviewPage`, `HistoricalTrendsPage`,
`CountryProfilePage`, `ForecastsPage`, `ScenarioComparisonPage`) get an explicit `headingLevel` at
every call site, fixing the confirmed `H1→H5→H5→H2→H5` order (systemic, not just Overview — every
`ChartCard` defaults to `h5` with no caller overriding it).

### 5.6 — Polish

`Icon` gains `expand`/`collapse` glyphs (naming consistent with the existing `chevron-down`/
`chevron-up` pairing). `ScenarioComparisonPage` gets a fullscreen toggle for its charts using
`ChartCard`'s existing `actions` slot (already used for the download button — no `ChartCard`
change needed) and the new glyphs; `SyChart`'s existing `ResizeObserver` + `responsive: true`
should already pick up the container-size change on toggle, with an explicit
`Plotly.Plots.resize()` treated as a safety net to verify empirically rather than assumed
necessary. The divider-token contrast (`#263757` on `#121e35`, computed independently at
**1.40:1**, confirming the audit, vs WCAG 1.4.11's 3:1) is low-priority — only matters where a
divider is a component's sole boundary, and the tier cards already carry a background fill — bump
opportunistically, not worth its own PR.

### 5.7 — Rollout sequencing

Four phases by severity, one feature branch per PR: the two traps (5.1 `design-system` PR, then
5.1's app-side wiring) → iOS/iPad (5.3's app PR, 5.4's app PR, either order) → accessibility
(5.5's two `design-system` PRs first, then its app-side PRs) → polish (5.6, whenever convenient).
`design-system` PRs land before the app-side PRs that consume them within each phase. Standard
Mac Mini deploy-after-merge for every PR (`vitepreview` rebuild+restart only — nothing here
touches `api`/`app.py`), via the now-fixed `sauparnasarkar@Sauparnas-Mac-mini.local` hostname.

### 5.8 — Shipped: PRs, fixes found in review, and deploy verification

Nine PRs merged: `design-system` #17 (5.1/5.2 treemap-click-cancel + choropleth reset-view), #18
(5.5 MultiSelect touch target + KpiStat non-color cue), #19 (5.5 `SidebarNav` click-handler,
carrying a real `href` per item without also double-firing native navigation), #20 (5.6 Icon
expand/collapse glyphs); `climate-dashboard-react` #101 (5.1 `onTileClick` wiring +
tapped-tile detail area), #102 (5.4 PWA meta tags, safe-area insets, stale-copy reword), #103 (5.3
hero-grid breakpoint + dead-prop removal), #104 (5.5 `App.tsx` href/title/focus/skip-link bundled
with `useCountUp` reduced-motion and `CountUpText` ARIA, plus explicit `headingLevel` on every
`ChartCard` site), #105 (5.6 scenario expand/restore control).

Two real regressions were caught and fixed before merge, both in `SidebarNav`'s click handler
(PR #19): the first (self-caught, mid-implementation) was giving every nav item a real `href`
without guarding `preventDefault()`, which would have fired the SPA handler *and* a native
full-page navigation on every plain click; the second (Copilot-caught, same PR) was the fix for
the first unconditionally calling `preventDefault()` even when a consumer had a real `href` and no
`onItemClick`, silently no-oping it. Both verified via genuine click-through testing, not just
code review. Copilot review on PR #101 also caught a `toLocaleString` locale-fragility assumption
in a test (broadened the separator regex); on PR #102, a `minHeight: 100vh` + safe-area padding
box-model bug (fixed with `boxSizing: 'border-box'`); on PR #104, a `useCountUp` test-mock leak
(`window.matchMedia` direct assignment surviving `vi.restoreAllMocks()` — fixed with
`vi.stubGlobal`/`vi.unstubAllGlobals()`, plus a `typeof window.matchMedia === 'function'` guard
added to the hook itself); on PR #105, the expand overlay ignoring safe-area insets under
`position: fixed` (fixed with `calc(16px + env(safe-area-inset-*, 0px))` per side) and a missing
test for the expand/restore control.

Each merge deployed to the Mac Mini (`vitepreview` rebuild + restart, `git fetch && git merge
--ff-only` in both repo directories) and verified live against
`labs.syena.io/ghg-emissions-analysis`, including a service-worker/cache-clear step every time to
rule out a stale bundle before checking: tapping a treemap tile shows the detail area with no
drill-zoom; the world map's "Reset view" control returns to the default projection after a
pinch/scroll zoom; the Overview hero grid stays single-column through both reported iPad widths
(1024 portrait, 1366 landscape) with no dead space below the map; route changes update the tab
title and move focus to the new page's heading; the scenario treemap's expand/restore toggle
renders inside a safe-area-aware fixed overlay at both sizes, with the tapped-tile detail area
still functional expanded.

---

## Release 6 — Generalized Chart Expand/Restore Control

**Status: Shipped.** `climate-dashboard-react` + `design-system` only — no Streamlit/`app.py`,
no `api/` change. Tracked in `SPEC.md` §5.11.

Prompted directly by user feedback after using Release 5's scenario-treemap expand/restore
control live: the same need exists on every other chart that doesn't already fill the page's
full width, and Release 5 built that control by hand, once, inline in
`ScenarioComparisonPage.tsx` — copy-pasting the same ~40-line `position: fixed`
safe-area-overlay block at each new site would be the wrong direction the moment a second real
need for it showed up, which it just did.

### 6.1 — `expandable` on `ChartCard`

`design-system`'s `ChartCard` (`SyChart/ChartCard.tsx`) gains an `expandable?: boolean` prop.
When set, `ChartCard` owns the toggle state itself, renders the expand/collapse button (reusing
Release 5's `Icon` glyphs) in its existing header `actions` slot, and wraps its content in the
same safe-area-aware fixed overlay Release 5 already validated live (`calc(16px +
env(safe-area-inset-*, 0px))` per side) — all internal to the component, no per-page duplication.
`children` is widened to accept `React.ReactNode | ((isExpanded: boolean) => React.ReactNode)` so
a caller that wants a size-reactive chart (taller `SyChart`, not just a bigger empty card) can
pass a function instead of a plain node; existing call sites that don't pass `expandable` are
unaffected.

### 6.2 — Applying it across the app

`ScenarioComparisonPage.tsx`'s treemap `ChartCard` drops its own `treemapExpanded` state and
inline overlay markup in favor of the new `expandable` prop + children-function form — behavior
is unchanged from what Release 5 shipped, just no longer duplicated in app code. The same prop is
then added to five more sites, matching the user's own stated rule ("essentially any chart that
does not occupy the full width of the available screen"): the BAU/Moderate/Aggressive comparison
panels on the same page (300px collapsed / 600px expanded); Country Profile's CO₂ Emissions and
CO₂ per Capita charts, both in its 2-column grid (280px collapsed / 560px expanded; the
already-full-width Year-on-Year chart below them is untouched); and Overview's world map, which
shares a 2fr/1fr hero-grid row with the tier summary panel above 1400px. The map needs no explicit
height prop — its `ResizeObserver` already recomputes height from container width alone (§5.10's
`height={420}` dead-code removal), so widening the container on expand is sufficient — and its own
internal "Reset view" control (§5.1/5.2) coexists without conflict, since it's a different button
in a different location. Historical Trends' two charts and the Forecasts page's ETS/
feature-importance charts are already full-width and are left unchanged.

### 6.3 — Rollout sequencing

One `design-system` PR (the `ChartCard` change) lands first; one app-side PR bundles the treemap
refactor and the five new `expandable` sites, since they're all the same mechanical change applied
at different call sites, not independent features. Standard Mac Mini deploy-after-merge
(`vitepreview` rebuild+restart only — nothing here touches `api`/`app.py`).

### 6.4 — Shipped: a real bug found live, and two rounds of Copilot review

Two PRs merged: `design-system` #21 (the `ChartCard` change) and
`climate-emissions-analysis-project` #106 (the treemap refactor + five new `expandable` sites).

Verifying the change live — clicking Expand on the treemap right after the sidebar-overlap
concern was raised — reproduced a real bug not caught by code review: the expanded overlay's
prior ad-hoc `z-index: 50` sat below the sidebar nav's own vendor-CSS z-index
(`--__s9cmpx-c-sidebar-z-index`, computed to 310 from `--__s9cmpx-z-index-sticky` + 10), so
`position: fixed` escaping the app shell's flex layout meant the overlay's left edge rendered
*behind* the always-visible desktop sidebar instead of over it. Confirmed via
`document.elementFromPoint` at the overlapping pixel, which returned a sidebar `<a>` instead of
the chart. Fixed with `var(--__s9cmpx-z-index-modal)` — this design system's own existing token
tier for a full-content-covering overlay — replacing the old magic number, in the same PR.

Copilot's review of `design-system` PR #21 was a clean pass (no comments), but — confirmed by
direct inspection of the PR's commit history, not assumed — it also pushed a commit directly to
the branch (`copilot-swe-agent[bot]`, "Add modal behavior to expanded ChartCard") adding proper
modal accessibility semantics: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing at
the card's title, a focus trap via the existing shared `useFocusTrap` hook (already used by
`Modal` and `Drawer` — reused, not reinvented), and Escape-to-close. This was reviewed like any
other change before being treated as shipped: confirmed `useFocusTrap` is a real pre-existing
hook (not a hallucinated import), re-ran `tsc -b` and the full test suite (143/143 pass), and
verified live post-deploy that Escape actually closes the expanded overlay and restores the
collapsed view.

Copilot's review of `climate-emissions-analysis-project` PR #106 caught two real issues, both
verified against current code before fixing: a test in `ScenarioComparisonPage.test.tsx` located
the BAU panel's expand button via `.closest('.__s9cmpx-card-header')` — a brittle traversal into
`design-system`'s internal markup — replaced with an index into the ordered list of "Expand
chart" buttons instead; and `CountryProfilePage`'s new expand/restore wiring (height 280↔560) had
no test coverage at all, so a regression there would have gone unnoticed — added a test mirroring
`ScenarioComparisonPage`'s existing pattern. Both fixed, pushed, and re-reviewed clean (`copilot`
check run `conclusion: success`) before merge.

Deployed to the Mac Mini and verified live against `labs.syena.io/ghg-emissions-analysis`
(service-worker/cache-clear step before each check, as established since Release 5): after the
`design-system`-only deploy, the treemap's expand button was confirmed still using its old
Release-5 hand-rolled overlay (expected — the app hadn't switched over yet) and the sidebar-
overlap bug was confirmed still present there, ruling out a false "already fixed" read. After the
app-side deploy, the treemap, all 3 Country Comparison panels, both Country Profile grid charts,
and the Overview world map all expand/restore correctly; `document.elementFromPoint` at the
previously-broken pixel now resolves to the chart, not the sidebar; Escape closes the expanded
view and returns focus; and the world map's own "Reset view" control coexists with the new expand
button without conflict.

### 6.5 — Follow-up: two real bugs found on an actual iPhone, fixed in `design-system` #22

Found by the user on a real device shortly after Release 6 shipped — landscape iPhone
specifically: expanding a chart didn't reliably cover the full visual viewport and the rest of
the chart couldn't be scrolled into view; separately, the treemap's own tapped-tile detail box
(an ordinary in-page element below the treemap, not part of any overlay — the intentional
touch-equivalent-of-hover feature from §5.1) became visible bleeding through the top edge of a
*different* chart's expanded overlay. Both traced to the same root cause: the overlay computed
its box from `top/right/bottom/left: calc(16px + env(safe-area-inset-*))`, which depends on iOS
Safari correctly recomputing four separate viewport-relative distances as its toolbar shows/hides
(a real gap on landscape, where the toolbar eats a much larger share of the available height) —
and it never locked background scroll, so a touch-drag meant for the overlay's own internal
`overflow: auto` region could instead scroll the page underneath.

Two fixes, both in `ChartCard.tsx`: the overlay now uses `inset: 0` (always fills 100% of its
containing block, immune to the four-separate-offsets recalculation issue) with the equivalent
margin applied as `padding` instead; and body scroll is now locked while any `ChartCard` is
expanded, using the `position: fixed` + restore-scroll-offset pattern rather than bare `body {
overflow: hidden }`, which is a known no-op against touch-driven scrolling on iOS Safari
specifically. Copilot's review of this PR caught one real gap in that pattern — the effect only
captured/restored the vertical scroll offset, so a horizontally-panned page (pinch-zoom on mobile
can leave the visual viewport panned even without page overflow) would shift on lock and not be
restored on cleanup — fixed by capturing/restoring `scrollX` too, with a matching negative `left`.
Per the user's request, this PR skipped the automated review-and-merge loop in favor of manual
review. Deployed to the Mac Mini and confirmed fixed on the reporting user's actual iPhone in
landscape — both the partial/unscrollable overlay and the bleed-through are resolved.

## Release 7 — Chart Legibility & Visual Impact

**Status: Planned.** `design-system` only, no app-side code change beyond one decidable follow-up.
Tracked in `SPEC.md` §5.12.

Prompted by the dashboard's charts reading as dull next to a Financial Times dark-theme line
chart used as a reference. A separate Claude session drafted the original proposal (measured the
FT reference pixel-by-pixel and compared it against this repo's actual token values); every claim
in that draft was independently re-verified against current `design-system` source before this
section was written — not taken at face value. That pass confirmed the palette/contrast math
exactly (recomputed from raw hex values: current palette mean 3.83:1 contrast vs. `#1e2f52`,
range 0.193–0.291 relative luminance; FT reference 7.40:1, range 0.167–0.848), confirmed
`SyChart.tsx`'s current rendering defaults exactly as claimed (`line: { width: 1.5 }`,
`mode: 'lines+markers'` with `marker: { size: 5 }`, no `showgrid` on either axis, both
`paper_bgcolor`/`plot_bgcolor` transparent), and confirmed the app-level
`[data-chart-category='projection']` override (`climate-dashboard-react/src/styles.css`) exists
exactly as described.

It also caught one real problem the draft's own review missed: two of the nine proposed
replacement tokens — `-03` "mint" (`#4ee0a8`) and `-09` "rose" (`#ff5c8a`) — sit in the same hue
family as this dashboard's own sentiment-positive (`#3ecf95`, ~1° apart) and sentiment-negative
(`#f36b84`, ~6° apart) tokens. The draft's stated constraint ("keep the categorical ramp
non-semantic... its greens are pale desaturated tints, not signal green") was asserted but never
checked against the real token hex values — on a dashboard whose whole visual language is
green=decrease/good, red=increase/bad, a country line series landing on either token could read as
an accidental sentiment cue. A second, minor inconsistency: the draft's claimed "mean adjacent-pair
luminance gap 0.177 (5.5× today's 0.032)" for the proposed palette doesn't reproduce under any of
the four gap methodologies tried (sequential-order: 0.070, sorted: 0.070, nearest-neighbor: 0.058,
all-pairwise: 0.202) — the *current* palette's 0.032 figure does check out exactly under the
sequential-order method, so this looks like a bookkeeping slip on the proposed side specifically;
it doesn't change the actual outcome (the headline contrast numbers are solid) and isn't carried
into the shipped figures.

### 7.1 — Root cause and the revised palette

Same root cause as §3.1.2/Release 3.1's "projection palette lacks contrast between countries" item
(fixed there by widening *hues* in the app-level override above): the nine
`--__s9cmpx-chart-categorical-default-0N` tokens are highly saturated (mean ~0.74) but occupy a
luminance band only 0.098 wide, so on a dark ground — where perceived prominence tracks luminance,
not saturation — the ramp collapses to a near-uniform mid-grey. Widening *luminance* in the base
theme fixes both the dullness and the distinguishability at once, and likely makes the app-level
override redundant (§7.4).

Revised 9-token ramp (`src/styles/themes/analytics.css`), ordered brightest-first:

`-01` `#ecf0f6` cream · `-02` `#c3e86b` lime · `-03` `#eab8e4` **orchid** (reshaped from the
draft's `#4ee0a8` mint — sentiment-green collision) · `-04` `#ffb454` amber · `-05` `#5ecbf5` cyan
· `-06` `#c89cff` violet · `-07` `#ff8f6b` coral · `-08` `#7aa5ff` sky · `-09` `#ff4ae7`
**magenta** (reshaped from the draft's `#ff5c8a` rose — sentiment-red collision).

The two reshaped tokens sit in a ~308° hue valley — roughly 41° from both sentiment tokens and
every other categorical hue, and distinguishable from each other by lightness/saturation (`-03` a
pale tint, `-09` a fully-saturated mid-tone) rather than hue. Both were placed by matching the
original tokens' luminance targets exactly (0.578 and 0.307 respectively), so the overall
hierarchy is unaffected: mean luminance 0.529 (draft: 0.528), mean contrast 7.31:1 (draft: 7.30:1).

### 7.2 — `SyChart` rendering defaults

Three changes in `SyChart.tsx`, one in `ChartCard.tsx`, all bundled in the same PR as the palette
since they touch the same file/theme:

- **Stroke width**: `line: { width: 1.5 }` → `2.75` (midpoint of the reference-derived 2.5–3px
  range) — highest-impact single-line change after the palette.
- **Markers**: new `showMarkers?: boolean` on `SyChartSeries` (same per-series pattern as the
  existing `dashed` prop), defaulting to `s.x.length < 10` — dense multi-country charts (35 annual
  points × up to 10 countries today puts ~350 dots on top of the strokes) switch to pure strokes;
  sparse charts keep markers unchanged.
- **Vertical gridlines**: `xaxis.showgrid: false` only — `yaxis` is untouched, so horizontal
  gridlines remain (the reference's convention). Safe to set unconditionally since Plotly ignores
  irrelevant cartesian-axis keys for choropleth/treemap traces.
- **Chart-card background** (`ChartCard.tsx`, not `SyChart.tsx`): since `paper_bgcolor`/
  `plot_bgcolor` are transparent, charts inherit whatever's behind them — currently the general
  card surface (`#1e2f52`), one step lighter than the page (`#121e35`), costing contrast for free.
  Traced `.__s9cmpx-card`'s actual background rule and found it already resolves through a
  per-instance CSS custom property (`--__s9cmpx-c-card-background-color-default`, defaulting to
  `var(--__s9cmpx-static-background-standard)`) rather than a hardcoded value — so `ChartCard`
  overrides just that one variable on its own `<Card>`, to `var(--__s9cmpx-static-background-weak)`
  (the page background). No new `Card` prop, no new token, no `Card.tsx` change — a narrower fix
  than the draft's own suggestion of "a `ChartCard` variant, or a token for chart surfaces."

Legend-inside-plot-area and title-hierarchy (tied to the existing §5.10 heading-order fix) are
both deferred as optional, independently larger changes — not part of this release.

### 7.3 — Sequencing

One `design-system` PR carries the full palette + rendering-default change. The app inherits it
with zero code changes but needs a full visual pass across **all seven pages** after the bump —
not just the two chart-heavy ones — since every chart in the app picks up new colors/strokes at
once from a single base-theme change.

### 7.4 — Follow-up: does the projection-palette override become redundant?

`styles.css`'s `[data-chart-category='projection']` override (used by `ScenarioComparisonPage.tsx`
and `ForecastsPage.tsx`) was Release 3.1's fix for the same underlying luminance problem, scoped to
just those two pages by widening hues rather than luminance. Once the base theme's ramp is fixed
at the root, this override may no longer add anything — but that's decided from the actual
rendered result during the required visual pass (§7.3), not assumed; if it's still pulling its
weight, it stays.
