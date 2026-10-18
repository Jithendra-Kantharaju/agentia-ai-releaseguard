"""Command line interface.

Examples
  python -m releaseguard check --scenario pass
  python -m releaseguard check --scenario review --reviewer alice
  python -m releaseguard check --scenario pass --authorize-submit
  python -m releaseguard gate --scenario fail             # non-interactive, exit code for quality gates
  python -m releaseguard demo
  python -m releaseguard history
  python -m releaseguard verify-audit
  python -m releaseguard eval --dataset sample
  python -m releaseguard eval --dataset data/logchunks.jsonl --split test --llm --limit 100
  python -m releaseguard check --mode real --work-id US-0000001 --preflight preflight.json

Exit codes: 0 = passed / ready / validated, 1 = blocked or failed, 2 = human review still required.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

from . import audit
from .cli_adapter import AdapterError, AgentiaAdapter
from .graph import build_graph
from .policy_engine import load_policies
from .preflight import PreflightError

load_dotenv()

LINE = "=" * 64
DEMO_SCENARIOS = ("pass", "review", "fail", "injection", "fixed")


def exit_code_for(state: dict) -> int:
    status = state.get("final_status")
    if status in ("VALIDATED", "READY_FOR_VALIDATION"):
        return 0
    if status == "REVIEW_REQUIRED":
        return 2
    return 1


def run_check(
    args: argparse.Namespace,
    approval: str | None = None,
    scenario: str | None = None,
    authorize: bool | None = None,
    label: str = "check",
) -> dict:
    use_scenario = scenario or args.scenario
    adapter = AgentiaAdapter(mode=args.mode, scenario=use_scenario)
    policies = load_policies(args.policies)
    audit_dir = Path(args.audit_dir) if args.audit_dir else audit.AUDIT_DIR
    app = build_graph(
        adapter,
        policies,
        use_llm=not args.no_llm,
        approval_mode=approval or getattr(args, "approval", "prompt"),
        authorize_submit=getattr(args, "authorize_submit", False) if authorize is None else authorize,
        reviewer=args.reviewer,
        preflight_path=args.preflight,
        audit_dir=audit_dir,
    )
    run_id = "run-" + uuid.uuid4().hex[:8]
    print(LINE)
    print(f"ReleaseGuard {label}  run={run_id}  mode={args.mode}" + (f"  scenario={use_scenario}" if args.mode == "mock" else ""))
    print(LINE)
    state = app.invoke({"run_id": run_id, "mode": args.mode, "work_id": args.work_id, "job_id": args.job_id})
    print(LINE)
    print(f"RESULT: decision={state['decision']}  final_status={state['final_status']}")
    print(LINE)
    return state


def cmd_check(args: argparse.Namespace) -> int:
    return exit_code_for(run_check(args))


def cmd_gate(args: argparse.Namespace) -> int:
    """Non-interactive quality gate: never prompts, never submits. The exit code is the result."""
    return exit_code_for(run_check(args, approval="none", authorize=False, label="gate"))


def cmd_demo(args: argparse.Namespace) -> int:
    args.mode = "mock"
    args.preflight = None
    summary = []
    for scenario in DEMO_SCENARIOS:
        state = run_check(args, approval="approve", scenario=scenario, authorize=True, label="demo")
        summary.append((scenario, state["decision"], state["final_status"], (state.get("risk") or {}).get("score")))
        print()
    print("DEMO SUMMARY")
    print("-" * 62)
    print(f"{'scenario':<11}{'decision':<15}{'risk':<7}{'final status'}")
    for scenario, decision, final, risk in summary:
        print(f"{scenario:<11}{decision:<15}{str(risk):<7}{final}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    audit_dir = Path(args.audit_dir) if args.audit_dir else audit.AUDIT_DIR
    entries = audit.load_log(audit_dir)
    if not entries:
        print("No audit entries yet. Run: python -m releaseguard check --scenario pass")
        return 0
    print(f"{'run_id':<14}{'work item':<10}{'decision':<14}{'risk':<6}{'reviewer':<12}{'final status'}")
    print("-" * 74)
    for e in entries:
        record = e.get("approval_record") or {}
        reviewer = record.get("reviewer") or "-"
        risk = (e.get("risk") or {}).get("score", "-")
        print(f"{e['run_id']:<14}{str(e['work_id']):<10}{str(e['decision']):<14}{str(risk):<6}{str(reviewer)[:11]:<12}{e['final_status']}")
    result = audit.verify_chain(audit_dir)
    print("-" * 74)
    print(f"audit chain: {'OK' if result['ok'] else 'BROKEN'} ({result['message']}; {result['chained']} chained, {result['legacy']} legacy)")
    return 0


def cmd_verify_audit(args: argparse.Namespace) -> int:
    audit_dir = Path(args.audit_dir) if args.audit_dir else audit.AUDIT_DIR
    result = audit.verify_chain(audit_dir)
    print(f"{'OK' if result['ok'] else 'BROKEN'}: {result['message']}")
    print(f"entries={result['entries']} chained={result['chained']} legacy(unchained)={result['legacy']}")
    return 0 if result["ok"] else 1


def cmd_eval(args: argparse.Namespace) -> int:
    from .evaluate import run_eval

    try:
        run_eval(args.dataset, split=args.split, limit=args.limit, use_llm=args.llm, dump_misses=args.dump_misses)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    from .evaluate import diagnose

    try:
        diagnose(args.dataset, limit_misses=args.misses)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_inspect_logchunks(args: argparse.Namespace) -> int:
    from .logchunks import inspect_logchunks

    return 0 if inspect_logchunks(Path(args.src)) else 2


def cmd_prepare_logchunks(args: argparse.Namespace) -> int:
    from .logchunks import prepare_logchunks

    try:
        stats = prepare_logchunks(Path(args.src), Path(args.out), max_lines=args.max_lines)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if stats["written"] == 0:
        print("\nNothing was written. Run inspect-logchunks and send me the first XML snippet so I can match the format.")
        return 2
    print(f"\nWrote {stats['written']} labelled logs to {args.out}")
    print(f"Next: python -m releaseguard eval --dataset {args.out} --split test")
    return 0


def cmd_import_sf(args: argparse.Namespace) -> int:
    from .cli_adapter import MOCK_DIR
    from .sf_import import import_apex_json, parse_security

    out_dir = Path(args.out_dir) if args.out_dir else MOCK_DIR / args.name
    acceptance = [a.strip() for a in (args.acceptance or "").split(";") if a.strip()]
    try:
        result = import_apex_json(
            Path(args.apex_json), out_dir, args.work_id, args.title, parse_security(args.security), acceptance, args.job_id
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: could not import: {exc}", file=sys.stderr)
        return 2
    t = result["test_results"]
    print(f"Imported: {t['passed']} passed, {t['failed']} failed, coverage {t['coverage_percent']}%")
    if not args.security:
        print("Note: no --security values given, so the security rules (R4/R5) are not evaluated.")
    print(f"Scenario folder: {result['out_dir']}")
    print(f"Run it with: python -m releaseguard check --scenario {out_dir.name}")
    return 0


def cmd_replay_logchunks(args: argparse.Namespace) -> int:
    from .cli_adapter import MOCK_DIR
    from .replay import list_candidates, make_scenario

    try:
        if args.list:
            rows = list_candidates(args.dataset, "all", args.list)
            print(f"{'id':<46}{'language':<12}{'lines':<8}{'category'}")
            for r in rows:
                print(f"{r['id']:<46}{str(r['language']):<12}{r['lines']:<8}{r['category']}")
            print(f"\nPick one: python -m releaseguard replay-logchunks --dataset {args.dataset} --id \"<id>\" --name real_failure")
            return 0
        if not args.id or not args.name:
            print("ERROR: give --list N, or both --id and --name", file=sys.stderr)
            return 2
        out_dir = Path(args.out_dir) if args.out_dir else MOCK_DIR / args.name
        result = make_scenario(args.dataset, args.id, out_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Scenario written: {result['out_dir']}")
    print(f"Human-labelled failure lines (ground truth): {result['gold_lines'][:8]}")
    print(f"Run it with: python -m releaseguard gate --scenario {out_dir.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="releaseguard", description="Evidence-driven, policy-governed release safety")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--mode", choices=["mock", "real"], default="mock")
        p.add_argument("--scenario", default="pass", help="mock mode: pass, review, fail, injection, fixed, or an imported folder name")
        p.add_argument("--work-id", default=None)
        p.add_argument("--job-id", default=None)
        p.add_argument("--preflight", default=None, help="JSON from: agentia releaseguard preflight --json")
        p.add_argument("--reviewer", default=None, help="name recorded with a human approval (default: Copado user or OS user)")
        p.add_argument("--no-llm", action="store_true", help="skip OpenAI and use the offline analysis")
        p.add_argument("--policies", default=None, help="path to a policies.json file")
        p.add_argument("--audit-dir", default=None, help=argparse.SUPPRESS)

    check = sub.add_parser("check", help="run the release check workflow")
    add_common(check)
    check.add_argument("--approval", choices=["prompt", "approve", "reject"], default="prompt")
    check.add_argument("--authorize-submit", action="store_true", help="allow 'agentia cicd work submit' (validation only)")
    check.set_defaults(func=cmd_check)

    gate = sub.add_parser("gate", help="non-interactive quality gate; exit code 0 pass, 1 blocked, 2 review required")
    add_common(gate)
    gate.set_defaults(func=cmd_gate)

    demo = sub.add_parser("demo", help="run pass, review, fail, injection and fixed scenarios (mock mode)")
    add_common(demo)
    demo.set_defaults(func=cmd_demo)

    hist = sub.add_parser("history", help="show the audit log")
    hist.add_argument("--audit-dir", default=None, help=argparse.SUPPRESS)
    hist.set_defaults(func=cmd_history)

    ver = sub.add_parser("verify-audit", help="check that the audit log has not been tampered with")
    ver.add_argument("--audit-dir", default=None, help=argparse.SUPPRESS)
    ver.set_defaults(func=cmd_verify_audit)

    ev = sub.add_parser("eval", help="measure baseline vs LLM triage on labelled failure logs")
    ev.add_argument("--dataset", default="sample", help="'sample' or a JSONL file made by prepare-logchunks")
    ev.add_argument("--split", choices=["dev", "test", "all"], default="test")
    ev.add_argument("--limit", type=int, default=None)
    ev.add_argument("--dump-misses", type=int, default=0, help="write the first N baseline misses to eval/misses_*.md (use with --split dev)")
    ev.add_argument("--llm", action="store_true", help="also evaluate OpenAI (needs OPENAI_API_KEY; costs tokens)")
    ev.set_defaults(func=cmd_eval)

    dg = sub.add_parser("diagnose", help="why does the baseline miss? (dev split only)")
    dg.add_argument("--dataset", default="sample")
    dg.add_argument("--misses", type=int, default=40, help="how many missed logs to list")
    dg.set_defaults(func=cmd_diagnose)

    ins = sub.add_parser("inspect-logchunks", help="show the structure of an extracted LogChunks folder")
    ins.add_argument("--src", required=True)
    ins.set_defaults(func=cmd_inspect_logchunks)

    prep = sub.add_parser("prepare-logchunks", help="convert LogChunks into a JSONL evaluation file")
    prep.add_argument("--src", required=True, help="folder where LogChunks.zip was extracted")
    prep.add_argument("--out", default="data/logchunks.jsonl")
    prep.add_argument("--max-lines", type=int, default=20000, help="skip logs longer than this")
    prep.set_defaults(func=cmd_prepare_logchunks)

    rep = sub.add_parser("replay-logchunks", help="turn a real public CI failure into a scenario you can run through the gate")
    rep.add_argument("--dataset", default="data/logchunks.jsonl")
    rep.add_argument("--list", type=int, default=0, help="show N candidate logs (one per repository)")
    rep.add_argument("--id", default=None)
    rep.add_argument("--name", default=None, help="scenario folder name under mock_data/")
    rep.add_argument("--out-dir", default=None)
    rep.set_defaults(func=cmd_replay_logchunks)

    imp = sub.add_parser("import-sf", help="turn Salesforce CLI Apex test JSON into a scenario")
    imp.add_argument("--apex-json", required=True)
    imp.add_argument("--name", required=True, help="scenario folder name under mock_data/")
    imp.add_argument("--work-id", required=True)
    imp.add_argument("--title", required=True)
    imp.add_argument("--job-id", default=None)
    imp.add_argument("--security", default=None, help="e.g. critical=0,high=1,medium=2")
    imp.add_argument("--acceptance", default=None, help="acceptance criteria separated by ;")
    imp.add_argument("--out-dir", default=None)
    imp.set_defaults(func=cmd_import_sf)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # never crash on a log line the console cannot print
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (AdapterError, PreflightError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())