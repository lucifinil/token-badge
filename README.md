# Token Badge

Token Badge grants public profile badges for subscription-based AI agent token usage.
The first provider target is Codex, using `ccusage codex monthly --json` as the local
usage source.

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
| 500,000,000 tokens | Wonder AI Kid |
| 1,000,000,000 tokens | Key AI Player |
| 10,000,000,000 tokens | World-Class AI Player |

Tier names salute the old Championship Manager / Football Manager player-role ladder.
The important invariant is that a public grant is based on the highest accepted
provider total for the linked GitHub profile.

## MVP Flow

1. User signs in with GitHub. The service stores the GitHub `node_id`, not just the
   mutable login name.
2. Service issues a one-time collection challenge.
3. Local collector runs `ccusage codex monthly --json`, computes the total, attaches
   the challenge, and signs a usage snapshot with the user's collector key.
4. Service records the snapshot as Codex subscription usage.
5. Service grants the highest matching badge from the user's highest provider total.

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

## Repository Map

- `src/token_badge/`: small collector and tiering prototype.
- `docs/product-brief.md`: product framing and first user experience.
- `docs/data-model.md`: identity, usage, and badge grant model.
- `docs/badge-model.md`: tier rationale, profile association, and badge visuals.
- `docs/deployment.md`: TiDB-backed upload API setup and metadata boundary.
- `docs/trust-model.md`: anti-fooling model and its limits.
- `docs/roadmap.md`: build sequence from local prototype to badge service.
