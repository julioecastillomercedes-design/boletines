#!/usr/bin/env python3
"""Generador del portal de boletines.

Uso:  python3 build.py            -> escribe el sitio en ./docs
Entrada: issues/<especialidad>/<AAAA-MM-DD>.md  (frontmatter YAML simple + markdown)
         audio/<especialidad>-<AAAA-MM-DD>.mp3  (opcional)
         config.json
Requiere: pip install markdown
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("Falta el paquete 'markdown': pip install markdown")

ROOT = Path(__file__).resolve().parent
ISSUES = ROOT / "issues"
AUDIO = ROOT / "audio"
OUT = ROOT / "docs"
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SITE_URL = CFG["site_url"].rstrip("/")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v in ("null", "", "[]"):
            v = None
        elif v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        meta[k.strip()] = v
    return meta, m.group(2)


URL_RE = re.compile(r"(?<![\"'>(])(https?://[^\s<>\)\]]+)")


def linkify(text: str) -> str:
    return URL_RE.sub(lambda m: f'<{m.group(1)}>', text)


def split_whatsapp(body: str):
    """Separa el bloque 'Texto para WhatsApp' del cuerpo."""
    m = re.search(r"^##\s*Texto para WhatsApp\s*$", body, re.M | re.I)
    if not m:
        return body, None
    wa = body[m.end():].strip()
    return body[: m.start()].rstrip(), wa


def strip_redundant_title(body: str, title: str) -> str:
    lines = body.lstrip("\n").split("\n")
    first = lines[0].strip()
    if first and (first.upper().startswith("BOLETÍN") or first.upper().startswith("BOLETIN")) and len(first) < 140:
        lines = lines[1:]
    return "\n".join(lines).lstrip("\n")


def md_to_html(body: str) -> str:
    body = linkify(body)
    return markdown.markdown(body, extensions=["nl2br", "sane_lists"], output_format="html5")


def load_issues():
    issues = []
    for spec_dir in sorted(ISSUES.iterdir()):
        if not spec_dir.is_dir() or spec_dir.name not in CFG["specialties"]:
            continue
        for f in sorted(spec_dir.glob("*.md")):
            meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            d = datetime.strptime(meta["date"], "%Y-%m-%d").date()
            body, wa = split_whatsapp(body)
            body = strip_redundant_title(body, meta.get("title", ""))
            audio = AUDIO / f"{spec_dir.name}-{meta['date']}.mp3"
            issues.append({
                "spec": spec_dir.name,
                "date": d,
                "slug": meta["date"],
                "title": meta.get("title") or f"Boletín — {fecha_larga(d)}",
                "body_html": md_to_html(body),
                "whatsapp": wa,
                "audio": audio if audio.exists() else None,
                "audio_minutes": meta.get("audio_minutes"),
                "summary": summary_of(body),
            })
    issues.sort(key=lambda i: i["date"], reverse=True)
    return issues


def summary_of(body: str) -> str:
    for line in body.split("\n"):
        s = line.strip()
        if len(s) > 80 and not s.startswith("#") and not s.startswith("http"):
            s = re.sub(r"\s+", " ", s)
            return (s[:220].rsplit(" ", 1)[0] + "…") if len(s) > 220 else s
    return ""


def e(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- CSS

CSS = """
:root{--bg:#f6f3ee;--surface:#fffdf9;--ink:#1d1a16;--ink-2:#5b554d;--ink-3:#8a837a;--line:#e4ddd2;--accent:hsl(var(--hue) 55% 42%);--accent-soft:hsl(var(--hue) 60% 94%);--radius:14px;--hue:20;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15130f;--surface:#1e1b16;--ink:#efe9e0;--ink-2:#b8b0a4;--ink-3:#847d73;--line:#332e27;--accent:hsl(var(--hue) 60% 62%);--accent-soft:hsl(var(--hue) 35% 18%)}}
[style*="--h"]{--accent:hsl(var(--h) 55% 42%);--accent-soft:hsl(var(--h) 60% 94%)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) [style*="--h"]{--accent:hsl(var(--h) 60% 62%);--accent-soft:hsl(var(--h) 35% 18%)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 Georgia,'Iowan Old Style','Times New Roman',serif}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
header.top{border-bottom:1px solid var(--line);background:var(--surface)}
header.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;flex-wrap:wrap}
.brand{font-weight:700;font-size:1.05rem;text-decoration:none;color:var(--ink);letter-spacing:.01em}
.brand small{display:block;font-weight:400;font-size:.8rem;color:var(--ink-3);font-family:system-ui,sans-serif}
nav.specs{display:flex;gap:6px;flex-wrap:wrap;font-family:system-ui,sans-serif;font-size:.82rem}
nav.specs a{--hue:var(--h);padding:5px 11px;border-radius:999px;background:var(--accent-soft);color:var(--accent);text-decoration:none;font-weight:600;white-space:nowrap}
nav.specs a[aria-current]{outline:2px solid var(--accent)}
main{padding:28px 0 56px}
h1{font-size:clamp(1.6rem,4.5vw,2.3rem);line-height:1.15;margin:.2em 0 .4em;letter-spacing:-.01em}
h2{font-size:1.3rem;margin:1.8em 0 .5em;padding-top:.6em;border-top:1px solid var(--line)}
h3{font-size:1.08rem;margin:1.4em 0 .3em;line-height:1.3}
p{margin:.5em 0 1em}
.meta{font-family:system-ui,sans-serif;font-size:.85rem;color:var(--ink-2);display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.pill{--hue:var(--h);background:var(--accent-soft);color:var(--accent);padding:3px 10px;border-radius:999px;font-weight:600;font-size:.78rem}
.hero{padding:10px 0 26px}
.hero p.lead{font-size:1.12rem;color:var(--ink-2);max-width:60ch;margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{--hue:var(--h);background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px 18px 16px;display:flex;flex-direction:column;gap:8px;border-top:4px solid var(--accent)}
.card h2{border:0;margin:0;padding:0;font-size:1.15rem}
.card h2 a{color:var(--ink);text-decoration:none}.card h2 a:hover{color:var(--accent)}
.card .blurb{color:var(--ink-2);font-size:.95rem;margin:0}
.card .last{font-family:system-ui,sans-serif;font-size:.85rem;color:var(--ink-3);margin-top:auto;padding-top:6px}
.card .last a{font-weight:600}
.list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:10px}
.list li{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px}
.list li a.t{font-weight:700;color:var(--ink);text-decoration:none;font-size:1.05rem}
.list li a.t:hover{color:var(--accent)}
.list li p{margin:.3em 0 0;color:var(--ink-2);font-size:.95rem}
.audio{--hue:var(--h);background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:var(--radius);padding:14px 16px;margin:18px 0 8px;font-family:system-ui,sans-serif}
.audio strong{display:block;margin-bottom:6px;font-size:.95rem}
.audio audio{width:100%;display:block}
.audio .dl{font-size:.85rem;margin-top:8px;display:flex;gap:14px;flex-wrap:wrap}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 18px;font-family:system-ui,sans-serif}
button.btn{--hue:var(--h);font:600 .9rem system-ui,sans-serif;background:var(--accent);color:#fff;border:0;border-radius:999px;padding:9px 16px;cursor:pointer}
button.btn.secondary{background:var(--accent-soft);color:var(--accent)}
button.btn:active{transform:translateY(1px)}
article.issue{font-size:1.02rem}
article.issue a{word-break:break-all}
details.wa{margin:26px 0;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface)}
details.wa summary{cursor:pointer;padding:12px 16px;font:600 .95rem system-ui,sans-serif}
details.wa pre{white-space:pre-wrap;word-break:break-word;margin:0;padding:0 16px 16px;font:.92rem/1.5 system-ui,sans-serif;color:var(--ink-2)}
.prevnext{display:flex;justify-content:space-between;gap:12px;margin-top:36px;padding-top:16px;border-top:1px solid var(--line);font-family:system-ui,sans-serif;font-size:.9rem}
footer{border-top:1px solid var(--line);padding:22px 0 40px;font-family:system-ui,sans-serif;font-size:.85rem;color:var(--ink-3)}
footer p{margin:.3em 0}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:10px 16px;border-radius:999px;font:600 .9rem system-ui,sans-serif;opacity:0;transition:opacity .25s;pointer-events:none}
.toast.show{opacity:1}
@media (max-width:520px){body{font-size:16px}h2{font-size:1.2rem}}
"""

JS = """
function copiar(id,btn){var t=document.getElementById(id).textContent;
navigator.clipboard.writeText(t).then(function(){aviso('Copiado. Pégalo en WhatsApp.')},function(){aviso('No se pudo copiar')})}
function aviso(m){var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(function(){t.classList.remove('show')},2200)}
function compartir(title,url){if(navigator.share){navigator.share({title:title,url:url}).catch(function(){})}else{navigator.clipboard.writeText(url).then(function(){aviso('Enlace copiado')})}}
"""


# ---------------------------------------------------------------- layout

def nav_html(current=None):
    links = []
    for key, s in CFG["specialties"].items():
        cur = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{SITE_URL}/{key}/" style="--h:{s["hue"]}"{cur}>{e(s["short"])}</a>')
    return '<nav class="specs" aria-label="Especialidades">' + "".join(links) + "</nav>"


def page(title, body, *, desc, url, current=None, extra_head=""):
    full_title = title if title == CFG["site_name"] else f"{title} · {CFG['site_name']}"
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{e(CFG['site_name'])}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="application/rss+xml" title="{e(CFG['site_name'])}" href="{SITE_URL}/feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23b8432f'/%3E%3Cpath d='M9 8h14M9 16h14M9 24h9' stroke='%23fff' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E">
{extra_head}
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="{SITE_URL}/">{e(CFG['site_name'])}<small>{e(CFG['author'])}</small></a>
{nav_html(current)}
</div></header>
<main><div class="wrap">
{body}
</div></main>
<footer><div class="wrap">
<p><strong>{e(CFG['site_name'])}</strong> · Curaduría de {e(CFG['author'])}, {e(CFG['author_role'])}.</p>
<p>Cada número resume publicaciones, guías, ensayos y avisos regulatorios verificados, con lectura crítica de su calidad (diseño, tamaño muestral, financiación). Es material informativo para profesionales; no sustituye la lectura de la fuente original ni el juicio clínico.</p>
<p><a href="{SITE_URL}/feed.xml">RSS</a></p>
</div></footer>
<div id="toast" class="toast" role="status"></div>
<script>{JS}</script>
</body>
</html>"""


# ---------------------------------------------------------------- pages

def build():
    issues = load_issues()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "audio").mkdir(parents=True)
    by_spec = {k: [i for i in issues if i["spec"] == k] for k in CFG["specialties"]}
    urls = []

    # Portada
    cards = []
    for key, s in CFG["specialties"].items():
        lst = by_spec[key]
        last = lst[0] if lst else None
        last_html = (f'Último número: <a href="{SITE_URL}/{key}/{last["slug"]}.html">{e(fecha_larga(last["date"]))}</a>'
                     f' · {len(lst)} número{"s" if len(lst) != 1 else ""}') if last else "Próximamente"
        cards.append(f"""<div class="card" style="--h:{s['hue']}">
<span class="pill">{e(s['cadence'])}</span>
<h2><a href="{SITE_URL}/{key}/">{e(s['name'])}</a></h2>
<p class="blurb">{e(s['blurb'])}</p>
<div class="last">{last_html}</div>
</div>""")
    recent = "".join(issue_li(i) for i in issues[:6])
    home = f"""<section class="hero">
<h1>{e(CFG['site_tagline'])}</h1>
<p class="lead">Boletines de actualización científica por especialidad, con texto completo y noticiero en audio, preparados para {e(CFG['author_role'].split(' · ')[1] if ' · ' in CFG['author_role'] else 'nuestros grupos de trabajo')} y abiertos a todo el que quiera leerlos.</p>
</section>
<section class="grid">{''.join(cards)}</section>
<section><h2>Últimos números</h2><ul class="list">{recent}</ul></section>"""
    write(OUT / "index.html", page(CFG["site_name"], home, desc=CFG["description"], url=f"{SITE_URL}/"))
    urls.append((f"{SITE_URL}/", issues[0]["date"] if issues else date.today(), "daily", "1.0"))

    # Especialidades
    for key, s in CFG["specialties"].items():
        lst = by_spec[key]
        body = f"""<section class="hero" style="--h:{s['hue']}">
<div class="meta"><span class="pill">{e(s['cadence'])}</span><span>Para {e(s['audience'])}</span></div>
<h1>{e(s['name'])}</h1>
<p class="lead">{e(s['blurb'])}</p>
</section>
<h2>Números publicados</h2>
<ul class="list">{''.join(issue_li(i, show_spec=False) for i in lst) or '<li>Todavía no hay números publicados.</li>'}</ul>
<p class="meta" style="margin-top:18px"><a href="{SITE_URL}/{key}/feed.xml">RSS de esta especialidad</a></p>"""
        write(OUT / key / "index.html", page(s["name"], body, desc=s["blurb"], url=f"{SITE_URL}/{key}/", current=key))
        urls.append((f"{SITE_URL}/{key}/", lst[0]["date"] if lst else date.today(), "weekly", "0.8"))
        write(OUT / key / "feed.xml", rss(lst, s["name"], f"{SITE_URL}/{key}/"))

        for n, it in enumerate(lst):
            prev_i = lst[n + 1] if n + 1 < len(lst) else None
            next_i = lst[n - 1] if n > 0 else None
            write(OUT / key / f"{it['slug']}.html", issue_page(it, s, prev_i, next_i))
            urls.append((f"{SITE_URL}/{key}/{it['slug']}.html", it["date"], "never", "0.6"))
            if it["audio"]:
                shutil.copy2(it["audio"], OUT / "audio" / it["audio"].name)

    write(OUT / "feed.xml", rss(issues, CFG["site_name"], f"{SITE_URL}/"))
    write(OUT / "sitemap.xml", sitemap(urls))
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    write(OUT / ".nojekyll", "")
    print(f"OK: {len(issues)} números, {len(urls)} páginas -> {OUT}")


def issue_li(i, show_spec=True):
    s = CFG["specialties"][i["spec"]]
    spec = f'<span class="pill" style="--h:{s["hue"]}">{e(s["short"])}</span> ' if show_spec else ""
    audio = " · 🎧 audio" if i["audio"] else ""
    return (f'<li><div class="meta">{spec}<span>{e(fecha_larga(i["date"]))}{audio}</span></div>'
            f'<a class="t" href="{SITE_URL}/{i["spec"]}/{i["slug"]}.html">{e(i["title"])}</a>'
            f'<p>{e(i["summary"])}</p></li>')


def issue_page(it, s, prev_i, next_i):
    url = f"{SITE_URL}/{it['spec']}/{it['slug']}.html"
    audio_html = ""
    if it["audio"]:
        aurl = f"{SITE_URL}/audio/{it['audio'].name}"
        mins = f" · {round(float(it['audio_minutes']))} min" if it["audio_minutes"] else ""
        audio_html = f"""<div class="audio" style="--h:{s['hue']}">
<strong>🎧 Noticiero en audio{mins}</strong>
<audio controls preload="none" src="{aurl}"></audio>
<div class="dl"><a href="{aurl}" download>Descargar MP3</a><a href="https://wa.me/?text={e(html.escape(it['title']))}%20{aurl}" target="_blank" rel="noopener">Enviar audio por WhatsApp</a></div>
</div>"""
    wa_html = ""
    tools = f'<button class="btn secondary" style="--h:{s["hue"]}" onclick="compartir({json.dumps(it["title"])},{json.dumps(url)})">Compartir enlace</button>'
    if it["whatsapp"]:
        tools = f'<button class="btn" style="--h:{s["hue"]}" onclick="copiar(\'wa\',this)">Copiar texto para WhatsApp</button>' + tools
        wa_html = f"""<details class="wa"><summary>Texto listo para WhatsApp</summary><pre id="wa">{e(it['whatsapp'])}</pre></details>"""
    nav = ""
    if prev_i or next_i:
        left = f'<a href="{SITE_URL}/{it["spec"]}/{prev_i["slug"]}.html">← {e(fecha_larga(prev_i["date"]))}</a>' if prev_i else "<span></span>"
        right = f'<a href="{SITE_URL}/{it["spec"]}/{next_i["slug"]}.html">{e(fecha_larga(next_i["date"]))} →</a>' if next_i else "<span></span>"
        nav = f'<div class="prevnext">{left}{right}</div>'
    ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": it["title"], "datePublished": it["date"].isoformat(), "inLanguage": "es",
        "author": {"@type": "Person", "name": CFG["author"]},
        "publisher": {"@type": "Organization", "name": CFG["site_name"]},
        "mainEntityOfPage": url, "description": it["summary"],
    }
    body = f"""<article class="issue" style="--h:{s['hue']}">
<div class="meta"><span class="pill">{e(s['short'])}</span><time datetime="{it['date'].isoformat()}">{e(fecha_larga(it['date']))}</time></div>
<h1>{e(it['title'])}</h1>
{audio_html}
<div class="tools">{tools}</div>
{it['body_html']}
{wa_html}
{nav}
</article>"""
    extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
    return page(it["title"], body, desc=it["summary"] or s["blurb"], url=url, current=it["spec"], extra_head=extra)


def rss(items, title, link):
    out = [f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
           f'<title>{e(title)}</title><link>{e(link)}</link><description>{e(CFG["description"])}</description><language>es</language>']
    for i in items:
        url = f"{SITE_URL}/{i['spec']}/{i['slug']}.html"
        pub = datetime.combine(i["date"], datetime.min.time(), tzinfo=timezone.utc).strftime("%a, %d %b %Y 07:30:00 +0000")
        enc = f'<enclosure url="{SITE_URL}/audio/{i["audio"].name}" length="{i["audio"].stat().st_size}" type="audio/mpeg"/>' if i["audio"] else ""
        out.append(f"<item><title>{e(i['title'])}</title><link>{url}</link><guid>{url}</guid><pubDate>{pub}</pubDate>"
                   f"<description>{e(i['summary'])}</description>{enc}</item>")
    out.append("</channel></rss>")
    return "".join(out)


def sitemap(urls):
    out = ['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, d, freq, pri in urls:
        out.append(f"<url><loc>{e(u)}</loc><lastmod>{d.isoformat()}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>")
    out.append("</urlset>")
    return "".join(out)


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    build()
