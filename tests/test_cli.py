from pathlib import Path

from releaseguard.main import exit_code_for, main

FIXTURE = str(Path(__file__).parent / "fixtures" / "preflight_plugin_output.json")


def gate(tmp_path, *extra):
    return main(["gate", "--no-llm", "--audit-dir", str(tmp_path), *extra])


def test_exit_code_mapping():
    assert exit_code_for({"final_status": "VALIDATED"}) == 0
    assert exit_code_for({"final_status": "READY_FOR_VALIDATION"}) == 0
    assert exit_code_for({"final_status": "REVIEW_REQUIRED"}) == 2
    assert exit_code_for({"final_status": "BLOCKED"}) == 1


def test_gate_exit_codes(tmp_path):
    assert gate(tmp_path, "--scenario", "pass") == 0
    assert gate(tmp_path, "--scenario", "review") == 2
    assert gate(tmp_path, "--scenario", "fail") == 1
    assert gate(tmp_path, "--scenario", "injection") == 1
    assert gate(tmp_path, "--scenario", "fixed") == 0


def test_gate_with_failing_org_health_requires_review(tmp_path):
    assert gate(tmp_path, "--scenario", "pass", "--preflight", FIXTURE) == 2


def test_bad_scenario_and_bad_preflight_return_2(tmp_path, capsys):
    assert gate(tmp_path, "--scenario", "nope") == 2
    assert gate(tmp_path, "--scenario", "pass", "--preflight", str(tmp_path / "missing.json")) == 2
    assert "ERROR" in capsys.readouterr().err


def test_check_with_authorize_submit_validates(tmp_path):
    code = main(["check", "--scenario", "pass", "--approval", "approve", "--authorize-submit", "--no-llm", "--audit-dir", str(tmp_path)])
    assert code == 0


def test_history_and_verify_audit(tmp_path, capsys):
    gate(tmp_path, "--scenario", "pass")
    assert main(["history", "--audit-dir", str(tmp_path)]) == 0
    assert "audit chain: OK" in capsys.readouterr().out
    assert main(["verify-audit", "--audit-dir", str(tmp_path)]) == 0


def test_demo_runs_all_scenarios(tmp_path, capsys):
    assert main(["demo", "--no-llm", "--audit-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "DEMO SUMMARY" in out
    for scenario in ("pass", "review", "fail", "injection", "fixed"):
        assert scenario in out
