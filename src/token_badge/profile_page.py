from __future__ import annotations

import html
from typing import Any

from token_badge.badges import TIER_COLORS

PUBLIC_ORIGIN = "https://token-badge.vercel.app"

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Token Badge — @{login}</title>
<style>
  :root {{ --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --accent:{accent}; --bg:#f6f8fa; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
    color:var(--fg); background:radial-gradient(1200px 600px at 50% -10%, #efe9ff 0%, var(--bg) 60%);
    min-height:100vh; display:flex; align-items:center; justify-content:center; padding:32px; }}
  .card {{ width:100%; max-width:520px; background:#fff; border:1px solid var(--line); border-radius:16px;
    box-shadow:0 12px 40px rgba(31,35,40,.08); padding:36px 36px 28px; text-align:center; }}
  .brand {{ font-size:13px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); font-weight:700; }}
  .badge-img {{ margin:22px 0 8px; }}
  .badge-img img {{ height:34px; }}
  .handle {{ font-size:20px; font-weight:700; margin:6px 0 2px; }}
  .handle a {{ color:var(--accent); text-decoration:none; }}
  .tier {{ font-size:30px; font-weight:800; margin:18px 0 2px; }}
  .total {{ color:var(--muted); font-size:15px; }}
  .total b {{ color:var(--fg); }}
  .pill {{ display:inline-block; margin:18px 0 4px; padding:8px 14px; border-radius:999px;
    background:#f3eeff; color:#6639ba; font-size:14px; font-weight:600; }}
  .progress {{ margin:22px 0 6px; }}
  .bar {{ height:10px; border-radius:999px; background:#eef1f4; overflow:hidden; }}
  .bar > span {{ display:block; height:100%; width:{progress_pct}%; background:linear-gradient(90deg,{accent},#a371f7); }}
  .next {{ font-size:13px; color:var(--muted); margin-top:8px; }}
  .cta {{ margin-top:26px; padding-top:22px; border-top:1px solid var(--line); text-align:left; }}
  .cta h3 {{ font-size:14px; margin:0 0 8px; }}
  .cta code {{ display:block; background:#f6f8fa; border:1px solid var(--line); border-radius:8px;
    padding:12px 14px; font-size:12.5px; color:#1f2328; white-space:pre-wrap; line-height:1.5; }}
  .profile-repo {{ margin-top:18px; padding-top:16px; border-top:1px solid var(--line);
    font-size:13px; color:var(--muted); text-align:left; line-height:1.45; }}
  .profile-repo a {{ color:var(--accent); font-weight:700; text-decoration:none; }}
  .foot {{ margin-top:18px; font-size:12px; color:var(--muted); }}
  .foot a {{ color:var(--muted); }}
</style>
</head>
<body>
  <div class="card">
    <div class="brand">Token Badge</div>
    <div class="badge-img">
      <img id="badge-img" src="{public_origin}/v1/badges/{login}.svg" alt="Token Badge: {tier_alt}">
    </div>
    <div class="handle"><a href="https://github.com/{login}">@{login}</a></div>
    <div class="tier">{tier_line}</div>
    <div class="total">{total_line}</div>
    <div class="pill">{message}</div>
    <div class="progress">
      <div class="bar"><span></span></div>
      <div class="next">{next_line}</div>
    </div>
    <div class="cta">
      <h3>Get your own badge</h3>
      <code id="cta">Read /SKILL.md and follow the instructions to install Token Badge to get data for token consumption and badge.</code>
    </div>
    <div class="profile-repo">
      Profile README repo:
      <a href="https://github.com/{login}/{login}">{login}/{login}</a>.
      This special GitHub repository controls the README that can appear on @{login}'s public profile.
    </div>
    <div class="foot">
      {trust} · <a id="raw-badge-link" href="{public_origin}/v1/badges/{login}">raw badge data</a>
    </div>
  </div>
  <script>
    const tokenBadgeOrigin = location.protocol === "file:" || location.origin === "null"
      ? "{public_origin}"
      : location.origin;
    document.getElementById("cta").textContent =
      "Read " + tokenBadgeOrigin + "/SKILL.md and follow the instructions to install Token Badge to get data for token consumption and badge.";
    document.getElementById("badge-img").src = tokenBadgeOrigin + "/v1/badges/{login}.svg";
    document.getElementById("raw-badge-link").href = tokenBadgeOrigin + "/v1/badges/{login}";
  </script>
</body>
</html>
"""


def _progress_pct(total_tokens: int, next_threshold: int | None) -> float:
    if not next_threshold:
        return 100.0
    return round(min(total_tokens / next_threshold * 100, 100.0), 1)


def render_profile_html(
    github_login: str,
    badge_summary: dict[str, Any],
    ranking: dict[str, Any],
) -> str:
    """Render the public, shareable badge page for one GitHub profile."""
    login = html.escape(github_login)
    earned = bool(badge_summary.get("earned"))
    total_tokens = int(ranking.get("total_tokens") or badge_summary.get("winning_total_tokens") or 0)
    message = html.escape(str(ranking.get("message") or ""))

    if earned:
        tier_name = str(badge_summary["tier"]["name"])
        accent = TIER_COLORS.get(tier_name, "#8250df")
        tier_line = f"🏅 {html.escape(tier_name)}"
        tier_alt = html.escape(tier_name)
        provider = html.escape(str(badge_summary.get("winning_provider") or "—"))
        total_line = f"<b>{total_tokens:,}</b> subscription-agent tokens · via {provider}"
        upcoming = badge_summary.get("next")
        if upcoming:
            next_threshold = int(upcoming["threshold"])
            remaining = int(upcoming.get("tokens_remaining") or max(next_threshold - total_tokens, 0))
            next_line = f"{remaining:,} tokens to {html.escape(str(upcoming['name']))}"
        else:
            next_threshold = None
            next_line = "Top tier reached 🏆"
    else:
        accent = "#6e7781"
        tier_line = "No badge yet"
        tier_alt = "No Badge Yet"
        total_line = f"<b>{total_tokens:,}</b> subscription-agent tokens so far"
        upcoming = badge_summary.get("next")
        next_threshold = int(upcoming["threshold"]) if upcoming else None
        next_line = (
            f"{int(upcoming['tokens_remaining']):,} tokens to {html.escape(str(upcoming['name']))}"
            if upcoming
            else ""
        )

    return _PAGE_TEMPLATE.format(
        login=login,
        accent=accent,
        tier_line=tier_line,
        tier_alt=tier_alt,
        total_line=total_line,
        message=message,
        public_origin=PUBLIC_ORIGIN,
        progress_pct=_progress_pct(total_tokens, next_threshold),
        next_line=next_line,
        trust=html.escape(str(badge_summary.get("trust_level") or "local-self-reported")),
    )
