# `pipeline/ops/` — the refresh job, versioned (Release 21, Phase 1.1c)

The data-refresh job runs on the **Mac Mini** (`sauparnasarkar@Sauparnas-Mac-mini.local`), outside this
repo: `~/bin/ghg-data-refresh.sh`, scheduled by `~/Library/LaunchAgents/com.ghgemissions.datarefresh.plist`
(see the `ghg-data-refresh` skill). These are **versioned copies of the proposed new versions** — nothing here
is deployed by merging the PR. They differ from the original (pre-Release 21) job in exactly four ways (the first three were installed on 2026-10-02; the fourth is the 2026-10-03 fix):

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

3. **A post-refresh API restart (`restart_api`)**, mirroring what the India Allocation Monitor does in
   `run_scheduled_refresh.py` (`_restart_api_process`). The API's loaders are process-lifetime `@lru_cache`, and
   nothing in the live job restarts it, so refreshed CSVs are not served until the process happens to restart
   (found in 1.1c; `ENHANCEMENTS.md` Release 21, open item 8). After a **validated** refresh (status `clean` or
   `soft_flag`, notebooks all reran) the script runs `launchctl kickstart -k gui/$(id -u)/com.ghgemissions.uvicorn`;
   `KeepAlive` brings it straight back. Semantics copied from the companion apps: only after a genuinely successful
   refresh (never after a restored-backup failure, where nothing new is live), and **never fatal** — a failed
   restart is reported in the notification (`+ API restart FAILED`, priority at least `high`) but does not turn a
   successful refresh into a failed run. Only the API is restarted: the agent keeps per-conversation state in memory
   that a restart would wipe, the MCP server holds no data cache, and `vitepreview` serves static files off disk.
   Set `GHG_SKIP_API_RESTART=1` to skip it (e.g. an on-demand run you don't want to interrupt the API for).
   *Updated 2026-10-03 (Phase 1.4 made the API serve `data/climate/*`)*: the restart also fires after a **week-1 failure
   (backup restored)** when the Area 2 stage produced a summary that is not `urgent` (`PIPE_OK=1`), because the notebook CSVs
   are untouched there but the new Area 2 files are only served after a restart (`restart_if_pipeline_ok`). It never
   fires after a **weeks 2-5 failure**: those CSVs may be partially regenerated and a restart would load them (the
   notification says so).

4. **The Area 2 stage runs after the notebook weeks, not after week 1.** Its `scenario_temperature` stage reads
   `data/scenario_projections.csv`, which week 5 regenerates; run before the weeks it translated the *previous* month's
   scenarios (one month behind, and unavailable via the stale-scenario guard whenever OWID gained a year). It still runs
   in both failure branches (its own failure domain), so Area 2 files are refreshed even when a notebook fails.

The OWID step **does not download**: the script's existing backup → download → week-1 validation → restore
flow stays the single authority for that file; `pipeline/owid.py` only verifies and registers what is on disk
(provenance, checksum, completeness of the latest year) and publishes `data/climate/owid_world_co2_annual.csv`.

## Deploying (not done yet — needs the owner's go-ahead; it changes a live job)

On the Mac Mini, in this order, stopping if any check fails:

0. **Upgrade numpy in the Mac Mini's venv** (it has the same numpy 2.2.6 / Python 3.14 stack that corrupts large dense pandas reshapes; `requirements.txt` now pins 2.3.5): `cd ~/ClaudeWorkspace/climate-emissions-analysis-project && .venv/bin/pip install numpy==2.3.5 && .venv/bin/pip check`. Only numpy changes (verified: with every other package held identical, the notebooks' outputs and 24 API responses did not change apart from the unseeded Monte Carlo bands in `ets_forecasts.csv`). Do it before the first full run: that run restarts uvicorn, which then loads the new numpy; the agent and MCP server keep running on the old one in memory until their next restart, which is harmless.
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
5. **Trigger one full run** (`~/bin/ghg-data-refresh.sh`; it restarts the API at the end, so expect a few seconds of
   failed requests — prefix `GHG_SKIP_API_RESTART=1` for a run that must not) and read `~/.ghg-data-refresh/logs/<date>.log` and the ntfy
   push: both the notebook outcome and the `Area 2 pipeline:` section should be present; confirm `launchctl list | grep ghgemissions.uvicorn` shows a **new PID** (and that the log says
   `Restarted com.ghgemissions.uvicorn`).

Rollback: restore the two `.bak-…` files and repeat the `bootout`/`bootstrap`.

## Tests

`pipeline/tests/test_ops_script.py` extracts `pipeline_stage` and `max_priority` from the script (between its
`# >>> pipeline_stage` / `# <<< pipeline_stage` markers) and runs them in bash with a stub Python: summary and
priority handling, a crash that must not re-report stale files, a missing python/pipeline dir, priority ordering,
and syntax/wiring of the call sites; and `restart_api` with stub `launchctl`/`id` binaries (the exact kickstart call, a
failed restart being loud but never fatal and never downgrading `urgent`, the opt-out, and that the call sits after the
weeks 2–5 failure exit and before the notification, gated on a validated status). The live job itself can only be verified by step 5 above.
