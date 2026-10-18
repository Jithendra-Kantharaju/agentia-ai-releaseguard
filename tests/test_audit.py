import json

from releaseguard import audit


def entry(n):
    return {"run_id": f"run-{n}", "decision": "PASS", "final_status": "VALIDATED"}


def test_appended_entries_form_a_valid_chain(tmp_path):
    for n in range(3):
        audit.append_entry(entry(n), tmp_path)
    result = audit.verify_chain(tmp_path)
    assert result["ok"] and result["chained"] == 3 and result["legacy"] == 0
    entries = audit.load_log(tmp_path)
    assert entries[0]["prev_hash"] == audit.GENESIS
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]


def test_editing_an_old_entry_is_detected(tmp_path):
    for n in range(3):
        audit.append_entry(entry(n), tmp_path)
    path = tmp_path / "audit_log.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[1]["decision"] = "FAIL"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = audit.verify_chain(tmp_path)
    assert not result["ok"]
    assert "modified" in result["message"]


def test_deleting_an_entry_is_detected(tmp_path):
    for n in range(3):
        audit.append_entry(entry(n), tmp_path)
    path = tmp_path / "audit_log.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data[1]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert not audit.verify_chain(tmp_path)["ok"]


def test_legacy_v1_entries_are_tolerated_and_counted(tmp_path):
    (tmp_path / "audit_log.json").write_text(json.dumps([entry(0), entry(1)]), encoding="utf-8")
    audit.append_entry(entry(2), tmp_path)
    result = audit.verify_chain(tmp_path)
    assert result["ok"]
    assert result["legacy"] == 2 and result["chained"] == 1
    assert audit.load_log(tmp_path)[2]["prev_hash"] == audit.GENESIS


def test_empty_log_is_ok(tmp_path):
    assert audit.verify_chain(tmp_path)["ok"]
