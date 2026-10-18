"""Turns real Salesforce Apex test output into a ReleaseGuard scenario.

Create the input with the Salesforce CLI, for example:
    sf apex run test --code-coverage --result-format json --wait 10 --output-dir test-results
(or `--json > apex.json`), then:
    python -m releaseguard import-sf --apex-json apex.json --name my_story --work-id US-0001 --title "My change"
    python -m releaseguard check --scenario my_story

IMPORTANT: the field names below are based on the CLI's documented JSON shape from memory and were tested
only on a hand-made sample. The reader is tolerant, but if a value comes out as None, send me your real file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _get(data: dict, *names, default=None):
    lowered = {str(k).lower(): v for k, v in (data or {}).items()}
    for name in names:
        if name.lower() in lowered and lowered[name.lower()] is not None:
            return lowered[name.lower()]
    return default


def _percent(value) -> float | None:
    if value is None:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(match.group(1)) if match else None


def parse_security(text: str | None) -> dict:
    out: dict = {}
    for part in (text or "").split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            if value.strip().isdigit():
                out[key.strip().lower()] = int(value.strip())
    return out


def import_apex_json(
    apex_json: Path,
    out_dir: Path,
    work_id: str,
    title: str,
    security: dict | None = None,
    acceptance: list[str] | None = None,
    job_id: str | None = None,
) -> dict:
    raw = json.loads(Path(apex_json).read_text(encoding="utf-8-sig"))
    result = _get(raw, "result", default=raw)
    summary = _get(result, "summary", default={}) or {}
    tests = _get(result, "tests", default=[]) or []

    def outcome(t: dict) -> str:
        return str(_get(t, "outcome", default="")).lower()

    passed = _get(summary, "passing")
    failed = _get(summary, "failing")
    skipped = _get(summary, "skipped", default=0)
    if passed is None:
        passed = sum(1 for t in tests if outcome(t) == "pass")
    if failed is None:
        failed = sum(1 for t in tests if outcome(t) in ("fail", "compilefail"))
    total = _get(summary, "testsRan", default=(passed or 0) + (failed or 0) + (skipped or 0))
    coverage = _percent(_get(summary, "testRunCoverage")) or _percent(_get(summary, "orgWideCoverage"))

    failures = []
    log_lines = []
    job = job_id or f"JOB-{work_id}"
    log_lines.append(f"[00:00:01] Job {job} started: Apex test run for {work_id}")
    components = set()
    for t in tests:
        cls = _get(_get(t, "apexClass", default={}) or {}, "name")
        if cls:
            components.add(cls)
        if outcome(t) in ("fail", "compilefail"):
            name = _get(t, "fullName") or f"{cls or 'Unknown'}.{_get(t, 'methodName', default='test')}"
            message = str(_get(t, "message", default="") or "")
            failures.append({"name": name, "error": message})
            log_lines.append(f"ERROR: {name} - {message}")
            for trace_line in str(_get(t, "stackTrace", default="") or "").splitlines():
                log_lines.append(f"    {trace_line.strip()}")
    log_lines.append(f"{passed} tests passed, {failed} failed")
    if coverage is not None:
        log_lines.append(f"Code coverage: {coverage}%")
    final = "Success" if not failed else "Failed"
    log_lines.append(f"Job {job} finished: {final}")

    out_dir.mkdir(parents=True, exist_ok=True)
    work_item = {
        "id": work_id,
        "job_id": job,
        "title": title,
        "description": "Imported from Salesforce CLI Apex test output.",
        "acceptance_criteria": acceptance or [],
        "components": sorted(components),
        "security_findings": security or {},
    }
    test_results = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "coverage_percent": coverage,
        "failures": failures,
    }
    (out_dir / "work_item.json").write_text(json.dumps(work_item, indent=2), encoding="utf-8")
    (out_dir / "test_results.json").write_text(json.dumps(test_results, indent=2), encoding="utf-8")
    (out_dir / "job_log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    (out_dir / "validation_status.json").write_text(
        json.dumps({"status": final, "message": f"Imported Apex run: {final}", "job_id": job}, indent=2), encoding="utf-8"
    )
    return {"work_item": work_item, "test_results": test_results, "out_dir": str(out_dir)}
