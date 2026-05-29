# Data Model

## Core Objects

### `members`

Canonical public identity.

| Field | Notes |
| --- | --- |
| `id` | Internal stable UUID. |
| `github_node_id` | Immutable GitHub account identifier from OAuth. |
| `github_login` | Display login; mutable and refreshed from GitHub. |
| `created_at` | Enrollment timestamp. |

### `provider_identities`

Mapping between a member and a provider-specific collector identity.

| Field | Notes |
| --- | --- |
| `id` | Internal stable UUID. |
| `member_id` | Foreign key to `members.id`. |
| `provider` | `codex` first, later `claude_code`, `copilot`, etc. |
| `usage_kind` | `subscription` for the first scope. |
| `collector_installation_id` | Random local UUID generated during enrollment. |
| `collector_public_key` | Used to sign collection responses. |
| `verification_state` | `local-self-reported`, `challenge-signed`, or `provider-verified`. |
| `created_at` | Enrollment timestamp. |

For Codex v1, there may not be a stable official Codex user ID available through
`ccusage`. The reliable mapping is therefore:

`GitHub node_id <-> Token Badge member_id <-> collector_installation_id <-> usage snapshots`

If Codex later exposes an official account ID or signed usage export, add it as
`provider_subject_id` without replacing the internal member ID.

### `usage_snapshots`

One collected total at a point in time.

| Field | Notes |
| --- | --- |
| `id` | Internal stable UUID. |
| `member_id` | Foreign key to `members.id`. |
| `provider_identity_id` | Foreign key to `provider_identities.id`. |
| `provider` | `codex` first. |
| `usage_kind` | `subscription`. |
| `source_tool` | Example: `ccusage codex monthly --json`. |
| `total_tokens` | Normalized total used for badge tiering. |
| `raw_totals_json` | Minimal summary from `ccusage`, not full private logs. |
| `report_hash` | Hash of canonicalized raw summary and challenge metadata. |
| `challenge_nonce` | Server-issued nonce used for this collection. |
| `signature` | Collector signature over the report hash and nonce. |
| `trust_level` | Displayed with the badge evidence. |
| `collected_at` | Server receipt timestamp. |

### `badge_tiers`

Configurable threshold ladder.

| Field | Notes |
| --- | --- |
| `id` | Stable tier ID. |
| `scope` | `subscription_total`. |
| `threshold_tokens` | Integer threshold. |
| `name` | Badge label. |
| `sort_order` | Display and evaluation order. |
| `active` | Allows tier edits without deleting history. |

### `badge_grants`

Materialized badge state.

| Field | Notes |
| --- | --- |
| `id` | Internal stable UUID. |
| `member_id` | Foreign key to `members.id`. |
| `tier_id` | Highest tier granted at the time. |
| `usage_snapshot_id` | Evidence snapshot that crossed the threshold. |
| `trust_level` | Copied from the evidence snapshot. |
| `granted_at` | Timestamp. |

## Grant Rule

For each member and usage scope, find the maximum `total_tokens` from accepted
snapshots. Grant the highest active tier where:

```text
usage_snapshots.total_tokens >= badge_tiers.threshold_tokens
```

Do not downgrade badges automatically if a future provider parser changes. Instead,
record superseding grants or mark older evidence as disputed.

