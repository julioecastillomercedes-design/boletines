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
        "curated": "Curado por", "footer": "Cada número resume publicaciones, guías, ensayos y avisos regulatorios verificados, con lectura crítica de su calidad (diseño, tamaño muestral, financiación). Es material informativo para profesionales; no sustituye la lectura de la fuente original ni el juicio clínico.",
        "only_in": "Este número solo está disponible en español.", "audio_tag": "audio",
        "no_en_yet": "The English edition of this issue is not available. Showing the Spanish original.",
        "bulletin": "Boletín",
        "sub_title": "Reciba cada número por correo",
        "sub_text": "Gratis. Un correo por número, con el texto completo y el enlace al audio. Sin publicidad ni cesión de datos; se da de baja con un solo mensaje.",
        "sub_btn": "Suscribirme por correo",
        "sub_subject": "Suscripción a Boletines Médicos",
        "sub_body": "Hola. Quiero recibir por correo los boletines de estas especialidades: (escriba aquí las que le interesan, o «todas»).\n\nNombre:\nCiudad o institución (opcional):",
        "sub_hint": "Se abrirá su programa de correo con el mensaje ya redactado; solo tiene que enviarlo.",
        "sponsor": "Patrocinio y colaboración institucional",
        "subscribe": "Suscribirse",
        "contact": "Contacto", "about": "Quiénes somos y cómo trabajamos",
        "listen": "Escuchar el boletín", "listen_short": "Escuchar", "pause": "Pausa",
        "listen_sub": "Noticiero en audio",
        "audio_banner": "Cada boletín tiene su versión en audio: pulse ▶ Escuchar y óigalo en el carro o entre consultas.",
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
        "sub_title": "Get every issue by email",
        "sub_text": "Free. One email per issue, with the full text and the audio link. No advertising, no data sharing; unsubscribe with a single message.",
        "sub_btn": "Subscribe by email",
        "sub_subject": "Subscription to MedBulletins",
        "sub_body": "Hello. I would like to receive the bulletins for these specialties by email: (write the ones you want here, or \"all\").\n\nName:\nCity or institution (optional):",
        "sub_hint": "Your email program will open with the message already written; just send it.",
        "sponsor": "Sponsorship and institutional partnerships",
        "subscribe": "Subscribe",
        "contact": "Contact", "about": "About us and how we work",
        "listen": "Listen to this issue", "listen_short": "Listen", "pause": "Pause",
        "listen_sub": "Audio newscast",
        "audio_banner": "Every bulletin comes with an audio version: press ▶ Listen and hear it in the car or between patients.",
    },
}


def fecha_larga(d: date, lang="es") -> str:
    if lang == "en":
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def base(lang):
    return SITE_URL if lang == "es" else f"{SITE_URL}/en"


def seg(key, lang):
    """Segmento de URL de la especialidad: clave en español; en la edición inglesa, su slug en inglés."""
    return CFG["specialties"][key].get("slug_en", key) if lang == "en" else key


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


# URL con paréntesis equilibrados dentro (DOI de Lancet "(26)01861-1", "(utis)"...)
URL_RE = re.compile(r"(?<![\"'>(\]])(https?://(?:[^\s<>()\[\]]|\([^\s<>()\[\]]*\))+)")
TRAIL = ".,;:!?\u00bb\u201d'\""


def _link(m):
    url = m.group(1)
    tail = ""
    while url and url[-1] in TRAIL:
        tail = url[-1] + tail
        url = url[:-1]
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>{tail}'


def linkify(text: str) -> str:
    return URL_RE.sub(_link, text)


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
    # El crédito oficial es "Aura Celeste" (sin "Vascular"), aunque un bot lo escriba con el nombre antiguo
    meta, body = parse_frontmatter(f.read_text(encoding="utf-8").replace("Aura Celeste Vascular", "Aura Celeste")
                                       .replace("enlaces a las fuentes primarias", "enlaces a sus fuentes")
                                       .replace("links to the primary sources", "links to their sources")
                                       .replace("links to primary sources", "links to their sources"))
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
.sub{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px;margin:26px 0 8px;font-family:system-ui,sans-serif}
.sub h2{border:0;margin:0 0 .3em;padding:0;font-size:1.15rem}
.sub p{margin:.3em 0 .8em;color:var(--ink-2);font-size:.95rem}
.sub a.btn{display:inline-block;font:600 .95rem system-ui,sans-serif;background:var(--accent);color:#fff;border-radius:999px;padding:10px 18px;text-decoration:none}
.sub small{display:block;margin-top:8px;color:var(--ink-3);font-size:.8rem}
article.static{font-size:1.02rem}article.static h2{margin-top:1.6em}article.static ul{padding-left:1.2em}
.mini{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:10px;font:.85rem system-ui,sans-serif}
.mini audio{flex:1 1 240px;height:36px}
.listen{--hue:var(--h);display:flex;align-items:center;gap:14px;background:var(--accent-soft);border:2px solid var(--accent);border-radius:var(--radius);padding:14px 16px;margin:18px 0 10px;font-family:system-ui,sans-serif}
.listen .play{flex:0 0 auto;width:64px;height:64px;border-radius:50%;border:0;background:var(--accent);color:#fff;cursor:pointer;display:grid;place-items:center;box-shadow:0 4px 14px hsl(var(--h,20) 55% 30% / .35);animation:pulso 2.4s ease-out 3}
.listen .play svg{width:28px;height:28px;fill:currentColor}
.listen .play .i-pause{display:none}.listen.on .play .i-play{display:none}.listen.on .play .i-pause{display:block}
.listen .lb{flex:1 1 auto;min-width:0}
.listen .lb strong{display:block;font-size:1.12rem;color:var(--ink);line-height:1.25}
.listen .lb span{display:block;font-size:.88rem;color:var(--ink-2);margin-bottom:6px}
.listen audio{width:100%;height:36px;display:block}
.listen .dl{font-size:.85rem;margin-top:6px;display:flex;gap:14px;flex-wrap:wrap}
.listen.sm{padding:10px 12px;gap:12px;margin:10px 0 0;border-width:1px}
.listen.sm .play{width:46px;height:46px;animation:none}
.listen.sm .play svg{width:20px;height:20px}
.listen.sm .lb strong{font-size:.98rem}
.card .listen.sm{margin-top:4px}
.abanner{display:flex;align-items:center;gap:10px;margin:16px 0 0;font:600 .98rem system-ui,sans-serif;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:9px 16px;width:fit-content;max-width:100%}
.abanner b{font-size:1.2rem}
@keyframes pulso{0%{box-shadow:0 0 0 0 hsl(var(--h,20) 55% 42% / .55)}100%{box-shadow:0 0 0 18px hsl(var(--h,20) 55% 42% / 0)}}
@media (prefers-reduced-motion:reduce){.listen .play{animation:none}}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:10px 16px;border-radius:999px;font:600 .9rem system-ui,sans-serif;opacity:0;transition:opacity .25s;pointer-events:none}
.toast.show{opacity:1}
@media (max-width:640px){header.top .wrap{padding:10px 16px;gap:8px}.navs{width:100%;min-width:0;flex-wrap:nowrap}nav.specs{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;min-width:0;flex:1 1 auto;padding:2px}nav.specs::-webkit-scrollbar{display:none}}
.hsub{display:inline-block;margin:12px 0 0 2px;font:600 .92rem system-ui,sans-serif}
@media (max-width:520px){body{font-size:16px}h2{font-size:1.2rem}}
"""


def js(lang):
    t = T[lang]
    return f"""
function copiar(id){{var t=document.getElementById(id).textContent;
navigator.clipboard.writeText(t).then(function(){{aviso({json.dumps(t['copied'])})}},function(){{aviso({json.dumps(t['copy_fail'])})}})}}
function tocar(b){{var w=b.closest('.listen'),a=w.querySelector('audio');
document.querySelectorAll('.listen audio').forEach(function(o){{if(o!==a&&!o.paused)o.pause()}});
if(a.paused){{a.play()}}else{{a.pause()}}}}
document.addEventListener('play',function(ev){{var w=ev.target.closest&&ev.target.closest('.listen');if(w){{w.classList.add('on');var b=w.querySelector('.play');b.setAttribute('aria-label',b.dataset.pause)}}}},true);
document.addEventListener('pause',function(ev){{var w=ev.target.closest&&ev.target.closest('.listen');if(w){{w.classList.remove('on');var b=w.querySelector('.play');b.setAttribute('aria-label',b.dataset.play)}}}},true);
function aviso(m){{var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(function(){{t.classList.remove('show')}},2200)}}
function compartir(title,url){{if(navigator.share){{navigator.share({{title:title,url:url}}).catch(function(){{}})}}else{{navigator.clipboard.writeText(url).then(function(){{aviso({json.dumps(t['link_copied'])})}})}}}}
"""


# ---------------------------------------------------------------- suscripción / estáticas

def sub_body(lang):
    names = "\n".join(f"- {spec_field(s, 'name', lang)}" for s in CFG["specialties"].values())
    if lang == "es":
        return ("Hola. Quiero recibir por correo los boletines de estas especialidades "
                "(borre las que no le interesen):\n" + names + "\n\nNombre:\nCiudad o institución (opcional):")
    return ("Hello. I would like to receive the bulletins for these specialties by email "
            "(delete the ones you do not want):\n" + names + "\n\nName:\nCity or institution (optional):")


def mailto(subject, body=""):
    from urllib.parse import quote
    return f"mailto:{CFG.get('contact_email', '')}?subject={quote(subject)}" + (f"&body={quote(body)}" if body else "")


def subscribe_block(lang, hue=None):
    t = T[lang]
    style = f' style="--h:{hue}"' if hue else ""
    return f"""<section class="sub" id="suscribir"{style}>
<h2>{e(t['sub_title'])}</h2>
<p>{e(t['sub_text'])}</p>
<a class="btn" href="{e(mailto(t['sub_subject'], sub_body(lang)))}">{e(t['sub_btn'])}</a>
<small>{e(t['sub_hint'])}</small>
</section>"""


def analytics_html():
    code = CFG.get("analytics_goatcounter")
    if not code:
        return ""
    return f'<script data-goatcounter="https://{code}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'


def static_pages(lang, urls):
    """Páginas fijas (patrocinio, suscripción) desde issues/paginas/<slug>.<lang>.md"""
    from datetime import date as _d
    t = T[lang]
    out = OUT if lang == "es" else OUT / "en"
    other = t["other_code"]
    pdir = ROOT / "issues" / "paginas"
    if not pdir.exists():
        return
    for f in sorted(pdir.glob(f"*.{lang}.md")):
        meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        slug = meta.get("slug") or f.name.split(".")[0]
        alt_slug = meta.get("alt_slug") or slug
        url = f"{base(lang)}/{slug}.html"
        alt_url = f"{base(other)}/{alt_slug}.html"
        html_body = f'<article class="static"><h1>{e(meta.get("title", slug))}</h1>{md_to_html(body)}</article>'
        if meta.get("subscribe"):
            html_body += subscribe_block(lang)
        write(out / f"{slug}.html", page(meta.get("title", slug), html_body, lang=lang,
                                         desc=meta.get("description", meta.get("title", slug)), url=url, alt_url=alt_url))
        urls.append((url, _d.today(), "monthly", "0.5"))


# ---------------------------------------------------------------- layout

def nav_html(lang, current=None):
    links = []
    for key, s in CFG["specialties"].items():
        cur = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{base(lang)}/{seg(key, lang)}/" style="--h:{s["hue"]}"{cur}>{e(spec_field(s, "short", lang))}</a>')
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
<meta property="og:image" content="{CFG['site_url']}/og-{lang}.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{CFG['site_url']}/og-{lang}.png">
<link rel="alternate" type="application/rss+xml" title="{e(site_name)}" href="{base(lang)}/feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23b8432f'/%3E%3Cpath d='M9 8h14M9 16h14M9 24h9' stroke='%23fff' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E">
{extra_head}
{analytics_html()}
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
<p><strong>{e(site_name)}</strong> · {e(t['curated'])} {e(CFG['author'])}{(', ' + e(cfg_field('author_role', lang))) if cfg_field('author_role', lang) else ''}.</p>
<p>{e(t['footer'])}</p>
<p><a href="{base(lang)}/{'como-trabajamos' if lang == 'es' else 'how-we-work'}.html">{e(t['about'])}</a> · <a href="{base(lang)}/{'suscribirse' if lang == 'es' else 'subscribe'}.html">{e(t['subscribe'])}</a> · <a href="{base(lang)}/{'patrocinio' if lang == 'es' else 'sponsorship'}.html">{e(t['sponsor'])}</a> · <a href="{e(mailto(t['contact'] + ' — ' + site_name))}">{e(t['contact'])}</a> · <a href="{base(lang)}/feed.xml">RSS</a> · <a href="{e(alt_url)}" hreflang="{other}">{e(t['other_lang'])}</a></p>
</div></footer>
<div id="toast" class="toast" role="status"></div>
<script>{js(lang)}</script>
</body>
</html>"""


# ---------------------------------------------------------------- pages

def issue_url(i, lang=None):
    lang = lang or i["lang"]
    return f"{base(lang)}/{seg(i['spec'], lang)}/{i['slug']}.html"


def alt_issue_url(i):
    """URL de la versión en el otro idioma; si no existe, la portada de la especialidad en ese idioma."""
    other = T[i["lang"]]["other_code"]
    if i.get("alt"):
        return issue_url(i["alt"])
    return f"{base(other)}/{seg(i['spec'], other)}/"


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
    for lang in LANGS:
        write((OUT if lang == "es" else OUT / "en") / "podcast.xml", podcast_feed(all_issues[lang], lang))
    write(OUT / "sitemap.xml", sitemap(urls))
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    write(OUT / ".nojekyll", "")
    for f in (ROOT_STATIC := OUT.parent / "static").glob("*"):
        shutil.copy2(f, OUT / f.name)
    if CFG.get("custom_domain"):
        write(OUT / "CNAME", CFG["custom_domain"] + "\n")
    print(f"OK: {len(all_issues['es'])} números ES, {len(all_issues['en'])} EN, {len(urls)} páginas -> {OUT}")


def build_lang(lang, issues, urls, fallback=()):
    t = T[lang]
    out = OUT if lang == "es" else OUT / "en"
    by_spec = {k: [i for i in issues if i["spec"] == k] for k in CFG["specialties"]}
    # En la edición inglesa, los números que solo existen en español se listan igualmente (enlazan al original).
    # Edición inglesa: solo números en inglés (nunca se enlaza contenido en español).
    shown = sorted(list(issues), key=lambda i: i["date"], reverse=True)
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
<h2><a href="{base(lang)}/{seg(key, lang)}/">{e(spec_field(s, 'name', lang))}</a></h2>
<p class="blurb">{e(spec_field(s, 'blurb', lang))}</p>
<div class="last">{last_html}</div>
{listen_block(last, lang, s['hue'], small=True) if last and last.get("audio") else ""}
</div>""")
    recent = "".join(issue_li(i, ui=lang) for i in shown[:6])
    home = f"""<section class="hero">
<h1>{e(cfg_field('site_tagline', lang))}</h1>
<p class="lead">{e(cfg_field('site_lead', lang))}</p>
<p class="abanner"><b>🎧</b><span>{e(t['audio_banner'])}</span></p>
<a class="hsub" href="#suscribir">✉ {e(t['sub_title'])} →</a>
</section>
<section class="grid">{''.join(cards)}</section>
{subscribe_block(lang)}
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
<p class="meta" style="margin-top:18px"><a href="{base(lang)}/{seg(key, lang)}/feed.xml">{e(t['rss_spec'])}</a></p>"""
        write(out / seg(key, lang) / "index.html", page(spec_field(s, "name", lang), body, lang=lang, desc=spec_field(s, "blurb", lang),
                                             url=f"{base(lang)}/{seg(key, lang)}/", alt_url=f"{base(t['other_code'])}/{seg(key, t['other_code'])}/", current=key))
        urls.append((f"{base(lang)}/{seg(key, lang)}/", lst[0]["date"] if lst else date.today(), "weekly", "0.8"))
        write(out / seg(key, lang) / "feed.xml", rss(lst, spec_field(s, "name", lang), f"{base(lang)}/{seg(key, lang)}/", lang))

        for n, it in enumerate(lst):
            prev_i = lst[n + 1] if n + 1 < len(lst) else None
            next_i = lst[n - 1] if n > 0 else None
            write(out / seg(key, lang) / f"{it['slug']}.html", issue_page(it, s, prev_i, next_i))
            urls.append((issue_url(it), it["date"], "never", "0.6"))

    if lang == "en":
        # Redirecciones desde las antiguas direcciones en español de la edición inglesa (/en/<clave>/...)
        for key in CFG["specialties"]:
            new = seg(key, "en")
            if new == key:
                continue
            targets = [("index.html", f"{base('en')}/{new}/")] + [
                (f"{it['slug']}.html", issue_url(it)) for it in by_spec[key]]
            for fname, target in targets:
                write(out / key / fname, redirect_html(target))

    write(out / "feed.xml", rss(issues, site_name, f"{base(lang)}/", lang))
    static_pages(lang, urls)


PLAY_SVG = ('<svg class="i-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'
            '<svg class="i-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>')


def audio_minutes(i):
    if i.get("audio_minutes"):
        return round(float(i["audio_minutes"]))
    if i.get("audio"):
        return max(1, round(i["audio"].stat().st_size * 8 / 48000 / 60))
    return None


def listen_block(i, lang, hue, small=False, extra=""):
    """Reproductor destacado: botón grande ▶ + reproductor nativo debajo."""
    t = T[lang]
    aurl = f"{SITE_URL}/audio/{i['audio'].name}"
    m = audio_minutes(i)
    sub = t["listen_sub"] + (f" · {m} {t['min']}" if m else "")
    title = t["listen_short"] if small else t["listen"]
    sp = spec_field(CFG["specialties"][i["spec"]], "short", lang)
    when = fecha_larga(i["date"], lang)
    lbl = f'{t["listen"]}: {sp}, {when}'
    plbl = f'{t["pause"]}: {sp}, {when}'
    return (f'<div class="listen{" sm" if small else ""}" style="--h:{hue}">'
            f'<button class="play" type="button" onclick="tocar(this)" aria-label="{e(lbl)}" data-play="{e(lbl)}" data-pause="{e(plbl)}">{PLAY_SVG}</button>'
            f'<div class="lb"><strong>🎧 {e(title)}</strong><span>{e(sub)}</span>'
            f'<audio controls preload="none" src="{aurl}"></audio>{extra}</div></div>')


def issue_li(i, show_spec=True, ui=None):
    lang = ui or i["lang"]
    s = CFG["specialties"][i["spec"]]
    spec = f'<span class="pill" style="--h:{s["hue"]}">{e(spec_field(s, "short", lang))}</span> ' if show_spec else ""
    audio = ""
    if i["lang"] != lang:
        audio += " · " + ("Español" if i["lang"] == "es" else "English")
    return (f'<li><div class="meta">{spec}<span>{e(fecha_larga(i["date"], lang))}{audio}</span></div>'
            f'<a class="t" href="{issue_url(i)}">{e(i["title"])}</a>'
            f'<p>{e(i["summary"])}</p>'
            + (listen_block(i, lang, s["hue"], small=True) if i["audio"] else "")
            + '</li>')


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
        dl = (f'<div class="dl"><a href="{aurl}" download>{e(t["download"])}</a>'
              f'<a href="https://wa.me/?text={e(html.escape(it["title"]))}%20{aurl}" target="_blank" rel="noopener">{e(t["send_wa"])}</a></div>')
        audio_html = listen_block(it, lang, s["hue"], extra=dl)
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
        "author": {"@type": "Organization", "name": CFG["author"]},
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
{subscribe_block(lang, s['hue'])}
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


PODCAST = {
    "es": {"title": "Boletines Médicos — noticiero", "cover": "podcast-es.jpg", "lang": "es",
           "desc": "Noticiero en audio de Boletines Médicos: lo nuevo y verificado en 15 especialidades médicas, con lectura crítica de cada estudio. "
                   "Material informativo para profesionales. Curado por Aura Celeste."},
    "en": {"title": "MedBulletins — audio newscast", "cover": "podcast-en.jpg", "lang": "en-us",
           "desc": "The MedBulletins audio newscast: what is new and verified across 15 medical specialties, with a critical reading of every study. "
                   "Informational material for health professionals. Curated by Aura Celeste."},
}
PODCAST_EMAIL = "auracelestevascular@gmail.com"


def podcast_feed(items, lang):
    """Feed de podcast (Apple Podcasts, Spotify, YouTube Music): un episodio por cada número con audio."""
    P = PODCAST[lang]
    self_url = f"{base(lang)}/podcast.xml"
    cover = f"{SITE_URL}/{P['cover']}"
    out = ['<?xml version="1.0" encoding="UTF-8"?>'
           '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
           'xmlns:atom="http://www.w3.org/2005/Atom" xmlns:podcast="https://podcastindex.org/namespace/1.0"><channel>',
           f'<title>{e(P["title"])}</title><link>{base(lang)}/</link><language>{P["lang"]}</language>',
           f'<atom:link href="{self_url}" rel="self" type="application/rss+xml"/>',
           f'<description>{e(P["desc"])}</description><itunes:summary>{e(P["desc"])}</itunes:summary>',
           '<itunes:author>Aura Celeste</itunes:author>',
           f'<itunes:owner><itunes:name>Aura Celeste</itunes:name><itunes:email>{PODCAST_EMAIL}</itunes:email></itunes:owner>',
           f'<itunes:image href="{cover}"/><image><url>{cover}</url><title>{e(P["title"])}</title><link>{base(lang)}/</link></image>',
           '<itunes:category text="Health &amp; Fitness"><itunes:category text="Medicine"/></itunes:category>',
           '<itunes:category text="Science"/>',
           '<itunes:explicit>false</itunes:explicit><itunes:type>episodic</itunes:type>',
           f'<copyright>Aura Celeste</copyright><podcast:locked>no</podcast:locked>']
    for i in items:
        if not i["audio"]:
            continue
        url = issue_url(i)
        size = i["audio"].stat().st_size
        secs = int(float(i["audio_minutes"]) * 60) if i.get("audio_minutes") else int(size * 8 / 48000)
        pub = datetime.combine(i["date"], datetime.min.time(), tzinfo=timezone.utc).strftime("%a, %d %b %Y 11:30:00 +0000")
        desc = f"{i['summary']} {url}"
        out.append(f"<item><title>{e(i['title'])}</title><link>{url}</link><guid isPermaLink=\"false\">{i['audio'].name}</guid>"
                   f"<pubDate>{pub}</pubDate><description>{e(desc)}</description><itunes:summary>{e(desc)}</itunes:summary>"
                   f'<enclosure url="{SITE_URL}/audio/{i["audio"].name}" length="{size}" type="audio/mpeg"/>'
                   f"<itunes:duration>{secs}</itunes:duration><itunes:explicit>false</itunes:explicit>"
                   f"<itunes:episodeType>full</itunes:episodeType></item>")
    out.append("</channel></rss>")
    return "".join(out)


def redirect_html(target):
    t = e(target)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved</title>'
            f'<link rel="canonical" href="{t}"><meta name="robots" content="noindex">'
            f'<meta http-equiv="refresh" content="0; url={t}"></head>'
            f'<body><p>This page has moved: <a href="{t}">{t}</a></p></body></html>')


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
