"""Evaluation harness: how well does the triage find the real failure evidence?

Input: a JSONL file where each line is one failed build:
  {"id": "...", "repo": "owner@name", "log": "<full log text>", "gold_lines": [12, 13, 14], ...}
gold_lines are the log lines that a human marked as "why the build failed" (e.g. from LogChunks).

Methods compared
  baseline - keyword/regex rules (cites the last matching lines)
  llm      - OpenAI triage; only citations verified against the log count

Metrics
  evidence hit rate  - share of logs where at least one cited line is inside the human-labelled chunk
  precision / recall - line-level overlap with the labelled chunk
  citation validity  - (LLM) share of cited lines that really match the log
No model is trained or tuned on the test split: repos are split deterministically into dev and test.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from pathlib import Path
from typing import Callable

from .analyzer import analyze_with_openai, baseline_triage

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = PROJECT_ROOT / "eval_data" / "sample_synthetic.jsonl"
EVAL_DIR = PROJECT_ROOT / "eval"


def split_of(repo: str, seed: str = "rg1") -> str:
    digest = hashlib.sha256((seed + repo).encode("utf-8")).hexdigest()
    return "dev" if int(digest[:8], 16) % 2 == 0 else "test"


def load_dataset(path: str | Path, split: str = "test", limit: int | None = None) -> list[dict]:
    p = SAMPLE_PATH if str(path) == "sample" else Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {p}")
    items = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    items = [i for i in items if i.get("gold_lines")]
    if split in ("dev", "test"):
        items = [i for i in items if split_of(i.get("repo", "")) == split]
    items.sort(key=lambda i: str(i.get("id")))
    return items[:limit] if limit else items


def score_item(pred_lines: list[int], gold_lines: list[int]) -> dict:
    pred, gold = set(pred_lines), set(gold_lines)
    overlap = pred & gold
    return {
        "hit": bool(overlap),
        "precision": len(overlap) / len(pred) if pred else 0.0,
        "recall": len(overlap) / len(gold) if gold else 0.0,
        "n_pred": len(pred),
    }


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 3) if values else 0.0


def run_method(items: list[dict], method: str, say: Callable[[str], None] = print) -> dict:
    per_item = []
    valid_total = cited_total = errors = 0
    latencies: list[float] = []
    prompt_tokens = completion_tokens = 0
    for index, item in enumerate(items, start=1):
        row = {"id": item["id"], "repo": item.get("repo")}
        pred: list[int] = []
        if method == "baseline":
            started = time.perf_counter()
            pred = [c["line"] for c in baseline_triage(item["log"])["cited_lines"]]
            latencies.append(time.perf_counter() - started)
        else:
            try:
                result = analyze_with_openai({"work_item": {}, "test_results": {}, "job_log": item["log"]})
                pred = [c["line"] for c in result["cited_lines"]]
                valid = len(result["cited_lines"])
                invalid = len(result["unverified_citations"])
                valid_total += valid
                cited_total += valid + invalid
                usage = result.get("usage") or {}
                latencies.append(float(usage.get("latency_s") or 0))
                prompt_tokens += int(usage.get("prompt_tokens") or 0)
                completion_tokens += int(usage.get("completion_tokens") or 0)
                row["category"] = result.get("category")
            except Exception as exc:
                errors += 1
                row["error"] = f"{type(exc).__name__}: {exc}"[:200]
        row["pred_lines"] = sorted(set(pred))
        row.update(score_item(pred, item["gold_lines"]))
        per_item.append(row)
        if method == "llm" and index % 10 == 0:
            say(f"  ... {index}/{len(items)} logs done")

    scored = per_item
    summary = {
        "method": method,
        "n": len(scored),
        "evidence_hit_rate": _mean([1.0 if r["hit"] else 0.0 for r in scored]),
        "mean_precision": _mean([r["precision"] for r in scored]),
        "mean_recall": _mean([r["recall"] for r in scored]),
        "empty_rate": _mean([1.0 if r["n_pred"] == 0 else 0.0 for r in scored]),
        "avg_lines_cited": _mean([float(r["n_pred"]) for r in scored]),
        "mean_latency_s": _mean(latencies),
        "errors": errors,
    }
    if method == "llm":
        summary["citation_validity"] = round(valid_total / cited_total, 3) if cited_total else None
        summary["prompt_tokens"] = prompt_tokens
        summary["completion_tokens"] = completion_tokens
    return {"summary": summary, "items": per_item}


def render_markdown(dataset: str, split: str, synthetic: bool, results: list[dict]) -> str:
    lines = [f"# ReleaseGuard evaluation - dataset `{dataset}`, split `{split}`", ""]
    if synthetic:
        lines += ["> **SYNTHETIC SAMPLE. This is a smoke test, not a result. Do not report these numbers.**", ""]
    names = [r["summary"]["method"] for r in results]
    header = "| Metric | " + " | ".join(names) + " |"
    lines += [header, "|---|" + "---|" * len(names)]
    rows = [
        ("Logs evaluated", "n"),
        ("Evidence hit rate", "evidence_hit_rate"),
        ("Mean line precision", "mean_precision"),
        ("Mean line recall", "mean_recall"),
        ("Empty answers", "empty_rate"),
        ("Avg lines cited", "avg_lines_cited"),
        ("Mean latency (s)", "mean_latency_s"),
        ("Errors", "errors"),
        ("Citation validity", "citation_validity"),
        ("Prompt tokens", "prompt_tokens"),
        ("Completion tokens", "completion_tokens"),
    ]
    for label, key in rows:
        values = [r["summary"].get(key) for r in results]
        if all(v is None for v in values):
            continue
        lines.append(f"| {label} | " + " | ".join("-" if v is None else str(v) for v in values) + " |")
    lines += ["", "Evidence hit rate: share of logs where at least one cited line falls inside the human-labelled failure chunk."]
    return "\n".join(lines) + "\n"


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "not", "are", "was", "has", "have", "you", "your", "can",
    "all", "out", "use", "run", "line", "file", "path", "usr", "bin", "tmp", "home", "travis", "build", "true", "false",
}


def diagnose(dataset: str, limit_misses: int = 40, out_dir: Path = EVAL_DIR, say: Callable[[str], None] = print) -> dict:
    """Why does the baseline miss? DEV split only - the test split is never inspected."""
    import re
    from collections import Counter

    items = load_dataset(dataset, "dev")
    if not items:
        raise ValueError("No labelled logs found in the dev split.")
    hits = misses = empty = 0
    gold_words: Counter = Counter()
    positions: list[float] = []
    rows: list[str] = []
    for item in items:
        log_lines = item["log"].split("\n")
        cited = [c["line"] for c in baseline_triage(item["log"])["cited_lines"]]
        gold = item["gold_lines"]
        positions.append(gold[0] / max(1, len(log_lines)))
        if set(cited) & set(gold):
            hits += 1
            continue
        misses += 1
        empty += 0 if cited else 1
        text = " | ".join(log_lines[g - 1].strip() for g in gold[:2] if 0 < g <= len(log_lines))
        for word in set(re.findall(r"[a-z][a-z_\-]{3,}", text.lower())) - STOPWORDS:
            gold_words[word] += 1
        rows.append(f"{item['id'][:34]:<35} gold L{gold[0]}-{gold[-1]} of {len(log_lines)} | cited {cited[:4] or '-'} | {text[:150]}")
    n = len(items)
    third = lambda lo, hi: sum(1 for p in positions if lo <= p < hi)
    report = [
        f"DEV split diagnosis: {n} logs, baseline hit {hits} ({hits / n:.3f}), missed {misses} (of which {empty} cited nothing)",
        f"Where the labelled failure sits in the log: first third {third(0, 1/3)}, middle {third(1/3, 2/3)}, last third {third(2/3, 1.01)}",
        "",
        "Most common words in the missed gold lines (count of logs):",
        ", ".join(f"{w}={c}" for w, c in gold_words.most_common(30)),
        "",
        f"First {min(limit_misses, len(rows))} misses (id | where the gold is | what the baseline cited | the gold text):",
        *rows[:limit_misses],
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "diagnose_dev.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    say("\n".join(report))
    say(f"\nSaved: {out_dir / 'diagnose_dev.txt'}")
    return {"n": n, "hits": hits, "misses": misses}


def _clip(text: str, width: int = 180) -> str:
    return text if len(text) <= width else text[:width] + "..."


def render_misses(items: list[dict], result: dict, count: int, per_repo: int = 2) -> str:
    """Markdown of `count` logs where the method missed the labelled chunk (for error analysis on DEV).
    At most `per_repo` per repository, so the sample is not dominated by one project."""
    by_id = {i["id"]: i for i in items}
    out = [f"# Misses for method `{result['summary']['method']}` (first {count})", ""]
    shown = 0
    seen_repos: dict[str, int] = {}
    for row in result["items"]:
        if row.get("hit") or row["id"] not in by_id:
            continue
        item = by_id[row["id"]]
        repo = str(item.get("repo"))
        if seen_repos.get(repo, 0) >= per_repo:
            continue
        seen_repos[repo] = seen_repos.get(repo, 0) + 1
        lines = item["log"].split("\n")
        out.append(f"## {row['id']}  (category {item.get('category')}, {len(lines)} lines)")
        out.append("Labelled failure lines:")
        for n in item["gold_lines"][:8]:
            out.append(f"  L{n}: {_clip(lines[n - 1]) if 0 < n <= len(lines) else ''}")
        out.append("Method cited:")
        for n in row.get("pred_lines", [])[:8]:
            out.append(f"  L{n}: {_clip(lines[n - 1]) if 0 < n <= len(lines) else ''}")
        if not row.get("pred_lines"):
            out.append("  (nothing)")
        out.append("")
        shown += 1
        if shown >= count:
            break
    return "\n".join(out) + "\n"


def run_eval(
    dataset: str,
    split: str = "test",
    limit: int | None = None,
    use_llm: bool = False,
    out_dir: Path = EVAL_DIR,
    say: Callable[[str], None] = print,
    dump_misses: int = 0,
) -> list[dict]:
    items = load_dataset(dataset, split, limit)
    if not items:
        raise ValueError("No labelled logs found for that dataset/split.")
    synthetic = any(i.get("synthetic") for i in items)
    methods = ["baseline"]
    if use_llm:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("--llm needs OPENAI_API_KEY (put it in your .env file).")
        methods.append("llm")
    if synthetic:
        say("WARNING: synthetic sample data - smoke test only, not a result.")
    say(f"Evaluating {len(items)} logs (split={split}) with: {', '.join(methods)}")
    if use_llm:
        say(f"This makes {len(items)} OpenAI calls and costs tokens. Check usage afterwards.")
    results = [run_method(items, m, say) for m in methods]

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"results_{Path(str(dataset)).stem}_{split}"
    (out_dir / f"{stem}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    markdown = render_markdown(str(dataset), split, synthetic, results)
    (out_dir / f"{stem}.md").write_text(markdown, encoding="utf-8")
    say("")
    say(markdown)
    say(f"Saved: {out_dir / (stem + '.md')} and .json")
    if dump_misses > 0:
        if split == "test":
            say("NOTE: looking at test-split misses and then tuning on them would leak the test set. Use --split dev for error analysis.")
        miss_path = out_dir / f"misses_{Path(str(dataset)).stem}_{split}.md"
        miss_path.write_text(render_misses(items, results[0], dump_misses), encoding="utf-8")
        say(f"Saved baseline misses: {miss_path}")
    return results