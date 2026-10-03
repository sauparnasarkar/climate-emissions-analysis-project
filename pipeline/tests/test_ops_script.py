"""The refresh script's new pipeline stage, exercised in bash with a stub python (the live job runs on
the Mac Mini and can't be run from here). The functions are extracted between the script's own markers."""
import os
import re
import subprocess
import textwrap

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "ops", "ghg-data-refresh.sh")


def stage_source():
    text = open(SCRIPT).read()
    m = re.search(r"# >>> pipeline_stage.*?# <<< pipeline_stage", text, re.S)
    assert m, "pipeline_stage markers not found"
    return m.group(0)


def run_stage(tmp_path, stub_body, make_py=True, make_pipeline_dir=True):
    repo = tmp_path / "repo"
    (repo / "data" / "climate").mkdir(parents=True)
    if make_pipeline_dir:
        (repo / "pipeline").mkdir()
    py = tmp_path / "py"
    if make_py:
        py.write_text("#!/bin/bash\n" + textwrap.dedent(stub_body))
        py.chmod(0o755)
    # stale summaries from a previous run that must NOT be reported if this run dies early
    (repo / "data" / "climate" / "last_run.priority").write_text("default\n")
    (repo / "data" / "climate" / "last_run.title").write_text("STALE TITLE\n")
    (repo / "data" / "climate" / "last_run.message").write_text("STALE MESSAGE\n")
    log = tmp_path / "log"
    script = f'''
REPO_DIR="{repo}"; PY="{py}"; LOG_FILE="{log}"
log() {{ echo "$1" >> "$LOG_FILE"; }}
{stage_source()}
pipeline_stage
echo "PRIORITY=$PIPE_PRIORITY"
echo "SUFFIX=$PIPE_TITLE_SUFFIX"
echo "OK=$PIPE_OK"
echo "SECTION<<$PIPE_SECTION>>"
echo "MAX1=$(max_priority default high) MAX2=$(max_priority urgent high) MAX3=$(max_priority default default) MAX4=$(max_priority high urgent)"
'''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout, log.read_text() if log.exists() else ""


STUB_OK = """
# emulate: python -m pipeline.run --source all  -> writes the summary files
d="$PWD/data/climate"
printf 'high\\n' > "$d/last_run.priority"
printf 'Area 2 pipeline: deviations flagged\\n' > "$d/last_run.title"
printf '4 source(s) ok, 0 failed, 1 deviation(s).\\nDEVIATION owid: stale\\n' > "$d/last_run.message"
exit 0
"""


STUB_URGENT = STUB_OK.replace("printf 'high", "printf 'urgent")
STUB_CLEAN = STUB_OK.replace("printf 'high", "printf 'default")


@pytest.mark.parametrize("stub,ok", [(STUB_OK, "1"), (STUB_CLEAN, "1"), (STUB_URGENT, "0"), ("exit 3\n", "0")])
def test_pipe_ok_is_set_only_when_the_stage_produced_a_non_urgent_summary(tmp_path, stub, ok):
    out, _ = run_stage(tmp_path, stub)
    assert f"OK={ok}" in out


def test_pipe_ok_is_zero_when_the_stage_could_not_run(tmp_path):
    out, _ = run_stage(tmp_path, "exit 0\n", make_py=False)
    assert "OK=0" in out


def test_stage_reports_summary_and_priority(tmp_path):
    out, log = run_stage(tmp_path, STUB_OK)
    assert "PRIORITY=high" in out and "SUFFIX= + pipeline flagged" in out
    assert "Area 2 pipeline: deviations flagged" in out and "DEVIATION owid: stale" in out
    assert "STALE" not in out and "pipeline stage: priority=high exit=0" in log


def test_stage_without_summary_is_urgent_and_never_reports_stale_files(tmp_path):
    out, log = run_stage(tmp_path, "exit 3\n")  # crashes before writing anything
    assert "PRIORITY=urgent" in out and "produced no summary (exit 3)" in out
    assert "STALE" not in out  # the old summaries were removed first


def test_stage_missing_python_or_pipeline_dir_is_urgent_and_not_run(tmp_path):
    out, _ = run_stage(tmp_path, "exit 0\n", make_py=False)
    assert "PRIORITY=urgent" in out and "pipeline NOT RUN" in out
    out2, _ = run_stage(tmp_path / "b", STUB_OK, make_pipeline_dir=False) if (tmp_path / "b").mkdir() is None else (None, None)
    assert "PRIORITY=urgent" in out2 and "not run" in out2


def test_max_priority_ordering(tmp_path):
    out, _ = run_stage(tmp_path, STUB_OK)
    assert "MAX1=high MAX2=urgent MAX3=default MAX4=urgent" in out


def test_script_syntax_and_wiring():
    assert subprocess.run(["bash", "-n", SCRIPT]).returncode == 0
    text = open(SCRIPT).read()
    # every notification carries the stage's section
    calls = [m.start() for m in re.finditer(r"^\s*pipeline_stage\b(?!\()", text, re.M)]  # call sites; the definition is "pipeline_stage() {"
    assert len(calls) == 3  # week-1 failure branch (after the restore), weeks 2-5 failure branch, and the success path
    assert text.count("${PIPE_SECTION}") >= 5
    assert 'max_priority default "$PIPE_PRIORITY"' in text and 'max_priority high "$PIPE_PRIORITY"' in text


def test_the_stage_runs_after_the_notebook_weeks_so_the_scenario_stage_reads_this_runs_scenario_file():
    text = open(SCRIPT).read()
    weeks_loop, week1_ok, failed_branch, step4b = text.index("for wk in week2_features"), text.index('log "week1 status: $STATUS"'), text.index('if [ -n "$FAILED_WEEK" ]'), text.index("# --- Step 4b")
    calls = [m.start() for m in re.finditer(r"^\s*pipeline_stage\b(?!\()", text, re.M)]
    # no call between a successful week 1 and the weeks loop (it used to be there, one month behind on the scenario file)
    assert not [c for c in calls if week1_ok < c < weeks_loop]
    # a call in the weeks-failure branch and one after the loop that precedes the restart
    assert any(failed_branch < c < failed_branch + 400 for c in calls) and any(failed_branch + 400 < c < step4b + 5 for c in calls)
    assert max(calls) < text.index("clean|soft_flag:*) restart_api")
    # week 1's failure branch still runs it (the other sources are independent of OWID)
    assert any(text.index("week1_eda.ipynb FAILED") < c < week1_ok for c in calls)


# ---------------------------------------------------------------- API restart (mirrors the Allocation Monitor's)


def restart_source():
    text = open(SCRIPT).read()
    m = re.search(r"# >>> restart_api.*?# <<< restart_api", text, re.S)
    assert m, "restart_api markers not found"
    return m.group(0)


def run_restart(tmp_path, launchctl_body, env_prefix="", initial_priority="default"):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    args_file = tmp_path / "launchctl.args"
    (bindir / "launchctl").write_text("#!/bin/bash\n" + f'echo "$@" > "{args_file}"\n' + textwrap.dedent(launchctl_body))
    (bindir / "id").write_text("#!/bin/bash\necho 501\n")
    for f in bindir.iterdir():
        f.chmod(0o755)
    log = tmp_path / "log"
    script = f'''
PATH="{bindir}:$PATH"
LOG_FILE="{log}"
log() {{ echo "$1" >> "$LOG_FILE"; }}
{stage_source()}
PIPE_PRIORITY="{initial_priority}"
{restart_source()}
{env_prefix}
restart_api
echo "RC=$?"
echo "PRIORITY=$PIPE_PRIORITY"
echo "SUFFIX=$PIPE_TITLE_SUFFIX"
echo "SECTION<<$PIPE_SECTION>>"
'''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout, (args_file.read_text().strip() if args_file.exists() else None), (log.read_text() if log.exists() else "")


def test_restart_kickstarts_the_api_service_and_reports_it(tmp_path):
    out, args, log = run_restart(tmp_path, "exit 0\n")
    assert args == "kickstart -k gui/501/com.ghgemissions.uvicorn"  # the same call the companion apps make
    assert "PRIORITY=default" in out and "SUFFIX=" in out and "API: restarted com.ghgemissions.uvicorn" in out
    assert "Restarted com.ghgemissions.uvicorn" in log


def test_failed_restart_is_never_fatal_but_is_loud(tmp_path):
    out, args, log = run_restart(tmp_path, 'echo "Could not find service" >&2\nexit 113\n')
    assert "RC=0" in out  # the function itself never fails the run
    assert "PRIORITY=high" in out and "+ API restart FAILED" in out
    assert "FAILED to restart com.ghgemissions.uvicorn (exit 113): Could not find service" in out
    assert "WARNING: failed to restart" in log


def test_failed_restart_does_not_downgrade_an_urgent_pipeline_priority(tmp_path):
    out, _, _ = run_restart(tmp_path, "exit 1\n", initial_priority="urgent")
    assert "PRIORITY=urgent" in out


def test_skip_env_var_does_not_touch_launchctl(tmp_path):
    out, args, log = run_restart(tmp_path, "exit 0\n", env_prefix="export GHG_SKIP_API_RESTART=1")
    assert args is None  # launchctl never invoked
    assert "restart skipped" in out and "PRIORITY=default" in out and "skipped (GHG_SKIP_API_RESTART=1)" in log


def test_restart_only_runs_on_a_validated_refresh_or_after_a_week1_failure_with_new_area2_files():
    text = open(SCRIPT).read()
    call = text.index("clean|soft_flag:*) restart_api")
    assert text.count(") restart_api") == 1  # exactly one direct call site (the validated notebook refresh)
    # after the weeks 2-5 failure exit, before the notification
    assert text.index('if [ -n "$FAILED_WEEK" ]') < call < text.index("# --- Step 5")
    assert "unrecognized status marker" in text  # an unknown marker is not restarted, and says so
    # the weeks 2-5 failure branch never restarts (partially regenerated CSVs must not be loaded) and says so
    failed = text[text.index('if [ -n "$FAILED_WEEK" ]'):text.index("# --- Step 4a")]
    assert "restart_api" not in failed and "restart_if_pipeline_ok" not in failed and "not restarted" in failed and "partially regenerated" in failed
    # week 1's failure branch restarts only through the pipeline-gated helper
    w1 = text[text.index("week1_eda.ipynb FAILED"):text.index("exit 1", text.index("week1_eda.ipynb FAILED"))]
    assert "restart_if_pipeline_ok" in w1 and "restart_api\n" not in w1.replace("restart_if_pipeline_ok", "")


def run_gated(tmp_path, pipe_ok):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    args_file = tmp_path / "launchctl.args"
    (bindir / "launchctl").write_text("#!/bin/bash\n" + f'echo "$@" > "{args_file}"\nexit 0\n')
    (bindir / "id").write_text("#!/bin/bash\necho 501\n")
    for f in bindir.iterdir():
        f.chmod(0o755)
    log = tmp_path / "log"
    script = f'''
PATH="{bindir}:$PATH"
LOG_FILE="{log}"
log() {{ echo "$1" >> "$LOG_FILE"; }}
{stage_source()}
PIPE_OK={pipe_ok}
{restart_source()}
restart_if_pipeline_ok
echo "SECTION<<$PIPE_SECTION>>"
'''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout, (args_file.read_text().strip() if args_file.exists() else None), (log.read_text() if log.exists() else "")


def test_the_gated_restart_restarts_the_api_when_the_pipeline_stage_produced_files(tmp_path):
    out, args, log = run_gated(tmp_path, 1)
    assert args == "kickstart -k gui/501/com.ghgemissions.uvicorn" and "API: restarted com.ghgemissions.uvicorn" in out


def test_the_gated_restart_does_nothing_and_says_so_when_the_pipeline_stage_did_not_complete(tmp_path):
    out, args, log = run_gated(tmp_path, 0)
    assert args is None  # launchctl never invoked
    assert "API: not restarted -- the Area 2 pipeline stage did not complete" in out and "API not restarted: the Area 2 pipeline stage did not complete." in log


# ---------------------------------------------------------------- OWID_URL single source of truth


def owid_url_snippet():
    text = open(SCRIPT).read()
    m = re.search(r"# >>> owid_url.*?# <<< owid_url", text, re.S)
    assert m, "owid_url markers not found"
    return m.group(0)


def read_owid_url(tmp_path, constants_text):
    repo = tmp_path / "repo"
    (repo / "notebook").mkdir(parents=True)
    if constants_text is not None:
        (repo / "notebook" / "constants.py").write_text(constants_text)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "curl").write_text("#!/bin/bash\nexit 0\n")  # notify() must never reach the real ntfy
    (bindir / "curl").chmod(0o755)
    script = f'''
PATH="{bindir}:$PATH"
REPO_DIR="{repo}"; LOG_FILE="{tmp_path}/log"
log() {{ echo "$1" >> "$LOG_FILE"; }}
notify() {{ echo "NOTIFY: $1 | $2"; }}
{owid_url_snippet()}
echo "URL=$OWID_URL"
'''
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def test_owid_url_is_read_from_the_shared_constants_file(tmp_path):
    out = read_owid_url(tmp_path, '# c\nOWID_URL = "https://example.test/owid.csv"  # trailing comment\nOTHER = 1\n')
    assert out.returncode == 0 and "URL=https://example.test/owid.csv" in out.stdout
    out2 = read_owid_url(tmp_path / "b", "OWID_URL='https://single.quoted/x.csv'\n") if (tmp_path / "b").mkdir() is None else None
    assert "URL=https://single.quoted/x.csv" in out2.stdout


def test_owid_url_missing_or_unreadable_fails_fast_before_any_download(tmp_path):
    out = read_owid_url(tmp_path, "X = 1\n")
    assert out.returncode == 1 and "NOTIFY: GHG data refresh: FAILED -- no download attempted | urgent" in out.stdout and "URL=" not in out.stdout


def test_script_does_not_duplicate_the_url_and_matches_the_real_constants():
    from pipeline import owid

    text = open(SCRIPT).read()
    assert "raw.githubusercontent.com" not in text  # no hardcoded copy left to drift
    assert text.index("# >>> owid_url") < text.index('curl -fsSL -o "$DATA_FILE" "$OWID_URL"')  # defined before the download uses it
    # the sed in the script resolves to exactly what pipeline/owid.py records as the source
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    script = f'REPO_DIR="{repo_root}"; LOG_FILE=/dev/null; log() {{ :; }}; notify() {{ :; }}\n{owid_url_snippet()}\necho "$OWID_URL"'
    got = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout.strip()
    assert got == owid.owid_url()


# ---------------------------------------------------------------- mtime preservation on backup/restore


def test_every_data_file_copy_preserves_mtime_so_a_restored_old_file_stays_stale(tmp_path):
    import time

    text = open(SCRIPT).read()
    copies = re.findall(r'^\s*(cp [^\n]*"\$(?:DATA_FILE|TODAY_BACKUP)"[^\n]*)$', text, re.M)
    assert len(copies) == 4 and all(c.startswith("cp -p ") for c in copies)  # 1 backup + 3 restores, none plain

    # behavioural: backup then restore with the script's own commands; the old mtime must survive both
    data, backup = tmp_path / "owid.csv", tmp_path / "owid.csv.bak"
    data.write_text("x")
    old = time.time() - 120 * 86400
    os.utime(data, (old, old))
    backup_cmd = next(c for c in copies if c.endswith('"$TODAY_BACKUP"') and c.split()[2] == '"$DATA_FILE"')
    restore_cmd = next(c for c in copies if c.split()[2] == '"$TODAY_BACKUP"')
    script = f'''DATA_FILE="{data}"; TODAY_BACKUP="{backup}"
{backup_cmd}
rm -f "$DATA_FILE"
{restore_cmd}
'''
    assert subprocess.run(["bash", "-c", script]).returncode == 0
    assert abs(os.stat(backup).st_mtime - old) < 2 and abs(os.stat(data).st_mtime - old) < 2
