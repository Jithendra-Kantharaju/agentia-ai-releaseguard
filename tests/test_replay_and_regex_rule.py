import json

from releaseguard import cli_adapter, policy_engine as pe
from releaseguard.main import main
from releaseguard.replay import list_candidates, make_scenario

POLICIES = pe.load_policies()
OK_WORK = {"acceptance_criteria": ["a"], "security_findings": {}}
OK_TESTS = {"total": 1, "passed": 1, "failed": 0, "coverage_percent": 99.0}


def verdict(log):
    v = pe.evaluate(POLICIES, OK_WORK, OK_TESTS, log, {"risk_level": "low"})
    return pe.decide(v), [x["rule_id"] for x in v]


def test_travis_nonzero_exit_fails_the_release():
    decision, rules = verdict('building\nThe command "make test" exited with 2.\nDone. Your build exited with 1.')
    assert decision == pe.FAIL and "R10_JOB_EXIT_NONZERO" in rules


def test_github_actions_nonzero_exit_fails():
    assert verdict("Error: Process completed with exit code 1.")[0] == pe.FAIL


def test_zero_exit_does_not_trigger_the_rule():
    decision, rules = verdict('The command "make" exited with 0.\nDone. Your build exited with 0.')
    assert "R10_JOB_EXIT_NONZERO" not in rules and decision == pe.PASS


def test_empty_log_still_goes_to_a_human():
    assert verdict("")[0] == pe.NEEDS_REVIEW


LOG = "\n".join(["compile"] * 5 + ["configure: error: C compiler cannot create executables", "thread 'main' panicked", 'The command "ci/script.sh" exited with 101.', "Done. Your build exited with 1."])


def write_dataset(tmp_path, items=None):
    items = items or [
        {"id": "own@lib:111", "repo": "own@lib", "language": "Rust", "category": "0", "log": LOG, "gold_lines": [6, 7]},
        {"id": "own@lib:112", "repo": "own@lib", "language": "Rust", "category": "0", "log": LOG, "gold_lines": [6]},
        {"id": "x@y:5", "repo": "x@y", "language": "Go", "category": "1", "log": LOG, "gold_lines": [7]},
    ]
    path = tmp_path / "d.jsonl"
    path.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")
    return str(path)


def test_list_candidates_shows_one_row_per_repo(tmp_path):
    rows = list_candidates(write_dataset(tmp_path), "all", 10)
    assert [r["id"] for r in rows] == ["own@lib:111", "x@y:5"]


def test_make_scenario_writes_real_log_and_unknown_test_evidence(tmp_path):
    out = tmp_path / "scn"
    result = make_scenario(write_dataset(tmp_path), "own@lib:111", out)
    assert result["gold_lines"] == [6, 7] and (out / "job_log.txt").read_text(encoding="utf-8").startswith("compile")
    tests = json.loads((out / "test_results.json").read_text(encoding="utf-8"))
    assert tests["failed"] is None
    assert json.loads((out / "replay_source.json").read_text(encoding="utf-8"))["source"].startswith("LogChunks")


def test_make_scenario_unknown_id_is_a_clear_error(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="No log with id"):
        make_scenario(write_dataset(tmp_path), "nope:1", tmp_path / "o")


def test_replayed_real_failure_is_blocked_by_the_gate_with_verified_evidence(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_adapter, "MOCK_DIR", tmp_path / "mock")
    dataset = write_dataset(tmp_path)
    assert main(["replay-logchunks", "--dataset", dataset, "--id", "own@lib:111", "--name", "real_rust"]) == 0
    code = main(["gate", "--scenario", "real_rust", "--no-llm", "--audit-dir", str(tmp_path / "audit")])
    out = capsys.readouterr().out
    assert code == 1 and "R10_JOB_EXIT_NONZERO" in out and "configure: error" in out
    assert "decision=FAIL" in out


def test_replay_command_needs_arguments(tmp_path, capsys):
    assert main(["replay-logchunks", "--dataset", write_dataset(tmp_path)]) == 2
    assert main(["replay-logchunks", "--dataset", write_dataset(tmp_path), "--list", "5"]) == 0
    assert "own@lib:111" in capsys.readouterr().out