from __future__ import annotations

# Canonical agent-facing skill, served at GET /SKILL.md by the deployed service and
# mirrored to the repository-root SKILL.md. A user bootstraps the whole flow with a
# single statement to their coding agent:
#
#   "Read https://token-badge.vercel.app/SKILL.md and follow the instructions to
#    publish my token usage and get my badge."
#
# The agent then follows the steps below against the host it fetched this file from.
# Everything runs locally with `ccusage` + `curl`; there is nothing to install from the
# service and no Python package to download.
SKILL_MARKDOWN = """\
# Token Badge — Agent Setup Skill

You are an AI coding agent (Claude Code or Codex). Follow these steps to publish the
user's subscription-agent token usage as a public Token Badge and show how they rank
against other AI adopters.

Everything runs locally with `ccusage` and `curl`. There is **nothing to install** from
this service — no Python package, no `uvx`, no clone. You already have a shell; just call
the HTTP API directly.

## 0. Base URL

Use the origin you fetched this file from as `TOKEN_BADGE_URL`. For example, if you read
`https://token-badge.vercel.app/SKILL.md`, then
`TOKEN_BADGE_URL=https://token-badge.vercel.app`.

## 1. Check prerequisites

Confirm each; if one is missing, tell the user how to install it and stop:

- `ccusage --version` — the local usage source. Install with `npm install -g ccusage`.
- `curl` and `jq` — to call the API and parse JSON.
- `gh auth status` — GitHub CLI, to identify the user (and, optionally, to place the
  badge on their profile later).

## 2. Pick the provider

Set `PROVIDER` to the agent you are:

- Codex → `codex`
- Claude Code → `claude`

If you cannot tell which agent is running, ask the user. Do not guess.

## 3. Identity

```bash
TOKEN_BADGE_URL="https://token-badge.vercel.app"   # the origin you fetched this file from
PROVIDER="claude"                                   # or "codex"
LOGIN=$(gh api /user --jq .login)
NODE_ID=$(gh api /user --jq .node_id)
COLLECTOR="github:$NODE_ID"
```

## 4. Collect usage locally

```bash
TOTAL=$(ccusage "$PROVIDER" monthly --json | jq '.totals.totalTokens // ([.monthly[].totalTokens] | add)')
echo "Total $PROVIDER tokens: $TOTAL"
```

## 5. Upload (the service computes the integrity hash — no client-side hashing)

```bash
NONCE=$(curl -s -X POST "$TOKEN_BADGE_URL/v1/challenges" \\
  -H 'content-type: application/json' \\
  -d "{\\"collector_installation_id\\":\\"$COLLECTOR\\",\\"github_login\\":\\"$LOGIN\\",\\"github_node_id\\":\\"$NODE_ID\\"}" \\
  | jq -r .challenge_nonce)

curl -s -X POST "$TOKEN_BADGE_URL/v1/usage-snapshots" \\
  -H 'content-type: application/json' \\
  -d "{\\"challenge_nonce\\":\\"$NONCE\\",\\"collector_installation_id\\":\\"$COLLECTOR\\",\\"github_login\\":\\"$LOGIN\\",\\"github_node_id\\":\\"$NODE_ID\\",\\"provider\\":\\"$PROVIDER\\",\\"usage_kind\\":\\"subscription\\",\\"trust_level\\":\\"local-self-reported\\",\\"source\\":\\"ccusage $PROVIDER monthly --json\\",\\"total_tokens\\":$TOTAL}"
```

The challenge metadata (`collector_installation_id`, `github_login`, `github_node_id`)
must match between the two calls.

## 6. Show the result

```bash
curl -s "$TOKEN_BADGE_URL/v1/badges/$LOGIN"     # earned tier + highest accepted total
curl -s "$TOKEN_BADGE_URL/v1/rankings/$LOGIN"   # percentile / early-adopter message
```

Report to the user in plain language:

- total consumption — `winning_total_tokens` (badge) / `total_tokens` (ranking)
- earned tier — `tier.name`, or "none yet"
- ranking line — `message` (either "one of the first 100 adopters" or "beat XX% of
  other AI adopters")
- public badge page — `$TOKEN_BADGE_URL/u/$LOGIN`

If the badge shows a higher total than you just uploaded, that is expected: Token Badge
keeps the highest accepted total across all of a profile's agents.

## 7. (Optional) Put it on their GitHub profile

Only if the user asks. Share the badge page and the markdown:

```markdown
[![Token Badge]($TOKEN_BADGE_URL/v1/badges/<login>.svg)]($TOKEN_BADGE_URL/u/<login>)
```

The most reliable placement is the profile **Website** field or a **social link**
pointing at `$TOKEN_BADGE_URL/u/<login>` (GitHub does not always render API-created
profile-README images). Ask before changing the user's public profile.
"""
