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
