#!/usr/bin/env python3
"""Generate animated SVG stat cards for the profile README (stdlib only).

Usage
  python scripts/generate_stats.py            # live data (needs GITHUB_TOKEN for GitHub cards)
  python scripts/generate_stats.py --offline  # empty placeholder cards
  python scripts/generate_stats.py --demo --out /tmp/demo   # sample data, for previewing

If a data source fails, its cards are left untouched so the workflow never breaks the README.
"""
import argparse
import html
import json
import os
import random
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

GH_USER = os.environ.get("GH_USER", "aryankr01")
LC_USER = os.environ.get("LC_USER", "4ryanks")
SANS = "'Segoe UI',Ubuntu,'Helvetica Neue',Arial,sans-serif"
PALETTE = ["#58a6ff", "#bc8cff", "#3fb950", "#ffa657", "#ff7b72", "#79c0ff"]

CSS = """
text{font-family:%s}
.t{font-size:15px;font-weight:600;fill:#e6edf3}
.u{font-size:12px;fill:#8b949e}
.n{font-size:25px;font-weight:700}
.l{font-size:12px;fill:#8b949e}
.s{font-size:11px;fill:#6e7681}
.a{animation:fade .8s ease-out both}
.g{transform-box:fill-box;transform-origin:left center;animation:grow 1.3s cubic-bezier(.2,.8,.2,1) both}
.ring{animation:ring 1.6s cubic-bezier(.2,.8,.2,1) both}
.dl{stroke-dasharray:1;animation:draw 2.6s ease-out both}
.bar{animation:sheen 4s ease-in-out infinite alternate}
@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes ring{from{stroke-dasharray:0 100}}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes sheen{from{opacity:.55}to{opacity:1}}
""" % SANS


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(n):
    n = int(n)
    return f"{n/1000:.1f}k" if n >= 10000 else f"{n:,}"


def short(d):
    dt = datetime.fromisoformat(d)
    return f"{dt.strftime('%b')} {dt.day}"


def card(w, h, title, tag, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img" aria-label="{esc(title)}">
<defs>
<clipPath id="c"><rect width="{w}" height="{h}" rx="14"/></clipPath>
<linearGradient id="ac" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#58a6ff"/><stop offset=".5" stop-color="#bc8cff"/><stop offset="1" stop-color="#3fb950"/></linearGradient>
<linearGradient id="lc" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffa116"/><stop offset="1" stop-color="#ff6a3d"/></linearGradient>
</defs>
<style>{CSS}</style>
<g clip-path="url(#c)">
<rect width="{w}" height="{h}" fill="#0d1117"/>
<rect width="{w}" height="3" fill="url(#ac)" class="bar"/>
<circle cx="{w-30}" cy="-20" r="110" fill="#58a6ff" fill-opacity=".06"/>
<circle cx="14" cy="22" r="4" fill="#58a6ff"><animate attributeName="opacity" values="1;.3;1" dur="2.4s" repeatCount="indefinite"/></circle>
<text class="t" x="28" y="27">{esc(title)}</text>
<text class="u" x="{w-20}" y="27" text-anchor="end">{esc(tag)}</text>
{body}
</g>
<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="14" stroke="#30363d"/>
</svg>"""


# ───────────────────────── data ─────────────────────────
def gh_graphql(token):
    q = """query($login:String!){user(login:$login){
      followers{totalCount}
      pullRequests{totalCount} issues{totalCount}
      repositories(ownerAffiliations:OWNER,isFork:false,first:100,privacy:PUBLIC){
        totalCount
        nodes{stargazerCount forkCount languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}
      contributionsCollection{totalCommitContributions
        contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"login": GH_USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]["user"]


def fetch_github(token):
    u = gh_graphql(token)
    repos = u["repositories"]["nodes"]
    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]
            cur = langs.setdefault(n["name"], [0, n["color"] or "#8b949e"])
            cur[0] += e["size"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return {
        "stars": sum(r["stargazerCount"] for r in repos),
        "forks": sum(r["forkCount"] for r in repos),
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "commits": u["contributionsCollection"]["totalCommitContributions"],
        "total": cal["totalContributions"],
        "days": days,
        "langs": sorted(([k, v[0], v[1]] for k, v in langs.items()), key=lambda x: -x[1]),
    }


def fetch_leetcode(user):
    q = """query u($u:String!){allQuestionsCount{difficulty count}
      matchedUser(username:$u){profile{ranking} submitStatsGlobal{acSubmissionNum{difficulty count}}}}"""
    req = urllib.request.Request(
        "https://leetcode.com/graphql",
        data=json.dumps({"query": q, "variables": {"u": user}}).encode(),
        headers={"Content-Type": "application/json", "Referer": "https://leetcode.com", "User-Agent": "Mozilla/5.0 (profile-readme)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)["data"]
    mu = data["matchedUser"]
    if not mu:
        raise RuntimeError("LeetCode user not found")
    solved = {x["difficulty"]: x["count"] for x in mu["submitStatsGlobal"]["acSubmissionNum"]}
    total = {x["difficulty"]: x["count"] for x in data["allQuestionsCount"]}
    return {"solved": solved, "total": total, "rank": mu["profile"]["ranking"]}


def empty_days():
    today = date.today()
    return [((today - timedelta(days=364 - i)).isoformat(), 0) for i in range(365)]


def empty_gh():
    return {"stars": 0, "forks": 0, "repos": 0, "followers": 0, "prs": 0, "issues": 0, "commits": 0,
            "total": 0, "days": empty_days(), "langs": []}


def empty_lc():
    return {"solved": {"All": 0, "Easy": 0, "Medium": 0, "Hard": 0},
            "total": {"All": 0, "Easy": 0, "Medium": 0, "Hard": 0}, "rank": 0}


def demo_gh():
    random.seed(7)
    days = [(d, max(0, int(random.gauss(2.2, 2.8))) if random.random() > .35 else 0) for d, _ in empty_days()]
    return {"stars": 42, "forks": 9, "repos": 18, "followers": 31, "prs": 27, "issues": 6, "commits": 612,
            "total": sum(c for _, c in days), "days": days,
            "langs": [["C++", 52000, "#f34b7d"], ["Python", 31000, "#3572A5"], ["Java", 18000, "#b07219"],
                      ["C", 9000, "#555555"], ["Jupyter Notebook", 6000, "#DA5B0B"], ["Kotlin", 3000, "#A97BFF"]]}


def demo_lc():
    return {"solved": {"All": 214, "Easy": 110, "Medium": 88, "Hard": 16},
            "total": {"All": 3500, "Easy": 880, "Medium": 1840, "Hard": 780}, "rank": 184532}


# ───────────────────────── streaks ─────────────────────────
def streaks(days):
    best, run, rs = (0, None, None), 0, None
    for d, c in days:
        if c > 0:
            if run == 0:
                rs = d
            run += 1
            if run > best[0]:
                best = (run, rs, d)
        else:
            run = 0
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1  # today may not have contributions yet
    end = days[i][0] if i >= 0 else None
    cur, start = 0, None
    while i >= 0 and days[i][1] > 0:
        cur, start, i = cur + 1, days[i][0], i - 1
    return cur, (start, end), best


# ───────────────────────── cards ─────────────────────────
def stats_card(g):
    tiles = [("Total Stars", g["stars"]), ("Commits (1y)", g["commits"]), ("Pull Requests", g["prs"]),
             ("Issues", g["issues"]), ("Public Repos", g["repos"]), ("Followers", g["followers"])]
    body = []
    for i, (label, val) in enumerate(tiles):
        x, y = 28 + (i % 2) * 208, 84 + (i // 2) * 44
        body.append(
            f'<g class="a" style="animation-delay:{.12*i:.2f}s">'
            f'<rect x="{x-10}" y="{y-26}" width="3" height="38" rx="1.5" fill="{PALETTE[i]}"/>'
            f'<text class="n" x="{x}" y="{y}" fill="{PALETTE[i]}">{fmt(val)}</text>'
            f'<text class="l" x="{x}" y="{y+16}">{label}</text></g>')
    return card(440, 210, "GitHub Stats", f"@{GH_USER}", "\n".join(body))


def streak_card(g):
    cur, cr, (lon, ls, le) = streaks(g["days"])
    pct = min(100, round(100 * cur / max(lon, 1)))
    rng = lambda a, b: f"{short(a)} – {short(b)}" if a and b else "no active streak"
    body = f"""
<line x1="147" y1="60" x2="147" y2="180" stroke="#21262d"/><line x1="293" y1="60" x2="293" y2="180" stroke="#21262d"/>
<g class="a"><text class="n" x="73" y="110" text-anchor="middle" fill="#58a6ff">{fmt(g['total'])}</text>
<text class="l" x="73" y="132" text-anchor="middle">Contributions</text><text class="s" x="73" y="150" text-anchor="middle">last 12 months</text></g>
<g class="a" style="animation-delay:.2s">
<circle cx="220" cy="105" r="36" stroke="#21262d" stroke-width="6"/>
<circle class="ring" cx="220" cy="105" r="36" stroke="url(#ac)" stroke-width="6" stroke-linecap="round" pathLength="100" stroke-dasharray="{pct} 100" transform="rotate(-90 220 105)"/>
<text class="n" x="220" y="114" text-anchor="middle" fill="#e6edf3">{cur}</text>
<text class="l" x="220" y="163" text-anchor="middle" fill="#e6edf3" style="fill:#e6edf3;font-weight:600">Current Streak</text>
<text class="s" x="220" y="181" text-anchor="middle">{rng(*cr)}</text></g>
<g class="a" style="animation-delay:.4s"><text class="n" x="367" y="110" text-anchor="middle" fill="#ffa657">{lon}</text>
<text class="l" x="367" y="132" text-anchor="middle">Longest Streak</text><text class="s" x="367" y="150" text-anchor="middle">{rng(ls, le)}</text></g>"""
    return card(440, 210, "Contribution Streak", f"@{GH_USER}", body)


def lang_card(g):
    langs = g["langs"][:6]
    total = sum(s for _, s, _ in langs) or 1
    if not langs:
        return card(440, 210, "Top Languages", f"@{GH_USER}",
                    '<text class="l" x="220" y="115" text-anchor="middle">Push some code and this fills up</text>')
    segs, x = [], 28.0
    for i, (n, s, c) in enumerate(langs):
        w = 384 * s / total
        segs.append(f'<rect class="g" x="{x:.1f}" y="52" width="{w:.1f}" height="10" fill="{c}" style="animation-delay:{.1*i:.1f}s"/>')
        x += w
    leg = []
    for i, (n, s, c) in enumerate(langs):
        lx, ly = 28 + (i % 2) * 200, 98 + (i // 2) * 36
        leg.append(f'<g class="a" style="animation-delay:{.15*i+.3:.2f}s"><circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{c}"/>'
                   f'<text class="t" x="{lx+18}" y="{ly}" style="font-size:13px">{esc(n)}</text>'
                   f'<text class="l" x="{lx+170}" y="{ly}" text-anchor="end">{100*s/total:.1f}%</text></g>')
    body = f'<clipPath id="b"><rect x="28" y="52" width="384" height="10" rx="5"/></clipPath><g clip-path="url(#b)">{"".join(segs)}</g>' + "".join(leg)
    return card(440, 210, "Top Languages", f"@{GH_USER}", body)


def leetcode_card(lc):
    S, T = lc["solved"], lc["total"]
    pct = min(100, round(100 * S["All"] / max(T["All"], 1), 1))
    rows = []
    for i, (name, col) in enumerate([("Easy", "#00b8a3"), ("Medium", "#ffc01e"), ("Hard", "#ef4743")]):
        y = 78 + i * 38
        w = 236 * S[name] / max(T[name], 1)
        rows.append(
            f'<g class="a" style="animation-delay:{.15*i+.2:.2f}s"><text class="t" x="176" y="{y}" style="font-size:13px;fill:{col}">{name}</text>'
            f'<text class="l" x="412" y="{y}" text-anchor="end"><tspan fill="#e6edf3" font-weight="600">{S[name]}</tspan> / {T[name]}</text>'
            f'<rect x="176" y="{y+8}" width="236" height="6" rx="3" fill="#21262d"/>'
            f'<rect class="g" x="176" y="{y+8}" width="{max(w, 0):.1f}" height="6" rx="3" fill="{col}" style="animation-delay:{.15*i+.3:.2f}s"/></g>')
    rank = f"Global rank #{lc['rank']:,}" if lc["rank"] else "Global rank —"
    body = f"""
<g class="a"><circle cx="90" cy="110" r="46" stroke="#21262d" stroke-width="8"/>
<circle class="ring" cx="90" cy="110" r="46" stroke="url(#lc)" stroke-width="8" stroke-linecap="round" pathLength="100" stroke-dasharray="{pct} 100" transform="rotate(-90 90 110)"/>
<text class="n" x="90" y="112" text-anchor="middle" fill="#e6edf3">{S['All']}</text>
<text class="l" x="90" y="129" text-anchor="middle">solved</text></g>
<text class="s" x="90" y="184" text-anchor="middle">{rank}</text>
{''.join(rows)}"""
    return card(440, 210, "LeetCode Progress", f"@{LC_USER}", body)


def smooth(pts, top, bot):
    cl = lambda v: min(max(v, top), bot)
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, cl(p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, cl(p2[1] - (p3[1] - p1[1]) / 6))
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def graph_card(g):
    days = g["days"]
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    sums = [sum(c for _, c in w) for w in weeks]
    x0, x1, top, bot = 50, 860, 78, 196
    mx = max(max(sums), 1)
    pts = [(x0 + (x1 - x0) * i / max(len(sums) - 1, 1), bot - (bot - top) * s / mx) for i, s in enumerate(sums)]
    line = smooth(pts, top, bot)
    area = f"{line} L{pts[-1][0]:.1f},{bot} L{pts[0][0]:.1f},{bot} Z"
    grid = "".join(
        f'<line x1="{x0}" x2="{x1}" y1="{y}" y2="{y}" stroke="#21262d" stroke-dasharray="3 5"/>'
        f'<text class="s" x="{x0-10}" y="{y+4}" text-anchor="end">{int(mx*f)}</text>'
        for f, y in [(1, top), (.5, (top + bot) / 2), (0, bot)])
    months, prev = "", None
    for i, w in enumerate(weeks):
        m = datetime.fromisoformat(w[0][0]).strftime("%b")
        if m != prev and i > 1:
            months += f'<text class="s" x="{pts[i][0]:.1f}" y="{bot+20}" text-anchor="middle">{m}</text>'
        prev = m
    peak = max(range(len(sums)), key=lambda i: sums[i])
    body = f"""
<defs><linearGradient id="af" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#58a6ff" stop-opacity=".35"/><stop offset="1" stop-color="#58a6ff" stop-opacity="0"/></linearGradient></defs>
{grid}{months}
<path d="{area}" fill="url(#af)" class="a" style="animation-delay:.6s"/>
<path class="dl" d="{line}" pathLength="1" stroke="url(#ac)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
<g class="a" style="animation-delay:1.8s"><circle cx="{pts[peak][0]:.1f}" cy="{pts[peak][1]:.1f}" r="4.5" fill="#0d1117" stroke="#ffa657" stroke-width="2"/>
<text class="s" x="{pts[peak][0]:.1f}" y="{pts[peak][1]-12:.1f}" text-anchor="middle" style="fill:#ffa657">peak week · {sums[peak]}</text></g>
<circle r="5" fill="#fff"><animateMotion dur="7s" repeatCount="indefinite" path="{line}"/></circle>
<circle r="11" fill="#58a6ff" fill-opacity=".25"><animateMotion dur="7s" repeatCount="indefinite" path="{line}"/></circle>"""
    return card(900, 232, "Contribution Activity", f"{fmt(g['total'])} contributions · last 12 months", body)



# ───────────────────────── theme conversion ─────────────────────────
DARK_TO_LIGHT = {
    "#0d1117": "#ffffff",
    "#161b22": "#f6f8fa",
    "#21262d": "#d0d7de",
    "#30363d": "#d8dee4",
    "#e6edf3": "#1f2328",
    "#c9d1d9": "#24292f",
    "#8b949e": "#656d76",
    "#6e7681": "#818a91",
    "#484f58": "#8c959f",
    "#fff": "#1f2328",
}

def light_variant(svg):
    # Keep accent colors intact while translating GitHub dark neutrals to light neutrals.
    out = svg
    for src, dst in DARK_TO_LIGHT.items():
        out = out.replace(src, dst)
    return out

# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "assets"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    gh = lc = None
    if a.demo:
        gh, lc = demo_gh(), demo_lc()
    elif a.offline:
        gh, lc = empty_gh(), empty_lc()
    else:
        try:
            gh = fetch_github(os.environ["GITHUB_TOKEN"])
        except Exception as e:  # keep old cards on failure
            print("GitHub fetch failed:", e)
        try:
            lc = fetch_leetcode(LC_USER)
        except Exception as e:
            print("LeetCode fetch failed:", e)
    if gh:
        for name, fn in [("github-stats", stats_card), ("streak", streak_card),
                         ("languages", lang_card), ("contributions", graph_card)]:
            svg = fn(gh)
            (out / f"{name}-dark.svg").write_text(svg, encoding="utf-8")
            (out / f"{name}-light.svg").write_text(light_variant(svg), encoding="utf-8")
    if lc:
        svg = leetcode_card(lc)
        (out / "leetcode-dark.svg").write_text(svg, encoding="utf-8")
        (out / "leetcode-light.svg").write_text(light_variant(svg), encoding="utf-8")
    print("wrote cards to", out)


if __name__ == "__main__":
    main()
