# Badge Model

## Provider Aggregation

Token Badge stores every accepted provider upload as its own `usage_snapshots` row.
If the same GitHub login uploads both Codex and Claude Code totals, both rows are kept.

The public badge grant is derived from the highest accepted `total_tokens` for that
GitHub login across all supported providers:

```text
max(codex.total_tokens, claude.total_tokens, future_provider.total_tokens)
```

The winning provider is retained on the grant so the public evidence remains
explainable.

## Table Roles

### `usage_challenges`

This table records one-time server-issued nonces. It exists so a collector cannot submit
an old copied report without first asking the backend for a fresh challenge. When a
snapshot arrives, the backend checks that the `challenge_nonce` was issued, has not been
used, and has the same collector/GitHub identity metadata before marking it used.

### `usage_snapshots`

This table is the audit log. Each accepted provider upload creates one immutable-ish
snapshot row with minimal metadata: provider, GitHub identity fields, total tokens, trust
level, report hash, challenge nonce, source command, and summarized raw totals. This is
where both Codex and Claude Code usage are logged.

### `badge_grants`

This table is the profile-facing derived state. It points at the provider snapshot that
currently wins for a GitHub login. A lower future upload does not downgrade the grant; a
higher future upload from any accepted provider can replace it.

## Tier Ladder

The tier ladder intentionally uses sparse order-of-magnitude thresholds. That keeps each
promotion meaningful and avoids making the public badge feel like a frequent progress
counter.

| Threshold | Badge | Rationale |
| ---: | --- | --- |
| 100,000,000 | Hot AI Prospect | First serious, badge-worthy usage. |
| 1,000,000,000 | Wonder AI Kid | Billion-token usage, strong enough to feel rare. |
| 10,000,000,000 | Key AI Player | Heavy recurring user across subscription-agent workflows. |
| 100,000,000,000 | World-Class AI Player | Hall-of-fame level usage. |

The 100B tier is intentionally aspirational. It can remain sparse until real usage
distribution data proves that another tier is needed above it.

## GitHub Profile Association

The current association is not automatic GitHub profile mutation. The backend associates
uploads with the submitted `github_login` and publishes badge endpoints:

```text
GET /v1/badges/<github-login>
GET /v1/badges/<github-login>.svg
```

The profile owner adds the SVG endpoint to their profile README:

```markdown
[![Token Badge](https://token-badge.example.com/v1/badges/lucifinil.svg)](https://token-badge.example.com/v1/badges/lucifinil)
```

Later GitHub OAuth should replace the login-only association with a verified
`github_node_id` enrollment flow and optional GitHub App README updates.

## Visual Direction

The MVP serves a self-hosted SVG badge because it works directly in GitHub READMEs and
does not require a third-party badge service. The shape is intentionally compatible with
the Shields.io / Badgen convention: short label, status text, tier color, and linkable
target page.

Recommended visual options:

- Self-hosted SVG endpoint: best control, no external dependency, easiest to attach to
  profile evidence pages.
- Shields.io endpoint JSON: best if we want a very familiar open-source badge style.
- Badgen-style SVG: compact and visually clean, good fallback if we later split badge
  rendering into a tiny service.

Reference services:

- Shields.io: https://shields.io/docs/
- Shields endpoint badges: https://img.shields.io/endpoint
- Badgen: https://badgen.net/
