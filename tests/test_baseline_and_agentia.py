import json
import subprocess

import pytest

from releaseguard import cli_adapter
from releaseguard.analyzer import baseline_triage
from releaseguard.cli_adapter import AgentiaAdapter
from releaseguard.evaluate import render_misses, run_method


def cited(log):
    return [c["line"] for c in baseline_triage(log)["cited_lines"]]


# ---- shapes taken from real LogChunks dev failures (caffe/cmake, ripgrep/rust, shell cd error)
CMAKE = "\n".join(["step"] * 10 + [
    "CMake Error at /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:138 (message):",
    "  Could NOT find Halide (missing: HALIDE_ROOT_DIR)",
    "-- Configuring incomplete, errors occurred!",
    "make: *** [all] Error 1",
    'The command "make" exited with 2.',
])
RUST = "\n".join(["compile"] * 5 + [
    "error: failed to run custom build command for `jemalloc-sys v0.3.0`",
    "configure: error: C compiler cannot create executables",
    "thread 'main' panicked at 'command did not execute successfully'",
    "error: build failed",
    'The command "ci/script.sh" exited with 101.',
    "Done. Your build exited with 1.",
])


def test_cmake_error_is_found_and_wrapper_lines_are_not_preferred():
    lines = cited(CMAKE)
    assert 11 in lines and 12 in lines
    assert 14 not in lines and 15 not in lines  # make: *** and "The command ... exited with"


def test_rust_root_cause_beats_build_failed_summary():
    lines = cited(RUST)
    assert 7 in lines and 8 in lines
    assert 9 not in lines and 10 not in lines and 11 not in lines


def test_shell_cd_error_is_found():
    assert cited("ok\n./scripts/travis/install-deps.sh: line 117: cd: ./scripts/travis: No such file or directory\nend") == [2]


def test_travis_timeout_message_is_found():
    log = "build\nNo output has been received in the last 10m0s, this potentially indicates a stalled build\nThe build has been terminated"
    result = baseline_triage(log)
    assert result["category"] == "timeout" and [c["line"] for c in result["cited_lines"]] == [2, 3]


def test_wrapper_lines_are_still_cited_when_nothing_else_exists():
    assert cited('all fine\nThe command "make test" exited with 1.\nDone. Your build exited with 1.') == [2, 3]


def test_generic_error_lines_still_work_and_zero_failures_are_ignored():
    assert cited("a\nERROR: disk full\nb") == [2]
    assert cited("0 failed, Errors: 0") == []


# ---- misses report is spread over repositories
def test_misses_are_capped_per_repo():
    items = [
        {"id": f"a@a:{n}", "repo": "a@a", "log": "x\ny\nz", "gold_lines": [2]} for n in range(5)
    ] + [{"id": "b@b:1", "repo": "b@b", "log": "x\ny\nz", "gold_lines": [2]}]
    result = run_method(items, "baseline", say=lambda _m: None)
    text = render_misses(items, result, 10, per_repo=2)
    assert text.count("## a@a") == 2 and text.count("## b@b") == 1


# ---- real-mode command construction (no real agentia needed)
class FakeProc:
    def __init__(self, out="{}", code=0):
        self.stdout, self.stderr, self.returncode = out, "", code


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake_run(cmd, **_kw):
        recorded.append(cmd)
        return FakeProc(json.dumps({"id": "US-1", "name": "Story"}))

    monkeypatch.setattr(cli_adapter.shutil, "which", lambda c: "agentia")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.delenv("AGENTIA_APEX_TEST_CLASSES", raising=False)
    return recorded


def test_real_get_uses_json_flag_and_id(calls):
    AgentiaAdapter("real").get_work_item("US-1")
    assert calls[0] == ["agentia", "cicd", "work", "get", "--json", "US-1"]


def test_real_submit_does_not_bypass_local_quality_gates(calls):
    AgentiaAdapter("real").submit("US-1")
    assert "--skip-local-tests" not in calls[0] and calls[0][-1] == "US-1"


def test_real_submit_without_structured_job_id_is_unverified(calls):
    result = AgentiaAdapter("real").submit("US-1")
    assert result["ok"] is True and result["job_id"] is None
    assert "UNVERIFIED" in result["message"]


def test_real_tests_never_call_work_test_local_and_pass_no_work_id(calls):
    AgentiaAdapter("real").run_tests("US-1")
    assert calls[0] == ["agentia", "cicd", "work", "test", "apex"]
    assert "--local" not in calls[0] and "US-1" not in calls[0]


def test_real_tests_forward_apex_classes_from_the_gate_environment(calls, monkeypatch):
    monkeypatch.setenv("AGENTIA_APEX_TEST_CLASSES", "AccountTest,LeadTest")
    AgentiaAdapter("real").run_tests("US-1")
    assert calls[0][-1] == "--apex-test-classes=AccountTest,LeadTest"


# ---- second tuning round, from other dev repositories
def test_travis_sudo_banner_and_job_stages_noise_is_ignored():
    log = "\n".join([
        "Configure options: --prefix=/usr --with-logging=syslog",
        "Authentication timestamp timeout: 15.0 minutes",
        "Password prompt timeout: 0.0 minutes",
        "the USA under License Exception TSU of the U.S. Export",
        "/Users/travis/.travis/job_stages: line 476: yarn: command not found",
        "An error occured while installing Cake.",
        "/Users/travis/.travis/job_stages: line 166: shell_session_update: command not found",
    ])
    assert cited(log) == [6]


def test_mocha_error_is_found_even_though_npm_summary_exists():
    log = "start\n  1) \n     fourslash tests\n      Error: At line 1, col 3: Should find at least 1 codefix(es)\n      at TestState.raiseError\nnpm ERR! Test failed.  See above for more details."
    lines = cited(log)
    assert 4 in lines and 6 not in lines


def test_phpunit_failure_heading_is_found():
    log = "run\n1) Composer\\Test\\RepoTest::testCanonicalizeUrl with data set #0\nArgument 4 passed to X must be an instance of Y\n"
    assert 2 in cited(log)


def test_program_not_installed_and_tool_error_prefix():
    assert 2 in cited("ok\nThe program 'swift' is currently not installed. To run 'swift' please ask your administrator")
    assert 2 in cited("ok\nxcodebuild: error: Unable to find a destination matching the provided destination specifier:")


def test_yaml_scanner_error_is_found_before_summary():
    log = "x\n(./a.markdown): found character that cannot start any token while scanning for the next token at line 8\nPlease check the YAML headers!\nCommand failed with status (1)"
    assert 2 in cited(log)


def test_specific_lines_are_supplemented_with_latest_generic_errors():
    log = "a\nERROR: no certificate subject alternative name matches\nb\nmd5sum: x.pkl: No such file or directory\nend"
    assert cited(log) == [2, 4]
