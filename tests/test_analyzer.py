import json

from releaseguard import analyzer
from releaseguard.analyzer import (
    analyze,
    analyze_offline,
    baseline_triage,
    build_user_message,
    numbered_window,
    verify_citations,
)

FAIL_EVIDENCE = {
    "work_item": {"security_findings": {"critical": 1, "high": 0}},
    "test_results": {"failed": 2, "coverage_percent": 60, "failures": [{"name": "T1", "error": "boom"}]},
    "job_log": "step 1\nERROR: broken thing\nstep 3\nBUILD FAILED",
}
CLEAN_EVIDENCE = {
    "work_item": {"security_findings": {"critical": 0, "high": 0}},
    "test_results": {"failed": 0, "coverage_percent": 95},
    "job_log": "128 tests passed, 0 failed\nJob finished: Success",
}
LOG = "line one\nERROR: disk full on /var\nline three"


# ---- baseline
def test_baseline_cites_real_lines_with_numbers():
    result = baseline_triage(LOG)
    assert result["category"] == "generic_error"
    assert result["cited_lines"] == [{"line": 2, "text": "ERROR: disk full on /var"}]


def test_baseline_ignores_zero_failure_lines():
    assert baseline_triage(CLEAN_EVIDENCE["job_log"])["cited_lines"] == []


def test_baseline_picks_the_highest_priority_category():
    log = "ERROR: something\nCould not resolve dependencies for project"
    assert baseline_triage(log)["category"] == "dependency_error"


# ---- citation verification
def test_verified_citation_uses_the_real_line_text():
    valid, invalid = verify_citations([{"line": 2, "quote": "ERROR: disk full"}], LOG.split("\n"))
    assert valid == [{"line": 2, "text": "ERROR: disk full on /var"}]
    assert invalid == []


def test_wrong_quote_for_the_line_is_rejected():
    valid, invalid = verify_citations([{"line": 1, "quote": "ERROR: disk full"}], LOG.split("\n"))
    assert valid == [] and invalid[0]["reason"] == "quote does not match that line"


def test_nonexistent_line_and_garbage_are_rejected():
    valid, invalid = verify_citations([{"line": 99, "quote": "anything"}, {"line": "x"}, "nope"], LOG.split("\n"))
    assert valid == [] and len(invalid) == 3


# ---- prompt construction
def test_long_logs_keep_head_and_tail_with_original_line_numbers():
    log = "\n".join(f"row {i}" for i in range(1, 1001))
    window, lines = numbered_window(log)
    assert "1: row 1" in window and "1000: row 1000" in window
    assert "omitted" in window and "500: row 500" not in window
    assert len(lines) == 1000


def test_prompt_marks_evidence_as_untrusted_data():
    assert "untrusted DATA" in analyzer.SYSTEM_PROMPT
    assert "1: line one" in build_user_message({"job_log": LOG})


# ---- LLM path with a fake model
def fake_model(reply):
    def _call(_system, _user):
        return reply, {"model": "fake", "prompt_tokens": 10, "completion_tokens": 5, "latency_s": 0.01}

    return _call


def test_llm_result_is_verified_and_unverifiable_citations_are_dropped(monkeypatch):
    reply = {
        "category": "generic_error", "root_cause": "Disk is full", "confidence": "high",
        "cited_lines": [{"line": 2, "quote": "ERROR: disk full"}, {"line": 3, "quote": "made up error text"}],
        "risk_level": "high", "summary": "s", "key_risks": ["disk"], "failure_explanations": [], "recommendation": "reject",
    }
    monkeypatch.setattr(analyzer, "_call_openai", fake_model(reply))
    result = analyzer.analyze_with_openai({"job_log": LOG})
    assert result["source"] == "openai:fake"
    assert [c["line"] for c in result["cited_lines"]] == [2]
    assert len(result["unverified_citations"]) == 1
    assert result["citation_validity"] == 0.5
    assert result["usage"]["prompt_tokens"] == 10


def test_confidence_is_lowered_when_nothing_can_be_verified(monkeypatch):
    reply = {"category": "test_failure", "confidence": "high", "cited_lines": [{"line": 50, "quote": "x"}], "risk_level": "low"}
    monkeypatch.setattr(analyzer, "_call_openai", fake_model(reply))
    result = analyzer.analyze_with_openai({"job_log": LOG})
    assert result["confidence"] == "low" and "lowered" in result["note"]


def test_invalid_model_values_are_normalised(monkeypatch):
    reply = {"category": "banana", "confidence": "certain", "risk_level": "extreme", "recommendation": "ship it", "cited_lines": "none"}
    monkeypatch.setattr(analyzer, "_call_openai", fake_model(reply))
    result = analyzer.analyze_with_openai({"job_log": LOG})
    assert (result["category"], result["confidence"], result["risk_level"], result["recommendation"]) == ("other", "low", "medium", "review")


def test_analyze_uses_the_llm_when_a_key_is_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(analyzer, "_call_openai", fake_model({"risk_level": "low", "cited_lines": []}))
    result = analyze(CLEAN_EVIDENCE, use_llm=True)
    assert result["source"] == "openai:fake" and "baseline" in result


# ---- offline and fallbacks
def test_offline_flags_high_risk_and_cites_lines():
    result = analyze_offline(FAIL_EVIDENCE)
    assert result["risk_level"] == "high"
    assert result["failure_explanations"][0]["item"] == "T1"
    assert result["cited_lines"] and result["source"] == "offline-baseline"


def test_offline_low_risk_for_clean_release():
    assert analyze_offline(CLEAN_EVIDENCE)["risk_level"] == "low"


def test_analyze_without_api_key_falls_back(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = analyze(FAIL_EVIDENCE, use_llm=True)
    assert result["source"] == "offline-baseline"
    assert "OPENAI_API_KEY" in result["note"]


def test_analyze_survives_openai_errors(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")

    def boom(_system, _user):
        raise RuntimeError("network down")

    monkeypatch.setattr(analyzer, "_call_openai", boom)
    result = analyze(CLEAN_EVIDENCE, use_llm=True)
    assert result["source"] == "offline-baseline"
    assert "failed" in result["note"]


def test_no_llm_flag_skips_openai_even_with_a_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")

    def must_not_run(_system, _user):
        raise AssertionError("OpenAI must not be called")

    monkeypatch.setattr(analyzer, "_call_openai", must_not_run)
    assert analyze(CLEAN_EVIDENCE, use_llm=False)["source"] == "offline-baseline"
    assert json.dumps(analyze(CLEAN_EVIDENCE, use_llm=False))  # result is JSON-serialisable
