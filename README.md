# Token Badge

Token Badge grants public profile badges for subscription-based AI agent token usage.
The first provider target is Codex, using `ccusage codex monthly --json` as the local
usage source.

## First Scope

- Count subscription-based token consumption only.
- Start with Codex usage collected by `ccusage`.
- Bind usage to a GitHub identity before granting a badge.
- Keep provider-specific identity and usage evidence separate so the project can add
  Claude Code, Copilot, Gemini, and other agents later.

## Badge Tiers

| Threshold | Badge |
| ---: | --- |
| 100,000,000 tokens | Wonder Kid |
| 1,000,000,000 tokens | AI Smart Boy |
| 10,000,000,000 tokens | AI Power User |
| 100,000,000,000 tokens | Context Titan |

Tier names are configuration, not hard-coded product truth. The important invariant is
that a grant is based on the highest verified total crossing a threshold.

## MVP Flow

1. User signs in with GitHub. The service stores the GitHub `node_id`, not just the
   mutable login name.
2. Service issues a one-time collection challenge.
3. Local collector runs `ccusage codex monthly --json`, computes the total, attaches
   the challenge, and signs a usage snapshot with the user's collector key.
4. Service records the snapshot as Codex subscription usage.
5. Service grants the highest matching badge to the associated GitHub profile.

The first implementation is not provider-certified. It should label Codex `ccusage`
snapshots as `local-self-reported` until Codex exposes a server-side usage API or signed
export.

## Local Prototype

Run the Codex collector directly from the checkout:

```bash
PYTHONPATH=src python3 -m token_badge.cli codex --github <github-login> --json
```

List configured tiers:

```bash
PYTHONPATH=src python3 -m token_badge.cli tiers
```

## Repository Map

- `src/token_badge/`: small collector and tiering prototype.
- `docs/product-brief.md`: product framing and first user experience.
- `docs/data-model.md`: identity, usage, and badge grant model.
- `docs/trust-model.md`: anti-fooling model and its limits.
- `docs/roadmap.md`: build sequence from local prototype to badge service.
