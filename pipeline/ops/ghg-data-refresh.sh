#!/bin/bash
set -uo pipefail
export LC_ALL=C

REPO_DIR="$HOME/ClaudeWorkspace/climate-emissions-analysis-project"
JUPYTER="$REPO_DIR/.venv/bin/jupyter"  # launchd's bare PATH doesn't include the venv
PY="$REPO_DIR/.venv/bin/python"  # same reason: absolute path for the Area 2 pipeline
DATA_FILE="$REPO_DIR/data/owid-co2-data.csv"
STATE_DIR="$HOME/.ghg-data-refresh"
LOG_DIR="$STATE_DIR/logs"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"
NTFY_TOPIC_FILE="$STATE_DIR/ntfy-topic.txt"
# OWID_URL is read from notebook/constants.py (the single source of truth, also what pipeline/owid.py records as the source in
# provenance) rather than duplicated here, so the URL downloaded and the URL recorded can never drift apart.
MIN_BYTES=5000000  # ~5 MB -- current file is ~14 MB

mkdir -p "$LOG_DIR"

notify() {
  # notify <title> <priority: default|high|urgent> <message>
  local title="$1" priority="$2" message="$3"
  local topic
  topic=$(cat "$NTFY_TOPIC_FILE" 2>/dev/null) || return 0
  [ -z "$topic" ] && return 0
  curl -s \
    -H "Title: $title" \
    -H "Priority: $priority" \
    -H "Tags: bar_chart" \
    -d "$message" \
    "https://ntfy.sh/$topic" > /dev/null 2>&1
}

log() {
  echo "$1" >> "$LOG_FILE"
}


# >>> pipeline_stage (Area 2 ingestion: NOAA GML, Berkeley Earth, PRIMAP-hist, OWID registration, then the harmonized layer)
# Its own failure domain: it runs once the OWID file is final (after week1, or after week1 failed
# and the backup was restored), never blocks the notebook weeks, and its outcome is appended to
# whichever notification goes out. Source scripts live in pipeline/ (see pipeline/README.md);
# deviations from norm and failures come back as last_run.{priority,title,message}.
PIPE_PRIORITY="default"
PIPE_SECTION=""
PIPE_TITLE_SUFFIX=""
PIPE_OK=0  # 1 once the stage produced a summary that is not "urgent" (every source ran; the Area 2 files are new and usable)

max_priority() {  # max_priority <a> <b>   (default < high < urgent)
  case "$1$2" in
    *urgent*) echo urgent ;;
    *high*) echo high ;;
    *) echo default ;;
  esac
}

pipeline_stage() {
  local out_dir="$REPO_DIR/data/climate" rc
  # Remove stale summaries first: if pipeline.run dies before writing, we must not report the last run's.
  rm -f "$out_dir/last_run.priority" "$out_dir/last_run.title" "$out_dir/last_run.message"
  if [ ! -x "$PY" ] || [ ! -d "$REPO_DIR/pipeline" ]; then
    PIPE_PRIORITY="urgent"
    PIPE_OK=0
    PIPE_TITLE_SUFFIX=" + pipeline NOT RUN"
    PIPE_SECTION="

Area 2 pipeline: not run -- missing $PY or $REPO_DIR/pipeline."
    log "pipeline stage skipped: missing python or pipeline dir"
    return 0
  fi
  log "--- Area 2 pipeline ---"
  (cd "$REPO_DIR" && "$PY" -m pipeline.run --source all) >> "$LOG_FILE" 2>&1
  rc=$?
  PIPE_PRIORITY=$(cat "$out_dir/last_run.priority" 2>/dev/null)
  PIPE_OK=0
  # pipeline.run writes the summary files one after another, so an interrupted run can leave only some of them: a stage counts as complete (and
  # may gate an API restart) only with a zero exit AND all three files present and non-empty. Anything else fails closed.
  local complete=0
  if [ "$rc" -eq 0 ] && [ -n "$PIPE_PRIORITY" ] && [ -s "$out_dir/last_run.title" ] && [ -s "$out_dir/last_run.message" ]; then
    complete=1
  fi
  if [ -z "$PIPE_PRIORITY" ]; then
    PIPE_PRIORITY="urgent"
    PIPE_SECTION="

Area 2 pipeline: produced no summary (exit $rc). Tail of log:
$(tail -n 8 "$LOG_FILE")"
  else
    PIPE_SECTION="

$(cat "$out_dir/last_run.title")
$(cat "$out_dir/last_run.message")"
  fi
  if [ "$complete" -eq 0 ] && [ "$PIPE_PRIORITY" != "urgent" ]; then
    # a non-urgent summary from a run that exited non-zero or left its summary incomplete is not trustworthy: report it as a failure
    PIPE_PRIORITY="urgent"
    PIPE_SECTION="${PIPE_SECTION}

Area 2 pipeline: the run exited $rc or left an incomplete summary, so it is treated as failed."
  fi
  case "$PIPE_PRIORITY" in
    urgent) PIPE_TITLE_SUFFIX=" + pipeline FAILED" ;;
    high) PIPE_TITLE_SUFFIX=" + pipeline flagged"; PIPE_OK=1 ;;
    *) PIPE_OK=1 ;;
  esac
  log "pipeline stage: priority=$PIPE_PRIORITY exit=$rc"
}
# <<< pipeline_stage

# >>> restart_api
# Mirrors the Allocation Monitor's `_restart_api_process` (run_scheduled_refresh.py): the API's loaders are
# process-lifetime @lru_cache, so refreshed CSVs are only served after a restart -- freshness is a property
# of process lifetime, not of any in-process invalidation. Only called after the notebooks reran on validated
# data (never after a restored-backup failure, where nothing new is live). Never fatal: a failed restart is
# reported (priority high, in the notification) but does not turn a successful refresh into a failed run.
# Only the API is restarted: the agent keeps per-conversation state in memory that a restart would wipe
# (and the MCP server holds no data cache); vitepreview serves static files off disk.
# GHG_SKIP_API_RESTART=1 skips it (e.g. an on-demand run you don't want to interrupt the API for).
API_LABEL="com.ghgemissions.uvicorn"
restart_api() {
  local out rc
  if [ "${GHG_SKIP_API_RESTART:-0}" = "1" ]; then
    log "API restart skipped (GHG_SKIP_API_RESTART=1)."
    PIPE_SECTION="${PIPE_SECTION}

API: restart skipped (GHG_SKIP_API_RESTART=1) -- it keeps serving the previous data until restarted."
    return 0
  fi
  out=$(launchctl kickstart -k "gui/$(id -u)/$API_LABEL" 2>&1)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    log "WARNING: failed to restart $API_LABEL (exit $rc): $out"
    PIPE_PRIORITY=$(max_priority "$PIPE_PRIORITY" high)
    PIPE_TITLE_SUFFIX="${PIPE_TITLE_SUFFIX} + API restart FAILED"
    PIPE_SECTION="${PIPE_SECTION}

API: FAILED to restart $API_LABEL (exit $rc): $out -- it keeps serving the previous data until restarted."
  else
    log "Restarted $API_LABEL to load the refreshed data."
    PIPE_SECTION="${PIPE_SECTION}

API: restarted $API_LABEL to load the refreshed data."
  fi
}
# After the pipeline stage the API also serves data/climate/* (Phase 1.4), so a refresh whose notebooks did NOT complete (week 1 failed and
# the backup was restored: the notebook CSVs are untouched) must still restart the API when the Area 2 stage produced new files. Not when the
# pipeline stage itself failed (nothing usable is new). Never used after a weeks 2-5 failure: those CSVs may be partially regenerated, and a
# restart would load them.
restart_if_pipeline_ok() {
  if [ "$PIPE_OK" = "1" ]; then
    restart_api
  else
    log "API not restarted: the Area 2 pipeline stage did not complete."
    PIPE_SECTION="${PIPE_SECTION}

API: not restarted -- the Area 2 pipeline stage did not complete, so there is nothing new to load."
  fi
}
# <<< restart_api

log "--- $(date) ---"

cd "$REPO_DIR" || { notify "GHG data refresh: FAILED" "urgent" "Could not cd to $REPO_DIR"; exit 1; }

# >>> owid_url
OWID_URL=$(sed -n "s/^OWID_URL[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'].*/\1/p" "$REPO_DIR/notebook/constants.py" | head -n 1)
case "$OWID_URL" in
  https://*) ;;
  *)
    log "Could not read OWID_URL from notebook/constants.py (got: '$OWID_URL')."
    notify "GHG data refresh: FAILED -- no download attempted" "urgent" \
      "Could not read OWID_URL from $REPO_DIR/notebook/constants.py. Nothing was changed. See $LOG_FILE."
    exit 1
    ;;
esac
# <<< owid_url

# --- Step 1: backup ---
# `cp -p` everywhere the data file is copied (here and on every restore below): pipeline/owid.py takes the file's
# mtime as its retrieval time and uses it to detect a stopped refresh job, so a restored (old) file must keep
# its original mtime -- a plain cp would stamp it "now" and mask both the staleness and the true retrieval time.
TODAY_BACKUP="data/owid-co2-data.csv.bak-$(date +%Y%m%d)"
if [ -f "$TODAY_BACKUP" ]; then
  log "Backup for today already exists ($TODAY_BACKUP) -- not overwriting."
else
  cp -p "$DATA_FILE" "$TODAY_BACKUP"
  log "Backed up $DATA_FILE -> $TODAY_BACKUP"
fi

# --- Step 2: delete + download ---
rm -f "$DATA_FILE"
if ! curl -fsSL -o "$DATA_FILE" "$OWID_URL"; then
  log "Download FAILED (curl error) -- restoring backup."
  cp -p "$TODAY_BACKUP" "$DATA_FILE"
  notify "GHG data refresh: FAILED -- old data restored" "urgent" \
    "curl failed to download $OWID_URL. Backup restored from $TODAY_BACKUP. See $LOG_FILE."
  exit 1
fi

NEW_SIZE=$(stat -f%z "$DATA_FILE" 2>/dev/null || echo 0)
if [ "$NEW_SIZE" -lt "$MIN_BYTES" ]; then
  log "Downloaded file implausibly small ($NEW_SIZE bytes) -- restoring backup."
  cp -p "$TODAY_BACKUP" "$DATA_FILE"
  notify "GHG data refresh: FAILED -- old data restored" "urgent" \
    "Downloaded file was only $NEW_SIZE bytes (expected >$MIN_BYTES). Backup restored. See $LOG_FILE."
  exit 1
fi
log "Downloaded new file OK ($NEW_SIZE bytes)"

# --- Step 3: run week1 (includes validation against the backup) ---
rm -f data/.refresh_status data/.refresh_row_diff
if ! (cd notebook && "$JUPYTER" nbconvert --to notebook --execute --inplace week1_eda.ipynb) >> "$LOG_FILE" 2>&1; then
  log "week1_eda.ipynb FAILED -- restoring backup, skipping weeks 2-5."
  cp -p "$TODAY_BACKUP" "$DATA_FILE"
  pipeline_stage  # the OWID file is final again (restored); the other sources are independent
  restart_if_pipeline_ok  # the notebook CSVs are untouched, but the API serves the new Area 2 files only after a restart
  TAIL=$(tail -n 15 "$LOG_FILE")
  notify "GHG data refresh: FAILED -- old data restored" "urgent" \
    "week1 validation/execution failed. Old data restored. Tail of log:
$TAIL${PIPE_SECTION}"
  exit 1
fi

STATUS=$(cat data/.refresh_status 2>/dev/null || echo "clean")
log "week1 status: $STATUS"
# Row-level diff (added/removed/updated/no-change) -- written by week1_eda.ipynb's
# validation cell (see its own comment there), keyed on (country, year). Purely
# informational: absence (e.g. first-ever run, no prior backup) just means no line gets
# appended to the notification below.
ROW_DIFF=$(cat data/.refresh_row_diff 2>/dev/null || echo "")
log "row diff: ${ROW_DIFF:-<none>}"

# --- Step 4: rerun weeks 2-5 ---
FAILED_WEEK=""
for wk in week2_features week3_regression week4_ets_forecasting week5_scenarios; do
  if ! (cd notebook && "$JUPYTER" nbconvert --to notebook --execute --inplace "$wk.ipynb") >> "$LOG_FILE" 2>&1; then
    FAILED_WEEK="$wk"
    break
  fi
  log "$wk.ipynb OK"
done

if [ -n "$FAILED_WEEK" ]; then
  pipeline_stage  # its own failure domain: the Area 2 files are independent of the notebooks, so they are still refreshed
  PIPE_SECTION="${PIPE_SECTION}

API: not restarted -- $FAILED_WEEK failed partway, so the notebook CSVs may be partially regenerated and must not be loaded; it keeps serving the previous data."
  TAIL=$(tail -n 15 "$LOG_FILE")
  notify "GHG data refresh: FAILED at $FAILED_WEEK" "urgent" \
    "New owid-co2-data.csv passed validation, but $FAILED_WEEK failed to execute. Some derived CSVs may be partially regenerated -- check manually. Tail of log:
$TAIL${PIPE_SECTION}"
  exit 1
fi

# --- Step 4a: the Area 2 pipeline runs AFTER the notebook weeks: its scenario stage reads data/scenario_projections.csv, which week 5 just regenerated ---
pipeline_stage

# --- Step 4b: restart the API so its @lru_cache loaders pick up the refreshed CSVs ---
# Only for a validated refresh (clean / soft_flag): a hard-fail already exited above with the backup restored.
case "$STATUS" in
  clean|soft_flag:*) restart_api ;;
  *)
    log "API not restarted: unrecognized status marker ($STATUS)."
    PIPE_SECTION="${PIPE_SECTION}

API: not restarted (unrecognized status marker: $STATUS)."
    ;;
esac

# --- Step 5: notify outcome (always) ---
ROWS=$(($(wc -l < "$DATA_FILE") - 1))
MAX_YEAR=$(awk -F',' 'NR==1{for(i=1;i<=NF;i++) if($i=="year") c=i; next} {if($c>m) m=$c} END{print m}' "$DATA_FILE")
# Appended (with a leading blank line for readability) only when present -- absent for a
# first-ever run with no backup to diff against.
ROW_DIFF_SUFFIX=""
[ -n "$ROW_DIFF" ] && ROW_DIFF_SUFFIX="

$ROW_DIFF"

case "$STATUS" in
  clean)
    notify "GHG data refresh: OK${PIPE_TITLE_SUFFIX}" "$(max_priority default "$PIPE_PRIORITY")" \
      "All 5 notebooks reran cleanly. Rows: $ROWS. Max year: $MAX_YEAR.${ROW_DIFF_SUFFIX}${PIPE_SECTION}"
    ;;
  soft_flag:*)
    REASON="${STATUS#soft_flag: }"
    notify "GHG data refresh: change flagged${PIPE_TITLE_SUFFIX}" "$(max_priority high "$PIPE_PRIORITY")" \
      "All 5 notebooks reran cleanly, but validation flagged: $REASON. Rows: $ROWS. Max year: $MAX_YEAR.${ROW_DIFF_SUFFIX}${PIPE_SECTION}"
    ;;
  *)
    notify "GHG data refresh: OK (unrecognized status)${PIPE_TITLE_SUFFIX}" "$(max_priority default "$PIPE_PRIORITY")" \
      "All 5 notebooks reran cleanly. Status marker was: $STATUS. Rows: $ROWS. Max year: $MAX_YEAR.${ROW_DIFF_SUFFIX}${PIPE_SECTION}"
    ;;
esac

log "Run complete. Status: $STATUS"
