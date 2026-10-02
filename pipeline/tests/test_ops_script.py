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
    # the stage runs after week1 succeeds and after a week1 failure restores the backup, and every notification carries it
    calls = re.findall(r"^\s*pipeline_stage\b(?!\()", text, re.M)  # call sites; the definition is "pipeline_stage() {"
    assert len(calls) == 2  # week-1 failure branch (after the restore) + the success path
    assert text.count("${PIPE_SECTION}") >= 5
    assert 'max_priority default "$PIPE_PRIORITY"' in text and 'max_priority high "$PIPE_PRIORITY"' in text


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


def test_restart_only_runs_on_a_validated_successful_refresh():
    text = open(SCRIPT).read()
    call = text.index("clean|soft_flag:*) restart_api")
    assert text.count("restart_api") >= 3 and text.count(") restart_api") == 1  # exactly one call site
    # after the weeks 2-5 failure exit, before the notification; never in a restored-backup failure branch
    assert text.index('if [ -n "$FAILED_WEEK" ]') < call < text.index("# --- Step 5")
    assert "unrecognized status marker" in text  # an unknown marker is not restarted, and says so
    assert text.count("exit 1") >= 4 and all("restart_api" not in blk for blk in re.findall(r'FAILED[^\n]*\n(?:.*\n){0,8}?\s*exit 1', text))


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
