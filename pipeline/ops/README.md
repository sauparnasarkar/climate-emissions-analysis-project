# `pipeline/ops/` — the refresh job, versioned (Release 21, Phase 1.1c)

The data-refresh job runs on the **Mac Mini** (`sauparnasarkar@Sauparnas-Mac-mini.local`), outside this
repo: `~/bin/ghg-data-refresh.sh`, scheduled by `~/Library/LaunchAgents/com.ghgemissions.datarefresh.plist`
(see the `ghg-data-refresh` skill). These are **versioned copies of the proposed new versions** — nothing here
is deployed by merging the PR. They differ from what is live in exactly two ways:

1. **Schedule: weekly (Sunday 03:30) → monthly (day 10, 03:30).** `Weekday` is replaced by `Day = 10`. Annual-release
   datasets (PRIMAP-hist, OWID) don't need a weekly cycle (`SPEC.md` §5.26 decision 10); day 10 lets NOAA's
   monthly file (published in the first days of the month) and Berkeley Earth's monthly update land first. Change the
   `Day` value if you prefer another day (launchd can't express "first Sunday").
2. **A new stage, `pipeline_stage`,** that runs `python -m pipeline.run --source all` (NOAA GML, Berkeley Earth,
   PRIMAP-hist, OWID registration; **EDGAR is shelved and not part of `all`**) once the OWID file is final —
   after week 1 validates it, or after a week-1 failure restores the backup. It is its own failure domain: it never
   blocks the notebook weeks, and its outcome is **appended to whichever notification goes out**
   (`pipeline.run` writes `data/climate/last_run.{priority,title,message}`; the script just reads them).
   - `urgent` if a source failed outright, or the stage could not run / produced no summary;
   - `high` if any source reported deviations from norm (stale source, completeness exclusions beyond one year,
     licence change, row-count drop, reconciliation gaps, …);
   - otherwise the notebook outcome's own priority is unchanged. The ntfy title gains a suffix
     (` + pipeline flagged` / ` + pipeline FAILED` / ` + pipeline NOT RUN`) when it isn't clean.
   - Stale summaries are deleted before each run, so a crash can never re-report the previous run's result.

The OWID step **does not download**: the script's existing backup → download → week-1 validation → restore
flow stays the single authority for that file; `pipeline/owid.py` only verifies and registers what is on disk
(provenance, checksum, completeness of the latest year) and publishes `data/climate/owid_world_co2_annual.csv`.

## Deploying (not done yet — needs the owner's go-ahead; it changes a live job)

On the Mac Mini, in this order, stopping if any check fails:

1. **Get the code**: the Mac Mini checkout has no `pipeline/` yet. `git pull --ff-only` in
   `~/ClaudeWorkspace/climate-emissions-analysis-project` (after confirming the tree is clean and on `main`).
   This updates source files on disk only: the running API/`vitepreview` keep serving what is loaded/built until
   they are restarted/rebuilt. **No `pip install` is needed** for the monthly job (pandas/numpy are already in the
   venv; `openpyxl` is only used by the dormant EDGAR source).
2. **Dry-run the stage alone** (does not touch the OWID file or notebooks):
   `cd ~/ClaudeWorkspace/climate-emissions-analysis-project && .venv/bin/python -m pipeline.run --source all`
   then read `data/climate/last_run.message`. Expect `owid` to be fine only if the file is fresh.
3. **Back up, then install the script**:
   `cp ~/bin/ghg-data-refresh.sh ~/bin/ghg-data-refresh.sh.bak-$(date +%Y%m%d)` and copy
   `pipeline/ops/ghg-data-refresh.sh` over it (`chmod +x`).
4. **Back up, then install the plist** (`~/Library/LaunchAgents/com.ghgemissions.datarefresh.plist.bak-…`), then
   reload it: `launchctl bootout gui/$(id -u)/com.ghgemissions.datarefresh` followed by
   `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ghgemissions.datarefresh.plist`
   (`kickstart -k` would keep the old definition).
5. **Trigger one full run** (`~/bin/ghg-data-refresh.sh`) and read `~/.ghg-data-refresh/logs/<date>.log` and the ntfy
   push: both the notebook outcome and the `Area 2 pipeline:` section should be present.

Rollback: restore the two `.bak-…` files and repeat the `bootout`/`bootstrap`.

## Tests

`pipeline/tests/test_ops_script.py` extracts `pipeline_stage` and `max_priority` from the script (between its
`# >>> pipeline_stage` / `# <<< pipeline_stage` markers) and runs them in bash with a stub Python: summary and
priority handling, a crash that must not re-report stale files, a missing python/pipeline dir, priority ordering,
and syntax/wiring of the call sites. The live job itself can only be verified by step 5 above.
