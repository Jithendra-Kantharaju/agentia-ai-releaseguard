#!/usr/bin/env bash
# Agentia local quality gate. Never choose a passing demo when unconfigured.
set -euo pipefail
mode="${RELEASEGUARD_MODE:-}"
args=()
case "$mode" in
  mock)
    if [[ -z "${RELEASEGUARD_SCENARIO:-}" ]]; then
      echo "REVIEW_REQUIRED: mock mode requires RELEASEGUARD_SCENARIO" >&2
      exit 2
    fi
    args=(--mode mock --scenario "$RELEASEGUARD_SCENARIO")
    ;;
  real)
    if [[ -z "${RELEASEGUARD_WORK_ID:-}" ]]; then
      echo "REVIEW_REQUIRED: real mode requires RELEASEGUARD_WORK_ID" >&2
      exit 2
    fi
    args=(--mode real --work-id "$RELEASEGUARD_WORK_ID")
    [[ -z "${RELEASEGUARD_JOB_ID:-}" ]] || args+=(--job-id "$RELEASEGUARD_JOB_ID")
    [[ -z "${RELEASEGUARD_PREFLIGHT:-}" ]] || args+=(--preflight "$RELEASEGUARD_PREFLIGHT")
    ;;
  *)
    echo "REVIEW_REQUIRED: explicitly set RELEASEGUARD_MODE=real or RELEASEGUARD_MODE=mock" >&2
    exit 2
    ;;
esac
[[ "${RELEASEGUARD_LLM:-0}" == 1 ]] || args+=(--no-llm)
exec "${PYTHON:-python3}" -m releaseguard gate "${args[@]}"
