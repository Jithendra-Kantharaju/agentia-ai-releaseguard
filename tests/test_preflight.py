from pathlib import Path

import pytest

from releaseguard.preflight import PreflightError, default_reviewer, load_preflight, merge_work_item

FIXTURE = Path(__file__).parent / "fixtures" / "preflight_plugin_output.json"


def test_loads_real_plugin_output_with_the_cli_envelope():
    pf = load_preflight(FIXTURE)
    assert pf["user"]["username"] == "dana.dev@example.com"
    assert pf["org_health"]["fail"] == 1
    assert pf["org_health"]["failing"][0]["name"] == "Local quality gate configured"
    assert pf["work_item"]["id"] == "US-0000042"
    assert pf["work_item"]["acceptance_criteria"] == ["Downgrade blocked", "Upgrade saves"]


def test_rejects_files_without_the_schema(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(PreflightError, match="releaseguard.preflight/1"):
        load_preflight(bad)


def test_rejects_invalid_json_and_missing_files(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(PreflightError):
        load_preflight(bad)
    with pytest.raises(PreflightError):
        load_preflight(tmp_path / "missing.json")


def test_cli_work_item_wins_over_plugin_data():
    pf = load_preflight(FIXTURE)
    merged = merge_work_item({"id": "US-1", "title": "From CLI", "acceptance_criteria": []}, pf)
    assert merged["title"] == "From CLI"
    assert merged["id"] == "US-1"
    assert merged["acceptance_criteria"] == ["Downgrade blocked", "Upgrade saves"]


def test_default_reviewer_prefers_copado_identity():
    assert default_reviewer(load_preflight(FIXTURE)) == "dana.dev@example.com"
    assert default_reviewer(None)  # falls back to the OS user
