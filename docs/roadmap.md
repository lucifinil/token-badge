# Roadmap

## Milestone 0: Local Codex Prototype

- Define badge thresholds.
- Run `ccusage codex monthly --json`.
- Normalize `totals.totalTokens`.
- Return the earned tier for a GitHub login hint.
- Label all evidence `local-self-reported`.

## Milestone 1: Enrolled Collector

- Add GitHub OAuth.
- Generate a member record using GitHub `node_id`.
- Generate local collector installation ID and keypair.
- Add server-issued nonce challenges.
- Accept signed Codex usage snapshots.

## Milestone 2: Badge Service

- Persist members, provider identities, snapshots, tiers, and grants.
- Serve public badge SVGs.
- Serve public evidence pages with provider, total, timestamp, and trust level.
- Add a private dashboard for refreshing usage.

## Milestone 3: GitHub Publication

- Add copyable profile README Markdown.
- Optionally add a GitHub app for profile README or gist updates.
- Refresh badge assets when a higher tier is granted.

## Milestone 4: Provider Expansion

- Add provider adapters behind the same `UsageSnapshot` contract.
- Keep subscription usage separate from API usage.
- Support provider-verified receipts when available.
- Add per-provider and combined-subscription badge scopes.

