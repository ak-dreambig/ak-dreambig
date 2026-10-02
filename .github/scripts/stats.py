"""Generate assets/stats.svg from the public GitHub API.

Run locally:   GITHUB_TOKEN=$(gh auth token) python .github/scripts/stats.py
In Actions:    uses the built-in GITHUB_TOKEN (see .github/workflows/stats.yml)
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "ak-dreambig")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "stats.svg")

FONT = "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace"
LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Dart": "#00B4AB",
    "C++": "#f34b7d", "C": "#8a8a8a", "Java": "#b07219", "PHP": "#8892bf", "HTML": "#e34c26",
    "CSS": "#8b5cf6", "Assembly": "#9b7653", "Shell": "#89e051", "Jupyter Notebook": "#DA5B0B",
}
SKIP_LANGS = {"Jupyter Notebook"}  # notebooks dwarf real code by byte count


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"},
    )
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def ago(iso):
    d = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    if d < 1:
        return "today"
    if d < 14:
        return f"{d}d ago"
    if d < 60:
        return f"{d // 7}w ago"
    if d < 730:
        return f"{d // 30}mo ago"
    return f"{d // 365}y ago"


user = api(f"/users/{USER}")
repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed") if not r["fork"] and r["name"].lower() != USER.lower()]

langs = {}
for r in repos:
    try:
        for k, v in api(f"/repos/{USER}/{r['name']}/languages").items():
            if k in SKIP_LANGS:
                continue
            # Flutter generates C++/CMake/Swift/Kotlin platform scaffolding; count only the Dart code
            if r["language"] == "Dart" and k != "Dart":
                continue
            langs[k] = langs.get(k, 0) + v
    except Exception:
        pass


def contributions():
    """Public contributions in the last 12 months via GraphQL (needs a token)."""
    if not TOKEN:
        return None
    q = {"query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions}}}}", "variables": {"u": USER}}
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps(q).encode(),
                                 headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "profile-stats"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except Exception:
        return None


contrib = contributions()
total = sum(langs.values()) or 1
top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
recent = repos[:4]

W, H = 1000, 270
o = []
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="GitHub activity summary for {escape(USER)}">')
o.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#070b1a"/><stop offset="1" stop-color="#150f36"/></linearGradient>'
         '<clipPath id="bar"><rect x="330" y="86" width="330" height="12" rx="6"/></clipPath></defs>')
o.append(f'<rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/><rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="18" fill="none" stroke="#fff" stroke-opacity=".08"/>')

# column 1: numbers
o.append(f'<text x="32" y="46" font-family="{MONO}" font-size="11" fill="#8f93b8" letter-spacing="2.2">THE NUMBERS</text>')
numbers = [(len(repos), "public repositories")]
if contrib is not None:
    numbers.append((contrib, "contributions, last 12 months"))
numbers.append((user["followers"], "followers"))
for i, (num, label) in enumerate(numbers):
    y = 98 + i * 62
    o.append(f'<text x="32" y="{y}" font-family="{FONT}" font-size="40" font-weight="800" fill="#e7e8ff">{num}</text>')
    o.append(f'<text x="32" y="{y + 20}" font-family="{FONT}" font-size="13" fill="#8f93b8">{label}</text>')

# column 2: languages
o.append(f'<text x="330" y="46" font-family="{MONO}" font-size="11" fill="#8f93b8" letter-spacing="2.2">LANGUAGES BY CODE</text>')
o.append('<g clip-path="url(#bar)">')
x = 330.0
for name, b in top:
    w = 330 * b / sum(v for _, v in top)
    o.append(f'<rect x="{x:.1f}" y="86" width="{w + 0.5:.1f}" height="12" fill="{LANG_COLORS.get(name, "#8b7cff")}"/>')
    x += w
o.append('</g>')
for i, (name, b) in enumerate(top):
    col, row = i % 2, i // 2
    lx, ly = 330 + col * 170, 134 + row * 34
    o.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{LANG_COLORS.get(name, "#8b7cff")}"/>')
    o.append(f'<text x="{lx + 18}" y="{ly}" font-family="{FONT}" font-size="14" fill="#e7e8ff">{escape(name)}</text>')
    o.append(f'<text x="{lx + 150}" y="{ly}" font-family="{FONT}" font-size="13" fill="#8f93b8" text-anchor="end">{100 * b / total:.0f}%</text>')
o.append(f'<text x="330" y="246" font-family="{FONT}" font-size="11" fill="#6b6f93">Excludes notebooks. Public, non-fork repos. Updated {datetime.now(timezone.utc):%d %b %Y}.</text>')

# column 3: recent
o.append(f'<text x="710" y="46" font-family="{MONO}" font-size="11" fill="#8f93b8" letter-spacing="2.2">RECENTLY SHIPPED</text>')
for i, r in enumerate(recent):
    y = 90 + i * 44
    name = r["name"] if len(r["name"]) <= 24 else r["name"][:23] + "…"
    o.append(f'<circle cx="716" cy="{y - 5}" r="4" fill="#ffb86b"/>')
    o.append(f'<text x="730" y="{y}" font-family="{FONT}" font-size="14" font-weight="600" fill="#e7e8ff">{escape(name)}</text>')
    o.append(f'<text x="730" y="{y + 18}" font-family="{FONT}" font-size="12" fill="#8f93b8">pushed {ago(r["pushed_at"])}</text>')
o.append('</svg>')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf8") as f:
    f.write("\n".join(o))
print(f"wrote {os.path.normpath(OUT)}: {len(repos)} repos, contrib={contrib}, langs={[k for k, _ in top]}")
