from releaseguard import policy_engine as pe

POLICIES = pe.load_policies()

GOOD_WORK = {"acceptance_criteria": ["a"], "security_findings": {"critical": 0, "high": 0}}
GOOD_TESTS = {"total": 10, "passed": 10, "failed": 0, "coverage_percent": 90.0}
CLEAN_LOG = "all good\nJob finished: Success"
LOW_RISK = {"risk_level": "low", "source": "test"}
HEALTHY = {"org_health": {"fail": 0, "warn": 0, "pass": 5, "total": 5, "failing": []}}


def run(work=GOOD_WORK, tests=GOOD_TESTS, log=CLEAN_LOG, analysis=LOW_RISK, preflight=None):
    violations = pe.evaluate(POLICIES, work, tests, log, analysis, preflight)
    return violations, pe.decide(violations)


def test_clean_release_passes():
    violations, decision = run()
    assert violations == []
    assert decision == pe.PASS


def test_failed_tests_fail_the_release():
    _, decision = run(tests={**GOOD_TESTS, "failed": 2})
    assert decision == pe.FAIL


def test_coverage_between_75_and_85_needs_review():
    _, decision = run(tests={**GOOD_TESTS, "coverage_percent": 80.0})
    assert decision == pe.NEEDS_REVIEW


def test_coverage_below_75_fails():
    _, decision = run(tests={**GOOD_TESTS, "coverage_percent": 70.0})
    assert decision == pe.FAIL


def test_critical_security_fails():
    work = {**GOOD_WORK, "security_findings": {"critical": 1, "high": 0}}
    _, decision = run(work=work)
    assert decision == pe.FAIL


def test_high_security_needs_review():
    work = {**GOOD_WORK, "security_findings": {"critical": 0, "high": 1}}
    _, decision = run(work=work)
    assert decision == pe.NEEDS_REVIEW


def test_error_in_log_fails():
    _, decision = run(log="ERROR: something broke")
    assert decision == pe.FAIL


def test_missing_acceptance_criteria_needs_review():
    _, decision = run(work={**GOOD_WORK, "acceptance_criteria": []})
    assert decision == pe.NEEDS_REVIEW


def test_missing_mandatory_test_evidence_blocks_release():
    _, decision = run(tests={"total": None, "passed": None, "failed": None, "coverage_percent": None})
    assert decision == pe.FAIL


def test_empty_log_blocks_when_log_is_mandatory():
    _, decision = run(log="")
    assert decision == pe.FAIL


def test_ai_high_risk_escalates_to_review():
    _, decision = run(analysis={"risk_level": "high", "source": "openai:x"})
    assert decision == pe.NEEDS_REVIEW


def test_ai_low_risk_cannot_override_a_failure():
    _, decision = run(tests={**GOOD_TESTS, "failed": 3}, analysis={"risk_level": "low", "recommendation": "approve"})
    assert decision == pe.FAIL


def test_failing_org_health_needs_review():
    pf = {"org_health": {"fail": 2, "failing": [{"name": "Gate config"}]}}
    violations, decision = run(preflight=pf)
    assert decision == pe.NEEDS_REVIEW
    assert "Gate config" in violations[0]["message"]


def test_healthy_org_or_missing_preflight_adds_nothing():
    assert run(preflight=HEALTHY)[1] == pe.PASS
    assert run(preflight=None)[1] == pe.PASS


def test_risk_score_is_the_sum_of_weights():
    violations, _ = run(tests={**GOOD_TESTS, "failed": 1, "coverage_percent": 80.0})
    risk = pe.score(violations, POLICIES)
    assert risk["score"] == 5 + 2
    assert risk["level"] == "high"
    assert {b["rule_id"] for b in risk["breakdown"]} == {"R1_NO_FAILED_TESTS", "R3_TARGET_COVERAGE"}


def test_clean_release_has_zero_risk():
    risk = pe.score([], POLICIES)
    assert risk == {"score": 0, "level": "low", "breakdown": []}
