# Agentia AI ReleaseGuard v2

Evidence-driven, policy-governed release safety for Copado Agentia.
**The AI explains and escalates. Deterministic policy decides. A human approves, and the approval is bound to the exact evidence.**

```
Agentia plugin (TypeScript)  ->  Python core
agentia releaseguard         collect -> evidence SHA-256 -> triage (rules + OpenAI, citations verified)
  preflight --json           -> policy engine (policies.json, risk score) -> PASS / NEEDS_REVIEW / FAIL
                             -> human approval (reviewer + evidence hash) -> recheck -> optional submit (validation only)
                             -> verify -> hash-chained audit log + Markdown report
```

Design rules
- The AI can only raise risk (rule R8). It can never turn a failing release into a passing one.
- Missing evidence goes to a human, never to PASS.
- Log text is treated as data. A prompt injection inside a log cannot change the decision.
- Every AI citation is checked against the real log (line number + quote). Unverifiable citations are dropped.
- If the evidence changes after approval, the approval is void and the release is blocked.
- Nothing is submitted unless you pass `--authorize-submit`, and even then it is `work submit` (validation) only.

## Upgrading from v1 (you already have the project open)

1. Close VS Code terminals. Unzip `releaseguard_v2.zip` into a NEW folder (e.g. `releaseguard_v2`), open that folder in VS Code. Keep your v1 folder as a backup.
2. Copy your key: copy `.env` from the v1 folder into the v2 folder (or copy `.env.example` to `.env` and set `OPENAI_API_KEY`).
3. Old `audit/audit_log.json` files still work: old entries are shown as "legacy" and new ones are chained.

## Run it (Windows, VS Code, Git Bash)

```bash
python -m pip install -r requirements.txt
python -m pytest -q                       # expect: 97 passed
python -m releaseguard demo --no-llm      # five scenarios, no API key needed
```
Skip the venv if it caused trouble before. If you want one: `python -m venv .venv` then `source .venv/Scripts/activate` (Git Bash, not the .ps1 file).

Expected `demo` summary:
```
scenario   decision       risk   final status
pass       PASS           0      VALIDATED
review     NEEDS_REVIEW   8      VALIDATED
fail       FAIL           26     BLOCKED
injection  FAIL           19     BLOCKED
fixed      PASS           0      VALIDATED
```
(`review` is VALIDATED in the demo only because the demo auto-approves as a human and authorizes submit.)

## Everyday commands

| Command | What it does |
|---|---|
| `python -m releaseguard check --scenario pass` | Full workflow, readiness only (no submit) |
| `python -m releaseguard check --scenario review --reviewer alice` | Asks YOU to approve; records reviewer + evidence hash |
| `python -m releaseguard check --scenario pass --authorize-submit` | Allows `agentia cicd work submit` (validation) |
| `python -m releaseguard gate --scenario fail` | Non-interactive quality gate. Exit 0 ok, 1 blocked, 2 review required |
| `python -m releaseguard history` | Audit log + chain status |
| `python -m releaseguard verify-audit` | Detects edited/deleted audit entries |
| `python -m releaseguard eval --dataset sample` | Triage metrics on the synthetic sample (smoke test only) |

Add `--no-llm` to run offline. With `OPENAI_API_KEY` in `.env`, OpenAI triage runs and falls back to offline if the API fails.

Expected `check --scenario fail` (abridged):
```
[triage]   source=offline-baseline  category=test_failure  confidence=low  risk=high
           L5: [09:14:20] ERROR: ApprovalServiceTest.testBulkApproval - UNABLE_TO_LOCK_ROW
[policy]   violations: 7   risk score: 26 (high)
[decide]   FAIL
[block]    release blocked, nothing submitted
RESULT: decision=FAIL  final_status=BLOCKED
```

## Real-data evaluation (this is what makes the project credible)

Use the LogChunks dataset (real Travis CI failure logs, human-labelled failure chunk, CC BY 4.0, 24 MB).

```bash
# 1. Download LogChunks.zip from https://zenodo.org/records/3632351 in your browser, extract to data/logchunks_raw
python -m releaseguard inspect-logchunks --src data/logchunks_raw
python -m releaseguard prepare-logchunks --src data/logchunks_raw --out data/logchunks.jsonl
python -m releaseguard eval --dataset data/logchunks.jsonl --split test              # baseline only, free
python -m releaseguard eval --dataset data/logchunks.jsonl --split test --llm --limit 100   # costs tokens
```
The XML tag names were not verifiable from my environment, so the converter finds entries by structure. If `prepare-logchunks` shows `written: 0` or odd counts, paste the output of `inspect-logchunks` to me and I will adjust it. Repos are split into dev/test by hash; never tune on the test split. Report only numbers from real data, never from `sample`.

## Copado plugin (preflight)

`plugin/` is a TypeScript Agentia plugin: `agentia releaseguard preflight --json` emits verified Copado context (user, work item, workspace, org health checks). Build: `cd plugin && npm install && npm run build`, then link it with the Agentia CLI per the plugin SDK docs. Pass its JSON to Python with `--preflight preflight.json`. A failing governance health check forces human review (rule R9).
Plugins cannot run `agentia` themselves, which is why the Python core calls the CLI.

## Salesforce scenarios

```bash
sf apex run test --code-coverage --result-format json --wait 10 --output-dir test-results
python -m releaseguard import-sf --apex-json apex.json --name my_story --work-id US-0001 --title "My change" --security critical=0,high=1
python -m releaseguard check --scenario my_story
```

## Honest caveats

- `--mode real` command templates (`agentia_commands.json`) and the Apex JSON field names were written from documentation and memory, not tested against a live Copado org. Test them on your org and adjust.
- The LogChunks XML reader and the plugin against a real host are unverified for the same reason.
- `mock_data` and `eval_data/sample_synthetic.jsonl` are synthetic.
- The offline baseline is keyword-based; the eval shows how it compares with OpenAI on real logs.
