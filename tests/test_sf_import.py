import json

from releaseguard.sf_import import import_apex_json, parse_security

APEX = {
    "status": 0,
    "result": {
        "summary": {"outcome": "Failed", "testsRan": 3, "passing": 2, "failing": 1, "skipped": 0, "testRunCoverage": "71%"},
        "tests": [
            {"outcome": "Pass", "fullName": "AccountTest.ok", "apexClass": {"name": "AccountTest"}},
            {"outcome": "Pass", "fullName": "AccountTest.ok2", "apexClass": {"name": "AccountTest"}},
            {
                "outcome": "Fail", "fullName": "LeadTest.lock", "message": "UNABLE_TO_LOCK_ROW: record locked",
                "stackTrace": "Class.LeadTest.lock: line 12", "apexClass": {"name": "LeadTest"},
            },
        ],
    },
}


def test_parse_security():
    assert parse_security("critical=0, high=2") == {"critical": 0, "high": 2}
    assert parse_security(None) == {} and parse_security("junk,high=x") == {}


def test_import_writes_a_runnable_scenario(tmp_path):
    src = tmp_path / "apex.json"
    src.write_text(json.dumps(APEX), encoding="utf-8")
    out = tmp_path / "scn"
    result = import_apex_json(src, out, "US-9", "Lock fix", {"critical": 0}, ["Works"])
    tests = result["test_results"]
    assert (tests["passed"], tests["failed"], tests["total"], tests["coverage_percent"]) == (2, 1, 3, 71.0)
    assert tests["failures"][0]["name"] == "LeadTest.lock"
    log = (out / "job_log.txt").read_text(encoding="utf-8")
    assert "ERROR: LeadTest.lock - UNABLE_TO_LOCK_ROW" in log and "finished: Failed" in log
    assert sorted(p.name for p in out.iterdir()) == ["job_log.txt", "test_results.json", "validation_status.json", "work_item.json"]
    assert json.loads((out / "work_item.json").read_text(encoding="utf-8"))["components"] == ["AccountTest", "LeadTest"]


def test_import_without_summary_counts_tests(tmp_path):
    src = tmp_path / "a.json"
    src.write_text(json.dumps({"result": {"tests": APEX["result"]["tests"]}}), encoding="utf-8")
    result = import_apex_json(src, tmp_path / "o", "US-1", "t")
    assert result["test_results"]["passed"] == 2 and result["test_results"]["failed"] == 1
    assert result["test_results"]["coverage_percent"] is None


def test_imported_scenario_is_blocked_by_the_workflow(tmp_path, monkeypatch):
    from releaseguard import cli_adapter
    from releaseguard.main import main

    src = tmp_path / "apex.json"
    src.write_text(json.dumps(APEX), encoding="utf-8")
    monkeypatch.setattr(cli_adapter, "MOCK_DIR", tmp_path / "mock")
    assert main(["import-sf", "--apex-json", str(src), "--name", "imp", "--work-id", "US-9", "--title", "T"]) == 0
    code = main(["gate", "--scenario", "imp", "--no-llm", "--audit-dir", str(tmp_path / "audit")])
    assert code == 1
