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
