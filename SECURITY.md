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
and rollout files. The panel keeps Codex, Antigravity model groups, and direct
Claude Code quotas separate. The optional Claude Code status-line bridge reads
JSON from stdin and saves only normalized quota percentages, reset times, and an
update timestamp in a private local file. It does not save session identifiers,
transcript paths, credentials, or unrelated status-line fields. Missing, stale,
or expired quotas are unavailable rather than assumed to be full.

The widget can send desktop notifications for approvals and low limits. The
optional lockscreen mode includes task titles and activity in resident
notifications; visibility depends on the desktop's privacy settings. Keep it
disabled if those details should not appear on the lockscreen. Screenshots and
debug logs may contain private task information or paths; review them before
sharing. The panel installer creates a user autostart entry only when explicitly
run.
