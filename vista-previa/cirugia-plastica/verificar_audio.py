#!/usr/bin/env python3
"""Transcribe los 4 MP3 de cirugía plástica con Whisper local (gratuito) y los compara con sus guiones.

Uso (en un equipo con acceso a los modelos de Whisper, p. ej. el Mac):
    pip install faster-whisper
    python3 vista-previa/cirugia-plastica/verificar_audio.py            # modelo "small"
    python3 vista-previa/cirugia-plastica/verificar_audio.py medium     # más preciso, más lento
Ejecutar desde la raíz del repositorio. Escribe en vista-previa/cirugia-plastica/transcripciones/:
  <audio>.transcripcion.txt  (segmentos con marcas de tiempo mm:ss)
  INFORME_AUDIO.txt          (por audio: palabras omitidas/añadidas/cambiadas, cifras, fechas, negaciones y final)
No usa ningún servicio de pago ni envía audio a internet (solo descarga el modelo la primera vez).
"""
import difflib, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "transcripciones"
PARES = [  # (mp3, guion, idioma, final exacto)
    ("cirugia-plastica-2026-10-16.mp3", "cirugia-plastica-2026-10-16.guion.txt", "es", "Gracias por escuchar."),
    ("cirugia-plastica-2026-10-16-en.mp3", "cirugia-plastica-2026-10-16.en.guion.txt", "en", "Thank you for listening."),
    ("cirugia-plastica-2026-10-16-viene.mp3", "cirugia-plastica-2026-10-16-viene.guion.txt", "es", "Gracias por escuchar."),
    ("cirugia-plastica-2026-10-16-viene-en.mp3", "cirugia-plastica-2026-10-16-viene.en.guion.txt", "en", "Thank you for listening."),
]
# Palabras cuya pérdida o cambio altera el sentido: cifras, meses, negaciones
NUM = {"es": "cero uno una dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno veintidos veintitres veinticuatro veinticinco veintiseis veintisiete veintiocho veintinueve treinta cuarenta cincuenta sesenta setenta ochenta noventa cien ciento cientos doscientos trescientos cuatrocientos quinientos seiscientos setecientos ochocientos novecientos mil coma por ciento primero",
       "en": "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand point percent first second third fourth fifth sixth seventh eighth eleventh twelfth thirteenth fifteenth sixteenth eighteenth twentieth twentyeighth twentyninth thirtieth thirtyfirst"}
MESES = {"es": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
         "en": "january february march april may june july august september october november december"}
NEG = {"es": "no ni sin nunca tampoco", "en": "not no nor without never"}


def norm(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    t = t.replace("-", " ")
    return re.findall(r"[a-z0-9]+", t)


def mmss(s):
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def comparar(guion, trans, lang):
    g, t = norm(guion), norm(trans)
    clave = set((NUM[lang] + " " + MESES[lang] + " " + NEG[lang]).split())
    sm = difflib.SequenceMatcher(a=g, b=t, autojunk=False)
    lineas, criticos = [], []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            continue
        dice, oye = " ".join(g[a1:a2]), " ".join(t[b1:b2])
        ctx = " ".join(g[max(0, a1 - 6):a1])
        tipo = {"delete": "OMITIDO", "insert": "AÑADIDO", "replace": "CAMBIADO"}[op]
        critico = bool(clave & set(g[a1:a2] + t[b1:b2]) or any(w.isdigit() for w in g[a1:a2] + t[b1:b2]))
        l = f"  [{tipo}{' · CRÍTICO' if critico else ''}] …{ctx} | guion: «{dice}» | audio: «{oye}»"
        lineas.append(l)
        if critico:
            criticos.append(l)
    return sm.ratio(), len(g), len(t), lineas, criticos


def main():
    modelo = sys.argv[1] if len(sys.argv) > 1 else "small"
    from faster_whisper import WhisperModel
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    OUT.mkdir(exist_ok=True)
    inf = [f"INFORME DE CORRESPONDENCIA AUDIO-GUION · Whisper local '{modelo}' (faster-whisper) · sin servicios de pago",
           "Advertencia: una transcripción automática puede fallar por sí misma; cada diferencia debe confirmarse escuchando el minuto indicado.",
           "Esto comprueba correspondencia de palabras, no la calidad de la pronunciación.", ""]
    for mp3, gn, lang, final in PARES:
        segs, info = m.transcribe(str(ROOT / "audio" / mp3), language=lang, beam_size=5, word_timestamps=False,
                                  condition_on_previous_text=False)
        segs = list(segs)
        texto = " ".join(s.text.strip() for s in segs)
        (OUT / f"{mp3}.transcripcion.txt").write_text(
            "\n".join(f"[{mmss(s.start)}–{mmss(s.end)}] {s.text.strip()}" for s in segs) + "\n", encoding="utf-8")
        guion = (ROOT / "guiones" / gn).read_text(encoding="utf-8")
        r, ng, nt, lineas, crit = comparar(guion, texto, lang)
        fin_ok = norm(texto)[-len(norm(final)):] == norm(final)
        inf += [f"== {mp3}  ↔  guiones/{gn}",
                f"Duración {mmss(info.duration)} · palabras guion {ng} · palabras transcritas {nt} · similitud {r:.3f}",
                f"Final exacto «{final}»: {'SÍ' if fin_ok else 'NO — revisar'}",
                f"Diferencias críticas (cifras, fechas, negaciones): {len(crit)}"] + crit + \
               [f"Todas las diferencias ({len(lineas)}):"] + lineas + [""]
    (OUT / "INFORME_AUDIO.txt").write_text("\n".join(inf) + "\n", encoding="utf-8")
    print("\n".join(inf))


if __name__ == "__main__":
    main()
