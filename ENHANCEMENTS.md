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

**Status: Shipped.** `design-system` #23 plus one small app-side follow-up, #107. Tracked in
`SPEC.md` §5.12.

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
- **Vertical gridlines**: gridlines now follow the **value** axis, not `xaxis` unconditionally —
  `showgrid: orientation === 'h' ? undefined : false` on both `xaxis` and `yaxis` (mirrored). The
  first version hardcoded `xaxis.showgrid: false`, which Copilot's review of PR #23 caught as
  wrong for `orientation="h"` charts (categories on y, values on x — e.g. Forecasts'
  feature-importance chart): it would have dropped the useful value-axis gridlines and left
  gridlines on the now-useless category axis instead. Verified against the real call site
  (`ForecastsPage.tsx:82` genuinely uses `orientation="h"`) before fixing, not assumed theoretical.
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

One `design-system` PR carried the full palette + rendering-default change (#23). The app inherited
it with zero code changes; a full visual pass across **all seven pages** confirmed no regressions,
since every chart in the app picked up new colors/strokes at once from a single base-theme change.

### 7.4 — Follow-up: the projection-palette override is now redundant

`styles.css`'s `[data-chart-category='projection']` override (used by `ScenarioComparisonPage.tsx`
and `ForecastsPage.tsx`) was Release 3.1's fix for the same underlying luminance problem, scoped to
just those two pages by widening hues rather than luminance. Rather than assume the base theme's
fix made it redundant, this was checked with a live A/B: temporarily disabling the override in the
running deployed app and comparing the Scenario Comparison country-comparison panels side by side.
The base ramp's full hue spread (cream/lime/orchid/amber/cyan/violet/coral/sky/magenta) read at
least as distinct as the override's narrower amber/violet-only family — confirming it no longer
earned its keep. Retired in `climate-emissions-analysis-project` #107 (removes the CSS block and
the `data-chart-category="projection"` wrapper attribute from both pages).

### 7.5 — Shipped

Two PRs merged: `design-system` #23 (palette + `SyChart`/`ChartCard` changes) and
`climate-emissions-analysis-project` #107 (the override retirement above). Copilot's review of
#23 caught the gridline-orientation bug described in §7.2 — fixed, re-reviewed, clean (`copilot`
check run `conclusion: success`) before merge. Copilot's review of #107 was a clean pass with no
comments.

Deploying #23 to the Mac Mini surfaced a real deploy-process bug, unrelated to the code change
itself: `climate-dashboard-react`'s build needs `DEPLOY_BASE_PATH=/ghg-emissions-analysis/` set at
*build* time (it's compiled into the bundle's asset paths), not just at serve time (already set in
the `com.ghgemissions.vitepreview` LaunchAgent's own environment for `vite preview`). A plain
`npm run build` without it produced an `index.html` referencing assets at the wrong path — every
JS/CSS request 404'd and the site loaded blank. Caught via network-request inspection rather than
assumed from a visual check alone, fixed by rebuilding with the env var set. Same fix applied again
for the #107 deploy.

Verified live against `labs.syena.io/ghg-emissions-analysis` across all seven pages, reading actual
Plotly trace/layout state and computed styles rather than eyeballing screenshots: Historical
Trends' multi-country chart confirmed the reshaped `-03`/`-09` tokens, 2.75px strokes, `mode:
'lines'` (no markers) on the 35-point series; Forecasts' feature-importance chart confirmed
`yaxis.showgrid: false` / `xaxis.showgrid` unset (Plotly's default applies) for its
`orientation="h"` trace; `ChartCard` confirmed rendering at `rgb(18, 30, 53)` (`#121e35`, the page
background) via `getComputedStyle`; Overview, Country Profile, Data Explorer, and About all
confirmed unaffected/unregressed.

## Release 8 — Climate Theme Variant (Parked)

**Status: Parked — feature branch only, not merged, not deployed.** Tracked in `SPEC.md` §5.13.

A follow-on to Release 7: repositioning the dashboard's dark theme from generic corporate navy to
a climate-specific identity derived from Pentagram's Zeff brand system — earth-green surfaces, a
seafoam/cooled-cyan accent, and a muted categorical ramp in place of Release 7's neon one.

### 8.1 — Explicit instruction: build and preview before any merge decision

Unlike every prior release, the user asked upfront to see the whole thing running before deciding
whether to keep it — the opposite of this project's usual merge-then-deploy-then-verify-live
sequence. Both repos got a `feature/8.1-climate-analytics-theme` branch, neither ever opened as a
PR: `design-system`'s carries the actual theme (new `climate-analytics.css`, `analytics.css`'s
shared selectors widened to cover it, Storybook wiring); `climate-emissions-analysis-project`'s
just flips `App.tsx`'s `data-theme` and adds the stylesheet import in `main.tsx`. Verified with
`npm run dev` against a local `uvicorn` instance (real data, no deploy) rather than the Mac Mini —
since `climate-dashboard-react` aliases straight to `design-system/src`, having the design-system
branch checked out locally was enough for the running app to reflect it immediately.

### 8.2 — The dark-green derivation

Surfaces/dividers/text/categorical-ramp values were given verbatim by the consumer and
independently re-verified (every relative-luminance/contrast figure recomputed exactly). Two
things the request flagged as needing derivation rather than assumption: `--color-brand-100/200`
(SyChart's gridline/zeroline tokens) and the `.ag-theme-s9cmpx` AG Grid block, both derived by
matching each navy token's own contrast-against-background, hue-rotated to the new surface hue.
Everything else that was navy/cyan-hued got a systematic straight hue rotation, flagged in the CSS
file's own comments as lower-rigor than the individually-verified items. Seafoam-verbatim for
"large fills" (hero panels/selected states/chart bands) was deliberately left unwired — no single
existing token in the theme cleanly represents that role.

### 8.3 — Three variants tried live, none kept

After the dark-green derivation was previewed and approved-in-spirit, the user asked to try a
"light, muted mint... sage or pastel" variant instead. That required a real architectural change,
not just new hex values: a light theme is structurally different from a dark one (dark-on-light
ink, light sentiment washes, etc.), so it was rebuilt as an independent theme layered on the
project's existing light-theme defaults (the same pattern its `green`/`blue` theme variants already
use) rather than as a variant of the dark `analytics` block. Seen running, it read as too light —
the user asked for something between that and the original dark forest-green. A medium-toned sage
iteration followed (surfaces re-luminance-matched to a genuine midpoint, ink direction re-checked
empirically rather than assumed, since a "medium" green still leans light for contrast purposes,
categorical ramp re-derived a third time for the new lightness band).

The medium variant surfaced a real, reproducible problem: `climate-dashboard-react`'s larger
paginated AG Grid tables (Data Explorer's dataset preview, Forecasts' summary table) rendered
blank white in every screenshot, despite `getComputedStyle` confirming correct sage colors and
content on the actual row elements — reproduced in a fresh tab and in a production build (`vite
preview`), ruling out a dev-server/HMR artifact, but not root-caused (smaller, non-paginated AG
Grid tables on the same pages rendered correctly) before the direction was abandoned.

### 8.4 — Outcome

After comparing all three variants live, the decision was to keep none of them and stay on the
existing navy `analytics` theme. Both feature branches were left pushed rather than deleted, as a
record — `design-system`'s was explicitly restored to the original dark forest-green variant's
file contents (not left at the medium-sage state) via a new commit on top, non-destructively,
rather than rewriting branch history. Neither branch has an open PR; nothing was merged or
deployed.

## Release 9 — Scenario Panel Legend Consistency

**Status: Shipped.** `climate-emissions-analysis-project` PR #109. Tracked in `SPEC.md` §5.14.

`ScenarioComparisonPage.tsx`'s three Country Comparison panels (BAU/Moderate/Aggressive) map over
`SCENARIO_PANELS` and set `showLegend={i === 0}` on each `SyChart` call — only the first (BAU)
panel in the array got a static legend rendered. That pushed BAU's y-axis down relative to
Moderate/Aggressive (the legend consumes vertical space the other two don't lose), breaking
horizontal axis alignment across the three-panel row, and read poorly on a narrow/mobile
viewport. All three panels already show the same series breakdown via `hovermode: 'x unified'`
on hover — the static legend was redundant on top of being inconsistent. Fixed by setting
`showLegend={false}` uniformly (dropping the `i` index entirely, since it was only ever used for
this one conditional). Merged, deployed, and verified live: all three panels' y-axes now align at
the same baseline.

## Release 10 — Fixed-Position, Translucent Hover Tooltip

**Status: Shipped.** `design-system` PRs #24, #25, #26. Tracked in `SPEC.md` §5.15. Affects every
cartesian (`line`/`bar`/`band`) `SyChart` instance app-wide, since `hovermode: 'x unified'` is set
once at the layout level, not per page.

### 10.1 — The problem

Plotly's own unified-hover label box is positioned near the topmost active trace's own y-pixel at
the hovered x. Since that value moves as you scan across a series, the box moves vertically with
it, and Plotly also flips it from one side of the cursor to the other as the hover approaches
either edge of the plot (to keep it from overflowing). Confirmed live on Scenario Comparison's
10-series charts (`document.elementFromPoint`-style direct inspection of the rendered hover
layer, not just visual guessing) that this made some rows genuinely hard to reach — you'd have to
re-hover at a different x to see a row the box had scrolled past.

### 10.2 — The fix (PR #24)

Plotly's own hover *detection* (hit-testing, event firing) is left completely intact — it still
drives the vertical spike guideline, which stays visible. Only the label box's own *rendering* is
suppressed: confirmed via live DOM inspection that Plotly renders it as a `.legend`-classed group
inside `.hoverlayer`, distinct from the `.spikeline` groups in the same layer, so a CSS rule
scoped to `.hoverlayer > .legend` (in `overrides.css`, gated behind a
`__s9cmpx-chart-plotly--custom-tooltip` class SyChart only applies for cartesian charts) hides
just the box, not the guideline. A React-rendered `<div>` takes its place: pinned to the chart's
vertical middle (`top: 50%; transform: translateY(-50%)`, so it never moves regardless of where
the hovered trace's value sits), horizontally follows the cursor with edge clamping so it never
overflows the chart's own left/right bounds, and is internally scrollable (`maxHeight` +
`overflowY: auto`) if a series list is ever taller than the chart.

### 10.3 — Copilot caught three real issues on PR #24, all fixed before merge

- **`innerHTML` with interpolated series names/values** — a real HTML-injection risk, since
  `SyChart` is a general-purpose component with no way to guarantee a caller's series `name`s or
  axis categories are pre-sanitized. Rewritten to build the tooltip via `document.createElement`
  and `.textContent` instead of template-string HTML.
- **`pointerEvents: 'none'` directly contradicted the intended `overflowY: 'auto'` scroll
  affordance** — with pointer events disabled, a user literally couldn't scroll a tooltip taller
  than its container. Enabling pointer events surfaced a second problem: the tooltip is a sibling
  element painted on top of the chart, so Plotly's own `plotly_unhover` fires the instant the
  cursor reaches it (Plotly loses the pointer under an overlapping element) — an immediate hide on
  that event lost the race and made the tooltip vanish before a reaching cursor arrived, confirmed
  live before landing on the fix: a short grace-period `setTimeout` before hiding, canceled by
  either a fresh `plotly_hover` or the tooltip's own `onMouseEnter`.
- A comment referencing `ChartCard/SyChart.tsx` when the tooltip actually lives in
  `SyChart/SyChart.tsx` — corrected.

### 10.4 — Follow-up: opacity tuned twice after live verification (PRs #25, #26)

Manual verification of the live deploy found the tooltip's flat `--static-layer-standard`
background fully hid whatever chart lines it happened to sit over. Made translucent via the
existing `withAlpha` helper (already used for band-chart fill opacity) at 0.85 opacity (#25) —
resolved once per mount via `cssVar`, not per hover event, since it doesn't depend on hover data.
Confirmed on the live site that 0.85 still read as effectively opaque; dropped to 0.65 (#26),
confirmed live (zoomed screenshot) that chart lines are now clearly visible through the tooltip
body while every row of text stays legible.

## Release 11 — Final Presentation Link

**Status: Shipped.** `climate-emissions-analysis-project`. Tracked in `SPEC.md` §5.16. No
`design-system` change. Branches: `feature/9.1-about-presentation-embed` (initial iframe design,
merged as PR #110, deployed live) superseded by `fix/9.2-presentation-open-new-tab` (two-link
design — see "Revised" below, merged as PR #111), then `fix/9.3-pwa-navigate-fallback-denylist`,
`fix/9.4-pptx-content-disposition`, and `fix/9.5-navigate-denylist-query-string` (three real bugs
found live post-merge — see below), then `fix/9.6-remove-pptx-download-link` (product decision —
see "Product decision" below), which is the current, shipped design: a single "Open the
presentation" link, deployed and verified live opening Microsoft's viewer in a new tab and
rendering slide 1 of 17 of the actual deck.

Adds a "Final Presentation" section to `AboutPage.tsx` for the internship review Q&A deck,
requested specifically to preserve its original PowerPoint animations/transitions — ruling out a
PDF export or a plain download link, neither of which plays animations. Considered and rejected:
a client-side pptx-rendering library (no mature OSS option reliably replays native PowerPoint
animation timing); Google Slides embed (requires a manual upload/publish step and has less
reliable animation-fidelity conversion from PowerPoint's animation model); a PowerPoint-exported
video (perfect fidelity of whatever was recorded, but fixed-timing rather than click-to-advance,
and needs re-exporting by hand whenever the deck changes).

Landed on embedding via Microsoft's own web viewer (`view.officeapps.live.com`), which needs no
upload/publish step at all — it fetches the file directly from a URL the caller supplies. The
deck is served as a plain static asset:
`climate-dashboard-react/public/GHG_Internship_Review_QA_Deck.pptx`, copied from
`docs/GHG_Internship_Review_Q&A_Deck.pptx` and renamed to drop the `&` (URL-safety, avoiding any
double-encoding surprises across the Vite dev/preview server and the Cloudflare Tunnel). The
embed URL is built at runtime (`window.location.origin` + `import.meta.env.BASE_URL` + filename)
rather than hardcoded, so it resolves correctly whether running locally or under the production
deploy prefix — confirmed the constructed URL is correct in both contexts, though the embed only
actually *renders* on a publicly-reachable URL (Microsoft's servers can't fetch `localhost`, an
expected and accepted limitation of local dev). A plain download/open link sits below the iframe
as a fallback, confirmed to work independently of the iframe (it's a direct `<a href>` to the
static file, unaffected by the CSP gate the iframe is behind).

**Copilot review on PR #110 (all three real, fixed before merge):** both `target="_blank"` links
in the file (the Data Sources URL link, pre-existing, and the new presentation fallback link) were
missing an explicit `rel="noopener"` alongside `rel="noreferrer"` — `noreferrer` alone already
blocks `window.opener` access in all current browsers, so there was no live vulnerability, but the
explicit pairing is the conventional, linter-expected form and costs nothing, so added to both. The
new test hard-coded the expected pptx URL as `${origin}/...` instead of matching the component's
own `${origin}${import.meta.env.BASE_URL}...` construction — fixed to derive it the same way, so
the assertion won't silently pass for the wrong reason if `BASE_URL` ever changes. A code comment
describing the local-dev limitation was corrected — the actual cause is `window.location.origin`
being `localhost`, not `BASE_URL` (which is only the deploy path prefix, unrelated to reachability).

**Revised from an inline `<iframe>` embed to two `target="_blank"` links, before ever flipping this
section to Shipped.** After PR #110 merged and deployed, decided a same-page iframe embed wasn't
the right shape — replaced with two links that open in a new tab instead: one to the Office
viewer URL, one a direct `.pptx` download, both `target="_blank" rel="noopener noreferrer"`. Beyond
being simpler, this **removes the CSP dependency entirely**: a new-tab link is a full top-level
navigation to `view.officeapps.live.com`, governed by no CSP directive that either repo or the
production Cloudflare config need to touch, whereas an iframe embed needs an explicit `frame-src`
allowance for the exact origin being framed. No further Cloudflare change is needed for this
feature specifically (the world map's `cdn.plot.ly` `connect-src` requirement, §5.8, is unrelated
and still applies — that's a real same-page fetch, not an embed).

**Real bug found live after PR #111 shipped: PWA service worker swallowed the download link.**
Clicking "Download the .pptx" opened a new tab that redirected to the Overview page instead of
downloading the file — confirmed via browser automation (checked `location.href` after the click:
still `/about` in the original tab, and the new tab's URL/title were empty, i.e. the browser
treated it as a download rather than a navigable page once fixed). Root cause: `vite-plugin-pwa`'s
generated `sw.js` registers Workbox's default `NavigationRoute` with no
`navigateFallbackDenylist` — `e.registerRoute(new e.NavigationRoute(e.createHandlerBoundToURL
("index.html")))`, confirmed by reading the actual built `sw.js` on the Mac Mini. This intercepts
*every* top-level navigation request (`mode: 'navigate'`), including a plain `<a target="_blank">`
click on a static asset, and serves the SPA shell instead — the route has no way to distinguish an
app client-side route from a real file. `curl` and Microsoft's own server-side fetch (for "Open the
presentation") both worked fine throughout, since neither is a browser navigation the service
worker's `fetch` handler intercepts — only an actual browser link click surfaced this. Fixed in
`vite.config.ts`'s `workbox` config: `navigateFallbackDenylist: [/\.[a-zA-Z0-9]{2,5}$/]`, excluding
any path ending in a file extension (safe here since every one of this app's routes —
`/`, `/historical`, `/country-profile`, `/data-explorer`, `/forecasts`, `/scenarios`, `/about` — is
extensionless). Verified fixed locally with a real service-worker-controlled `vite preview` page
(not just a fresh unregistered load, since a worker only *controls* a page from its second load
onward — confirmed `navigator.serviceWorker.controller` was truthy before testing the click).

**Third real bug, found live immediately after the navigation-fallback fix shipped: the download
rendered as raw binary instead of downloading.** With the redirect fixed, clicking "Download the
.pptx" opened a new tab, but it displayed the file's garbled raw binary content rather than
downloading it — a screenshot from the user's own browser showed the literal `PK` zip-header bytes
and XML fragment names rendered as text (`.pptx` is a zip container; `PK` is the zip magic number).
Root cause: neither `vite dev` nor `vite preview` set a `Content-Type` header for a `public/` file
with an extension they don't recognize (`curl -sI` showed an empty `Content-Type` for `.pptx` in
both modes — flagged as a known gap when this feature first shipped, but judged non-blocking at
the time on the reasoning that "browsers/PowerPoint rely on the extension regardless"; that
reasoning didn't hold for a plain browser tab with no PowerPoint file handler registered, which
falls back to sniffing the response and rendering it as text). `vite preview` is the literal
process the Mac Mini's Cloudflare Tunnel deploy forwards to — no separate reverse proxy or static
host sits in front setting headers — so the fix had to live in `vite.config.ts` itself: a new
`pptxDownloadHeadersPlugin`, a small Connect middleware mirroring the existing
`redirectBareBasePlugin` pattern (applied to both `configureServer` and `configurePreviewServer`
so dev and preview behave identically), setting `Content-Type: application/vnd.openxmlformats-
officedocument.presentationml.presentation` and `Content-Disposition: attachment;
filename="GHG_Internship_Review_QA_Deck.pptx"` for any request ending in `.pptx`. The explicit
`Content-Disposition: attachment` does double duty — it also forces a download regardless of how
any given browser's MIME-sniffing heuristics would otherwise have handled the response, matching
the link's own label ("Download the .pptx") exactly. Confirmed this doesn't affect "Open the
presentation": Microsoft's viewer fetches the same URL server-side, the same way `curl` does, not
as a browser navigation that interprets `Content-Disposition` — only an actual top-level browser
navigation honors that header. Verified fixed locally: `curl -sI` shows both headers on the
response, and a real browser click now triggers an actual file download (new tab opens with an
empty URL/title, the download-then-auto-close pattern) instead of rendering garbled binary.

**Copilot review on PR #113 (one real issue, fixed before merge):** the middleware matches any
`.pptx` request path, but the `Content-Disposition` filename was hardcoded to the one file that
exists today — if a second `.pptx` were ever added to `public/`, it would download under the wrong
suggested name. Fixed to derive it via `path.basename(pathname)` instead; confirmed with a request
to a differently-named `.pptx` path that the header now reflects that file's own name, not the
hardcoded one.

**Fourth real bug, found live while investigating what first looked like the third bug
recurring.** After PR #113 shipped, a user screenshot showed "Download the .pptx" rendering raw
binary again — same symptom as the third bug. Investigated via a page-context `fetch()` with
`cache: 'reload'` (bypasses the browser's own HTTP cache, unlike a plain `fetch()` or a `curl` from
a different process) against the exact URL: confirmed the server was sending the correct headers.
The screenshot was almost certainly this same browser's own stale disk-cache entry for that exact
URL, cached during earlier testing sessions before the header fix shipped — not a live regression,
and not fixable in application code (a returning visitor's own browser cache is outside the app's
control; a first-time visitor would never hit this). But testing this surfaced a fifth, genuinely
new bug: appending any query string to the `.pptx` URL (e.g. a cache-busting param used purely for
testing) resurrected the *third* bug's redirect-to-Overview symptom. Root cause: Workbox's
`NavigationRoute` tests its denylist against the full `pathname + search`, not just `pathname` —
confirmed empirically, not assumed: the existing `\.[a-zA-Z0-9]{2,5}$` pattern stopped matching,
and the SPA fallback fired again, the instant a query string was appended to the same `.pptx` URL
that worked fine without one. Fixed by widening the regex to `/\.[a-zA-Z0-9]{2,5}(\?.*)?$/`,
tolerating an optional trailing query string. Verified with a real service-worker-controlled page
(after forcing `registration.update()` and confirming the new regex was actually active in the
served `sw.js` before testing): navigating a fresh tab directly to a query-stringed `.pptx` URL now
correctly triggers a download (the tab reverts to blank/new-tab state, the same signature confirmed
throughout this section) instead of rendering the Overview page.

**Product decision: removed the direct download link, viewer-only access
(`fix/9.6-remove-pptx-download-link`).** After the two-link design shipped and its bugs were fixed,
decided the deck should only be viewable through Microsoft's online viewer — no direct "Download
the .pptx" affordance. Removed that `<Link>` from `AboutPage.tsx` and its test assertions (now
asserts the link is *absent*, not present), and removed `pptxDownloadHeadersPlugin` from
`vite.config.ts` entirely, since that middleware's `Content-Type`/`Content-Disposition` handling
existed solely to make the download link behave correctly (the second and fourth bugs above) — with
the link gone, so is the reason for the middleware. `presentationUrl` (the raw `.pptx` URL) is
still computed internally, since it's still needed to build the Office viewer's `src`; it's just no
longer rendered as its own link. The file itself is unchanged — still a public static asset that
Microsoft's viewer fetches server-side — this is a UI-level decision, not an access-control one:
anyone who already has or inspects the URL can still reach the file directly, which isn't
meaningfully preventable without a token-gated endpoint, disproportionate for an internship deck.
Kept the `navigateFallbackDenylist` fix (`fix/9.3`/`fix/9.5`) as-is — it's a general robustness fix
for any static asset under `public/`, independent of whether a download link exists for this one.

Two things worth flagging for whoever picks this up next:

- **`.gitignore` gap, fixed narrowly rather than broadly.** The repo's blanket `*.pptx` rule
  (confirmed via its own comment: "Generated artefacts — not part of the intern template", meant
  for the mentor's own working drafts under `docs/`) was silently ignoring the new file under
  `climate-dashboard-react/public/` too — it would have built and run correctly locally (Vite
  just copies whatever physically exists in `public/`) while being completely absent from a fresh
  clone or the Mac Mini's `git pull`-based deploy, a real "works on my machine" trap caught before
  it shipped broken. Fixed with a narrow negation,
  `!climate-dashboard-react/public/*.pptx`, rather than loosening the broad rule or force-adding
  the file, so the reason a `.pptx` is tracked here (and only here) stays self-documenting.
- **No longer blocked on a CSP change** — this was true of the original iframe design (needed a
  `frame-src` allowance for `view.officeapps.live.com`, which was in fact added to the production
  CSP, but with a syntax error: `frame-src 'view.officeapps.live.com'` wraps the hostname in
  single quotes, which CSP reserves for keywords like `'self'`/`'none'`, not host sources, so as
  written that source is invalid and gets dropped — flagged for a fix to
  `frame-src https://view.officeapps.live.com`, which was applied). Moot either way after the
  revision above: new-tab links need no `frame-src` entry at all.

## Release 12 — Animated Choropleth Time-Series

**Status: Shipped.** Tracked in `SPEC.md` §5.17. Three PRs across both repos: `design-system` #28
(`SyChart` `colorRange`/`animationFrame`/no-data trace, `Slider` keyboard nav, new
`useReducedMotion` hook), `climate-emissions-analysis-project` #117 (`GET
/overview/world-map-series`, `OverviewTierMetrics.co2_by_year`), #118 (the Overview page wiring —
`useYearAnimation`, `AnimatedWorldMap`, Play/Pause + year `Slider`). Each reviewed and merged via
the `copilot-review-loop` skill. Not an internship requirement change.

Turns the Overview world map from a static latest-year snapshot into an autoplaying, scrubbable
1990–2024 sequence, synchronized with the KPI/tier numbers so they read the actual totals for
whichever year the map is currently showing — not a decorative 0→final count-up layered on top of
an otherwise-static map.

### The one architectural decision that drove everything else

`SyChart` had no way for a consumer to update its choropleth's colors without a full
`Plotly.react` re-render — which resets any zoom/pan the user has applied (confirmed live:
zooming, then pushing a new `colorValues` array through the `series` prop, loses the zoom; the
same update via a direct `Plotly.restyle` call preserves it exactly). The fix: a new
`animationFrame?: { colorValues: Array<number | null> }` prop on `SyChartProps`, watched by a
second, small `useEffect` — deliberately *not* joined to the big effect that owns `series`,
`height`, and everything else — which calls `Plotly.restyle` directly. Rejected a classic
`forwardRef`/`useImperativeHandle` escape hatch as unnecessary: it would hand every consumer of a
shared component an untyped "call arbitrary Plotly method" surface, where the narrow, prop-driven
`animationFrame` does the same job while keeping `SyChart` purely declarative from the outside.

The consumer-side implication: the choropleth `series` array passed to `SyChart` must be memoized
to the *initial* year only and never change reference for the component's lifetime — every
subsequent frame goes through `animationFrame` instead. Getting this wrong is easy and the symptom
is subtle (the map still animates, just with a full teardown/rebuild per frame and the user's zoom
silently reset each time), so this is called out explicitly in both the prop's own doc comment and
the app-side `AnimatedWorldMap` component.

### `colorRange` — the true blocker

Without a way to pin the color axis across frames, the animation would be actively misleading, not
just unpolished: every year would re-normalize its own min/max, so 1990's largest emitter would
render identically to 2024's, hiding the real growth in magnitude behind constant-looking colors.
`colorRange?: [number, number]` on `SyChartSeries`, applied as `zmin`/`zmax` + `zauto: false`
(choropleth) or `cmin`/`cmax` (treemap/bar) — same units as `colorValues`, i.e. pre-log when `zLog`
is set, so a caller never has to think about log space (the same guarded `Math.log10` transform
`colorValues` itself already gets is applied to both bounds).

### No-data trace

Six countries (the original draft's claim) — later corrected to nine, see below — have no CO₂ data
in some years. Plotly simply doesn't draw a location with a `null` z-value, leaving the map
background showing through, which against this app's dark theme reads as ocean, not "no data." A
second, flat-colored choropleth trace, rendered underneath the primary data trace and restyled on
the same `animationFrame` tick, makes the gap visually unambiguous — confirmed live by zooming into
Namibia (a real early-1990s no-data country) at year 1990 and watching it resolve to real data by
the mid-90s as the animation played.

### API: a new, selection-invariant endpoint

`GET /overview/world-map-series` serves the full 1990–2024 range in a columnar shape
(`values[yearIdx][countryIdx]`) — measured 8.3× smaller (≈62 KB against the real dataset) than a
per-year-list-of-objects shape, and the layout `SyChart`'s `colorRange`/`animationFrame` want
directly, so the frontend does no reshaping. Deliberately not folded into the existing `/overview`
endpoint, which re-fetches on every country-selection change — attaching this payload to that
endpoint would ship it on every one of those re-fetches for no reason. Confirmed live (both
pre-deploy against the real API and post-deploy against production) that it's fetched exactly once
per page load, regardless of how many times the country selection changes.

`OverviewTierMetrics` gained `co2_by_year`, populated for All Countries/Expanded only — Selected is
summed client-side from the same `world-map-series` payload restricted to the current selection,
since re-computing it server-side would mean re-fetching (or re-deriving) it on every selection
change, defeating the point of a selection-invariant endpoint.

### Two corrections found by checking the real data, not assumed from the draft

- **Nine no-data countries, not six.** The original draft (based on a general pass over the
  dataset) named six countries with an early-1990s gap, all resolved by 1995 (`CXR, ERI, FSM, MHL,
  NAM, TLS`). Verified against the actual OWID data before implementing: three more — Monaco, San
  Marino, Vatican City — report **zero** CO₂ data across the *entire* 1990–2024 range, not a
  temporary gap. No code change was needed (the no-data trace design handles any number of
  always/sometimes-null countries generically), but `load_world_map_series`'s docstring documents
  the real figure rather than the draft's.
- **A literal zero breaks a log-scaled floor.** Antarctica has a real ISO-3 code and reports
  genuine `0.0` CO₂ for 2008–2024 — not missing data, an actual zero. `log10(0)` is undefined, so
  `WorldMapTimeSeries.value_range`'s floor excludes exact zero, using the smallest genuinely
  positive value instead (confirmed: `0.004` Mt, not `0.0`) — otherwise a zLog-scaled `colorRange`
  computed from the naive min would produce a null `zmin`.

### Copilot review (design-system #28) — two real findings, both fixed before merge

1. **`colorRange`'s own log10 transform could produce the same null-zmin problem it exists to
   prevent.** If a caller passed a `colorRange` with a non-positive lower bound (e.g. a naive
   `[0, max]`), the zLog-guarded transform would return `null` for that bound, and Plotly's
   behavior with `zmin: null` alongside `zauto: false` is undefined — it could silently fall back
   to auto-scaling, defeating the entire point of pinning the range. Fixed with a defensive floor
   (`Number.MIN_VALUE`) on the bound-transform specifically, kept distinct from the per-data-point
   transform (where `null` legitimately means "no color for this point," an intentional and
   different case).
2. **The no-data trace's existence was decided once, at mount, based on whether that render's data
   happened to contain a null.** An animated choropleth whose first frame was fully populated would
   permanently lose no-data highlighting for every later frame that did introduce a gap, since
   `animationFrame`'s own effect never re-runs the trace-construction code that decides whether the
   trace exists at all. Fixed by always constructing the trace — with empty `locations` when
   there's nothing to highlight yet, which costs nothing and renders nothing — removing the whole
   class of bug rather than special-casing it.

Both re-verified live (the `ChoroplethAnimated` Storybook story + direct `Plotly` state inspection)
before Copilot's re-review came back clean ("No further issues"). The api (#117) and app (#118)
PRs each came back clean on first review, no fixes needed.

### Verified live, pre- and post-deploy

Pre-deploy (a git worktree running the app against the real local API): zoomed the map, then let a
full ~23s animation run play out — zoom held exactly at the end (`geo.projection.scale`/`center`
unchanged). `world-map-series` fetched exactly once per page load (confirmed via network
inspection across two reloads); removing a country from the selection triggered a new `/overview`
call but no new `world-map-series` call. Namibia rendered in the no-data gray at 1990 and resolved
to real data by the mid-90s. Console clean throughout.

Post-deploy, against `labs.syena.io/ghg-emissions-analysis` (service worker and Cache Storage
cleared first, per the standing practice): fetched `/api/overview` and `/api/overview/world-map-series`
directly to confirm the real response shape (218 countries, 35 years, `value_range` maxing at
12,289 Mt — matching the independently-derived China-2024-peak figure from `SPEC.md` §5.17.2
exactly), then confirmed the rendered page settles to those exact figures once `CountUpText`'s
count-up animation completes (a fast screenshot taken immediately after navigation caught the
numbers mid-transition at 0 — expected behavior, not a bug, since `CountUpText` always eases from
its previous value on mount). Console clean.

### Release 12 follow-up: decade-stepped autoplay

**Status: Shipped.** `climate-emissions-analysis-project` PR #119, merged the same day as Release
12 itself. React-only. Prompted directly by feedback after using the year-by-year autoplay live:
annual emissions change is gradual enough that stepping through every single year makes the trend
hard to notice, whereas jumping decade to decade is glaring. The user's own framing: "the year-by-
year transition makes it difficult to see the evolving of the emitters as the change is gradual,
whereas decade level changes can be more glaring."

`useYearAnimation` now autoplays through a fixed stop list — `minYear`, every decade boundary after
it, then `maxYear` (appended only if it isn't already a decade boundary, avoiding a duplicate final
stop) — computed generically from whatever `minYear`/`maxYear` the caller passes, not hardcoded to
1990/2024. For the real 1990–2024 range this produces exactly `[1990, 2000, 2010, 2020, 2024]`.
Manual scrubbing via the `Slider`/`seek()` needed no change at all — it was already independent of
whatever stepping scheme autoplay used internally, and still allows any year in range. Resuming
Play after a manual seek to a non-stop year (e.g. 2015) advances to the next stop strictly *after*
that year (2020), not the next index in the stop list — otherwise seeking backward past an already-
visited stop and hitting Play would either replay a stop already seen or skip one arbitrarily.

Dwell time per stop raised from 600ms (one per year) to 1800ms (one per stop) — with 5 stops
instead of 35, total autoplay time actually *drops* to ~9s (from ~21s) despite each stop lasting 3×
longer, while giving both the map's color jump and the KPI count-up time to actually register
before the next stop fires.

**Real bug found while implementing, not in the original design:** the tick logic that decides
when to stop autoplay only flipped `isPlaying` to `false` the tick *after* reaching the final stop,
not upon arrival — at 35 roughly-one-second ticks this one-tick lag was invisible, but surfaced
immediately once verified live with only 5 stops at 1.8s each: the Play/Pause button visibly read
"Pause" for a full extra 1.8s after the map had already landed on 2024 and stopped changing, which
reads as a stale or broken control. Root cause: the interval callback's `next === undefined` branch
(meaning "no stop left after the current year") was the only place `setIsPlaying(false)` fired, and
that branch is only reached on the tick *after* arrival, since the tick that arrives at the final
stop takes the normal "advance to next stop" branch instead. Fixed with a second, separate effect
keyed on `currentYear` reaching `stops[stops.length - 1]`, which fires in the same render the final
stop is reached — confirmed live (both against the real API on `localhost` and again post-deploy
on `labs.syena.io`) that the button now flips back to "Play" the instant the map lands on 2024, no
lag. The same effect also correctly handles a degenerate single-stop range (`minYear === maxYear`)
without needing a tick at all, since it fires on mount if `currentYear` already equals the only
stop.

`useYearAnimation.test.ts` rewritten for the decade-stop model: stepping sequence lands on
2000/2010/2020/2024 rather than 1991/1992/…; a new test confirms no duplicate final stop when
`maxYear` already falls on a decade boundary; the final-stop-immediate-stop fix has its own
assertion (`isPlaying` false in the *same* tick that reaches the last stop, not the next one);
resuming Play after a seek to a non-stop year is asserted to advance to the correct next stop;
replay-from-start, reduced-motion gating, and the live OS-setting-change case all carried over
from the year-by-year test suite with values adjusted for the new stops.

Copilot's review was a clean pass, no comments. Verified live pre- and post-deploy: watched the
sequence land on 2010 mid-run and 2024 at the end with Play/Pause flipping back immediately, and
confirmed Namibia's no-data gray rendering at 1990 is unaffected by the pacing change (the no-data
trace logic itself didn't change, only when frames are dispatched).

### Release 12 second follow-up: separate KPI count-up duration from autoplay interval

**Status: Shipped.** `climate-emissions-analysis-project` PR #120, same day as the decade-autoplay
follow-up above. React-only. Reported live immediately after that change shipped: the KPI numbers
didn't have enough time to sit still and be read before the slider advanced to the next decade.

Root cause: `TierSummaryPanel`'s `CountUpText` instances and `useYearAnimation`'s tick interval
were both driven by the same constant (`ANIMATION_STOP_MS`, 1800ms) — the count-up animation was
still easing toward its target right up until the same 1800ms mark triggered the next decade jump,
so the numbers never actually held still.

Split into two named constants in `OverviewPage.tsx`:

| constant | value | role |
|---|---|---|
| `KPI_COUNT_UP_MS` | 1200ms | how long the count-up itself takes to ease to its new value |
| `ANIMATION_STOP_MS` | 4200ms | total dwell per autoplay stop, passed to `useYearAnimation`'s `intervalMs` |

The ~3s gap between them (4200 − 1200) is genuine settled, fully-readable time where the numbers
and the map's color both stay put before the next stop fires — the actual fix the report asked
for. No logic changed, only which constant feeds which prop.

No Copilot review requested for this one, per explicit instruction — small, low-risk change (two
numeric constants, no new code paths), verified directly instead: `tsc --noEmit` clean, the full
`vitest` suite (66 tests) unaffected since none of them assert on the specific millisecond values,
and a live check against the real API and (post-deploy) `labs.syena.io` confirming multiple real
decade stops (1990, 2000, 2010, 2024) each show correct, settled figures matching the API exactly,
with the Play/Pause control still flipping back to "Play" immediately on reaching 2024.
