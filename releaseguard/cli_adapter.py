"""Adapter around the Agentia CLI.

Two modes:
  * mock - reads evidence from mock_data/<scenario>/ (no Copado org needed)
  * real - runs the real `agentia` commands listed in agentia_commands.json

All methods return plain dicts so the rest of the app never cares which mode is used.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOCK_DIR = PROJECT_ROOT / "mock_data"
COMMANDS_FILE = PROJECT_ROOT / "agentia_commands.json"


class AdapterError(Exception):
    pass


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_tests(raw: Any) -> dict:
    """Turn whatever the CLI returned into a standard test-results dict.

    Unknown values stay None, so the policy engine can send the release to a human
    instead of guessing.
    """
    result = {
        "total": None,
        "passed": None,
        "failed": None,
        "skipped": None,
        "coverage_percent": None,
        "failures": [],
    }
    if isinstance(raw, dict) and "raw" not in raw:
        for key in result:
            if key in raw:
                result[key] = raw[key]
        return result

    text = raw.get("raw", "") if isinstance(raw, dict) else str(raw or "")
    m = re.search(r"(\d+)\s+(?:tests?\s+)?passed", text, re.I)
    if m:
        result["passed"] = int(m.group(1))
    m = re.search(r"(\d+)\s+(?:tests?\s+)?failed", text, re.I)
    if m:
        result["failed"] = int(m.group(1))
    m = re.search(r"coverage[^0-9]{0,20}(\d+(?:\.\d+)?)\s*%", text, re.I)
    if m:
        result["coverage_percent"] = float(m.group(1))
    if result["passed"] is not None and result["failed"] is not None:
        result["total"] = result["passed"] + result["failed"]
    return result


class AgentiaAdapter:
    def __init__(self, mode: str = "mock", scenario: str = "pass"):
        if mode not in ("mock", "real"):
            raise AdapterError(f"Unknown mode: {mode}")
        self.mode = mode
        self.scenario = scenario
        self._commands: dict | None = None
        if mode == "mock":
            self._scenario_dir = MOCK_DIR / scenario
            if not self._scenario_dir.is_dir():
                raise AdapterError(f"Unknown mock scenario '{scenario}' (looked in {MOCK_DIR})")

    # ------------------------------------------------------------------ helpers
    def _load_commands(self) -> dict:
        if self._commands is None:
            self._commands = _read_json(COMMANDS_FILE)
        return self._commands

    def _run(self, key: str, extra_arg: str | None = None) -> dict:
        cfg = self._load_commands()
        cmd = list(cfg[key])
        exe = shutil.which(cmd[0])
        if exe is None:
            raise AdapterError(
                "The 'agentia' command was not found on PATH. Install it with "
                "'npm install -g @copado/agentia-cli@beta' and authenticate, "
                "or use --mode mock."
            )
        cmd[0] = exe
        if extra_arg:
            cmd.append(extra_arg)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(cfg.get("timeout_seconds", 600)),
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(f"Command timed out: {' '.join(cmd)}") from exc
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        parsed: Any
        try:
            parsed = json.loads(out)
        except (json.JSONDecodeError, ValueError):
            parsed = {"raw": out}
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "command": " ".join(cmd),
            "data": parsed,
            "stderr": err,
        }

    # ------------------------------------------------------------------ evidence
    def get_work_item(self, work_id: str | None = None) -> dict:
        if self.mode == "mock":
            return _read_json(self._scenario_dir / "work_item.json")
        res = self._run("work_get", work_id)
        if not res["ok"]:
            raise AdapterError(f"work get failed: {res['stderr'] or res['data']}")
        data = res["data"] if isinstance(res["data"], dict) else {}
        data.setdefault("id", work_id or "unknown")
        data.setdefault("title", data.get("name", ""))
        data.setdefault("security_findings", {})
        return data

    def run_tests(self, work_id: str | None = None) -> dict:
        if self.mode == "mock":
            return normalize_tests(_read_json(self._scenario_dir / "test_results.json"))
        res = self._run("work_test", work_id)
        # A non-zero exit code usually means failing tests, which is still useful evidence.
        normalized = normalize_tests(res["data"])
        if not res["ok"] and normalized["failed"] is None:
            normalized["failed"] = 1
        return normalized

    def get_job_log(self, job_id: str | None = None) -> str:
        if self.mode == "mock":
            return _read_text(self._scenario_dir / "job_log.txt")
        if not job_id:
            return ""
        res = self._run("job_log_get", job_id)
        if not res["ok"]:
            return f"(could not fetch job log: {res['stderr']})"
        data = res["data"]
        return data["raw"] if isinstance(data, dict) and "raw" in data else json.dumps(data, indent=2)

    def get_preflight(self, path: str | None = None) -> dict | None:
        """Optional context exported by the ReleaseGuard Agentia plugin (see plugin/ folder)."""
        from .preflight import load_preflight

        if path:
            return load_preflight(path)
        if self.mode == "mock":
            candidate = self._scenario_dir / "preflight.json"
            if candidate.exists():
                return load_preflight(candidate)
        return None

    # ------------------------------------------------------------------ actions
    def submit(self, work_id: str | None = None) -> dict:
        """Submit for VALIDATION only. This never promotes or deploys to production."""
        if self.mode == "mock":
            return {
                "ok": True,
                "command": "agentia cicd work submit (mock)",
                "message": "Submitted for validation. Validation job started.",
            }
        res = self._run("work_submit", work_id)
        return {
            "ok": res["ok"],
            "command": res["command"],
            "message": res["stderr"] if not res["ok"] else "Submitted for validation.",
            "data": res["data"],
        }

    def status(self, work_id: str | None = None) -> dict:
        if self.mode == "mock":
            data = _read_json(self._scenario_dir / "validation_status.json")
            return {"ok": True, "command": "agentia cicd work status (mock)", **data}
        res = self._run("work_status", work_id)
        data = res["data"]
        text = data["raw"] if isinstance(data, dict) and "raw" in data else json.dumps(data)
        return {
            "ok": res["ok"],
            "command": res["command"],
            "status": "Success" if res["ok"] and re.search(r"success|succeeded|passed", text, re.I) else "Unknown",
            "message": text[:500],
        }
