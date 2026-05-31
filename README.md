# Token Badge

Token Badge grants public profile badges for subscription-based AI agent token usage.
The first provider target is Codex, using `ccusage codex monthly --json` as the local
usage source.

## Start From Your AI Agent

Token Badge is a deployed service. Users do not run anything by hand — they give their
coding agent (Claude Code or Codex) one statement:

> **"Read https://&lt;your-token-badge-host&gt;/SKILL.md and follow the instructions to
> install and configure Token Badge for Claude Code."**

The service serves agent-followable instructions at `GET /SKILL.md`. The agent reads
them, collects the user's usage locally via `ccusage`, uploads it, reports the badge
tier and percentile, and — only with the user's consent — adds the badge to their GitHub
profile. The canonical copy lives in [SKILL.md](SKILL.md).

## First Scope

- Count subscription-based token consumption only.
- Start with Codex usage collected by `ccusage`.
- Support Claude Code through the same local `ccusage` collection path.
- Bind usage to a GitHub identity before granting a badge.
- Keep provider-specific identity and usage evidence separate so the project can add
  Claude Code, Copilot, Gemini, and other agents later.

## Badge Tiers

| Threshold | Badge |
| ---: | --- |
| 100,000,000 tokens | Hot AI Prospect |
| 1,000,000,000 tokens | Wonder AI Kid |
| 10,000,000,000 tokens | Key AI Player |
| 100,000,000,000 tokens | World-Class AI Player |

Tier names salute the old Championship Manager / Football Manager player-role ladder.
The important invariant is that a public grant is based on the highest accepted
provider total for the linked GitHub profile.

## Consumption Percentile

Every upload is ranked against all other adopters who have uploaded, so a user sees
where their consumption lands in the community:

- While the project is still in its first 100 uploads, early adopters get a celebratory
  line instead of a noisy percentile:

  ```text
  Total consumption: 150,000,000 tokens (claude)
  Badge tier: Hot AI Prospect
  You're one of the first 100 AI adopters to upload — yay! Check back later for your percentile.
  ```

- Once more than 100 profiles have uploaded, the line becomes a percentile against
  everyone else:

  ```text
  Total consumption: 12,400,000,000 tokens (codex)
  Badge tier: Key AI Player
  Your consumption has beat 87% of other AI adopters.
  ```

The percentile counts the share of *other* adopters whose highest accepted total is
below yours. It is served from `GET /v1/rankings/<github-login>` and returned by the
`start` quickstart described below.

## Quickstart

`start` is the one-statement entry point. It uploads your usage, prints your total
consumption, badge tier, and percentile, then asks before touching your GitHub profile:

```bash
PYTHONPATH=src python3 -m token_badge.cli start \
  --provider claude \
  --collector-id <collector-installation-id> \
  --upload-url https://token-badge.example.com
```

If you answer yes at the prompt, `start` creates the special `<login>/<login>` profile
repository when it does not exist yet and installs the badge in its README. If you
answer no, nothing is written to GitHub — your usage is still recorded. Add `--json` to
get the summary without the prompt.

## MVP Flow

1. User signs in with GitHub. The service stores the GitHub `node_id`, not just the
   mutable login name.
2. Service issues a one-time collection challenge.
3. Local collector runs `ccusage codex monthly --json`, computes the total, attaches
   the challenge, and signs a usage snapshot with the user's collector key.
4. Service records the snapshot as Codex subscription usage.
5. Service grants the highest matching badge from the user's highest provider total and
   reports the user's consumption percentile against all other adopters.

The first implementation is not provider-certified. It should label Codex `ccusage`
snapshots as `local-self-reported` until Codex exposes a server-side usage API or signed
export.

## Local Prototype

Install local collector dependencies:

```bash
npm install -g ccusage
```

Current local collector dependencies are:

- Python 3.11 or newer.
- Node.js/npm for installing or upgrading `ccusage`.
- `ccusage` with Codex and Claude Code command support.

Check readiness before collecting usage:

```bash
PYTHONPATH=src python3 -m token_badge.cli doctor
```

Run the Codex collector directly from the checkout:

```bash
PYTHONPATH=src python3 -m token_badge.cli codex --github <github-login> --json
```

Run the Claude Code collector directly from the checkout:

```bash
PYTHONPATH=src python3 -m token_badge.cli claude --github <github-login> --json
```

Bind a Codex report to a server-issued collection challenge:

```bash
PYTHONPATH=src python3 -m token_badge.cli codex \
  --github <github-login> \
  --collector-id <collector-installation-id> \
  --challenge <server-nonce> \
  --json
```

To upload usage and immediately install or refresh the GitHub profile README badge,
add `--profile-badge`. The command uses the connected local GitHub account and defaults
the badge URL to `--upload-url` unless `TOKEN_BADGE_PUBLIC_URL` or `--badge-base-url` is
set:

```bash
PYTHONPATH=src python3 -m token_badge.cli codex \
  --github <github-login> \
  --collector-id <collector-installation-id> \
  --upload-url https://token-badge.example.com \
  --profile-badge
```

The same challenge-bound upload flow is available for Claude Code:

```bash
PYTHONPATH=src python3 -m token_badge.cli claude \
  --github <github-login> \
  --collector-id <collector-installation-id> \
  --challenge <server-nonce> \
  --json
```

List configured tiers:

```bash
PYTHONPATH=src python3 -m token_badge.cli tiers
```

Run tests:

```bash
PYTHONPATH=src python3 -m unittest
```

## Public Badge

The backend exposes a GitHub-profile-friendly SVG badge:

```markdown
[![Token Badge](https://token-badge.example.com/v1/badges/<github-login>.svg)](https://token-badge.example.com/v1/badges/<github-login>)
```

The JSON endpoint at `/v1/badges/<github-login>` explains which provider snapshot is
currently winning the badge.

Install or refresh the badge block in the authenticated user's GitHub profile README:

```bash
TOKEN_BADGE_PUBLIC_URL=https://token-badge.example.com \
  PYTHONPATH=src python3 -m token_badge.cli profile-badge
```

Use `--dry-run` to preview the README content first. The command uses the existing local
GitHub connection through `gh`; if that connection is missing or lacks access, proceed
with GitHub SSO/OAuth before retrying.

## Repository Map

- `src/token_badge/`: small collector and tiering prototype.
- `docs/product-brief.md`: product framing and first user experience.
- `docs/data-model.md`: identity, usage, and badge grant model.
- `docs/badge-model.md`: tier rationale, profile association, and badge visuals.
- `docs/deployment.md`: TiDB-backed upload API setup and metadata boundary.
- `docs/trust-model.md`: anti-fooling model and its limits.
- `docs/roadmap.md`: build sequence from local prototype to badge service.
