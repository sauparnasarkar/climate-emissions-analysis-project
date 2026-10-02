"""ISO3-based country crosswalk between EDGAR and OWID (Release 21, Phase 1.1b; `SPEC.md` §5.26).

Built once per ingestion run from the two datasets' own entity lists, never hand-maintained, so
it can't drift from the data. It records only what the data shows:

- `iso3_exact`: the code exists in both datasets (names may still differ -- `name_differs`).
- `edgar_only`: in EDGAR, not OWID (small territories, the pre-2006 Serbia-and-Montenegro entity).
- `owid_only`: a sovereign OWID country with no EDGAR row.
- `bunker`: EDGAR's international aviation/shipping entities (`AIR`, `SEA`), matched by name to
  OWID's non-ISO "International aviation/shipping" rows. Bunkers are never part of a country
  total or of the country cumulative-share denominator (`SPEC.md` §5.26 decision 9).

Where EDGAR folds a small territory into a neighbour, the EDGAR files don't say so, so the
crosswalk does not claim to know: it only flags many-to-one cases that the entity *names* reveal
(an EDGAR entity whose name contains the names of OWID-only countries).
"""

from __future__ import annotations

import pandas as pd

BUNKER_CODES = {"AIR": "International aviation", "SEA": "International shipping"}


def build_crosswalk(edgar_names: dict[str, str | None], owid: pd.DataFrame, expanded: list[str] | None = None, source_label: str = "edgar") -> pd.DataFrame:
    """`edgar_names`: ISO3 -> source entity name (None when the source gives codes only, as PRIMAP-hist does);
    `source_label` names the column (`<label>_name`). `owid`: needs columns `country`, `iso_code`.
    `expanded`: OWID country names of the expanded set, used to flag coverage of the countries
    the platform actually analyses."""
    coded = owid.dropna(subset=["iso_code"]).drop_duplicates("iso_code")
    # OWID tags some aggregates/special entities with non-ISO identifiers (e.g. OWID_WRL); those are
    # not countries and must not enter the crosswalk. Reported via `df.attrs["excluded_owid_codes"]`.
    is_iso3 = coded["iso_code"].str.fullmatch(r"[A-Z]{3}")
    excluded = sorted(coded.loc[~is_iso3, "iso_code"])
    owid_iso = coded[is_iso3].set_index("iso_code")["country"].to_dict()
    owid_names = set(owid["country"].unique())
    rows = []
    for code, ename in edgar_names.items():
        if code in BUNKER_CODES:
            oname = BUNKER_CODES[code]
            rows.append(
                {"iso3": code, f"{source_label}_name": ename, "owid_name": oname if oname in owid_names else None, "entity_type": "bunker", "match": "bunker",
                 "name_differs": False, "note": "International bunker: excluded from country totals and cumulative-share denominators."}
            )
        elif code in owid_iso:
            rows.append(
                {"iso3": code, f"{source_label}_name": ename, "owid_name": owid_iso[code], "entity_type": "country", "match": "iso3_exact",
                 "name_differs": bool(ename) and ename.strip().lower() != owid_iso[code].strip().lower(), "note": ""}
            )
        else:
            rows.append({"iso3": code, f"{source_label}_name": ename, "owid_name": None, "entity_type": "country", "match": f"{source_label}_only", "name_differs": False, "note": ""})
    owid_only = {c: n for c, n in owid_iso.items() if c not in edgar_names}
    for code, oname in owid_only.items():
        rows.append({"iso3": code, f"{source_label}_name": None, "owid_name": oname, "entity_type": "country", "match": "owid_only", "name_differs": False, "note": ""})

    df = pd.DataFrame(rows)
    # Many-to-one cases revealed by names alone (e.g. EDGAR "Serbia and Montenegro" vs OWID Serbia + Montenegro).
    for i, r in df[df["match"] == f"{source_label}_only"].iterrows():
        name = r[f"{source_label}_name"]
        if not name:
            continue
        parts = [n for n in owid_only.values() if n.lower() in name.lower()]
        if len(parts) >= 2:
            df.at[i, "note"] = f"{source_label.upper()} reports one entity covering {', '.join(sorted(parts))}, which OWID reports separately; not directly comparable."
    df = df.assign(expanded=df["owid_name"].isin(expanded or []))
    df = df.sort_values(["match", "iso3"]).reset_index(drop=True)
    df.attrs["excluded_owid_codes"] = excluded
    return df


def expanded_gaps(crosswalk: pd.DataFrame, expanded: list[str]) -> list[str]:
    """Expanded-set countries that don't have an exact ISO3 match in EDGAR."""
    ok = set(crosswalk.loc[crosswalk["match"] == "iso3_exact", "owid_name"])
    return sorted(c for c in expanded if c not in ok)
