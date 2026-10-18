"""Evidence snapshots and hashing.

Approvals are bound to the SHA-256 hash of the evidence that was reviewed. If the evidence changes
before submission, the approval is void and the release must be re-checked.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Fields of the work item that count as "the change under review". Volatile fields such as
# timestamps are deliberately left out so a harmless refresh does not void an approval.
STABLE_WORK_ITEM_KEYS = ("id", "title", "description", "acceptance_criteria", "components", "security_findings")

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def normalize_log(log: str | None) -> str:
    """One consistent line structure for hashing, analysis and evaluation."""
    return (log or "").replace("\r\n", "\n").replace("\r", "\n")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_work_item(work_item: dict | None) -> dict:
    work_item = work_item or {}
    return {k: work_item.get(k) for k in STABLE_WORK_ITEM_KEYS}


def evidence_hash(
    work_item: dict | None, test_results: dict | None, job_log: str | None,
    preflight: dict | None = None, policies: dict | None = None,
) -> str:
    snapshot = {
        "work_item": stable_work_item(work_item),
        "test_results": test_results or {},
        "job_log": normalize_log(job_log),
        "preflight": preflight or {},
        "policies": policies or {},
    }
    return sha256_text(canonical(snapshot))


def short(h: str | None, n: int = 12) -> str:
    return (h or "")[:n]
