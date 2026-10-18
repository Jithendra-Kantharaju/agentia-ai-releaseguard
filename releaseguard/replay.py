"""Replays a REAL public CI failure (from the LogChunks dataset) through ReleaseGuard.

Without a Copado org there is no live user story to check, so this turns one of the 797 real failed Travis CI
builds into a scenario folder (mock_data/<name>/). The log is real; the work item around it is a stand-in, and no
test results are claimed (unknown evidence goes to a human). Source: LogChunks, Brandt et al., CC BY 4.0,
https://zenodo.org/records/3632351
"""

from __future__ import annotations

import json
from pathlib import Path

from .evaluate import load_dataset


def list_candidates(dataset: str, split: str = "all", count: int = 20) -> list[dict]:
    """One row per repository, so the list shows a variety of languages and failure types."""
    seen: set[str] = set()
    rows = []
    for item in load_dataset(dataset, split):
        repo = str(item.get("repo"))
        if repo in seen:
            continue
        seen.add(repo)
        rows.append(
            {"id": item["id"], "language": item.get("language"), "lines": item["log"].count("\n") + 1, "category": item.get("category")}
        )
        if len(rows) >= count:
            break
    return rows


def make_scenario(dataset: str, item_id: str, out_dir: Path) -> dict:
    match = [i for i in load_dataset(dataset, "all") if i["id"] == item_id]
    if not match:
        raise ValueError(f"No log with id '{item_id}'. List some with: replay-logchunks --dataset {dataset} --list 20")
    item = match[0]
    build = item["id"].split(":")[-1]
    repo = str(item.get("repo"))
    out_dir.mkdir(parents=True, exist_ok=True)
    job = f"CI-{build}"
    work_item = {
        "id": job,
        "job_id": job,
        "title": f"Replay of public CI failure: {repo} build {build}",
        "description": "A real failed Travis CI build from the LogChunks dataset (CC BY 4.0, Brandt et al.). "
        "The log is real; this work item is a stand-in. No test results are claimed.",
        "acceptance_criteria": [],
        "components": [],
        "security_findings": {},
    }
    test_results = {"total": None, "passed": None, "failed": None, "skipped": None, "coverage_percent": None, "failures": []}
    (out_dir / "work_item.json").write_text(json.dumps(work_item, indent=2), encoding="utf-8")
    (out_dir / "test_results.json").write_text(json.dumps(test_results, indent=2), encoding="utf-8")
    (out_dir / "job_log.txt").write_text(item["log"] + "\n", encoding="utf-8")
    (out_dir / "validation_status.json").write_text(
        json.dumps({"status": "Failed", "message": "Replayed public CI failure", "job_id": job}, indent=2), encoding="utf-8"
    )
    (out_dir / "replay_source.json").write_text(
        json.dumps(
            {"id": item["id"], "repo": repo, "language": item.get("language"), "category": item.get("category"),
             "human_labelled_failure_lines": item["gold_lines"], "source": "LogChunks, CC BY 4.0"},
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"work_item": work_item, "gold_lines": item["gold_lines"], "out_dir": str(out_dir)}