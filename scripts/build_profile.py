#!/usr/bin/env python3
"""Build a terminal-style GitHub profile for ZyuuDev.

The script refreshes public GitHub profile/repository/language data and the
public contribution calendar when run by GitHub Actions. It writes SVG cards
and an animated ASCII terminal GIF into assets/.
"""
from __future__ import annotations

import json
import math
import os
import random
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
USERNAME = "ZyuuDev"

# Screenshot-derived values are only a local preview fallback. The workflow
# replaces them with current public GitHub data when the API is reachable.
FALLBACK_STATS = {
    "public_repos": 25,
    "followers": 52,
    "following": 57,
    "stars": 27,
    "contributions": 419,
    "active_days": 110,
    "current_streak": 0,
    "best_streak": 22,
}
FALLBACK_LANGUAGES = {
    "JavaScript": 71,
    "Dart": 7,
    "PHP": 6,
    "CSS": 4,
    "Blade": 3,
    "Other": 9,
}

PROJECTS = [
    ("Sentinel-AI", "AI-assisted code analysis, retrieval and repair workflows", "https://github.com/ZyuuDev/Sentinel-AI", "A"),
    ("ZyuuBotz-V3", "WhatsApp automation platform and bot core", "https://github.com/ZyuuDev/ZyuuBotz-V3", "Z"),
    ("FIKSI-SasmitaLens", "IoT fruit-ripeness scanner using sound analysis + AI", "https://github.com/ZyuuDev/FIKSI-SasmitaLens", "S"),
    ("Finspire-JHIC-DB", "Financial-literacy learning platform for students", "https://github.com/ZyuuDev/Finspire-JHIC-DB", "F"),
    ("UKK_E-Teller_Bank_Mini_ArrasydNandaFairuz", "School mini-bank system with teller workflows and RBAC", "https://github.com/ZyuuDev/UKK_E-Teller_Bank_Mini_ArrasydNandaFairuz", "B"),
    ("Project_Taman_Bhinneka_UGM", "Interactive digital exhibition for Nusantara culture", "https://github.com/ZyuuDev/Project_Taman_Bhinneka_UGM", "N"),
]

COLORS = {
    "bg": "#0b0f12", "card": "#0e1319", "bar": "#151c24", "border": "#26313b",
    "text": "#d6dee6", "muted": "#74818d", "green": "#59d68b", "green2": "#2fa866",
    "blue": "#68a9ff", "cyan": "#67d5d0", "yellow": "#e7d35b", "red": "#ff6b62",
    "purple": "#b68cff", "track": "#313a45", "dim": "#3f4a55"
}


def github_json(url: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ZyuuDev-Profile-Builder"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def external_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "ZyuuDev-Profile-Builder"})
    with urllib.request.urlopen(req, timeout=18) as response:
        return json.loads(response.read().decode("utf-8"))


def load_live_data():
    stats = dict(FALLBACK_STATS)
    languages = dict(FALLBACK_LANGUAGES)
    days = []
    live = {"profile": False, "languages": False, "contributions": False}

    try:
        user = github_json(f"https://api.github.com/users/{USERNAME}")
        repos = []
        for page in range(1, 4):
            batch = github_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner&sort=updated")
            repos.extend(batch)
            if len(batch) < 100:
                break
        public_repos = [r for r in repos if not r.get("fork", False)]
        stars = sum(int(r.get("stargazers_count", 0) or 0) for r in public_repos)
        stats.update({
            "public_repos": int(user.get("public_repos", len(public_repos))),
            "followers": int(user.get("followers", 0)),
            "following": int(user.get("following", 0)),
            "stars": stars,
        })
        live["profile"] = True

        totals = {}
        for repo in public_repos:
            full_name = repo.get("full_name")
            if not full_name:
                continue
            try:
                lang_data = github_json(f"https://api.github.com/repos/{full_name}/languages")
                for lang, size in lang_data.items():
                    totals[lang] = totals.get(lang, 0) + int(size)
            except Exception:
                continue
        if totals:
            total_bytes = sum(totals.values())
            selected = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]
            calculated = {name: round(size * 100 / total_bytes) for name, size in selected}
            remainder = max(0, 100 - sum(calculated.values()))
            if remainder:
                calculated["Other"] = remainder
            languages = calculated
            live["languages"] = True
    except Exception as exc:
        print(f"GitHub profile refresh skipped: {exc}")

    try:
        contribution_data = external_json(f"https://github-contributions-api.jogruber.de/v4/{USERNAME}?y=last")
        all_days = contribution_data.get("contributions", [])
        cutoff = date.today() - timedelta(days=181)
        days = [d for d in all_days if date.fromisoformat(d.get("date", "2000-01-01")) >= cutoff]
        stats["contributions"] = sum(int(d.get("count", 0)) for d in days)
        active = [d for d in days if int(d.get("count", 0)) > 0]
        stats["active_days"] = len(active)
        # Current and best streak are calculated from recent calendar days.
        count_by_date = {d.get("date"): int(d.get("count", 0)) for d in days}
        today = date.today()
        streak = 0
        probe = today
        if count_by_date.get(probe.isoformat(), 0) == 0:
            probe -= timedelta(days=1)
        while count_by_date.get(probe.isoformat(), 0) > 0:
            streak += 1
            probe -= timedelta(days=1)
        best = run = 0
        for d in sorted(days, key=lambda x: x.get("date", "")):
            if int(d.get("count", 0)) > 0:
                run += 1
                best = max(best, run)
            else:
                run = 0
        stats["current_streak"] = streak
        stats["best_streak"] = best
        live["contributions"] = True
    except Exception as exc:
        print(f"Contribution refresh skipped: {exc}")

    return stats, languages, days, live


def svg_text(x, y, content, size=22, fill=None, weight="400", anchor="start"):
    fill = fill or COLORS["text"]
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="DejaVu Sans Mono, ui-monospace, monospace" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(content))}</text>')


def card_header(width, height, command):
    c = COLORS
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%%" height="100%%" rx="20" fill="%s" stroke="%s" stroke-width="2"/>' % (c["card"], c["border"]),
        '<rect x="1" y="1" width="%d" height="48" rx="19" fill="%s"/>' % (width-2, c["bar"]),
        '<rect x="1" y="29" width="%d" height="20" fill="%s"/>' % (width-2, c["bar"]),
        '<circle cx="28" cy="24" r="7" fill="#ff625a"/><circle cx="52" cy="24" r="7" fill="#f5c451"/><circle cx="76" cy="24" r="7" fill="#45c878"/>',
        svg_text(110, 31, command, 17, c["muted"]),
    ]
    return pieces


def make_projects_svg():
    width, height = 1200, 510
    c = COLORS
    p = card_header(width, height, "ls -la ~/projects --featured")
    p += [svg_text(44, 91, "drwxr-xr-x  projects/", 18, c["green"], "700")]
    start_y = 145
    row_h = 56
    for idx, (name, desc, url, letter) in enumerate(PROJECTS):
        y = start_y + idx * row_h
        if idx:
            p.append(f'<line x1="38" y1="{y-28}" x2="1160" y2="{y-28}" stroke="{c["border"]}" stroke-width="1"/>')
        accent = [c["yellow"], c["cyan"], c["blue"], c["green"], c["purple"], c["yellow"]][idx]
        p.append(f'<rect x="48" y="{y-19}" width="25" height="25" rx="5" fill="{accent}"/>')
        p.append(svg_text(60.5, y, letter, 15, c["bg"], "700", "middle"))
        label = name
        if len(label) > 38:
            label = label[:35] + "..."
        p.append(svg_text(91, y, label, 19, c["blue"], "700"))
        desc_short = desc if len(desc) < 70 else desc[:67] + "..."
        p.append(svg_text(565, y, desc_short, 15, c["muted"]))
        p.append(svg_text(1145, y, "↗", 20, c["green"], "700", "end"))
    p.append(svg_text(44, 485, "6 featured repositories  •  click the project links below", 14, c["muted"]))
    p.append('</svg>')
    (ASSETS / "projects.svg").write_text("\n".join(p), encoding="utf-8")


def make_languages_svg(languages, live):
    width, height = 1200, 380
    c = COLORS
    p = card_header(width, height, "cat languages.txt")
    p.append(svg_text(46, 88, "LANGUAGE DISTRIBUTION  /  PUBLIC REPOSITORIES", 15, c["muted"], "700"))
    if not live.get("languages"):
        p.append(svg_text(1145, 88, "PREVIEW DATA", 14, c["yellow"], "700", "end"))
    items = (sorted(languages.items(), key=lambda x: x[1], reverse=True)[:6] if live.get("languages") else list(languages.items())[:5])
    palette = [c["yellow"], c["cyan"], c["blue"], c["purple"], c["red"], c["green"]]
    max_bar = 760
    start_y = 135
    for idx, (name, value) in enumerate(items):
        y = start_y + idx * 39
        p.append(f'<rect x="48" y="{y-15}" width="22" height="22" rx="5" fill="{palette[idx % len(palette)]}"/>')
        p.append(svg_text(85, y+3, name, 17, c["text"], "700"))
        p.append(f'<rect x="270" y="{y-12}" width="{max_bar}" height="17" rx="8" fill="{c["track"]}"/>')
        bar = max(3, round(max_bar * float(value) / 100))
        p.append(f'<rect x="270" y="{y-12}" width="{bar}" height="17" rx="8" fill="{palette[idx % len(palette)]}"/>')
        p.append(svg_text(1085, y+3, f"{value}%", 16, c["muted"], "700", "end"))
    note = "calculated from public repository language bytes" if live.get("languages") else "values shown are from the reference screenshot; refresh via GitHub Actions"
    p.append(svg_text(48, 360, note, 13, c["muted"]))
    p.append('</svg>')
    (ASSETS / "languages.svg").write_text("\n".join(p), encoding="utf-8")


def make_activity_svg(stats, days, live):
    width, height = 1200, 365
    c = COLORS
    p = card_header(width, height, "git log --since=26.weeks --graph")
    p.append(svg_text(48, 88, "CONTRIBUTION ACTIVITY  /  LAST 26 WEEKS", 15, c["muted"], "700"))
    if not live.get("contributions"):
        p.append(svg_text(1150, 88, "PREVIEW PATTERN  /  LIVE SYNC PENDING", 14, c["yellow"], "700", "end"))
    counts = {d.get("date"): int(d.get("count", 0)) for d in days}
    # A 26-week calendar grid, ordered column-wise as GitHub's contribution view.
    start = date.today() - timedelta(days=181)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # align to Sunday
    if not live.get("contributions"):
        # Clearly-labelled design-only pattern, constrained to match the visible
        # fallback totals from the reference screenshot. Actions replaces it.
        rng = random.Random(20261123)
        active_slots = set(rng.sample(range(182), min(110, 182)))
        preview_counts = {slot: 1 for slot in active_slots}
        extras = 419 - len(preview_counts)
        for _ in range(max(0, extras)):
            preview_counts[rng.choice(tuple(active_slots))] += 1
        counts = {(start + timedelta(days=slot)).isoformat(): value for slot, value in preview_counts.items()}
    max_count = max(counts.values(), default=1)
    shades = ["#18212a", "#0e4429", "#006d32", "#26a641", "#39d353"]
    cell, gap = 18, 6
    for col in range(26):
        for row in range(7):
            d = start + timedelta(days=col*7 + row)
            count = counts.get(d.isoformat(), 0)
            if count == 0:
                shade = shades[0]
            else:
                ratio = count / max_count if max_count else 0
                shade = shades[min(4, max(1, int(ratio*4)+1))]
            x = 50 + col * (cell + gap)
            y = 125 + row * (cell + gap)
            p.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{shade}"/>')
    # Legend
    p.append(svg_text(50, 315, "less", 13, c["muted"]))
    for i, shade in enumerate(shades):
        p.append(f'<rect x="{92 + i*25}" y="301" width="18" height="18" rx="4" fill="{shade}"/>')
        # place cells sequentially
        if i < len(shades)-1:
            pass
    p.append(svg_text(215, 315, "more", 13, c["muted"]))
    # Right-side metrics
    x0 = 835
    metrics = [
        ("CONTRIBUTIONS", stats.get("contributions", 0)),
        ("ACTIVE DAYS", stats.get("active_days", 0)),
        ("CURRENT STREAK", f"{stats.get('current_streak', 0)} days"),
        ("BEST STREAK", f"{stats.get('best_streak', 0)} days"),
    ]
    for i, (label, value) in enumerate(metrics):
        y = 142 + i*52
        p.append(svg_text(x0, y-8, label, 12, c["muted"], "700"))
        p.append(svg_text(x0, y+18, value, 23, c["text"], "700"))
    p.append(svg_text(48, 349, "preview grid is illustrative until the first successful GitHub Actions sync", 12, c["muted"]))
    p.append('</svg>')
    (ASSETS / "activity.svg").write_text("\n".join(p), encoding="utf-8")


def font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        "DejaVuSansMono.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def torus_ascii(frame_index, cols=47, rows=25):
    """Return a green shaded ASCII torus, rotating around two axes."""
    theta_y = frame_index * 0.105
    theta_x = frame_index * 0.067
    screen = [[(" ", 0.0) for _ in range(cols)] for _ in range(rows)]
    zbuf = [[-1e9 for _ in range(cols)] for _ in range(rows)]
    R, r = 1.03, 0.46
    light = (-0.35, 0.55, -0.76)
    llen = math.sqrt(sum(v*v for v in light))
    light = tuple(v/llen for v in light)
    for iu in range(150):
        u = 2 * math.pi * iu / 150
        cu, su = math.cos(u), math.sin(u)
        for iv in range(70):
            v = 2 * math.pi * iv / 70
            cv, sv = math.cos(v), math.sin(v)
            x = (R + r*cv) * cu
            y = (R + r*cv) * su
            z = r * sv
            # Rotate around Y then X.
            x1 = x*math.cos(theta_y) + z*math.sin(theta_y)
            z1 = -x*math.sin(theta_y) + z*math.cos(theta_y)
            y1 = y*math.cos(theta_x) - z1*math.sin(theta_x)
            z2 = y*math.sin(theta_x) + z1*math.cos(theta_x)
            # Rotate normal in the same way for directional shading.
            nx, ny, nz = cv*cu, cv*su, sv
            nx1 = nx*math.cos(theta_y) + nz*math.sin(theta_y)
            nz1 = -nx*math.sin(theta_y) + nz*math.cos(theta_y)
            ny1 = ny*math.cos(theta_x) - nz1*math.sin(theta_x)
            nz2 = ny*math.sin(theta_x) + nz1*math.cos(theta_x)
            lum = 0.38 + 0.62*max(0.0, nx1*light[0] + ny1*light[1] + nz2*light[2])
            depth = z2 + 3.4
            inv = 1.0 / max(0.2, depth)
            sx = int(cols/2 + (x1*inv) * cols*0.82)
            sy = int(rows/2 - (y1*inv) * rows*1.02)
            if 0 <= sx < cols and 0 <= sy < rows and depth > zbuf[sy][sx]:
                zbuf[sy][sx] = depth
                ch = " .,:;!+*#%@"[min(10, int(lum*10))]
                screen[sy][sx] = (ch, lum)
    lines = []
    for row in screen:
        lines.append("".join(ch for ch, _ in row))
    return lines, screen


def make_hero_gif(stats, live):
    W, H = 1200, 650
    frames = []
    bg = COLORS["bg"]
    c = COLORS
    f_small = font(16)
    f_body = font(18)
    f_bold = font(18)
    f_title = font(20)
    f_ascii = font(11)

    for frame_no in range(48):
        im = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(im)
        # Outer terminal window.
        d.rounded_rectangle((2, 2, W-3, H-3), radius=20, fill=c["card"], outline=c["border"], width=2)
        d.rounded_rectangle((3, 3, W-3, 55), radius=18, fill=c["bar"])
        d.rectangle((3, 34, W-3, 55), fill=c["bar"])
        for x, color in [(28, "#ff625a"), (52, "#f5c451"), (76, "#45c878")]:
            d.ellipse((x-7, 17, x+7, 31), fill=color)
        d.text((110, 16), "zyuudev  /  README.md  /  terminal profile", font=f_small, fill=c["muted"])
        d.text((43, 82), "zyuudev@github:~$ neofetch", font=f_body, fill=c["blue"])
        # ASCII artwork left column.
        lines, shading = torus_ascii(frame_no)
        char_w = 7.2
        char_h = 16
        start_x = 46
        start_y = 142
        for ri, row in enumerate(shading):
            for ci, (ch, lum) in enumerate(row):
                if ch == " ":
                    continue
                intensity = int(95 + 145*lum)
                green = (max(25, int(intensity*0.34)), min(255, intensity), max(45, int(intensity*0.52)))
                d.text((start_x + ci*char_w, start_y + ri*char_h), ch, font=f_ascii, fill=green)
        d.text((45, 585), "zyuudev@github:~$", font=f_body, fill=c["blue"])
        # vertical divider
        d.line((600, 122, 600, 590), fill=c["border"], width=2)

        # Right-side neofetch fields.
        rx = 635
        d.text((rx, 113), "zyuudev@github", font=f_title, fill=c["blue"])
        d.line((790, 128, 1150, 128), fill=c["dim"], width=1)
        rows = [
            ("Name", "Arrasyd Nanda Fairuz"),
            ("Role", "Full-Stack Developer"),
            ("Focus", "AI Engineering / Backend / IoT"),
            ("Education", "SMK Negeri 1 Bantul  •  RPL"),
            ("Location", "Yogyakarta, Indonesia"),
        ]
        y = 150
        for label, value in rows:
            d.text((rx, y), f"- {label}:", font=f_body, fill=c["blue"])
            d.text((rx+160, y), "." * 17, font=f_small, fill=c["dim"])
            # right align value
            tw = d.textbbox((0,0), value, font=f_body)[2]
            d.text((1150-tw, y), value, font=f_body, fill=c["text"])
            y += 25

        y += 7
        d.text((rx, y), "- About", font=f_body, fill=c["blue"])
        d.line((715, y+13, 1150, y+13), fill=c["dim"], width=1)
        d.text((rx+2, y+27), "Building practical products,", font=f_body, fill=c["text"])
        d.text((rx+2, y+51), "from ideas to deployment.", font=f_body, fill=c["text"])

        y += 78
        d.text((rx, y), "- Contact", font=f_body, fill=c["blue"])
        d.line((725, y+13, 1150, y+13), fill=c["dim"], width=1)
        for label, value in [("GitHub", "github.com/ZyuuDev"), ("Email", "zyuudev@gmail.com"), ("Instagram", "@nndaaaaxy_")]:
            y += 22
            d.text((rx+2, y), f"{label}:", font=f_small, fill=c["blue"])
            tw = d.textbbox((0,0), value, font=f_small)[2]
            d.text((1150-tw, y), value, font=f_small, fill=c["text"])

        y += 32
        d.text((rx, y), "- GitHub Stats", font=f_body, fill=c["blue"])
        d.line((770, y+13, 1150, y+13), fill=c["dim"], width=1)
        stat_rows = [
            ("Repos", stats.get("public_repos", 0), "Stars", stats.get("stars", 0)),
            ("Followers", stats.get("followers", 0), "Following", stats.get("following", 0)),
            ("Contributions", stats.get("contributions", 0), "Active days", stats.get("active_days", 0)),
            ("Streak", f"{stats.get('current_streak', 0)}d", "Best streak", f"{stats.get('best_streak', 0)}d"),
        ]
        for left_label, left_val, right_label, right_val in stat_rows:
            y += 22
            d.text((rx+2, y), f"{left_label}:", font=f_small, fill=c["blue"])
            d.text((rx+142, y), str(left_val), font=f_small, fill=c["text"])
            d.text((rx+270, y), f"{right_label}:", font=f_small, fill=c["blue"])
            d.text((rx+430, y), str(right_val), font=f_small, fill=c["text"])
        if not live.get("profile"):
            d.text((rx, 604), "preview metrics from reference image  •  auto-refresh on workflow", font=font(12), fill=c["muted"])
        frames.append(im.convert("P", palette=Image.Palette.ADAPTIVE, colors=160))

    frames[0].save(ASSETS / "hero-terminal.gif", save_all=True, append_images=frames[1:], duration=95, loop=0, optimize=True, disposal=2)


def make_readme():
    readme = '''<p align="center">
  <img src="assets/hero-terminal.gif" width="100%" alt="Animated ASCII terminal profile for ZyuuDev" />
</p>

<div align="center">

### Hi there, I'm **Arrasyd Nanda Fairuz** 👋
**Fullstack Web Developer (Learner)** • **Backend / API Builder** • **Cybersecurity & AI Enthusiast**

🎓 *Student at **SMK Negeri 1 Bantul** — Major in **Software Engineering (RPL)**.*  
I build practical, end-to-end digital solutions: **UI → API → Database → Deployment**.

<i>Goal:</i> to contribute as an <b>intern / junior developer</b> in a <b>Web Development</b> team while continuously improving.

</div>

---

### `$ ls ~/projects --featured`

<p align="center">
  <img src="assets/projects.svg" width="100%" alt="Featured projects displayed in a terminal window" />
</p>

<p align="center">
  <a href="https://github.com/ZyuuDev/Sentinel-AI"><b>Sentinel AI</b></a> ·
  <a href="https://github.com/ZyuuDev/ZyuuBotz-V3"><b>ZyuuBotz V3</b></a> ·
  <a href="https://github.com/ZyuuDev/FIKSI-SasmitaLens"><b>SASMITA LENS</b></a> ·
  <a href="https://github.com/ZyuuDev/Finspire-JHIC-DB"><b>Finspire</b></a> ·
  <a href="https://github.com/ZyuuDev/UKK_E-Teller_Bank_Mini_ArrasydNandaFairuz"><b>E-Teller Bank Mini</b></a> ·
  <a href="https://github.com/ZyuuDev/Project_Taman_Bhinneka_UGM"><b>Taman Bhinneka</b></a>
</p>

<p align="center">
  🏆 <b>Achievements:</b><br>
  🥉 <b>3rd Place National Winner</b> — Jagoan Hosting Innovation Competition 2.0 · <i>Finspire</i><br>
  🥇 <b>1st Place Provincial Winner</b> — FIKSI 2026, Agribusiness · <i>SASMITA LENS</i><br>
  🥈 <b>1st Runner-Up Provincial Winner</b> — CCA Islam 2019<br>
  🥉 <b>3rd Place Provincial Winner</b> — IRM Jambidan Kids Festival 2020 (Angklung Group)
</p>

---

### `$ cat /about/profile.txt`

<div align="center">

🎓 <b>Student at SMK N 1 Bantul</b> — Major in <b>Software Engineering (RPL)</b>  
💡 Focus: <b>Fullstack Web Development</b>, <b>Backend Architecture</b>, and fundamentals of <b>Cybersecurity & AI</b>  
🧩 Enjoy building end-to-end applications: <b>UI</b> → <b>API</b> → <b>Database</b> → <b>Deployment</b>  
📌 Work style: <b>fast learner</b>, <b>organized</b>, <b>consistent</b>, with strong interest in documentation and clean code  
🧐 Fun fact: <b>I love chicken noodle soup (mie ayam)</b> 🍜

</div>

#### 🔭 Current Learning Focus
- 🔭 **Fullstack Mini-Projects:** Building portfolio projects with public repositories and well-structured READMEs
- 🧠 **Backend Mastery:** Deepening skills in REST API design, JWT/OAuth authentication, and database optimization
- 🛡️ **Cybersecurity:** Learning web application security fundamentals, OWASP Top 10, and vulnerability assessment
- 🤖 **AI Engineering & IoT:** Exploring agentic workflows, RAG, and sensor integrations

#### 💼 What I Can Help With
- Building responsive web interfaces using **React, Vue, Next.js, Nuxt**, and **Tailwind CSS**
- Developing robust REST APIs with **Node.js/Express, FastAPI, Laravel**, and **NestJS**
- Implementing CRUD workflows, authentication (JWT/OAuth), and database schemas (**MySQL, PostgreSQL, MongoDB, SQLite**)
- Setting up deployment (**Vercel, Netlify, Docker**) and CI/CD pipelines (**GitHub Actions**)

---

### `$ cat ~/toolbox.txt`

> Technologies I have used or am currently actively learning and exploring. 🚀

#### Languages & Fundamentals
<div align="center">
  <img src="https://skillicons.dev/icons?i=js,ts,python,php,bash,html,css,markdown&theme=dark" height="42" alt="Languages" />
</div>

#### Frontend
<div align="center">
  <img src="https://skillicons.dev/icons?i=react,vue,nextjs,nuxt,vite,tailwind,bootstrap,materialui&theme=dark" height="42" alt="Frontend" />
</div>

#### Backend & Database
<div align="center">
  <img src="https://skillicons.dev/icons?i=nodejs,express,fastapi,laravel,nestjs,django,mysql,postgres,mongodb,sqlite&theme=dark" height="42" alt="Backend and Database" />
</div>

#### DevOps, Cloud & Tools
<div align="center">
  <img src="https://skillicons.dev/icons?i=git,githubactions,docker,nginx,vercel,netlify,cloudflare,vscode,linux,figma,postman&theme=dark" height="42" alt="DevOps and Tools" />
</div>

#### Cybersecurity (Learning)
<div align="center">
  <img src="https://cdn.simpleicons.org/kalilinux/557C94" alt="Kali Linux" height="40" />
  <img src="https://cdn.simpleicons.org/burpsuite/FF6633" alt="Burp Suite" height="40" />
  <img src="https://cdn.simpleicons.org/wireshark/1679A7" alt="Wireshark" height="40" />
  <img src="https://cdn.simpleicons.org/metasploit/2E2E2E" alt="Metasploit" height="40" />
  <img src="https://cdn.simpleicons.org/owasp/000000" alt="OWASP" height="40" />
  <img src="https://img.icons8.com/color/48/network-card.png" alt="Nmap" height="40" />
</div>

---

### `$ ./github-stats`

<p align="center">
  <img src="assets/languages.svg" width="100%" alt="Programming language distribution in a terminal window" />
</p>

<p align="center">
  <img src="assets/activity.svg" width="100%" alt="GitHub contribution calendar in a terminal window" />
</p>

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/ZyuuDev/ZyuuDev/output/pacman-contribution-graph-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/ZyuuDev/ZyuuDev/output/pacman-contribution-graph.svg">
    <img alt="Pacman contribution graph" src="https://raw.githubusercontent.com/ZyuuDev/ZyuuDev/output/pacman-contribution-graph.svg">
  </picture>
</div>

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=ZyuuDev&label=Profile%20views&color=59d68b&style=flat-square" alt="Profile views" />
</p>

---

### `$ ./connect`

<p align="center">
  <a href="https://github.com/ZyuuDev" target="_blank">
    <img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub" />
  </a>
  <a href="https://www.linkedin.com/in/arrasyd-nanda-fairuz/" target="_blank">
    <img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=flat-square&logo=linkedin&logoColor=white" alt="LinkedIn" />
  </a>
  <a href="https://instagram.com/nndaaaaxy_" target="_blank">
    <img src="https://img.shields.io/badge/Instagram-E4405F?style=flat-square&logo=instagram&logoColor=white" alt="Instagram" />
  </a>
  <a href="mailto:zyuudev@gmail.com">
    <img src="https://img.shields.io/badge/Gmail-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email" />
  </a>
</p>

<p align="center">
  📍 <b>Location:</b> Yogyakarta, Indonesia &nbsp;•&nbsp;
  🕒 <b>Availability:</b> Open for internships, freelance, and part-time opportunities
</p>

<p align="center"><sub>Arrasyd Nanda Fairuz · Built with curiosity, shipped one commit at a time.</sub></p>
'''
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


def make_preview():
    try:
        import cairosvg
        from io import BytesIO
        hero = Image.open(ASSETS / "hero-terminal.gif").convert("RGB")
        width = 820
        def svg_to_img(name):
            png = cairosvg.svg2png(url=str(ASSETS / name), output_width=width)
            return Image.open(BytesIO(png)).convert("RGB")
        pieces = [hero.resize((width, round(hero.height*width/hero.width))),
                  svg_to_img("projects.svg"), svg_to_img("languages.svg"), svg_to_img("activity.svg")]
        gap = 22
        total_h = sum(im.height for im in pieces) + gap*(len(pieces)+1)
        canvas = Image.new("RGB", (width+gap*2, total_h), COLORS["bg"])
        y = gap
        for im in pieces:
            canvas.paste(im, (gap, y))
            y += im.height + gap
        canvas.save(ROOT / "preview.png", optimize=True)
    except Exception as exc:
        print(f"Preview generation skipped: {exc}")


def main():
    stats, languages, days, live = load_live_data()
    print("Profile source status:", live)
    make_hero_gif(stats, live)
    make_projects_svg()
    make_languages_svg(languages, live)
    make_activity_svg(stats, days, live)
    make_readme()
    make_preview()


if __name__ == "__main__":
    main()
