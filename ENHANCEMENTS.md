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

### Release 12 third follow-up: shorten the dwell time

**Status: Shipped.** `climate-emissions-analysis-project`, committed directly to `main` (no
feature branch, PR, or Copilot review — per explicit instruction, given how small and low-risk the
change was). React-only. Reported live immediately after the second follow-up shipped: the ~3s
settled hold that fixed the previous "numbers don't stay still" report had overshot — it now read
as too long a pause between decade jumps.

`ANIMATION_STOP_MS` tuned down from 4200ms to 2400ms; `KPI_COUNT_UP_MS` left unchanged at 1200ms,
so the settled window per stop is now ~1.2s instead of ~3s. Verified: `tsc --noEmit` clean, the
full `vitest` suite (66 tests, unaffected — none assert on the specific millisecond values), and a
live check post-deploy against `labs.syena.io` confirming multiple real decade stops still settle
to the correct figures with Play/Pause flipping back immediately on reaching 2024.

Three same-day tuning passes on one control (600ms/year → 1800ms/stop → split into 1200ms
count-up/4200ms stop → 2400ms stop) is a reminder that pacing like this is very much a "know it
when you see it live" judgment call, not something to over-engineer a configuration system for
up front — the constants stayed as plain named numbers in `OverviewPage.tsx` throughout, not
exposed as a prop or setting, which made each iteration a one-line change.

### Release 12 fourth follow-up: 5-year steps, no KPI count-up

**Status: Shipped.** `climate-emissions-analysis-project`, committed directly to `main` (no
feature branch, PR, or Copilot review — per explicit instruction). React-only. Two changes
requested together in one message: step every 5 years instead of every 10, and drop the KPI
count-up animation entirely so the tier numbers change in lockstep with the map instead of easing.

**5-year steps.** `useYearAnimation`'s stop-computation function renamed `computeDecadeStops` →
`computeAutoplayStops` (the old name stopped describing it) and its hardcoded `10`-year increment
replaced with a named `STEP_YEARS = 5` constant. For the real 1990–2024 range this produces
`[1990, 1995, 2000, 2005, 2010, 2015, 2020, 2024]` — 8 stops instead of 5. Manual scrubbing via
`seek()`/the `Slider` needed no change, as before.

**No KPI count-up.** At a 1200ms tick interval (this session's third follow-up), the tier numbers'
count-up animation was either still visibly easing when the next tick fired or lagging noticeably
behind the map's own instant color change — animating a value that's about to be replaced again in
barely more than a second reads as motion for its own sake rather than something worth the visual
noise. `TierSummaryPanel`'s three metrics (Countries, `CO₂ (year)`, `% Change since 1990`) now
render their formatted value directly rather than through `CountUpText`, snapping in step with the
map on every tick. `KPI_COUNT_UP_MS` removed entirely as now-dead. `CountUpText` itself is
untouched — still used, unaffected, for the two `KpiStat` cards elsewhere on Overview (Fastest
Growth/Largest Reduction), which count up exactly once from the initial page load and were never
wired to `currentYear` in the first place, so "the KPI animation" the request referred to was
specifically the tier panel's synced numbers, not those.

`useYearAnimation.test.ts` rewritten in full for 5-year steps (all the numeric stop assertions
shifted from decade values to 5-year values; the "resume after a manual seek" test's seek target
changed to a year that's genuinely non-stop under the new scheme). `OverviewPage.test.tsx`'s tier-
number assertions changed from `toHaveLength(2)` (the old aria-hidden + visually-hidden
`CountUpText` pair) to a single `getByText`/`toBeInTheDocument()`, since these three metrics no
longer render duplicate text nodes at all.

Verified: `tsc --noEmit` clean, full `vitest` suite (66 tests) passing, no new lint warnings, and a
live check both pre-deploy (dev server against the real API) and post-deploy (`labs.syena.io`)
confirming a genuine 5-year stop mid-run (landed on 2005, then 2000 on a separate check), correct
settled figures with zero animation lag, a clean finish at 2024 with Play/Pause flipping back
immediately, and no console errors.

### Release 12 fifth follow-up: richer color palette

**Status: Shipped.** `climate-emissions-analysis-project`, feature branch + merge to `main` on
explicit go-ahead. React-only. Reported live: the visual difference between 1990 and 2024 wasn't
clear enough — the map didn't look dramatically different at the two ends of the animation despite
real emissions having grown ~69% globally.

Before touching anything, clarified which "range" the request meant (asked directly, since a
literal wider *numeric* `colorRange` would make things worse, not better — see below), confirming
it was about color richness, not the pinned min/max.

`colorRange` itself (`worldMapSeries.value_range`, the true global min/max across every country and
year, §5.17.2) had to stay exactly as-is: it's deliberately pinned across the whole animation so
the color scale doesn't re-normalize per frame, which is the entire reason the animation is
trustworthy at all — widening or narrowing that range would silently reintroduce the "1990's
largest emitter renders identically to 2024's" problem §5.17.2 exists to prevent. The actual
problem was `MAGNITUDE_SCALE`, the CSS-color side of the mapping: only 3 stops (`#fff2cc` pale
cream → `#f0a24a` orange → `#7a1f1f` deep red), which Plotly interpolates almost linearly across
the full log-scaled range. Since most countries in most years sit in the same middle band of that
range, they all land in the same narrow, nearly-linear middle segment of a 3-stop gradient and read
as similar shades of orange regardless of real magnitude difference.

Replaced with ColorBrewer's YlOrRd (Yellow-Orange-Red) 9-class sequential palette — a well-
established, perceptually-tuned choropleth palette:

```
#ffffcc, #ffeda0, #fed976, #feb24c, #fd8d3c, #fc4e2a, #e31a1c, #bd0026, #800026
```

at evenly-spaced stops (0, 0.125, 0.25, ..., 1.0). Same `colorRange`, same `zLog` transform, same
`NO_DATA_COLOR` (`#4a4a4a`, still visually distinct from every new stop — neutral gray against a
yellow/orange/red family, no collision at either end). Only the color *resolution* across the fixed
range changed.

Verified live, pre- and post-deploy: paused autoplay, seeked to 1991, screenshotted, seeked to
2024, screenshotted, and compared directly — countries that were pale yellow or light orange near
the start of the range (India, much of Africa and South America) now read as visibly, distinctly
deeper red or maroon by the end, a clear improvement over the old scale's near-uniform orange.
`tsc --noEmit` clean, full `vitest` suite (66 tests) unaffected, no new lint warnings, console clean
on both the local dev check and the production check.

### Release 12 sixth follow-up: slider range labels and a moving current-value label

**Status: Shipped.** `design-system` PR #29 + `climate-emissions-analysis-project` PR #121, both
reviewed via the `copilot-review-loop` skill and merged. React-only. Requested directly: indicate
the year slider's start/end years, and show a label that moves with the thumb as it plays or is
scrubbed.

**`design-system` (`Slider`, PR #29):** two new opt-in props, additive to the existing `showValue`
(a static line above the track), not a replacement for it:

- `showRangeLabels` — renders `min`/`max` as a row below the track's two ends.
- `showThumbValue` — a small floating label positioned directly above the thumb via the same `pct`
  calculation the thumb's own `left` already uses, so it tracks live regardless of *how* the value
  changes (drag, keyboard, or a programmatic change like this app's autoplay). `aria-hidden="true"`,
  since the value is already exposed via the slider role's own `aria-valuenow` — this is a purely
  visual aid, `pointerEvents: 'none'` so it never interferes with dragging.

New Storybook story (`YearRangeWithMovingLabel`) demonstrates both against the actual 1990–2024 use
case, with interaction tests confirming the range labels render and the current value appears in
both the static header and the moving bubble.

Copilot's review of #29 was a clean pass — one harmless note (an explicit `position: 'relative'`
added to the track `div` is redundant, since the vendor CSS already sets it), no action needed.

**`climate-emissions-analysis-project` (Overview page, PR #121):** wired both new props into the
year `Slider`. Copilot's review was also clean — a single prop-only diff, no logic or test-surface
change, 66 Vitest tests unaffected.

**Same-turn follow-up, no separate PR needed initially but folded into #121 before merge:** the
old static "Year ... 2024" value next to the label was reported as redundant once the moving label
shows the same number in context, and removed (`showValue={false}` — the `label="Year"` text
itself stays, only the value span goes).

Verified live, pre- and post-deploy: the moving label tracks the thumb correctly through a full
autoplay run, confirmed no clipping at either range extreme (checked 1990 and 2024 directly — the
bubble's `translate(-50%, ...)` centering means it slightly overflows the track's own edge at
either extreme, but stays within the `ChartCard`'s padding with nothing cut off), no layout clash
with the Play button or the `ChartCard` title, and the static value label confirmed removed. Console
clean on both checks.

## Release 13 — Overview Headline Sentence, Compressed Tier Panel, Slider Touch Target & No-Data Hover

**Status: Shipped.** Bundles two unrelated efforts from the same review pass under one release
(SPEC.md §5.18), following the §5.9/Release 3.1 precedent — no dependency between them and no
shared code, but no reason that requires separate release numbers either.

### Headline sentence + compressed tier panel (`climate-emissions-analysis-project` PR #122)

Added a one-sentence, data-derived headline above the Overview page's tier table, in the hero
row's existing right-hand column rather than a new full-width section, to avoid re-growing page
height after prior releases (the 2/3-map/1/3-KPI restructure, §5.10) fought it down. Deterministic
string templating from `OverviewResponse.top_movers`, explicitly not an LLM call: this project
verifies every number before stating it, and free-form generation can't be unit-tested for factual
correctness the way a template can.

New `src/lib/overviewHeadline.ts` — the first standalone utility module in `src/lib/` alongside
`basePath.ts` — derives `absGrower`, `pctGrower`, `mostStable`, and up to two `decliners` via
hand-rolled `maxBy`/`minBy` (no `lodash` dependency in this project) rather than trusting
`top_movers`' given sort order, which is a server-side (Python) contract not encoded in the TS
type. Handles every edge case the draft spec called out — `absGrower === pctGrower` collapses to
one clause instead of naming the same country twice, zero decliners drops the final clause
entirely, fewer than 4 usable rows suppresses only the "most stable" clause, ties resolve
deterministically via first-in-input-order — plus one the draft didn't call out: exactly one
decliner needs its own singular-wording branch ("`X` shows the steepest decline"), not the plural
template with an empty second slot. Rows with a `null` `absolute_change`/`pct_change` are excluded
from consideration entirely rather than coerced to `0`, since "0% change" is a substantive claim,
not a safe fallback for "unknown." Labeled with a "Since 1990" eyebrow so it doesn't read as
describing whatever year the adjacent, user-scrubbable §5.17 animated map happens to be paused on.

`OverviewHeadline` is gated on `selected.length > 0` — a correctness fix over the original spec
draft, not something the draft itself specified: `top_movers` reflects the server's default
selection even when the local `selected` array is empty, which would otherwise narrate a phantom
selection right next to the "Select at least one country" warning. Uses the exact same gate the
Selected tier row already relied on.

`AnimatedWorldMap`'s returned Fragment previously had exactly two top-level children (the map
`ChartCard`, then `TierSummaryPanel`), which CSS Grid treated as its two direct items. Adapted only
the second child — now a wrapper `<div>` containing `OverviewHeadline` above `TierSummaryPanel` —
without touching the grid itself or `useYearAnimation`/the map, which were already working and
shipped as part of §5.17.

`TierSummaryPanel` recompressed from three per-tier cards (each with a per-tier icon column) to a
single `Table`, freeing the vertical space the headline needs. Direct precedent for exactly this
shape already existed in this file's own git history — commit `47c6e3d` did this once before,
later reverted to cards in `a4d3967` for unrelated reasons. `Table<Row extends Record<string,
unknown>>`'s generic constraint meant `TierRow` needed its `[key: string]: unknown` index
signature back, the same fix made once before (`bf84e76`) and dropped when cards replaced the
table (`940ccb9`). The per-tier `Icon`/`TierIcon` machinery was dropped entirely — a compressed
table has no room for a 20px icon column.

Copilot's review of #122 came back clean — one cosmetic observation: a positive-but-near-zero
`mostStable` value reads as "stayed comparatively flat," mildly odd wording for a country that
still grew, in an all-growth selection. Confirmed this is exactly SPEC.md §5.18.1's own specified
algorithm (`minBy(topMovers, m => Math.abs(m.pctChange))`) and template wording, not a deviation
introduced by this implementation — replied explaining that, no code change made. 9 new
`overviewHeadline.test.ts` cases (null filtering, same-leader collapse, 0/1/2-decliner wording,
the `MIN_SELECTION_FOR_STABLE_CLAUSE` boundary, tie-breaking) plus 3 new/updated
`OverviewPage.test.tsx` assertions (headline renders with the multi-mover fixture, absent at 0
selected, "Since 1990" eyebrow present; the `CO₂ (2024)` header-count assertion changed from 3 —
one per card — to 1, a single column header).

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first): the headline renders and matches this section's own hand-verified example
(China +9,806 MtCO₂ absolute/since 1990, India +452.5% fastest rate, United States −4.4% most
stable, United Kingdom/Germany steepest declines at −48.0%/−45.7%); disappears when deselecting to
0 countries and reappears on "Reset to default"; the compressed table doesn't stretch the hero row
past the map's own height (`alignItems: 'stretch'` on the grid would otherwise reintroduce the
dead-space problem §5.10 fixed); both the ≥1400px two-column and <1400px single-column breakpoints
render correctly; console clean through a full animation run.

### Slider touch target + SyChart no-data hover (`design-system` PR #30)

Two independent, small fixes, bundled in one PR since neither shares code or has an ordering
dependency with the other.

**Slider touch target (WCAG 2.2 §2.5.8).** `.__s9cmpx-slider__thumb` was 16×16 at rest, 20×20 on
`:hover` in the vendored CSS — both below the 24×24 CSS px minimum, and `:hover` doesn't help
keyboard or touch users reach even that still-failing size. Fixed in `overrides.css` (this repo's
own bug-fix layer on top of the vendored CSS, per its `CLAUDE.md` — never hand-edit the vendor
file directly) by raising the resting size to 24×24 and matching `:hover` to the same value, so
hover becomes a no-op instead of a shrink. Followed the exact template of this same file's existing
`.__s9cmpx-tags__remove-button` WCAG fix (comment style: what the vendor bug is, how it was
confirmed, why the chosen value doesn't overreach) but landed at a different conclusion on size:
that fix stayed at 24×24 rather than 44×44 specifically because the tags button sits in a dense,
crowded list; the slider thumb sits alone on an otherwise-open track (the whole track is already
the effective drag target — `Slider.tsx`'s `onPointerDown` fires from anywhere on it, so this was
always a rendered-target-size fix, not a drag-precision one), so there's no adjacent-element reason
to keep it small — 24×24 chosen over 44×44 to stay proportionate to the compact inline slider row
next to the Play/Pause button. New Storybook `play` assertion on the `Playground` story
(`getBoundingClientRect() >= 24×24`) — no existing story asserted thumb pixel size before this.

**SyChart no-data hover text.** The no-data choropleth trace used `hoverinfo: 'skip'`, giving
no-data countries a silent, uninformative hover — correct in that it avoided a false numeric value,
but read as an unresponsive control. Replaced with an explicit `hovertemplate` defaulting to "No
data reported," extracted into a new `noDataHovertemplate()` helper in `chartMath.ts` (this file's
already-established home for `SyChart`'s Plotly-free pure logic, per its own `CLAUDE.md` — kept
`SyChart`/`Score`'s existing pattern of extracting pure logic for direct unit-testing rather than
only through a rendered story) and a new optional `SyChartSeries` field, `noDataHoverText`, for
callers wanting a more specific label than the generic default. The unrelated `'band'` kind's own
`hoverinfo: 'skip'` (its invisible lower-bound line for confidence-interval shading) was
deliberately left untouched — confirmed via `grep` that the string appears at exactly two lines in
the file, only one of which was the actual fix target.

Copilot's first review attempt on #30 failed at the infrastructure level — "the job was not
acquired by Runner of type hosted even after multiple attempts" — not an actual completed review,
confirmed via the check-run's own annotation before re-requesting rather than assuming a silent
pass meant "clean." The second attempt reviewed all 6 changed files cleanly, no comments.

Consuming apps need no code change for either fix to land: `climate-dashboard-react`'s
`vite.config.ts` aliases `design-system` straight to its source directory (`design-system` has no
`main`/`module`/`exports` field and a static `"version": "0.0.0"` — it isn't consumed as a
versioned package at all in this setup), so both fixes are live the moment `design-system`'s `main`
is merged, no version bump or reinstall needed.

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first): the Overview year slider's thumb measures exactly 24×24 via a direct
`getBoundingClientRect()` check against the live DOM; the no-data (gray) countries' Plotly trace
carries the new `"%{location}<br>No data reported<extra></extra>"` hovertemplate in place of the
old silent `hoverinfo: 'skip'`, confirmed by reading the live `.js-plotly-plot` trace data directly
rather than only visually.

### Deploy

Both PRs merged via the `copilot-review-loop` skill running in parallel across the two repos.
Deployed to the Mac Mini: fast-forward `git merge origin/main` in both `climate-emissions-analysis-
project` and `design-system` checkouts (leaving the unrelated, expected `notebook/`/`data/`
modifications from the weekly `ghg-data-refresh` job untouched — confirmed the incoming commits
touched none of those files before merging), `climate-dashboard-react` rebuilt with
`DEPLOY_BASE_PATH=/ghg-emissions-analysis/` set at build time (the known Release 7 gotcha — the
Mac Mini rebuild needs this at build time, not just serve time), `vitepreview` LaunchAgent
unloaded/reloaded (`uvicorn` untouched — no `api`/`app.py` change in this release). `design-system`
needed no separate deploy step of its own, consumed live via the source alias.

### Release 13 follow-up: headline redundancy and tier-name truncation

**Status: Shipped.** `climate-emissions-analysis-project` PR #123, React-only. Two issues found in
live review of the just-shipped panel, both real:

1. **"Since 1990" stated twice in three lines.** The eyebrow label and the headline sentence
   itself both carried the timeframe — "Since 1990 / China has grown the most in absolute terms
   (+9,806 MtCO₂ *since 1990*), while...". The eyebrow's own purpose (anchoring the sentence
   against the live-scrubbable map beside it) was sound; the sentence just didn't need to repeat
   it once the eyebrow existed. Dropped "since 1990" from both `overviewHeadline.ts` sentence
   branches (distinct-leaders and same-country-collapsed) — the eyebrow now carries the timeframe
   alone. New test asserts the rendered sentence never contains the phrase, in either branch.
2. **Real truncation, not cosmetic.** Measured directly against the DOM: "Expanded (Coverage +
   ≥100 Mt)" needs 204px and the compressed table's Tier column was giving it 133px — 71px short,
   clipping to "Expanded (Cover..." and losing the coverage/materiality qualifier this tier's
   entire definition rests on (the reason 40 countries are selected out of 218). The % Change
   column header clipped too, by a much smaller margin.

   Fix: dropped the single 4-column `Table` for a full-width tier-name heading per row above a
   compact 3-column metric strip (Countries/CO₂/%Change) — the tier name gets the panel's entire
   ~380-450px width to wrap into instead of a cramped fourth of a shared row, while the three
   short, fixed-format numeric metrics (never the truncation risk) move into a `display: grid,
   gridTemplateColumns: repeat(3, 1fr)` strip below it. Still one visually compact bordered block
   (a shared panel border, per-row top borders, no per-tier cards or icons) — not a reversion to
   the taller original card layout. `Table` import and `TierRow`'s `[key: string]: unknown` index
   signature both dropped as no longer needed.

   Live DOM measurement post-fix: `scrollWidth === clientWidth` on the tier-name element and all
   three "% Chg. since 1990" metric labels — none truncated.

Copilot's review of #123 came back clean, no findings. `overviewHeadline.test.ts` gained a
dedicated regression test asserting the sentence never contains "since 1990" in either branch;
`OverviewPage.test.tsx`'s tier-metric-label count assertion changed from 1 (a shared column
header, the now-reverted Table shape) back to 3 (one inline label per tier row, matching the
per-row heading-plus-strip structure). Verified live pre- and post-deploy
(`labs.syena.io/ghg-emissions-analysis`, service worker/Cache Storage cleared first): both fixes
confirmed via direct DOM measurement rather than only visually — zero "since 1990" occurrences in
the rendered sentence text, zero truncated elements in the tier panel.

### Release 13 second follow-up: decouple the headline from the country picker

**Status: Shipped.** `climate-emissions-analysis-project` PR #124, both `api/` and
`climate-dashboard-react/` (one PR — same git repo, direct precedent for a single commit spanning
both, e.g. `53b9370`/`30aa68a`). Prompted by a direct question about what the headline sentence
was actually describing: the answer, checked against `api/routers/overview.py`, was "whatever's
currently selected in the picker" — correct today only because the picker's default
(`FEATURED_COUNTRIES`) happens to coincide with a sensible-looking story, and silently wrong the
moment a user changes the selection, since the headline sits above the fold and is easy to miss
re-reading while the picker lives below it.

**Backend.** New `TOP_N_HEADLINE = 10` constant in `api/constants.py`, placed next to
`PCT_CHANGE_BASELINE_YEAR` (both consumed directly in `overview.py`'s movers logic). New
`headline_movers: list[MoverRow]` field on `OverviewResponse`, computed in a new block in
`overview.py` — inserted after the existing `world_map` construction since it needs
`df_all`/`all_latest_year`/`df_map`, all already in scope there, no new loader calls. The set is
fixed by `df_map.nlargest(TOP_N_HEADLINE, "co2")` **before** the baseline/latest/pct-change
figures are computed — a materially different selection mechanism from `top_movers`, which takes
whichever countries are in `selected` with no cap at all. Uses `PCT_CHANGE_BASELINE_YEAR` properly
rather than the literal `1990` the existing `top_movers` block hardcodes (an existing
inconsistency, not copied into the new code). Sorted by `co2_latest` descending, not `pct_change`
like `top_movers` — the set itself was chosen by magnitude, so returning it in that order is
self-documenting; the frontend's `buildHeadlineSentence` derives every fact itself regardless of
input order (verified directly in the file), so this is a pure API-clarity choice, commented
explicitly so a future maintainer doesn't "fix" it into consistency by mistake. `top_movers`
itself is completely untouched.

Two new tests: `test_overview_headline_movers_unaffected_by_countries_param` (mirrors the existing
`world_map` invariance test exactly — the load-bearing regression proof, using the standard
`client` fixture since proving invariance doesn't need magnitude diversity) and
`test_overview_headline_movers_ordering_and_top_n_cap` (a new dedicated 12-country fixture,
`owid_raw_headline_df()`, following `owid_raw_world_map_series_df()`'s exact precedent of NOT
being part of `FIXTURE_BUILDERS`/`full_data` — the shared 4-country fixture can't exercise a real
top-10 cap; the new fixture includes two countries just below the cutoff to prove they're
excluded despite otherwise-complete 1990/2024 pairs).

**Frontend.** `buildHeadlineSentence` gains a required second parameter, `scope: string` — the
caller supplies the exact wording ("the top 10 emitters by 2024 output"), fused via a plain comma
splice onto the sentence's first clause: `"Among ${scope}, ${...}"`. Required, not
optional/defaulted, since the sentence now always describes a fixed scope rather than being
conditionally rendered. Kept out of the pure function for the same reason the file's own doc
comment already gives for the "Since 1990" eyebrow: it's a rendering/wording concern, not a
derived fact, so the function stays independently testable against arbitrary scope text — the
same discipline that made the Release 13 first follow-up's redundant-"since 1990" bug a one-line
fix rather than a rearchitecture. All derivation logic (`maxBy`/`minBy`/decliners/edge cases) is
unchanged.

`AnimatedWorldMap`'s `topMovers` prop renamed to `headlineMovers`, now fed `data.headline_movers`.
`scope` is computed inline from props already in scope — `headlineMovers.length` and
`allCountriesTier.latest_year` (confirmed via `_tier_metrics`: `all_countries.latest_year ==
int(df_all["year"].max())`, i.e. exactly the backend's `all_latest_year` — no new API field
needed for this). The `selected.length > 0` gate on `OverviewHeadline` — previously needed because
`top_movers` reflected the server's default selection even when `selected` was empty — is removed
entirely: `headline_movers` doesn't depend on the picker at all, so the headline now stays visible
even at 0 selected countries. The below-the-fold Top Movers section's `moverCountries`/`moverPct`
(still `data.top_movers`) and its "Top Movers Since 1990 (N Selected Countries)" heading are
completely untouched.

`RESPONSE.headline_movers` in `OverviewPage.test.tsx` is a **different**, independent 10-country
fixture from `top_movers`'s existing 5-country one, deliberately, to prove independence in tests
rather than accidentally re-testing the same array twice. The "deselecting to 0" test's assertion
flipped from `queryByText('Since 1990')).not.toBeInTheDocument()` to
`findByText('Since 1990')).toBeInTheDocument()` — the single most load-bearing test change proving
the fix actually works.

Verified against real 2024 OWID data before implementing (not assumed): the true top 10 emitters
(China, United States, India, Russia, Japan, Indonesia, Iran, Saudi Arabia, South Korea, Germany)
is not `FEATURED_COUNTRIES` — the United Kingdom drops out of the headline entirely (its 48%
decline was only ever there because it's in the curated `FEATURED_COUNTRIES` list, not its raw
tonnage), Germany becomes the steepest decliner, Russia (−29.8%) enters in the UK's place.

Copilot's review of #124 came back clean, no findings — confirmed, per this project's now-standard
discipline, by checking the `copilot_work_started`/`copilot_work_finished` timeline event pair
matched the substantive review comment's timestamp, not just treating a posted comment as
sufficient on its own (the Release 13 first follow-up's PR #30 had already shown a posted-looking
signal can actually be an infrastructure failure).

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first, both `uvicorn` and `vitepreview` LaunchAgents restarted since this release
touches both `api/` and `climate-dashboard-react/`): headline text read directly from the live DOM
via `document.querySelectorAll` and confirmed **byte-identical** before and after deselecting
every country in the picker down to 0 — the core fix; the headline stayed visible throughout
(rather than disappearing, the pre-fix behavior); the below-the-fold Top Movers section still
showed "Largest Reduction — United Kingdom," confirming `top_movers` continues reacting to the
picker exactly as before; console clean throughout.

### Release 13 third follow-up: highlight countries, color values in the headline

**Status: Shipped.** `climate-emissions-analysis-project` PR #125, React-only. Requested directly:
highlight the countries named in the headline sentence, and color the numeric values using this
app's color-coding convention. The convention already existed and didn't need inventing —
`TierSummaryPanel`'s % Change column colors an increase `NEGATIVE_COLOR` (more emissions, bad) and
a decrease `POSITIVE_COLOR` (less, good) — so the work was applying that existing rule to the
headline, not choosing a new one.

**The architecture question.** `buildHeadlineSentence` was a pure function returning a plain
string. Styling individual words within an already-assembled string means either (a) regex-based
post-processing to re-find country names and numbers inside the final text — fragile, since a
country name could coincidentally appear as a substring elsewhere, and offers no way to know a
value's sign without re-parsing it back out of formatted text like `"-45.7%"` — or (b) having the
function build tagged segments directly, since it already knows exactly which piece of text
corresponds to which country or value at the moment it assembles them. Chose (b): a new
`HeadlineSegment` union type (`{ kind: 'text' }` / `{ kind: 'country' }` / `{ kind: 'value';
sentiment: 'positive' | 'negative' }`), and `buildHeadlineSentence` now returns
`HeadlineSegment[] | null` instead of `string | null`.

`sentiment` is computed once, at the point each value is known (`raw >= 0 ? 'negative' :
'positive'` — the same `>= 0` rule `TierSummaryPanel`'s existing pctChange coloring already uses),
and treated as a **derived fact** the function states, not a color choice — the actual
`NEGATIVE_COLOR`/`POSITIVE_COLOR` mapping happens in the rendering component. This mirrors the
split this file already established for the "Since 1990" eyebrow and the `scope` parameter
(SPEC.md §5.18.5): the pure function owns facts and prose, the component owns presentation. Kept
the absolute-change display's existing quirk of always showing a leading `+` (`formatMtSigned`,
new, mirrors `formatPct`'s existing signed-formatting convention) inside the colored `value`
segment now, rather than as a separate uncolored text segment in front of it — a minor visual
tightening (the whole "+9,806 MtCO₂" token now reads as one colored unit) that doesn't change the
flattened text output.

A new `headlineSegmentsToText(segments)` helper flattens segments back into the original plain
sentence (`segments.map(s => s.text).join('')`) — confirmed byte-for-byte identical to every
existing test's expected string, proving this was a pure structural refactor with zero wording
change. All the actual derivation logic (`maxBy`/`minBy`/decliners/edge cases) is untouched; only
how the pieces get assembled changed, from template-literal string concatenation to pushing typed
segments onto an array.

**Rendering.** `OverviewHeadline` maps segments to JSX: `country` → `<strong>`, `value` → a `<span
style={{ color: sentiment === 'negative' ? NEGATIVE_COLOR : POSITIVE_COLOR }}>`, `text` → the raw
string (no wrapper needed). Both color constants were already imported in `OverviewPage.tsx` for
the tier table, so no new import.

**Test fallout.** The dedicated headline test's exact-string `screen.getByText(fullSentence)`
assertion broke — the sentence is no longer one text node, so RTL's default text-node matching
can't find it directly. Fixed with a custom matcher function checking the `<p>` element's full
`textContent` against the expected string (`(_, element) => element?.tagName === 'P' &&
element.textContent === expectedText`), then added targeted assertions on top of that match: `
within(paragraph).getByText('China').tagName === 'STRONG'` for bolding, and `
within(paragraph).getByText('+452.5%')).toHaveStyle({ color: NEGATIVE_COLOR })` for coloring —
this is the first place this test file needed a split-text matcher, so it's now the template for
any future rich-text rendering test in this codebase. `overviewHeadline.test.ts` gained direct
segment-level tests (country segments appear in the right order, values carry the correct
sentiment, the same-country collapse case produces exactly one country segment not two) alongside
every existing test, all updated to flatten segments via the new helper before asserting on wording.

Copilot's review of #125 posted **no comment at all** — before treating that as clean, checked the
`copilot_work_started`/`copilot_work_finished` timeline pair (both present) and, critically, the
`copilot` check-run's `conclusion` field directly: `success`, not `cancelled` — the exact
distinction that mattered on the Release 13 first follow-up's PR #30, where a similarly
comment-free result turned out to be an infrastructure failure (`"the job was not acquired by
Runner of type hosted"`), not a real review. Confirming the conclusion field rather than just the
absence of a flagged comment is what made this genuinely safe to merge.

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first, `vitepreview` LaunchAgent rebuilt/restarted — this release is
`climate-dashboard-react`-only, no `api/` change, so `uvicorn` was untouched): country names bold,
China's absolute change and India's growth rate (both increases) render red, United
States/Germany/Russia's values (all decreases) render green, visually consistent with the tier
table's own coloring; console clean.

## Release 14 — Per-Page "Jump To" Navigation

**Status: Shipped.** `design-system` PR #31 + `climate-emissions-analysis-project` PR #126
(SPEC.md §5.19). A small in-page anchor-link row under each of the six main pages' `<h1>`, letting
a user jump straight to a below-the-fold section instead of scrolling.

### The reuse discovery that reshaped the plan

The original draft called for a new `Chip`-based `JumpNav` component, built from scratch: a `Chip`
`href` variant plus a hand-rolled click handler doing smooth-scroll and focus management. Before
implementing, a planning pass turned up something the draft hadn't accounted for: `design-system`
already shipped a `JumpLinks` component (`src/components/JumpLinks/JumpLinks.tsx`), exported from
`src/index.ts`, with real vendored CSS (`__s9cmpx-jump-links` family) already present in the
stylesheet — and confirmed, via a direct grep across both repos, to have **zero actual usages**
anywhere except its own story file. Built for exactly this use case (in-page anchor navigation,
styled as underline tabs rather than pill chips) and never wired up.

Presented as an explicit choice rather than assumed: reuse `JumpLinks` (extending it with the
scroll/focus/click-interception behavior the draft wanted), or build the draft's `Chip`-based
`JumpNav` from scratch. Reuse was chosen — it eliminated the need for the `Chip` `href` variant
entirely and meant the visual design (underline tabs) didn't need inventing either.

### `design-system` changes (PR #31)

**`ChartCard` gained a passthrough `id?: string`.** The underlying `Card` component already
extended `React.HTMLAttributes<HTMLDivElement>` and spread `{...rest}` onto its own outer `<div>`,
so it already supported `id` — `ChartCard` itself just needed to accept and forward it, a one-line
addition confirmed via direct read before writing it.

**`JumpLinks` gained scroll/focus/click-interception behavior plus an `onBeforeJump` hook.** New
optional field on `JumpLinkItem`: `onBeforeJump?: () => void | Promise<void>`, run and awaited
before the scroll — used by Forecasts to force-open a collapsed `Accordion` panel before jumping
into it (see below). Per-item rather than a page-level id-keyed lookup, since only 3 of Forecasts'
5 items actually need it and this keeps each item's wiring colocated with itself. The click handler
mirrors `SidebarNav.tsx`'s exact interception guard: a modified click (ctrl/cmd/shift/alt) or a
non-primary mouse button is never intercepted, so "open in new tab," middle-click, and right-click
"copy link address" all keep working natively against the real `href`. When `onBeforeJump` exists,
the handler awaits it, then waits a double-`requestAnimationFrame` ("wait for the next paint after
a state update" — the standard pattern for this) before measuring scroll position, since a state
update from `onBeforeJump` (e.g. an Accordion panel opening, which mounts new DOM) isn't
synchronously reflected in layout. This double-rAF wait is paid only by items that actually have
`onBeforeJump` — the other 17 of 20 jump items across all six pages keep identical latency to a
plain scroll. A new exported `scrollToJumpTarget(id, opts)` helper factors the scroll/focus logic
out of the click handler, reused by the consuming apps' own hash-on-load effect (below).

**`Accordion` gained an optional controlled `openIds`/`onOpenChange` pair**, additive alongside the
existing uncontrolled internal `useState<Set<string>>` fallback. Confirmed via grep that
`ForecastsPage.tsx` is `Accordion`'s only consumer in either repo (previously fully uncontrolled),
so this addition couldn't break anything else. A controlled pair rather than a `defaultOpenIds`
seed was the right shape specifically because a jump click needs to force-open a panel on demand
*after* mount, not just seed initial state. Each panel's actual DOM id is already the existing
`` `${item.id}-accordion-panel` `` convention — the 3 Forecasts jump items target that suffixed id,
not the bare accordion item id.

**Copilot's review of #31** found one real bug: `e.preventDefault()` (needed so the handler's own
scroll/focus sequence runs instead of the browser's native jump) meant the URL hash never actually
updated on a click — breaking "copy link address" and back-button/forward-button behavior, since
nothing was ever pushed onto history. Fixed with a `window.history.pushState(null, '', `#${id}`)`
call after the scroll, added by a follow-up commit, re-reviewed, confirmed clean.

**A Storybook test-runner crash, root-caused and worked around.** A `ModifiedClickIsNotIntercepted`
story — asserting a ctrl/cmd-click is *not* intercepted, i.e. that real hash-navigation is allowed
to proceed — reproducibly crashed the Storybook/vitest browser-mode test runner's RPC connection
(`[vitest] Browser connection was closed while running tests`). Diagnosed via careful bisection:
confirmed the original 2-story file passed cleanly; confirmed adding a separate
`ClickScrollsAndFocusesTarget` story alone still passed; confirmed adding the modified-click story
on top reliably crashed the runner; confirmed removing only that one story (keeping an
`onBeforeJump`/Accordion story instead) passed cleanly again. Concluded the root cause was
environmental — letting a real native hash-navigation actually complete inside that specific
test-runner setup destabilizes it — not a bug in the interception-guard logic itself, which is a
direct, already-proven port of `SidebarNav`'s shipped pattern. Dropped that one story/test
permanently, added an explanatory comment in `JumpLinks.stories.tsx`, and covered that specific
behavior (modified-click passthrough) via live browser interaction instead: real ctrl/cmd-click
opens a new tab, right-click "copy link address" yields a real anchor URL.

### `climate-emissions-analysis-project` changes (PR #126)

All six pages (Overview, Historical Trends, Country Profile, Forecasts, Scenario Comparison, Data
Explorer) render a `<JumpLinks>` row directly under their `<h1>`. A new shared
`useJumpToHashOnLoad(ready, reduceMotion)` hook, using a `useRef` guard to fire exactly once per
page load (not on every subsequent `ready` change from e.g. a picker-triggered refetch), replays
the jump for a bookmarked/shared `#anchor` URL once the target section actually exists — the
browser's own native hash-scroll on initial page load fires too early for a data-loaded page's
target to exist in the DOM yet.

**Missing-target handling was mostly free.** For three pages — Historical Trends, Scenario
Comparison, Data Explorer — the target `<h2>` headings were already unconditionally rendered (only
the chart/table content beneath was gated behind a selection or loading state), so placing the
anchor `id` directly on the static heading gave a jump target that always exists once the page has
loaded at all, regardless of the current selection. No refactor needed for these three.

**Overview needed an actual refactor.** Its "By Country" and "% Change" sections previously had
their *entire* heading-and-content block inside the `selected.length === 0 ? <InlineAlert/> :
(...)` ternary — no persistent heading to anchor. Fixed by splitting into two independently-gated
blocks, matching the pattern `HistoricalTrendsPage.tsx` already established (heading outside the
gate, only the `ChartCard`/chart content beneath it conditional) — confirmed by reading that
existing pattern directly before applying it, rather than inventing a third way to solve the same
problem. Side effect, deliberate and accepted: the "Select at least one country." warning now
renders once per gated section (2×) instead of once.

**Forecasts is the special case.** 3 of its 5 jump targets — Model Comparison, ETS Parameters,
Feature Importance — live inside a collapsed-by-default `Accordion`. Each of those `JumpLinkItem`s'
`onBeforeJump` opens its panel via `Accordion`'s new controlled `openIds`; the accordion-backed
items only appear in the jump row once their underlying data has actually loaded, matching how
`accordionItems` itself is conditionally built.

**A genuine test-infrastructure bug, found and fixed along the way.** `vi.unstubAllGlobals()`,
added to five page test files' `afterEach` blocks by copying `useCountUp.test.ts`'s established
`matchMedia`-stubbing pattern too literally, also wiped the global `ResizeObserver` stub
`src/test/setup.ts` establishes once per file (needed because jsdom has no native `ResizeObserver`
and `design-system`'s `DataTable` uses one) — breaking every `DataTable`-rendering test after the
first in each affected file. Confirmed as a real regression, not pre-existing flakiness, via `git
stash`/`git stash pop` bisection on `ScenarioComparisonPage.test.tsx` (clean stash: 9/9 pass; with
the changes applied: 4/10 failing with `ReferenceError: ResizeObserver is not defined`). Fixed by
dropping the blanket unstub from all five files' `afterEach`, keeping only `vi.clearAllMocks()` —
each file's `beforeEach` already re-stubs `matchMedia` fresh before every test, so nothing else
needed cleaning up. Verified the fix: all five files together, 44/44 passing, zero `ResizeObserver`
errors.

**Copilot's review of #126** found one real bug, plus two minor notes. The bug:
`useJumpToHashOnLoad(true, ...)` on `ForecastsContent` fired on the component's very first render
— hardcoded `ready: true` — before `modelComparison`/`etsParams`/`featureImportance` had resolved,
at which point the 3 accordion-backed targets didn't exist in the DOM at all (the panel content
only mounts once its Accordion item is open, and the accordion item itself is only added once its
data resolves). Since the hook is one-shot, a bookmarked
`/forecasts#model-comparison-accordion-panel` URL would silently no-op forever. Fixed by resolving
the URL's hash against a new `PANEL_TO_ACCORDION_ID` map at mount, opening the matching panel once
all three accordion datasets have loaded, and gating `useJumpToHashOnLoad`'s `ready` argument on
that panel actually being open — while `#forecast-chart`/`#forecast-summary` (always in the DOM
from first render) keep firing immediately as before, unaffected. Added a regression test
asserting `document.activeElement?.id === 'model-comparison-accordion-panel'` after loading with
that hash pre-set, and verified the exact fix live pre-deploy
(`/forecasts#model-comparison-accordion-panel` correctly opens the panel and scrolls to it). The
two minor notes — an inert `reduceMotion` effect dependency, and a documented but genuinely correct
`headingLevel` downgrade on the "By Country" `ChartCard` (verified live via a full DOM heading dump
that the resulting outline has no skipped levels or duplicates) — were addressed and confirmed
respectively in the same follow-up commit. Copilot's second review pass confirmed the fix and
cleared the PR to merge.

### Deploy

Both repos fast-forwarded on the Mac Mini (`git fetch && git merge --ff-only`); `design-system` had
to be pulled first since `climate-dashboard-react`'s build failed against its stale copy (missing
`scrollToJumpTarget` export, `ChartCard.id`, `JumpLinks`' new `onBeforeJump`, `Accordion`'s
`openIds`) until it was. `vitepreview` LaunchAgent rebuilt (`DEPLOY_BASE_PATH=/ghg-emissions-analysis/
npm run build`) and restarted via `launchctl kickstart -k`; no `api/` change in this release, so
`uvicorn` was left untouched.

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first): all six pages' jump rows render the correct labels/hrefs; clicking scrolls
to and focuses the right target; keyboard Tab+Enter activation works; a fresh page load with
`#pct-change` already in the Overview URL lands on the right section once data resolves; loading
`/forecasts#model-comparison-accordion-panel` fresh — the exact case the PR #126 review caught —
correctly opens the Model Comparison panel and scrolls/focuses it; jump-link `href`s resolve to
real, copyable anchor URLs.

## Release 15 — Floating "Back to Top" Button

**Status: Shipped.** `design-system` PR #32 + `climate-emissions-analysis-project` PR #127
(SPEC.md §5.20). Requested directly, as a companion to Release 14's jump nav: a floating button
that appears once the user scrolls below the fold and, on click, returns to the top of the page.
Checked first whether `design-system` already had something reusable for this the way `JumpLinks`
turned out to be for Release 14 — it didn't (no existing component, no unused vendored CSS class
for a floating/back-to-top/FAB pattern) — so this one was a genuine new build, not a reuse-and-extend.

**Page-agnostic, unlike Release 14.** The jump nav needed per-page wiring because each page has
different sections and labels. A back-to-top button doesn't — same behavior everywhere — and
`climate-dashboard-react`'s `App.tsx` already wraps every route in one shared shell (`<Header>` /
`<SidebarNav>` / `<main id="main-content">` / `<Routes>` / `<Footer>`), the same shell that already
centralizes route-change title/focus management in one effect rather than duplicating it per page.
So this needed exactly one new `design-system` component plus one line in `App.tsx`, not six
per-page integrations.

### `design-system` component: `BackToTop`

Composed from the existing `Button` (`iconOnly` + `fullRadius` + `iconLeft="chevron-up"` +
`variant="primary"`) rather than custom-styled from scratch — confirmed via the vendored CSS that
`icon-only` + `full-radius` together already render a circular icon button, so no new visual
styling needed inventing. Positioned `fixed`, bottom-right, honoring the same
`env(safe-area-inset-*)` padding `App.tsx`'s shell already applies, with `z-index:
var(--__s9cmpx-z-index-modal)` to clear the sidebar nav's own z-index — the same fix `ChartCard`'s
expand overlay already needed for the same reason, confirmed by grepping this file's own prior
z-index lessons before picking a value. A plain `window` `scroll` listener toggles visibility once
`scrollY` passes a `threshold` prop (400px default) — the first draft rAF-throttled this, dropped
after live Storybook testing showed `requestAnimationFrame` callbacks can simply never fire in a
backgrounded/non-foregrounded test-runner tab, breaking the visibility toggle entirely in that
environment; a plain synchronous `setState` call turned out both correct and more testable, with no
real performance cost worth trading away testability for.

### A real cross-browser scroll bug, found before merge

The first working version called `window.scrollTo({ top: 0, behavior })` directly on click,
matching the plan's draft exactly. Live testing (polling `window.scrollY` over several seconds
after a real click) showed this was a complete no-op under `behavior: 'smooth'` in some of the
browser contexts this app runs in — not slow, not eventually-consistent, genuinely stuck at the
pre-click scroll position indefinitely. `behavior: 'auto'` (instant) worked correctly every time.
Isolated further: `Element.scrollIntoView({ behavior: 'smooth' })` — the mechanism
`scrollToJumpTarget` (Release 14) already uses for JumpLinks — did not share this problem when
tested against a real element with a real position. This was reproducible via direct script
injection and via genuine click-triggered activation alike, ruling out a user-activation-gating
explanation.

Fixed by having `BackToTop` stop calling `window.scrollTo` for its primary path entirely:
`handleClick` now calls `scrollToJumpTarget(targetId, { reduceMotion })` directly whenever a
`targetId` is supplied, reusing Release 14's already-shipped, already-proven mechanism rather than
re-implementing scroll-plus-focus logic a second time with different (and apparently less
reliable) browser behavior. `targetId` stayed optional in the prop type — for API symmetry and
because a truly standalone `BackToTop` with no landmark to point at is a reasonable use elsewhere
— but is effectively required in practice: the one real caller (`climate-dashboard-react`'s
`App.tsx`) always has `#main-content` to target. An instant, non-animated `window.scrollTo(0, 0)`
remains as the fallback for the no-`targetId` case, deliberately not attempting the (now known
unreliable) smooth variant there either.

### Two more issues found by Copilot's review

**A real accessibility bug, found and fixed by Copilot directly.** Activating the button via
keyboard (focus it, press Enter/Space) and landing back below the visibility threshold would
unmount the button — `if (!visible) return null` — while it still held keyboard focus, silently
dropping a keyboard user's focus into the void with nothing announced and nowhere for their next
Tab press to go. Copilot's own fix pushed directly to the PR branch: a `focusWithin` state, set via
`onFocusCapture`/cleared via `onBlurCapture` (checking `relatedTarget` isn't still inside the
wrapper), that keeps the button mounted as long as it still contains focus, independent of
`visible`. Confirmed this doesn't conflict with the `targetId` path's own focus handoff — when a
real `targetId` is given, `scrollToJumpTarget` moves focus to that element as part of the same
click, which is outside the button's own wrapper and correctly lets `focusWithin` go false and the
button unmount once it's genuinely no longer needed; the fix's real value is specifically for the
no-`targetId` fallback case, where nothing else claims focus afterward.

**A smaller test-hygiene fix, also pushed by Copilot.** A Storybook story's `window.matchMedia`
override (forcing reduced motion, for a deterministic click-scroll assertion) was applied once at
render time with no teardown — leaking the stub into every subsequent story run in the same test
session. Fixed with proper Storybook `beforeEach`/`afterEach` story hooks restoring the original
`matchMedia` after each run, rather than a render-time side effect with no corresponding cleanup.

Both of Copilot's fixes were verified correct and merged in by hand alongside this session's own
`scrollToJumpTarget` change — the two touched the same story file in adjacent but
non-conflicting regions (git's automatic merge resolved `BackToTop.tsx` cleanly on its own; only
`BackToTop.stories.tsx` needed manual reconciliation), confirmed via a full re-run of the
Storybook suite (166/166 passing) after combining them.

### `climate-emissions-analysis-project`: one line in `App.tsx`

`<BackToTop targetId="main-content" />` added once in `App.tsx`, outside `<Routes>`.
`targetId="main-content"` deliberately reuses the exact `<main id="main-content" tabIndex={-1}>`
element `App.tsx`'s existing route-change effect already focuses on in-app navigation, so a
back-to-top click lands focus in the same place a normal page navigation already does — one
consistent focus-landing convention, not two. No new `App.test.tsx` was added: `BackToTop`'s own
behavior (visibility toggling, click-scroll-focus, keyboard-focus retention) is already covered by
its own Storybook stories in isolation, and mocking the full page tree, routing, and API layer just
to assert one declarative line would cost more than it proves — verified instead via live browser
testing of the actual wired app.

Sequencing followed the plan exactly: `design-system` PR #32 landed first, then
`climate-emissions-analysis-project` PR #127. Deploy pulled `design-system` before
`climate-dashboard-react` on the Mac Mini for the same reason Release 14's deploy needed the same
order — the app's build failed against a stale `design-system` checkout missing the new
`BackToTop` export until `design-system`'s own checkout was fast-forwarded first.

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first, `vitepreview` LaunchAgent rebuilt/restarted — no `api/` change in this
release, `uvicorn` untouched): the button is absent at the top of the page and appears once
scrolled past the threshold; clicking it moves focus to `#main-content`, confirmed via direct
`document.activeElement` inspection. Real smooth-scroll-animation *completion* wasn't reliably
observable through this session's own browser-automation tooling specifically — a limitation of
that tool in this session (the same class of issue already documented for Release 14's dropped
modified-click Storybook test), not evidence of a problem in the shipped code; the underlying
instant/`'auto'` scroll path, which the automation tool could observe reliably, was separately and
repeatedly confirmed correct before relying on it.

### Post-ship bug report: the button never appeared after a JumpLinks click

Reported directly: on Country Profile, clicking "Emissions" or "Per Capita" (`JumpLinks`, Release
14) scrolled the page but `BackToTop` never appeared; same on Data Explorer's "Summary Statistics"
link. Reproduced live in a real browser session, not assumed.

**Root cause, precisely isolated.** Attached a plain counting `scroll` listener to `window`, then
called `Element.scrollIntoView()` directly (the exact mechanism `scrollToJumpTarget` uses) on an
element far down the page. `window.scrollY` genuinely changed — confirmed past `BackToTop`'s
visibility threshold — but the counting listener recorded **zero** `scroll` events. `BackToTop`'s
visibility toggle is a passive `scroll` listener with nothing else driving it, so with no event to
react to, it never re-checked `scrollY` and never became visible. This is a bug in
`scrollToJumpTarget` itself — shared by every `JumpLinks` click on all six pages, not something
specific to Country Profile or Data Explorer — not in `BackToTop`'s own logic. It hadn't surfaced
during Release 15's own verification because that testing exercised `BackToTop`'s own click handler
and its visibility threshold directly; nothing exercised the case of a *different* component's
navigation being the thing that ought to make it visible.

An initial, flawed test attempt (calling `el.scrollIntoView()` directly from a script, bypassing the
real `scrollToJumpTarget` function entirely) gave a false negative before this was caught and
corrected — a reminder that testing "the mechanism" isn't the same as testing "the actual code path
a real click goes through."

**The fix.** `scrollToJumpTarget` now dispatches a synthetic `scroll` event on `window` immediately
after calling `scrollIntoView` — covering the reduced-motion/instant case, where the scroll position
is already final by that point — and once more on the native `scrollend` event, covering the default
smooth case once the animation has genuinely finished. `scroll` listeners re-read `window.scrollY`
fresh every time they fire, so a synthetic event carrying no real position data is enough to make
any of them re-check. Fixed at the shared `scrollToJumpTarget` utility rather than with
`BackToTop`-specific code, since any other future passive scroll-position observer built on top of
this app's design system would hit the exact same bug.

**A genuine test-environment limitation, documented rather than papered over.** Storybook's own
browser-mode test harness does *not* reproduce the missing-event behavior at all — a raw
`scrollIntoView` call inside that environment fires real `scroll` events reliably, confirmed by
temporarily reverting the fix and re-running the new regression test: it passed either way. This
means the Storybook test alone cannot prove the fix works; the real proof is the direct, live
counting-listener test described above, run in an actual browser session outside Storybook. Still
added the regression story (`BecomesVisibleAfterAJumpLinksNavigationElsewhere`, simulating an
external `scrollToJumpTarget` call and asserting `BackToTop` reacts) for documentation value and as
a partial guard against a future accidental removal of the dispatch code — with this exact
limitation spelled out in a comment directly above the story, rather than presented as a
self-sufficient regression proof it isn't.

**Deploy and post-deploy verification.** `design-system` fast-forwarded on the Mac Mini,
`climate-dashboard-react` rebuilt (bundles `design-system`'s source, so needed rebuilding even
though its own source hadn't changed) and `vitepreview` restarted. Verified live against
`labs.syena.io/ghg-emissions-analysis` with service worker/Cache Storage cleared first: fetched the
deployed JS bundle directly and confirmed it contains the `scrollend` token, proving the fix
actually shipped rather than trusting the build log alone; attached a fresh counting `scroll`
listener and clicked a real Country Profile `JumpLinks` link, confirming the fix's synthetic
dispatch genuinely fires against production on a real click, not just in the earlier isolated test.
Full visual confirmation that the button appears after a real smooth-scroll animation completes
wasn't independently re-observable through this session's own browser-automation tooling — the same
pre-existing limitation already affecting this release's original verification — but every other
link in the causal chain was directly confirmed correct in production.

### Second post-ship bug report: jump targets near the bottom of a page undershoot the top

Reported directly, with a screen recording: clicking a `JumpLinks` link on Country Profile still
left part of the previous section visible above the target — a different symptom from the first
bug report (that one was "the button never appears at all"; this one is "the scroll itself lands
short").

**Root cause, isolated with exact math rather than guesswork.** Measured Country Profile's
`#key-stats` directly against production: it needs `958px` of scroll to reach the top of the
viewport, but the page's total scrollable range (`document.documentElement.scrollHeight -
clientHeight`) is only `732px` — a `226px` shortfall the browser silently clamps to, independent of
whether the scroll animates smoothly, jumps instantly, or anything about *how* it's triggered. The
identical shortfall (`~226px`) reproduced on Data Explorer's `#summary-stats`, and a smaller one
(`116px`) on Overview's `#pct-change` — confirming this wasn't a Country-Profile-specific issue but
a structural one: every page's *last* jump target is close enough to the document's natural end
that there isn't `226px`(ish) of real content left below it to scroll into.

**The fix.** `scrollToJumpTarget` now computes this shortfall before scrolling
(`getBoundingClientRect().top + window.scrollY`, minus the page's current max scroll position) and,
if positive, temporarily appends an `aria-hidden` `<div>` spacer of exactly that height, giving the
target just enough extra room to reach the top. Removed once the scroll settles — on the default
smooth path, on the native `scrollend` event with a 1s fallback timeout; on the reduced-motion
path, a double `requestAnimationFrame` rather than immediate synchronous removal. That last detail
mattered in practice: removing the spacer synchronously (in the same tick as the `scrollIntoView`
call) was tried first, on the theory that an instant scroll's position is "already final" by then —
but confirmed live that it isn't guaranteed to have actually applied to the DOM yet, so removing
the extra room that early let the browser re-clamp the scroll against the now-shorter document,
silently reintroducing the exact bug the fix exists to prevent. Caught this by the same regression
test the fix itself added, not by inspection — reverting to synchronous removal made the test fail
at precisely the original, unfixed shortfall value.

**Copilot's review** caught one more real correctness gap: the shortfall was measured via
`el.offsetTop`, which is relative to the element's `offsetParent`, not the document origin — only
equivalent to `document.body` when no ancestor between the target and `<body>` is positioned. Not
currently a live bug (grepped this app's own components; none of the current jump targets sit
inside a positioned ancestor), but a latent one waiting for a future page to introduce it. Fixed by
switching to `getBoundingClientRect().top + window.scrollY`, correct regardless of DOM nesting.

**A regression test that actually discriminates, confirmed by the same revert-and-rerun check used
for the first bug report's test — with a different outcome this time.** The first fix's Storybook
test (for the missing-`scroll`-event bug) turned out unable to tell fixed from unfixed, because
Storybook's own browser-mode harness doesn't reproduce that particular bug at all. This fix's test
(`ClickScrollsFullyToTopEvenNearPageBottom`) does: reverting the fix and re-running showed the test
failing at exactly `827.8px` (the shortfall in Storybook's own test viewport), and passing (under
`10px`) with the fix restored — genuine, verified regression protection, not just documentation of
intent.

Deployed and verified: both repos fast-forwarded on the Mac Mini, `climate-dashboard-react`
rebuilt, `vitepreview` restarted. Confirmed the exact just-tested build (not a stale bundle) is
what's actually live by matching the deployed script's Vite content-hash filename against the
build's own output. By this point in the session, this session's browser-automation tool's
reliability had degraded further than earlier in the release (even basic click registration, not
just smooth-scroll animation, became inconsistent in the same tab) — real-browser click-through
verification of the visual scroll landing wasn't achievable through that tool this time, a
continuation of the same pre-existing environment limitation, not a code concern.

### Third post-ship bug report: clicking a near-top target still scrolled, for no benefit

The user's clarification of the *first* bug report turned out to describe a genuinely different,
third bug — not "the button never appears" (report one) and not "the scroll undershoots the top"
(report two), but: on Country Profile, clicking "Emissions" or "Per Capita" scrolled the page a
little even though both charts were already fully visible without scrolling at all, just enough to
push the `JumpLinks` nav row itself (and the page's own `<h1>`) out of view, with nothing new
brought into view to justify it. Since the scroll distance was under `BackToTop`'s threshold, the
button never appeared either — leaving no easy way back up except a manual scroll, exactly matching
what the user described watching happen.

**The fix.** `scrollToJumpTarget` now checks, before anything else, whether the target is already
fully contained within the viewport (`rect.top >= 0 && rect.bottom <= window.innerHeight`) and
skips scrolling entirely when it is. Focus still moves to the target either way — a click should
still mean something for a keyboard/screen-reader user even when nothing visually moves. All of the
shortfall-spacer and scroll-event-dispatch logic from the two earlier fixes now lives inside the
"the target actually isn't fully visible yet" branch, otherwise unchanged.

**Three attempts at a regression test, and a genuinely useful discovery about the test harness
itself along the way.** The first attempt set up its "already visible" precondition with a raw
`scrollIntoView({ block: 'start' })` call, then asserted position didn't change after the real
click — but passed regardless of whether the fix was present, because `block: 'start'` positions
the target at *exactly* the same spot a buggy click handler would also produce; there was nothing
left for the assertion to distinguish. Investigating why led to a second, more useful discovery: a
diagnostic dump of `document.body.children` showed this Storybook browser-mode test harness doesn't
unmount previous stories' rendered DOM between `play`-function runs within the same file — every
earlier story's own content (and scroll position) silently accumulates in `document.body`, so
nothing genuinely starts "at the top of the page" by default. This had likely been quietly
corrupting `rect.top`/`offsetTop` measurements throughout this whole release's testing without ever
being caught, since every earlier test either didn't care about absolute position or used spacers
generous enough to swamp the effect. The working version establishes its precondition with
`block: 'center'` instead (leaving genuine room both above and below the target, so a real bug is
actually distinguishable from the fix) combined with forcing reduced motion for deterministic
timing. Confirmed by reverting the fix and re-running: fails at exactly the wrong scroll position
(`866` → `1298`, precisely what a `block: 'start'` scroll would produce) without it, passes with it.

Deployed and verified live directly against the reported scenario, not just inferred from the fix
logic: on production, clicking "Per Capita" on Country Profile now leaves `window.scrollY` at `0`
(read directly, not assumed) while `document.activeElement` confirms focus still correctly lands on
the target. The "Key Statistics" case (the one that genuinely needs to scroll, from the second bug
report) still correctly updates the hash and moves focus on production — the visual scroll
animation itself remained unobservable through this session's own degraded browser-automation
tooling by this point, the same pre-existing limitation noted for the two earlier fixes, not a gap
in what actually shipped.

### Fourth post-ship bug report: "skip scroll when visible" needed an exception for later sections

The user confirmed the third fix worked as intended, but wanted one more allowance: a section that
*isn't* the page's top section should always scroll to the top when its link is clicked, even if it
happens to already be visible — otherwise the link looks broken, like it isn't pointing anywhere.
Two concrete examples: Country Profile's "YoY Change" (the 3rd of 4 jump items) and Historical
Trends' "GHG Share by Decade" (the 2nd and last item). Both had inherited the third fix's
"already-visible → skip" behavior even though neither is genuinely the page's top section — they
just happened to already be on screen, which the third fix's own logic couldn't tell apart from
actually being the top.

**The first attempt at fixing this was itself wrong — caught before the user ever saw it, purely
through this session's own habit of live-verifying immediately after every deploy.** It defined
"top section" geometrically: a target counts if its document-relative position is less than
`window.innerHeight`, i.e. "would this be visible with zero scrolling." Every Storybook test
passed. But testing it live on production immediately after deploying (part of this session's
standing verification routine, not a special extra step taken because something felt off) turned up
a direct counterexample: on a perfectly ordinary 1920x963 desktop viewport, Country Profile's "YoY
Change" sits only 604px down the page — comfortably inside a 963px-tall viewport — so it still got
classified as top-section and its link still did nothing. The very fix meant to resolve the bug
report reproduced the bug report, on the exact example the user had named.

**The corrected fix (`design-system` PR #37) treats "top section" as a structural fact instead of a
geometric one.** Only `items[0]` — literally the first entry in a page's `JumpLinks` array, the one
that renders immediately after the page's `<h1>` — is ever eligible to skip its scroll when already
visible. Every other item always scrolls flush to the top when clicked, full stop, regardless of
whatever viewport happens to already have it in view. `scrollToJumpTarget` now takes an explicit
`isTopSection` option instead of inferring one, set by `JumpLinks`' own click handler as `item.id
=== items[0]?.id`. Callers that don't pass it at all — `BackToTop`'s own click handler, and a
page's hash-on-load effect — always scroll unconditionally, which is correct for both: "back to
top" always means go all the way, and a freshly loaded page with a `#anchor` already in its URL
should just land there, the same as the browser's own native hash-scroll would.

Both regression stories were rewritten around this structural definition — `overview` (items[0])
must not scroll when already visible; `research` (a later item) must always scroll to top even when
already visible — and confirmed to genuinely discriminate against the *first, flawed* attempt's
geometric code (both fail against it), not just against the pre-fourth-fix baseline. Deployed and
verified against both of the user's own named examples: "YoY Change" now reaches `scrollY = 556`
with `BackToTop` appearing; "GHG Share by Decade" now scrolls where it previously did nothing.

### Anchor-placement bug report: "By Country"/"Country Comparison" should land on the picker

Reported alongside the fourth bug: on Overview, the "By Country" jump target sits on the section's
own `<h2>`, but the country picker that section actually needs — shared with the "% Change" section
further down — sits *above* that heading, not below it. Confirmed with exact document-position
math against production: the heading sits at y=728, the picker at y=656, 72px above. Scrolling the
heading to the top of the viewport (exactly what the anchor was doing) leaves the picker 72px
*above* the fold, scrolled out of view — the one control a user actually needs after following the
link ("I want to change my selection") isn't reachable without an extra manual scroll up, which
defeats a good chunk of the point of having a jump link there at all. Scenario Comparison's
"Country Comparison" target got the identical treatment for consistency, even though its own picker
already sat close to (just below, not above) its own heading.

Fixed in `climate-dashboard-react` (PR #128): moved the `id` from each page's `<h2>` heading onto
the `country-picker-row` div itself, in both `OverviewPage.tsx` and `ScenarioComparisonPage.tsx`.
Both picker rows were already unconditionally rendered (never gated behind a selection state, same
as the headings they replaced as anchor targets), so no existing test needed to change — the
existing assertions only checked that the target `id` exists somewhere in the DOM, not where.
Deployed and verified live: Overview's "By Country" now lands with the "Select countries" picker
flush at the top of the viewport, with the "By Country" heading and its chart both visible right
below it.

### Fifth post-ship bug, found by accident while verifying the fourth: the shortfall spacer's own cleanup silently undid the fix it was cleaning up after

While live-verifying that "GHG Share by Decade" now scrolls (the fourth fix, above), direct
`scrollY` polling over the course of the scroll caught something the earlier position-only
snapshots had never caught: `scrollY` genuinely reached the intended flush-to-top position (`671`,
with the second fix's shortfall spacer from Release 15's earlier work still in place) — and then,
the instant that spacer was removed on `scrollend`, snapped straight back down to `255`. That's the
exact "previous section stays visible" bug the second fix (the shortfall spacer, described earlier
in this release) exists to prevent, reproduced live on the very page that originally motivated it.

**Root-caused as structural, not a timing race — the kind of bug no amount of waiting longer before
removal could have fixed.** Removing a spacer that is the *only* thing making a target's position
reachable will always make the browser re-clamp `scrollY` back down, because `scrollTop` is
continuously clamped to `[0, scrollHeight - clientHeight]` as the document resizes — true no matter
how long the code waits first. The original regression test (`ClickScrollsFullyToTopEvenNearPageBottom`,
from the second fix) only ever looked correct because its own assertion happened to run before the
scheduled removal fired; it was never actually testing the state that mattered.

**The fix (`design-system` PR #38): stop removing the spacer on any timer or event at all.**
Instead, it's reclaimed lazily — at the very start of the *next* jump, tracked via a module-level
`activeSpacer` variable, cleaned up right before deciding anything about the new jump. The
reasoning: a scroll adjustment as a side effect of the user's *own next click* isn't surprising the
way one appearing out of nowhere, seconds after they'd already moved on, would be. A new regression
test (`ClickStaysFlushToTopAfterScrollSettles`) dispatches a real `scrollend` event and then waits
past the *old* 1-second fallback-removal window before asserting the position still holds — proving
the fix holds over time, not just for one lucky instant right after the click. Confirmed genuinely
discriminating by reverting to the old removal-on-settle logic and re-running: fails at `827.9`
(reclamped back down), passes with the fix.

**Two follow-up commits pushed by Copilot's review during this PR's own review cycle — one reverted,
one kept, both independently verified rather than taken on faith.** The first tried to improve on
the fix's one real cosmetic tradeoff (a small amount of blank scrollable space can linger below a
page's last section until the user's next jump) by proactively reclaiming the spacer via a
persistent `window` `scroll` listener, torn down once the user scrolls back to a position that's
valid without it. Pulling the commit and running `BackToTop.stories.tsx` in isolation — not
combined with `JumpLinks.stories.tsx`, so this wasn't just the familiar cross-story DOM-accumulation
quirk — surfaced a real regression: a listener armed by one story's spacer stays registered on
`window` past that story's own lifetime (this harness doesn't unmount between stories), and when a
later, unrelated story dispatches its own synthetic `scroll` event, that stale listener fires,
removes its spacer, and the resulting document resize re-clamps `scrollY` synchronously — before
`BackToTop`'s *own* visibility listener, registered on that same event, gets a chance to read the
value. The button silently never appears. This is the identical class of bug the whole PR exists to
fix, just relocated from a one-shot timed removal into a longer-lived global listener with more
surface area for exactly this kind of cross-listener interference. Reverted with a PR comment
explaining the mechanism, then re-requested review on the reverted state rather than layering a fix
for the new bug on top of the change that caused it.

Copilot's second commit was unrelated to any of that: switching one story's `userEvent.click(...)`
to a raw DOM `.click()` call, since Playwright's `userEvent.click` can auto-scroll a target into an
interactable position *before* clicking it, which would contaminate that story's own
"scroll shouldn't have moved" assertion for reasons that have nothing to do with the app's actual
click-handling logic. This commit didn't touch the reverted source file at all — verified
independently anyway (`tsc`, the full `JumpLinks`/`BackToTop` story suite, and the project's full
`npm run test`, 193/193) before merging.

Deployed and verified: the spacer-plus-instant-scroll mechanics were confirmed directly against
production by manually replicating `scrollToJumpTarget`'s exact math and calling `scrollIntoView`
with `behavior: 'auto'` — the target landed exactly flush (`scrollY = 672 = targetY`) and held there
1.2 seconds later, spacer still present. The `smooth`-animation path itself remained unobservable
through this session's own browser-automation tooling — confirmed separately, on the same tab, that
`behavior: 'auto'` scrolls correctly and instantly, isolating the gap to that tool's already-known
inability to progress `smooth` scroll animation frames (not a defect in what shipped), the same
pre-existing limitation noted throughout this release.

### Sixth post-ship refinement: items[0]-only was too strict for a genuine second neighbor

Reported directly, once the fourth fix (above) had shipped and was confirmed working for "YoY
Change" and "GHG Share by Decade": Country Profile's "Per Capita" chart sits stacked directly under
"Emissions" -- close enough a neighbor that scrolling it to the top while both charts are already
visible just hides the nav for no benefit, exactly the same reasoning the fourth fix's
`items[0]`-only rule had already been built on. Restricting "skip if already visible" to strictly
`items[0]` turned out to be one section too strict for this specific page's layout.

**Why this couldn't just be solved with better geometry, again.** A purely geometric check can't
tell "a later section that happens to fit this particular viewport" apart from "a genuine neighbor
of the top section" -- both are just a document position measured against a viewport height, and
the fourth fix in this same release had already demonstrated, live, exactly how that goes wrong
(the "YoY Change" / 1920x963 viewport counterexample). Whatever rule handles "Per Capita" correctly
by geometry alone would need to also *not* apply to "YoY Change" under the same geometric
conditions -- and there's no fact about either target's raw document position that distinguishes
the two on its own.

The user raised the natural follow-on question directly: what about a mobile viewport, where "Per
Capita" is genuinely below the fold because "Emissions" alone fills the whole screen? Any fix here
has to still scroll normally in that case, not just skip unconditionally because the section
happens to be "adjacent" in some structural sense.

**The fix (`design-system` PR #39): an explicit per-item opt-in instead of another inference
attempt.** Adds `JumpLinkItem.topSection`, set by whichever page author knows a later item is a
close neighbor of the actual top section -- Country Profile's `JUMP_ITEMS[1]` ("Per Capita") is the
one place across the whole app this gets set (`climate-emissions-analysis-project` PR #129); every
other page's jump items are untouched, still defaulting to the fourth fix's `items[0]`-only
behavior. Critically, the flag only widens *eligibility* for the existing `alreadyFullyVisible`
runtime check -- it doesn't replace or bypass that check. This is what answers the mobile question
for free: on a narrow/short viewport where "Per Capita" is genuinely off-screen, the same
visibility check that already handles every other target on every other viewport correctly decides
to scroll, with no separate mobile-specific branch needed anywhere.

Two new regression stories cover both directions of this behavior, using a items array where only
the *second* item (not the first) carries the flag, to prove the split is driven by the flag
itself and not by list position: one confirms the marked item skips its scroll while already
visible -- confirmed genuinely discriminating against the pre-flag code by reverting and
re-running (fails at `470` vs. an expected `38`, passes with the fix) -- the other confirms the
same marked item still scrolls normally once it's genuinely not visible.

Deployed and verified live on production: "Per Capita", fully visible on a real 1920x963 viewport
(rect spanning 254px to 588px, well within the 963px viewport height), no longer scrolls when
clicked -- `scrollY` stays at `0`, confirmed by direct measurement before and after the click, with
focus still correctly landing on the target. With the page pre-scrolled so "Per Capita" was
genuinely off-screen, the underlying scroll-to-target mechanics were confirmed correct via the same
instant-scroll verification technique used earlier in this release (this session's browser-
automation tool still can't reliably progress a real `smooth`-scroll animation to completion, the
same already-documented environment limitation, not a gap in what shipped).

### Seventh post-ship bug report, with screenshots: BackToTop stranded below the footer

Reported directly, with screenshots: jumping to Overview's last section ("% Change") opened a
large blank area beneath the page's real content, and the floating "Back to top" button rendered
well below the footer, visibly detached from it -- floating alone in otherwise-empty space rather
than anywhere near the page's actual last piece of content.

**This is a direct, previously-unaddressed consequence of the fifth fix's own design, not a new
bug in unrelated code.** The shortfall spacer `scrollToJumpTarget` uses to bring a short page's
last jump target flush to the top is deliberately never auto-removed -- that fix's entire point was
that removing it re-clamps `scrollY` back down, a worse bug than a little extra scrollable space.
Confirmed live before writing anything: Overview's `#pct-change` spacer measures `348px`, and
scrolling fully into the gap it leaves puts the footer's `bottom` edge at `-1082px` -- deep
off-screen above the viewport. `BackToTop` is `position: fixed`, so it kept rendering at its
normal viewport-anchored bottom-right spot regardless of any of this, which is exactly correct
*in isolation* -- the button doesn't know or care how tall the document is -- but the net visual
effect, once the document has this much unexpected trailing empty space, is a button that looks
lost, floating nowhere near any real content.

**The fix (`design-system` PR #40): a new optional `BackToTop.avoidSelector` prop.** Once the
element matched by the selector -- in this app, the real `<footer>` `Footer` itself renders -- has
its top edge rise above the viewport's bottom edge, the button's `bottom` offset grows to keep it
docked just above that edge instead of the raw viewport edge. Critically, this offset keeps
growing as the user scrolls *further* into the gap (past where the footer's own top edge was),
which means the button eventually scrolls out of view entirely once even the footer itself has
scrolled past -- rather than staying visually pinned in the middle of pure empty space forever,
which would arguably have been just as disorienting as the original bug. Wired into
`climate-dashboard-react`'s one `<BackToTop>` instance (PR #130) as
`avoidSelector="footer"`, matching `Footer`'s own real `<footer>` element -- no page-specific
wiring needed, since `BackToTop` is mounted once in the shared app shell.

**Copilot's review caught a real, if subtle, math error before this ever shipped.** The initial
implementation computed `dockOffset` as `window.innerHeight - avoidRectTop + DOCK_GAP_PX`, then
added that directly on top of the button's existing 24px base bottom margin -- double-counting the
base margin, so the button ended up docking a full 24px higher above the footer than intended.
Still functionally correct (the button never actually overlapped the footer, satisfying the
original bug report), but the gap ended up 40px instead of the intended, deliberately-chosen 16px.
Copilot's fix subtracts the base offset back out of the `dockOffset` calculation so the two don't
stack. Pulled the commit and verified independently rather than trusting it on its own say-so
(this session's established practice after catching two earlier bot-introduced regressions this
same release): `tsc`, the full `BackToTop`/`JumpLinks` Storybook suite (17/17), and the project's
full `npm run test` (197/197) -- all clean, no new failures, before merging.

Two new regression stories cover the fix directly: one confirms the button's bottom edge never
renders below the footer's top edge once scrolled into the gap -- confirmed genuinely
discriminating against the pre-fix code by reverting and re-running (`876` vs. an expected `804`,
a 72px overlap, without the fix) -- and, after Copilot's correction, additionally confirms the gap
is close to the intended 16px rather than an inflated 40px. A companion story confirms the prop
only ever pulls the button *up* -- it stays at its normal position when the avoided element isn't
anywhere near the viewport yet.

Deployed and verified live against the exact reported scenario: on production, jumping to
Overview's `#pct-change` and forcing the scroll to its fully-settled position (the same
instant-scroll technique used throughout this release to work around this session's own inability
to reliably observe a completed `smooth`-scroll animation) shows the button's bottom edge at
`y=542` and the footer's top edge at `y=558` -- a clean, exact `16px` gap, with the button visibly
docked just above the footer rather than stranded in empty space well below it.

### Eighth post-ship fix: stop leaving blank space past the page's real content at all

The seventh fix (above) treated a symptom -- `BackToTop` rendering inside the blank gap a short
page's shortfall spacer leaves below the footer -- without touching the gap itself. Once that
symptom was fixed and the user could see the actual page again, the gap was still there and still
looked wrong: reported directly, with screenshots, jumping to a short page's last section (e.g.
Historical Trends' "GHG Share by Decade") pulled it flush to the very top, leaving a large blank
area below the real content, with the footer scrolled far out of view above it. The user asked the
more fundamental question directly: could the scrolling instead be controlled so the footer always
stays at the bottom of the page?

**Root cause, traced back to the second post-ship fix earlier in this release.** The shortfall
spacer that fix introduced exists specifically to defeat the browser's own scroll clamp --
`scrollTop` is naturally bounded to `[0, scrollHeight - clientHeight]` -- so that a target could
always reach exactly flush-to-top even on a page too short to naturally support that. That was the
right fix for the bug it was solving at the time (part of the previous section staying visible
above the target), but it came with a cost that only became fully visible once `BackToTop` was
also docking against the footer correctly: forcing the scroll further than the page's real content
genuinely extends, at all, is what creates blank space in the first place. There was no way to keep
"target always flush at top" and "never show blank space below real content" simultaneously on a
page short enough that the two goals conflict -- something had to give, and the user's own priority
was now clear.

**The fix (`design-system` PR #41): delete the spacer mechanism, don't resize it.** Once nothing
artificially extends `scrollHeight`, the browser's own native clamp already does exactly what's
wanted -- the page scrolls exactly as far as its real content allows, landing the footer at the
bottom with nothing past it. This is a case where the "right" fix was to remove a whole mechanism
rather than patch it further: it also deleted a meaningful chunk of accumulated complexity that
existed only to manage that mechanism's own lifecycle (the module-level `activeSpacer` tracking
and its lazy-reclaim-on-next-jump logic from the fifth fix, several paragraphs of comment
explaining exactly why removing a spacer any other way re-clamped scroll -- all of it moot once the
spacer doesn't exist to begin with).

The two regression tests written specifically to prove the spacer stayed in place
(`ClickScrollsFullyToTopEvenNearPageBottom`, `ClickStaysFlushToTopAfterScrollSettles`) were, by
definition, now testing behavior being deliberately removed -- replaced with one test proving the
opposite (`ClickNeverScrollsPastTheDocumentsNaturalEnd`), confirmed genuinely discriminating by
reverting the fix and re-running: a spacer gets created when none should exist. `BackToTop.avoid
Selector` from the seventh fix was kept, not reverted alongside the mechanism that originally
motivated it -- it's independently useful general "dock above the footer" behavior for any deep
scroll, not specific to the spacer bug. Copilot's review was clean (one informational note about
the public API's behavior change, already stated directly in the PR description), independently
re-verified (typecheck, full `JumpLinks`/`BackToTop` story suite, full `npm run test` -- 196/196)
before merging.

Deployed and verified live against the exact reported scenario: on Historical Trends, forcing the
scroll to "GHG Share by Decade"'s fully-settled position shows `scrollY` (`294`) exactly equal to
the document's own natural max scroll, with the footer's `bottom` edge (`905px`) landing right at
the viewport's own bottom edge (`913px` -- the 8px gap consistent with ordinary layout rounding,
not a leftover spacer) -- confirmed both by direct measurement and visually, via screenshot: no
blank space past the footer, no spacer left in the DOM.

### Ninth post-ship bug report: BackToTop never appears on a page short enough to stay under threshold

A direct, immediate consequence of the eighth fix, reported the moment it could actually be
observed: on Historical Trends, clicking "GHG Share by Decade" now correctly scrolled down at
all -- the eighth fix's whole point -- but the "Back to top" button still never appeared. Not a
new, unrelated bug so much as an old one finally becoming visible: Historical Trends' entire
natural scroll range is only `~294px`, comfortably under `BackToTop`'s `400px` default
`threshold`. The now-removed shortfall spacer used to inflate `scrollY` well past that threshold
as an incidental side effect on every short page, which had been silently masking, this whole
release, that the button's raw-pixel-only visibility check could never fire on a page this short
at all -- not "rarely," not "only right at the edge," but *never*, for any scroll position,
including the genuine bottom.

**The fix (`design-system` PR #42): a second, independent visibility trigger.** Alongside the
existing `scrollY > threshold` check, the button now also becomes visible once `scrollY` reaches
the document's own natural maximum (`scrollHeight - clientHeight`), regardless of how few pixels
that represents. The reasoning: a user who has genuinely scrolled to the end of a page's real
content -- however short that page happens to be -- has a legitimate reason to want a quick way
back to the top, and "how many raw pixels did that take" isn't really the thing that reason
depends on.

**Writing a regression test for this surfaced a second, smaller lesson about this same test file's
own environment.** The first draft of the new story rendered a modest 150px spacer below the
button and scrolled to the resulting "natural bottom" -- and passed identically whether the fix
was present or not, a silent vacuous pass. A diagnostic dump (rather than an assumption) showed why
directly: in this exact test environment, that layout produced a `scrollHeight` of `900px` against
a `clientHeight` of `900px` -- zero actual overflow, so the test's own "skip if the environment
doesn't reproduce a real natural bottom" safety valve was firing silently, every single run,
rather than exercising anything. Fixed by using enough content (`1500px`) to guarantee real
overflow regardless of this particular test's own layout quirks, combined with deliberately setting
`threshold` to an unreachable `100000` -- which meant the *size* of the natural overflow no longer
needed to precisely mirror a real short page's numbers, only needed to be reliably nonzero, to
correctly isolate the new trigger from the old pixel-based one. Confirmed genuinely discriminating
afterward by reverting the fix and re-running: the button never appears against the old code, even
scrolled to the real, now-guaranteed-nonzero bottom.

Copilot's review was clean -- confirming the `naturalMaxScroll > 0` guard's purpose (skip
non-scrollable pages), the `-1` pixel tolerance's consistency with the same sub-pixel rounding
tolerance the footer-docking logic (v44) already established elsewhere in this file, and that
`scrollHeight`/`clientHeight` are read fresh inside the scroll callback rather than captured stale
from outer scope -- independently re-verified anyway (typecheck, full `JumpLinks`/`BackToTop`
story suite -- 17/17, full `npm run test` -- 197/197) before merging.

Deployed and verified live against the exact reported scenario: on production, forcing the scroll
to "GHG Share by Decade"'s settled position on Historical Trends now shows the button present at
`scrollY: 184` -- well under the `400px` threshold, confirming the new "at natural bottom" trigger
is what's actually firing, not a coincidental crossing of the old pixel check -- confirmed
visually via screenshot, alongside the eighth fix's own footer-flush-at-bottom result in the same
view: no blank space, footer at the true bottom, button correctly present and docked in its normal
corner position (not needing `avoidSelector`'s docking adjustment at all here, since nothing is
past the footer to avoid).

## Release 16 — Dependency Maintenance from the 2026-08-11 Infra Audit

A `/security-infra-audit` run against the Mac Mini deployment (published as an Artifact, later
updated in place as findings were resolved) flagged two Medium-severity dependency findings --
real CVEs, both confirmed to have no exploitable path in this app as actually built and used --
alongside a host-level finding (AirPlay Receiver reachable on the LAN) that's intentionally not
narrated here, since this project's docs track the app/curriculum itself rather than host-specific
infrastructure checks.

**Backend** (`pip-audit`): roughly 60 advisories, every one landing in `jupyterlab`,
`jupyter-server`, `mistune`, `pillow`, `GitPython`, `pytest`, and `setuptools` -- none imported
anywhere in `api/` or `app.py`, and no Jupyter server actually running on the host. `fastapi` and
`uvicorn`, the packages that matter for the deployed service, came back clean. Five of the flagged
packages aren't in `requirements.txt` at all -- they're transitive, pulled in by `nbconvert`,
`matplotlib`, `streamlit`, and `jupyterlab`/`notebook` respectively -- and each of those real
requirers already permits the fixed version via an open-ended constraint, so clearing each CVE
was just a matter of adding a new explicit floor pin rather than touching anything that pulls it
in. `jupyterlab` itself needed one extra bit of care: `notebook==7.5.6` caps it at `<4.6`, so the
fix raises the floor to `jupyterlab>=4.5.10` (the 4.5.x line's own fix) rather than jumping to
`4.6.2`, which would have forced bumping `notebook` too for no real reason. `pytest==8.3.4 ->
9.0.3` is the one genuine major-version bump in the set -- checked first against pytest's own
changelog and this repo's actual test usage (no removed APIs touched, no `pytest.ini`/
`pyproject.toml` config section to migrate at all), then verified for real: the full `api/tests`
suite passed 104/104, and `week1_eda.ipynb` executed end-to-end via `jupyter nbconvert --execute`
with no errors, confirming the upgraded `jupyterlab`/`notebook`/`nbformat`/`ipykernel`/`mistune`/
`pillow` toolchain still cooperates for real notebook execution, not just at the import level.

**Frontend** (`npm audit`, `climate-dashboard-react/`): `react-router-dom` 7.18.1 carried a High
advisory (GHSA-qwww-vcr4-c8h2, an RSC-Mode CSRF bypass), plus five transitive build-tool packages
(`undici`, `nanoid`, `postcss`, `fast-uri`, `brace-expansion`) that don't appear in `package.json`
at all. Confirmed directly in `src/main.tsx` that this app uses plain `<BrowserRouter>`, not React
Router's framework/RSC mode -- the specific code path the advisory describes was never reachable
here. `npm audit fix --dry-run` confirmed every one of the 6 advisories resolves inside the
existing lockfile's own semver constraints (react-router-dom's fix, 7.18.2, sits inside the
already-declared `^7.18.1`), so the real fix needed no `--force` and no `package.json` edit at
all -- `npm audit fix` alone updated `package-lock.json` only. Verified afterward: `npm test`
90/90, `npm run build` succeeded, `npm run lint` produced no new warnings (the two pre-existing
ones are unrelated to this change).

Both `pip-audit` and `npm audit` re-ran clean locally after the fixes, and the audit Artifact was
updated in place to mark both findings Resolved -- the same before/after-evidence treatment
already used earlier the same day for the AirPlay Receiver finding. Shipped as
`climate-emissions-analysis-project` PR #131, mentor-reviewed and merged (never self-merged), then
deployed to the Mac Mini per this project's standard deploy-after-merge convention --
`pip-audit`/`npm audit` re-ran clean there too, not just in the local checkout, and the live site
was confirmed responding correctly through the tunnel afterward.

## Release 17 — Sovereign-Scope Gas Coverage & Historical `scope` Parameter

Prerequisite `api/`-only work for the MCP server sub-project now underway at
`services/mcp-server/` (design doc brought into the repo and implementation started after this
release shipped — see `services/mcp-server/SPEC.md` and its own `ENHANCEMENTS.md`), which wraps
this project's REST API as a set of hand-curated MCP tools for a future conversational agent.
Defining that tool set surfaced two real gaps in this API's historical-data coverage, worth
fixing regardless of whether the agent project ever ships, since both changes are ordinary
`api/` improvements on their own.

**The gap.** `load_raw_sovereign()` -- the loader backing `/overview`'s "All Countries" tier --
carried only `co2`. `load_raw()` (the ~40-country "expanded" pool) already carried `methane` and
`nitrous_oxide` too, an inconsistency nobody had needed to close until an agent tool wanted
"decade methane composition for every sovereign country" and hit a wall. Separately, neither
`/historical/timeseries` nor `/historical/decade-composition` had any concept of scope at all --
both silently resolved against the expanded ~40 only, regardless of what a caller might actually
want.

**Fix 1: three-gas sovereign loader.** `load_raw_sovereign()`'s `usecols` extended to
`["country", "year", "co2", "methane", "nitrous_oxide", "iso_code"]` -- same `iso_code.notna()`
filter, same `year >= 1990` range, additive columns only. Before touching it, every consumer was
traced directly rather than assumed safe: `/overview` is the loader's sole caller, and every
touchpoint there (`_tier_metrics`'s `.sum()`/`.groupby(...)["co2"]`, the world-map and
headline-movers blocks) explicitly selects the `co2` column only -- the two new columns are
genuinely inert for it. `/overview/world-map-series` was checked separately and confirmed to use
a fully different loader (`load_world_map_series()`, reads `owid-co2-data.csv` directly with its
own narrower `usecols`), untouched by this change regardless.

**Fix 2: `scope` on both historical endpoints, not just one.** A new
`scope: Literal["featured", "expanded", "sovereign"] = "expanded"` parameter, added via a small
shared `_scoped_pool()` helper in `historical.py` rather than duplicating the same three-way
branch in both route handlers. `featured`/`expanded` still read `load_raw()` exactly as before
(`featured` filtered further to `FEATURED_COUNTRIES`); `sovereign` reads the now-three-gas
`load_raw_sovereign()`. The original design for this change only proposed adding `scope` to
`/historical/timeseries` -- verifying it against the actual code before implementing (rather than
just inserting what was proposed) surfaced that `/historical/decade-composition` shares the
identical expanded-only limitation, and already aggregates all three gases, so it would have been
left as a near-identical gap for a second follow-up change with no stated reason to exclude it.
Extended to both endpoints in this same change instead.

`"expanded"` as the default matters for backward compatibility specifically: it's the pool both
endpoints already implicitly served before `scope` existed. `climate-dashboard-react/src/api/
client.ts` was checked directly (not assumed) to confirm neither endpoint's client function even
accepts a `scope` argument today, let alone sends one -- so every existing dashboard call resolves
identically to before. The two endpoints' no-`countries` fallbacks diverge in a way worth being
explicit about: `get_timeseries`'s fallback (`FEATURED_COUNTRIES[:5]`) stays scope-independent,
since those five countries exist in all three pools; `get_decade_composition`'s fallback (already
"the whole pool" before this change) now means "the whole *selected-scope* pool" -- a direct
generalization of its prior behavior, not a new rule.

**`/countries` gains a `sovereign` field.** Alongside the existing `featured`/`expanded` lists,
`/countries` now returns the full ~218-country sovereign name list. This wasn't part of either
change above, but both the MCP design doc and this change's own planning flagged the same gap
independently: a future agent-facing country-resolution guard needs a real canonical name list to
validate a `scope=sovereign` query against, and `/countries` previously exposed only the ~40
expanded names -- a sovereign-scope query couldn't even be spelling-checked. Small and cheap to
add now (`load_raw_sovereign()["country"].unique()`) rather than deferring it to a third near-term
follow-up touching the same files. One real behavior change worth flagging: `/countries` can now
503 on a missing raw CSV, which it structurally couldn't before this field existed (the
`featured`/`expanded` fields never depended on that file).

**Testing.** New `load_raw_sovereign()` unit test (methane/N₂O values spot-checked against the
fixture, not assumed correct); `scope` tests for all three values on both historical endpoints,
each paired with an explicit "no `scope` sent -> byte-identical response to before" case; a
`/countries` test for the new `sovereign` field and its new 503 path. Every new/changed test was
independently confirmed to actually discriminate old from new behavior -- reverting the source
changes (`git stash`) and re-running showed 4 tests fail with exactly the expected error shapes
(a `KeyError: 'methane'` for the loader test; empty-series/mismatched-response assertions for the
scope tests), not just re-running green against the new code and trusting that. 112/112 tests pass
overall (8 new/changed). Live-smoke-tested afterward against real local data, not just fixtures:
`scope=sovereign&countries=Bhutan&gas=methane` returns real methane figures for a country entirely
outside the ~40-country expanded pool; a no-`scope` call for China returns the same 35 data points
as before the change.

Shipped as `climate-emissions-analysis-project` PR #133, mentor-reviewed and merged. Per updated
guidance from the repo owner (2026-08-12), this documentation itself was committed straight to
`main` rather than going through its own PR -- doc-only updates no longer need the branch+PR+review
cycle that code changes still do.

**Follow-up (PR #134, Shipped): `get_timeseries`'s no-`countries` default widened to the full
`FEATURED_COUNTRIES`.** Found while reviewing this release for the MCP server sub-project: the
React frontend's country picker already seeds itself with all 10 `FEATURED_COUNTRIES` (a prior
fix to a 5-vs-10 inconsistency) and always sends `countries` explicitly, so the backend default —
still a `FEATURED_COUNTRIES[:5]` slice, five countries, dating from before the featured list grew
to 10 — was a straggler nobody was actually exercising except a bare unparameterized `GET`. Fixed
to `FEATURED_COUNTRIES` (all 10), matching the frontend. Also adds a pinning test,
`test_timeseries_default_countries_ignores_scope`, documenting a separate, pre-existing (not new)
behavior surfaced during the same review: `scope` has no observable effect on this endpoint's
no-`countries` default path, at either list size — the fallback is a fixed name list, not a
scope-aware pool, unlike `get_decade_composition`'s no-`countries` default (which does aggregate
the whole selected-scope pool). Confirmed via `mcp-server-spec.md` §3.2 that no real caller hits
this combination: the MCP tool layer always resolves and ranks its own country list before
calling this endpoint, never omitting `countries` to lean on the API's own default. Not a bug —
recorded so a future change to this endpoint's default doesn't have to re-discover it. 113/113
tests pass.

## Release 18 — Per-Capita / YoY Growth / Per-GDP Fields on `GET /historical/timeseries`

**Status: Shipped.** Written up before implementation started, per the project's docs-first
convention; revised below to mark shipped now that it's merged and deployed.

**The gap.** MCP server testing surfaced that multi-country historical comparisons need richer
data than raw gas values — the agent kept falling back to N calls to the single-country
`/country_profile` endpoint (which has per-capita/YoY/intensity) instead of one call to the
multi-country `/historical/timeseries` endpoint (which doesn't). Root-caused to a real data gap
in `/historical/timeseries` itself, not an MCP-layer tool-calling bug.

**The fix.** Three new fields on each `TimeseriesSeries` — `per_capita`, `yoy_pct_change`,
`per_gdp` — sourced verbatim from columns already present in `data/owid-co2-data.csv`:
`{gas}_per_capita`, `co2_growth_prct`, `co2_per_gdp`. No new derivation, no risk of drifting from
the notebooks. `per_capita` is populated for all three gases; `yoy_pct_change`/`per_gdp` have no
OWID methane/nitrous_oxide equivalent, so they're `None`-filled (same length as `years`) whenever
`gas != "co2"`.

**Explicitly distinct from two similarly-named existing fields.** `co2_per_gdp` (CO2-only carbon
intensity, straight OWID passthrough) is a different metric from `ghg_features.csv`'s
`ghg_intensity` (`total_ghg/gdp` across all three gases, computed in `week2_features.ipynb`,
consumed by `country_profile.py`) — confirmed numerically different (China/2020: 0.451 vs
0.5186). Likewise the new `yoy_pct_change` (straight `co2_growth_prct` passthrough) differs from
`country_profile.py`'s independently-computed `co2_yoy_pct_change` (`pct_change()` on
`ghg_features.csv`'s `co2`, different formula/semantics). Both new fields keep their own names
(`per_gdp`, `yoy_pct_change`) rather than reusing the existing ones, to avoid conflating two real,
differently-sourced numbers.

**Scope.** `/historical/timeseries` only — `/historical/decade-composition` returns a
cross-country aggregate with no per-country rows, so none of this applies there.

**Loader changes.** `load_raw()`/`load_raw_sovereign()`'s `usecols` extended with the 5 new
columns. Traced before implementing: `load_raw()` is used only by `historical.py`;
`load_raw_sovereign()`'s other callers (`countries.py`, `overview.py`) read unrelated columns
only — the new columns are inert everywhere except `historical.py`.

**NaN handling.** `dropna(subset=[gas])` only guarantees the *requested gas* column is non-null
per row — not `per_capita`/`co2_growth_prct`/`co2_per_gdp`, which can be independently missing
(e.g. `co2_growth_prct` is naturally null on a country's first data year). The new fields get
their own `pd.isna()`-based None-conversion, reusing the idiom already established in
`data_loaders.py`'s `load_world_map_series`.

**Testing.** A CO2-gas test asserting all three new fields populated, including the deliberate
first-year `co2_growth_prct` null converting to `None`; a non-CO2-gas (methane) test asserting
`yoy_pct_change`/`per_gdp` are `None`-filled while `per_capita` still varies with real per-gas
values. Both new tests were independently confirmed to actually discriminate old from new
behavior, not just pass green against the new code: reverting the router change (`git stash`) and
re-running reproduces a `pydantic.ValidationError` (`TimeseriesSeries` missing the new required
fields), the expected failure shape for a schema addition, not a vaguer or unrelated error.
115/115 tests pass overall (2 new).

**Verification.** Live-smoke-tested against real local data before opening the PR, then again
through the public tunnel after deploying to the Mac Mini: China's `co2` values (`per_capita`,
`yoy_pct_change`, `per_gdp`) spot-checked directly against a pandas read of the raw
`owid-co2-data.csv` and matched exactly (1990: `2.153`/`0.869`/`0.734`); `methane` confirmed
`yoy_pct_change`/`per_gdp` all-`None` with `per_capita` still carrying real per-year values. The
post-deploy tunnel response was byte-identical to the local pre-merge check.

Shipped as `climate-emissions-analysis-project` PR #139, mentor-reviewed and merged. This
documentation, per the established convention, was committed straight to `main` rather than
through its own PR.

## Release 19 — App-wide Admin Capability (Docs-first Stage)

**Status: Docs-first stage (design written; implementation not yet started).**

A new, cross-cutting admin capability, gated by a single Cloudflare Access login policy (Google
as identity provider, restricted to one account) — full design in `ARCHITECTURE.md` §8. Owned
federated-ly: each admin capability lives on the service that already owns the underlying
setting, not a new shared admin service or database. This repo's own piece of it is a new,
unlisted `/admin` route in `climate-dashboard-react/` (`src/pages/AdminPage.tsx`, reachable by
URL only, same precedent `/ask` already set — absent from `NAV_ITEMS`/nav) that hosts the actual
capability, LLM provider/model switching for `services/agent`. Full feature design lives in
`services/agent/SPEC.md` §14 and `services/agent/ENHANCEMENTS.md`, not duplicated here — this
entry exists because the SPA route itself is a root-tracked `climate-dashboard-react/` change.
Will be revised once the frontend branch (Section 4 of the implementation sequence) actually
lands.


---

## Release 20 — Landing Page, Emissions Globe, Overview Restyle, and Dedicated Sub-Domain

**Status: In progress — PRs 1–4 merged (globe, routing/shell, landing page, Overview restyle + URL params + header actions); PR 5 (cutover) — **done: live on `climate-analytics.syena.io` since 2026-09-29** (runbook steps 1–7 done and verified).**

A Claude Design pass (2026-09-29, seven boards: landing page in dark/light desktop, tablet 768
and phone 390; restyled Overview in dark/light; standalone globe) proposes three things, plus a
hosting decision made by the mentor alongside it. Not a curriculum change and not internship
scope — same category as the rest of `SPEC.md` §5 (`SPEC.md` §5.25 is the durable reference).

### Decisions (settled)

| # | Decision |
|---|---|
| 1 | **New sub-domain `climate-analytics.syena.io`**, serving the dashboard from the host root (`DEPLOY_BASE_PATH=/`) instead of `labs.syena.io/ghg-emissions-analysis/`. |
| 2 | **Landing page becomes `/`; the Overview moves to `/overview`.** `path="*"` continues to redirect to `/` (now the landing page). |
| 3 | **Overview sections stay anchor-based** (`#map`, `#by-country`, `#pct-change`, `JumpLinks`, `useJumpToHashOnLoad` — `SPEC.md` §5.19). The design's Map / By Country / % Change *tab strip* is **not** adopted: tabs would hide two of the three sections at a time and break bookmarked `#anchor` URLs. The restyle keeps `JumpLinks`, and its visual treatment can follow the mock's underline-tab look. |
| 4 | The Overview keeps the §5.7 three-tier model (All Countries / Expanded / Selected) and the ≤10-country picker — the first design draft dropped both; the revised design restores them, and this release keeps them. |
| 5 | **The old `labs.syena.io/ghg-emissions-analysis/*` URLs are not preserved** — no external users, so no redirect period and no 301. They stop working when the new build goes live. |
| 6 | **`DEPLOY_BASE_PATH=/` does not affect the other apps on the shared tunnel.** It is an environment variable on this project's own processes only; routing is matched in Cloudflare by hostname, then path, so rules for `climate-analytics.syena.io` don't interact with the `labs.syena.io` rules for `global-funds-india-allocation-monitor` (8082/4174) or `india-ipo-intelligence` (8083/4175). |

### What the design adds

- **Landing page (`/`)** — its own layout (top nav, no sidebar): hero with headline and three KPIs
  (All Countries total, % change since 1990, Expanded-set count) beside the globe; three "story"
  cards (`headline_movers`-derived: largest absolute rise, fastest growth, steepest decline among
  the 10 largest emitters of the latest year) with real 35-point sparklines; a ranking race of the
  real top 10 for every year 1990–2024 (heading percentage computed per year); feature cards
  using the app's exact nav labels; a "Built on" strip (Linear Regression, Random Forest,
  ETS(A,Ad,N)); forecasts stated to **2043**, scenarios to **2040**. Tablet and phone layouts
  are specified (menu button on small viewports).
- **Emissions globe** — an orthographic globe of CO₂ by country, one rotation per step, sharing
  the live map's YlOrRd log scale and `value_range`; drag/arrow-key rotate, +/− zoom, Reset view,
  Table view listing every country, Gray = no data; reduced-motion users get no auto-play or spin
  (Play steps years without colour blending); the host picks autoplay stops via `useYearAnimation`'s `stepYears`
  (Landing: decades, see the post-ship follow-ups; ≈35 s at 5-year steps); pauses when scrolled offscreen or tab hidden; countries keyed by **ISO
  code** and shapes self-hosted (removes the `cdn.plot.ly` CSP dependency for this component).
- **Overview restyle (`/overview`)** — same content, new visual language (cards, Selected-country
  outline on the flat map, bars in brand blue, % Change in the brown = increase / teal = decrease
  pair with a legend). The sidebar gains a **Home** item (→ `/`) and "Ask the Agent" sits at the
  top of the sidebar body.

### Open items carried from the design review

1. **Headline sentence.** The mock's copy ("…United States has stayed comparatively flat…") does
   not match what `buildHeadlineSentence` produces. The implementation keeps that function as the
   source of truth; the design copy is illustrative.
2. **Story-card links** pass `?country=` / `?countries=`, which no page reads yet. Historical
   Trends, Country Profile and Overview each need small query-parameter support (validated
   against the expanded list, capped at 10 — the same rule as the picker), or the links drop the
   parameters.
3. **Light-theme bar colour.** The design uses the dark theme's blue for bars on the light theme
   because the light brand blue (`#0A6E8C`) reads too dark on the light chart panel. That is a
   `design-system` token decision, made in that repo — not patched in this app.
4. **Overview at tablet/phone** was not redrawn; the assumption is the existing 1400px/768px
   collapse rules still apply. Verify at 768 and 390 during the preview step.
5. **Landing header on dark** uses a navy slightly off-theme; use the theme's own surface token.
6. **Globe** is SVG in the mock; the app implementation should draw on canvas. It becomes a new
   `design-system` component (needs `d3-geo` as a dependency and a self-hosted ISO-keyed
   geometry file), not app-local code.
7. **Ranking race data** needs no new endpoint — top-10-per-year is computable client-side from
   `worldMapSeries` (already loaded by the Overview). Revisit only if landing-page payload
   size becomes a concern.
8. **Existing tests.** `OverviewPage.test.tsx` and the nav/route tests will need rewriting for the
   new route, Home item and picker layout; the new landing page and globe need their own suites.

### Sub-domain cutover checklist (operational — routing and old-URL decisions settled above; nothing done yet)

Moving hosts touches infrastructure well beyond this repo. Each item needs a decision or action
before the first deploy:

- **Old URL.** Not preserved (decision 5). The four `labs.syena.io/ghg-emissions-analysis…`
  tunnel routes and their Access applications are deleted *after* the new host is verified live.
- **Cloudflare Tunnel** (shared with other apps — only this project's rules change). Add a
  public hostname `climate-analytics.syena.io` (Cloudflare normally creates the DNS CNAME
  itself) with these rules, matched top to bottom, catch-all last:

  | Order | Path | Service |
  |---|---|---|
  | 1 | `^/api` | `http://localhost:8081` (`uvicorn`) |
  | 2 | `^/mcp` | `http://localhost:8765` (`mcpserver`) |
  | 3 | `^/agent` | `http://localhost:8766` (`agent`) |
  | 4 | *(empty — matches everything)* | `http://localhost:4173` (`vitepreview`) |

  Optionally tighten to `^/api(/|$)` etc. so `/apixyz` doesn't match (the existing rules don't).
  Checked: no SPA client route (`/ask`, `/historical`, `/country-profile`, `/forecasts`,
  `/scenarios`, `/data-explorer`, `/about`, `/admin`, `/overview`) collides with `/api`, `/mcp`
  or `/agent`. Then delete the four old rules (`labs.syena.io/^/ghg-emissions-analysis/api|mcp|agent`
  and `labs.syena.io/ghg-emissions-analysis`).
- **Base path in code.** Every service currently takes `DEPLOY_BASE_PATH=/ghg-emissions-analysis/`
  (`api/main.py`, `services/mcp-server`, `services/agent`, `vite.config.ts`, `src/api/client.ts`,
  `src/lib/theme.ts`, `App.tsx`); `/` must work as a first-class value, with tests.
- **Cloudflare Access.** Recreate the login application (`/admin`, `/agent/admin` path rules) and
  the MCP Service Auth application for the new host; existing Service Tokens/policies are
  host-scoped.
- **CORS** (`SPEC.md` §5.24): add `https://climate-analytics.syena.io` to `allow_origins`
  (test both allowed and unlisted-origin cases, as before).
- **Edge config per host.** CSP (`connect-src` for `*.cloudflareaccess.com`, plus `cdn.plot.ly`
  for the Plotly map), response-header rules, rate-limit rule (currently keyed on the
  `/ghg-emissions-analysis` prefix — must be re-keyed to the new host), `sw.js` cache-control rule.
- **PWA.** New origin means a fresh service worker and manifest scope/start URL; the
  `navigateFallbackDenylist` (must still cover `/admin` and any future gated route) is re-checked.
  Installed PWAs on the old origin do not migrate.
- **MCP clients.** Claude Desktop's `mcp-remote` config and any external tester use the old
  `…/ghg-emissions-analysis/mcp` URL — update, and reissue nothing unless policies are recreated.
- **Mac Mini tooling** outside the repo (`syena-traffic-check`, tailscale/baseline checks)
  references the old host — update separately.
- **Docs** with old-host references: `ARCHITECTURE.md` §§6–9 (updated on ship, not now — that
  file describes current state), `services/mcp-server/*`, `services/agent/*`, `CLAUDE.md`.

### Cutover runbook (values read from the Mac Mini's `~/Library/LaunchAgents/com.ghgemissions.*.plist`, 2026-09-29)

Code side: **PR #194** (additive — accepts the new host in api/agent CORS and MCP `allowed_hosts`/`allowed_origins`; service-worker denylist for `/api` `/mcp` `/agent`). It can merge and deploy *before* anything below. The services already handle a root base; the cutover is **env + Cloudflare only**.

| LaunchAgent | Today | After the cutover |
|---|---|---|
| `uvicorn` (`api`, :8081) | `DEPLOY_BASE_PATH=/ghg-emissions-analysis/` | `DEPLOY_BASE_PATH=/` |
| `mcpserver` (:8765) | `DEPLOY_BASE_PATH=/ghg-emissions-analysis/` → path `/ghg-emissions-analysis/mcp` | `DEPLOY_BASE_PATH=/` → path `/mcp` |
| `agent` (:8766) | `DEPLOY_BASE_PATH=/ghg-emissions-analysis/agent/`; `MCP_SERVER_URL=http://127.0.0.1:8765/ghg-emissions-analysis/mcp` | `DEPLOY_BASE_PATH=/agent/` (**not `/`** — the agent's routes are bare `/query`, `/admin/llm`, and the middleware strips exactly this prefix); `MCP_SERVER_URL=http://127.0.0.1:8765/mcp` |
| `vitepreview` (:4173) | built with `DEPLOY_BASE_PATH=/ghg-emissions-analysis/` | rebuilt with `DEPLOY_BASE_PATH=/` |

**Order matters — Access before traffic:**

1. **Merge PR #194** and pull it (and `design-system`, `git merge --ff-only`) on the Mac Mini. Nothing changes for users.
2. **Cloudflare Access — create for the new host *before* any route goes live:** the login application with path rules `climate-analytics.syena.io/admin` and `/agent/admin`; the MCP Service Auth application on `climate-analytics.syena.io/mcp` (recreate the named Service Tokens' policy — tokens themselves can be reused). If routes go live first, `/agent/admin` is briefly reachable **ungated**.
3. **Cloudflare Tunnel:** add public hostname `climate-analytics.syena.io` with, in order: `^/api` → `http://localhost:8081`, `^/mcp` → `http://localhost:8765`, `^/agent` → `http://localhost:8766`, then an empty path → `http://localhost:4173` (optionally tighten to `^/api(/|$)` etc.). Harmless until step 4: the services still speak the old prefix, so the new host just 404s.
4. **Edge rules for the new host:** re-key the rate-limit rule (today it matches the `/ghg-emissions-analysis` prefix), and copy the response-header/CSP rules (`connect-src` needs `*.cloudflareaccess.com` and `cdn.plot.ly`) and the `sw.js` cache-control rule.
5. **Flip the Mac Mini** (this is the point of no return — the old URLs stop working, as decided): edit the four plists per the table; `DEPLOY_BASE_PATH=/ npm run build` in `climate-dashboard-react/`; then `launchctl kickstart -k gui/$(id -u)/com.ghgemissions.{uvicorn,mcpserver,agent,vitepreview}`. Confirm the fresh bundle by its `assets/index-<hash>.js` name.
6. **Verify from outside the Mac Mini:** `/` (landing), `/overview`, `/api/health` (200), `/api/overview`, `/mcp` (403 with no Service Token — Access enforcing), `/agent/health`, `/admin` and `/agent/admin` (redirect to Google login — *not* 200), an agent query end-to-end from `/ask`, a hard reload on `/overview#pct-change`, and a PWA install/launch on the new origin.
7. **Then clean up:** delete the four old `labs.syena.io/ghg-emissions-analysis…` tunnel routes and the old Access applications; update Claude Desktop's `mcp-remote` config to `https://climate-analytics.syena.io/mcp`; update `syena-traffic-check` and the other Mac Mini toolkit scripts to the new host; open a follow-up PR removing `labs.syena.io` from the allow-lists; refresh `ARCHITECTURE.md` §§6–9 and the sub-project docs (they describe the old host).

**Cutover executed 2026-09-29.** Plists backed up to `~/plist-backup-release20/` and the prefixed bundle to `~/dist-prev-release20/` on the Mac Mini. Two things worth remembering: (1) the Access app for `/mcp` was first saved with a typo (`/map`), which left the MCP server ungated on the new host — caught by an outside-in probe (`/mcp` returned 404, not 403) *before* the flip; (2) plist environment edits need `launchctl bootout`+`bootstrap` — `kickstart -k` would have kept the old env. Verified from outside: `/`, `/overview`, `/historical`, `/ask`, `/api/health`, `/api/countries`, `/agent/health` → 200; `/mcp` (+`/mcp/x`, POST) → 403; `/admin` and `/agent/admin/llm` → Access login; a real agent query end-to-end through `/agent/query` (agent → `/mcp` → API → chart widget); service worker active at scope `/`; `/overview#pct-change` loads with the anchor present; the other two labs apps unaffected. **Rate limit (step 4, done 2026-09-29):** the `syena.io` zone is on the Free plan — one rate-limit rule, URI Path only — so the existing `rate_limit_10` (50 req / 10 s per IP, Block) was extended with `/agent`, `/api`, `/admin`, `mcp` instead of adding a host match. Burst-tested from outside: 300 requests → ~113 allowed then 429, clear again within 15 s. Caveats: one shared per-IP counter across every matched path and app; `mcp` (no leading slash) should be `/mcp`; it caps floods, not slow LLM-cost abuse (per-IP limiting inside the agent service is on the backlog: `services/agent/SPEC.md` §12 item 7). **Step 7 clean-up — all done 2026-09-29/30:** edge rules for the new host (response headers incl. CSP via a `http.host in {…}` match; the `sw.js`/`registerSW.js`/`manifest.webmanifest` cache bypass — first saved with `"sw.js"` missing its leading slash, caught because `/sw.js` still came back `max-age=14400`; fixed); old `labs.syena.io/ghg-emissions-analysis…` tunnel routes and Access destinations removed; `labs.syena.io` removed from the api/agent/MCP/vite allow-lists (#195, deployed); Claude Desktop's `mcp-remote` re-pointed at `https://climate-analytics.syena.io/mcp`; the Mac Mini's `syena-apps-healthcheck.sh` GHG frontend probe moved from `/ghg-emissions-analysis/` to `/` (it only passed by SPA-fallback luck; backup `~/bin/syena-apps-healthcheck.sh.bak-release20`). The traffic/security check scripts had no references to the old host. **One incident worth remembering:** removing the old tunnel routes also deleted the `labs.syena.io` DNS record (the other two apps share that hostname), taking them offline for ~15 minutes until the Tunnel-type record was re-added — decline the "also delete DNS record" prompt when other routes still use the hostname. **Second incident (`/admin` → landing page, #196):** at the root base the service worker's scope is the whole origin, and its navigation fallback answered Access's post-login callback (`/cdn-cgi/access/authorized?…`) with the cached SPA shell — so the Access cookie was never set and the router's `*` route redirected to `/`. `navigateFallbackDenylist` now also excludes `/cdn-cgi/` and `/.well-known/` (root-level edge paths, whatever the base); a browser holding the old worker needs one page load to update. Verified live: a fresh `/admin` navigation completes login and renders the Admin page. Also: Cloudflare's negative DNS cache (SOA minimum 1800 s) kept resolvers returning NXDOMAIN after the record was restored — `curl --resolve` against the authoritative answer is the way to test in the meantime.

Rollback (if step 6 fails badly): put the four plists' env back and rebuild with the old base — the old tunnel routes are still in place until step 7.

### Implementation sequence (one PR each; mentor reviews, then merge; visual preview before merge)

1. **`design-system`:** globe component (canvas, keyboard, table view, reduced-motion, ISO
   geometry asset) — plus any new tokens the design needs.
2. **This repo — routing and shell:** `/` landing route with its own layout, Overview to
   `/overview`, Home nav item, redirect/fallback updates, test updates. Behind the new base-path
   support if it lands first.
3. **This repo — landing page:** hero, stories, ranking race, feature cards, tablet/phone layouts.
4. **This repo — Overview restyle** (anchors kept), query-parameter support on target pages.
5. **Cutover**, in this order:
   1. Code: `/` as a first-class base path across services + CORS (with tests), merged first.
   2. Rebuild the frontend with `DEPLOY_BASE_PATH=/` and restart `uvicorn`, `vitepreview`,
      `mcpserver` and `agent` with the new environment. One build serves one base path, so the
      old URLs stop working the moment the new build is live (accepted — decision 5); the build
      itself is the point of no return.
   3. Add the new-host tunnel rules and Access applications (checklist above), verify, then
      delete the old routes/Access apps.
   4. Update `ARCHITECTURE.md`, service docs and MCP client configs.

### Progress

- **PR 1 — `design-system` `Globe`: merged** (`design-system#94`). Canvas globe, ISO-3 keyed, `SyChart`-style
  `colorScale`/`colorRange`/`zLog`, controlled `yearIndex`, keyboard + Table view, reduced-motion support; geometry is a
  self-hosted, trimmed copy of the Plotly/Natural Earth 110m atlas the flat map already uses (same borders and ids).
  Adds `d3-geo`. Two pre-existing `design-system` test failures on `main` (unrelated) were left alone.
- **PR 2 — routing and shell: merged** (`#189`). `/` → `LandingLayout`; dashboard pages incl. `/overview` under an
  extracted `DashboardLayout`; unlabeled Home item in the sidebar; `App.test.tsx` (incl. the phone menu, after Copilot
  review). Findings worth keeping: (1) app `vite`/`vitest` configs needed `server.fs.allow` for design-system's directory
  once its `Globe` imported a `?url` asset (`Denied ID` otherwise); (2) **`preview.allowedHosts` was `undefined` for a root
  base** — it would have 403'd the tunnel's Host header at cutover, so it now always lists `climate-analytics.syena.io`;
  (3) Overview uses the `expand` glyph because `home` now means Home (a globe icon in design-system would let Overview
  take `home` back — planned in PR 4a); (4) clicking Home did nothing until a test caught that Home wasn't in the
  `onItemClick` lookup.
- **PR 3 — landing page: merged** (`#190`, plus `design-system#95`). Every number/year/count is computed from `/overview`
  and `/overview/world-map-series`. Findings worth keeping: (1) `pickHeadlineFacts` was extracted from
  `buildHeadlineSentence` so the story cards and the Overview headline sentence can never name different countries;
  (2) the Globe's panel overflowed a narrow parent by 24px (`content-box` + padding) — fixed in `design-system#95`, its new
  `NarrowContainer` story fails without it; (3) **only ETS carries 2043 forecasts and bands in the UI** — the mockup's
  "Linear Regression, Random Forest and ETS forecasts" wording was wrong and was corrected after Copilot review (RF is
  feature importance; LR/RF are model-comparison benchmarks); (4) the globe now spins only while the year animation plays
  (Pause / a manual seek stops both), one rotation per step at **8 s** (≈56 s for a full 1990→2024 pass; originally 5 s —
  slowed after review); (5) the race world-total (`co2_by_year`) equals the sum of the map series each year, so its
  "x% of the world's CO₂" is right; (6) the page indexes by `year − firstYear`, the same contiguous-years assumption the
  Overview makes.
- **PR 4 — Overview restyle + URL params (in progress), split three ways:** **4a** `design-system` (outline selected
  countries on the choropleth as its own prop so `series` stays reference-stable and the user's zoom survives; zoom ±;
  globe icon), **4b** `?country=` / `?countries=` support (validated against the expanded list, deduped, capped at
  `MAX_SELECTED_COUNTRIES`, URL kept in sync) and story links that honour it, **4c** the Overview restyle itself (anchors
  `#map`/`#by-country`/`#pct-change` and the `MultiSelect` picker kept; map Table view; Top Movers beside the By Country
  chart; SyChart stays — the mockup's hand-drawn SVG map/bars are a design-tool artifact, not a requirement).

### Post-ship follow-ups (2026-09-30, after the cutover)

Three changes requested after Release 20 was live; the first two shipped as one PR each, the theme default went
straight to `main` by instruction.
- **Decade steps on the Landing globe** (`#200`). `useYearAnimation` gained an optional `stepYears` (default 5); only the
  Landing hero passes `10`, so autoplay stops at 1990, 2000, 2010, 2020, then the latest year (2024) — about 40 s for a
  full pass at the unchanged 8 s dwell. The Overview map keeps 5-year steps; the slider still scrubs any year.
- **Disputed zones merged into India** (`design-system#101`). `XJK`, `XAC` and `XAP` (J&K, Aksai Chin, Arunachal Pradesh)
  exist in the shared 110m topology but have no data rows, so both the globe and the Overview choropleth drew them as gray
  gaps inside India. They are dissolved into `IND` (topojson-client `merge`, rebuilt with topojson-server at 1e4
  quantization: 199 → 196 features, one MultiPolygon, no internal border). Fixed in the geometry asset rather than by
  duplicating India's data onto three extra ids, so hover and the Table view never list them as separate entries. The
  other Natural Earth `X*` ids (e.g. `XHT`, `XBT`, `XIT`) were left alone. Live after the usual `design-system` pull →
  rebuild; verified by fetching the served topology (196 ids, none of the three).
- **Default theme is Dark.** `App.tsx`'s initial theme is `analytics` for anyone with nothing stored (or storage
  blocked); an existing stored Bright/Dark choice still wins, so returning visitors see no change. Confirmed live.

Revised again once each step ships.


---

## Release 21 — Area 2: Climate Context Layer (Emissions → Concentration → Forcing → Temperature)

**Status: Planned (docs-first stage, 2026-10-01) — no implementation started.**

Source requirements: `climate_analytics_area2_requirements.docx` (mentor's Drive, `ClimateAdvocacyDashboards/IDEAS TIH Internship/`).
This release extends the platform with the emissions → atmospheric concentration → radiative forcing →
temperature anomaly narrative, new data sources, a new `correlation` API domain, a landing carousel, an
expanded Overview, a Temperature & GHG Correlation module, and agent/MCP support. Additive: no existing
emissions, historical, forecast, scenario or agent contract changes. Not internship scope — same category
as the rest of `SPEC.md` §5 (`SPEC.md` §5.26 is the durable reference).

### Effort assessment

Roughly Releases 17–20 combined: **11 phases (1.1–2.6) plus a Section 3 phase, ~20–28 PRs**, across
`api/`, `pipeline/` (new), `climate-dashboard-react/`, `design-system` (sibling checkout) and, for Section 3,
`services/mcp-server` and `services/agent`. Phase 1.1 (four new sources, harmonization) and 1.3 (methodology)
carry the most risk.

### Decisions (settled, 2026-10-01 — amend the requirements doc where they differ)

| # | Decision |
|---|---|
| 1 | **Concentration source = NOAA GML Mauna Loa (annual means from 1959, monthly from Mar 1958; measured ppm), spliced to the Law Dome ice-core/firn spline before 1959.** The splice year is **1959**, not 1958 (corrected after the live run, 1.1a): NOAA's annual-mean file starts at the first full year. Added as a fourth row of the §1.1.1 source table. The 1959 splice point, the measured overlap gap and a methodology note are mandatory, same pattern as the EDGAR/PRIMAP caveats. |
| 2 | **Radiative forcing is copy-only.** §2.4's "not modeled" list gains: *"Radiative forcing appears only as a narrative/conceptual link in the causal-chain explainer; no forcing dataset, calculation, or endpoint exists in this phase."* |
| 3 | **Domain-bounded endpoints only; no aggregation/BFF layer in this release.** Indicators split into `concentration` and `temperature`. The "landing-page summary" and "overview combined" endpoints from §1.4 are **dropped**: Landing/Overview compose bounded endpoints client-side. A BFF is re-evaluated only on a measured latency problem. The "agent-ready contract" is satisfied by MCP tool wrappers (Section 3), not a REST contract. |
| 4 | **Headline slope = TCRE-style OLS of Berkeley Earth anomaly on OWID cumulative fossil CO₂, 1850+.** The EDGAR 1970+ total-GHG pairing is a secondary **"recent all-gas relationship"**, never called TCRE in any copy, chart title or agent response. Requires an edit to requirements §1.3.1 and to agent guardrail language implying one unified "headline" model. **Amended by decision 40:** the headline `x` is now *total* anthropogenic CO₂ (fossil + cement + land-use change); fossil + cement only becomes the labelled secondary variant. |
| 5 | **Scenario→temperature (§1.3.5)** uses OWID World cumulative CO₂ to 2024 as the base, applies the scenario pathways only to the 40-country covered set, holds rest-of-world at its last-observed share, and applies the **OWID CO₂ slope from #4** (not the EDGAR slope). Always labelled *"illustrative, partial-coverage translation"*. |
| 6 | **CIs:** Newey-West (HAC) standard errors for the headline CI (§1.3.1); **block bootstrap** for the §1.3.6 stability check. Two distinct requirements, not either/or. |
| 7 | **Source/baseline matrix** below. `edgar_total_ghg` + `preindustrial` → hard 4xx validation error; `edgar_total_ghg` + `1990` → allowed with a warning note in the response. *(Restated for PRIMAP-hist in Phase 1.4's docs: `edgar_total_ghg` is shelved, decision 20.)* |
| 8 | **Berkeley Earth baseline offset** (native 1951–1980 → 1850–1900) is computed from Berkeley Earth's own data and published, with its derivation method, in `GET /api/correlation/meta`. Not hardcoded from literature. |
| 9 | **Harmonization rule (ingestion, not per-endpoint):** an ISO3-based country crosswalk built once at ingestion reconciles OWID vs EDGAR naming; international aviation/shipping are excluded from country cumulative-share calculations and reported only as a separate "international bunkers" line, so shares sum to 100% of territorial emissions. *(PRIMAP-hist contains no international aviation/shipping at all, decision 21; the ISO3 crosswalk in `pipeline/crosswalk.py` is reused.)* |
| 10 | **Ingestion lives in a new top-level `pipeline/` directory** (separate from `api/` runtime and the intern notebooks): one versioned script per source (OWID, EDGAR, Berkeley Earth, NOAA GML), writing to the normalized store `api/` reads. The refresh job is extended with clear logs (records processed, deviations from norm) and alerting, and **moves from weekly to monthly for both existing and new sources**. |
| 11 | **Section 3 (MCP/agent) is tracked as its own phase** with entries in `services/mcp-server/{SPEC,ENHANCEMENTS}.md` and `services/agent/{SPEC,ENHANCEMENTS}.md`, written before that phase starts. |
| 12 | **Landing globe is reversed from Release 20's decade steps:** continuous rotation over **1970–2024** with a smoothly advancing year counter and colours changing over time; **amended 2026-10-04 (owner: the strict version looked wrong):** the colour legend, the globe's controls, the year slider and the world total stay visible whether or not the globe is spinning; **only the per-country MtCO₂ labels on the map are hidden while it spins**, and appear when it stops (pause, completion, or reduced motion, which starts paused). The Overview choropleth is the analytical counterpart: decade stops (1970, 1980, 1990, 2000, 2010, 2020, 2024) at ~1.5–2 s each with every year-dependent value and card synchronized (the tiers, the ranking, the atmospheric CO₂ panel), plus year-by-year scrubbing. The fixed "Since 1990" headline card is deliberately a 1990-to-latest comparison, is labelled as such, and does not follow the map's year. |
| 13 | **No auth added for `/api/correlation/*`** — read-only public data endpoints structurally identical to the existing public `/api/*` surface (see the "API has no auth yet" constraint: `/docs`, `/redoc`, `/openapi.json` stay unexposed). |

### Endpoint list (net new; all `GET /api/correlation/*`, models `Correlation{Resource}Response`)

```
/meta                      /concentration            /temperature
/emissions-temperature     /ghg-composition          /country-share
/scenario-temperature
```

### Source/baseline validity matrix (`/emissions-temperature`)

| source | `preindustrial` (1850) | `1970` | `1990` |
|---|---|---|---|
| `owid_co2` | ✅ headline TCRE view | ✅ | ✅ existing ML-module consistency |
| `edgar_total_ghg` | ❌ 4xx (no pre-1970 data) | ✅ default | ⚠️ allowed, warning in response |

### Phases (one branch + PR per phase or sub-phase; docs-first; visual preview before merge for frontend)

| Phase | Scope | Size | PRs |
|---|---|---|---|
| **1.1** Data acquisition | `pipeline/` + four sources (OWID retained, PRIMAP-hist (EDGAR shelved), Berkeley Earth, NOAA GML + ice-core splice), Climate Watch deferred; ISO3 crosswalk; provenance metadata store; monthly refresh with logs/alerting. Split: **1.1a** foundation + NOAA/Law Dome + Berkeley (PR #201, merged); **1.1b** EDGAR + ISO3 crosswalk + gas-split reconciliation (PR #202 — merged as a dormant internal-validation source, decision 20); **1.1b′** PRIMAP-hist ingestion + completeness validation (decisions 21–22; PR #203, merged); **1.1c** OWID step + refresh wiring/alerting (PR #204; ops copies versioned, deploy pending) | L | 3–4 |
| **1.2** Harmonized layer | Year keys, units, global vs country indicators, indexed/rolling/baseline-relative derivations, provenance carried through. Split: **1.2a** `derive.py` + indicator catalog + harmonized tables as a derived pipeline stage (decisions 25–28); **1.2b** `align_pair` (decision 29) | M | 2 |
| **1.3** Correlation analytics | TCRE OLS + HAC CI + R², recent all-gas relationship, composition (AR5 GWP), cumulative share, scenario translation, bootstrap stability check; lag analysis stays stretch | L | 3–4 |
| **1.4** API | The seven endpoints above, Pydantic models, validation (matrix), explicit nulls, tests incl. 4xx/503 paths. Design written 2026-10-02 (decisions 44–55): **1.4a** infrastructure + `/meta` + `/concentration` + `/temperature`; **1.4b** `/emissions-temperature` + `/ghg-composition`; **1.4c** `/country-share` + `/scenario-temperature` | M | 3 |
| **1.5** Performance & reliability | Pre-aggregate/cache; missing-year, unit and source-update validation. Cross-cutting: its checks are also acceptance criteria of every phase above. **Done 2026-10-03** (acceptance table and measured baseline above) | S | 1 |
| **2.1** Landing | Four-step band, ≥2-banner carousel (keyboard accessible, auto-rotate off by default), Banner 1 climate signal, Banner 2 existing hero, 1970–2024 continuous globe behaviour per decision 12 | M | 2 |
| **2.2** Overview | Five content blocks, "Why emissions matter" card (matches the "Since 1990" card treatment), anchors; needs a stub route for the 2.4 link | L | 3 |
| **2.3** UX & content | Copy/tone, visual-purpose and traceability review for every new chart/KPI (duplicated text in the requirements doc is one requirement). Cross-cutting with 2.1/2.2 | S | 1 |
| **2.4** Correlation module | New page: causal-chain explainer, global vs country-responsibility views, methodology notes and attribution in-module | L | 3–4 |
| **2.5** Baseline rules | Per-module baselines (1990 = 100 / full OWID history / 1970+ EDGAR / pre-industrial CO₂-only), exposing baseline year, reference period, formula, range and excluded years | S–M | 1–2 |
| **2.6** Globe & choropleth | Distinct animation behaviours per decision 12; Overview synchronization | M | 2 |
| **3** MCP & agent | Tool wrappers, intent routing (emissions / climate / combined), guardrails, Ask-page prompts; own docs per decision 11 | L | 4–6 |

Known ordering friction (accepted, user's order kept): 2.1 links to an Overview anchor 2.2 creates; 2.2 links to the module 2.4 builds (stub first); 2.6 reopens pages 2.1/2.2 changed.

### Settled after review (2026-10-01, replaces open items 1–3)

| # | Decision |
|---|---|
| 14 | **Rest-of-world = share held flat.** RoW's 2024 share of the global total is held constant and scaled against the covered-country pathway each year (`global_t = covered_t / (1 − RoW_share_2024)`), so RoW moves proportionally with the scenario. Rejected: freezing RoW in absolute terms — under the Aggressive scenario it would let an unmodeled bloc dominate global cumulative emissions and dilute the scenario's logic. International bunkers sit inside the RoW bucket (World − covered set), consistent with decision 15's regression X-variable. The assumption is stated in the **`scenario-temperature` response metadata** (not just a label footnote). |
| 15 | **Two different "global" quantities, documented as such.** The TCRE regression's X-variable is OWID's full **World** row (bunkers included — they are real atmospheric loading; excluding them undercounts X and biases the slope upward). The country-share denominator is the **bunker-excluded national sum** (shares sum to ~100% of national emissions). `/api/correlation/meta` (and the relevant endpoint docs) states that the two differ and why. **Amended by decision 40:** the headline `x` also adds land-use CO₂ (the World total including bunkers is unchanged); the denominator difference statement stands. |
| 16 | **IPCC comparability is stated, not just avoided.** Methodology copy shown with the slope/CI/R² names the differences: *"This estimate is derived from OWID fossil CO₂ + cement emissions (excludes land-use/LULUCF emissions) regressed against Berkeley Earth global temperature anomaly. It will not match the IPCC's published TCRE estimate (about 0.45 °C per 1,000 GtCO₂, ~1.65 °C per 1,000 GtC), which is derived from CO₂-only forcing in a full Earth-system model context and includes land-use emissions. This platform's figure is a simplified, data-driven analog to TCRE, not a restatement of the IPCC value."* The slope also absorbs non-CO₂ forcing co-varying with CO₂ (add to the note). **Superseded by decision 40:** the methodology copy is rewritten — the headline no longer excludes land-use emissions, and the comparison is to the AR6 range, not a point value. |
| 17 | **Berkeley Earth vintage discrepancy is open and carried as a caveat (found in 1.1a).** The downloadable summary file (last modified 2025-01-10, ends 2024) gives 2024 = 1.617 °C above 1850–1900 — reproducing Berkeley's own Jan-2025 report (1.62 ± 0.06). Berkeley's Jan-2026 report, on the *same stated 1850–1900 baseline*, implies 2024 ≈ 1.52 (2025 = 1.44, "~0.08 cooler than 2024") and 2023 ≈ 1.47 vs 1.535 in our file. A baseline mix-up is therefore **ruled out** (verified against both reports' text, 2026-10-01); the residual ~0.10 °C (2024) / ~0.065 °C (2023) is a genuine vintage difference, not uniform (so not purely a shift of the 1850–1900 offset). It cannot be reconciled until a current-vintage file is obtained (`berkeleyearth.lbl.gov` timed out; `data.berkeleyearth.org/auto/…` returns 403). Until resolved: the pipeline keeps raising the stale-source deviation, and the headline regression output carries *"based on Berkeley Earth file vintage [last-modified date]; a possible ~0.1 °C discrepancy with Berkeley Earth's most recent published report text has not yet been reconciled"*. If still unresolved after a fresh file is obtained, document as a flagged deviation — never a silent pick-one. |
| 18 | **Coverage years are read from the data, never hardcoded in docs or code.** EDGAR's current release is **2026 (1970–2025)**, not the requirements doc's 1970–2023. `/api/correlation/meta` reports earliest/latest year per source from the ingested files' own coverage (already stored in `provenance.json`); specs say "1970 – latest EDGAR release" rather than a fixed end year. The 1970 *baseline year* is unaffected (it is EDGAR's start, not a coverage claim). *(Applies equally to PRIMAP-hist, decision 21.)* |
| 19 | **EDGAR gas split comes from the per-gas files, reconciled to the combined workbook (Phase 1.1b scope).** The combined `EDGAR_AR5_GHG` workbook has country/sector totals only. `ghg-composition` is built from the separate files — fossil CO₂ (`IEA_EDGAR_CO2`), CH₄, N₂O (Gg × AR5 GWP-100) and F-gases (`AR5g` file, already CO₂-eq) — and an explicit ingestion step **sums them and checks the result against the combined workbook's total**, recording the residual per year in provenance and raising a deviation beyond tolerance. **Superseded by decisions 20–21 for the active pipeline; the reconciliation still runs in the dormant EDGAR code.** |
| 20 | **EDGAR is shelved for publication; its code is kept dormant for internal validation (mentor decision, 2026-10-02).** The specific reason: the fuel-combustion CO₂ (IPCC 1.A) in EDGAR's CO₂ file is IEA data licensed **CC BY-NC-ND 4.0**, and the workbook's own citation text asks users of it to contact the IEA for permission. It is **88.5% of EDGAR's CO₂ and 65.5% of its total GHG (2023)** and is embedded in the combined AR5 totals, so it cannot be stripped out. The mentor confirmed the site is non-commercial (so NC is met) and understands the ND clause. But ND bars sharing *adapted* material, and Phases 1.2–1.4 would convert units, aggregate sectors and countries, add gases into a CO₂e total and publish shares through a public API — transformations that plausibly count as adaptation. IEA permission has not been obtained, so **no EDGAR-derived series may be served publicly**. `pipeline/edgar.py` (PR #202) is merged as a **dormant** source: excluded from `--source all`, writes only to `data/internal/edgar/`, provenance `published: false`, used to cross-check the active source locally. **The IEA permission route will be pursued later**, if the platform grows and EDGAR's sector detail proves worth incorporating; re-activation needs the permission in hand and a docs-first update. |
| 21 | **PRIMAP-hist v2.8 replaces EDGAR as the total-GHG / gas-composition / country-share source** (Zenodo doi 10.5281/zenodo.22876287, released 2026-09-29, 1750–2025). Settings: country-reported scenario (HISTCR — the third-party scenario is unmaintained, builds heavily on EDGAR/FAOSTAT, and is excluded from the commercial licence); the `no_extrap` file; AR5 GWP-100 baskets (`KYOTOGHG`, `FGASES`; CH₄ and N₂O at 28/265 to match AR5); category `M.0.EL` (national total excluding LULUCF, which stays out of scope as in the EDGAR design). OWID is unchanged for CO₂-only modules and the headline TCRE regression. **Licence: CC BY-NC-SA 4.0 since v2.8** (the dataset's YAML says "Attribution-NonCommercial"; Zenodo and the description say NC-SA): fine for a non-commercial site; published derived datasets must carry CC BY-NC-SA 4.0 and attribution; the authors ask to be notified of use (nc-support@johannes-guetschow.de). Upstream: gap-filling uses EDGAR 2025 for non-energy CO₂ and all CH₄/N₂O/F-gases (EDGAR's CC BY part, not the IEA energy CO₂) and CDIAC / Energy Institute for energy CO₂ — those upstream licences are **not yet verified**. Measured against EDGAR (national totals, Gt CO₂e, 2026 release): 1990 +0.0%, 2000 −0.3%, 2010 −2.1%, 2019 −2.9%, 2023 −3.2%, 2024 −3.6%; the third-party scenario is +1.3% in 2023 (4.7% above country-reported); by country India −14%, US +6%, China −2.7% (2023); CH₄ −9%. **International aviation and shipping are not in PRIMAP-hist** and the file has no `EARTH` aggregate: the all-gas view is national-only (labelled "excluding international transport", no bunker line item) and the world total is the sum of areas. PRIMAP-hist is a composite with extrapolation and mixed sources; it is cited as such, not presented as a single measured inventory. |
| 22 | **Incomplete trailing years are excluded, not published (mentor decision).** In the `no_extrap` file PRIMAP's 2025 is incomplete: CH₄ has 3 areas, N₂O 2 and F-gases 0 (vs 206 / 206 / 151 in 2024), and its CO₂-only "total" is 36.3 Gt, −28% on 2024. A year is *complete* only if, for each of the four gas series (CO₂, CH₄, N₂O, F-gas basket), **emission-weighted coverage** — the share of the previous year's emissions that is still reported — is ≥ 98% **and** the national total is within ±15% of the prior year. Emission-weighted rather than area-count because F-gas reporting drifts from 169 areas (2010–17) to 151 (2024) while the missing areas hold ~0.04% of emissions (an area-count rule would wrongly reject 2023–2024). Calibrated over 1751–2024: every gas ≥ 99.96% in every year; total year-on-year −9.2% (1945) to +9.9% (1920); v2.8's 2025 fails every test (CH₄ 2.0%, N₂O 0.06%, F-gases 0.0%; total −28.3%). *(The first draft of this decision said area coverage ≥ 98% of the previous-five-year maximum and ±10%, calibrated on 1975–2024 totals only; per-gas calibration in Phase 1.1b′ showed both were wrong and they were replaced.)* Trailing years that fail are trimmed and recorded in provenance with their metrics (a note; more than one trailing year trimmed raises a deviation); a failing year *followed by* a passing one raises an error, so an interior gap is never silently dropped. The extrapolated variant of the file is never ingested, so extrapolated values are not published. 2025 returns automatically once a release passes the test. Implemented and tested in Phase 1.1b′ (PR #203). |
| 23 | **The OWID step registers, it does not download.** The refresh job's existing backup → download → week-1 validation → restore flow stays the single authority for `data/owid-co2-data.csv` (the notebook, not a second code path, is the validation authority). `pipeline/owid.py` takes the file as it stands afterwards, records provenance (sha256, rows, coverage, licence CC BY, citations; `retrieved_at` = file mtime) and publishes `owid_world_co2_annual.csv`: World CO₂ **including international transport** (the TCRE X-variable, decision 15), cumulative CO₂, `national_sum_mt` (the country-share denominator) and `international_transport_mt` — which reconcile within 0.02% (2024; >1% is a deviation). This also settles open item 7 in part: OWID's international aviation/shipping CO₂ is now carried alongside the national sum. Completeness applies to the trailing years only (emission-weighted country coverage ≥ 98%, World within ±15% of the prior year; the World series swings −27%…+34% in 1803–1830 so a full-history test is meaningless), checked over the last four years with everything from the **first** failing year trimmed — two consecutive partial years would otherwise let the second look complete relative to the first (found by a test); more than two raises. |
| 24 | **Refresh wiring (versioned in `pipeline/ops/`, not yet deployed).** `pipeline.run` writes `last_run.{priority,title,message}` (urgent = a source failed, high = deviations from norm, default = clean). The Mac Mini script gains a `pipeline_stage` that runs `python -m pipeline.run --source all` (NOAA GML, Berkeley Earth, PRIMAP-hist, OWID; EDGAR is shelved) once the OWID file is final — after week-1 validates it, or after a week-1 failure restores the backup — as its own failure domain: it never blocks the notebook weeks and its outcome is appended to whichever ntfy push goes out (priority = the higher of the two; stale summaries are deleted first so a crash cannot re-report the last run). **Cadence moves from weekly (Sunday 03:30) to monthly (day 10, 03:30)** so NOAA's and Berkeley's monthly updates land first (decision 10). **The script also restarts the API after a validated refresh**, mirroring the India Allocation Monitor's `_restart_api_process` (`launchctl kickstart -k gui/$UID/com.ghgemissions.uvicorn`; only after a genuinely successful refresh, never after a restored-backup failure, never fatal — a failed restart is reported in the push at priority ≥ high; `GHG_SKIP_API_RESTART=1` opts out). API only: the agent holds per-conversation state in memory a restart would wipe, the MCP server holds no data cache, `vitepreview` serves static files. Deploying is a separate, owner-approved step (runbook: `pipeline/ops/README.md`); merging changes nothing live. |
| 25 | **Phase 1.2 — the harmonized layer is built in `pipeline/`, precomputed, and read (not recomputed) by the API.** Requirements §1.3/§1.5 want derived outputs precomputed so frontend and agent see identical numbers, so `pipeline/derive.py` (pure, tested functions) and `pipeline/harmonize.py` (builds the tables) run as a **derived stage after the source steps** inside `python -m pipeline.run` (and so inside the monthly job), writing `data/climate/indicator_catalog.json`, `harmonized_global_annual.csv` and `harmonized_country_annual.csv`. The API (Phase 1.4) loads these like any other CSV; there is deliberately **no shared derivation library between `pipeline/` and `api/`** (the repo's convention is mirrored loaders, not shared code), so a baseline choice at request time is a lookup among precomputed indicators, never a computation. |
| 26 | **Indicator catalog.** Every indicator has a stable id (`snake_case`, derived ones `<base>__<metric>`), a display name, a canonical unit (`ppm`, `°C`, `MtCO2e`, `Mt CO2`, `%`, index), a **scope** (`global` or `country` — a global and a country indicator can never be paired), a **kind** (`level`, `cumulative`, `anomaly`, `uncertainty`), its source series id (a key into `provenance.json`, whose release/licence/checksums the catalog entry links, so provenance survives into every derived number), its own coverage `[first, last]`, decimals for display, and caveats. Sources: NOAA/Law Dome ppm; Berkeley anomaly on both references plus its 95% interval; OWID World CO₂ (incl. international transport), its cumulative, national sum and international transport; PRIMAP-hist global total GHG and the four gases, plus the cumulative national total from 1750; country level: PRIMAP total and cumulative per area. |
| 27 | **Year keys, ranges and nulls.** The key is the integer calendar year, unique per indicator; each indicator keeps **its own coverage** (concentration to 2025, the rest to 2024) and a "common range" exists only for a pair, computed on request of the pairing function, never baked in. Gaps stay **explicit nulls** — no interpolation anywhere in this layer (a documented method may add it later, per §1.5). A catalog entry whose source series is missing from `provenance.json`, or a unit/scope conflict, is a deviation; a missing *input file* skips the affected indicators with a deviation rather than failing the run. |
| 28 | **Derived metrics and baseline policy (SPEC §2.5).** `level` indicators get: year-on-year %, a **trailing 5-year mean** (null until 5 observations: no look-ahead), and an index (`100 × value / value[baseline year]`) for each baseline allowed by §2.5 — **1990, 1970, pre-industrial (1850)**; the default baseline per indicator follows §2.5 (OWID-based: 1990; PRIMAP all-gas: 1970; CO₂ full-industrialization and concentration: pre-industrial). An index is defined only if the baseline-year value exists and is > 0; otherwise it is null and the catalog records the excluded baseline and why. `cumulative` indicators get no index or rolling mean (indexing a running total is meaningless). **`anomaly` indicators are never indexed** — the 1850–1900 anomaly is −0.13 °C in 1850, so "= 100" has no meaning — they carry both native references (1951–1980 and 1850–1900) and the trailing mean. Every derived indicator's catalog entry exposes the baseline year, reference period, formula, source range and excluded years (§2.5). Country level is deliberately small: PRIMAP total, per-gas and cumulative per area (what §1.3.4's shares need); per-country indices are not precomputed (size, little demand) and are decided in 1.4. |
| 29 | **Correlation-ready pairing (Phase 1.2b).** `align_pair(a, b, start, end, min_overlap=20)` returns the aligned frame plus metadata: years used, **every omitted year with its reason** (`a missing` / `b missing` / outside range), per-series coverage, and both indicators' provenance links. It refuses a pair across scopes, a pair with fewer than `min_overlap` shared years, and — to keep correlation features honest — stamps the result with the "interpretive context, not causal proof" note the requirements demand. Phase 1.3 builds the co-trend, regression and composition outputs on this. |
| 30 | **Phase 1.3 — scope and shape.** Four sub-phases, one branch + PR each: **1.3a** headline regression (OLS + HAC CI + R² + window sensitivity + holdout); **1.3b** block-bootstrap stability check; **1.3c** recent all-gas relationship, GHG composition, country cumulative share; **1.3d** scenario→temperature translation. All of it is computed in `pipeline/` (new `pipeline/correlation.py`, a derived stage after `harmonize` inside `python -m pipeline.run`) and written to `data/climate/correlation_*.json|csv`; the API (1.4) only reads them (decision 25). Built on `align_pair`. statsmodels is imported from its submodules (`statsmodels.regression.linear_model`, `statsmodels.tools.tools`), **never `statsmodels.api`** (open item 15). Lag analysis (§1.3.2) stays stretch; `include_lag_analysis=true` is rejected in 1.4 as not implemented, never ignored.
| 31 | **Headline specification (§1.3.1; redefined by decision 40).** `y` = Berkeley Earth anomaly on the 1850–1900 reference; `x` = **cumulative total anthropogenic CO₂ since 1850 = OWID World fossil + cement (bunkers included, decision 15) + OWID World land-use-change CO₂**, in thousand GtCO₂ (Mt ÷ 10⁶), paired by `align_pair` over the common range read from the data (today 1850–2024, n = 175), OLS **with intercept**. Primary unit **°C per 1,000 GtCO₂**; also per 1,000 GtC (×3.664), the IPCC's unit. Reported: slope, intercept, R², n, range, plain-OLS SE beside the HAC SE, source selection, gases, baseline, and **the AR6 very-likely range (0.27–0.63, best estimate 0.45) shown beside both the headline and the secondary variant**. Fossil + cement only (`x` = OWID World cumulative CO₂ from 1850) is published as the **secondary, labelled variant** — the common meaning of "CO₂ emissions" — never hidden. The requirement says cumulative from 1850 while the harmonized fossil cumulative starts in 1750: the slope is invariant to that (a constant moves only the intercept). **Measured 2026-10-02: headline 0.520 [0.480, 0.559], R² 0.903, plain SE 0.0129, Durbin–Watson 0.89, intercept −0.099; fossil-only 0.797 [0.752, 0.843], R² 0.909.** Cumulative total CO₂ since 1850 = 2.75 thousand GtCO₂ (fossil 1.84 + land-use 0.91).
| 32 | **HAC bandwidth.** Newey–West, Bartlett kernel (`cov_type="HAC"`), **maxlags = ⌊1.5·n^(1/3)⌋ (= 8 at n = 175)**, 95% CI from the HAC SE; the textbook ⌊4(n/100)^(2/9)⌋ (= 4) under-corrects at this autocorrelation. Sensitivity is published, not hidden. Headline: maxlags 4 / 8 / 16 → SE 0.0177 / 0.0202 / 0.0229, CI [0.485, 0.554] / [0.480, 0.559] / [0.475, 0.565]; fossil-only: SE 0.0218 / 0.0232 / 0.0255. The conclusion does not depend on the choice; the response carries the maxlags used and the table.
| 33 | **Estimation window is chosen from a precomputed grid.** Because outputs are precomputed (decision 25), `start_year` takes only **1850, 1900, 1950, 1970** (end = last common year); anything else is a 422 listing the allowed values, never substituted. **Headline slopes by window (HAC 8): 1850 → 0.520 [0.480, 0.559]; 1900 → 0.556 [0.514, 0.599]; 1950 → 0.589 [0.531, 0.647]; 1970 → 0.638 [0.593, 0.684]** (fossil-only: 0.797 / 0.786 / 0.758 / 0.787). The headline slope **rises** with later start years — away from the IPCC best estimate — and the UI says so; a later window is not a way to tune the number. The grid doubles as stability evidence. The all-gas view (decision 35) uses the same grid clipped to its own coverage.
| 34 | **Stability check (§1.3.6) = moving block bootstrap of the *residuals*, X held fixed.** B = 2,000, block length 10, **fixed seed recorded in the output** (an unseeded Monte Carlo made the ETS bands irreproducible, Backlog B1 — this must not repeat). Why not a pairs/row block bootstrap: `x` is a trending cumulative series, so (x, y) blocks from different eras give resamples with little `x` spread. Measured on fossil-only it was unstable (upper bound 0.884 → 1.397 for blocks 10 → 30); on the headline it is milder but still wider and shifted (block 10: [0.444, 0.551], median 0.508 vs the fitted 0.520), while the residual bootstrap is stable: **headline [0.473, 0.566] at block 10, median 0.520; [0.481, 0.558] … [0.465, 0.576] for blocks 5 … 30** (design-stage run; the shipped, seeded stage with seed 20261002 gives [0.473, 0.568] at block 10 and [0.481, 0.560] … [0.462, 0.579] for blocks 5 … 30 — same conclusion). Output: percentile interval, median, the block-length sensitivity, the HAC interval alongside, **decade holdouts** (implemented at the four splits 1980 / 1990 / 2000 / 2010, because the requirement says "decade-based train/test splits" and one split cannot show whether a result is typical; the 2000 split is the one quoted here: fit 1850–1999 → test 2000–2024: **slope 0.466, RMSE 0.174 °C**; fossil-only 0.849 / 0.126 — reported as measured: the headline's out-of-sample error is *larger* — **and the shipped four-split run shows it is larger at every split**, RMSE 0.229 / 0.203 / 0.174 / 0.164 vs 0.150 / 0.135 / 0.126 / 0.126 for fossil-only: adding land-use CO₂ fixes the definition, not the temperature fit, and the UI should say so), and the window grid of decision 33. It publishes numbers and a generated summary, **no pass/fail label**.
| 35 | **"Recent all-gas relationship" (§1.3.1 secondary view).** `y` = same anomaly, `x` = cumulative PRIMAP-hist total GHG (MtCO₂e, AR5 GWP-100) summed **from 1970**, 1970 to the last *complete* PRIMAP year (2024: 2025 is excluded by the completeness rule, so n = 55), OLS + HAC with ⌊1.5·n^(1/3)⌋ = 5 lags. Unit °C per 1,000 GtCO₂e. **Never called TCRE** in the output field names, titles, notes or agent text; the response says why it is a different thing (all gases, national-only, short window, collinear with time). **Resolves open item 7:** OWID's international-transport CO₂ is *not* added to this `x` — mixing a CO₂-only source into an all-gas series from a different provider is worse than the undercount — so the view is labelled "national totals, international aviation and shipping excluded" and the headline view remains the one that includes them.
| 36 | **GHG composition (§1.3.3).** From `primap_global_composition_annual`: per year, each gas's MtCO₂e and share of the total (CO₂, CH₄, N₂O, F-gases; AR5 GWP-100), only for years that passed the completeness test. Where a gas has no coverage (F-gases before the first reporting year) its value and share are **null and the row lists `gases_included`** — no zero is invented and no share is quietly renormalised. Validation: included shares sum to 100 ± 1e-6 or the stage fails. A selected-year table is served from the same long file.
| 37 | **Country responsibility (§1.3.4).** Cumulative share = a country's cumulative emissions ÷ the sum of all ISO3 countries' cumulative emissions (**national sum, bunkers and non-ISO aggregates excluded — decision 15**), per year from 1850, for `owid_co2` (CO₂), and PRIMAP-hist `co2` and `total_ghg`, written as one long file `correlation_country_share.csv` (country, year, source, gas_scope, cumulative, share_pct; ≈ 100k rows). **No country series is ever regressed against the global temperature series**; every response carries the no-attribution caveat, and the frontend (Section 2) shows it beside the global anomaly line only.
| 38 | **Scenario→temperature (§1.3.5), method.** Inputs: Week 5's `data/scenario_projections.csv` (40 covered countries × BAU/Moderate/Aggressive × 2025–2040, **fossil + cement CO₂ only**) and OWID World cumulative CO₂ at the last observed year *T₀* (2024). RoW share *s* = 1 − covered₍T₀₎ ÷ World₍T₀₎ (World incl. bunkers; read from data, reported). Each year `global_t = covered_t ÷ (1 − s)` (decision 14). **Because the headline slope is per unit of *total* CO₂, the translation must also say what land-use CO₂ does after *T₀*: it is held flat at its trailing 5-year mean (2020–24: 4,658 Mt/yr, 10.6% of the 2024 total) — an explicit, stated assumption in the response metadata, since the scenarios do not model it.** `cum_t = cum_T₀ + Σ (global_u + luc_flat)`; implied warming is incremental, `ΔT_t = slope × (cum_t − cum_T₀)`, with the headline slope and a band from its HAC CI (slope uncertainty only, labelled). A **second line applies the fossil-only slope to fossil-only increments** (internally consistent, no land-use assumption) so a reader sees how much the definition matters. Absolute level = `anchor + ΔT_t`, **anchor = the trailing 5-year mean of the observed anomaly at T₀ (1.390 °C)**, not the single 2024 value (1.617) and not the line (1.331 headline; 1.470 fossil-only): the observed 2024 anomaly sits 0.286 °C above the headline line, so an intercept-based curve would jump at T₀ and a one-year anchor would bake ENSO noise and the unreconciled Berkeley file vintage into every scenario. Labels: "illustrative, partial-coverage translation", "implied temperature outcomes", dependent on regression period / source / assumptions, "not formal climate-model projections"; the RoW and land-use assumptions are in the response metadata.
| 39 | **Scenario guard and output contract.** The scenario file is produced by the notebooks, **not** by the monthly refresh, so it goes stale when OWID gains a year: the stage requires the scenario's first year to equal *T₀* + 1 and every scenario country to be present in the World series, otherwise it raises a deviation ("scenarios are stale relative to OWID — rerun Week 5") and writes **explicit nulls with that reason**, never a stale translation. Every output JSON carries `schema_version`, `generated_at`, `method`, the inputs' provenance links (from the catalog), `caveats` — including the mandatory ones (not a climate model; the comparability text of decision 40 (what the figure includes and omits, the AR6 range, non-CO₂ forcing and aerosols absorbed); the denominator difference of decision 15) and the **Berkeley vintage caveat** ("based on Berkeley Earth file vintage [date]; a possible ~0.1 °C discrepancy with Berkeley Earth's most recent published report text has not yet been reconciled", the date taken from the file's recorded Last-Modified) which stays until the owner sets `vintage_reconciled: true` on the Berkeley entry in `pipeline/source_notices.json`. Validation (RunReport deviations): finite slope, CI brackets the slope, `n` equals the pairing's, shares sum to 100, no negative cumulative.
| 40 | **Headline redefined to total anthropogenic CO₂ — a definitional correction found by testing against real numbers (2026-10-02, owner-approved).** The original plan regressed on fossil + cement only (slope 0.797), but the IPCC's TCRE is defined on *total* anthropogenic CO₂ including land-use change; the question being answered was narrower than the one being compared against. OWID's World row already carries `land_use_change_co2` (1850–2024), so **no new source** — it is the same OWID file. **Gap analysis, all measured on the real data:** (a) adding land-use CO₂ → **0.520 [0.480, 0.559]**, inside the AR6 very-likely range 0.27–0.63 and 0.07 from its best estimate 0.45 — adopted; (b) a two-predictor regression (CO₂ + non-CO₂ from PRIMAP-hist) was **rejected: the predictors are collinear** (correlation with fossil CO₂ 0.983, with total CO₂ 0.999; decayed-stock proxy for the short-lived gases (CH₄ 12 yr, N₂O 109 yr) 0.997), giving unusable coefficients (e.g. CO₂ 1.96 / non-CO₂ −4.45; or intervals [−0.002, 1.166] and [−7.2, 5.8]) — and it would still omit aerosol cooling, the largest non-CO₂ term, for which we hold no series; (c) a later window **raises** the slope (0.520 → 0.638 for 1970+), so it does not help; (d) ENSO/volcanic filtering would narrow intervals, not move the slope — a methodology note only. **Sensitivities published as measured:** land-use scaled ×0.7 / 1.0 / 1.3 → 0.583 / 0.520 / 0.468 (GCB's own uncertainty on E_LUC is ±0.7 GtC/yr, ≈ ±2.6 GtCO₂/yr); the window grid of decision 33. **The remaining ~0.07 gap is not pushed further**: it is plausibly aerosols/non-CO₂ forcing and single-realization variance versus a multi-model ensemble, and tuning further would be fitting to a target. **Methodology copy (replaces decision 16's):** "Derived from OWID cumulative CO₂ from fossil fuels, cement and land-use change (Global Carbon Project), regressed against the Berkeley Earth anomaly. A simplified, data-driven analog to the IPCC's TCRE (AR6 best estimate about 0.45 °C per 1,000 GtCO₂, very likely range 0.27–0.63), not a restatement of it: this regression also absorbs warming from non-CO₂ gases and aerosols that varies with CO₂, uses one observed climate history rather than a multi-model ensemble, and depends on land-use emission estimates that are themselves uncertain." **Pipeline work this adds to 1.3a:** the OWID step keeps `land_use_change_co2` for the World row (it currently filters it out) and harmonize gains `owid_luc_co2_world_mt`, its cumulative, and `owid_total_co2_world_cumulative_mt` (fossil-cumulative + land-use-cumulative from 1850; documented as not comparable to the 1750-based fossil cumulative). **Licence check (done):** OWID: "completely open access under the Creative Commons BY license", with the carve-out that third-party data is "subject to the license terms from the original third-party authors"; the Global Carbon Budget paper is CC BY 4.0, but **the dataset's own page (icos-cp.eu/GCP/2024) names no licence** — only "the use of data is conditional on citing the original data sources" and the citation *Global Carbon Project (2024), Supplemental data of Global Carbon Budget 2024 (Version 1.0), doi:10.18160/gcp-2024*. No non-commercial, no-derivatives or share-alike term was found, so the only condition identified is attribution, which every output carries — but it is **not confirmed as CC BY**; see open item 17. |
| 41 | **The land-use fit-quality trade-off gets the same visibility in the UI and agent copy as in the README (owner-directed 2026-10-02).** Decision 34's stability check is deliberately a set of published numbers, not a pass/fail verdict, so users can see the nuance: the headline (total anthropogenic CO₂) matches the IPCC's TCRE definition, but out of sample it is **less accurate than the fossil-only variant at every decade split** (RMSE 0.229 / 0.203 / 0.174 / 0.164 vs 0.150 / 0.135 / 0.126 / 0.126 °C for splits 1980 / 1990 / 2000 / 2010; ≈ 38–53% larger), while the in-sample fits are nearly identical (R² 0.903 vs 0.909). **Required copy (headline module, and any agent response quoting the headline), as the owner proposed it and as amended after measurement:** *"Including land-use emissions aligns this estimate with the IPCC's own TCRE definition. Land-use CO₂ is estimated with more uncertainty than fossil-fuel emissions, and in an out-of-sample test this headline predicted recent temperatures with a larger error than the fossil-only variant ({headline_rmse} vs {fossil_rmse} °C for {test_range}). The data cannot say whether that reflects land-use measurement uncertainty or something else. In-sample, both variants fit the historical record almost identically (R² {headline_r2} vs {fossil_r2}); the difference appears specifically in out-of-sample prediction."* **The in-sample sentence is part of the required copy (owner-directed 2026-10-02):** without it "worse holdout error" reads as "worse model fit" in general, when what was measured is narrower and more informative — both variants explain the historical record almost equally well (R² 0.903 vs 0.909, in-sample RMSE 0.129 vs 0.125 °C), and the land-use-inclusive variant is less accurate when extrapolated to years it was not fitted on **Two deliberate departures from the first wording, both because the evidence does not support them:** (a) *"which results in"* asserts a cause. The data cannot attribute one: holdout RMSE at 2000 is **U-shaped in the land-use weight** (x = fossil + s·land-use: s = 0 → 0.126, 0.25 → **0.095**, 0.5 → 0.111, 0.7 → 0.136, 1.0 → 0.174, 1.3 → 0.206 °C; the train slope falls monotonically 0.849 → 0.409), so some land-use weight *improves* out-of-sample prediction and the full weight worsens it — not what pure measurement noise would give, though noise may contribute; land-use CO₂ here is also close to flat in annual terms (≈ 4.5–6.7 Gt/yr since 1900, against fossil rising to 38.6 Gt/yr), so its cumulative grows almost linearly while the temperature response to it need not; (b) *"modestly"* understates a 38–53% larger error and is replaced by the numbers. **Implementation:** the sentence and its numbers are generated in the pipeline (`headline.fit_quality_note`, from the holdout block) and carried through the API, so the UI, the agent and the docs cannot drift apart or round differently; it ships as a small follow-up PR after #213 merges (not pushed to #213 while its Copilot review is running). The requirements `.docx` gets the same requirement as a tracked change when the owner asks. |
| 42 | **A "How this number was derived" section, linked from the headline's methodology note (owner-suggested 2026-10-02).** The headline's derivation involves enough deliberate choices — the TCRE definition correction (0.797 → 0.520), the rejected two-predictor regression, the HAC bandwidth and its sensitivity, the estimation-window grid, the land-use sensitivity, the residual (not pairs) bootstrap and its coverage check, four decade holdouts, the land-use weight scan, the AR6 comparison, sources/licences and the Berkeley vintage caveat — that one inline caveat cannot carry it, and a reviewer will want the trail. **Design (built in Section 2, linked from the methodology note; the agent gets the same content through its tools in Section 3):** an expandable section on the headline module, or a dedicated page if it outgrows that, with the narrative as static copy and **every number read from the pipeline output** (`correlation_headline.json`), never retyped, so the page cannot drift from the figures. Structure follows the derivation order: (1) what is regressed on what, and why total anthropogenic CO₂ (the fossil-only result shown beside it); (2) uncertainty — HAC and why plain errors are too narrow, with the bandwidth sensitivity; (3) how sensitive the slope is — estimation window, land-use scaling; (4) stability — residual bootstrap and why not a pairs bootstrap, block-length sensitivity, the decade holdouts, including the in-sample vs out-of-sample statement of decision 41; (5) comparison to the IPCC's range and why the figures differ; (6) data, licences and attribution, and the Berkeley vintage caveat; (7) what this is not (not a climate model; correlation, not proof of cause). **Reproducibility rule:** anything the page shows must be reproducible from the repository. Two analyses behind the trail currently are not pipeline output — the **land-use weight scan** (holdout RMSE vs land-use weight) and the **rejected two-predictor regression** (collinearity 0.98–0.999). The weight scan is cheap and decision-relevant, so it moves into the pipeline output (`land_use_weight_scan`) in the same follow-up PR as `fit_quality_note` (decision 41); the two-predictor result is shown as a dated analysis note citing decision 40 with its numbers fixed at the time of analysis, and the script that produced it is committed under `pipeline/analysis/` before the page ships. |
| 43 | **The scenario translation is shown beside the emissions, with a generated reading note (owner-directed 2026-10-02).** The small 2040 gap between scenarios (BAU − Aggressive ≈ 0.11 °C) must not read as the model failing to register the scenarios, when their annual emissions diverge 2.2× (46,647 vs 21,611 Mt global in 2040). **UI requirement (Section 2):** the scenario temperature module shows **two figures side by side** — (1) annual emissions by scenario (the large divergence; the existing Scenario Comparison page already shows `year_2040` per country, and the translation output carries covered-country and global annual emissions per year) and (2) the cumulative increment and implied temperature by scenario (the small divergence) — with a short note next to the temperature figure. **Measured facts the note rests on (2026-10-02):** 78–83% of the 2040 headline level is warming *already observed* by 2024 (the 1.39 °C anchor; 71–78% on the fossil-only line); the gap between scenarios widens every year the pathways stay apart (0.000 °C in 2025 → 0.015 in 2030 → 0.053 in 2035 → 0.111 in 2040); and relative to the *additional* warming (BAU +0.40 °C) the Aggressive pathway adds 28% less (+0.29), although relative to the whole 2040 level the gap is only ≈ 6%. **Required copy, as the owner proposed it and as amended after measurement, generated from the output numbers:** *"Scenarios diverge sharply in annual emissions by {year} ({bau} vs {aggressive} Mt a year, {ratio}×), but the implied temperatures differ by only {gap} °C. {first}–{last} is a short window against the {n_years} years of emissions already accumulated, and {pct}% of the {year} implied level ({anchor} °C) is warming already observed by {t0}, before any scenario begins. What the scenarios change is only the emissions still to come: relative to the {increment} °C of additional warming, the {lowest} pathway adds {x}% less than {highest}. The gap widens every year the pathways stay apart ({gap_a} °C in {year_a}, {gap_b} °C in {year_b})."* **Departures from the first wording, all because the evidence supports a more precise claim:** (a) "most of the projected temperature … reflects emissions that already occurred" becomes "**warming already observed**" with the measured percentage (the anchor is an observation, not an emissions total); (b) "projected" becomes "**implied**", consistent with the required labels; (c) "divergence grows larger over longer horizons" becomes **"the gap widens every year the pathways stay apart"**, with the numbers the data shows — the scenario files end in 2040, so no figure beyond it is quoted (any statement about longer horizons is conditional on the pathways staying apart, an inference from the model's arithmetic, not a computed result); (d) the **relative-to-additional-warming** sentence is added so a small absolute gap is not mistaken for no effect. **Implementation:** a conditional `reading_note` and a `spread` block (per-year max − min of annual emissions and of implied level, and the ratio) are generated in `scenario_temperature.py` as a small follow-up PR after #218 merges, so the UI, the agent and the docs quote identical figures; the note is only generated when the emissions ratio between the highest and lowest scenario is at least 1.25 (otherwise the premise does not hold). The requirements `.docx` gets the requirement as a tracked change when the owner asks. |
| 44 | **Phase 1.4 — the API only reads; nothing is recomputed per request (restates decision 25).** Every `/api/correlation/*` response is built from the files `pipeline/` wrote to `data/climate/` (the `harmonized_*` tables, `indicator_catalog.json`, `provenance.json`, and the `correlation_*`, `co2_concentration_*` and `temperature_anomaly_*` outputs), loaded with `@lru_cache` like the existing loaders (the monthly refresh already `kickstart`s uvicorn, so a cache is never stale). `api/` does **not** import `pipeline/` (independent deployables); the one piece of logic it shares conceptually, aligning two series on shared years, is a few lines of pandas re-implemented in `api/` and tested against the same fixtures. A new `CLIMATE_DATA_DIR` setting (default `data/climate`) lets tests point at a temp directory. |
| 45 | **Missing or unavailable data is a 503 with the reason, never a 200 with nulls to chart.** (a) A required file does not exist (pipeline has not run) → 503 "not generated yet". (b) A pipeline output exists but carries `unavailable_reason` (the stage's explicit-null result, decisions 25/36) → 503 with that reason in `detail`. (c) A file with an unsupported `schema_version` → 503. (d) Within a *served* series, a missing year is an explicit `null` value with the year kept (no interpolation, no gap closing), and `coverage`/`notes` say so. |
| 46 | **One response envelope.** Every response model (`Correlation{Resource}Response`) carries `schema_version`, `generated_at` (of the underlying file), `note` (the causation/interpretive-context note for pairings, the "not a responsibility measure" note for shares), `caveats`, `attribution` and `source_vintage` where the source has one (Berkeley Earth). Licence and attribution therefore travel with every number the UI or the agent shows, not only with `/meta`. |
| 47 | **`/concentration` and `/temperature` (single-series views).** Concentration: `view` ∈ `level` (default) · `yoy_pct` · `mean5y` · `index` (+ `baseline` ∈ `preindustrial` · `1970` · `1990`, required for `index`, rejected otherwise); `resolution` ∈ `annual` (default) · `monthly` (Mauna Loa only, from 1958, the ice-core splice is annual and is not offered monthly); `start_year`/`end_year`. Temperature: `view` ∈ `level` (default) · `mean5y`; `baseline` ∈ `1850_1900` (default, the preindustrial-referenced series used by the regression) · `1951_1980` (Berkeley Earth native); `start_year`/`end_year`. Temperature points carry the 95% uncertainty. The series are the catalog indicators (`co2_concentration_ppm`, `…__yoy_pct`, `…__mean5y`, `…__index_{1990,1970,preindustrial}`, `temperature_anomaly_{1850_1900,1951_1980}_c`, `…__mean5y`), so ids, units and decimals match the indicator catalog exactly. |
| 48 | **`/emissions-temperature` (the relationship, restated source/baseline matrix).** Parameters: `source` ∈ `owid_co2` (default) · `primap_ghg`; `baseline` ∈ `preindustrial` (default for `owid_co2`) · `1970` (default for `primap_ghg`) · `1990`; `variant` ∈ `total` (default, the headline definition: fossil + cement + land-use CO₂) · `fossil` (`owid_co2` only; rejected for `primap_ghg`). `baseline` is the first year of the displayed pair (the window start); `x` is the harmonized cumulative series as published, **not rebased** to the window start (the slope does not depend on where the cumulative starts, only the window does). A published fit is attached only when its start year, end year **and** number of years all equal the pair's (so a pair with an omitted year, or one longer than the fit's data, gets no fit). The response is the aligned pair (`year`, `cumulative_emissions`, `temperature`, years omitted from either side listed with the reason) plus `fit` (slope, HAC 95% CI, R², n, window, the published stability and fit-quality notes) **only when that exact window is a published one**; otherwise `fit` is `null` with a note, never a fit computed on the fly. Matrix: `owid_co2` × all three baselines valid (a fit for 1850 and 1970, the pipeline's published window grid; none for 1990); `primap_ghg` × `1970` valid with the published recent all-gas fit; `primap_ghg` × `1990` valid, pair only (shorter window), warning note; `primap_ghg` × `preindustrial` → **422** (the all-gas relationship is defined from 1970 and no 1850-based fit exists; PRIMAP-hist's own coverage from 1750 would make the pair possible but not the published fit). The all-gas relationship is **never called TCRE** and never compared with the AR6 range (decision 4); the headline response carries the AR6 reference and the total-versus-fossil fit-quality note (decision 41). |
| 49 | **`/ghg-composition`.** Parameters: `start_year`/`end_year`, or `year` for a single-year view (mutually exclusive with the range, else 422). Serves the long file (year × gas: `mtco2e`, `share_pct`, `gases_included`) with the reconciliation and basis from `correlation_composition.json`. A gas with no value for a year is `null` and listed in `gases_included`, shares are over the gases included (decision 36). |
| 50 | **`/country-share`.** Parameters: `source` and `gas_scope` limited to the combinations `correlation_country_share.json` publishes as available (`owid_co2`/`co2`, `primap_hist`/`co2`, `primap_hist`/`total_ghg`; note the share file's source id is `primap_hist`, where `/emissions-temperature` says `primap_ghg`) (anything else → 422 listing the valid ones); either `year` (ranking, default the latest, `limit` ≤ 50, default 15) or `countries` (a series, ≤ 10 ISO3 codes, unknown → 404). Shares are of the bunker-excluded national sum and the response states it (decisions 9, 15); the note says cumulative share is not a measure of responsibility, and nothing here regresses a country against the global temperature (requirements §1.3.4). |
| 51 | **`/scenario-temperature`.** Pass-through of `correlation_scenario_temperature.json` with filters: `scenario` (repeatable; unknown → 422) and `line` ∈ `both` (default) · `headline` · `fossil_only`. Always returns the four mandatory labels, the assumptions block (rest-of-world share, flat land-use, anchor), `base.step_check`/`base.pathway_baseline`, the `spread` block and the generated `reading_note` (decisions 38, 39, 43), so the UI and the agent quote identical figures. A stale or failed translation is 503 (decision 45). |
| 52 | **`/meta`.** One call that makes the rest interpretable: sources with coverage, release, licence and attribution (from `provenance.json`); the Berkeley Earth offset derivation (decision 8); the statement that the regression's X-variable (OWID World, bunkers included) and the country-share denominator (bunker-excluded national sum) are **different totals and why** (decision 15); the valid `source`/`baseline`/`variant` matrix; the catalog's indicator ids; the pipeline's last run (time, status, number of deviations from `last_run.json`); and each correlation output's `generated_at`. Coverage years come from the data, never hardcoded (decision 18). |
| 53 | **Validation is strict and never substitutes.** Enumerated parameters are `Literal`s (FastAPI returns 422 listing the allowed values); cross-parameter rules (matrix, `index` needs `baseline`, `year` vs range, `variant` vs `source`) are checked explicitly and return 422 with a message naming the rule; a `start_year` after `end_year` is 422; a year range entirely outside coverage returns an empty list **with** the coverage in the response, not an error. NaN/Infinity never reach a response (strict JSON; a non-finite value in a source file is a 503, not a silent null). |
| 54 | **Security and exposure unchanged (restates decision 13).** Read-only `GET`, no auth, same CORS allow-list; `/docs`, `/redoc`, `/openapi.json` stay unexposed through the public tunnel until the API has auth. No endpoint accepts a path, a filename, a free-text expression or a country-vs-global regression request. |
| 55 | **Phase 1.4 is three PRs, docs-first.** **1.4a** infrastructure (`api/climate_loaders.py`, the common envelope, error mapping) + `/meta` + `/concentration` + `/temperature`; **1.4b** `/emissions-temperature` + `/ghg-composition`; **1.4c** `/country-share` + `/scenario-temperature` and the final contract test. Each ships with fixture-backed tests (written to a temp `CLIMATE_DATA_DIR`, never the real data): every endpoint's happy path, each 422 and 404 rule, each 503 cause in decision 45, strict-JSON parsing of every response, and a check that `note`, `attribution` and `caveats` are present. A contract test per endpoint builds the fixture by running the real pipeline stage on small stubbed inputs, so a pipeline schema change breaks the API tests rather than production. |
| 56 | **Phase 1.5 — freshness is reported, never assumed (decision 52 extended).** `/meta`'s `outputs[name]` gains `age_days` and `stale`, and the response a `freshness` block (`refresh_cadence_days` 31, `stale_after_days` 45 = one monthly cadence plus a grace period, `checked_at`). `stale` is true only when the age is strictly greater than 45 days; a missing, unparsable or non-string `generated_at` gives `age_days: null, stale: null` (unknown, never fresh); a timestamp in the future gives age 0, a naive one is read as UTC; a missing or unavailable output has no freshness. The flag is informational (an alert lives in the pipeline's refresh job); the data endpoints still serve a stale output, because the age is visible in `/meta` and the stage's own `unavailable_reason` already covers a failed refresh. |

**Phase 1.4a status 2026-10-02:** `api/climate_loaders.py` (read-only loaders: missing file, `unavailable_reason`, unsupported `schema_version` and non-finite numbers are all 503s with the cause), `api/schemas_correlation.py`, and `api/routers/correlation.py` with `/meta`, `/concentration` and `/temperature`. A series is never served without its provenance entry (a missing one is a 503). The test climate directory is built by running the real `pipeline` harmonize stage, so a pipeline schema change breaks the API tests.

**Phase 1.4b status 2026-10-02:** `/emissions-temperature` (owid_co2 total/fossil × preindustrial/1970/1990, primap_ghg × 1970/1990; primap × preindustrial and variant on primap are 422; fits attached only for exact published windows; full stability/AR6/fit-quality context only for the primary window, never for the all-gas relationship) and `/ghg-composition` (`year` or a range, gases in published order, null gases left out of `gases_included`, a CSV/JSON inconsistency is a 503).

**Phase 1.4c status 2026-10-02:** `/country-share` (ranking by `year`/`limit` or a `countries` series with `start_year`/`end_year`; the valid combinations are read from the file, an unsupported one is a 422 listing them; unknown ISO3 is 404; ≤ 10 countries) and `/scenario-temperature` (`scenario` repeatable, `line` both/headline/fossil_only; the spread and reading note are never filtered, and the response says so). The test fixtures for both come from the real `country_share` and `scenario_temperature` stages. Phase 1.4 is complete; 1.5 (performance and reliability) is next.

**Refresh-job fix 2026-10-03 (found while deploying Section 1 to the Mac Mini).** Two gaps in `pipeline/ops/ghg-data-refresh.sh`, both only reachable once the API served `data/climate/*`: (1) the Area 2 stage ran right after week 1, before weeks 2-5, so its scenario stage read the previous month's `scenario_projections.csv` (always one month behind; unavailable via the stale-scenario guard whenever OWID gained a year); it now runs after the weeks (and still in both failure branches). (2) a pipeline-only refresh (week 1 failed, backup restored) never restarted the API, so new Area 2 files were not served; it now restarts when the stage produced a non-urgent summary (`PIPE_OK`), and still never after a weeks 2-5 failure (partially regenerated CSVs). Tests: `pipeline/tests/test_ops_script.py` (order, the `PIPE_OK` flag, the gated restart, the no-restart branch); 7 mutations caught. **Not yet deployed:** merging changes nothing on the Mac Mini; the live script is replaced by hand (backed up first) only after the PR merges, and the next scheduled run (October 10, 03:30) is then its first full exercise. The restart gate fails closed: `PIPE_OK` needs a zero exit and all three `last_run.*` summary files non-empty, otherwise the run is reported as failed.

**Phase 1.5 status 2026-10-03 — Section 1 complete.** Requirements' 1.5 ("pre-aggregate/cache; missing-year, unit and source-update validation; also acceptance criteria of every phase") is met by mechanisms already built plus three small additions in this PR. **Acceptance table:**

| Criterion | Mechanism | Evidence |
|---|---|---|
| Pre-aggregated, not recomputed per request | every figure is a pipeline output read by the API (decision 44) | no endpoint imports `pipeline/` or fits a model |
| Cached | `@lru_cache` on every file loader; the monthly refresh restarts uvicorn | **new:** `test_a_second_request_reads_no_file_again` (a warm request opens no data file; mutation-verified with `maxsize=0`) |
| Missing years | pipeline: contiguous-year checks, `align_pair`'s omitted-year list; API: explicit nulls, omitted-year lists, never interpolated | tests per endpoint (interior null, omitted year with reason) |
| Units | the indicator catalog carries `unit` and `decimals` for every indicator | **new:** the response unit equals the catalog unit for every series endpoint and every pair axis |
| Source updates | pipeline: provenance, checksums, vintage and stale-source alerts, monthly refresh; API: `generated_at`, per-output status | **new:** `age_days`/`stale` and `freshness` in `/meta` (decision 56) |
| Coverage honesty | a range outside coverage is an empty list with the coverage; the CSVs are cross-checked against their JSON metadata (counts, years, finiteness) | **new:** no endpoint serves a year outside the reported coverage |

**Measured baseline (real data, 2026-10-03, TestClient in-process; the Mac Mini will add network and a slower CPU):** warm (cached) response median 1.1–40 ms, cold (first request after a restart) 2–81 ms. Payloads: `/meta` 41 KB, `/concentration` 24 KB (monthly 67 KB), `/temperature` 17 KB, `/emissions-temperature` 26 KB (all-gas 13 KB), `/ghg-composition` 132 KB for the full 275-year range, `/country-share` 7-10 KB (a three-country series 37 KB), `/scenario-temperature` 39 KB. The slowest warm endpoint is `/ghg-composition` (40 ms: the per-year assembly is not cached), well inside any budget the dashboard needs; it is the first candidate if a measured problem ever appears. No BFF or extra pre-aggregation is justified (decision 3).

**Status 2026-10-02:** the `reading_note` and `spread` block are implemented in `scenario_temperature.py` (PR for the decision-43 follow-up). Today's generated note: "…BAU 44,877 vs Aggressive 20,791 Mt a year, 2.2×… differ by only 0.11 °C… 175 years of emissions already accumulated… 78–83% of the 2040 implied level (1.39 °C) is warming already observed by 2024… Aggressive pathway adds 28% less than BAU… (0.027 °C in 2032, 0.107 °C in 2040)." The mid-horizon gap year is the middle of the scenario window (2032), not a fixed 2030. The figures are a little below the first-draft numbers because the scenario file is now the Week 5 refit.

### Open items (resolve in the relevant phase's docs-first step)

1. **`baseline` parameter semantics.** Define explicitly whether it sets the emissions index base, the temperature reference period, or both (and `preindustrial` = 1850–1900 via decision 8's offset).
2. **Monthly cadence (decision 10) changes the existing weekly Mac Mini job** (launchd + the `ghg-data-refresh` skill); coordinate as an operational change in 1.1c.
3. **The requirements `.docx` is now out of date** for decisions 20–22 (EDGAR → PRIMAP-hist in §1.1.1, §1.1.3, §1.3.3, §1.4.2–1.4.3, §2.4, §2.5; the gas-split and bunker rules). Pending: re-amend as tracked changes when the mentor asks.
4. `ARCHITECTURE.md` gets updated when `pipeline/` and the `correlation` domain land (new data flow), not now.
5. **Source/baseline matrix and `source` parameter** to be restated for PRIMAP-hist (name, coverage from 1750, which baselines are valid, whether the "recent all-gas relationship" keeps a 1970 default given pre-1970 values are reconstructions) in Phase 1.4's docs.
6. **Licensing follow-ups:** (a) pursue IEA permission later (decision 20); (b) verify PRIMAP-hist's and OWID's upstream licences (Energy Institute, CDIAC, FAOSTAT, CEDS, Global Carbon Project); **PRIMAP-hist's upstream licences: confirmed compatible by its maintainer 2026-10-08 (see (c)); OWID's remain open;** (b′) **Berkeley Earth is CC BY-NC 4.0, not CC BY 4.0 as first recorded** (found 2026-10-02 against their data page; non-commercial only, attribution to Berkeley Earth with www.berkeleyearth.org) — provenance corrected in PR #205; fine for this non-commercial platform but a standing restriction; (c) ~~notify the PRIMAP-hist authors of use~~ — **sent 2026-10-02 06:27:27 UTC for v2.8; REPLIED 2026-10-08 09:15 UTC by Johannes Gütschow** — (1) the YAML `rights` omitting ShareAlike "is a mistake on our side. It should be 'share alike' everywhere", so CC BY-NC-SA 4.0 is authoritative; (2) "all upstream licenses are compatible with CC-NC-BY-SA, so you don't have to pass on additional restrictions". Recorded in `source_notices.json` (an informal email confirmation, not a formal licence statement) and in the PRIMAP provenance licence text; the no-reply note stops. Nothing changes in how derived data are published. (recorded in the tracked `pipeline/source_notices.json`, copied into PRIMAP provenance as `author_notification` on every run — PR #206; a release it doesn't cover, e.g. v2.9, raises a note; no reply after 60 days raises a note). When they answer, add the reply there and update decision 21's licence wording (their answers to: which licence is authoritative, and whether upstream sources impose redistribution conditions); (d) publish derived data with the CC BY-NC-SA 4.0 notice.
8. ~~The API is not reloaded after a refresh~~ — **resolved 2026-10-02** (deployed with PR #204): the refresh script now runs `launchctl kickstart -k gui/$UID/com.ghgemissions.uvicorn` after a validated refresh, mirroring the India Allocation Monitor. Remaining limit: it triggers on the notebook refresh path only; when Phase 1.4 serves `data/climate/*`, a pipeline-only refresh (notebooks failed or skipped) needs the same trigger — decide in 1.4.
9. ~~Deploy the refresh wiring~~ — **done 2026-10-02**: Mac Mini pulled to `4617508` (fast-forward), pipeline stage dry-run, script and plist backed up (`*.bak-20261002`) and installed byte-identical to `pipeline/ops/`, launchd reloaded with `bootout`/`bootstrap` (schedule now Day 10, 03:30, was Sunday 03:30), one full run verified (see Progress).
7. ~~**Bunkers in the all-gas relationship**~~ — **resolved by decision 35:** not added; labelled instead.

10. **A standing deviation makes every push `high`.** Berkeley Earth's download file has been stale since 2025-01-10 (ends 2024; decision 17), so every pipeline run reports one deviation and the monthly push is `high` until that is resolved. That is honest, but a known, already-diagnosed condition that never clears trains the owner to ignore the channel (the Allocation Monitor's notes make the same point). Options: keep it; add an acknowledged-deviations list (still shown in the message, but not raising the priority); or obtain a current Berkeley file (`berkeleyearth.lbl.gov` timed out from the Mac Mini's network too, so the dry-run showed no new route). Decide before the first scheduled run (Nov 10). **Owner decision 2026-10-02: keep the alert active for now** (it is true and still unresolved); revisit if it is still firing after the Berkeley Earth reply (item 11). **Update 2026-10-06:** the reply named a current file (decision 83); the standing deviation clears when the migration ships.

11. **Berkeley Earth inquiry — sent 2026-10-02 14:20:19 UTC, awaiting reply** (confirmed from sent mail; subject "Where is the current Land_and_Ocean_summary.txt? The S3 file was last updated Jan 2025", to `data@berkeleyearth.org`). It asks where the current auto-updating file lives and whether the S3 bucket is still canonical, and cites the January 2026 report (2025 = 1.44 °C above 1850–1900, ~0.08 °C cooler than 2024 ⇒ ≈1.52 for 2024, vs 1.617 in our file) to ask which vintage underlies it. Facts verified 2026-10-02 from this machine and the Mac Mini: the S3 file serves 200 with Last-Modified 2025-01-10; `data.berkeleyearth.org/auto/Global/Land_and_Ocean_summary.txt` returns 403; `berkeleyearth.lbl.gov` does not respond; the data page links the S3 file under *Global Temperature Data → Global Monthly Averages (1850 – Recent) → annual summary*. Recorded in `pipeline/source_notices.json` and carried into the Berkeley provenance as `provider_correspondence` (PR #210); an unanswered inquiry is a note, never an alert, and the run says so if the source file's Last-Modified later moves past the inquiry date. When they reply: add it to `replies`, then update the Berkeley provenance/licence/source wording, decision 17 and item 10, and — **owner-confirmed 2026-10-02** — set `berkeley_earth.vintage_reconciled: true` in `pipeline/source_notices.json` **only when the reply settles the vintage question** (which file is current and whether the January 2026 report's figures apply); that flag is what removes the "possible ~0.1 °C discrepancy" caveat from the headline regression output (decision 39, PR #212). **Update 2026-10-06: reply received** (Zeke Hausfather, Berkeley Earth, 14:04 CDT): *"Berkeley Earth switched to our high resolution dataset as the operational product. Its available here: https://berkeleyearth.org/data/ (annual file here)."* Recorded in `source_notices.json`; the migration is decision 83. Closed by decision 83 (implemented).
12. **Mac Mini pull of PRs #205/#206 is deferred until all of Section 1 (Phases 1.1–1.5) is complete (owner decision 2026-10-02).** Until then the Mac Mini's provenance keeps the old Berkeley licence string and has no notification record, so a pipeline run there raises a spurious "no record of notifying the PRIMAP-hist authors" deviation. The next scheduled run is **Nov 10**; if Section 1 is not finished by then, pull before that date or accept one spurious `high` push.

13. ~~**Environment bug: numpy 2.2.6 on Python 3.14 silently corrupts large dense pandas reshapes**~~ — **fixed by pinning numpy 2.3.5 (PR #208, merged 2026-10-02; owner asked for the upgrade).** Found in Phase 1.2a: `DataFrame.pivot`/`unstack` on a fully populated frame of more than ~32k rows returned wrong, duplicated year labels with no error; numpy ≥ 2.3.0 fixes it (2.3.0–2.3.5, 2.5.3 checked), pandas 2.3.3 does not while numpy stays 2.2.6. **Verified before/after with every other package held identical** (a venv from the project's exact `pip freeze`, only numpy swapped): 24 of 24 API responses byte-identical; 7 of 8 notebook CSVs byte-identical; the 8th (`ets_forecasts.csv`) differs only in the Monte Carlo bands, by the same amount as a rerun under the *same* numpy (item 14), with the forecast mean identical. No production code path was ever affected (API world-map pivot 7.6k rows from 1990). The pipeline's reshape canary stays as a guard and no longer fires on the upgraded venv. **The Mac Mini is not upgraded yet**: it is step 0 of the deferred Section 1 deploy runbook (`pipeline/ops/README.md`).

14. ~~**The ETS forecast bands are not reproducible**~~ — **owner decision 2026-10-02: leave as is for now; moved to the Backlog (B1) below.** Summary: `week4_ets_forecasting.ipynb`'s 95% bands come from an unseeded `fit.simulate(repetitions=1000)`, so `ci_lower`/`ci_upper` re-draw on every refresh (up to ~1,550 Mt between two runs on identical data; the forecast `mean` is deterministic). Full detail, evidence and options are in B1.

15. ~~**scipy is not pinned, and `statsmodels.api` is broken**~~ — **resolved in PR #211:** `scipy==1.17.1` pinned. The Mac Mini was checked read-only on 2026-10-02: Python 3.14.6, scipy 1.17.1, statsmodels 0.14.4, numpy 2.2.6, and the same `import statsmodels.api` ImportError (`scipy._lib._util._lazywhere` removed in scipy 1.17), so pinning the version already running in both places makes the environment reproducible without a behaviour change. Rule: import statsmodels from its submodules (`statsmodels.regression.linear_model`, `statsmodels.tsa.holtwinters`, …), never `statsmodels.api`; nothing in the repo uses `statsmodels.api`.
16. **For the mentor's review of this design:** decision 33 (precomputed window grid; other `start_year`/`end_year` rejected, not computed on request — the alternative is computing in the API per request, which breaks "precomputed, one source of numbers"), decision 38 (5-year-mean anchor, incremental ΔT, land-use held flat after *T₀*, the second fossil-only line) and decision 34 (residual over pairs bootstrap). **Decision 40 is approved** (headline = total anthropogenic CO₂; fossil-only secondary; AR6 range shown with both).

17. ~~**Global Carbon Project dataset licence is not stated on its page**~~ — **decided by the owner 2026-10-02: include the land-use series, with the citation requirement satisfied in the attribution metadata and the licence/provenance note worded, not defaulted to CC BY.** Recorded verbatim in provenance (`land_use_license_note`, PR #211): *"Land-use CO2 data originates from the Global Carbon Project via OWID. No formal license (e.g., CC BY) is stated on the Global Carbon Project's data page; use is conditional on citing the original source per their stated terms. The required citation is included in this platform's data attribution. No non-commercial, no-derivatives, or share-alike restrictions were found."* A test guards that the note never claims a CC BY licence. Still to do when the headline ships (1.4/Section 2): carry the GCP citation (`required_citation_format`, edition matching what OWID republishes) in the API's attribution metadata and the UI's data-sources panel. A written licence from the Global Carbon Project remains an optional future step.
18. ~~**The requirements `.docx` needs an amendment for decision 40**~~ — **done 2026-10-02 (owner asked):** tracked changes (author Claude) applied to the Drive file: §1.3.1 headline redefined to total anthropogenic CO₂ with the fossil-only variant as a labelled secondary and the AR6 range (0.27–0.63) shown with both; methodology note rewritten (land-use now included, residual gap expected), land-use sensitivity and attribution wording (verbatim, decision 40) added; §1.3.5 land-use-after-last-year assumption and fossil-only second line; summary, agent-guardrail and acceptance-criterion lines updated; a second 2026-10-02 revision note. Validated against the schema; the previous version is kept locally. **Not yet reflected in the .docx:** the API-level details of decisions 30–39 (window grid, bootstrap method, HAC lag, scenario anchor) — those are design choices recorded here, to be added when Phase 1.4 fixes the endpoint contracts.

### Section 2 (Frontend) — implementation plan (docs-first, 2026-10-04)

**Sources of truth.** Requirements doc §§2.1–2.6 and the Claude Design handoff
(`Area 2 Final Design.dc.html` + README, artboards L1 Landing desktop, L2 Landing mobile, O1/O2
Overview desktop/mobile, M1 Correlation module). **The final design supersedes the README's
option tables** (its body still describes earlier options: e.g. the top-5 ranking "removed", older
anchor lists). Where the final design and the requirements doc differ, the final design wins and
the doc is amended (list below). The design renders and matches its SPEC NOTES (checked in a
browser 2026-10-04: L1, O1 viewed; the rest read from the artboard text). Chart values in the
design marked `[mock]` are placeholders; every figure ships from pipeline/API output, never
hard-coded. Design decisions A–D (confirmed by the owner 2026-10-04): headline = total CO₂ incl.
land use (0.520), fossil + cement (0.797) as the labelled comparison; IPCC comparator 0.45 within
the AR6 0.27–0.63 range; top-5 leading-emitter ranking for all countries stays beside the map;
§1.3.2 lag analysis is out of scope.

| # | Decision |
|---|---|
| 57 | **Anchors and order (final design).** Overview: `#climate-signal → #relationship → #top-emitters → #share → #by-country → #percent-change → #pathways`; the anchor row sticks on scroll. Module sections: causal chain, long-run relationship (headline), recent all-gas relationship 1970+ (tagged NOT TCRE), gas composition, country responsibility, scenarios, methodology & sources. |
| 58 | **Product name is "Climate Analytics Platform" everywhere** (landing nav, inner header, tab titles, **footer and About page** (owner, 2026-10-04), meta/OG tags, PWA manifest). Current sites to change: `navigation.ts` (`APP_TITLE`, `LANDING_TITLE`), `DashboardLayout.tsx:137`, `LandingLayout.tsx:81`, `AboutPage.tsx:41` (heading and any body copy naming the product), `index.html` `<title>`, `vite.config.ts:108` (PWA manifest name), and the footer, which takes its text from `APP_TITLE`; tests asserting the old strings are updated with them. Nav gains **Climate Correlation**; Data Explorer and About move to the footer and menu so the nav fits one line at 1280px. |
| 59 | **Landing carousel auto-rotates, controlled only by its Play/Pause button (owner decisions 2026-10-04; amends the design's "manual only").** Rate-limited per requirements doc §2.1: **10 s on each banner**; a visible Pause/Play button first in tab order (WCAG 2.2.2) is the **only** thing that starts or stops the rotation: it loops while on; moving to a banner by hand (arrows, tab buttons, ←/→) leaves it on and starts the dwell afresh; the pointer, keyboard focus and the browser tab have no effect; starts paused under `prefers-reduced-motion`. *(An earlier revision also paused on hover/focus/hidden tab and stopped after one cycle; a pointer resting on the banner held it paused indefinitely, so those rules were removed.)* Banners **slide sideways** (500 ms): going forward the next enters from the right and the old leaves left, going back reverses it; no motion under reduced motion. The slide region is `aria-live="off"` while rotating and `polite` when paused. Built app-local (`CardCarousel` in `design-system` is a paged card row, not a hero carousel); promote to `design-system` only if reused. The globe keeps its own play/pause; the carousel button governs the banners only. |
| 60 | **Country-share gains an all-countries snapshot and annual values (owner decision 2026-10-04; additive, read-only; design 2026-10-04).** **Why:** (G1) rankings are capped at `limit ≤ 50` while the data has ~215 countries, but the Cumulative choropleth and the Cumulative columns of the All/Expanded tiers need every country at one year; (G2) the series carry only cumulative values, but the Share section's "flow" bar needs the annual share, for all three measures. **Where the work belongs:** `pipeline/country_share.py` already computes each country's annual emissions (`cumulate()` → `annual`) and throws them away after the cumsum; decisions 46–55 make the API read-only over pipeline outputs, so the annual values are **written by the pipeline, never recomputed in the API**. **Pipeline:** `correlation_country_share.csv` gains two columns after `share_pct`: `annual_mt` (the country's emissions that year; a missing year inside a record is the same zero `cumulate()` already uses) and `annual_share_pct` (`annual_mt` ÷ the sum of all countries' `annual_mt` that year × 100 — the same national-sum, bunkers-excluded denominator as the cumulative share, per decision 37); a year whose national annual sum is zero is a pipeline error, like the cumulative case. **API (`GET /api/correlation/country-share`):** (1) `ShareRow` and `SharePoint` gain `annual_mt` and `annual_share_pct` (`number \| null`; null when the CSV predates the columns, so an older pipeline output still serves, with a note). (2) New query parameter `all_countries: bool = false` on the ranking form: returns every country at `year` (default: the latest), ranked by cumulative share, `limit` ignored and reported as null. Rejected with 422 when combined with `countries` (a series) or with an explicit `limit`. (3) `limit` becomes optional (default stays 15, max 50) so an explicit `limit` can be told apart from the default; no existing request changes meaning. (4) The response adds `annual_total_mt` (sum of `annual_mt` at `year`; null for older outputs) beside `total_cumulative_mt`. **Not changed:** the 10-country series cap, `source`/`gas_scope` validation, 404 for unknown codes, every 503 consistency check (the optional columns are validated only when present: both columns together, and finite values; a negative annual value is allowed because the pipeline already reports it as a deviation but still publishes it). **Deploy:** the Mac Mini's CSV gets the new columns on its next pipeline run; no migration, and until then the new fields are null. Tests: pipeline (columns, annual sum = reconciled national sum, shares sum to 100 per year), API (snapshot, 422 combinations, older-CSV tolerance, 503 on a malformed annual column). |
| 61 | **`design-system` gains a secondary y-axis and a vertical reference line for `SyChart` (G3; spike 2026-10-04, by reading `SyChart.tsx`, not a prototype).** `SyChart` has one `yaxis`, `referenceY` only, no `referenceX`. The Overview relationship chart (bars + line on two axes) needs the first; the 1959 splice markers and the 2025 scenario start need the second. Per-point colours (`pointColors`), stacked/percent area, horizontal stacked bars and point annotations already exist and cover the scatter, composition and Share bars. Separate small PR in the sibling `design-system` repo, before the pages that use it. |
| 62 | **Globe (G5) is checked in Step 2 of the sequence.** Whether `Globe` supports hiding values/legend while playing and the continuous 1970–2024 rotation is read from `Globe.tsx` first; any gap becomes a `design-system` PR. |
| 63 | **Step 6 design (Overview C; owner review 2026-10-05), originally split 6a Share / 6b Pathways + anchors; re-sequenced by decision 64 into 6a page year, 6b Share, 6c year-following sections, 6d Pathways.** **Share (6a).** One `/country-share` *series* request per measure (OWID CO₂ = `owid_co2`/`co2`, PRIMAP CO₂ = `primap_hist`/`co2`, PRIMAP all-GHG = `primap_hist`/`total_ghg`), for the Selected countries (≤10), 1970 → the data's last year; switching measure refetches. Each frame is read straight from the points: stock = `share_pct` (cumulative since the response's `cumulative_from`), flow = `annual_share_pct`; **Rest of world = 100 − Σ selected**, exact because the denominator is the national sum (decisions 37, 60). **Fixed order and colours:** selected countries sorted by the *last* year's stock share, then Rest of world; one colour per country shared by both bars, assigned by that order. **Bars are plain DOM flex segments** (not Plotly): width tweens with `transition: width 250ms linear`, off under reduced motion; the section has a semantic legend table (country · stock % · flow %) that doubles as the accessible data and the only place small segments are readable. Inline label rule: ≥ 8 % code + value, 3–8 % code only, < 3 % none. **Playback is user-initiated only** (no autoplay — the map already auto-plays when scrolled into view and two simultaneous animations compete): ▶/❚❚, 1970 → latest at 250 ms/year, stops at the end and replays from 1970, slider scrubs and pauses; reduced motion keeps Play but drops the tween. **Graceful states:** no countries selected → prompt; request fails (e.g. a selected code the source does not cover) → the API's own message, other sections unaffected; `annual_share_pct` null (pipeline output predates decision 60) → the flow bar and its column are omitted with a one-line note, the stock bar still works. Baseline chip reads the response (`cumulative since {cumulative_from}`). **Pathways (6b).** The final design's closing block, not the 2a/2b chart treatments: heading "Where today's patterns lead", the generated one-line summary (emissions ratio and temperature gap from `spread.reading_note_facts`, not the long `reading_note`), the warning chip "ILLUSTRATIVE · IMPLIED OUTCOMES, NOT PROJECTIONS", three scenario cards (name, method from the response, implied 2040 temperature, 2040 emissions), links to Forecasts and Scenario Comparison; the full scenario charts live in the module (Step 8). Unavailable scenario data → the section is omitted, never zeros. **Anchors.** The sticky row becomes Climate signal · Relationship · Top emitters · Share · By Country · % Change · Pathways; `#pct-change` is renamed `#percent-change` (design name) with the old id kept on a wrapper, as `#map` was. **Not in scope:** the design's note that By Country "follows the map year" — By Country stays the existing latest-year chart, unchanged (raised with the owner). |
| 64 | **Page year — one year for the middle of the Overview (design update, owner 2026-10-05; amends decisions 12 and 63).** A sticky **Year** control sits at the right of the anchor bar: a select over the decade stops (1970, 1980 … 2020, latest) plus ▶ Play at ~1.75 s per stop. The map's decade stops and Play change the **same** value; the map slider still scrubs single years (the select then shows that year as an extra option). Default latest; kept in the URL (`/overview?year=2010#share`, alongside `?countries=`; an unknown year falls back to the latest). **Follows the page year:** map, summary tiers, leading-emitter ranking, CO₂ ppm card, Share, By Country, Top Movers, % Change, each with a year badge in its header. **Does not follow it:** Climate signal KPIs (always the latest year), the relationship chart (full series), Pathways (2025–2040). **Share:** the slider is removed; "▶ Replay 1970 → {year}" animates at ~250 ms/year, then returns to the page year; while it runs the readout reads "replaying · temporary" and nothing else on the page changes; changing the page year or pressing Play cancels it (this replaces decision 63's slider and "Play from the end"). **By Country:** the existing chart, titled "CO₂ Emissions by Country ({year})" and re-sorted for that year; Top Movers measure "1990 → {year}". **% Change:** titled "CO₂ % Change by Country, 1990–{year}", axis rescaling per year; for years ≤ 1990 the chart and Top Movers grey out with the prompt "The baseline is 1990… choose 2000 or later." **Data:** no API change — `/world-map` already carries every country's annual values from 1970, so By Country, % change and movers for any year are computed in the client from it (the same definitions the API uses; the 1990 base is inside the series). **Mobile:** the page year is the first chip of the sticky chip row; tapping it opens a bottom sheet with the stops and Play. Supersedes the "By Country stays the latest-year chart" reading of decision 63. **The map no longer auto-plays when it scrolls into view** (Step 5a's behaviour): the page year is a shared, URL-kept value that the other sections follow, so it moves only when the user presses Play or picks a year (the design's own mock starts paused). **Step 6a scope:** the control, the URL, and the map/tiers/ranking/ppm following it; Share, By Country, Top Movers and % Change follow in 6b/6c, which also add their year badges (the map, ranking and ppm headers already state the year); the mobile bottom-sheet chip is left to the Step 10 mobile pass, the control simply wraps under the anchor links meanwhile. |
| 65 | **Step 7 design — the Correlation module, split 7a / 7b (2026-10-05).** **7a: shell, causal chain, headline relationship.** `/climate-correlation` gets the sticky anchor row (Causal chain · Global relationship now; Country view, Scenarios, Methodology join as Steps 8–9 build them — an anchor exists only with its section) and the intro. **Causal chain** (`#causal-chain`): four cells in one bordered strip — Emissions, Concentration, Forcing · concept (hatched, "Not calculated here", the existing `FORCING_CONCEPT_ONLY` copy), Temperature — each with its latest value, year and baseline chip, every number from the API (world emissions from `/world-map` totals, concentration and anomaly from the climate signal). **Global relationship** (`#global-relationship`): the era-coloured scatter (the Landing's `ClimateScatter`, on the dark chart panel) beside a stat card "Warming per 1,000 GtCO₂" with the slope (0.520 °C), the Newey–West 95% CI, R², the window and years, and the fossil + cement-only slope (0.797, a second `/emissions-temperature?variant=fossil` request), then an **AR6 strip** (axis 0.20–0.90, very-likely band 0.27–0.63, markers at the two slopes, the 0.45 best estimate named) — the AR6 figures are hard-coded copy per owner decision D (decision 40), everything else is read from the response — and a baseline card (reference 1850–1900 mean, formula ΔT = T − mean(T₁₈₅₀–₁₉₀₀), range, excluded years from the response, plus the Berkeley Earth vintage caveat while unreconciled). R² comes from the API (0.903), not the design mock (0.91). The caption says correlation, not proof of cause; the sentence pointing at the all-gas chart arrives with 7b. Climate data unavailable → the module says so once and omits the chain and relationship, never zeros. **7b: recent all-gas relationship (1970+).** The PRIMAP-hist `/emissions-temperature?source=primap_ghg` view as its own chart, tagged "Recent all-gas relationship · not TCRE" (never called TCRE, never compared with the AR6 range), with its slope, CI, R² and the stability summary and caveats the API publishes. Decision 41's fit-quality copy stays out until the owner asks. |
| 66 | **Step 8 design — gas composition, country view, scenarios; split 8a / 8b (2026-10-05).** **8a: gas composition + country view.** **Gas composition** (`#gas-composition`, requirements §1.3.3): from `/ghg-composition` (PRIMAP-hist, CO₂-equivalent on the AR5 100-year GWP basis the response states), a 100%-stacked **area** of CO₂ · CH₄ · N₂O · fluorinated gases over **1970 → the latest complete year** (the all-gas window; the response's own incomplete trailing year is excluded and stated), and a **selected-year bar** (slider, default latest) with a table of shares and MtCO₂e; one fixed colour per gas; the API's basis note and the caveats that belong beside it (national totals exclude land use and aviation/shipping, so CO₂ here excludes deforestation; shares sum the gases included that year, residual vs PRIMAP's national total is published) behind a disclosure. **Country view** (`#country-view`, §1.3.4): two cards — "Share of cumulative CO₂ since 1850, %" (multi-line from `/country-share` series, **default the five largest cumulative emitters** from the all-countries snapshot, editable up to 10, end-of-line labels via the legend and a table equivalent) and "Global temperature anomaly, °C" (annual line at reduced opacity + the 5-year mean, from the temperature endpoints) — with the info banner that shares describe contribution to emissions and **no country series is regressed against temperature and no warming is attributed to a country**; the share denominator is the national sum (bunkers excluded), the baseline chip says so. Each section degrades alone (request fails → that section is omitted, never zeros). Anchor row gains **Country view**. **8b: scenarios** (`#scenarios`, §1.3.5): "Implied temperature by scenario, 2025–2040" with the illustrative label, the annual-emissions chart (observed 2015–latest + three pathways, 2025 start marked) and the implied-temperature chart (observed annual + 5-year mean, pathways, the anchor, the 2040 gap), and the **reading note** — the API's `reading_note` verbatim (generated server-side from the output, decision 43), shown only when the API publishes one. Anchor row gains **Scenarios**. |
| 67 | **Step 9 design — methodology & sources, split 9a / 9b (2026-10-05).** `#methodology` is the module's last section (anchor row gains **Methodology**; the Overview and Landing already link to `/climate-correlation#methodology`). Nothing here is typed in that the API supplies: it reads `/meta` (and, in 9b, the headline response's `fit_context`). **9a: sources, baselines, why the numbers differ.** (1) A **sources table** — Source · Used for · Coverage · Vintage · Licence — from `/meta.sources`, the dataset-level rows merged by source name (OWID country + World, PRIMAP-hist country + composition, Berkeley Earth, NOAA GML + Law Dome annual + monthly); coverage, retrieved/published vintage and the licence text are the API's (the licence is whatever the API states, verbatim — e.g. Berkeley Earth is CC BY-NC 4.0 International, non-commercial; never a figure typed into the UI); only the short "used for" phrase per source is fixed copy; the dataset the pipeline has not yet licence-verified says so in the API's own words. (2) A **baselines-by-view table** (requirements §2.5: Overview/Historical/Scenario Comparison 1990 = 100; Country Profile full OWID history; all-gas and composition 1970 onward; long-run relationship 1850–1900 reference; global non-ML totals full range) as fixed copy, with the **computed 1850–1900 temperature offset** (−0.306 °C, 51 years) from `/meta`. (3) Three short notes: why the emissions series differ (scope, method, bunker treatment, vintage — fixed copy), the **two global totals** (the API's `two_global_totals` text verbatim), and the **1959 splice** (splice year, overlap years and the gap, from the concentration response). Each part degrades alone; if `/meta` fails the section says so once and the table is omitted, never blank cells. **9b: "How this number was derived"** — the single-open accordion (first open, `aria-expanded`) with the design's seven steps, each body read from the headline response's `fit_context` where the API has the numbers (what is regressed on what; the Newey–West bandwidth sensitivity; land-use sensitivity; the seeded residual-block bootstrap, block-length sensitivity and decade holdouts; the AR6 comparison; the attribution list) and fixed copy only for "what this is not". The mobile pass of the module moves to Step 10 with the other phone-width checks. |
| 68 | **Step 10 — cross-cutting audit: method, findings, fix plan (2026-10-05).** **Method:** axe-core 4.10 (WCAG 2.0/2.1 A + AA + best-practice) run in the browser on the Overview, the Correlation module and the Landing page, in **both themes**; a 390 px iframe (media queries respond) for **horizontal overflow** and screenshots of the Overview and module on a phone-width viewport; the reduced-motion paths are covered by their unit tests (carousel, replay/tween, map, globe) and were not re-run in a browser. **Findings, mine to fix (10a, contrast/landmarks):** (1) muted text (`--__s9cmpx-static-text-weak` #5C7683, designed for white surfaces at 4.7:1) sits directly on the tinted page background (3.84:1) or on baseline chips (3.6:1; dark theme 3.98:1) in the baseline chips, the Year label, the ppm card, footnotes and the Pathways/Scenario captions — fixed by an Area 2 muted-text variable scoped to the new surfaces (darker in the bright theme, lighter in the dark theme) rather than changing the shared token; (2) the "illustrative" chip and the vintage caveat use a fixed amber (#8A5A00): 4.0:1 on the light tint and 2.2–2.3:1 on dark — now theme-aware; (3) the app's default link colour on the new Overview/Pathways links is 4.49:1 (light) and 2.4–3.0:1 (dark) — themed; (4) "Why emissions matter" is an `<aside>` nested in `<main>` (complementary landmark must be top level) — made a labelled section. **Findings, mobile (10b):** the Overview's sticky row wraps to three lines (~140–170 px of a 784 px viewport) and the module's to two; no horizontal overflow on either at 390 px. Fix per decision 64: on phones the Overview row becomes one horizontally scrollable line led by the **page-year chip**, which opens a **bottom sheet** with the decade stops and Play; the module's row scrolls on one line. **Findings for the owner (design-system, not changed here):** the shared `JumpLinks` inactive text is 3.84:1 (light) / 3.46:1 (dark) and the map's "Reset view" button 3.3:1 — both come from the same token; the fix is a darker `text-weak` in the bright theme (e.g. #4A6270: 5.1:1 on the page, 6.4:1 on white) or a dedicated token for text on the page background, which changes every consumer and is therefore the owner's call. **Not re-verified in a browser:** the globe/map playing animation (hidden preview tab throttles timers), the carousel under reduced motion (tests only). **No PWA change:** no new gated route was added, so `navigateFallbackDenylist` is unchanged. |
| 69 | **Step 10b design — phone navigation (2026-10-05; implements decision 64's mobile paragraph and decision 68's finding).** Below **640 px** (`(max-width: 640px)`): (1) the **anchor rows** of the Overview and the Correlation module become **one horizontally scrolling line** (no wrapping; scrollbar hidden; a soft fade at the trailing edge signals more; the current link -- which follows clicks and deep links, the shared component does not track scrolling -- is scrolled into view), which takes the Overview's sticky area from ~140–170 px to one line; (2) on the Overview the **page year** leaves the row as a **chip** pinned at its left ("Year 2024 ▾", `aria-haspopup="dialog"`, with a "playing" mark while Play runs) that opens a **bottom sheet**: a modal dialog (focus moves in and returns to the chip, Tab is trapped, Escape and a tap on the backdrop close it, page scroll is locked while it is open) holding the decade stops as buttons (`aria-pressed` on the current one, any slider-chosen year listed too) and Play/Pause; picking a stop or pressing Play closes the sheet so the change is seen on the page, and it uses the same year value as every other control. Above 640 px nothing changes (the select + Play in the row). One control renders at a time (a media-query hook, not CSS hiding), so assistive technology never sees two. The sheet's slide-in is dropped under reduced motion. Tables and chart cards that are wider than a phone already scroll inside their cards (checked: no horizontal overflow of the page at 390 px on either page). |
| 70 | **Deploy plan for Section 2 (Step 10c; a plan, written 2026-10-05 — nothing below has been run).** The Mac Mini already serves Section 1 (pipeline + `/api/correlation/*`, deployed 2026-10-03), so Section 2 is one combined deploy of three things, in this order, each verified before the next: **(1) data + API.** Pull `main`; run `python -m pipeline.run --source all` once (this adds the `annual_share_pct` columns the Share section needs, from the Step 2 API change, and refreshes the Berkeley Earth provenance, which a local copy had stale against the pipeline's CC BY-NC correction); restart **only** the uvicorn job; check `/api/correlation/{meta,country-share,scenario-temperature}` return 200, that `/meta` shows Berkeley Earth as CC BY-NC 4.0, and that country-share series carry `annual_share_pct`. The prior state is restorable from the data-directory backup the run makes and the previous commit. **(2) design-system.** Pull the sibling `design-system` checkout to its current `main` (it supplies the retuned `--__s9cmpx-static-text-weak`, `SyChart` no-data fix and others; the app reads it live from that working tree, so an old checkout silently fails contrast and breaks the empty map layer). **(3) frontend.** `npm ci`, then `DEPLOY_BASE_PATH=/ npm run build` — **the point of no return**, since the preview server serves `dist/` live off disk — so copy the current `dist/` aside first as the rollback. Then verify on `climate-analytics.syena.io`: `/` (landing, carousel, globe), `/overview`, `/climate-correlation`, one deep link with a `#anchor` and one with `?year=`, the theme toggle, and a phone width. Browsers that already visited need the service worker unregistered and a cache-busted reload to see it (known PWA behaviour, not a deploy fault). **Not part of this deploy (separate owner decisions):** swapping the live refresh job to `pipeline/ops/ghg-data-refresh.sh` and its plist (weekly → monthly; ops README steps 3–5), and decision 41. Re-run the audit's axe check on the live pages after the build (both themes) before calling it done. |
| 71 | **Banner 1's second button goes to the correlation module (owner-requested 2026-10-05, after the deploy).** On the climate banner (Banner 1) "See the climate signal" (→ `/overview#climate-signal`) and "Explore the data" (→ `/overview`) both led to the Overview. The second becomes **"Explore climate correlation" → `/climate-correlation`**, so the banner offers two different places and the module has a way in from the Landing page. The primary button and the "Forecasts to 2043 →" link are unchanged. **Dwell time: tried 5 s (2026-10-05), reverted to 10 s the same day at the owner's request** (decision 72); decision 59's "10 s on each banner" stands. The original hero banner keeps its "Explore the data" → `/overview` (it is about the emissions dashboard, and it is also what the page shows while data loads or fails, so that fallback keeps its way in). |
| 72 | **Landing carousel on phones: compact banners with the controls close, after Claude Design's mobile frame (owner-requested 2026-10-05, after the deploy; also reverts the dwell to 10 s).** Measured at 390 × 664 on the live build: the controls sat ~1,480 px down the page, the climate banner was 1,404 px tall and the globe banner 1,276 px, so on an iPhone the Pause/Play and the way between banners were far below the content and the banner lost the desktop's effect. At ≤ 640 px: **(1) controls** become one row under the banner — previous, a Pause/Play button, a dot per banner (the active one a longer pill; each still a ≥ 44 px tap target with its name kept for assistive technology) and "1 of 2", next — instead of a wrapping row of labelled buttons; the Pause/Play button stays first in DOM and tab order (WCAG 2.2.2) and nothing about auto-rotation changes. **(2) Banner 1** (climate signal): smaller headline, the temperature and CO₂ concentration as **two side-by-side cards** (the third figure, the slope, is dropped on phones — it is the chart's own reading and the Overview/module headline; this follows the design frame), the chart panel compacted (its baseline chip, source note and "not a climate model" line stay), and the buttons full-width and stacked, **with the "Forecasts to 2043 →" link kept below them** (decision 71 leaves it unchanged; an early cut hid it on phones, which dropped the phone landing page's forecast entry point). **(3) Banner 2** (emissions): smaller headline, buttons full-width and stacked, the three KPIs in **one row** (not three stacked rows), then the globe. The measured heights before/after are in the PR. Desktop and tablet layouts are unchanged. |
| 73 | **Phone carousel: the controls float in view, and both banners share one order (owner-requested 2026-10-05, after trying decision 72 on a phone; amends 72).** Compacting the banners (decision 72) still left the controls below the first screen, so a visitor would not know the banner moves or how to go back and forth until it moved. Modelled on the Fitch Ratings mobile hero, whose pagination dots sit in a pill at the bottom of the first screen: at ≤ 640 px the controls row becomes a **pill pinned to the bottom of the viewport while the carousel is on screen** (CSS `position: sticky; bottom`, so it docks at the carousel's own end instead of following the visitor down the page), with the same contents (previous, Pause/Play, a dot per banner, "1 of 2", next) and **larger dots**, and the page reserves scroll-padding for it so a focused element is never left hidden behind it (WCAG 2.2 focus not obscured). It overlays the lower edge of the banner at the first screen; that is the cost of keeping it in view. **Banner order is now the same on both:** copy → figures → picture → buttons. For the emissions banner the buttons (Explore the data, Forecasts to 2043) move **below the globe**, after the KPIs and the globe, as the climate banner's already sit below its chart. Desktop and tablet are unchanged. |
| 74 | **A phone in landscape keeps the phone header on the Landing page (owner-reported 2026-10-05).** The landing header collapses its links behind the Menu button below 768 px wide (design-system's `useIsMobile`), so a phone turned sideways (~844 px wide) got the desktop link row, which wrapped to three lines. The header now also uses the compact menu when the screen is short and landscape (`(orientation: landscape) and (max-height: 500px)`: phones in landscape are ≤ ~430 px tall, tablets and desktop windows are taller), so portrait and landscape look the same. **Not changed here:** the dashboard pages' sidebar follows the same design-system `useIsMobile` internally and so still shows its desktop sidebar on a landscape phone; making that consistent means changing `useIsMobile` in `design-system`, which the India Allocation Monitor and India IPO Intelligence also use — an owner decision. |
| 75 | **Landing globe plays twice as fast: 700 ms → 350 ms a year (owner-requested 2026-10-05).** One constant (`GLOBE_STEP_MS`) drives three things that stay in step: the year advances every 350 ms, the colours blend over that same 350 ms, and the globe makes its single turn across the whole 1970 → latest pass, so the pass takes about **19 s instead of ~38 s** and the globe turns about twice as fast. Pause/Play, the slider, reduced-motion behaviour and the 1-year step are unchanged. Supersedes the "~700 ms a year" in decision 12's Landing description. |
| 76 | **iPad: the landing page uses the compact header and the carousel pill (owner-reported 2026-10-05, from an iPad; amends 72–74).** On an iPad the six page links wrapped to a second line in the landing header and pushed the banner controls down. The compact header (logo + menu button) and the bottom carousel pill now apply up to **1100 px** (the page's one-column breakpoint), and up to **1440 px on a touch screen** (`(max-width: 1440px) and (pointer: coarse)`, so an iPad Pro 13 in landscape, 1376 px, is covered while a laptop window that wide keeps the desktop header). One shared `TABLET_QUERY`; the two CSS media queries repeat it. The phone-only pieces (the stacked buttons after the picture, the compact KPI/metric cards) stay at ≤ 640 px. |
| 77 | **Jump links follow the scroll and are pinned on every page (owner-requested 2026-10-05).** (1) On Overview and Climate Correlation the underlined link stayed on the last one clicked while scrolling; a `useScrollSpy` hook now picks the current section (the last whose top has passed under the header + the pinned row, the first one before that, the last once the page can scroll no further) and feeds `JumpLinks`' `activeId`. (2) The pinned row of Area 2 is now on the older pages too (Historical Trends, Country Profile, Forecasts, Scenario Comparison, Data Explorer) as `StickyJumpLinks`: the same sticky row, scroll-spy, and a `scroll-margin-top` for jump targets (every id except the shared `#main-content`, which keeps the app-wide 68 px). Deep-link jumps on load wait for the row's first measurement, since the offset depends on whether it wrapped. |
| 78 | **Landing globe: labels and rotation stay while it is on screen (owner-requested 2026-10-06; amends decisions 12 and 75).** Decision 12 hid the per-country MtCO₂ labels while the globe spun and tied rotation to Play. Now the labels are always shown, and the globe turns whenever it is on screen (viewport check) **and its banner is the showing one**, playing or paused — Pause stops the years, not the turning. Under Reduce Motion it turns only while the visitor's own Play press runs, as before. |
| 79 | **Phone banners: picture before figures, and a new Banner 2 subtitle (Claude Design update `Area 2 Final Design.dc.html`, 2026-10-06; owner-confirmed; amends 72–73).** **(1) Subtitle (all viewports):** Banner 2's paragraph becomes *"Global CO₂ emissions have grown by more than two-thirds since 1990, and the 10 largest emitters now account for 71% of the total."* — both numbers computed, not typed: the growth from `pct_change_since_1990` (direction-aware: "fallen by N%" for a decline, "barely changed" if it rounds to 0%; for a rise "grown by more than two-thirds" from 66.7%, "doubled" at exactly +100%, "more than doubled" above it, else "grown by N%"), and the **71%** from the **same top-10 share the "10 countries, N% of the world's CO₂" ranking-race heading uses** (`raceShare` over `raceFrame` of the final year, extracted into one shared helper), so they change together. **(2) Phone order, both banners: copy → picture → figures → buttons.** Banner 1: the chart now sits above the two figure cards. Banner 2: the globe comes straight after the copy, its "2024 · 37,398 MtCO₂ · all countries" readout is the caption **under** it (not above), followed by Play, the year slider and the legend; the globe is capped at about **62 % of the viewport height** so Play and the slider stay with it. **(3) Banner 2 phone figures** are two cards, **+68.6 % since 1990** and **71 % from the top 10 emitters in 2024** (the 37,398 and "40 Expanded set" figures are dropped on phones — the readout carries the total; desktop and tablet keep the three KPIs). The cards repeat the subtitle's numbers; the design allows swapping one for a forecast figure if that reads as too much. **(4) Carousel controls: the owner kept the floating pill (decision 73) rather than the design's in-flow row**, and pads each banner at the bottom by the pill's height so it docks below the picture and buttons at rest; the design's concern (the pill covering the chart or globe) is therefore reduced, not removed, while the carousel's end is below the screen — to be judged in the 390 px preview. **Not taken from the design:** its eyebrow reads "1990–2024", but the globe plays 1970–2024 so the eyebrow keeps showing the data's real span; its "swipe to change banners" and "banner height fixed to the taller one" mobile rules are not part of this change (the latter conflicts with decision 72's showing-slide-only height). |
| 80 | **Two phone-preview fixes after decision 79 (owner-reported 2026-10-06, from a 440 px preview).** **(1) Globe labels no longer overprint (design-system `Globe`, owner-confirmed).** With the per-country labels always on (decision 78), a ~400 px phone globe showed "Ukraine 737" over "Germany". `Globe` now places labels **largest first and skips any whose box would overlap one already placed**, then keeps filling from the next-largest until its cap (3 on a small globe, 5 on a large one) — so the picture stays readable at any size, on desktop as well. No app change and no per-viewport rule. **(2) The carousel pill becomes translucent glass, not an opaque bar (owner-requested).** It keeps its place (decision 73, padded under each banner per decision 79), but its background is a semi-transparent tint of the surface with a backdrop blur and saturation boost, a hairline border and a softer shadow, so the picture shows through while the controls stay plainly visible and obvious — the owner does not want the controls faded or hard to find, so the buttons, dots and "n of 2" keep full-strength text. Two guards: where `backdrop-filter` is unsupported the pill falls back to the old opaque surface, and under `prefers-reduced-transparency` it is opaque as well; the contrast of its text is checked in both themes. The design's in-flow alternative was weighed and not taken. |
| 81 | **Shorter banner titles (owner-requested 2026-10-06).** Banner 1: *"Warming tracks the CO₂ we’ve accumulated"* (was "Global temperature has risen with the CO₂ we have accumulated."). Banner 2: *"Where the world’s CO₂ comes from"* (was "… — and where it’s heading."). The "where it's heading" half is carried by the subtitle and the Forecasts button, and by the page's closing call to action ("Pick a country. See where it’s heading."), which is unchanged. The same Banner 2 title is the landing page's heading while its data loads or fails, so both places change together. The apostrophes are typographic (’), as in the rest of the copy. **Both titles carry no ending period (owner, 2026-10-06).** |
| 82 | **Phone Banner 2: the year, total and legend sit clear of the pill at rest (owner-reported 2026-10-06, from an iPhone).** On a real phone the globe took the design's fixed ~62 % of the screen height, which left its caption (year · total) and colour legend underneath, exactly where the floating pill docks, so the pill covered them. The globe on a phone is now sized to **what fits**: the stable (toolbars-shown) viewport height, minus where the globe starts on the page, minus the Globe panel's padding, the **measured** height of its caption and legend (the legend wraps onto more lines on a narrower phone, so a fixed reserve was not enough) and the pill's zone — never above the design's 62 % and never below 160 px. The viewport height used is **stable**: it follows a rotation but not Safari's toolbar collapsing while scrolling, so the globe does not resize under the visitor's finger. To buy room, the phone landing header keeps the product name on one line and the banner's gaps are tightened. **The year · total caption steps down with a small globe but keeps a legible floor** (year 22 → 18 px, total 13 → 12 px) rather than shrinking proportionally. Checked at 390×664, 360×740, 430×760 and 430×875: the legend ends 9–12 px above the pill or further. The pill itself is unchanged (translucent glass, decision 80). The trade-off is a smaller globe on a short phone; on a tall one the 62 % cap still applies. |
| 83 | **Berkeley Earth source moves to the high-resolution annual file (Zeke Hausfather's reply, 2026-10-06; owner-approved plan 2026-10-06; implemented on `feat/berkeley-earth-hr-source`, PR pending merge).** Berkeley Earth replied that the high-resolution dataset is now their operational product and the S3 `Land_and_Ocean_summary.txt` (last modified 2025-01-10) is superseded. New source: `https://storage.googleapis.com/berkeley-earth-temperature-hr/global/Global_TAVG_annual.txt` (Last-Modified 2026-09-14; land analysis run 2026-09-11, ocean published 2026-08-13; 1850–2025 contiguous, 176 rows; same columns and 1951–1980 baseline). **Measured before implementation (2026-10-06):** computed 1850–1900 offset is −0.265 °C (was −0.306); 2024 = 1.285 °C native → **1.550** above 1850–1900 (old file 1.617); 2025 = 1.186 → **1.451** (Berkeley's Jan-2026 report: 1.44 ± 0.09); 2023 = 1.214 → 1.479 (report-implied ≈1.47). The new file therefore **reconciles the vintage discrepancy of decision 17** (2024 ≈1.52 implied; file gives 1.55, within the stated uncertainty). **Differences to handle:** (1) the file is headed *PRELIMINARY DATA – SUBJECT TO CHANGE WITHOUT NOTICE – NOT YET PEER REVIEWED* with *no citation currently available* — provenance drops the Rohde & Hausfather 2020 citation as the product's own, adds a `preliminary: true` flag and a caveat, and the dashboard source/methodology copy says so; (2) the header's absolute-mean line is garbled (`14.107 +/- 0.0000.0000…`) and has no air/water split, so `parse_release` takes the value leniently or omits it rather than failing; (3) licence terms for this product are not yet confirmed — the CC BY-NC wording is carried as *the data page's stated terms* and verified against the data page/README in the implementation step. **Decisions (owner, 2026-10-06):** operational source = the high-res annual file despite its preliminary status, with a visible caveat; set `berkeley_earth.vintage_reconciled: true` in `pipeline/source_notices.json` **when the implementation PR merges** (the reply settles which file is current and the numbers match the January 2026 report), removing the ~0.1 °C caveat from the headline output; the old S3 URL is **retired outright**, no fallback (a stale source must not be served silently). Open items 10 and 11 are closed by this decision once shipped. **Implemented and re-measured (2026-10-06, real file):** pipeline run reports 0 deviations (the standing stale-source alert clears). Headline **0.520 → 0.486** °C per 1,000 GtCO₂ (95% HAC CI [0.442, 0.530], R² 0.903 → 0.888, n 175; now inside the AR6 very-likely 0.27–0.63); all-gas **0.579 → 0.572** [0.522, 0.621], R² 0.917 → 0.910; scenario anchor (2020–24 mean) **1.390 → 1.320** °C, 2040 BAU/Moderate/Aggressive headline levels 1.68/1.64/1.58 (were 1.78/1.73/1.67). `vintage_reconciled: true` is set in `source_notices.json`; the preliminary status travels in provenance (`preliminary: true`, a PRELIMINARY caveat, the BEST-HR preprint citation doi:10.5194/essd-2026-412) and, because the vintage caveat slot is otherwise empty once reconciled, the same `temperature_source_vintage.caveat` carries a one-line preliminary-release note to the dashboard. **Copilot review of PR #260 (2026-10-06), all four findings valid and fixed:** preliminary wording (provenance caveat, source label, catalog caveat) now derives from the parsed header flag, not hardcoded; `vintage_reconciled` is honoured only when provenance `source_urls` names the new file (a failed Berkeley run no longer lets old provenance inherit the flag); the catalog's preliminary note is built from provenance for base and derived temperature indicators; the remaining README measurements were regenerated. **Side effect found while regenerating:** on the new series the headline's land-use trade-off is sharper — holdout RMSE (split 2000) 0.211 vs 0.103 °C fossil-only (was 0.174 vs 0.126), R² 0.888 vs 0.902, and the land-use weight scan is monotonic rather than U-shaped, so `fit_quality_note` now omits the "similar in-sample" sentence; fossil-only slope 0.749 [0.705, 0.793]. Licence: Berkeley's data page states CC BY-NC 4.0 "in general" with no separate terms for the beta high-resolution files — carried as stated. |
| 84 | **The temperature caveat is shown whenever the API sends one (found checking the live dashboard after decision 83's deploy, 2026-10-06).** `vintageCaveat()` in `climate-dashboard-react/src/lib/climateSignal.ts` surfaced the caveat only while `source_vintage.reconciled === false`, so once decision 83 set it true the preliminary-release note (carried in the same slot) never reached the Overview/landing/module pages — contradicting decision 83's claim that no frontend change was needed. Fix: surface any non-empty `caveat`; `reconciled` now only changes *which* caveat it is. Unit test updated (reconciled + preliminary note → shown; no caveat → null). Needs a frontend rebuild on the Mac Mini (the build flips prod live; owner confirmation before the build). |
| 85 | **Landing banner lines visible in the light theme (owner-reported 2026-10-06).** The KPI rows' rules (and the phone metric cards' borders) on **both** banners (Banner 1 `ClimateSignalBanner`; Banner 2 `Hero` in `LandingPage.tsx` — missed at first, owner-spotted) and the carousel controls' top line — plus the **landing header's bottom line and the mobile menu's** (owner asked whether the light header should be darker; decided no, give it a visible edge instead) — used `--__s9cmpx-static-divider-weak`, which on the Tidewater landing background (`#dce8ed`) is *lighter* than the page (`#e5eef1`; even divider-strong is 1.24:1), so they vanished. They now use `color-mix(text-weak 55%, transparent)` (themed, so it holds in dark), with divider-strong as a fallback. Not changed: the carousel buttons' own faint borders, the "Where CO₂ comes from" cards (`ChainBand`, same token) and the phone pill. Owner confirmed in a local light/dark preview; no Copilot review requested. Needs a frontend rebuild on the Mac Mini. |
| 86 | **Two temperature years, labelled (owner question 2026-10-07).** After decision 83 the temperature series runs to 2025 but the emissions data (OWID) ends at 2024, so the Home KPI showed **+1.45 °C (2025)** under an eyebrow reading "1850–2024" while the Climate Correlation chart labelled **2024 · +1.55 °C** — both correct, different years (2025 is ~0.1 °C cooler, matching Berkeley's January 2026 report), but unexplained. Owner chose option 1 of three (relabel; not aligning the KPI to 2024 and not possible to extend the chart): the Banner-1 KPI caption reads "2025 (latest), vs 1850–1900" and a one-sentence note beside the Banner-1 chart and the Correlation module's headline chart says the chart ends at 2024, the last year with CO₂ emissions data, and that the latest temperature has no emissions to pair with. Both appear **only when the latest temperature year is after the pair's end** (`isTemperatureAheadOfPair` / `pairedEndNote` in `climateSignal.ts`), so they disappear when OWID catches up. The Overview KPI ("Temperature anomaly · 2025") already carries its year and is unchanged. |
| 87 | **Carousel button borders visible in the light theme (owner, 2026-10-07; committed straight to main on the owner's say-so).** Follow-up to decision 85, which left them: the carousel's Pause/Play, previous/next and banner-tab buttons used `divider-standard` (`#c7d9e0` on the `#dce8ed` Tidewater page, ~1.15:1), and the phone pill's no-blur fallback border used it too. The controls row now defines one `--carousel-line` (themed `text-weak` at 55%, divider-strong fallback — the same colour as the KPI rows and header) and uses it for its top line, the buttons and the pill fallback. Same change: **Banner 2's KPI row gains the bottom line** it lacked (owner-requested from a screenshot; Banner 1's row already had one) with 16px bottom padding on each KPI so the text doesn't touch it. Unchanged: the pill's glass border when backdrop-filter is supported (decision 80) and the "Where CO₂ comes from" chain-band cards (not a carousel element, same weak-divider token — still open). No tests assert the colour; landing/page tests pass. |
| 88 | **Favicon and share image switched from Syena's logo / the Vite bolt to the app's globe (owner, 2026-10-07; committed straight to main on the owner's say-so).** The header icon is the 🌍 emoji (platform-rendered, so not usable as an image file); the favicon was still the Vite template bolt and `icon-192/512.png` — the `apple-touch-icon` and PWA manifest icons — were the **Syena bird**, which link-preview scrapers fell back to because the page had no Open Graph tags. Now: an original SVG globe illustration (no third-party artwork) — `favicon.svg` (transparent, globe only), `app-icon.svg` (source: globe at 70% on the app's navy `#121e35`, inside the maskable safe zone) and `icon-192/512.png` rendered from it; `index.html` gains `og:*` / `twitter:card=summary` tags with absolute URLs and `icon-512.png` as the share image. The globe is a stylised Africa/Europe view like the emoji, drawn by hand — swap `app-icon.svg` and re-render the PNGs for a designed mark. Link-preview caches (Slack, iMessage, WhatsApp, LinkedIn) and browsers' favicon caches hold the old image until re-scraped/refreshed; an installed PWA / home-screen icon needs re-adding. |
| 86 | **Two temperature years — the Home banner KPI follows its chart (owner question and follow-up 2026-10-07).** After decision 83 the temperature series runs to 2025 but the emissions data (OWID) ends at 2024, so the Home banner showed **+1.45 °C (2025)** beside a chart labelled **2024 · +1.55 °C** (both correct; 2025 is ~0.1 °C cooler, matching Berkeley's January 2026 report). The owner first chose to relabel ("2025 (latest)" plus a chart note); seeing it, they judged the KPI and chart still not in sync, so it was changed: the **Banner-1 KPI now reads the chart's own last point** (`pairedTemperature` in `climateSignal.ts` → **+1.55 °C, 2024**), matching the chart label and the "1850–2024" eyebrow; the banner's chart note was dropped. **The CO₂ figure follows too** (owner, same day): the KPI row is one year throughout — `pairedConcentration` reads the concentration for the pair's last year (**424.6 ppm, 2024**, falling back to the latest if that year is missing) instead of the 2025 reading, so the row is 2024 temperature, 2024 CO₂ and the 1850–2024 eyebrow, never 2024 beside 2025. The **Correlation module's headline chart keeps a one-sentence note** (`pairedEndNote`) that it ends at 2024, the last year with CO₂ emissions data, and that the latest temperature has no emissions to pair with — shown only while the latest temperature year is after the pair's end. Unchanged, each labelled with its own year: the Overview KPI ("Temperature anomaly · 2025", +1.45 °C) and the chain band's step 04, which are latest-value readouts with their own sparklines, not beside a paired chart. Trade-off: the newest temperature and CO₂ readings (2025: +1.45 °C, 427.4 ppm) are no longer on the Home banner itself; the Overview KPI strip and the chain band still show them. |

**Requirements-doc amendments — applied 2026-10-04 as tracked changes (author Claude) to the Drive
`.docx`; the pre-edit file is kept beside it as `*.bak-20261004.docx`.** The Drive file read on
2026-10-04 had no tracked changes, i.e. the amendment open item 18 records as done on 2026-10-02 was
not in it (cause unknown), so the decision-40 changes were re-applied here. Changes: a 2026-10-04
revision note; product name (Purpose); §1.3.1 headline = total anthropogenic CO₂ incl. land use with
the fossil-only fit as a labelled secondary and the AR6 range shown with both; methodology note
replaced with decision 40's copy plus a land-use sensitivity bullet; §1.3.2 lag analysis out of scope;
§1.3.5 land-use held flat after the last observed year and a fossil-only second line; §2.1 carousel
rate-limited autoplay with Pause/Play (decision 59); §2.4 headline wording. Validated against the
schema. **Not added:** decision 41's fit-quality copy (to be added when the owner asks, per decision
41) and the API-level details of decisions 30–39 (as in item 18).

**Implementation sequence** (one branch + PR per step; visual preview confirmed before each frontend merge;
**no Mac Mini deploy until all of Section 2 is complete — owner decision 2026-10-04**, so no feature flag or
production gate is used; `npm run build` is the deploy point of no return, so build only at that deploy):

| Step | Scope | Phase |
|---|---|---|
| 0 | This plan (docs only); dual-axis spike (decision 61) | – |
| 1 | Foundation: rename, nav, `/climate-correlation` stub route, typed correlation client + hooks, shared pieces (baseline chip, ⓘ baseline panel, purpose line, source note, copy-guardrail constants) | 2.5 |
| 1b | `design-system` PR: `SyChart` secondary axis + `referenceX`; check `Globe` (decision 62) | – |
| 2 | API PR: decision 60 | – |
| 3 | Landing: carousel (decision 59), Banner 1, Banner 2, four-step band (forcing copy-only), continuous globe | 2.1, 2.6 |
| 4 | Overview A: sticky anchors, KPI strip + baseline panels, relationship chart + toggle, "Why emissions matter" | 2.2, 2.5 |
| 5 | Overview B: map — Absolute/Cumulative, decade stops, tiers, ppm card, top-5 ranking, all synced to the year | 2.2, 2.6 |
| 6a | Overview C1: **page year** — lift the map's year to page state, sticky Year control + URL `?year=`, map/tiers/ranking/ppm follow it, year badges — decision 64 | 2.2 |
| 6b | Overview C2: Share (stock vs flow, three measures; **Replay 1970 → year**, no slider) — decisions 63, 64 | 2.2 |
| 6c | Overview C3: By Country, Top Movers and % Change follow the page year; ≤1990 greyed — decision 64 | 2.2 |
| 6d | Overview C4: Pathways closing block, `#percent-change` anchor — decision 63 | 2.2 |
| 7a | Module A1: shell, causal chain, headline relationship (stat card, AR6 strip, baseline) — decision 65 | 2.4, 2.5 |
| 7b | Module A2: recent all-gas relationship (1970+, not TCRE) — decision 65 | 2.4, 2.5 |
| 8a | Module B1: gas composition (stacked area + selected-year bar), country view (share lines + temperature) — decision 66 | 2.4 |
| 8b | Module B2: scenarios (emissions + implied-temperature charts, reading note) — decision 66 | 2.4 |
| 9a | Module C1: methodology & sources — sources table, baselines, why the numbers differ (decision 67) | 2.4 |
| 9b | Module C2: "How this number was derived" accordion (decision 67) | 2.4 |
| 10a | Audit fixes: contrast in both themes, theme-aware amber and links, landmark — decision 68 | 2.3 |
| 10b | Mobile: page-year chip + bottom sheet, one-line scrolling anchor rows (Overview, module) — decisions 64, 68 | 2.3 |
| 10c | Copy & traceability audit, docs revision (SPEC/ENHANCEMENTS/ARCHITECTURE), deploy plan | 2.3 |

Tests: Vitest per page/component with `SyChart` stubbed (existing pattern); carousel timer logic with
fake timers (pause on interaction, hover/focus pause, reduced motion, one-cycle stop, hidden-tab pause).

### Section 3 (MCP & agent) — design (docs-first, 2026-10-08)

Source: requirements doc §§3.1–3.6 and §1.4's "agent-ready" clause. Sections 1 and 2 are built; this
section's design lives in `services/mcp-server/SPEC.md` §5.1 and `services/agent/SPEC.md` §15, with
tracking in each sub-project's `ENHANCEMENTS.md`. The Section 3 stubs written 2026-10-01 were stale
(EDGAR, fossil-only headline, Berkeley vintage caveat) and were replaced.

| # | Decision |
|---|---|
| 89 | **Seven new MCP tools, one per bounded endpoint, plus an extended `get_methodology_notes`:** `get_co2_concentration`, `get_temperature_anomaly`, `get_correlation_metadata`, `get_emissions_temperature_relationship`, `get_ghg_composition`, `get_country_cumulative_share`, `get_scenario_temperature`. No aggregation tool (decision 3 holds); no change to `api/`. `include_lag_analysis` is not exposed (lag analysis out of scope, requirements §1.3.2). |
| 90 | **"Annotated summaries" = a deterministic `summary` object computed in Python** (first/last, change, slope/R²/CI, latest readings), so the model quotes numbers instead of deriving them. Same precedent as `get_emissions_change_summary`. Tool results stay free of UI directives (mcp-server `SPEC.md` §3.5); "chart-ready structures" means the structured series the widget consumes. |
| 91 | **Model sees a capped copy; the widget gets the full series (owner, 2026-10-08).** MCP tools return full data; the agent's `tools_node` stores the full result in `ToolCallRecord.result` and hands the model `summary` + ≤ ~25 evenly spaced points (first/last always kept) with `points_total`/`points_shown`. The cap is agent-side (`payload_cap.py`), keeping the MCP server consumer-agnostic and stateless. Envelope caveats are never capped away. |
| 92 | **Intent routing needs no new node.** Emissions / climate-context / combined is the `guardrail_router` classification plus the model's tool choice. The real risk is `general_climate` swallowing data-shaped relationship questions (it answers without tools), so the classifier prompt gains examples; "who is responsible for warming?" is a `data_query` answered with cumulative share, not an `opinion` decline. |
| 93 | **Caveats are structural, not prompt-only.** When an Area 2 tool succeeded, fixed per-tool statements are appended to `scope_notes` (the existing `InlineAlert` channel). The Berkeley preliminary-release note always accompanies a temperature-bearing result. Deterministic, so it cannot be omitted or drift. **Refined at implementation (step 3.3, 2026-10-08):** the statements are a fixed per-tool table in `services/agent/src/agent/caveats.py`, appended in `ui_selection_node`, not a pass-through of each result's raw envelope `caveats` (up to seven items per call of pipeline/licence prose, some already outdated upstream). The model still sees the full envelope. |
| 94 | **Terminology guardrails.** OWID cumulative CO₂ (1850+) is the "headline long-run relationship"; the PRIMAP-hist 1970+ pairing is the "recent all-gas relationship" and is never called TCRE; no country-level temperature attribution (cumulative share only); scenario temperatures are "implied" / "illustrative, partial-coverage translation". Verified by a golden-prompt eval set (real LLM, gated and skipped without a key — the repo's one-real-network-test rule). |
| 95 | **Widget mapping reuses existing `SyChart` capabilities** (second axis, stacked area, scatter-with-fit as already built for the Correlation module): relationship → line (`y2`) / cumulative scatter; composition → stacked area; share → line or bar; scenario temperature → line; latest readings → `KpiStat` card. No new design-system work expected. |
| 96 | **`follow_up_links` (owner approved 2026-10-08).** A new per-turn state/SSE field `[{label, route}]` of real in-app navigation links (Overview, Climate Correlation, Forecasts, Scenario Comparison), chosen by a **fixed tool→route lookup** (no model-invented routes) covering **emissions-only tools as well as Area 2 tools** (owner, 2026-10-08), at most three, rendered under the latest result only. Distinct from `suggested_prompts`, which prefill the prompt bar and exist only on `opinion` turns. Additive: absent for existing turns. |
| 97 | **Starter grid becomes 2×3 (owner).** Two "Climate context" tiles: *"Show the relationship between cumulative emissions and warming."* and *"How do temperature outcomes vary based on different emissions pathways?"* Same prefill-and-focus behavior as the existing four. |
| 98 | **Sonnet is the validated provider for Area 2 (owner).** The Ollama/Qwen option stays selectable in the admin panel and is kept for testing, documented as not validated for climate-context questions; the guardrail eval runs on Sonnet only. Structural guardrails (decision 93, the follow-up lookup) are provider-independent. |
| 99 | **`MAX_TOOL_CALLS_PER_TURN` stays 6.** A combined question needs ~3–4 calls; revisit only on observed truncation. |
| 100 | **No new auth or exposed surface.** The tools call the already-public read-only `/api/correlation/*` over the existing localhost B3 leg; nothing new is exposed through the tunnel (consistent with the "API has no auth yet" constraint and decision 13). |
| 101 | **Sequencing (one branch + PR each, docs direct to main):** 3.1 mcp-server plumbing + indicator tools; 3.2 mcp-server relationship/composition/share/scenario tools + methodology; 3.3 agent routing, guardrails, caveat channel, payload cap, eval; 3.4 agent widgets, progress labels, `follow_up_links` backend; 3.5 frontend (Ask-page renderers, link row, 2×3 grid) with visual preview before merge; 3.6 deploy (mcp-server → agent → frontend rebuild) and live walkthrough of the six starter prompts. |
| 102 | **Ask-the-Agent redesign adopted (design handoff received 2026-10-08; owner decisions same day).** Source: `climate-dashboard-react/design/ask-the-agent/` (README + an HTML reference, not production code; the Area 2 handoff it builds on is committed beside it in `design/area2-climate-context/`, see `design/README.md`). **Prompt cards PREFILL, they do not send** (SPEC.md §4 stands; the handoff's "click sends" is not adopted). **Layout: the handoff's three category columns** — HISTORICAL TRENDS, CLIMATE OUTCOMES (NEW tag), FORECASTS — two prompts each, which supersedes decision 97's 2×3 grid; the two Climate-outcomes prompts are the owner's, unchanged. The China, India and second forecast prompts take the handoff's wording (SPEC.md §4 table updated at implementation). Mobile: one column grouped by category. |
| 103 | **Earlier answers stay visible (owner).** `Keep them visible`: the thread is retained, "+ New question" starts a fresh thread. With the input pinned to the bottom the natural order is chronological with the newest answer in view; the current newest-first stack is **to be confirmed at the visual preview**, not assumed. |
| 104 | **`PromptBar` is redesigned in the design-system (owner), as its own PR before the Ask page.** Whole-field focus ring (never an inner rectangle), 40×40 (mobile 44×44) send button, hint line, prompts BELOW the field and outside it on the landing state, and a docked state pinned to the viewport bottom with follow-up chips above it. The `expandedContent` mechanism (design-system PR #44) is retired for this page. |
| 105 | **Agent answers reuse the Correlation module's components (owner).** New-tool renderers in `WidgetRenderer` (which dispatches by tool NAME, not `chart_kind`) wrap the module components fed by the tool result — e.g. `buildScenarioView` + `ScenarioSection` consume the same API JSON the tool returns. Consequence: the `scatter`/`area` chart kinds added in step 3.4 are unused and are **removed** from the backend contract. |
| 106 | **Answer blocks.** Beyond widgets and `response_text`, an answer carries: a lead that states figures (a deterministic lead from the API's `reading_note`, decision 43, for scenario answers; for others the compose prompt is changed from "don't restate numbers" to "state the key figures"); a KPI set labelled with its year; a source/scope line under every chart (Area 2: from the envelope's attribution; Stage 1 emissions tools: a fixed per-tool string — the designer asks us to confirm whether land use is included in country charts); deep links; follow-up prompt chips (a field separate from `follow_up_links`: chips are prompts, links are navigation). Exact backend schema is written before step 3.5a. |
| 107 | **Deep links carry state in the URL.** Bare routes (step 3.4) become routes with confirmed hash anchors and query state. Anchors confirmed in the built pages: Correlation `#global-relationship`, `#scenarios`, `#gas-composition`, `#country-view`, `#recent-all-gas`; Overview `#climate-signal`, `#relationship`, `#top-emitters`, `#pathways`. **The handoff's `#relationship` on the Correlation page is wrong** (that is the Overview's anchor). Query contract (`countries`, year range, `country`) is implemented by Historical Trends, Country Profile and Scenario Comparison in their own PR — **none of them reads URL state today**. |
| 108 | **Independent fixes found in the review (separate PR, ahead of the redesign):** `get_top_emitters` requires a `year` and the model chose 2020 — default to the latest data year; titles use "–"/"CO₂" instead of "--"/"CO2"; drop the duplicate single-country trend chart when a historical chart for the same country is already in the turn. |
| 109 | **The handoff's figures are pre-migration and must never be hardcoded.** Slope 0.520 (CI 0.480–0.559), fossil comparison 0.797, anchor 1.39 °C, 2040 levels 1.79/1.73/1.68, gap 0.11 °C are superseded by the current pipeline values (0.486 [0.442–0.530], 0.749, 1.32 °C, 1.68/1.64/1.58, 0.10 °C); the "Berkeley Earth vintage caveat" is now the preliminary-release note (decision 83). Every number on the page comes from the tool result. |

**Revised Section 3 sequencing (supersedes decision 101's steps 3.4–3.6):** 3.4 backend contract (PR #268, amended per 105 and 107) → 3.4b the decision-108 fixes → 3.5a agent answer blocks and chips (schema doc first) → 3.5b dashboard URL-state on three pages → 3.5c design-system `PromptBar` → 3.5d the Ask page and the seven new renderers (visual preview before merge) → 3.6 deploy and live eval.

Open items for this section: (a) ~~monthly concentration mode~~ — resolved 2026-10-08: annual only (no page shows monthly), (b) Overview anchors for the link row
are only used once confirmed in the built page; (c) the OWID-vs-PRIMAP "5–8%" reconciliation figure
was estimated against EDGAR and is still to be re-measured (requirements §1.1.2) — the agent must not
quote it as a measured PRIMAP-hist figure until it is.

### Progress

- Docs-first stage written (this entry, `SPEC.md` §5.26, sub-project pointers).
- **Section 2 (Frontend) — built 2026-10-04/05 and DEPLOYED to the Mac Mini 2026-10-05** (decision 70 followed as written: pipeline run + uvicorn-only restart, design-system pulled to `05f47bd`, then the root-base build; live bundle `index-zepswzJp.js`, previously `index-BSSWBm-n.js`; `/`, `/overview`, `/climate-correlation` verified rendering with real data, `/mcp` 403, `/admin` 302 to Access). A browser that had visited before showed the old landing until its service worker was unregistered (the known PWA behaviour). Rollbacks left on the Mini: `~/dist-prev-section2`, `~/data-prev-section2-20261005`, and the git stash `pre-section2-deploy 20261005` (re-executed notebook outputs). **Originally this entry read:** built, not deployed. Steps 0–10b merged (PRs #230–#251, design-system #102–#105), 10c's copy-audit fixes in PR #252; decisions 57–70. Held (owner): the Mac Mini deploy until all of Section 2 is done — that is now this section's last item, planned in decision 70. Open owner decisions: decision 41 (fit-quality copy; the API's `fit_quality_note` is not rendered) and the muted text of the two bright themes this app does not ship (`analytics-bright-signal`, `-broadsheet`).
- **Phase 1.1a — merged (PR #201, 2026-10-02).** `pipeline/` foundation, NOAA/Law Dome CO₂ (276 annual rows, 1750–2025; 822 monthly), Berkeley Earth annual anomaly (175 rows, 1850–2024; computed 1850–1900 offset −0.306 °C). Copilot review: missing-year validation, monthly freshness and atomic `last_run.json` added.
- **Phase 1.1b — PR #202 (EDGAR + ISO3 crosswalk), Copilot-clean, awaiting mentor merge.** Live EDGAR 2026: 224 entities × 56 years; per-gas sum vs combined total −0.47% … −0.38% (1990–2024); F-gas file has no 2025 or pre-1990 data. After review the scope changed (decision 20): EDGAR merges as a **dormant, internal-validation-only** source (excluded from `--source all`, output to `data/internal/edgar/`, `published: false`); its EDGAR outputs were purged from `data/climate/`.
- **Phase 1.1b — merged (PR #202)** as a dormant, internal-validation-only EDGAR source (decision 20).
- **Phase 1.1b′ — merged (PR #203)**: PRIMAP-hist ingestion with the emission-weighted completeness test (decision 22); live v2.8: 207 areas × 1750–2024, 0 deviations, 2025 excluded.
- **Phase 1.1c — merged (PR #204, `4617508`) and deployed 2026-10-02.** OWID step (decision 23), notification contract and refresh wiring (decision 24). Copilot loop on #204: three passes, five findings, all real or answered — a unit test that silently downloaded 73 MB of PRIMAP-hist per run (now an autouse network guard; suite ~4 min → ~11 s), OWID absent-year hole, duplicated `OWID_URL`, restored-file mtime masking the stale check (`cp -p` on all four copies), plus the plist/API-cache comment answered by `restart_api`. **Deploy verification (Mac Mini):** preflight (clean apart from the weekly job's own notebook artifacts; no `api/`, `app.py`, `notebook/constants.py` or frontend changes incoming — the only `requirements.txt` change was an unused `openpyxl` pin for the dormant EDGAR source, and `services/` changes were two markdown files), stage dry-run (4 sources ok), install, `bootout`/`bootstrap`, then one full run: backup ✓, OWID download 14,377,942 bytes ✓, week 1 `clean` ✓, pipeline stage ran (4 ok, 1 deviation = Berkeley staleness) ✓, weeks 2–5 ✓, `Restarted com.ghgemissions.uvicorn` ✓ (PID 62897 → 41129; agent, MCP server and vitepreview PIDs unchanged), API health 200, `/api/overview` 200 locally and through `climate-analytics.syena.io`. **Phase 1.1 is complete and deployed.** Rollback if ever needed: restore `~/bin/ghg-data-refresh.sh.bak-20261002` and `~/Library/LaunchAgents/com.ghgemissions.datarefresh.plist.bak-20261002`, then `bootout`/`bootstrap`. Next: Phase 1.2 (harmonized analytical layer).

- **Phase 1.2 — design written (decisions 25–29).** **1.2a — merged (PR #207, `8668d77`):** derive.py, harmonize.py, indicator catalog + harmonized global/country tables as a derived stage (21 base + 46 derived indicators on real data; every checked value matches an independent calculation). Copilot loop: two passes, six findings, all real and fixed — anomalies now carry the trailing mean as decision 28 says, cumulative indicators no longer advertise a baseline, catalog provenance links carry the source checksums, derived entries inherit their base's description and caveats, a missing country column no longer crashes the stage (reproduced), and a test that asserted `or True` was corrected. **1.2b — merged (PR #209):** `pipeline/pairing.py` (`load_harmonized`, `align_pair`; mutation-checked), plus two review follow-ups applied by the owner from GitHub (deep-copied provenance/caveats in the result metadata; `min_overlap >= 1`) which I covered with tests. **Phase 1.2 is complete.** Refinements to decision 29 settled while building it: (a) country-scope pairs need an explicit `geography` (one area for both series) and a global/country pair is refused; (b) `uncertainty` indicators are not pairable (they describe a series, they are not one); (c) "omitted years" are the years inside the *requested* range where `a`, `b` or both have no value, each with that reason, while the requested/common/used ranges are reported as metadata (listing every year outside the requested range would be noise); (d) the pair carries both indicators' catalog entries including provenance links and caveats, and a standing causation note.
- **Phase 1.3 — design written (decisions 30–39)**, grounded in measurements on the real data (slope, HAC lag sensitivity, window grid, bootstrap variants, holdout, scenario anchor). Implementation sequence: 1.3a → 1.3b → 1.3c → 1.3d, one PR each. **Decision 40 (headline redefined to total anthropogenic CO₂, 0.797 → 0.520) approved 2026-10-02.** **1.3a is two PRs:** data layer (**merged, PR #211**: OWID land-use column and cumulative, total-CO₂ indicators, attribution carried in provenance links, late/early-start guards, licence/citation provenance, scipy pin; Copilot loop: two passes, four findings, all real and fixed, including a dangling `see land_use_license_note` reference) and the regression core (**merged, PR #212**; Copilot loop: four passes, seven real findings, all one theme — what the stage does with bad or stale input — fixed, ending in a structural never-stale guarantee, plus a `run.DEPENDS_ON` gate so `correlate` is skipped when `harmonize` fails in the same run: `pipeline/correlation.py`, stage `correlate`; headline 0.520 [0.480, 0.559], fossil-only 0.797, AR6 range, HAC/window/land-use sensitivities, Berkeley vintage caveat; HAC verified against an independent Newey–West implementation). **1.3b follow-up — merged (PR #214):** generated `fit_quality_note` (decision 41) and `land_use_weight_scan` (decision 42). **1.3c is three PRs; 1.3c-i (recent all-gas relationship, decision 35) — merged, PR #215:** separate `correlation_all_gas.json`, 0.579 [0.533, 0.626] °C per 1,000 GtCO₂e, R² 0.917, n = 55; never called TCRE (a test scans the file), no IPCC comparison, licence/citation/excluded-years/vintage carried; **1.3c-ii (GHG composition, decision 36) — merged, PR #216** (Copilot: five real findings — gate on `primap_hist`, require provenance coverage, reject unusable years and totals instead of skipping, gas-neutral caveat — all fixed): `composition` stage, the long file + JSON metadata; 2024 = CO₂ 75.1 / CH₄ 16.7 / N₂O 5.4 / F-gases 2.9%; real data showed two things the design did not anticipate — nothing is null (PRIMAP-hist reports F-gases as 0.0 in 1750 and positive from 1850, so the null machinery guards a future release), and the 1750 composition is 95% CH₄ because national CO₂ excludes land-use change, flagged by a data-generated caveat (the UI should not open on 1750). **1.3c-iii (country cumulative share, decision 37) — merged, PR #217:** `country_share` stage; ~95k rows over three combinations (OWID CO₂, PRIMAP CO₂, PRIMAP total GHG); 2024 USA 24.1 / 24.0 / 20.5%, China 15.8 / 15.9 / 15.6%; denominator is the national sum (2.49% below the World series by design); a worry that non-ISO entities (USSR etc.) understate the historical denominator was checked and does not apply (OWID allocates them to successor states; World = ISO3 sum + transport to 0.0%); 47 OWID countries have 1800s gaps counted as zero and listed (≈ 0.015% of the total); reconciled exactly to the published artifacts. **1.3d (scenario temperature translation, decisions 14/38/39) — PR #218 open; it completes Phase 1.3:** `scenario_temperature` stage; to 2040 BAU +0.40 → 1.79 °C, Moderate +0.35 → 1.74 °C, Aggressive +0.29 → 1.68 °C (headline; fossil-only line +0.55 / +0.48 / +0.38); the scenarios differ by only ≈ 0.11 °C in 2040 although their emissions diverge strongly (an incremental cumulative-emissions model over 16 years, plus the flat land-use assumption common to all); all three scenarios start 2025 at +3.7% above the 2024 observed covered total, a step reported per scenario and in a generated caveat; stale-scenario guard per decision 39; skipped in a full run when `correlate`, `owid` or `berkeley_earth` failed. **Decision 43 (UI shows annual emissions and implied temperature side by side, with a generated reading note) recorded; follow-up PR after #218 merges.** **Backlog B2 recorded (the 2025 pathway step is a modelling artifact of the 2018-fitted ETS; per-country steps −51% to +62%; option 4's on-chart annotation is to be considered in the Area 2 UI).** **B2 updated: recommended path is Option A (a second, plain full-data ETS fit for the Week 5 / Area 2 feed; Week 4 untouched) — COVID-in-training does not distort and clearly helps near-term accuracy.** **Option A built in PR #219 (open): `ets_baseline` + `step_check`; Option 1 kept as the fallback; Kuwait looked at (Backlog B3, not COVID).** **After #218 merges: Section 1 continues with 1.4 (the `/api/correlation/*` endpoints, docs-first) and 1.5, then the deferred Mac Mini deploy.** **Decisions 41–42 recorded** (41: UI/agent copy for the land-use fit-quality trade-off, incl. the in-sample vs out-of-sample sentence, generated as `fit_quality_note` in a follow-up PR after #213 merges; 42: a "How this number was derived" section linked from the methodology note, numbers read from pipeline output, with the land-use weight scan moving into the pipeline and the two-predictor analysis script committed). **1.3b — merged (PR #213)** (Copilot loop: one real finding — row-based bootstrap blocks could span calendar-year gaps, 18% of blocks in a reproduced 10-year-gap case — fixed with gap-aware sampling that leaves gap-free results unchanged, plus a `contiguous` flag and HAC-gap deviation; the second pass found nothing) (seeded residual block bootstrap, four decade holdouts, generated summary; coverage of a known slope 0.92 on simulated data). Open item 16 remains.
- **numpy upgrade — PR #208 merged** (verified before/after; see open item 13); the Mac Mini's venv is upgraded as step 0 of the deferred deploy. **Berkeley inquiry record — PR #210 merged** (open item 11).

- **Berkeley Earth source migration — docs written and implemented 2026-10-06 (decision 83)**; PR open on `feat/berkeley-earth-hr-source`; after merge approval: Mac Mini deploy (pipeline run + API restart; no frontend rebuild needed unless copy changes).

- **Section 3 (MCP & agent) — design written 2026-10-08 (decisions 89–101)**; implementation not started. Next: Step 3.1 (`services/mcp-server` plumbing + indicator tools).

- **Section 3 step 3.3 — implemented 2026-10-08** (`services/agent`): model-facing payload cap, deterministic climate notes, guardrail prompts and routing examples, lint + a manually-run golden-prompt eval, progress labels for the seven new tools. The live eval has **not** been run (no `ANTHROPIC_API_KEY` in the dev environment) — to be run on the Mac Mini before deploy (step 3.6). Also fixed a stale agent test left failing by steps 3.1–3.2.

- **Section 3 step 3.4 — implemented 2026-10-08** (`services/agent`): widgets/titles for the seven Area 2 tools (titles built from the result so the all-gas relationship is never titled TCRE/headline and non-headline OWID windows never "headline"), `follow_up_links` (lookup, state, SSE field; emissions-only tools included per the owner), and Area 2 `summary` objects reaching the compose node. Verified end to end against the real API + MCP server. PR #267 (3.3) merged after a four-round Copilot loop.

- **Section 3 step 3.4b — implemented 2026-10-08** (`services/agent`): the agent-side decision-108 fixes (year from the result, omit-the-year prompt rule, "–"/"CO₂" typography, resolved-name headers, no duplicate single-country chart). Steps 3.4, 3.4b-MCP and 3.5a are merged (#268–#271).

Revised again once each phase ships.


## Backlog (not scheduled)

Things deliberately left as they are for now, with enough detail to pick them up later. Numbered `B<n>`; items stay here until done or dropped.

### B1 — ETS forecast bands are not reproducible (added 2026-10-02; owner decision: leave as is)

**What.** `notebook/week4_ets_forecasting.ipynb` computes the 95% bands in `data/ets_forecasts.csv` (`ci_lower`, `ci_upper`) with `fit.simulate(nsimulations=…, repetitions=1000, error='add')` and **no `random_state`**, in both the §4.2 example cell and the per-country loop. Every run is a fresh Monte Carlo draw.

**Evidence (2026-10-02).** Two runs on identical data and identical numpy (2.2.6) differ in `ci_lower`/`ci_upper` for all 1,000 rows, by up to ~1,550 / ~740 Mt, with a median band-width change of ~2.8%; China's 2043 lower bound was −5,436 in one run and −3,386 in another. `year` and `mean` (the forecast itself) are identical in every run. It was found while verifying the numpy upgrade (PR #208) and is **not** caused by numpy: 2.2.6 → 2.3.5 differs by the same amount as a rerun under 2.2.6.

**Effect.** The dashboard's forecast bands and the API's `forecasts/{country}` `ci_*` values move at every scheduled refresh with no change in the data. Nothing breaks, and the headline forecast is stable, but the bands can't be quoted precisely or compared across refreshes, and a before/after comparison of any change that regenerates the notebooks has to treat these two columns as noise.

**Options (not chosen).** (1) Seed the simulation (`random_state=`): reproducible, a one-line change per cell. (2) Also raise `repetitions` (1,000 draws are noisy in the 2.5%/97.5% tails at long horizons). (3) Use analytic prediction intervals instead of simulation.

**Why it waits.** It is a change to an intern-curriculum notebook (and the curriculum text on confidence intervals would need a matching note), so it is a deliberate decision rather than a fix to slip in. **Pick up when:** the forecast bands are quoted or compared anywhere (the Forecasts page, the agent, a Phase 1.3 scenario view), or the curriculum notebooks are next revised.

### B2 — The 2025 scenario pathways step up from the 2024 observed total (added 2026-10-02; owner decision: backlog; option 4 is to be considered for the Area 2 UI)

**What.** All three Week 5 scenarios start in 2025 at 35,740 Mt for the 40 covered countries, **+3.7%** above their 2024 observed total (34,477 Mt). The Phase 1.3d translation uses the pathways as given and reports the step per scenario (`base.first_scenario_year_vs_last_observed_pct`) and in a generated caveat whenever it exceeds 2%.

**Diagnostic result — the owner's recommended first check ("real data-vintage transition, or a modelling artifact?") is answered: a modelling artifact.** `notebook/week5_scenarios.ipynb` sets BAU to the **Week 4 ETS forecast mean** and applies the reduction as `(1 − rate)^years_elapsed`; `years_elapsed` is 0 in 2025, so all three scenarios share the BAU 2025 value and diverge from 2026. The ETS is fitted on `year <= TRAIN_CUTOFF` (**2018**) and forecasts 2019–2043 (`notebook/constants.py`), so the 2025 level is a **7-step-ahead extrapolation that never sees the observed 2019–2024 years**. Both the observed and the forecast series derive from the same OWID source, so there is no source or vintage boundary to disclose. **The aggregate +3.7% hides much larger per-country errors that partly cancel:** per country the 2025 BAU value differs from 2024 observed by a **median of +7.0%**, from **−50.9% (Venezuela) to +61.9% (Ukraine)**; only **4 of 40 countries are within ±2%**, 27 are above it and 9 below; the largest absolute contributors are the United States (+228 Mt), India (+205), Japan (+177) and Germany (+173). The translation uses the covered-country *total*, so the effect on the temperature result is the aggregate step, but any per-country view of the pathways (the existing Scenario Comparison page) inherits the larger per-country offsets.

**Options (owner-supplied, with the recommended path):**
1. **Anchor 2025 to the observed 2024 total — recommended, if the diagnostic shows a modelling artifact (it does).** Set each scenario's 2025 starting point to *2024 observed × (1 + the scenario's own year-1 rate)* per country instead of the independently-modelled ETS value. It is the same continuity-at-the-boundary principle as the regression-to-scenario handoff (trailing mean, not the regression line). A small change to the notebook's scenario-generation step, not a redesign. Because the cause is the per-country level, it should be applied **per country** (re-anchoring only the aggregate would leave the per-country offsets).
2. **If the step were a real data-vintage transition, disclose it instead of forcing continuity.** *Checked: it is not (see above); no disclosure-only path applies.*
3. **Smooth the transition (a short linear taper 2024→2026) only if a real discontinuity is expected.** Not indicated here: nothing in the pathways justifies a genuine step at 2025, so a taper would add complexity without addressing the cause.
4. **Interim, if the notebook change cannot land first: keep the caveat, but make it per-scenario and quantified in the UI, shown directly on the chart where the scenario lines begin** — a small marker or footnote at the 2025 point reading e.g. "+3.7% vs 2024 observed", not buried in a tooltip or methodology paragraph. **To be considered for the Area 2 UI (Section 2) regardless of whether option 1 lands**, as a safety net. The data for it already exists in `correlation_scenario_temperature.json` (`base.first_scenario_year_covered_mt` and `…_vs_last_observed_pct`, per scenario); on the existing per-country Scenario Comparison charts the per-country step is visible where the historical line meets the scenarios.
5. *(added by Claude, a curriculum decision for the mentor)* **Refit the ETS on all available data (through 2024) for the final forecast**, keeping the 1990–2018 / 2019–2023 split only for model evaluation. This would remove the cause for BAU itself, but it changes the Week 4 forecasts and the intern curriculum's train/test framing, so it is a deliberate decision, not a fix to slip in; option 1 achieves continuity without touching Week 4.

**Safeguard to add with the fix (owner-supplied).** A check that no scenario's first projected year diverges from the 2024 observed total by more than a sanity threshold (±2%), so recurrence is caught automatically instead of by hand. **Today it would fire on every refresh (3.7% in aggregate; 36 of 40 countries individually exceed ±2%)**, so until option 1 lands the 2% rule stays a caveat (as now), and it becomes a pipeline deviation (alert) in `scenario_temperature.py` — plus a per-country distribution in the output — once the pathways are re-anchored. A regression test for the aggregate and the per-country bound belongs with it.

**Update 2026-10-02 — owner analysis and Claude's diagnostics: the recommended path changes to a second, full-data ETS fit (Option A below), with no outlier handling.** The owner reframed the choice: the question is not "change the 2018 cutoff" but **whether Week 4's forecast output, which now also feeds Week 5 and Area 2, should be one artifact serving two purposes or two.** **Option A — two fits (recommended):** keep the 2018-cutoff fit exactly as it is for Week 4's forecast-vs-actual teaching chart (zero curriculum impact), and add a second ETS fit on the full data (through 2024) used only as the BAU input for Week 5 and the Area 2 temperature translation. ETS is cheap, so the extra fit costs nothing, and it makes explicit what is currently implicit and arguably accidental: Week 4's *evaluation* cutoff is being reused as a *production* assumption. **Option B — move the shared cutoff to 2024:** simpler, but it removes the 2019–2024 forecast-vs-actual demonstration from Week 4, a real if small curriculum change. The owner also raised the **COVID question**: the 2018-fit never saw the 2020 dip, and a refit through 2024 puts the dip and rebound inside the training data, which could distort a damped-trend model. Both were tested (scratch scripts `check.py` and `backtest.py`; reproduction of the saved `ets_forecasts.csv` agrees to 0.0005 Mt; same ETS(A,Ad,N) specification, 40 countries, fit on 1990 onward):

- **Is the 2018-fit's error concentrated in 2020–2022? No — it is a shock, then a persistent level shift, then horizon and regime effects.** 40-country total, forecast vs actual: **2019 +0.2%** (pre-COVID, the model was fine) → **2020 +6.0%** (the shock nobody could forecast) → **+2.6%, +2.3%, +2.2%, +2.4% for 2021–2024**: the aggregate rebounded (+4.8% in 2021) but never caught up to the extrapolated trend, a persistent ≈ 2.3% overshoot. 2020 is the worst single year but holds only 19% of the absolute per-country error; **2023–24 hold 43%**. The median per-country error grows from 4.0% (2019) to 11.1% (2024) and is **positive every year** (median signed error +5.4% in 2024): the 2018-fit is biased high for most countries, because it extrapolates the 1990–2018 growth regime into a period when many countries plateaued, plus country shocks (Ukraine +62%, Venezuela −51% at the 2025 step). So "the model could not see COVID" explains the 2020 miss and part of the persistent level gap, but not the whole divergence — which is horizon and trend-regime error as well. **This is a stronger Week 4 teaching story than generic staleness (shock → level shift → horizon error → regime bias) and is a reason to leave Week 4 untouched.**
- **The 3.7% step decomposes into the legitimate and the stale.** The 2018-fit's 2024 level was already **+2.4%** above the observed 2024 total, and one more forecast year adds **+1.3%**. A correctly anchored path still starts about one year of growth above 2024, so a safeguard threshold must allow for normal year-one growth (≈ 1%).
- **Does a refit through 2024 distort? No visible distortion with the plain fit.** Smoothing parameters barely move (median α 0.841 → 0.873, φ 0.965 → 0.967, β* ≈ 0 in both). The aggregate BAU trajectory is smooth (average growth 0.95%/yr, largest year-on-year move 1.07%; the 2018-fit has 1.03% / 1.24%), and the rebound is **not** extrapolated as a continuing trend. The 2025 step becomes **+0.9% in aggregate, per-country median +0.4%, 27 of 40 countries within ±2%, 37 within ±5%**; the outliers are **Kuwait −13.8%, Netherlands −5.8% and United Kingdom −5.4%** (Kuwait deserves a look).
- **Does having COVID in the training data help or hurt? It helps clearly (pseudo-out-of-sample backtest).** Fit through 2021, forecast 2022–24: median per-country error **3.5 / 6.4 / 6.8%** against **6.7 / 9.4 / 11.1%** for the stuck 2018-fit, and the 40-country total is within −1.2 to −1.6% instead of +2.2 to +2.4%. Fit through 2022, forecast 2023–24: **3.9 / 5.5%** against **9.4 / 11.1%**, total −0.6 / −0.4% against +2.2 / +2.4%. Fitting through 2019 (pre-COVID) is no better than the 2018-fit. A "last value held" baseline is competitive at one step (3.2–3.6%) but drifts to −4.2% by three steps.
- **Outlier handling is not supported.** Interpolating 2020 gives no consistent benefit (better at the 2022 cutoff, worse at 2021: 4.2 / 6.4 / 8.7% vs 3.5 / 6.4 / 6.8%), pushes the level smoothing parameter to α ≈ 0.98 (near a random walk), and creates a −40% step for Kuwait; interpolating 2020–22 also lowers the 2040 aggregate by 3.4% for no demonstrated gain. **So the owner's mitigation list is not needed: refit plainly.** The 2040 BAU aggregate differs by only ≈ 3% across all COVID treatments (38.7k–40.1k Mt), small against the scenario spread (BAU 41.7k vs Aggressive 19.3k).
- **Consequences for the options.** Option A with a **plain fit through 2024** is recommended. It removes the step at its source (+0.9%, normal growth) and makes **Option 1 (per-country re-anchoring) unnecessary**; Option 1 stays the **fallback** if the second fit cannot land (the owner noted that if refitting made the model worse, Option 1 would become the primary fix — the evidence says refitting does not). Where the second fit lives is the mentor's call: a labelled section of the optional Week 5 notebook (its BAU needs a current baseline) or the `pipeline/`. **The safeguard thresholds, revised by the measurements:** aggregate ±2% is right (the refit's +0.9% passes, the 2018-fit's +3.7% fails), but a **per-country ±2% would flag 13 of 40 even after the refit**; use **±5%** per country (3 flagged today: Kuwait, Netherlands, UK) and report the distribution.
- **Limits of this analysis.** ETS(A,Ad,N) only, no model selection; 40 countries; three backtest cutoffs with overlapping, short horizons (2–5 steps); aggregates mix large and small emitters. It tests whether the production fit is *better* than the stuck one and free of COVID distortion, not forecast skill over 16 years. Scratch scripts are in the session scratchpad and can be committed under `pipeline/analysis/` (decision 42's convention) on request.

**Status 2026-10-02 — owner decision: build Option A in `pipeline/` (PR #219); Option 1 stays in the backlog as the fallback.** The owner directed: build the second fit in `pipeline/`, apply the ±2% aggregate / ±5% per-country thresholds, look at Kuwait (not a blocker), keep **Option 1 (per-country re-anchoring) as the fallback if the second-fit work cannot land in time**, and carry the stated scope limits into the methodology documentation with the result. **Done in PR #219 (open):** `pipeline/ets_baseline.py` (the second, plain full-data ETS fit; point forecasts; ~3 s; the backtest re-run on every refresh), `pipeline/step_check.py` (the thresholds, shared), tests and the scope limits in `scope_limits` / `caveats` / `methodology` / the pipeline README. **Results:** aggregate first-year step **+0.9%** (the stuck fit: +3.7%); **37 of 40 countries within ±5%** (9 for the stuck fit); outliers Kuwait −13.8%, Netherlands −5.8%, United Kingdom −5.4%. **What I added to the owner's thresholds (for confirmation in the PR):** a per-country breach is a *note* unless **systematic (> 10% of countries outside ±5%)**, then a deviation — a few explained outliers should not page the owner monthly, while the stuck fit's 31 of 40 would. **Kuwait looked at:** not COVID; its 1991 value (493 Mt, the oil fires, 13× its neighbours) at the start of the training window drives its level-smoothing parameter to 0.145 (typical ≈ 0.85); **Backlog B3**. **Update (later 2026-10-02): the owner confirmed the decisions (including the systematic-breach rule) and directed the Week 5 notebook change.** **#219 merged. #220** fixes 25 failing scenario tests that appeared on `main` when five GitHub-applied commits landed on #218's branch after its last commit (and a real flaw: a rejected non-finite value survived into an *unavailable* output as invalid JSON). **#221 (open): the Week 5 notebook now fits its own full-data ETS** (in the notebook, not read from the pipeline, because interns do not run `pipeline/`; verified identical to `ets_baseline_full_data.csv`, max diff 0.0000 Mt over 640 values), adds the §5.2b continuity check, rewrites §5.4 from recomputed numbers (four claims no longer held), and carries the scope limits. **A new finding: the Netherlands' BAU falls 82% over 2025–2040 (to ≈ 19.5 Mt)** — the first-year thresholds cannot catch a steep long-horizon extrapolation; a per-country long-horizon plausibility check is a gap (flagged in the notebook, not fixed). **The API and Streamlit app needed a companion change** (they built BAU from `ets_forecasts.csv`, the 2018 fit, and would show a false mitigation step once the data is regenerated): **#222 (open)** makes all three scenario lines come from `scenario_projections.csv`, with each country's compare line = observed history then its projection, verified on the real API (all three scenarios start at 34,794 Mt, +0.9% on the last observed total) and on the Streamlit page. **Next, in order:** merge #220 (fixes `main`'s 25 failing tests), #221, #222; then **PR B** (the same step check inside `scenario_temperature.py` plus a comparison against `ets_baseline_full_data.csv`) and the decision-43 follow-up; then regenerate the scenario file on the Mac Mini by running the Week 5 notebook (it is not part of the monthly refresh). **Original ordering, now revised:** (1) ~~review/merge #219~~ done; (2) **PR B, after #218 merges**: apply the same `step_check` to the scenario file inside `scenario_temperature.py` (aggregate ±2% always a deviation, per-country ±5% by the systematic rule) and report that the pathways start on the stale baseline, with a comparison against `ets_baseline_full_data.csv`; (3) the **Week 5 notebook reads the new baseline** for its BAU (the mentor's call: a notebook change; I did not regenerate pathways in the pipeline, which would duplicate the scenario definitions) and the scenarios are regenerated; (4) the **Area 2 UI annotation** of the step (option 4) as a safety net regardless. **Option 1 remains the fallback** if step (3) cannot land before the scenario module ships: with the baseline now available as the reference, re-anchoring each country's 2025 to its 2024 observed value × the scenario's year-one rate is the stopgap, applied per country.

**Step 2 (PR B, 2026-10-02): the step check inside the scenario translation.** `pipeline/scenario_temperature.py` now applies the same `step_check` (±2% aggregate always a deviation; ±5% per country, a deviation only when systematic, otherwise a note) to each scenario's first projected year against the last observed value, publishes the full result as `base.step_check`, and uses the shared 2% threshold for the continuity caveat. Scenarios with identical starts are reported once. It also compares the scenario file's BAU with `ets_baseline_full_data.csv` (`base.pathway_baseline`: `current` within 0.01 Mt / `stale` = deviation naming the cause and "rerun the Week 5 notebook" / `unavailable` = note only). Today the refit scenario file is current (identical on all 640 values), aggregate step +0.9%, 37/40 countries within ±5% (Kuwait −13.8%, Netherlands −5.8%, UK −5.4%), no deviation; the old Week 4-based file, rebuilt in a temp directory, fires aggregate +3.7%, 31/40 outside ±5%, and the stale-baseline alert. Known gap unchanged: first-year thresholds cannot catch a steep long-horizon extrapolation (Netherlands BAU −82% by 2040).

**Why it waits.** It is a change to the scenario notebook (intern-curriculum code; Week 5 is optional) and the scenario page, so it is the owner's call and does not block Phase 1.3 or the 1.4 API. **Pick up when:** the scenario temperature module is built (Section 2), the Week 5 notebook is next revised, or the per-country scenario charts are shown to the public.

### B3 — Kuwait's 1991 data anomaly distorts its ETS fit (added 2026-10-02; found while looking at B2; owner: not a blocker)

**What.** OWID's Kuwait series has **1991 = 493 Mt**, against 37.9 (1990) and 29.7 (1992): the Gulf War oil fires. In an ETS fitted from 1990 the spike forces the optimiser to a very low level-smoothing parameter for Kuwait (**α = 0.145**, against about 0.85 for a typical country), so the fitted level lags the observed values and the forecast starts at **111.7 Mt against 129.5 observed in 2024 (−13.8%)**. It affects both fits: the Week 4 fit stuck at 2018 gives Kuwait −44%. **It is not a COVID effect.** A scan of all 40 covered countries for any single year more than 2× above or below its centred 7-year median finds exactly this one value.

**Measured options (Kuwait's 2025 step against the observed 2024 value).** Plain fit from 1990: −13.8% (α 0.145). **Train from 1992: +2.2%** (α 1.0). **Train from 1993: +1.0%** (α 0.83). Interpolate 1991 only: −9.8% (α 0.0 — not sufficient, because 1992 is also unusually low).

**Current handling.** None: the baseline stage fits plainly and **flags** any such anomaly (value, year, ratio to the local median, the country's parameters) so the cause is visible in the output and the notes, and it is why Kuwait's step is outside ±5% (a note, not a deviation, under the systematic rule). **Options if it needs handling:** a per-country training start (Kuwait from 1993), excluding flagged anomaly years, or leaving it as a documented, flagged exception. **Why it waits:** one country of 40, 0.3% of the covered total in 2024, a documented and visible exception; and any rule beyond "flag it" is a modelling choice that should be applied by a stated rule rather than a hard-coded country exception. **Pick up when:** a per-country view of the baseline or the scenarios is shown to the public, or a second anomaly appears in the flag list.

### B4 — Muted text on `analytics-bright-signal` / `-broadsheet` is below 4.5:1 (added 2026-10-05; owner decision: backlog, option 2)

**What.** The Step 10 audit retuned the shared muted-text token in the two themes this app ships (`analytics`, `analytics-bright-tidewater`; design-system #105, app #250). The design system's other two bright themes have the same failure on tinted surfaces and were not retuned.

**Why not now.** This app does not load them, so there is nothing to preview or verify here; retuning would be guessing at values.

**Where it is tracked.** In the `design-system` repo (`ENHANCEMENTS.md` Known small defects; `DESIGN.md` note), for the **India Allocation Monitor** and **India IPO Intelligence**, the companion apps that may adopt those themes: retune per theme to ≥ 4.5:1 against the most tinted surface, then axe on every page in both modes. Nothing in this repo changes.
