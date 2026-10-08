#!/usr/bin/env python3
"""
Importa al repositorio los números que los bots dejan en Google Drive ("Portal boletines/pendientes")
y genera el audio que falte a partir de los guiones. Lo ejecuta GitHub Actions cada hora.

Entrada (carpeta descargada de Drive, argumento 1):
  <esp>-<AAAA-MM-DD>.v.md            boletín en español VERIFICADO
  <esp>-<AAAA-MM-DD>.en.v.md         boletín en inglés VERIFICADO
  <esp>-<AAAA-MM-DD>.v.guion.txt     guion verificado del noticiero en español (un párrafo por bloque)
  <esp>-<AAAA-MM-DD>.en.v.guion.txt  guion verificado del noticiero en inglés
  (Los borradores sin ".v" que dejan los bots NO se publican.)
Salida: issues/<esp>/<fecha>(.en).md y audio/<esp>-<fecha>(-en).mp3
Nunca sobrescribe un número o un audio que ya esté en el repositorio (ni los borra de Drive).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SPECS = set(CFG["specialties"])
# Solo se publican archivos VERIFICADOS (sufijo ".v"): el verificador los crea tras cotejar
# cada cifra, fecha y población con su fuente. Los borradores de los bots (sin ".v") se ignoran.
NAME = re.compile(r"^(?P<esp>[a-z-]+?)-(?P<fecha>\d{4}-\d{2}-\d{2})(?P<en>\.en)?\.v(?P<guion>\.guion\.txt|\.md)$")

# Líneas que nunca deben llegar a la página pública
LIMPIAR = re.compile(r"^(audio_url:.*|.*claude\.ai/artifact.*|Versión en audio.*|Audio version.*|"
                     r"Enviado por el Dr\..*|Sent by Dr\..*|Boletín completo en el correo|Full bulletin in the email)\s*$",
                     re.M | re.I)


def limpiar(texto: str) -> str:
    texto = LIMPIAR.sub("", texto)
    return re.sub(r"\n{3,}", "\n\n", texto)


def voz(esp: str, en: bool):
    if en:
        return CFG.get("voice_en", "am_michael"), "en-us"
    return CFG["specialties"][esp].get("voice_es", "em_alex"), "es"


_kokoro = None


def sintetizar(guion: Path, destino: Path, esp: str, en: bool) -> bool:
    global _kokoro
    import soundfile as sf
    if _kokoro is None:
        import urllib.request
        base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
        for nombre in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
            if not (ROOT / nombre).exists():
                print(f"  descargando {nombre}…")
                urllib.request.urlretrieve(base + nombre, ROOT / nombre)
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(ROOT / "kokoro-v1.0.onnx"), str(ROOT / "voices-v1.0.bin"))
    v, lang = voz(esp, en)
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", guion.read_text(encoding="utf-8")) if p.strip()]
    if len(parrafos) < 3:
        print(f"  ! guion demasiado corto: {guion.name}")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lista = []
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", "0.8", str(tmp / "gap.wav")], check=True)
        for i, p in enumerate(parrafos):
            samples, sr = _kokoro.create(" ".join(p.split()), voice=v, speed=1.0, lang=lang)
            f = tmp / f"seg_{i:02d}.wav"
            sf.write(str(f), samples, sr)
            lista += [f"file '{f}'", f"file '{tmp / 'gap.wav'}'"]
        (tmp / "list.txt").write_text("\n".join(lista) + "\n")
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
                        "-af", "loudnorm=I=-16:TP=-1.5", "-ac", "1", "-ar", "24000",
                        "-codec:a", "libmp3lame", "-b:a", "48k", str(destino)], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(destino)], capture_output=True, text=True).stdout.strip() or 0)
    if dur < 60:
        print(f"  ! audio demasiado corto ({dur:.0f} s), descartado: {destino.name}")
        destino.unlink(missing_ok=True)
        return False
    print(f"  + audio {destino.name} ({dur / 60:.1f} min, voz {v})")
    return True


def descargar(entrada: Path) -> None:
    """Descarga la carpeta pública de Drive si el paso anterior del workflow no lo hizo."""
    if entrada.exists() and any(p.is_file() for p in entrada.rglob("*")):
        return
    url = os.environ.get("DRIVE_PENDIENTES")
    if not url:
        return
    import gdown
    entrada.mkdir(parents=True, exist_ok=True)
    try:
        gdown.download_folder(url=url, output=str(entrada), quiet=True)
    except Exception as ex:
        print(f"  ! no se pudo leer la carpeta de Drive: {ex}")
    print("Archivos en Drive:", sorted(p.name for p in entrada.rglob("*") if p.is_file()) or "ninguno")


def main(entrada: Path) -> None:
    descargar(entrada)
    nuevos, guiones = [], []
    for f in sorted(entrada.rglob("*")):
        m = NAME.match(f.name)
        if not f.is_file() or not m or m["esp"] not in SPECS:
            continue
        esp, fecha, en = m["esp"], m["fecha"], bool(m["en"])
        if m["guion"] == ".md":
            dest = ROOT / "issues" / esp / f"{fecha}{'.en' if en else ''}.md"
            if dest.exists():
                continue
            texto = f.read_text(encoding="utf-8")
            if not texto.startswith("---") or f"specialty: {esp}" not in texto:
                print(f"  ! encabezado inválido, se ignora: {f.name}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(limpiar(texto), encoding="utf-8")
            nuevos.append(dest.relative_to(ROOT))
            print(f"  + número {dest.relative_to(ROOT)}")
        else:
            guiones.append((f, esp, fecha, en))

    audios = 0
    for f, esp, fecha, en in guiones:
        mp3 = ROOT / "audio" / f"{esp}-{fecha}{'-en' if en else ''}.mp3"
        if mp3.exists():
            continue
        try:
            audios += sintetizar(f, mp3, esp, en)
        except Exception as ex:  # un audio fallido no detiene la publicación del resto
            print(f"  ! error de audio en {f.name}: {ex}")
    print(f"Importados: {len(nuevos)} números, {audios} audios")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
