
"""LangGraph workflow for Agentia AI ReleaseGuard.

Workflow:
collect -> triage -> validate -> decision

PASS:
    recheck -> ready / submit -> verify -> report

NEEDS_REVIEW:
    human_approval -> recheck / block / report

FAIL:
    block -> report

Safety:
- AI explains risks; deterministic policies decide.
- Mock approval is never valid authorization in real mode.
- Evidence is re-fetched before submission.
- Changed evidence invalidates prior approval.
- Submission requires explicit authorization.
- Submission means validation, not production deployment.
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
from .preflight import (
    default_reviewer,
    merge_work_item,
)


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


def _event(
    state: ReleaseState,
    step: str,
    detail: str,
) -> list:
    return list(state.get("events", [])) + [
        {
            "time": audit.now_iso(),
            "step": step,
            "detail": detail,
        }
    ]


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
    """Build and compile the ReleaseGuard workflow.

    Approval modes:
        prompt  - interactive approval, mock mode only
        approve - simulated approval, mock mode only
        reject  - simulated rejection, mock mode only
        none    - non-interactive quality gate

    Real mode:
        An approval requiring human review remains pending
        until authenticated reviewer integration is available.
    """

    def tag(name: str) -> str:
        return f"[{name}]".ljust(11)

    # -------------------------------------------------
    # 1. Collect evidence
    # -------------------------------------------------

    def collect(state: ReleaseState) -> dict:
        preflight = adapter.get_preflight(
            preflight_path
        )

        work_item = merge_work_item(
            adapter.get_work_item(
                state.get("work_id")
            ),
            preflight,
        )

        work_id = (
            state.get("work_id")
            or work_item.get("id")
        )

        job_id = (
            state.get("job_id")
            or work_item.get("job_id")
            or work_item.get("jobId")
        )

        tests = adapter.run_tests(work_id)
        job_log = adapter.get_job_log(job_id)

        digest = evidence_hash(
            work_item,
            tests,
            job_log,
            preflight,
            policies,
        )

        say(
            f"{tag('collect')}"
            f"work item {work_item.get('id')} "
            f"- {work_item.get('title')}"
        )

        say(
            f"{' ' * 11}"
            f"tests: {tests.get('passed')} passed, "
            f"{tests.get('failed')} failed, "
            f"coverage {tests.get('coverage_percent')}%"
        )

        if preflight:
            health = preflight["org_health"]

            who = (
                preflight["user"].get("username")
                or preflight["user"].get("name")
            )

            say(
                f"{' ' * 11}"
                f"plugin preflight: user={who}, "
                f"governance checks failing={health['fail']}"
            )

        say(
            f"{' ' * 11}"
            f"evidence hash: {short(digest)}..."
        )

        return {
            "work_item": work_item,
            "work_id": work_id,
            "job_id": job_id,
            "test_results": tests,
            "job_log": job_log,
            "preflight": preflight,
            "evidence_hash": digest,
            "events": _event(
                state,
                "collect",
                f"Collected evidence for {work_id}; "
                f"hash {short(digest)}",
            ),
        }

    # -------------------------------------------------
    # 2. Analyze failures and risks
    # -------------------------------------------------

    def triage(state: ReleaseState) -> dict:
        evidence = {
            "work_item": state["work_item"],
            "test_results": state["test_results"],
            "job_log": state["job_log"],
        }

        result = analyze(
            evidence,
            use_llm=use_llm,
        )

        say(
            f"{tag('triage')}"
            f"source={result['source']} "
            f"category={result.get('category')} "
            f"confidence={result.get('confidence')} "
            f"risk={result['risk_level']}"
        )

        for c in (
            result.get("cited_lines") or []
        )[:3]:
            say(
                f"{' ' * 11}"
                f"L{c['line']}: {c['text'][:90]}"
            )

        if result.get("unverified_citations"):
            say(
                f"{' ' * 11}"
                f"rejected "
                f"{len(result['unverified_citations'])} "
                f"unverifiable AI citation(s)"
            )

        if result.get("note"):
            say(
                f"{' ' * 11}"
                f"note: {result['note']}"
            )

        return {
            "analysis": result,
            "events": _event(
                state,
                "triage",
                f"{result['source']}: "
                f"category {result.get('category')}, "
                f"risk {result['risk_level']}",
            ),
        }

    # -------------------------------------------------
    # 3. Deterministic policy validation
    # -------------------------------------------------

    def validate(state: ReleaseState) -> dict:
        violations = policy_engine.evaluate(
            policies,
            state["work_item"],
            state["test_results"],
            state["job_log"],
            state.get("analysis"),
            state.get("preflight"),
        )

        decision = policy_engine.decide(
            violations
        )

        risk = policy_engine.score(
            violations,
            policies,
        )

        say(
            f"{tag('policy')}"
            f"violations: {len(violations)} "
            f"risk score: {risk['score']} "
            f"({risk['level']})"
        )

        for v in violations:
            say(
                f"{' ' * 11}"
                f"- [{v['severity'].upper()}] "
                f"{v['rule_id']}: {v['message']}"
            )

        say(
            f"{tag('decide')}{decision}"
        )

        return {
            "violations": violations,
            "risk": risk,
            "decision": decision,
            "events": _event(
                state,
                "decide",
                f"Policy decision {decision}; "
                f"{len(violations)} violation(s); "
                f"risk {risk['score']}",
            ),
        }

    # -------------------------------------------------
    # 4. Human approval
    # -------------------------------------------------

    def human_approval(
        state: ReleaseState,
    ) -> dict:

        who = (
            reviewer
            or default_reviewer(
                state.get("preflight")
            )
        )

        digest = state["evidence_hash"]

        # CRITICAL SAFETY FIX:
        # In real mode, CLI approvals are not verified
        # user authorization. Never accept demo flags.

        if adapter.mode == "real":
            answer = "pending"

            say(
                f"{tag('approval')}"
                "real-mode human approval requires "
                "verified reviewer authorization; "
                "not configured"
            )

        elif approval_mode == "none":
            answer = "pending"

            say(
                f"{tag('approval')}"
                "human review required; "
                "no reviewer available (gate mode)"
            )

        elif approval_mode == "approve":
            answer = "approved"

            say(
                f"{tag('approval')}"
                f"(auto) approved as {who}"
            )

        elif approval_mode == "reject":
            answer = "rejected"

            say(
                f"{tag('approval')}"
                f"(auto) rejected as {who}"
            )

        else:
            say(
                f"{tag('approval')}"
                f"human review required "
                f"(reviewer: {who}, "
                f"evidence {short(digest)}...)"
            )

            reply = ask(
                f"{' ' * 11}"
                "Approve this exact evidence "
                "for validation? [y/N]: "
            ).strip().lower()

            answer = (
                "approved"
                if reply in ("y", "yes")
                else "rejected"
            )

        record = {
            "reviewer": who,
            "decision": answer,
            "evidence_hash": digest,
            "time": audit.now_iso(),
        }

        update: dict = {
            "approval": answer,
            "approval_record": record,
            "events": _event(
                state,
                "approval",
                f"{who} {answer} evidence "
                f"{short(digest)}",
            ),
        }

        if answer == "pending":
            update["final_status"] = (
                "REVIEW_REQUIRED"
            )

        return update

    # -------------------------------------------------
    # 5. Recheck evidence before submission
    # -------------------------------------------------

    def recheck(state: ReleaseState) -> dict:
        # Re-fetch all decision-relevant evidence.

        fresh_preflight = (
            adapter.get_preflight(
                preflight_path
            )
        )

        fresh_work = merge_work_item(
            adapter.get_work_item(
                state.get("work_id")
            ),
            fresh_preflight,
        )

        fresh_tests = adapter.run_tests(
            state.get("work_id")
        )

        fresh_log = adapter.get_job_log(
            state.get("job_id")
        )

        fresh_policies = (
            policy_engine.load_policies(
                policy_path
            )
            if policy_path
            else policies
        )

        fresh = evidence_hash(
            fresh_work,
            fresh_tests,
            fresh_log,
            fresh_preflight,
            fresh_policies,
        )

        fresh_violations = (
            policy_engine.evaluate(
                fresh_policies,
                fresh_work,
                fresh_tests,
                fresh_log,
                state.get("analysis"),
                fresh_preflight,
            )
        )

        fresh_decision = (
            policy_engine.decide(
                fresh_violations
            )
        )

        ok = (
            fresh == state["evidence_hash"]
            and fresh_decision == state["decision"]
        )

        record = {
            "ok": ok,
            "approved_hash": state["evidence_hash"],
            "current_hash": fresh,
            "fresh_decision": fresh_decision,
        }

        if ok:
            say(
                f"{tag('recheck')}"
                f"evidence unchanged "
                f"({short(fresh)}...)"
            )

        else:
            say(
                f"{tag('recheck')}"
                f"EVIDENCE CHANGED: "
                f"{short(state['evidence_hash'])}... "
                f"-> {short(fresh)}..."
            )

        return {
            "recheck": record,
            "events": _event(
                state,
                "recheck",
                (
                    "Evidence unchanged"
                    if ok
                    else (
                        "Evidence changed after analysis; "
                        "approval void"
                    )
                ),
            ),
        }

    # -------------------------------------------------
    # 6. Ready for validation
    # -------------------------------------------------

    def ready(state: ReleaseState) -> dict:
        say(
            f"{tag('submit')}"
            "not authorized "
            "(add --authorize-submit "
            "to submit for validation)"
        )

        return {
            "final_status": (
                "READY_FOR_VALIDATION"
            ),
            "events": _event(
                state,
                "ready",
                "Checks passed; "
                "submit not authorized",
            ),
        }

    # -------------------------------------------------
    # 7. Submit to Agentia
    # -------------------------------------------------

    def submit(state: ReleaseState) -> dict:
        say(
            f"{tag('submit')}"
            "agentia cicd work submit "
            "(validation only)..."
        )

        result = adapter.submit(
            state.get("work_id")
        )

        say(
            f"{' ' * 11}{result['message']}"
        )

        return {
            "submit_result": result,
            "events": _event(
                state,
                "submit",
                result["message"],
            ),
        }

    # -------------------------------------------------
    # 8. Verify validation job
    # -------------------------------------------------

    def verify(state: ReleaseState) -> dict:
        submit_result = (
            state.get("submit_result") or {}
        )

        if not submit_result.get("ok"):
            status = {
                "status": "Failed",
                "message": (
                    "Submission command failed"
                ),
            }

            final = "VALIDATION_FAILED"

        elif not submit_result.get("job_id"):
            status = {
                "status": "Unknown",
                "message": (
                    "No structured job ID "
                    "returned by Agentia CLI"
                ),
            }

            final = "VALIDATION_UNVERIFIED"

        else:
            expected_id = (
                submit_result["job_id"]
            )

            attempts = (
                1
                if adapter.mode == "mock"
                else 4
            )

            status = {
                "status": "Unknown",
                "message": "Not checked",
            }

            for attempt in range(attempts):
                status = adapter.status(
                    state.get("work_id"),
                    job_id=expected_id,
                )

                if (
                    status.get("status")
                    in ("Success", "Failed")
                    or not status.get("ok")
                ):
                    break

                if attempt < attempts - 1:
                    sleep(2)

            final = {
                "Success": "VALIDATED",
                "Failed": "VALIDATION_FAILED",
            }.get(
                status.get("status"),
                "VALIDATION_UNVERIFIED",
            )

            if not status.get("ok"):
                final = (
                    "VALIDATION_UNVERIFIED"
                )

        say(
            f"{tag('verify')}"
            f"status: {status.get('status')} "
            f"- {status.get('message')}"
        )

        return {
            "verify_result": status,
            "final_status": final,
            "events": _event(
                state,
                "verify",
                "Validation status: "
                f"{status.get('status')}",
            ),
        }

    # -------------------------------------------------
    # 9. Block unsafe release
    # -------------------------------------------------

    def block(state: ReleaseState) -> dict:
        reasons = [
            f"{v['rule_id']}: {v['message']}"
            for v in state.get(
                "violations",
                [],
            )
        ]

        record = (
            state.get("recheck") or {}
        )

        if record and not record.get("ok"):
            if (
                state.get("approval")
                == "approved"
            ):
                reasons.append(
                    "Evidence changed after "
                    "human approval, so "
                    "approval is void"
                )

            else:
                reasons.append(
                    "Evidence changed between "
                    "analysis and submission"
                )

        if state.get("approval") == "rejected":
            reasons.append(
                "Human reviewer rejected the release"
            )

        say(
            f"{tag('block')}"
            "release blocked, nothing submitted"
        )

        for reason in reasons:
            say(
                f"{' ' * 11}- {reason}"
            )

        cited = (
            (state.get("analysis") or {})
            .get("cited_lines")
            or []
        )

        if cited:
            say(
                f"{' ' * 11}evidence:"
            )

            for c in cited[:3]:
                say(
                    f"{' ' * 13}"
                    f"L{c['line']}: "
                    f"{c['text'][:90]}"
                )

        return {
            "block_reasons": reasons,
            "final_status": "BLOCKED",
            "events": _event(
                state,
                "block",
                "Release blocked; "
                f"{len(reasons)} reason(s) recorded",
            ),
        }

    # -------------------------------------------------
    # 10. Audit and reporting
    # -------------------------------------------------

    def report(state: ReleaseState) -> dict:
        events = _event(
            state,
            "report",
            "Final status "
            f"{state.get('final_status')}",
        )

        final_state = {
            **state,
            "events": events,
            "authorize_submit": (
                authorize_submit
            ),
        }

        report_path = audit.write_report(
            final_state,
            audit_dir,
        )

        audit.append_entry(
            audit.build_entry(
                final_state
            ),
            audit_dir,
        )

        say(
            f"{tag('report')}{report_path}"
        )

        return {
            "events": events,
            "report_path": str(
                report_path
            ),
        }

    # -------------------------------------------------
    # Routing
    # -------------------------------------------------

    def route_after_validate(
        state: ReleaseState,
    ) -> str:

        return {
            policy_engine.PASS: "recheck",
            policy_engine.NEEDS_REVIEW: (
                "human_approval"
            ),
            policy_engine.FAIL: "block",
        }[state["decision"]]

    def route_after_approval(
        state: ReleaseState,
    ) -> str:

        return {
            "approved": "recheck",
            "rejected": "block",
            "pending": "report",
        }[state["approval"]]

    def route_after_recheck(
        state: ReleaseState,
    ) -> str:

        if not state["recheck"]["ok"]:
            return "block"

        return (
            "submit"
            if authorize_submit
            else "ready"
        )

    # -------------------------------------------------
    # LangGraph wiring
    # -------------------------------------------------

    graph = StateGraph(ReleaseState)

    graph.add_node("collect", collect)
    graph.add_node("triage", triage)
    graph.add_node("validate", validate)
    graph.add_node(
        "human_approval",
        human_approval,
    )
    graph.add_node("recheck", recheck)
    graph.add_node("ready", ready)
    graph.add_node("submit", submit)
    graph.add_node("verify", verify)
    graph.add_node("block", block)
    graph.add_node("report", report)

    graph.set_entry_point("collect")

    graph.add_edge(
        "collect",
        "triage",
    )

    graph.add_edge(
        "triage",
        "validate",
    )

    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "recheck": "recheck",
            "human_approval": "human_approval",
            "block": "block",
        },
    )

    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "recheck": "recheck",
            "block": "block",
            "report": "report",
        },
    )

    graph.add_conditional_edges(
        "recheck",
        route_after_recheck,
        {
            "submit": "submit",
            "ready": "ready",
            "block": "block",
        },
    )

    graph.add_edge(
        "submit",
        "verify",
    )

    graph.add_edge(
        "verify",
        "report",
    )

    graph.add_edge(
        "ready",
        "report",
    )

    graph.add_edge(
        "block",
        "report",
    )

    graph.add_edge(
        "report",
        END,
    )

    return graph.compile()
