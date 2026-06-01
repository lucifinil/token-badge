# Token Badge — Agent Setup Skill

You are an AI coding agent (Claude Code or Codex). Follow these steps to publish the
user's subscription-agent token usage as a public Token Badge and, only with the
user's consent, add the badge to their GitHub profile.

## 0. Base URL

Use the origin you fetched this file from as `TOKEN_BADGE_URL`. For example, if you
read `https://token-badge.vercel.app/SKILL.md`, then
`TOKEN_BADGE_URL=https://token-badge.vercel.app`.

## 1. Check prerequisites

Run and confirm each is available; if one is missing, tell the user how to install it
and stop:

- `node --version` and `ccusage --version` — the local usage source. If `ccusage` is
  missing, install it with `npm install -g ccusage`.
- `gh auth status` — an authenticated GitHub CLI (needed only if the user wants the
  profile badge).
- `uvx --version` (from `uv`) — runs the Token Badge collector package without a local
  repo checkout or direct `python3 -m ...` command.

## 2. Detect the provider

Set `TOKEN_BADGE_PROVIDER` from the agent currently running this skill:

- If you are Codex, use `codex`; the collector will run `ccusage codex monthly --json`.
- If you are Claude Code, use `claude`; the collector will run `ccusage claude monthly --json`.
- If you cannot confidently tell which agent is running, ask the user. Do not default
  to either provider.

## 3. Set collector identity

Set a stable collector ID for this GitHub account:

```bash
TOKEN_BADGE_COLLECTOR_ID="${TOKEN_BADGE_COLLECTOR_ID:-github:$(gh api /user --jq .node_id)}"
```

## 4. Collect, upload, and rank (report only)

Run the collector in report-only mode and show the user the result:

```bash
uvx --from git+https://github.com/lucifinil/token-badge token-badge start \
  --provider "$TOKEN_BADGE_PROVIDER" \
  --collector-id "$TOKEN_BADGE_COLLECTOR_ID" \
  --upload-url "$TOKEN_BADGE_URL" \
  --json
```

Parse the JSON and report to the user, in plain language:

- `total_tokens` / `profile_total_tokens` — the total used for the public badge and
  ranking. This is the highest accepted provider total for this GitHub profile across
  all uploaded agents.
- `current_provider_total_tokens` — the total from the provider run you just uploaded.
- `earned_badge` — the badge tier they have earned (or "none yet"), based on
  `profile_total_tokens`.
- `badge_tiers` — the public tiering standard.
- `public_profile_url` — the Token Badge landing page for this GitHub login.
- `profile_repository_url` — the special GitHub profile repository.
- `ranking.message` — either "you are one of the first 100 adopters" or
  "your consumption has beat XX% of other AI adopters".
- If `current_provider_total_tokens` differs from `profile_total_tokens`, explain that
  this is expected when the same GitHub profile has uploaded multiple agents. Do not
  call it a discrepancy: the badge and ranking intentionally use the highest accepted
  provider total.

## 5. Ask before touching GitHub

Ask the user: "Create your GitHub profile repository (if needed) and add the Token
Badge to it?"

- If they decline, stop. Nothing is written to GitHub; their usage stays recorded.
- If they accept, run the same command again with `--install-badge` instead of `--json`:

```bash
uvx --from git+https://github.com/lucifinil/token-badge token-badge start \
  --provider "$TOKEN_BADGE_PROVIDER" \
  --collector-id "$TOKEN_BADGE_COLLECTOR_ID" \
  --upload-url "$TOKEN_BADGE_URL" \
  --install-badge
```

This creates the special `<login>/<login>` profile repository when it does not exist
and installs the badge in its README. If the repository was newly created, tell the
user they may need to open the printed GitHub repository URL and click `Share to
Profile` in the UI before GitHub shows the README publicly.

## 6. Confirm

Tell the user all of the following:

- Their total token consumption.
- Their earned tier/badge and the tiering standard.
- Their public Token Badge landing page.
- Their special GitHub profile repository link and any `Share to Profile` action needed.
- The badge markdown, so they can reuse it anywhere:

```markdown
[![Token Badge]($TOKEN_BADGE_URL/v1/badges/<login>.svg)]($TOKEN_BADGE_URL/u/<login>)
Token Badge profile: [what this badge means]($TOKEN_BADGE_URL/u/<login>)
```
