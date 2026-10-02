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
OWID_URL="https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"  # must match notebook/constants.py:OWID_URL
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


# >>> pipeline_stage (Area 2 ingestion: NOAA GML, Berkeley Earth, PRIMAP-hist, OWID registration)
# Its own failure domain: it runs once the OWID file is final (after week1, or after week1 failed
# and the backup was restored), never blocks the notebook weeks, and its outcome is appended to
# whichever notification goes out. Source scripts live in pipeline/ (see pipeline/README.md);
# deviations from norm and failures come back as last_run.{priority,title,message}.
PIPE_PRIORITY="default"
PIPE_SECTION=""
PIPE_TITLE_SUFFIX=""

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
  case "$PIPE_PRIORITY" in
    urgent) PIPE_TITLE_SUFFIX=" + pipeline FAILED" ;;
    high) PIPE_TITLE_SUFFIX=" + pipeline flagged" ;;
  esac
  log "pipeline stage: priority=$PIPE_PRIORITY exit=$rc"
}
# <<< pipeline_stage

log "--- $(date) ---"

cd "$REPO_DIR" || { notify "GHG data refresh: FAILED" "urgent" "Could not cd to $REPO_DIR"; exit 1; }

# --- Step 1: backup ---
TODAY_BACKUP="data/owid-co2-data.csv.bak-$(date +%Y%m%d)"
if [ -f "$TODAY_BACKUP" ]; then
  log "Backup for today already exists ($TODAY_BACKUP) -- not overwriting."
else
  cp "$DATA_FILE" "$TODAY_BACKUP"
  log "Backed up $DATA_FILE -> $TODAY_BACKUP"
fi

# --- Step 2: delete + download ---
rm -f "$DATA_FILE"
if ! curl -fsSL -o "$DATA_FILE" "$OWID_URL"; then
  log "Download FAILED (curl error) -- restoring backup."
  cp "$TODAY_BACKUP" "$DATA_FILE"
  notify "GHG data refresh: FAILED -- old data restored" "urgent" \
    "curl failed to download $OWID_URL. Backup restored from $TODAY_BACKUP. See $LOG_FILE."
  exit 1
fi

NEW_SIZE=$(stat -f%z "$DATA_FILE" 2>/dev/null || echo 0)
if [ "$NEW_SIZE" -lt "$MIN_BYTES" ]; then
  log "Downloaded file implausibly small ($NEW_SIZE bytes) -- restoring backup."
  cp "$TODAY_BACKUP" "$DATA_FILE"
  notify "GHG data refresh: FAILED -- old data restored" "urgent" \
    "Downloaded file was only $NEW_SIZE bytes (expected >$MIN_BYTES). Backup restored. See $LOG_FILE."
  exit 1
fi
log "Downloaded new file OK ($NEW_SIZE bytes)"

# --- Step 3: run week1 (includes validation against the backup) ---
rm -f data/.refresh_status data/.refresh_row_diff
if ! (cd notebook && "$JUPYTER" nbconvert --to notebook --execute --inplace week1_eda.ipynb) >> "$LOG_FILE" 2>&1; then
  log "week1_eda.ipynb FAILED -- restoring backup, skipping weeks 2-5."
  cp "$TODAY_BACKUP" "$DATA_FILE"
  pipeline_stage  # the OWID file is final again (restored); the other sources are independent
  TAIL=$(tail -n 15 "$LOG_FILE")
  notify "GHG data refresh: FAILED -- old data restored" "urgent" \
    "week1 validation/execution failed. Old data restored. Tail of log:
$TAIL${PIPE_SECTION}"
  exit 1
fi

STATUS=$(cat data/.refresh_status 2>/dev/null || echo "clean")
log "week1 status: $STATUS"
pipeline_stage
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
  TAIL=$(tail -n 15 "$LOG_FILE")
  notify "GHG data refresh: FAILED at $FAILED_WEEK" "urgent" \
    "New owid-co2-data.csv passed validation, but $FAILED_WEEK failed to execute. Some derived CSVs may be partially regenerated -- check manually. Tail of log:
$TAIL${PIPE_SECTION}"
  exit 1
fi

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
