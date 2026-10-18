"""LangGraph workflow for ReleaseGuard v2.

collect -> triage -> policy -> PASS ----------------------> recheck -> ready | submit -> verify -> report
                               NEEDS_REVIEW -> approval --> recheck (approved) | block (rejected) | report (pending)
                               FAIL ----------------------> block -> report

Safety rules
  * The AI only explains. The policy engine decides.
  * An approval is bound to the SHA-256 hash of the evidence and to the reviewer's identity.
  * Before anything is submitted the evidence is re-read; if it changed, the approval is void.
  * Nothing is submitted unless the caller passes authorize_submit=True. Submit means VALIDATION only.
"""

from __future__ import annotations

from pathlib import Path
from time import sleep
from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph

from . import audit, policy_engine
from .analyzer import analyze
from .cli_adapter import AgentiaAdapter
from .evidence import evidence_hash, short
from .preflight import default_reviewer, merge_work_item


class ReleaseState(TypedDict, total=False):
    run_id: str
    mode: str
    work_id: str
    job_id: str
    work_item: dict
    test_results: dict
    job_log: str
    preflight: dict
    evidence_hash: str
    analysis: dict
    violations: list
    risk: dict
    decision: str
    approval: str
    approval_record: dict
    recheck: dict
    authorize_submit: bool
    block_reasons: list
    submit_result: dict
    verify_result: dict
    final_status: str
    events: list
    report_path: str


def _event(state: ReleaseState, step: str, detail: str) -> list:
    return list(state.get("events", [])) + [{"time": audit.now_iso(), "step": step, "detail": detail}]


def build_graph(
    adapter: AgentiaAdapter,
    policies: dict,
    use_llm: bool = True,
    approval_mode: str = "prompt",
    authorize_submit: bool = False,
    reviewer: str | None = None,
    preflight_path: str | None = None,
    audit_dir: Path = audit.AUDIT_DIR,
    policy_path: str | Path | None = None,
    say: Callable[[str], None] = print,
    ask: Callable[[str], str] = input,
):
    """Build and compile the workflow.

    approval_mode: 'prompt' (ask in the terminal), 'approve' / 'reject' (automatic, for demos and
    tests) or 'none' (non-interactive gate: a release that needs review stops as REVIEW_REQUIRED).
    """

    def tag(name: str) -> str:
        return f"[{name}]".ljust(11)

    # ---------------------------------------------------------------- nodes
    def collect(state: ReleaseState) -> dict:
        preflight = adapter.get_preflight(preflight_path)
        work_item = merge_work_item(adapter.get_work_item(state.get("work_id")), preflight)
        work_id = state.get("work_id") or work_item.get("id")
        job_id = state.get("job_id") or work_item.get("job_id") or work_item.get("jobId")
        tests = adapter.run_tests(work_id)
        job_log = adapter.get_job_log(job_id)
        digest = evidence_hash(work_item, tests, job_log, preflight, policies)
        say(f"{tag('collect')}work item {work_item.get('id')} - {work_item.get('title')}")
        say(f"{' ' * 11}tests: {tests.get('passed')} passed, {tests.get('failed')} failed, coverage {tests.get('coverage_percent')}%")
        if preflight:
            health = preflight["org_health"]
            who = preflight["user"].get("username") or preflight["user"].get("name")
            say(f"{' ' * 11}plugin preflight: user={who}, governance checks failing={health['fail']}")
        say(f"{' ' * 11}evidence hash: {short(digest)}...")
        return {
            "work_item": work_item,
            "work_id": work_id,
            "job_id": job_id,
            "test_results": tests,
            "job_log": job_log,
            "preflight": preflight,
            "evidence_hash": digest,
            "events": _event(state, "collect", f"Collected evidence for {work_id}; hash {short(digest)}"),
        }

    def triage(state: ReleaseState) -> dict:
        evidence = {
            "work_item": state["work_item"],
            "test_results": state["test_results"],
            "job_log": state["job_log"],
        }
        result = analyze(evidence, use_llm=use_llm)
        say(f"{tag('triage')}source={result['source']}  category={result.get('category')}  confidence={result.get('confidence')}  risk={result['risk_level']}")
        for c in (result.get("cited_lines") or [])[:3]:
            say(f"{' ' * 11}L{c['line']}: {c['text'][:90]}")
        if result.get("unverified_citations"):
            say(f"{' ' * 11}rejected {len(result['unverified_citations'])} unverifiable AI citation(s)")
        if result.get("note"):
            say(f"{' ' * 11}note: {result['note']}")
        return {
            "analysis": result,
            "events": _event(state, "triage", f"{result['source']}: category {result.get('category')}, risk {result['risk_level']}"),
        }

    def validate(state: ReleaseState) -> dict:
        violations = policy_engine.evaluate(
            policies,
            state["work_item"],
            state["test_results"],
            state["job_log"],
            state.get("analysis"),
            state.get("preflight"),
        )
        decision = policy_engine.decide(violations)
        risk = policy_engine.score(violations, policies)
        say(f"{tag('policy')}violations: {len(violations)}   risk score: {risk['score']} ({risk['level']})")
        for v in violations:
            say(f"{' ' * 11}- [{v['severity'].upper()}] {v['rule_id']}: {v['message']}")
        say(f"{tag('decide')}{decision}")
        return {
            "violations": violations,
            "risk": risk,
            "decision": decision,
            "events": _event(state, "decide", f"Policy decision {decision}; {len(violations)} violation(s); risk {risk['score']}"),
        }

    def human_approval(state: ReleaseState) -> dict:
        who = reviewer or default_reviewer(state.get("preflight"))
        digest = state["evidence_hash"]
        if approval_mode == "none":
            answer = "pending"
            say(f"{tag('approval')}human review required; no reviewer available (gate mode)")
        elif approval_mode == "approve":
            answer = "approved"
            say(f"{tag('approval')}(auto) approved as {who}")
        elif approval_mode == "reject":
            answer = "rejected"
            say(f"{tag('approval')}(auto) rejected as {who}")
        else:
            say(f"{tag('approval')}human review required (reviewer: {who}, evidence {short(digest)}...)")
            reply = ask(f"{' ' * 11}Approve this exact evidence for validation? [y/N]: ").strip().lower()
            answer = "approved" if reply in ("y", "yes") else "rejected"
        record = {"reviewer": who, "decision": answer, "evidence_hash": digest, "time": audit.now_iso()}
        update: dict = {
            "approval": answer,
            "approval_record": record,
            "events": _event(state, "approval", f"{who} {answer} evidence {short(digest)}"),
        }
        if answer == "pending":
            update["final_status"] = "REVIEW_REQUIRED"
        return update

    def recheck(state: ReleaseState) -> dict:
        # Re-read ALL decision-relevant evidence; approval is invalid if any of it changed.
        fresh_preflight = adapter.get_preflight(preflight_path)
        fresh_work = merge_work_item(adapter.get_work_item(state.get("work_id")), fresh_preflight)
        fresh_tests = adapter.run_tests(state.get("work_id"))
        fresh_log = adapter.get_job_log(state.get("job_id"))
        fresh_policies = policy_engine.load_policies(policy_path) if policy_path else policies
        fresh = evidence_hash(fresh_work, fresh_tests, fresh_log, fresh_preflight, fresh_policies)
        fresh_violations = policy_engine.evaluate(
            fresh_policies, fresh_work, fresh_tests, fresh_log, state.get("analysis"), fresh_preflight
        )
        fresh_decision = policy_engine.decide(fresh_violations)
        ok = fresh == state["evidence_hash"] and fresh_decision == state["decision"]
        record = {
            "ok": ok, "approved_hash": state["evidence_hash"], "current_hash": fresh,
            "fresh_decision": fresh_decision,
        }
        if ok:
            say(f"{tag('recheck')}evidence unchanged ({short(fresh)}...)")
        else:
            say(f"{tag('recheck')}EVIDENCE CHANGED: {short(state['evidence_hash'])}... -> {short(fresh)}...")
        return {
            "recheck": record,
            "events": _event(state, "recheck", "Evidence unchanged" if ok else "Evidence changed after analysis; approval void"),
        }

    def ready(state: ReleaseState) -> dict:
        say(f"{tag('submit')}not authorized (add --authorize-submit to submit for validation)")
        return {
            "final_status": "READY_FOR_VALIDATION",
            "events": _event(state, "ready", "Checks passed; submit not authorized"),
        }

    def submit(state: ReleaseState) -> dict:
        say(f"{tag('submit')}agentia cicd work submit (validation only)...")
        result = adapter.submit(state.get("work_id"))
        say(f"{' ' * 11}{result['message']}")
        return {
            "submit_result": result,
            "events": _event(state, "submit", result["message"]),
        }

    def verify(state: ReleaseState) -> dict:
        submit_result = state.get("submit_result") or {}
        if not submit_result.get("ok"):
            status = {"status": "Failed", "message": "Submission command failed"}
            final = "VALIDATION_FAILED"
        elif not submit_result.get("job_id"):
            status = {"status": "Unknown", "message": "No structured job ID returned by Agentia CLI"}
            final = "VALIDATION_UNVERIFIED"
        else:
            expected_id = submit_result["job_id"]
            attempts = 1 if adapter.mode == "mock" else 4
            status = {"status": "Unknown", "message": "Not checked"}
            for attempt in range(attempts):
                status = adapter.status(state.get("work_id"), job_id=expected_id)
                if status.get("status") in ("Success", "Failed") or not status.get("ok"):
                    break
                if attempt < attempts - 1:
                    sleep(2)
            final = {
                "Success": "VALIDATED",
                "Failed": "VALIDATION_FAILED",
            }.get(status.get("status"), "VALIDATION_UNVERIFIED")
            if not status.get("ok"):
                final = "VALIDATION_UNVERIFIED"
        say(f"{tag('verify')}status: {status.get('status')} - {status.get('message')}")
        return {
            "verify_result": status,
            "final_status": final,
            "events": _event(state, "verify", f"Validation status: {status.get('status')}"),
        }

    def block(state: ReleaseState) -> dict:
        reasons = [f"{v['rule_id']}: {v['message']}" for v in state.get("violations", [])]
        record = state.get("recheck") or {}
        if record and not record.get("ok"):
            if state.get("approval") == "approved":
                reasons.append("Evidence changed after the human approval, so the approval is void")
            else:
                reasons.append("Evidence changed between analysis and submission")
        if state.get("approval") == "rejected":
            reasons.append("Human reviewer rejected the release")
        say(f"{tag('block')}release blocked, nothing submitted")
        for r in reasons:
            say(f"{' ' * 11}- {r}")
        cited = (state.get("analysis") or {}).get("cited_lines") or []
        if cited:
            say(f"{' ' * 11}evidence:")
            for c in cited[:3]:
                say(f"{' ' * 13}L{c['line']}: {c['text'][:90]}")
        return {
            "block_reasons": reasons,
            "final_status": "BLOCKED",
            "events": _event(state, "block", f"Release blocked; {len(reasons)} reason(s) recorded"),
        }

    def report(state: ReleaseState) -> dict:
        events = _event(state, "report", f"Final status {state.get('final_status')}")
        final_state = {**state, "events": events, "authorize_submit": authorize_submit}
        report_path = audit.write_report(final_state, audit_dir)
        audit.append_entry(audit.build_entry(final_state), audit_dir)
        say(f"{tag('report')}{report_path}")
        return {"events": events, "report_path": str(report_path)}

    # ---------------------------------------------------------------- routing
    def route_after_validate(state: ReleaseState) -> str:
        return {
            policy_engine.PASS: "recheck",
            policy_engine.NEEDS_REVIEW: "human_approval",
            policy_engine.FAIL: "block",
        }[state["decision"]]

    def route_after_approval(state: ReleaseState) -> str:
        return {"approved": "recheck", "rejected": "block", "pending": "report"}[state["approval"]]

    def route_after_recheck(state: ReleaseState) -> str:
        if not state["recheck"]["ok"]:
            return "block"
        return "submit" if authorize_submit else "ready"

    # ---------------------------------------------------------------- wiring
    graph = StateGraph(ReleaseState)
    graph.add_node("collect", collect)
    graph.add_node("triage", triage)
    graph.add_node("validate", validate)
    graph.add_node("human_approval", human_approval)
    graph.add_node("recheck", recheck)
    graph.add_node("ready", ready)
    graph.add_node("submit", submit)
    graph.add_node("verify", verify)
    graph.add_node("block", block)
    graph.add_node("report", report)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "triage")
    graph.add_edge("triage", "validate")
    graph.add_conditional_edges(
        "validate", route_after_validate, {"recheck": "recheck", "human_approval": "human_approval", "block": "block"}
    )
    graph.add_conditional_edges(
        "human_approval", route_after_approval, {"recheck": "recheck", "block": "block", "report": "report"}
    )
    graph.add_conditional_edges("recheck", route_after_recheck, {"submit": "submit", "ready": "ready", "block": "block"})
    graph.add_edge("submit", "verify")
    graph.add_edge("verify", "report")
    graph.add_edge("ready", "report")
    graph.add_edge("block", "report")
    graph.add_edge("report", END)
    return graph.compile()
