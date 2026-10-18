
"""Adapter for the Copado Agentia CLI.

Modes:
  mock - load local test scenarios
  real - execute configured Agentia CLI commands

All methods return normalized Python dictionaries.
"""

from __future__ import annotations

import json
import os
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
    """Normalize Agentia test results.

    Unknown values remain None rather than being guessed.
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

    text = (
        raw.get("raw", "")
        if isinstance(raw, dict)
        else str(raw or "")
    )

    m = re.search(
        r"(\d+)\s+(?:tests?\s+)?passed",
        text,
        re.I,
    )

    if m:
        result["passed"] = int(m.group(1))

    m = re.search(
        r"(\d+)\s+(?:tests?\s+)?failed",
        text,
        re.I,
    )

    if m:
        result["failed"] = int(m.group(1))

    m = re.search(
        r"coverage[^0-9]{0,20}(\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    )

    if m:
        result["coverage_percent"] = float(m.group(1))

    if (
        result["passed"] is not None
        and result["failed"] is not None
    ):
        result["total"] = (
            result["passed"] + result["failed"]
        )

    return result


class AgentiaAdapter:
    def __init__(
        self,
        mode: str = "mock",
        scenario: str = "pass",
    ):
        if mode not in ("mock", "real"):
            raise AdapterError(f"Unknown mode: {mode}")

        self.mode = mode
        self.scenario = scenario
        self._commands: dict | None = None

        if mode == "mock":
            self._scenario_dir = MOCK_DIR / scenario

            if not self._scenario_dir.is_dir():
                raise AdapterError(
                    f"Unknown mock scenario '{scenario}' "
                    f"(looked in {MOCK_DIR})"
                )

    # --------------------------------------------------
    # Command execution helpers
    # --------------------------------------------------

    def _load_commands(self) -> dict:
        if self._commands is None:
            self._commands = _read_json(COMMANDS_FILE)

        return self._commands

    def _run(
        self,
        key: str,
        extra_arg: str | None = None,
        extra_args: list[str] | None = None,
    ) -> dict:

        cfg = self._load_commands()
        cmd = list(cfg[key])

        exe = shutil.which(cmd[0])

        if exe is None:
            raise AdapterError(
                "The 'agentia' command was not found on PATH. "
                "Install and authenticate Agentia CLI, "
                "or use --mode mock."
            )

        cmd[0] = exe
        cmd.extend(extra_args or [])

        if extra_arg:
            cmd.append(extra_arg)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(
                    cfg.get("timeout_seconds", 600)
                ),
            )

        except subprocess.TimeoutExpired as exc:
            raise AdapterError(
                f"Command timed out: {' '.join(cmd)}"
            ) from exc

        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()

        try:
            parsed: Any = json.loads(out)

        except (json.JSONDecodeError, ValueError):
            parsed = {"raw": out}

        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "command": " ".join(cmd),
            "data": parsed,
            "stderr": err,
        }

    # --------------------------------------------------
    # Work-item evidence
    # --------------------------------------------------

    def get_work_item(
        self,
        work_id: str | None = None,
    ) -> dict:

        if self.mode == "mock":
            return _read_json(
                self._scenario_dir / "work_item.json"
            )

        res = self._run("work_get", work_id)

        if not res["ok"]:
            raise AdapterError(
                f"work get failed: "
                f"{res['stderr'] or res['data']}"
            )

        data = (
            res["data"]
            if isinstance(res["data"], dict)
            else {}
        )

        data.setdefault("id", work_id or "unknown")
        data.setdefault("title", data.get("name", ""))
        data.setdefault("security_findings", {})

        return data

    # --------------------------------------------------
    # Test results
    # --------------------------------------------------

    def run_tests(
        self,
        work_id: str | None = None,
    ) -> dict:

        if self.mode == "mock":
            return normalize_tests(
                _read_json(
                    self._scenario_dir / "test_results.json"
                )
            )

        # Do not invoke work test --local here.
        # It can invoke ReleaseGuard recursively.
        # Instead, use the configured Apex-test command.

        classes = os.getenv(
            "AGENTIA_APEX_TEST_CLASSES",
            "",
        ).strip()

        res = self._run(
            "work_test",
            None,
            (
                [f"--apex-test-classes={classes}"]
                if classes
                else None
            ),
        )

        normalized = normalize_tests(res["data"])

        # IMPORTANT:
        # Preserve command execution status independently
        # of individual test pass/fail counts.

        normalized["command_ok"] = bool(res["ok"])

        if not res["ok"]:
            normalized["execution_error"] = str(
                res.get("stderr")
                or "Test command exited nonzero"
            )[:500]

        return normalized

    # --------------------------------------------------
    # CI job logs
    # --------------------------------------------------

    def get_job_log(
        self,
        job_id: str | None = None,
    ) -> str:

        if self.mode == "mock":
            return _read_text(
                self._scenario_dir / "job_log.txt"
            )

        if not job_id:
            return ""

        res = self._run("job_log_get", job_id)

        if not res["ok"]:
            raise AdapterError(
                f"Job log unavailable: "
                f"{res['stderr'] or res['data']}"
            )

        data = res["data"]

        if isinstance(data, dict) and "raw" in data:
            return data["raw"]

        return json.dumps(data, indent=2)

    # --------------------------------------------------
    # Agentia plugin preflight
    # --------------------------------------------------

    def get_preflight(
        self,
        path: str | None = None,
    ) -> dict | None:

        from .preflight import load_preflight

        if path:
            return load_preflight(path)

        if self.mode == "mock":
            candidate = (
                self._scenario_dir / "preflight.json"
            )

            if candidate.exists():
                return load_preflight(candidate)

        return None

    # --------------------------------------------------
    # Structured job ID extraction
    # --------------------------------------------------

    @staticmethod
    def _job_id(payload: Any) -> str | None:

        if not isinstance(payload, dict):
            return None

        for key in (
            "job_id",
            "jobId",
            "validation_job_id",
            "validationJobId",
        ):
            val = payload.get(key)

            if (
                isinstance(val, (str, int))
                and str(val).strip()
            ):
                return str(val)

        for key in (
            "job",
            "validation",
            "result",
            "data",
        ):
            nested = payload.get(key)

            if isinstance(nested, dict):
                found = AgentiaAdapter._job_id(nested)

                if found:
                    return found

        return None

    # --------------------------------------------------
    # Structured job status extraction
    # --------------------------------------------------

    @staticmethod
    def _job_state(payload: Any) -> str:

        if not isinstance(payload, dict):
            return "Unknown"

        for key in (
            "status",
            "state",
            "job_status",
            "jobStatus",
        ):
            val = payload.get(key)

            if isinstance(val, str):
                normalized = val.strip().lower()

                if normalized in (
                    "success",
                    "succeeded",
                    "passed",
                ):
                    return "Success"

                if normalized in (
                    "failed",
                    "failure",
                    "error",
                    "cancelled",
                    "canceled",
                ):
                    return "Failed"

                if normalized in (
                    "pending",
                    "queued",
                    "running",
                    "in_progress",
                    "in progress",
                ):
                    return "Pending"

                return "Unknown"

        for key in (
            "job",
            "validation",
            "result",
            "data",
        ):
            nested = payload.get(key)

            if isinstance(nested, dict):
                return AgentiaAdapter._job_state(nested)

        return "Unknown"

    # --------------------------------------------------
    # Submit for validation
    # --------------------------------------------------

    def submit(
        self,
        work_id: str | None = None,
    ) -> dict:

        if self.mode == "mock":
            data = _read_json(
                self._scenario_dir
                / "validation_status.json"
            )

            return {
                "ok": True,
                "job_id": self._job_id(data),
                "command": (
                    "agentia cicd work submit (mock)"
                ),
                "message": (
                    "Mock submission for validation "
                    "(no cloud job executed)."
                ),
            }

        res = self._run(
            "work_submit",
            work_id,
        )

        job_id = self._job_id(res["data"])

        return {
            "ok": res["ok"],
            "job_id": job_id,
            "command": res["command"],
            "message": (
                res["stderr"]
                if not res["ok"]
                else (
                    "Submitted for validation; "
                    "job ID confirmed."
                    if job_id
                    else (
                        "CLI accepted submission but "
                        "returned no structured job ID. "
                        "Validation UNVERIFIED."
                    )
                )
            ),
            "data": res["data"],
        }

    # --------------------------------------------------
    # Verify the correct validation job
    # --------------------------------------------------

    def status(
        self,
        work_id: str | None = None,
        job_id: str | None = None,
    ) -> dict:

        if not job_id:
            return {
                "ok": False,
                "job_id": None,
                "status": "Unknown",
                "message": (
                    "No submission job ID to verify"
                ),
            }

        if self.mode == "mock":
            data = _read_json(
                self._scenario_dir
                / "validation_status.json"
            )

            seen = self._job_id(data)
            matched = seen == str(job_id)

            return {
                "ok": matched,
                "job_id": seen,
                "command": (
                    "agentia cicd work status (mock)"
                ),
                "status": (
                    self._job_state(data)
                    if matched
                    else "Unknown"
                ),
                "message": (
                    data.get(
                        "message",
                        "Mock job status",
                    )
                    if matched
                    else "Job ID mismatch"
                ),
            }

        res = self._run(
            "work_status",
            work_id,
        )

        data = res["data"]
        seen = self._job_id(data)

        matched = bool(
            seen and seen == str(job_id)
        )

        state = (
            self._job_state(data)
            if res["ok"] and matched
            else "Unknown"
        )

        return {
            "ok": res["ok"] and matched,
            "job_id": seen,
            "command": res["command"],
            "status": state,
            "message": (
                f"Verified job {seen}: {state}"
                if matched
                else (
                    "Unable to correlate validation "
                    f"status with submitted job {job_id}; "
                    f"reported={seen!r}"
                )
            ),
        }
