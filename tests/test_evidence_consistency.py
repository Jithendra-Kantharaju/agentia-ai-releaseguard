"""Regression tests: incomplete or untrusted test evidence cannot pass, and real mode never accepts demo approvals."""
import json
import subprocess

import pytest

from releaseguard import cli_adapter, policy_engine as pe
from releaseguard.cli_adapter import AgentiaAdapter
from releaseguard.graph import build_graph

POLICIES = pe.load_policies()
WORK = {"acceptance_criteria": ["a"], "security_findings": {"critical": 0, "high": 0}}
LOG = "All tests passed."
LOW = {"risk_level": "low"}


def decide(tests, work=WORK):
    return pe.decide(pe.evaluate(POLICIES, work, tests, LOG, LOW))


def good(**over):
    return {"total": 20, "passed": 20, "failed": 0, "coverage_percent": 95, "command_ok": True, **over}


def test_valid_complete_results_pass():
    assert decide(good()) == pe.PASS


@pytest.mark.parametrize("tests", [
    good(total=None, passed=None),            # counts missing
    good(total=0, passed=0),                  # nothing executed
    good(passed=25),                          # passed > total
    good(failed=2),                           # passed + failed > total
    good(passed=-1),                          # impossible value
    good(total="20"),                         # wrong type
    good(passed=True),                        # bool is not a count
])
def test_incomplete_or_inconsistent_counts_block(tests):
    assert decide(tests) == pe.FAIL


def test_failed_test_command_is_untrusted_even_if_counts_look_good():
    violations = pe.evaluate(POLICIES, WORK, good(command_ok=False), LOG, LOW)
    assert pe.decide(violations) == pe.FAIL
    assert any("test command failed" in v["message"] for v in violations)


def test_missing_command_status_in_mock_data_does_not_block():
    tests = {"total": 20, "passed": 20, "failed": 0, "coverage_percent": 95}
    assert decide(tests) == pe.PASS


class FakeProc:
    def __init__(self, out, code):
        self.stdout, self.stderr, self.returncode = out, "boom" if code else "", code


def _patch_run(monkeypatch, out, code):
    monkeypatch.setattr(cli_adapter.shutil, "which", lambda c: "agentia")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: FakeProc(out, code))
    monkeypatch.delenv("AGENTIA_APEX_TEST_CLASSES", raising=False)


def test_adapter_keeps_nonzero_exit_separate_from_reported_counts(monkeypatch):
    _patch_run(monkeypatch, json.dumps({"total": 5, "passed": 5, "failed": 0, "coverage_percent": 90}), 1)
    tests = AgentiaAdapter("real").run_tests("US-1")
    assert tests["command_ok"] is False and tests["failed"] == 0 and "boom" in tests["execution_error"]
    assert decide(tests) == pe.FAIL


def test_adapter_marks_successful_command(monkeypatch):
    _patch_run(monkeypatch, json.dumps({"total": 5, "passed": 5, "failed": 0, "coverage_percent": 90}), 0)
    tests = AgentiaAdapter("real").run_tests("US-1")
    assert tests["command_ok"] is True and decide(tests) == pe.PASS


class FakeRealAdapter(AgentiaAdapter):
    """Real-mode adapter with canned evidence that needs human review (no acceptance criteria)."""

    def __init__(self):
        super().__init__("real")
        self.submitted = False

    def get_work_item(self, work_id=None):
        return {"id": "US-1", "title": "t", "acceptance_criteria": [], "security_findings": {"critical": 0, "high": 0}}

    def run_tests(self, work_id=None):
        return good()

    def get_job_log(self, job_id=None):
        return LOG

    def get_preflight(self, path=None):
        return None

    def submit(self, work_id=None):
        self.submitted = True
        return {"ok": True, "job_id": "J-1", "message": "should never run"}


@pytest.mark.parametrize("mode", ["approve", "prompt", "reject"])
def test_real_mode_never_accepts_demo_or_terminal_approval(tmp_path, mode):
    adapter = FakeRealAdapter()
    app = build_graph(adapter, POLICIES, use_llm=False, approval_mode=mode, authorize_submit=True,
                      audit_dir=tmp_path, say=lambda _: None, ask=lambda _: "y")
    state = app.invoke({"run_id": f"real-{mode}", "mode": "real"})
    assert state["decision"] == pe.NEEDS_REVIEW
    assert state["approval"] == "pending" and state["final_status"] == "REVIEW_REQUIRED"
    assert adapter.submitted is False