# Trust Model

## Reality Check

`ccusage` is a strong starting point because it can read local Codex usage and produce a
structured total. It is not a fraud-proof source by itself. A motivated user can edit
local logs, wrap the `ccusage` binary, or submit fabricated JSON unless the service
adds controls.

The product should therefore display a trust level with every grant.

## Trust Levels

| Level | Meaning |
| --- | --- |
| `local-self-reported` | Local collector ran `ccusage` and submitted a total. Useful for MVP, easy to spoof. |
| `challenge-signed` | Server issued a nonce, the collector signed the report, and snapshots are monotonic. Harder to casually spoof. |
| `provider-verified` | Provider API or signed export confirms the total. Target level for serious leaderboard use. |

## Anti-Fooling Controls For MVP

- Use GitHub OAuth and store `github_node_id`, not only the typed login.
- Never accept manual token totals from the browser.
- Generate a local collector installation ID and keypair during enrollment.
- Require a fresh server challenge for every usage submission.
- Hash the canonicalized `ccusage` summary, nonce, collector ID, and GitHub login
  before submitting it.
- Sign the report hash once collector key management exists.
- Store hashes of accepted summaries so later submissions can be compared.
- Require totals to be monotonic unless the user explicitly starts a new provider
  identity.
- Flag large jumps, parser changes, and source-tool version changes for review.
- Show trust level on public badges.

These controls prevent casual copy/paste cheating. They do not defeat a user who fully
controls the local machine and wants to forge evidence.

## GitHub Profile Granting

There are two viable publication modes:

1. Badge URL: Token Badge hosts an SVG badge endpoint. User adds Markdown to their
   GitHub profile README.
2. GitHub app: user grants repository permission, and Token Badge updates the profile
   README or a badge gist on their behalf.

The first mode is safer for MVP because it avoids write access to GitHub repositories.

## Future Provider Verification

When a provider exposes server-side usage APIs or signed exports, store the provider
subject ID and signed receipt alongside the local collector identity. The badge grant
rule can stay the same; only the evidence trust level changes.
