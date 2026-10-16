#!/usr/bin/env python3
"""Gestión de suscriptores de Boletines Médicos / MedBulletins.

Lógica determinista: la tarea programada solo trae los datos (Gmail, Drive) y envía los
mensajes que este programa decide. Aquí NO hay datos personales: el registro vive en una
carpeta privada de Google Drive y se pasa por la línea de órdenes.

Archivos del registro (CSV, UTF-8):
  suscriptores.csv  email,nombre,ciudad,especialidades,idioma,estado,fecha_solicitud,fecha_alta,fecha_baja,confirmacion,ultimo_mensaje
                    estado: activo | baja | revisar   (revisar = solicitud sin especialidades reconocibles)
                    confirmacion: fecha en que se envió la confirmación, o "pendiente"
  envios.csv        email,numero,fecha_envio,mensaje_id      (un número enviado a un suscriptor: nunca se repite)
  procesados.csv    mensaje_id,fecha,accion,email            (cada correo entrante se procesa una sola vez)
  config.json       {"distribucion_activa": false, "remitente": "...", "max_correos_por_ejecucion": 100,
                     "inicio_distribucion": "AAAA-MM-DD"}

Órdenes:
  procesar --registro DIR --solicitudes solicitudes.json --hoy AAAA-MM-DD --salida DIR [--repo DIR]
      Lee las solicitudes (correos), actualiza el registro y prepara los correos salientes en
      DIR/salientes.json. Si distribucion_activa es false, no prepara ningún correo saliente
      (las confirmaciones quedan "pendiente" y los números no se envían).
  cerrar --salida DIR --resultados resultados.json --hoy AAAA-MM-DD
      Anota en envios.csv / suscriptores.csv lo que de verdad se envió (con su id de Gmail).
"""
import argparse
import os
import csv
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("BOLETINES_REPO") or Path(__file__).resolve().parent.parent)
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SITE = CFG["site_url"].rstrip("/")

SUB_COLS = ["email", "nombre", "ciudad", "especialidades", "idioma", "estado", "fecha_solicitud",
            "fecha_alta", "fecha_baja", "confirmacion", "ultimo_mensaje"]
ENV_COLS = ["email", "numero", "fecha_envio", "mensaje_id"]
PROC_COLS = ["mensaje_id", "fecha", "accion", "email"]

ASUNTO_ALTA = {"es": "suscripcion a boletines medicos", "en": "subscription to medbulletins"}
EXCLUIDAS = {"hitos"}  # no se ofrecen en el formulario de suscripción
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def email_de(remitente: str) -> str:
    m = EMAIL_RE.search(remitente or "")
    return m.group(0).lower() if m else ""


# Nombres de especialidad (ES y EN) -> clave
NOMBRES = {}
for _k, _s in CFG["specialties"].items():
    if _k in EXCLUIDAS:
        continue
    for _f in ("name", "name_en", "short", "short_en"):
        if _s.get(_f):
            NOMBRES[norm(_s[_f])] = _k
CLAVES = [k for k in CFG["specialties"] if k not in EXCLUIDAS]


def leer_csv(path: Path, cols):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    return [{c: (r.get(c) or "").strip() for c in cols} for r in filas]


def escribir_csv(path: Path, cols, filas):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in filas:
            w.writerow({c: r.get(c, "") for c in cols})


# ------------------------------------------------------------------ clasificación de correos

def clasificar(msg):
    """Devuelve (accion, datos). accion: alta | baja | ignorar."""
    asunto = norm(re.sub(r"^\s*((re|fwd?|rv|res)\s*:\s*)+", "", msg.get("subject", ""), flags=re.I))
    cuerpo = msg.get("body", "") or ""
    email = email_de(msg.get("from", ""))
    if not email:
        return "ignorar", {"motivo": "sin remitente"}

    # Alta: el asunto exacto que genera el formulario del portal
    for lang, a in ASUNTO_ALTA.items():
        if asunto == a:
            especs, todas = [], False
            nombre = ciudad = ""
            for linea in cuerpo.splitlines():
                l = linea.strip()
                if l.startswith(("-", "•", "*")):
                    n = norm(l.lstrip("-•* "))
                    if n in ("todas", "all", "todas las especialidades", "all specialties"):
                        todas = True
                    elif n in NOMBRES and NOMBRES[n] not in especs:
                        especs.append(NOMBRES[n])
                m = re.match(r"^(nombre|name)\s*:\s*(.*)$", l, re.I)
                if m:
                    nombre = m.group(2).strip()[:80]
                m = re.match(r"^(ciudad o institucion|city or institution)[^:]*:\s*(.*)$", norm(l), re.I)
                if m:
                    ciudad = l.split(":", 1)[1].strip()[:120]
            if todas or len(especs) == len(CLAVES):
                especs = ["todas"]
            return "alta", {"email": email, "idioma": lang, "especialidades": especs,
                            "nombre": nombre, "ciudad": ciudad}

    # Baja: la palabra Baja / Unsubscribe en el asunto o como primera línea del mensaje
    primera = ""
    for linea in cuerpo.splitlines():
        if linea.strip() and not linea.strip().startswith(">"):
            primera = norm(linea)
            break
    pal = re.compile(r"^(baja|darme de baja|unsubscribe|cancelar suscripcion)\b")
    if pal.match(asunto) or pal.match(primera) or asunto in ("baja", "unsubscribe"):
        return "baja", {"email": email}
    return "ignorar", {"motivo": "no es una solicitud"}


# ------------------------------------------------------------------ números publicados

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
EXTRAS_RE = re.compile(r"^##\s*(Texto para WhatsApp|Text for WhatsApp|WhatsApp text|WhatsApp|"
                       r"Texto para LinkedIn|Text for LinkedIn|LinkedIn post|LinkedIn|"
                       r"Texto para X(?: \(Twitter\))?|Text for X(?: \(Twitter\))?|X post|X \(Twitter\)|X)\s*$", re.M | re.I)


def _frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            meta[k.strip()] = v
    return meta, m.group(2)


def _resumen(body):
    m = EXTRAS_RE.search(body)
    if m:
        body = body[:m.start()]
    lines = body.lstrip("\n").split("\n")
    first = lines[0].strip().upper()
    if first and first.startswith(("BOLETÍN", "BOLETIN", "BULLETIN", "NEWSLETTER")) and len(first) < 140:
        lines = lines[1:]
    for line in lines:
        t = line.strip()
        if len(t) > 80 and not t.startswith("#") and not t.startswith("http"):
            t = re.sub(r"\s+", " ", t)
            return (t[:220].rsplit(" ", 1)[0] + "…") if len(t) > 220 else t
    return ""


def fecha_publicacion(cfg, spec, d):
    """Día en que el número sale en el portal. Con la edición conjunta (config.json → edicion_conjunta),
    lo fechado desde «vigente_desde» se publica el día «dia» siguiente a su fecha (el mismo día si coincide)."""
    ed = cfg.get("edicion_conjunta") or {}
    if not ed.get("activa") or spec in ed.get("excepto", []):
        return d
    if ed.get("vigente_desde") and d < date.fromisoformat(ed["vigente_desde"]):
        return d
    dia = int(ed.get("dia", 1))
    if d.day <= dia:
        return d.replace(day=dia)
    return date(d.year + 1, 1, dia) if d.month == 12 else date(d.year, d.month + 1, dia)


def numeros_publicados(repo: Path):
    """Números publicados en el portal (sin «Lo que viene» ni Hitos), en ambos idiomas.
    Solo LEE los archivos del repositorio (issues/, audio/, config.json): no ejecuta su código."""
    cfg = json.loads((repo / "config.json").read_text(encoding="utf-8"))
    out = []
    for spec_dir in sorted((repo / "issues").iterdir()):
        spec = spec_dir.name
        if not spec_dir.is_dir() or spec not in cfg["specialties"] or spec in EXCLUIDAS:
            continue
        for f in sorted(spec_dir.glob("????-??-??.md")):
            slug = f.stem
            for lang, fp in (("es", f), ("en", spec_dir / f"{slug}.en.md")):
                if not fp.exists():
                    continue
                texto = fp.read_text(encoding="utf-8").replace("Aura Celeste Vascular", "Aura Celeste")
                if lang == "en":
                    texto = texto.replace("Boletines Médicos", "MedBulletins")
                meta, body = _frontmatter(texto)
                d = date.fromisoformat(meta["date"])
                fecha = (f"{MONTHS[d.month - 1]} {d.day}, {d.year}" if lang == "en"
                         else f"{d.day} de {MESES[d.month - 1]} de {d.year}")
                titulo = meta.get("title") or f"{'Bulletin' if lang == 'en' else 'Boletín'} — {fecha}"
                seg = spec if lang == "es" else cfg["specialties"][spec].get("slug_en", spec)
                audio = repo / "audio" / (f"{spec}-{slug}.mp3" if lang == "es" else f"{spec}-{slug}-en.mp3")
                out.append({
                    "id": f"{spec}/{slug}.{lang}", "spec": spec, "lang": lang, "date": d.isoformat(),
                    "pub": fecha_publicacion(cfg, spec, d).isoformat(),
                    "title": titulo, "summary": _resumen(body),
                    "url": f"{SITE}{'/en' if lang == 'en' else ''}/{seg}/{slug}.html",
                    "audio": f"{SITE}/audio/{audio.name}" if audio.exists() else "",
                })
    return out


# ------------------------------------------------------------------ textos de los correos

def nombres_especs(especs, lang):
    if especs == ["todas"]:
        return "todas las especialidades" if lang == "es" else "all specialties"
    campo = "name" if lang == "es" else "name_en"
    return ", ".join(CFG["specialties"][k][campo] for k in especs)


def correo_confirmacion(s):
    lang = s["idioma"]
    especs = s["especialidades"].split(";")
    if lang == "es":
        asunto = "Suscripción confirmada — Boletines Médicos"
        cuerpo = (f"Hola{(' ' + s['nombre']) if s['nombre'] else ''}:\n\n"
                  f"Hemos registrado su suscripción gratuita a Boletines Médicos.\n"
                  f"Especialidades: {nombres_especs(especs, 'es')}.\n\n"
                  "Desde ahora recibirá un correo cada vez que se publique un número de esas especialidades, "
                  "con el enlace a la página y al audio.\n\n"
                  "Para darse de baja, responda a cualquier correo con la palabra Baja.\n"
                  "Su dirección se usa solo para enviarle los boletines; no se comparte ni se vende.\n\n"
                  f"Boletines Médicos · {SITE}/")
    else:
        asunto = "Subscription confirmed — MedBulletins"
        cuerpo = (f"Hello{(' ' + s['nombre']) if s['nombre'] else ''},\n\n"
                  "Your free subscription to MedBulletins has been registered.\n"
                  f"Specialties: {nombres_especs(especs, 'en')}.\n\n"
                  "From now on you will receive an email each time an issue is published in those specialties, "
                  "with links to the page and the audio.\n\n"
                  "To unsubscribe, reply to any email with the word Unsubscribe.\n"
                  "Your address is used only to send you the bulletins; it is never shared or sold.\n\n"
                  f"MedBulletins · {SITE}/en/")
    return asunto, cuerpo


def correo_numeros(s, nums):
    lang = s["idioma"]
    bloques = []
    for n in nums:
        b = f"{n['title']}\n{n['summary']}\n{('Página' if lang == 'es' else 'Page')}: {n['url']}"
        if n["audio"]:
            b += f"\n{'Audio' if lang == 'es' else 'Audio'}: {n['audio']}"
        bloques.append(b)
    if lang == "es":
        asunto = (nums[0]["title"] if len(nums) == 1 else f"{len(nums)} números nuevos — Boletines Médicos")
        cuerpo = ("Nuevo en Boletines Médicos:\n\n" + "\n\n".join(bloques) +
                  "\n\n—\nRecibe este correo porque se suscribió en boletinesmedicos.com. "
                  "Para darse de baja, responda con la palabra Baja.\n"
                  "Material informativo para profesionales; no sustituye la fuente original ni el juicio clínico.")
    else:
        asunto = (nums[0]["title"] if len(nums) == 1 else f"{len(nums)} new issues — MedBulletins")
        cuerpo = ("New on MedBulletins:\n\n" + "\n\n".join(bloques) +
                  "\n\n—\nYou receive this email because you subscribed at boletinesmedicos.com/en/. "
                  "To unsubscribe, reply with the word Unsubscribe.\n"
                  "Informational material for professionals; it does not replace the primary source or clinical judgment.")
    return asunto, cuerpo


# ------------------------------------------------------------------ proceso

def procesar(registro: Path, solicitudes, hoy: str, salida: Path, numeros, config, prueba=False):
    subs = {s["email"]: s for s in leer_csv(registro / "suscriptores.csv", SUB_COLS) if s["email"]}
    envios = leer_csv(registro / "envios.csv", ENV_COLS)
    procesados = leer_csv(registro / "procesados.csv", PROC_COLS)
    vistos = {p["mensaje_id"] for p in procesados}
    propios = {norm(x) for x in config.get("cuentas_propias", [])}
    resumen = {"altas": [], "reactivadas": [], "actualizadas": [], "bajas": [], "revisar": [],
               "ignorados": 0, "repetidos": 0}

    for msg in sorted(solicitudes, key=lambda m: m.get("date", "")):
        mid = msg.get("id") or msg.get("message_id")
        if not mid or mid in vistos:
            resumen["repetidos"] += 1
            continue
        vistos.add(mid)
        es_prueba = bool(re.match(r"^\s*\[prueba\]", msg.get("subject", ""), re.I))
        if prueba != es_prueba:
            # Modo prueba: solo correos «[PRUEBA] …». Modo real: esos correos se ignoran.
            procesados.append({"mensaje_id": mid, "fecha": hoy, "accion": "ignorar", "email": email_de(msg.get("from", ""))})
            resumen["ignorados"] += 1
            continue
        if es_prueba:
            msg = dict(msg, subject=re.sub(r"^\s*\[prueba\]\s*", "", msg["subject"], flags=re.I), prueba=True)
        accion, d = clasificar(msg)
        email = d.get("email", "")
        if accion == "alta" and email in propios and not msg.get("prueba"):
            accion, d = "ignorar", {"motivo": "cuenta propia"}
        if accion == "alta":
            especs = d["especialidades"]
            previo = subs.get(email)
            fila = previo or {c: "" for c in SUB_COLS}
            fila.update({"email": email, "idioma": d["idioma"], "fecha_solicitud": hoy,
                         "ultimo_mensaje": mid})
            if d["nombre"]:
                fila["nombre"] = d["nombre"]
            if d["ciudad"]:
                fila["ciudad"] = d["ciudad"]
            if not especs:
                fila["estado"] = fila["estado"] if fila["estado"] == "activo" else "revisar"
                resumen["revisar"].append(email)
            else:
                fila["especialidades"] = ";".join(especs)
                if previo and previo["estado"] == "activo":
                    resumen["actualizadas"].append(email)
                elif previo:
                    resumen["reactivadas"].append(email)
                else:
                    resumen["altas"].append(email)
                if fila["estado"] != "activo":
                    fila["fecha_alta"] = hoy
                    fila["fecha_baja"] = ""
                fila["estado"] = "activo"
                fila["confirmacion"] = "pendiente"
            subs[email] = fila
        elif accion == "baja" and email in subs and subs[email]["estado"] != "baja":
            subs[email].update({"estado": "baja", "fecha_baja": hoy, "ultimo_mensaje": mid,
                                "confirmacion": subs[email]["confirmacion"] if subs[email]["confirmacion"] != "pendiente" else ""})
            resumen["bajas"].append(email)
        else:
            if accion == "baja":
                accion = "ignorar"  # baja de alguien que no está (o ya estaba de baja)
            resumen["ignorados"] += 1
        procesados.append({"mensaje_id": mid, "fecha": hoy, "accion": accion, "email": email})

    # Correos salientes (uno por destinatario; nunca varios destinatarios en el mismo mensaje)
    salientes = []
    retenidos = 0
    ya = {(e["email"], e["numero"]) for e in envios}
    inicio = config.get("inicio_distribucion") or hoy
    tope = int(config.get("max_correos_por_ejecucion", 100))
    for s in sorted(subs.values(), key=lambda x: x["email"]):
        if s["estado"] != "activo":
            continue
        if s["confirmacion"] == "pendiente":
            a, c = correo_confirmacion(s)
            salientes.append({"tipo": "confirmacion", "to": s["email"], "subject": a, "body": c, "numeros": []})
        especs = s["especialidades"].split(";")
        desde = max(s["fecha_alta"] or hoy, inicio)
        nuevos = [n for n in numeros
                  if n["lang"] == s["idioma"] and (especs == ["todas"] or n["spec"] in especs)
                  and n.get("pub", n["date"]) >= desde and n.get("pub", n["date"]) <= hoy and (s["email"], n["id"]) not in ya]
        if nuevos:
            nuevos.sort(key=lambda n: n["date"])
            a, c = correo_numeros(s, nuevos)
            salientes.append({"tipo": "numeros", "to": s["email"], "subject": a, "body": c,
                              "numeros": [n["id"] for n in nuevos]})
    if prueba:
        # En modo prueba solo se escribe a las cuentas propias, y el asunto lo dice
        salientes = [dict(o, subject="[PRUEBA] " + o["subject"]) for o in salientes if norm(o["to"]) in propios]
    n_procesados_previos = len(leer_csv(registro / "procesados.csv", PROC_COLS))
    if not config.get("distribucion_activa"):
        retenidos, salientes = len(salientes), []
    elif len(salientes) > tope:
        retenidos, salientes = len(salientes) - tope, salientes[:tope]

    salida.mkdir(parents=True, exist_ok=True)
    escribir_csv(salida / "suscriptores.csv", SUB_COLS, sorted(subs.values(), key=lambda x: x["email"]))
    escribir_csv(salida / "envios.csv", ENV_COLS, envios)
    escribir_csv(salida / "procesados.csv", PROC_COLS, procesados)
    (salida / "salientes.json").write_text(json.dumps(salientes, ensure_ascii=False, indent=1), encoding="utf-8")
    activos = [s for s in subs.values() if s["estado"] == "activo"]
    resumen.update({"activos": len(activos), "de_baja": sum(1 for s in subs.values() if s["estado"] == "baja"),
                    "salientes": len(salientes), "retenidos": retenidos,
                    "distribucion_activa": bool(config.get("distribucion_activa")),
                    "mensajes_nuevos_procesados": len(procesados) - n_procesados_previos,
                    "hay_cambios": len(procesados) != n_procesados_previos or bool(salientes)})
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return resumen, salientes


def cerrar(salida: Path, resultados, hoy: str):
    """resultados: [{"to":..., "tipo":..., "numeros":[...], "mensaje_id": "..."}] solo de lo enviado con éxito."""
    subs = {s["email"]: s for s in leer_csv(salida / "suscriptores.csv", SUB_COLS)}
    envios = leer_csv(salida / "envios.csv", ENV_COLS)
    ya = {(e["email"], e["numero"]) for e in envios}
    for r in resultados:
        if not r.get("mensaje_id"):
            continue
        if r["tipo"] == "confirmacion" and r["to"] in subs:
            subs[r["to"]]["confirmacion"] = hoy
        for n in r.get("numeros", []):
            if (r["to"], n) not in ya:
                envios.append({"email": r["to"], "numero": n, "fecha_envio": hoy, "mensaje_id": r["mensaje_id"]})
                ya.add((r["to"], n))
    escribir_csv(salida / "suscriptores.csv", SUB_COLS, sorted(subs.values(), key=lambda x: x["email"]))
    escribir_csv(salida / "envios.csv", ENV_COLS, envios)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="orden", required=True)
    p = sp.add_parser("procesar")
    p.add_argument("--registro", required=True)
    p.add_argument("--solicitudes", required=True)
    p.add_argument("--hoy", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--repo", default=str(ROOT))
    p.add_argument("--prueba", action="store_true", help="procesa solo correos «[PRUEBA] …» (registro de pruebas)")
    c = sp.add_parser("cerrar")
    c.add_argument("--salida", required=True)
    c.add_argument("--resultados", required=True)
    c.add_argument("--hoy", required=True)
    a = ap.parse_args()
    if a.orden == "procesar":
        reg = Path(a.registro)
        cfgp = reg / "config.json"
        config = json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {}
        sol = json.loads(Path(a.solicitudes).read_text(encoding="utf-8"))
        resumen, _ = procesar(reg, sol, a.hoy, Path(a.salida), numeros_publicados(Path(a.repo)), config, prueba=a.prueba)
        print(json.dumps(resumen, ensure_ascii=False))
    else:
        cerrar(Path(a.salida), json.loads(Path(a.resultados).read_text(encoding="utf-8")), a.hoy)
        print("ok")


if __name__ == "__main__":
    main()
