"""Deterministic policy engine.

The AI explains risk, but THIS module makes the decision. The AI can only escalate a release to
human review (rule R8); it can never turn a failing release into a passing one.
The risk score is a plain sum of rule weights, so it is fully explainable.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_FILE = PROJECT_ROOT / "policies.json"

PASS = "PASS"
NEEDS_REVIEW = "NEEDS_REVIEW"
FAIL = "FAIL"

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
DEFAULT_RISK_LEVELS = {"medium": 1, "high": 5}


def load_policies(path: Path | str | None = None) -> dict:
    path = Path(path) if path else DEFAULT_POLICY_FILE
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _weight(rule: dict) -> int:
    if "weight" in rule:
        return int(rule["weight"])
    return 5 if rule["on_violation"] == "fail" else 2


def _violation(rule: dict, message: str, severity: str | None = None) -> dict:
    return {
        "rule_id": rule["id"],
        "description": rule.get("description", ""),
        "severity": severity or rule["on_violation"],
        "message": message,
        "weight": _weight(rule),
    }


def evaluate(
    policies: dict,
    work_item: dict,
    tests: dict,
    job_log: str,
    analysis: dict | None,
    preflight: dict | None = None,
) -> list[dict]:
    """Return the list of policy violations (empty list = clean)."""
    violations: list[dict] = []
    missing_reported: set[str] = set()

    def missing(rule: dict, what: str) -> None:
        # Missing evidence is never treated as a pass - it goes to a human.
        if what not in missing_reported:
            missing_reported.add(what)
            violations.append(_violation(rule, f"No {what} evidence was available", "review"))

    for rule in policies.get("rules", []):
        rtype = rule["type"]

        if rtype == "max_failed_tests":
            failed = tests.get("failed")
            if failed is None:
                missing(rule, "test result")
            elif failed > rule["threshold"]:
                violations.append(_violation(rule, f"{failed} test(s) failed (allowed: {rule['threshold']})"))

        elif rtype == "min_coverage":
            cov = tests.get("coverage_percent")
            if cov is None:
                missing(rule, "code coverage")
            elif cov < rule["threshold"]:
                violations.append(_violation(rule, f"Coverage {cov}% is below {rule['threshold']}%"))

        elif rtype == "max_security":
            sev = rule["severity"]
            count = (work_item.get("security_findings") or {}).get(sev)
            if count is None:
                continue  # scanner did not report this severity; nothing to compare
            if count > rule["threshold"]:
                violations.append(_violation(rule, f"{count} {sev} security finding(s) (allowed: {rule['threshold']})"))

        elif rtype == "log_patterns":
            if not job_log.strip():
                missing(rule, "job log")
                continue
            hits = [p for p in rule["patterns"] if p in job_log]
            if hits:
                violations.append(_violation(rule, "Job log contains: " + ", ".join(hits)))

        elif rtype == "requires_acceptance_criteria":
            if not work_item.get("acceptance_criteria"):
                violations.append(_violation(rule, "Work item has no acceptance criteria"))

        elif rtype == "llm_risk_at_least":
            if analysis is None:
                continue
            level = str(analysis.get("risk_level", "low")).lower()
            if RISK_ORDER.get(level, 0) >= RISK_ORDER[rule["level"]]:
                violations.append(_violation(rule, f"Risk analysis ({analysis.get('source', 'unknown')}) rated the release '{level}' risk"))

        elif rtype == "org_health":
            if not preflight:
                continue  # plugin preflight is optional evidence
            failed_checks = (preflight.get("org_health") or {}).get("fail", 0)
            if failed_checks > rule.get("max_failed_checks", 0):
                names = [c.get("name") or c.get("checkId") for c in (preflight["org_health"].get("failing") or [])][:3]
                detail = f" ({', '.join(str(n) for n in names if n)})" if names else ""
                violations.append(_violation(rule, f"{failed_checks} Copado governance health check(s) failing{detail}"))

    return violations


def decide(violations: list[dict]) -> str:
    """FAIL beats NEEDS_REVIEW beats PASS."""
    if any(v["severity"] == "fail" for v in violations):
        return FAIL
    if any(v["severity"] == "review" for v in violations):
        return NEEDS_REVIEW
    return PASS


def score(violations: list[dict], policies: dict | None = None) -> dict:
    """Explainable risk score: the sum of the weights of the violated rules."""
    levels = (policies or {}).get("risk_levels", DEFAULT_RISK_LEVELS)
    total = sum(v.get("weight", 0) for v in violations)
    if total >= levels.get("high", 5):
        level = "high"
    elif total >= levels.get("medium", 1):
        level = "medium"
    else:
        level = "low"
    return {
        "score": total,
        "level": level,
        "breakdown": [{"rule_id": v["rule_id"], "weight": v.get("weight", 0)} for v in violations],
    }
