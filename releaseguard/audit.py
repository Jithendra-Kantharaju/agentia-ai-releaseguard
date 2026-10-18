"""Hash-chained JSON audit log and Markdown report writer.

Every entry stores the hash of the previous entry, so editing or deleting an old entry breaks the
chain and `verify-audit` reports it. This detects accidental or casual tampering. It is not a
substitute for a protected, append-only store, because someone with file access could rebuild
the whole chain.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .evidence import canonical, sha256_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = PROJECT_ROOT / "audit"
GENESIS = "GENESIS"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dirs(audit_dir: Path) -> None:
    (audit_dir / "reports").mkdir(parents=True, exist_ok=True)


class AuditCorruptionError(ValueError):
    """Audit log is unreadable or not a list of JSON event objects."""


def load_log(audit_dir: Path = AUDIT_DIR) -> list[dict]:
    path = audit_dir / "audit_log.json"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError, UnicodeError) as exc:
        raise AuditCorruptionError(f"Unreadable audit log: {path}: {exc}") from exc
    if not isinstance(data, list) or not all(isinstance(entry, dict) for entry in data):
        raise AuditCorruptionError(f"Invalid audit log structure: {path}")
    return data


def _entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return sha256_text(canonical(body))


def _write_log(entries: list[dict], audit_dir: Path) -> Path:
    path = audit_dir / "audit_log.json"
    payload = json.dumps(entries, indent=2)
    tmp = audit_dir / "audit_log.json.tmp"
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:  # e.g. a sync client briefly locking the file
        path.write_text(payload, encoding="utf-8")
    return path


def append_entry(entry: dict, audit_dir: Path = AUDIT_DIR) -> Path:
    _ensure_dirs(audit_dir)
    # Do not append onto a damaged chain, which could conceal prior corruption.
    result = verify_chain(audit_dir)
    if not result["ok"]:
        raise AuditCorruptionError(result["message"])
    entries = load_log(audit_dir)
    last = entries[-1] if entries else None
    entry = dict(entry)
    entry["prev_hash"] = last["entry_hash"] if last and "entry_hash" in last else GENESIS
    entry["entry_hash"] = _entry_hash(entry)
    entries.append(entry)
    return _write_log(entries, audit_dir)


def verify_chain(audit_dir: Path = AUDIT_DIR) -> dict:
    """Returns {"ok": bool, "entries": n, "chained": n, "legacy": n, "message": str}."""
    try:
        entries = load_log(audit_dir)
    except AuditCorruptionError as exc:
        return {"ok": False, "entries": 0, "chained": 0, "legacy": 0, "message": str(exc)}
    expected_prev = GENESIS
    chained = legacy = 0
    for index, entry in enumerate(entries, start=1):
        if "entry_hash" not in entry:
            if chained:
                return _result(False, entries, chained, legacy, f"Entry {index} has no hash but follows hashed entries")
            legacy += 1
            continue
        chained += 1
        if entry.get("prev_hash") != expected_prev:
            return _result(False, entries, chained, legacy, f"Entry {index} ({entry.get('run_id')}): chain link is broken")
        if _entry_hash(entry) != entry["entry_hash"]:
            return _result(False, entries, chained, legacy, f"Entry {index} ({entry.get('run_id')}): content was modified")
        expected_prev = entry["entry_hash"]
    return _result(True, entries, chained, legacy, "Audit chain is intact")


def _result(ok: bool, entries: list, chained: int, legacy: int, message: str) -> dict:
    return {"ok": ok, "entries": len(entries), "chained": chained, "legacy": legacy, "message": message}


def build_entry(state: dict) -> dict:
    """The compact record stored in audit_log.json."""
    analysis = state.get("analysis") or {}
    work = state.get("work_item") or {}
    preflight = state.get("preflight") or {}
    return {
        "run_id": state["run_id"],
        "timestamp": now_iso(),
        "work_id": state.get("work_id"),
        "title": work.get("title"),
        "mode": state.get("mode"),
        "evidence_hash": state.get("evidence_hash"),
        "decision": state.get("decision"),
        "final_status": state.get("final_status"),
        "risk": state.get("risk"),
        "human_approval": state.get("approval"),
        "approval_record": state.get("approval_record"),
        "authorize_submit": state.get("authorize_submit"),
        "triage": {
            "source": analysis.get("source"),
            "category": analysis.get("category"),
            "confidence": analysis.get("confidence"),
            "risk_level": analysis.get("risk_level"),
            "cited_lines": analysis.get("cited_lines", []),
            "unverified_citations": len(analysis.get("unverified_citations") or []),
            "citation_validity": analysis.get("citation_validity"),
            "usage": analysis.get("usage"),
        },
        "org_health": (preflight.get("org_health") if preflight else None),
        "violations": state.get("violations", []),
        "recheck": state.get("recheck"),
        "submit_result": state.get("submit_result"),
        "verify_result": state.get("verify_result"),
        "events": state.get("events", []),
    }


def render_report(state: dict) -> str:
    work = state.get("work_item") or {}
    tests = state.get("test_results") or {}
    analysis = state.get("analysis") or {}
    risk = state.get("risk") or {}
    record = state.get("approval_record") or {}
    lines: list[str] = []
    add = lines.append

    add(f"# ReleaseGuard Report - {work.get('id', state.get('work_id'))}")
    add("")
    add(f"- **Run ID:** {state['run_id']}")
    add(f"- **Work item:** {work.get('id')} - {work.get('title')}")
    add(f"- **Mode:** {state.get('mode')}")
    add(f"- **Evidence hash (SHA-256):** `{state.get('evidence_hash')}`")
    add(f"- **Policy decision:** {state.get('decision')}")
    add(f"- **Risk score:** {risk.get('score')} ({risk.get('level')})")
    if record:
        add(f"- **Human review:** {record.get('decision')} by {record.get('reviewer')} at {record.get('time')}")
    else:
        add("- **Human review:** not required")
    add(f"- **Final status:** {state.get('final_status')}")
    add("")
    add("## Evidence summary")
    add("")
    add(f"- Tests: {tests.get('passed')} passed, {tests.get('failed')} failed (total {tests.get('total')})")
    add(f"- Coverage: {tests.get('coverage_percent')}%")
    sec = work.get("security_findings") or {}
    fmt = lambda key: str(sec[key]) if key in sec and sec[key] is not None else "NOT_SCANNED"
    add(f"- Security findings: critical={fmt('critical')}, high={fmt('high')}, medium={fmt('medium')}")
    pf = state.get("preflight")
    if pf:
        health = pf.get("org_health") or {}
        add(f"- Copado governance health: {health.get('pass', 0)} pass, {health.get('warn', 0)} warn, {health.get('fail', 0)} fail")
    add("")
    add("## Policy results")
    add("")
    violations = state.get("violations", [])
    if not violations:
        add("All policies passed.")
    else:
        add("| Rule | Outcome | Weight | Detail |")
        add("|---|---|---|---|")
        for v in violations:
            add(f"| {v['rule_id']} | {v['severity'].upper()} | {v.get('weight', '')} | {v['message']} |")
    add("")
    add("## Failure evidence (verified against the log)")
    add("")
    add(f"- **Source:** {analysis.get('source')}")
    add(f"- **Category:** {analysis.get('category')} (confidence: {analysis.get('confidence')})")
    if analysis.get("root_cause"):
        add(f"- **Root cause (AI):** {analysis['root_cause']}")
    if analysis.get("citation_validity") is not None:
        add(f"- **Citation validity:** {analysis['citation_validity']}")
    cited = analysis.get("cited_lines") or []
    if cited:
        add("")
        add("```")
        for c in cited:
            add(f"L{c['line']}: {c['text']}")
        add("```")
    else:
        add("- No failure lines were cited.")
    if analysis.get("unverified_citations"):
        add("")
        add(f"{len(analysis['unverified_citations'])} citation(s) from the model were rejected because they did not match the log.")
    add("")
    add("## AI risk analysis (advisory only)")
    add("")
    add(f"- **Risk level:** {analysis.get('risk_level')}")
    add(f"- **Recommendation:** {analysis.get('recommendation')}")
    add(f"- **Summary:** {analysis.get('summary')}")
    if analysis.get("note"):
        add(f"- **Note:** {analysis['note']}")
    if analysis.get("key_risks"):
        add("")
        add("Key risks:")
        for r in analysis["key_risks"]:
            add(f"- {r}")
    if analysis.get("failure_explanations"):
        add("")
        add("Failure explanations:")
        for f in analysis["failure_explanations"]:
            add(f"- **{f['item']}**: {f['explanation']} _Fix: {f['suggested_fix']}_")
    add("")
    if state.get("block_reasons"):
        add("## Why this release was blocked")
        add("")
        for r in state["block_reasons"]:
            add(f"- {r}")
        add("")
    if state.get("submit_result"):
        add("## Validation")
        add("")
        add(f"- Submit: {state['submit_result'].get('message')}")
        vr = state.get("verify_result") or {}
        add(f"- Status check: {vr.get('status')} - {vr.get('message')}")
        add("")
    add("## Timeline")
    add("")
    for ev in state.get("events", []):
        add(f"- `{ev['time']}` **{ev['step']}**: {ev['detail']}")
    add("")
    return "\n".join(lines)


def write_report(state: dict, audit_dir: Path = AUDIT_DIR) -> Path:
    _ensure_dirs(audit_dir)
    path = audit_dir / "reports" / f"{state['run_id']}.md"
    path.write_text(render_report(state), encoding="utf-8")
    return path
