# Security policy

## Supported versions

Security fixes target the current `main` branch. Community preview releases
should be updated to the latest source; older snapshots are not maintained
separately.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/mehiel-victor/usage-limit/security/advisories/new).
Include affected versions, reproduction steps, impact, and a minimal example
with synthetic data. Never include tokens, credentials, or real task transcripts.
Please avoid public issues for undisclosed vulnerabilities. No response-time
guarantee is offered.

## Data handling

The widget invokes locally installed provider CLIs. Their authentication and
network behavior remain under those tools' control; the widget has no telemetry
or separate analytics service. Codex task status can read local thread metadata
and rollout files. The Claude bridge saves rate-limit fields and a timestamp
in the local state directory.

The Git view executes read-only commands against local repositories. It does
not fetch, push, merge, or check out branches. Screenshots and debug logs may
contain private task information or paths; review them before sharing.
