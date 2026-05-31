# Token Badge — Agent Setup Skill

You are an AI coding agent (Claude Code or Codex). Follow these steps to publish the
user's subscription-agent token usage as a public Token Badge and, only with the
user's consent, add the badge to their GitHub profile.

## 0. Base URL

Use the origin you fetched this file from as `TOKEN_BADGE_URL`. For example, if you
read `https://tokenbadge.ai/SKILL.md`, then `TOKEN_BADGE_URL=https://tokenbadge.ai`.

## 1. Check prerequisites

Run and confirm each is available; if one is missing, tell the user how to install it
and stop:

- `node --version` and `ccusage --version` — the local usage source. If `ccusage` is
  missing, install it with `npm install -g ccusage`.
- `gh auth status` — an authenticated GitHub CLI (needed only if the user wants the
  profile badge).
- `uvx --version` (from `uv`) or `pipx --version` — used to run the collector without a
  clone.

## 2. Ask which provider

Ask the user whether to measure `claude` (Claude Code) or `codex` usage. Default to
`claude` if they have no preference.

## 3. Collect, upload, and rank (report only)

Run the collector in report-only mode and show the user the result:

```bash
uvx --from git+https://github.com/lucifinil/token-badge token-badge start \
  --provider <provider> \
  --upload-url "$TOKEN_BADGE_URL" \
  --json
```

(If you use `pipx`, replace the `uvx --from git+... token-badge` prefix with
`pipx run --spec git+https://github.com/lucifinil/token-badge token-badge`.)

Parse the JSON and report to the user, in plain language:

- `total_tokens` — their total subscription-agent consumption.
- `earned_badge` — the badge tier they have earned (or "none yet").
- `ranking.message` — either "you are one of the first 100 adopters" or
  "your consumption has beat XX% of other AI adopters".

## 4. Ask before touching GitHub

Ask the user: "Create your GitHub profile repository (if needed) and add the Token
Badge to it?"

- If they decline, stop. Nothing is written to GitHub; their usage stays recorded.
- If they accept, run the same command again with `--install-badge` instead of `--json`:

```bash
uvx --from git+https://github.com/lucifinil/token-badge token-badge start \
  --provider <provider> \
  --upload-url "$TOKEN_BADGE_URL" \
  --install-badge
```

This creates the special `<login>/<login>` profile repository when it does not exist
and installs the badge in its README.

## 5. Confirm

Tell the user their badge tier and percentile, and show the badge markdown so they can
reuse it anywhere:

```markdown
[![Token Badge]($TOKEN_BADGE_URL/v1/badges/<login>.svg)]($TOKEN_BADGE_URL/v1/badges/<login>)
```
