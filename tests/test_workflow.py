import json

import pytest

from releaseguard import audit, graph
from releaseguard.cli_adapter import AdapterError, AgentiaAdapter, normalize_tests
from releaseguard.graph import build_graph
from releaseguard.policy_engine import load_policies


def run_flow(scenario, approval="approve", authorize=False, tmp_path=None, reviewer="tester", adapter=None, preflight=None):
    app = build_graph(
        adapter or AgentiaAdapter("mock", scenario),
        load_policies(),
        use_llm=False,
        approval_mode=approval,
        authorize_submit=authorize,
        reviewer=reviewer,
        preflight_path=preflight,
        audit_dir=tmp_path,
        say=lambda _msg: None,
    )
    return app.invoke({"run_id": f"test-{scenario}-{approval}-{authorize}", "mode": "mock"})


def test_pass_without_authorization_is_ready_but_not_submitted(tmp_path):
    state = run_flow("pass", tmp_path=tmp_path)
    assert state["decision"] == "PASS"
    assert state["final_status"] == "READY_FOR_VALIDATION"
    assert "submit_result" not in state


def test_pass_with_authorization_is_validated(tmp_path):
    state = run_flow("pass", authorize=True, tmp_path=tmp_path)
    assert state["final_status"] == "VALIDATED"
    assert state["submit_result"]["ok"]
    assert state["recheck"]["ok"]


def test_fail_scenario_is_blocked_and_never_submitted_even_when_authorized(tmp_path):
    state = run_flow("fail", authorize=True, tmp_path=tmp_path)
    assert state["decision"] == "FAIL"
    assert state["final_status"] == "BLOCKED"
    assert "submit_result" not in state
    assert state["block_reasons"]
    assert state["analysis"]["cited_lines"]  # the block is explained with real log lines


def test_review_approved_records_reviewer_and_evidence_hash(tmp_path):
    state = run_flow("review", approval="approve", authorize=True, tmp_path=tmp_path, reviewer="alice")
    assert state["decision"] == "NEEDS_REVIEW"
    record = state["approval_record"]
    assert record["reviewer"] == "alice"
    assert record["decision"] == "approved"
    assert record["evidence_hash"] == state["evidence_hash"]
    assert state["final_status"] == "VALIDATED"


def test_review_rejected_is_blocked(tmp_path):
    state = run_flow("review", approval="reject", authorize=True, tmp_path=tmp_path)
    assert state["approval"] == "rejected"
    assert state["final_status"] == "BLOCKED"
    assert "submit_result" not in state


def test_gate_mode_stops_at_review_required_without_prompting(tmp_path):
    state = run_flow("review", approval="none", authorize=True, tmp_path=tmp_path)
    assert state["final_status"] == "REVIEW_REQUIRED"
    assert state["approval_record"]["decision"] == "pending"
    assert "submit_result" not in state


def test_interactive_prompt_answer_is_used(tmp_path):
    app = build_graph(
        AgentiaAdapter("mock", "review"), load_policies(), use_llm=False, approval_mode="prompt",
        authorize_submit=True, reviewer="bob", audit_dir=tmp_path, say=lambda _m: None, ask=lambda _q: "y",
    )
    state = app.invoke({"run_id": "t1", "mode": "mock"})
    assert state["approval"] == "approved"
    app = build_graph(
        AgentiaAdapter("mock", "review"), load_policies(), use_llm=False, approval_mode="prompt",
        authorize_submit=True, reviewer="bob", audit_dir=tmp_path, say=lambda _m: None, ask=lambda _q: "",
    )
    assert app.invoke({"run_id": "t2", "mode": "mock"})["final_status"] == "BLOCKED"


def test_fixed_scenario_passes_after_the_failing_one(tmp_path):
    assert run_flow("fail", tmp_path=tmp_path)["final_status"] == "BLOCKED"
    assert run_flow("fixed", authorize=True, tmp_path=tmp_path)["final_status"] == "VALIDATED"


class ChangingAdapter(AgentiaAdapter):
    """Simulates the job log being altered after the human reviewed it."""

    def __init__(self, scenario):
        super().__init__("mock", scenario)
        self.log_reads = 0

    def get_job_log(self, job_id=None):
        self.log_reads += 1
        log = super().get_job_log(job_id)
        return log if self.log_reads == 1 else log + "\n[12:00:00] extra line added later"


def test_evidence_change_after_approval_voids_the_approval(tmp_path):
    state = run_flow("review", approval="approve", authorize=True, tmp_path=tmp_path, adapter=ChangingAdapter("review"))
    assert state["approval"] == "approved"
    assert state["recheck"]["ok"] is False
    assert state["final_status"] == "BLOCKED"
    assert "submit_result" not in state
    assert any("approval is void" in r for r in state["block_reasons"])


def test_evidence_change_on_a_passing_release_blocks_it_too(tmp_path):
    state = run_flow("pass", authorize=True, tmp_path=tmp_path, adapter=ChangingAdapter("pass"))
    assert state["final_status"] == "BLOCKED"
    assert "submit_result" not in state


def test_prompt_injection_in_the_log_cannot_approve_a_failing_release(tmp_path):
    state = run_flow("injection", approval="approve", authorize=True, tmp_path=tmp_path)
    assert state["decision"] == "FAIL"
    assert state["final_status"] == "BLOCKED"
    assert "submit_result" not in state


def test_a_fully_compromised_ai_still_cannot_pass_a_failing_release(tmp_path, monkeypatch):
    def lying_ai(_evidence, use_llm=True):
        return {
            "source": "openai:compromised", "risk_level": "low", "recommendation": "approve", "summary": "All good!",
            "category": "none", "confidence": "high", "key_risks": [], "failure_explanations": [],
            "cited_lines": [], "unverified_citations": [], "citation_validity": None,
        }

    monkeypatch.setattr(graph, "analyze", lying_ai)
    state = run_flow("injection", approval="approve", authorize=True, tmp_path=tmp_path)
    assert state["decision"] == "FAIL"
    assert state["final_status"] == "BLOCKED"


def test_plugin_preflight_with_failing_health_check_forces_review(tmp_path):
    fixture = "tests/fixtures/preflight_plugin_output.json"
    import pathlib

    path = pathlib.Path(__file__).parent / "fixtures" / "preflight_plugin_output.json"
    state = run_flow("pass", approval="none", tmp_path=tmp_path, preflight=str(path))
    assert state["decision"] == "NEEDS_REVIEW"
    assert any(v["rule_id"] == "R9_ORG_HEALTH" for v in state["violations"])
    assert fixture  # keeps the relative path documented


def test_default_reviewer_comes_from_the_plugin_identity(tmp_path):
    import pathlib

    path = pathlib.Path(__file__).parent / "fixtures" / "preflight_plugin_output.json"
    state = run_flow("pass", approval="approve", tmp_path=tmp_path, reviewer=None, preflight=str(path))
    assert state["approval_record"]["reviewer"] == "dana.dev@example.com"


def test_audit_log_and_report_are_written_and_chained(tmp_path):
    run_flow("pass", authorize=True, tmp_path=tmp_path)
    run_flow("fail", tmp_path=tmp_path)
    entries = json.loads((tmp_path / "audit_log.json").read_text(encoding="utf-8"))
    assert [e["decision"] for e in entries] == ["PASS", "FAIL"]
    assert entries[0]["evidence_hash"] and entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert (tmp_path / "reports" / "test-pass-approve-True.md").exists()
    assert audit.verify_chain(tmp_path)["ok"]
    report = (tmp_path / "reports" / "test-fail-approve-False.md").read_text(encoding="utf-8")
    assert "Failure evidence (verified against the log)" in report and "Why this release was blocked" in report


def test_unknown_scenario_raises():
    with pytest.raises(AdapterError):
        AgentiaAdapter("mock", "does-not-exist")


def test_real_mode_without_cli_gives_clear_error(monkeypatch):
    monkeypatch.setattr("releaseguard.cli_adapter.shutil.which", lambda _cmd: None)
    adapter = AgentiaAdapter("real")
    with pytest.raises(AdapterError, match="agentia"):
        adapter.get_work_item("US-1")


def test_normalize_tests_parses_plain_text():
    result = normalize_tests({"raw": "134 tests passed, 6 failed. Code coverage: 68.5%"})
    assert result["passed"] == 134 and result["failed"] == 6
    assert result["coverage_percent"] == 68.5 and result["total"] == 140


def test_normalize_tests_keeps_unknowns_as_none():
    result = normalize_tests({"raw": "nothing useful here"})
    assert result["failed"] is None and result["coverage_percent"] is None
