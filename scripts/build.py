#!/usr/bin/env python3
"""Build the static site (index, one page per register, change log) from
data/registers.json, data/changelog.json and status.json.

  python3 scripts/build.py            -> site files for GitHub Pages
  python3 scripts/build.py --preview  -> also preview.html (single file, CSS + data inlined)

Standard library only. MIT licence (see LICENSE).
"""
import datetime as dt
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REG = json.loads((ROOT / "data/registers.json").read_text())["registers"]
LOG = json.loads((ROOT / "data/changelog.json").read_text())["entries"]
ST = json.loads((ROOT / "status.json").read_text()) if (ROOT / "status.json").exists() else {"registers": {}}
CSS = (ROOT / "assets/style.css").read_text()
SITE = "EU Company Register Tracker"
APIFY = "https://apify.com/fieldnoteagents/"
PAID = [("czech-company-check-ares", "Czech ARES check"), ("poland-krs-company-check", "Poland KRS check")]
FIELDS = [("register_url", "Official site"), ("free_api", "Free API"), ("api_docs", "API docs"),
          ("key_needed", "Key / account"), ("data", "Data available"), ("rate_limit", "Rate limits"),
          ("licence", "Licence / terms")]
e = html.escape


def fmt_utc(iso):
    if not iso:
        return "not yet checked"
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return t.strftime("%d %b %Y, %H:%M UTC")


def fmt_day(d):
    return dt.date.fromisoformat(d).strftime("%d %b %Y")


class Links:
    """Path helper: real files for the site, #hash routes for the single-file preview."""
    def __init__(self, preview, depth=0):
        self.preview, self.up = preview, "../" * depth
    def home(self): return "#/" if self.preview else (self.up + "index.html")
    def reg(self, slug): return f"#/r/{slug}" if self.preview else f"{self.up}registers/{slug}.html"
    def log(self): return "#/changelog" if self.preview else (self.up + "changelog.html")
    def about(self): return "#/about" if self.preview else (self.up + "index.html#about")


def pill(slug):
    s = ST["registers"].get(slug)
    if not s:
        return '<span class="pill s-unknown"><i class="dot"></i>Not checked</span>'
    return f'<span class="pill s-{s["state"]}" title="{e(s["detail"])}"><i class="dot"></i>{e(s["label"])}</span>'


def short(field, n=None):
    if field.get("documented") is False or field.get("value") is None:
        return '<span class="nd">Not documented</span>'
    return e(field.get("short") or field["value"])


def fact(field):
    v = field.get("value")
    out = ""
    if field.get("verified") and v:
        out += (f'<a href="{e(v)}">{e(v)}</a>' if v.startswith("http") else e(v))
    else:
        out += '<span class="nd">Not documented</span>'
    if field.get("note"):
        out += f' <span class="muted small">{e(field["note"])}</span>'
    meta = []
    if field.get("source"):
        meta.append(f'Source: <a href="{e(field["source"])}">{e(field["source"])}</a>')
    meta.append(f'checked {fmt_day(field["checked"])}')
    return out + f'<div class="src">{" · ".join(meta)}</div>'


def header(L, on):
    def a(href, label, key):
        return f'<a href="{href}"{" class=on" if on == key else ""}>{label}</a>'
    return (f'<header class="top"><div class="wrap"><a class="brand" href="{L.home()}"><span class="mark">F</span>'
            f'{SITE} <small class="hide-sm">by Fieldnote Agents</small></a><nav>'
            f'{a(L.home(), "Directory", "home")}{a(L.log(), "Change log", "log")}{a(L.about(), "About", "about")}</nav></div></header>')


def newsletter():
    return ('<section class="card news" id="newsletter"><div><h2>Register API changes, once a month</h2>'
            '<p>A free email when a register changes its API, limits or terms, or goes down for longer than a day.</p></div>'
            '<div><form onsubmit="return false" aria-label="Newsletter sign-up (coming soon)">'
            '<input type="email" placeholder="you@example.com" disabled aria-disabled="true">'
            '<button type="button" disabled>Coming soon</button></form>'
            '<span class="small">Free newsletter coming soon. This form is a placeholder: it sends nothing and stores nothing.</span></div></section>')


def footer(L):
    paid = " · ".join(f'<a href="{APIFY}{s}">{n}</a>' for s, n in PAID)
    return (f'<footer><div class="wrap">'
            f'<div>Built and maintained by Fieldnote Agents. Not affiliated with any register or authority. '
            f'Every fact links to the official page it came from; check the source before you rely on it. '
            f'Status = one light request per register every 6 hours. Code: MIT licence.</div>'
            f'<div class="paid">Need lookups without writing code? Fieldnote also makes small paid tools on Apify, first 25 lookups free: {paid}.</div>'
            f'</div></footer>')


def home(L):
    rs = ST["registers"]
    n_up = sum(1 for r in REG if rs.get(r["slug"], {}).get("state") in ("up", "limited"))
    n_issue = sum(1 for r in REG if rs.get(r["slug"], {}).get("state") in ("maintenance", "degraded", "down"))
    n_unk = len(REG) - n_up - n_issue
    n_nd = sum(1 for r in REG for k, _ in FIELDS if r[k].get("documented") is False)
    rows = []
    for group, title in (("country", "National registers"), ("eu", "EU-wide"), ("extra", "Outside the EU")):
        rows.append(f'<tr class="grp"><td colspan="5" class="muted small" style="padding-top:18px"><b>{title}</b></td></tr>')
        for r in [x for x in REG if x["group"] == group]:
            s = rs.get(r["slug"], {})
            ms = f'<span class="ms">{s["response_ms"]} ms</span>' if s.get("response_ms") is not None and s.get("http_status") else ""
            rows.append(
                f'<tr data-q="{e((r["country"] + " " + r["register"] + " " + r["operator"] + " " + r["code"]).lower())}">'
                f'<td><span class="cc">{e(r["code"])}</span>{e(r["country"])}</td>'
                f'<td class="reg"><a href="{L.reg(r["slug"])}">{e(r["register"].split(" – ")[0])}</a><small>{e(r["operator"])}</small></td>'
                f'<td class="yn hide-sm">{short(r["free_api"], 1)}</td>'
                f'<td class="yn hide-sm">{short(r["key_needed"], 1)}</td>'
                f'<td>{pill(r["slug"])}{ms}</td></tr>')
    return f'''
<section class="hero"><div class="wrap">
<h1>Europe's official company registers, and whether their APIs are answering right now.</h1>
<p>Free directory of {len(REG)} official sources: what each one offers, whether you need a key, documented limits and terms, each linked to the official page. A light automated check runs every 6 hours.</p>
<div class="stats">
<div class="stat"><b>{n_up}</b><span>answering at last check</span></div>
<div class="stat"><b>{n_issue}</b><span>maintenance or errors</span></div>
<div class="stat"><b>{n_unk}</b><span>can't tell (bot wall)</span></div>
<div class="stat"><b>{fmt_utc(ST.get("checked_at")).split(", ")[1] if ST.get("checked_at") else "–"}</b><span>last check, {fmt_utc(ST.get("checked_at")).split(",")[0] if ST.get("checked_at") else ""}</span></div>
</div></div></section>
<main class="wrap">
<section class="card">
<div class="toolbar"><input type="search" placeholder="Filter by country or register…" oninput="fnFilter(this.value)" aria-label="Filter registers">
<span class="muted small">Every fact links to an official source. {n_nd} cells say <span class="nd">Not documented</span> where the official source doesn't say.</span></div>
<table id="regs"><thead><tr><th>Country</th><th>Register</th><th class="hide-sm">Free API</th><th class="hide-sm">Key / account</th><th>Status</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></section>
{newsletter()}
<h2 class="sec" id="about">How this works</h2>
<section class="card"><p style="margin-top:0"><b>Facts.</b> Each cell comes from an official page (the register, its ministry or its API docs), linked next to the fact with the date we checked it. If the official source doesn't say, the cell reads <span class="nd">Not documented</span> and links to that source, rather than guessing.</p>
<p><b>Status.</b> An open-source Python script makes one GET request per register every 6 hours (a scheduled job) and records the HTTP result and response time. <i>Up</i> = the endpoint answered as expected. <i>Rate-limited</i> = it answered with HTTP 429. <i>Maintenance</i> = a maintenance page instead of data. <i>Unknown</i> = bot protection stops us telling. A status changes the <a href="{L.log()}">change log</a> automatically.</p>
<p style="margin-bottom:0"><b>Not legal advice.</b> Terms change. Read the register's own terms before building on it, especially where personal data is involved.</p></section>
</main>'''


def reg_page(L, r):
    s = ST["registers"].get(r["slug"], {})
    spark = "".join(f'<i class="{st}" title="{e(t)}: {st}"></i>' for t, st in s.get("history", [])[-60:])
    facts = "".join(f'<tr><td>{label}</td><td>{fact(r[k])}</td></tr>' for k, label in FIELDS)
    example = ""
    if r["check"]["expect"] == "json" and "{" not in r["check"]["url"] and r["key_needed"]["value"] and r["key_needed"]["value"].startswith("No"):
        example = (f'<section class="card"><b>Try it</b> <span class="muted small">(the same request our status check makes)</span>'
                   f'<pre>curl -s "{e(r["check"]["url"])}"</pre></section>')
    events = [x for x in LOG if x.get("code") == r["code"] and (r["group"] != "eu" or r["register"].split(" – ")[0] in x["text"] or x.get("type") != "status")]
    ev = "".join(f'<li><time>{fmt_day(x["date"])}</time><div><span class="tag">{e(x["type"])}</span>{e(x["text"])}</div></li>' for x in events) or '<li style="display:block" class="muted">No changes recorded yet.</li>'
    vies = ""
    if "member_states_unavailable" in s:
        down = s["member_states_unavailable"]
        vies = f'<p class="small" style="margin:10px 0 0">Member-state services unavailable at last check: {e(", ".join(down)) if down else "none"}.</p>'
    apify = ""
    if r.get("apify"):
        apify = f'<p class="muted small">No-code option: Fieldnote\'s <a href="{APIFY}{r["apify"]}">Apify tool for this register</a> (paid, first 25 lookups free).</p>'
    return f'''
<main class="wrap">
<p class="crumb"><a href="{L.home()}">← All registers</a></p>
<section class="hero" style="padding-top:14px"><span class="cc">{e(r["code"])}</span><span class="muted">{e(r["country"])}</span>
<h1 style="margin-top:10px">{e(r["register"])}</h1><p>{e(r["operator"])}. API access, keys, rate limits and terms, each with its official source. Last checked {fmt_day(r["last_checked"])}.</p></section>
<div class="grid2">
<section class="card" style="margin-top:0"><table class="facts"><tbody>{facts}</tbody></table></section>
<div>
<section class="card" style="margin-top:0"><b>Live status</b><div style="margin-top:10px">{pill(r["slug"])}</div>
<p class="small muted" style="margin:10px 0 0">{e(s.get("detail", ""))}{f" · {s['response_ms']} ms" if s.get("http_status") else ""}<br>Checked {fmt_utc(s.get("checked_at"))} · {s.get("uptime_pct", "–")}% answering over {s.get("checks", 0)} check(s)</p>
{vies}<div class="spark" aria-label="Recent checks">{spark}</div>
<p class="small muted" style="margin:10px 0 0;word-break:break-all">Endpoint: {e(s.get("endpoint", r["check"]["url"]))}</p></section>
{example}
<section class="card"><b>Changes</b><ul class="log">{ev}</ul></section>
{apify}
</div></div>
</main>'''


def log_page(L):
    items = "".join(f'<li><time>{fmt_day(x["date"])}</time><div><span class="tag">{e(x["type"])}{(" · " + e(x["code"])) if x.get("code") else ""}</span>{e(x["text"])}</div></li>' for x in sorted(LOG, key=lambda x: x["date"], reverse=True))
    return f'''
<main class="wrap"><section class="hero"><h1>Change log</h1><p>Dated changes to register APIs, limits and terms, plus status changes detected by the automated check.</p></section>
<section class="card"><ul class="log">{items}</ul></section>{newsletter()}</main>'''


FILTER_JS = """function fnFilter(q){q=q.toLowerCase().trim();document.querySelectorAll('#regs tbody tr').forEach(function(t){if(t.classList.contains('grp')){t.style.display=q?'none':'';return}t.style.display=!q||t.dataset.q.indexOf(q)>-1?'':'none'})}"""


def page(title, desc, body, L, on, css_href):
    css = f'<style>{CSS}</style>' if css_href is None else f'<link rel="stylesheet" href="{css_href}">'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">{css}</head><body>
{header(L, on)}{body}{footer(L)}<script>{FILTER_JS}</script></body></html>
'''


def build_site():
    L0 = Links(False, 0)
    (ROOT / "index.html").write_text(page(f"{SITE}: official EU company register APIs and live status",
        "Free directory of official European company registers: free API, key, rate limits, licence and a live status check every 6 hours.",
        home(L0), L0, "home", "assets/style.css"))
    (ROOT / "changelog.html").write_text(page(f"Change log – {SITE}", "Dated changes to European company register APIs and their status.",
        log_page(L0), L0, "log", "assets/style.css"))
    (ROOT / "registers").mkdir(exist_ok=True)
    L1 = Links(False, 1)
    for r in REG:
        (ROOT / "registers" / f'{r["slug"]}.html').write_text(page(
            f'{r["country"]}: {r["register"].split(" – ")[0]} API, key, rate limits and status – {SITE}',
            f'{r["register"]}: is there a free API, do you need a key, documented rate limits, licence and live status.',
            reg_page(L1, r), L1, "", "../assets/style.css"))


def build_preview():
    L = Links(True)
    sections = [f'<section data-route="#/">{home(L)}</section>', f'<section data-route="#/changelog" hidden>{log_page(L)}</section>']
    sections += [f'<section data-route="#/r/{r["slug"]}" hidden>{reg_page(L, r)}</section>' for r in REG]
    router = """
function fnRoute(){var h=location.hash||'#/';var about=h==='#/about';if(about)h='#/';var hit=false;
document.querySelectorAll('section[data-route]').forEach(function(s){var on=s.dataset.route===h;s.hidden=!on;if(on)hit=true});
if(!hit){document.querySelector('section[data-route="#/"]').hidden=false}
if(about){document.getElementById('about').scrollIntoView()}else{window.scrollTo(0,0)}}
window.addEventListener('hashchange',fnRoute);fnRoute();"""
    data = json.dumps({"registers": REG, "status": ST, "changelog": LOG}, ensure_ascii=False).replace("</", "<\\/")
    body = "".join(sections)
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PREVIEW – {SITE} (local, not published)</title><style>{CSS}
.pv{{background:#16181d;color:#fff;font-size:13px;text-align:center;padding:6px}}</style></head><body>
<div class="pv">Local preview only, not published. Data checked {e(fmt_utc(ST.get("checked_at")))}.</div>
{header(L, "home")}{body}{footer(L)}
<script type="application/json" id="fn-data">{data}</script>
<script>{FILTER_JS}{router}</script></body></html>
'''
    (ROOT / "preview.html").write_text(doc)


if __name__ == "__main__":
    build_site()
    if "--preview" in sys.argv:
        build_preview()
    print("built", len(REG), "register pages", "+ preview.html" if "--preview" in sys.argv else "")
