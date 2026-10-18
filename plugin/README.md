# ReleaseGuard plugin for Agentia CLI

`agentia releaseguard preflight` collects verified Copado context using only the supported plugin host API
(story, signed-in user, governance health check). It uses no credentials, no subprocesses, no files and no network.

The Python ReleaseGuard core reads its JSON output:

```
agentia releaseguard preflight --json > preflight.json
python -m releaseguard check --mode real --preflight preflight.json
```

## Build and link (needs Node 22.12 or newer and the Agentia CLI)

```
cd plugin
npm install
npm run build
agentia plugins link .
agentia releaseguard preflight
```

Why a plugin does not run the full check: the Agentia plugin SDK does not let plugins run `agentia` as a subprocess,
wrap built-in commands or read job logs (the host removes logs). So the plugin supplies verified context, and the
Python core does the log analysis, policy decision, approval and audit.

Status: compiles against `@copado/agentia-plugin-sdk` 0.1.x. It has NOT been run inside a live Agentia CLI session.
