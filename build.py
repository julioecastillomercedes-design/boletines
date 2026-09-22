#!/usr/bin/env python3
"""Generador del portal de boletines (bilingüe ES/EN).

Uso:  python3 build.py            -> escribe el sitio en ./docs
Entrada: issues/<especialidad>/<AAAA-MM-DD>.md      (español, frontmatter YAML simple + markdown)
         issues/<especialidad>/<AAAA-MM-DD>.en.md   (inglés, opcional)
         audio/<especialidad>-<AAAA-MM-DD>.mp3      (opcional)
         audio/<especialidad>-<AAAA-MM-DD>-en.mp3   (opcional)
         config.json
Requiere: pip install markdown
"""
import html
import json
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
LANGS = ("es", "en")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Textos de interfaz por idioma
T = {
    "es": {
        "lang_name": "Español", "other_lang": "English", "other_code": "en",
        "nav_label": "Especialidades", "latest": "Últimos números", "last_issue": "Último número",
        "issue": "número", "issues": "números", "soon": "Próximamente", "for": "Para",
        "published": "Números publicados", "none": "Todavía no hay números publicados.",
        "rss_spec": "RSS de esta especialidad", "audio": "🎧 Noticiero en audio", "min": "min",
        "download": "Descargar MP3", "send_wa": "Enviar audio por WhatsApp",
        "copy_wa": "Copiar texto para WhatsApp", "copy_li": "Copiar para LinkedIn", "copy_x": "Copiar para X",
        "share": "Compartir enlace", "wa_ready": "Texto listo para WhatsApp",
        "li_ready": "Texto listo para LinkedIn", "x_ready": "Texto listo para X (Twitter)",
        "copied": "Copiado.", "copy_fail": "No se pudo copiar", "link_copied": "Enlace copiado",
        "curated": "Curaduría de", "footer": "Cada número resume publicaciones, guías, ensayos y avisos regulatorios verificados, con lectura crítica de su calidad (diseño, tamaño muestral, financiación). Es material informativo para profesionales; no sustituye la lectura de la fuente original ni el juicio clínico.",
        "only_in": "Este número solo está disponible en español.", "audio_tag": "audio",
        "no_en_yet": "The English edition of this issue is not available. Showing the Spanish original.",
        "bulletin": "Boletín",
    },
    "en": {
        "lang_name": "English", "other_lang": "Español", "other_code": "es",
        "nav_label": "Specialties", "latest": "Latest issues", "last_issue": "Latest issue",
        "issue": "issue", "issues": "issues", "soon": "Coming soon", "for": "For",
        "published": "Published issues", "none": "No issues published yet.",
        "rss_spec": "RSS for this specialty", "audio": "🎧 Audio newscast", "min": "min",
        "download": "Download MP3", "send_wa": "Send audio via WhatsApp",
        "copy_wa": "Copy WhatsApp text", "copy_li": "Copy for LinkedIn", "copy_x": "Copy for X",
        "share": "Share link", "wa_ready": "Ready-to-paste WhatsApp text",
        "li_ready": "Ready-to-paste LinkedIn post", "x_ready": "Ready-to-paste X (Twitter) post",
        "copied": "Copied.", "copy_fail": "Could not copy", "link_copied": "Link copied",
        "curated": "Curated by", "footer": "Each issue summarizes verified publications, guidelines, trials and regulatory notices, with a critical reading of their quality (design, sample size, funding). Informational material for professionals; it does not replace reading the primary source or clinical judgment.",
        "only_in": "This issue is only available in Spanish.", "audio_tag": "audio",
        "no_en_yet": "", "bulletin": "Bulletin",
    },
}


def fecha_larga(d: date, lang="es") -> str:
    if lang == "en":
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def base(lang):
    return SITE_URL if lang == "es" else f"{SITE_URL}/en"


def spec_field(s, field, lang):
    """Campo de la especialidad en el idioma pedido (name_en, blurb_en…), con fallback al español."""
    if lang == "en":
        return s.get(f"{field}_en") or s.get(field, "")
    return s.get(field, "")


def cfg_field(field, lang):
    if lang == "en":
        return CFG.get(f"{field}_en") or CFG.get(field, "")
    return CFG.get(field, "")


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


EXTRA_HEADINGS = {
    "whatsapp": r"(Texto para WhatsApp|Text for WhatsApp|WhatsApp text|WhatsApp)",
    "linkedin": r"(Texto para LinkedIn|Text for LinkedIn|LinkedIn post|LinkedIn)",
    "x": r"(Texto para X(?: \(Twitter\))?|Text for X(?: \(Twitter\))?|X post|X \(Twitter\)|X)",
}


def split_extras(body: str):
    """Separa los bloques finales 'Texto para WhatsApp / LinkedIn / X' del cuerpo."""
    extras = {}
    pattern = re.compile(r"^##\s*(Texto para WhatsApp|Text for WhatsApp|WhatsApp text|WhatsApp|"
                         r"Texto para LinkedIn|Text for LinkedIn|LinkedIn post|LinkedIn|"
                         r"Texto para X(?: \(Twitter\))?|Text for X(?: \(Twitter\))?|X post|X \(Twitter\)|X)\s*$", re.M | re.I)
    matches = list(pattern.finditer(body))
    if not matches:
        return body, extras
    main = body[: matches[0].start()].rstrip()
    for n, m in enumerate(matches):
        end = matches[n + 1].start() if n + 1 < len(matches) else len(body)
        head = m.group(1).lower()
        key = "whatsapp" if "whatsapp" in head else "linkedin" if "linkedin" in head else "x"
        extras[key] = body[m.end():end].strip()
    return main, extras


def strip_redundant_title(body: str) -> str:
    lines = body.lstrip("\n").split("\n")
    first = lines[0].strip().upper()
    if first and (first.startswith("BOLETÍN") or first.startswith("BOLETIN") or first.startswith("BULLETIN")
                  or first.startswith("NEWSLETTER")) and len(first) < 140:
        lines = lines[1:]
    return "\n".join(lines).lstrip("\n")


def md_to_html(body: str) -> str:
    return markdown.markdown(linkify(body), extensions=["nl2br", "sane_lists"], output_format="html5")


def summary_of(body: str) -> str:
    for line in body.split("\n"):
        s = line.strip()
        if len(s) > 80 and not s.startswith("#") and not s.startswith("http"):
            s = re.sub(r"\s+", " ", s)
            return (s[:220].rsplit(" ", 1)[0] + "…") if len(s) > 220 else s
    return ""


def load_issue_file(f: Path, spec: str, lang: str):
    meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
    d = datetime.strptime(meta["date"], "%Y-%m-%d").date()
    body, extras = split_extras(body)
    body = strip_redundant_title(body)
    audio = AUDIO / (f"{spec}-{meta['date']}.mp3" if lang == "es" else f"{spec}-{meta['date']}-en.mp3")
    return {
        "spec": spec, "lang": lang, "date": d, "slug": meta["date"],
        "title": meta.get("title") or f"{T[lang]['bulletin']} — {fecha_larga(d, lang)}",
        "body_html": md_to_html(body), "extras": extras,
        "audio": audio if audio.exists() else None,
        "audio_minutes": meta.get("audio_minutes"),
        "summary": summary_of(body),
    }


def load_issues():
    """Devuelve {'es': [...], 'en': [...]}; cada número enlaza a su versión en el otro idioma si existe."""
    issues = {"es": [], "en": []}
    for spec_dir in sorted(ISSUES.iterdir()):
        if not spec_dir.is_dir() or spec_dir.name not in CFG["specialties"]:
            continue
        for f in sorted(spec_dir.glob("????-??-??.md")):
            es = load_issue_file(f, spec_dir.name, "es")
            en_file = spec_dir / f"{f.stem}.en.md"
            en = load_issue_file(en_file, spec_dir.name, "en") if en_file.exists() else None
            es["alt"] = en
            issues["es"].append(es)
            if en:
                en["alt"] = es
                issues["en"].append(en)
    for lang in LANGS:
        issues[lang].sort(key=lambda i: i["date"], reverse=True)
    return issues


def e(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- CSS / JS

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
.navs{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
nav.specs{display:flex;gap:6px;flex-wrap:wrap;font-family:system-ui,sans-serif;font-size:.82rem}
nav.specs a{--hue:var(--h);padding:5px 11px;border-radius:999px;background:var(--accent-soft);color:var(--accent);text-decoration:none;font-weight:600;white-space:nowrap}
nav.specs a[aria-current]{outline:2px solid var(--accent)}
a.lang{font:600 .8rem system-ui,sans-serif;border:1px solid var(--line);border-radius:999px;padding:5px 11px;color:var(--ink-2);text-decoration:none;white-space:nowrap}
a.lang:hover{border-color:var(--ink-3);color:var(--ink)}
main{padding:28px 0 56px}
h1{font-size:clamp(1.6rem,4.5vw,2.3rem);line-height:1.15;margin:.2em 0 .4em;letter-spacing:-.01em}
h2{font-size:1.3rem;margin:1.8em 0 .5em;padding-top:.6em;border-top:1px solid var(--line)}
h3{font-size:1.08rem;margin:1.4em 0 .3em;line-height:1.3}
p{margin:.5em 0 1em}
.meta{font-family:system-ui,sans-serif;font-size:.85rem;color:var(--ink-2);display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.pill{--hue:var(--h);background:var(--accent-soft);color:var(--accent);padding:3px 10px;border-radius:999px;font-weight:600;font-size:.78rem}
.note{font:.88rem system-ui,sans-serif;color:var(--ink-2);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:8px 0 14px}
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
details.wa{margin:14px 0;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface)}
details.wa summary{cursor:pointer;padding:12px 16px;font:600 .95rem system-ui,sans-serif}
details.wa pre{white-space:pre-wrap;word-break:break-word;margin:0;padding:0 16px 16px;font:.92rem/1.5 system-ui,sans-serif;color:var(--ink-2)}
.extras{margin-top:26px}
.prevnext{display:flex;justify-content:space-between;gap:12px;margin-top:36px;padding-top:16px;border-top:1px solid var(--line);font-family:system-ui,sans-serif;font-size:.9rem}
footer{border-top:1px solid var(--line);padding:22px 0 40px;font-family:system-ui,sans-serif;font-size:.85rem;color:var(--ink-3)}
footer p{margin:.3em 0}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:10px 16px;border-radius:999px;font:600 .9rem system-ui,sans-serif;opacity:0;transition:opacity .25s;pointer-events:none}
.toast.show{opacity:1}
@media (max-width:520px){body{font-size:16px}h2{font-size:1.2rem}}
"""


def js(lang):
    t = T[lang]
    return f"""
function copiar(id){{var t=document.getElementById(id).textContent;
navigator.clipboard.writeText(t).then(function(){{aviso({json.dumps(t['copied'])})}},function(){{aviso({json.dumps(t['copy_fail'])})}})}}
function aviso(m){{var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(function(){{t.classList.remove('show')}},2200)}}
function compartir(title,url){{if(navigator.share){{navigator.share({{title:title,url:url}}).catch(function(){{}})}}else{{navigator.clipboard.writeText(url).then(function(){{aviso({json.dumps(t['link_copied'])})}})}}}}
"""


# ---------------------------------------------------------------- layout

def nav_html(lang, current=None):
    links = []
    for key, s in CFG["specialties"].items():
        cur = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{base(lang)}/{key}/" style="--h:{s["hue"]}"{cur}>{e(spec_field(s, "short", lang))}</a>')
    return f'<nav class="specs" aria-label="{e(T[lang]["nav_label"])}">' + "".join(links) + "</nav>"


def page(title, body, *, lang, desc, url, alt_url, current=None, extra_head=""):
    t = T[lang]
    site_name = cfg_field("site_name", lang)
    full_title = title if title == site_name else f"{title} · {site_name}"
    other = t["other_code"]
    hreflang = (f'<link rel="alternate" hreflang="{lang}" href="{e(url)}">'
                f'<link rel="alternate" hreflang="{other}" href="{e(alt_url)}">'
                f'<link rel="alternate" hreflang="x-default" href="{e(url if lang == "es" else alt_url)}">')
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
{hreflang}
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:type" content="article">
<meta property="og:locale" content="{'es_DO' if lang == 'es' else 'en_US'}">
<meta property="og:site_name" content="{e(site_name)}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="application/rss+xml" title="{e(site_name)}" href="{base(lang)}/feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23b8432f'/%3E%3Cpath d='M9 8h14M9 16h14M9 24h9' stroke='%23fff' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E">
{extra_head}
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="{base(lang)}/">{e(site_name)}<small>{e(CFG['author'])}</small></a>
<div class="navs">{nav_html(lang, current)}<a class="lang" href="{e(alt_url)}" hreflang="{other}" lang="{other}">{e(t['other_lang'])}</a></div>
</div></header>
<main><div class="wrap">
{body}
</div></main>
<footer><div class="wrap">
<p><strong>{e(site_name)}</strong> · {e(t['curated'])} {e(CFG['author'])}, {e(cfg_field('author_role', lang))}.</p>
<p>{e(t['footer'])}</p>
<p><a href="{base(lang)}/feed.xml">RSS</a> · <a href="{e(alt_url)}" hreflang="{other}">{e(t['other_lang'])}</a></p>
</div></footer>
<div id="toast" class="toast" role="status"></div>
<script>{js(lang)}</script>
</body>
</html>"""


# ---------------------------------------------------------------- pages

def issue_url(i, lang=None):
    lang = lang or i["lang"]
    return f"{base(lang)}/{i['spec']}/{i['slug']}.html"


def alt_issue_url(i):
    """URL de la versión en el otro idioma; si no existe, la portada de la especialidad en ese idioma."""
    other = T[i["lang"]]["other_code"]
    if i.get("alt"):
        return issue_url(i["alt"])
    return f"{base(other)}/{i['spec']}/"


def build():
    all_issues = load_issues()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "audio").mkdir(parents=True)
    urls = []
    build_lang("es", all_issues["es"], urls)
    build_lang("en", all_issues["en"], urls, fallback=all_issues["es"])
    # audios (ambos idiomas)
    for lang in LANGS:
        for it in all_issues[lang]:
            if it["audio"]:
                shutil.copy2(it["audio"], OUT / "audio" / it["audio"].name)
    write(OUT / "sitemap.xml", sitemap(urls))
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    write(OUT / ".nojekyll", "")
    if CFG.get("custom_domain"):
        write(OUT / "CNAME", CFG["custom_domain"] + "\n")
    print(f"OK: {len(all_issues['es'])} números ES, {len(all_issues['en'])} EN, {len(urls)} páginas -> {OUT}")


def build_lang(lang, issues, urls, fallback=()):
    t = T[lang]
    out = OUT if lang == "es" else OUT / "en"
    by_spec = {k: [i for i in issues if i["spec"] == k] for k in CFG["specialties"]}
    # En la edición inglesa, los números que solo existen en español se listan igualmente (enlazan al original).
    shown = sorted(list(issues) + [i for i in fallback if not i.get("alt")], key=lambda i: i["date"], reverse=True)
    shown_by_spec = {k: [i for i in shown if i["spec"] == k] for k in CFG["specialties"]}
    site_name = cfg_field("site_name", lang)

    # Portada
    cards = []
    for key, s in CFG["specialties"].items():
        lst = shown_by_spec[key]
        last = lst[0] if lst else None
        n = len(lst)
        last_html = (f'{t["last_issue"]}: <a href="{issue_url(last)}">{e(fecha_larga(last["date"], lang))}</a>'
                     f' · {n} {t["issues"] if n != 1 else t["issue"]}') if last else t["soon"]
        cards.append(f"""<div class="card" style="--h:{s['hue']}">
<span class="pill">{e(spec_field(s, 'cadence', lang))}</span>
<h2><a href="{base(lang)}/{key}/">{e(spec_field(s, 'name', lang))}</a></h2>
<p class="blurb">{e(spec_field(s, 'blurb', lang))}</p>
<div class="last">{last_html}</div>
</div>""")
    recent = "".join(issue_li(i, ui=lang) for i in shown[:6])
    home = f"""<section class="hero">
<h1>{e(cfg_field('site_tagline', lang))}</h1>
<p class="lead">{e(cfg_field('site_lead', lang))}</p>
</section>
<section class="grid">{''.join(cards)}</section>
<section><h2>{e(t['latest'])}</h2><ul class="list">{recent}</ul></section>"""
    write(out / "index.html", page(site_name, home, lang=lang, desc=cfg_field("description", lang),
                                    url=f"{base(lang)}/", alt_url=f"{base(t['other_code'])}/"))
    urls.append((f"{base(lang)}/", issues[0]["date"] if issues else date.today(), "daily", "1.0"))

    # Especialidades
    for key, s in CFG["specialties"].items():
        lst = by_spec[key]
        body = f"""<section class="hero" style="--h:{s['hue']}">
<div class="meta"><span class="pill">{e(spec_field(s, 'cadence', lang))}</span><span>{e(t['for'])} {e(spec_field(s, 'audience', lang))}</span></div>
<h1>{e(spec_field(s, 'name', lang))}</h1>
<p class="lead">{e(spec_field(s, 'blurb', lang))}</p>
</section>
<h2>{e(t['published'])}</h2>
<ul class="list">{''.join(issue_li(i, show_spec=False, ui=lang) for i in shown_by_spec[key]) or f'<li>{e(t["none"])}</li>'}</ul>
<p class="meta" style="margin-top:18px"><a href="{base(lang)}/{key}/feed.xml">{e(t['rss_spec'])}</a></p>"""
        write(out / key / "index.html", page(spec_field(s, "name", lang), body, lang=lang, desc=spec_field(s, "blurb", lang),
                                             url=f"{base(lang)}/{key}/", alt_url=f"{base(t['other_code'])}/{key}/", current=key))
        urls.append((f"{base(lang)}/{key}/", lst[0]["date"] if lst else date.today(), "weekly", "0.8"))
        write(out / key / "feed.xml", rss(lst, spec_field(s, "name", lang), f"{base(lang)}/{key}/", lang))

        for n, it in enumerate(lst):
            prev_i = lst[n + 1] if n + 1 < len(lst) else None
            next_i = lst[n - 1] if n > 0 else None
            write(out / key / f"{it['slug']}.html", issue_page(it, s, prev_i, next_i))
            urls.append((issue_url(it), it["date"], "never", "0.6"))

    write(out / "feed.xml", rss(issues, site_name, f"{base(lang)}/", lang))


def issue_li(i, show_spec=True, ui=None):
    lang = ui or i["lang"]
    s = CFG["specialties"][i["spec"]]
    spec = f'<span class="pill" style="--h:{s["hue"]}">{e(spec_field(s, "short", lang))}</span> ' if show_spec else ""
    audio = f" · 🎧 {T[lang]['audio_tag']}" if i["audio"] else ""
    if i["lang"] != lang:
        audio += " · " + ("Español" if i["lang"] == "es" else "English")
    return (f'<li><div class="meta">{spec}<span>{e(fecha_larga(i["date"], lang))}{audio}</span></div>'
            f'<a class="t" href="{issue_url(i)}">{e(i["title"])}</a>'
            f'<p>{e(i["summary"])}</p></li>')


def extra_block(it, key, hue):
    t = T[it["lang"]]
    txt = it["extras"].get(key)
    if not txt:
        return "", ""
    labels = {"whatsapp": (t["copy_wa"], t["wa_ready"]), "linkedin": (t["copy_li"], t["li_ready"]), "x": (t["copy_x"], t["x_ready"])}
    btn_label, summary = labels[key]
    btn = f'<button class="btn{"" if key == "whatsapp" else " secondary"}" style="--h:{hue}" onclick="copiar(\'x-{key}\')">{e(btn_label)}</button>'
    block = f'<details class="wa"><summary>{e(summary)}</summary><pre id="x-{key}">{e(txt)}</pre></details>'
    return btn, block


def issue_page(it, s, prev_i, next_i):
    lang = it["lang"]
    t = T[lang]
    url = issue_url(it)
    alt = alt_issue_url(it)
    audio_html = ""
    if it["audio"]:
        aurl = f"{SITE_URL}/audio/{it['audio'].name}"
        mins = f" · {round(float(it['audio_minutes']))} {t['min']}" if it["audio_minutes"] else ""
        audio_html = f"""<div class="audio" style="--h:{s['hue']}">
<strong>{t['audio']}{mins}</strong>
<audio controls preload="none" src="{aurl}"></audio>
<div class="dl"><a href="{aurl}" download>{e(t['download'])}</a><a href="https://wa.me/?text={e(html.escape(it['title']))}%20{aurl}" target="_blank" rel="noopener">{e(t['send_wa'])}</a></div>
</div>"""
    buttons, blocks = [], []
    for key in ("whatsapp", "linkedin", "x"):
        b, blk = extra_block(it, key, s["hue"])
        if b:
            buttons.append(b)
            blocks.append(blk)
    buttons.append(f'<button class="btn secondary" style="--h:{s["hue"]}" onclick="compartir({json.dumps(it["title"])},{json.dumps(url)})">{e(t["share"])}</button>')
    note = "" if it.get("alt") or lang == "en" else f'<p class="note">{e(t["only_in"])}</p>'
    nav = ""
    if prev_i or next_i:
        left = f'<a href="{issue_url(prev_i)}">← {e(fecha_larga(prev_i["date"], lang))}</a>' if prev_i else "<span></span>"
        right = f'<a href="{issue_url(next_i)}">{e(fecha_larga(next_i["date"], lang))} →</a>' if next_i else "<span></span>"
        nav = f'<div class="prevnext">{left}{right}</div>'
    ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": it["title"], "datePublished": it["date"].isoformat(), "inLanguage": lang,
        "author": {"@type": "Person", "name": CFG["author"]},
        "publisher": {"@type": "Organization", "name": cfg_field("site_name", lang)},
        "mainEntityOfPage": url, "description": it["summary"],
    }
    body = f"""<article class="issue" style="--h:{s['hue']}">
<div class="meta"><span class="pill">{e(spec_field(s, 'short', lang))}</span><time datetime="{it['date'].isoformat()}">{e(fecha_larga(it['date'], lang))}</time></div>
<h1>{e(it['title'])}</h1>
{note}
{audio_html}
<div class="tools">{''.join(buttons)}</div>
{it['body_html']}
<div class="extras">{''.join(blocks)}</div>
{nav}
</article>"""
    extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
    return page(it["title"], body, lang=lang, desc=it["summary"] or spec_field(s, "blurb", lang), url=url, alt_url=alt,
                current=it["spec"], extra_head=extra)


def rss(items, title, link, lang):
    out = [f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
           f'<title>{e(title)}</title><link>{e(link)}</link><description>{e(cfg_field("description", lang))}</description><language>{lang}</language>']
    for i in items:
        url = issue_url(i)
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
