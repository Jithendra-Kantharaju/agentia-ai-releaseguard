#!/usr/bin/env bash
# ReleaseGuard as an Agentia local quality gate (macOS/Linux).
# Pick a scenario with: agentia cicd work test -e RELEASEGUARD_SCENARIO=fail
FLAGS="--no-llm"
[ "${RELEASEGUARD_LLM:-}" = "1" ] && FLAGS=""
exec "${PYTHON:-python3}" -m releaseguard gate --scenario "${RELEASEGUARD_SCENARIO:-pass}" $FLAGS