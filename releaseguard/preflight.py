"""Reads the output of the ReleaseGuard Agentia plugin (`agentia releaseguard preflight --json`).

The plugin runs inside the Agentia CLI and can only use the supported host API, so everything in it is
already redacted by Copado: story details, the signed-in user and the governance health check.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "releaseguard.preflight/1"


class PreflightError(Exception):
    pass


def _find_payload(obj: Any, depth: int = 0) -> dict | None:
    """The CLI wraps results in an envelope ({"result": ...}). Search a few levels for our payload."""
    if depth > 4:
        return None
    if isinstance(obj, dict):
        if obj.get("schema") == SCHEMA:
            return obj
        for value in obj.values():
            found = _find_payload(value, depth + 1)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_payload(value, depth + 1)
            if found:
                return found
    return None


def _criteria_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if not value:
        return []
    items = []
    for line in str(value).splitlines():
        line = re.sub(r"^[\s\-\*•\d\.\)]+", "", line).strip()
        if line:
            items.append(line)
    return items


def normalize(payload: dict) -> dict:
    user = payload.get("user") or {}
    work = payload.get("workItem") or {}
    health = payload.get("orgHealth") or {}
    summary = health.get("summary") or {}
    return {
        "schema": SCHEMA,
        "generated_at": payload.get("generatedAt"),
        "user": {
            "id": user.get("id"),
            "name": user.get("fullName"),
            "username": user.get("username"),
        },
        "work_item": {
            "id": work.get("name") or work.get("id"),
            "title": work.get("title"),
            "status": work.get("status"),
            "project": work.get("projectName"),
            "acceptance_criteria": _criteria_list(work.get("acceptanceCriteria")),
        },
        "workspace": payload.get("workspace") or {},
        "org_health": {
            "fail": int(summary.get("fail", 0) or 0),
            "warn": int(summary.get("warn", 0) or 0),
            "pass": int(summary.get("pass", 0) or 0),
            "total": int(summary.get("total", 0) or 0),
            "failing": health.get("failing") or [],
        },
    }


def load_preflight(path: Path | str) -> dict:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise PreflightError(f"Preflight file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"Preflight file is not valid JSON: {path} ({exc})") from exc
    payload = _find_payload(raw)
    if payload is None:
        raise PreflightError(
            f"{path} does not contain a '{SCHEMA}' payload. Create it with: "
            "agentia releaseguard preflight --json > preflight.json"
        )
    return normalize(payload)


def merge_work_item(work_item: dict, preflight: dict | None) -> dict:
    """Fill gaps in the CLI work item from the plugin data. The CLI data always wins."""
    merged = dict(work_item or {})
    if not preflight:
        return merged
    pf = preflight.get("work_item") or {}
    if not merged.get("title") and pf.get("title"):
        merged["title"] = pf["title"]
    if not merged.get("acceptance_criteria") and pf.get("acceptance_criteria"):
        merged["acceptance_criteria"] = pf["acceptance_criteria"]
    if not merged.get("id") and pf.get("id"):
        merged["id"] = pf["id"]
    return merged


def default_reviewer(preflight: dict | None) -> str:
    """Prefer the verified Copado identity, then fall back to the operating-system user."""
    if preflight:
        user = preflight.get("user") or {}
        name = user.get("username") or user.get("name")
        if name:
            return str(name)
    try:
        import getpass

        return getpass.getuser()
    except Exception:  # pragma: no cover - extremely rare
        return "unknown"
