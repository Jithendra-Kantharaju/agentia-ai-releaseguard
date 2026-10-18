"""Regression checks for ReleaseGuard's fail-closed release controls."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from releaseguard import audit, policy_engine
from releaseguard.cli_adapter import AgentiaAdapter
from releaseguard.graph import build_graph
from releaseguard.policy_engine import load_policies
from releaseguard.main import main

ROOT = Path(__file__).resolve().parent.parent
POLICIES = load_policies()
GOOD_WORK = {"id": "US-1", "acceptance_criteria": ["a"], "security_findings": {"critical": 0, "high": 0}}
GOOD_TESTS = {"total": 3, "passed": 3, "failed": 0, "coverage_percent": 92}
GOOD_LOG = "All tests passed."


def run_validation(work=GOOD_WORK, tests=GOOD_TESTS, log=GOOD_LOG):
    v = policy_engine.evaluate(POLICIES, work, tests, log, {"risk_level": "low"})
    return policy_engine.decide(v), v


def test_missing_critical_security_is_not_a_zero():
    decision, violations = run_validation({**GOOD_WORK, "security_findings": {"high": 0}})
    assert decision == "FAIL"
    assert any(v["rule_id"] == "R4_NO_CRITICAL_SECURITY" for v in violations)


def test_missing_high_security_requires_review():
    decision, violations = run_validation({**GOOD_WORK, "security_findings": {"critical": 0}})
    assert decision == "NEEDS_REVIEW"
    assert any(v["rule_id"] == "R5_HIGH_SECURITY_REVIEW" for v in violations)


def test_unknown_test_results_block():
    assert run_validation(tests={"failed": None, "coverage_percent": None})[0] == "FAIL"
    assert run_validation(tests={"failed": 0, "total": 0, "coverage_percent": 92})[0] == "FAIL"


def test_audit_malformed_fails_and_cannot_be_overwritten(tmp_path):
    (tmp_path / "audit_log.json").write_text("{not-json", encoding="utf-8")
    assert audit.verify_chain(tmp_path)["ok"] is False
    with pytest.raises(audit.AuditCorruptionError):
        audit.append_entry({"run_id": "x"}, tmp_path)
    assert (tmp_path / "audit_log.json").read_text(encoding="utf-8") == "{not-json"


def test_audit_invalid_structure_fails(tmp_path):
    (tmp_path / "audit_log.json").write_text('{"wrong": "shape"}', encoding="utf-8")
    assert audit.verify_chain(tmp_path)["ok"] is False


def test_real_job_status_must_match_expected_id(monkeypatch):
    adapter = AgentiaAdapter("real")
    monkeypatch.setattr(adapter, "_run", lambda name, work_id: {"ok": True, "command": "agentia", "data": {
        "job_id": "old-job", "status": "Success", "message": "latest job succeeded"}})
    status = adapter.status("US-1", "new-job")
    assert status["status"] == "Unknown" and not status["ok"]


def test_success_word_in_message_is_not_job_success(monkeypatch):
    adapter = AgentiaAdapter("real")
    monkeypatch.setattr(adapter, "_run", lambda name, work_id: {"ok": True, "command": "agentia", "data": {
        "job_id": "job-9", "message": "Success string somewhere"}})
    assert adapter.status("US-1", "job-9")["status"] == "Unknown"


def test_matching_structured_status_is_accepted(monkeypatch):
    adapter = AgentiaAdapter("real")
    monkeypatch.setattr(adapter, "_run", lambda name, work_id: {"ok": True, "command": "agentia", "data": {
        "jobId": "job-9", "status": "Succeeded"}})
    assert adapter.status("US-1", "job-9")["status"] == "Success"


def test_submit_without_job_id_unverified(tmp_path, monkeypatch):
    adapter = AgentiaAdapter("mock", "pass")
    monkeypatch.setattr(adapter, "submit", lambda work_id: {"ok": True, "job_id": None, "message": "accepted"})
    app = build_graph(adapter, POLICIES, use_llm=False, approval_mode="none", authorize_submit=True, audit_dir=tmp_path, say=lambda _: None)
    state = app.invoke({"run_id": "no-job-id", "mode": "mock"})
    assert state["final_status"] == "VALIDATION_UNVERIFIED"
    assert "VALIDATED" != state["final_status"]


class ChangedTests(AgentiaAdapter):
    def __init__(self):
        super().__init__("mock", "pass")
        self.reads = 0

    def run_tests(self, work_id=None):
        self.reads += 1
        tests = super().run_tests(work_id)
        return tests if self.reads == 1 else {**tests, "failed": 1}


def test_recheck_detects_new_test_failure(tmp_path):
    adapter = ChangedTests()
    app = build_graph(adapter, POLICIES, use_llm=False, approval_mode="none", authorize_submit=True, audit_dir=tmp_path, say=lambda _: None)
    state = app.invoke({"run_id": "test-changed", "mode": "mock"})
    assert state["decision"] == "PASS"
    assert state["final_status"] == "BLOCKED"
    assert state["recheck"]["ok"] is False
    assert adapter.reads == 2


def test_policy_file_change_voids_approval(tmp_path):
    from releaseguard import graph
    import copy
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(POLICIES), encoding="utf-8")
    class ChangedPolicy(AgentiaAdapter):
        def __init__(self):
            super().__init__("mock", "pass")
            self.reads = 0
        def run_tests(self, work_id=None):
            self.reads += 1
            if self.reads == 2:
                new_rules = copy.deepcopy(POLICIES)
                new_rules["policy_version"] = "new-version"
                policy_file.write_text(json.dumps(new_rules), encoding="utf-8")
            return super().run_tests(work_id)
    adapter = ChangedPolicy()
    app = build_graph(adapter, POLICIES, policy_path=policy_file, use_llm=False, approval_mode="none", authorize_submit=True, audit_dir=tmp_path, say=lambda _: None)
    state = app.invoke({"run_id": "policy-changed", "mode": "mock"})
    assert state["final_status"] == "BLOCKED"
    assert state["recheck"]["ok"] is False


def test_cli_gate_requires_explicit_mock_scenario(tmp_path):
    assert main(["gate", "--no-llm", "--audit-dir", str(tmp_path)]) == 2


def test_shell_gate_without_configuration_never_passes():
    if os.name == "nt":
        pytest.skip("bash gate script test runs only on POSIX")
    env = os.environ.copy()
    for k in ("RELEASEGUARD_MODE", "RELEASEGUARD_SCENARIO", "RELEASEGUARD_WORK_ID"):
        env.pop(k, None)
    proc = subprocess.run(["bash", str(ROOT / ".agentia_quality_gates.sh")], cwd=ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "REVIEW_REQUIRED" in proc.stderr
