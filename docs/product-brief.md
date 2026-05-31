# Product Brief

## Idea

Token Badge is a public badge system for people who use subscription-based AI
coding agents heavily. It starts with Codex because the local `ccusage` command can
produce Codex token usage totals today.

The badge is attached to a GitHub profile because GitHub is the natural public
identity for coding-agent usage.

## First User Experience

1. User opens Token Badge and signs in with GitHub.
2. Token Badge shows a one-line local collection command.
3. User runs the command on the machine where Codex usage is available.
4. The collector reads `ccusage codex monthly --json` or `ccusage claude monthly --json`.
5. Token Badge records the provider total and grants from the user's highest provider total.
6. Token Badge can install the dynamic badge link in the user's profile README through
   the connected local GitHub session.

## Initial Badge Ladder

| Threshold | Badge |
| ---: | --- |
| 100 million tokens | Hot AI Prospect |
| 1 billion tokens | Wonder AI Kid |
| 10 billion tokens | Key AI Player |
| 100 billion tokens | World-Class AI Player |

## Product Principles

- Count subscription usage first. Do not mix API billing, credits, or organization
  usage into the first product surface.
- Start with Codex, but keep the provider model generic.
- Do not accept hand-entered totals.
- Keep badge grants explainable: provider, total, timestamp, source, and trust level.
- Avoid overstating verification. A local `ccusage` report is useful, but it is not a
  provider-signed usage receipt.

## Non-Goals For The First Version

- Pricing or cost leaderboard.
- Team or organization badges.
- API token usage.
- Native GitHub achievement badges.
- Direct mutation of a user's GitHub profile without an authenticated GitHub session.
