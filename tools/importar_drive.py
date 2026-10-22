#!/usr/bin/env python3
"""
Importa al repositorio los números que los bots dejan en Google Drive ("Portal boletines/pendientes")
y genera el audio que falte a partir de los guiones. Lo ejecuta GitHub Actions cada hora.

Entrada (carpeta descargada de Drive, argumento 1):
  <esp>-<AAAA-MM-DD>.v.md            boletín en español VERIFICADO
  <esp>-<AAAA-MM-DD>.en.v.md         boletín en inglés VERIFICADO
  <esp>-<AAAA-MM-DD>.v.guion.txt     guion verificado del noticiero en español (un párrafo por bloque)
  <esp>-<AAAA-MM-DD>.en.v.guion.txt  guion verificado del noticiero en inglés
  <esp>-<AAAA-MM-DD>-viene.v.md (y .en.v.md, .v.guion.txt, .en.v.guion.txt): sección «Lo que viene»
  (Los borradores sin ".v" que dejan los bots NO se publican.)
Salida: issues/<esp>/<fecha>(.en).md y audio/<esp>-<fecha>(-en).mp3
Las correcciones usan .rAAAAMMDDTHHMMSSZ antes de .v, con el mismo sello en
los cuatro archivos ES/EN (texto y guion). Cada revisión es inmutable.
Los nombres antiguos solo crean números nuevos o confirman contenido idéntico.
No borra archivos de Drive. Los errores dejan intacta la publicación anterior.
"""
import json
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SPECS = set(CFG["specialties"])
# Solo se publican archivos VERIFICADOS (sufijo ".v"): el verificador los crea tras cotejar
# cada cifra, fecha y población con su fuente. Los borradores de los bots (sin ".v") se ignoran.
NAME = re.compile(r"^(?P<esp>[a-z-]+?)-(?P<fecha>\d{4}-\d{2}-\d{2})(?P<viene>-viene)?(?P<en>\.en)?(?:\.r(?P<revision>\d{8}T\d{6}Z))?\.v(?P<guion>\.guion\.txt|\.md)$")

# Líneas que nunca deben llegar a la página pública
LIMPIAR = re.compile(r"^(audio_url:.*|.*claude\.ai/artifact.*|Versión en audio.*|Audio version.*|"
                     r"Enviado por el Dr\..*|Sent by Dr\..*|Boletín completo en el correo|Full bulletin in the email|"
                     r"</?(content|invoke|parameter|antml:[a-z_]+)\b[^>]*>)\s*$",
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
    """Enumera antes de descargar y conserva cada ID en su propio directorio.

    Dos archivos de Drive con el mismo nombre nunca pueden pisarse al bajar.
    Una descarga parcial falla antes de que main modifique el repositorio.
    """
    if entrada.exists():
        if any(entrada.iterdir()):
            raise ValueError(f"La carpeta de descarga debe estar vacía: {entrada}")
    url = os.environ.get("DRIVE_PENDIENTES")
    if not url:
        raise ValueError("Falta DRIVE_PENDIENTES")
    import gdown
    archivos = gdown.download_folder(url=url, skip_download=True, quiet=True,
                                    use_cookies=False, timeout=30)
    if archivos is None:
        raise RuntimeError("No se pudo enumerar Drive")
    entrada.mkdir(parents=True, exist_ok=True)
    for archivo in archivos:
        nombre = Path(archivo.path).name
        m = NAME.fullmatch(nombre)
        if not m or m["esp"] not in SPECS:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_-]+", archivo.id):
            raise ValueError("ID de Drive inválido")
        destino = entrada / archivo.id / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        resultado = gdown.download(id=archivo.id, output=str(destino), quiet=True,
                                   use_cookies=False, timeout=30)
        if resultado is None or not destino.is_file() or not destino.stat().st_size:
            raise RuntimeError(f"Descarga incompleta: {nombre}")
    print("Descarga de verificados completada")


def hash_texto(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def seleccionar(entrada):
    grupos = {}
    for f in sorted(entrada.rglob("*")):
        m = NAME.fullmatch(f.name)
        if not f.is_file() or not m or m["esp"] not in SPECS:
            continue
        fecha = m["fecha"] + (m["viene"] or "")
        revision = m["revision"] or ""
        if revision:
            momento = datetime.strptime(revision, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            if momento > datetime.now(timezone.utc):
                raise ValueError(f"Revisión futura: {f.name}")
        clave = (m["esp"], fecha)
        tipo = (bool(m["en"]), m["guion"] == ".guion.txt")
        texto = f.read_text(encoding="utf-8")
        if not tipo[1]:
            encabezado = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
            campos = dict(re.findall(r"^(specialty|date):\s*([^\n]+)$", encabezado[1], re.M)) if encabezado else {}
            if campos.get("specialty") != m["esp"] or campos.get("date") != m["fecha"]:
                raise ValueError(f"Encabezado inválido: {f.name}")
            texto = limpiar(texto)
        elif len([p for p in re.split(r"\n\s*\n", texto) if p.strip()]) < 3:
            raise ValueError(f"Guion demasiado corto: {f.name}")
        versiones = grupos.setdefault(clave, {})
        candidatos = versiones.setdefault(revision, {})
        if tipo in candidatos and candidatos[tipo] != texto:
            raise ValueError(f"Verificados contradictorios con el mismo nombre: {f.name}")
        candidatos[tipo] = texto
    seleccion = []
    for (esp, fecha), versiones in sorted(grupos.items()):
        revision = max(versiones)
        archivos = versiones[revision]
        if revision and set(archivos) != {(False, False), (True, False), (False, True), (True, True)}:
            raise ValueError(f"Revisión incompleta: {esp}/{fecha} r{revision}; se necesitan los cuatro archivos ES/EN")
        seleccion.append((esp, fecha, revision, archivos))
    return seleccion


def main(entrada: Path) -> None:
    if not entrada.is_dir():
        raise ValueError(f"No existe la carpeta de verificados: {entrada}")
    registro_path = ROOT / "issues" / ".revisiones.json"
    registro = json.loads(registro_path.read_text()) if registro_path.exists() else {}
    textos, audios = [], []
    # Validar y planificar todo antes de tocar archivos publicados.
    for esp, fecha, revision, archivos in seleccionar(entrada):
        clave = f"{esp}/{fecha}"
        anterior = registro.get(clave, {})
        if anterior and revision < anterior["revision"]:
            print(f"  = revisión antigua ignorada: {clave}")
            continue
        hashes = {f"{'en' if en else 'es'}/{'guion' if guion else 'texto'}": hash_texto(t)
                  for (en, guion), t in archivos.items()}
        if anterior and revision == anterior["revision"] and hashes != anterior["hashes"]:
            raise ValueError(f"Revisión ya publicada modificada: {clave} r{revision}; emita un sello nuevo")
        for (en, guion), texto in archivos.items():
            if guion:
                dest = ROOT / "guiones" / f"{esp}-{fecha}{'.en' if en else ''}.guion.txt"
            else:
                dest = ROOT / "issues" / esp / f"{fecha}{'.en' if en else ''}.md"
            distinto = not dest.exists() or dest.read_text(encoding="utf-8") != texto
            if distinto and dest.exists() and not revision:
                raise ValueError(f"Corrección sin sello de revisión: {dest.relative_to(ROOT)}; use .rAAAAMMDDTHHMMSSZ.v")
            if distinto and anterior and revision == anterior["revision"]:
                raise ValueError(f"Cambio local posterior en {dest.relative_to(ROOT)}; requiere revisión nueva")
            if distinto:
                textos.append((dest, texto))
            if guion:
                mp3 = ROOT / "audio" / f"{esp}-{fecha}{'-en' if en else ''}.mp3"
                if distinto or not mp3.exists():
                    audios.append((mp3, texto, esp, en))
        if revision:
            registro[clave] = {"revision": revision, "hashes": hashes}

    # Sintetizar primero en temporales. Un fallo conserva textos, guiones y MP3.
    with tempfile.TemporaryDirectory(dir=ROOT) as carpeta:
        temporal = Path(carpeta)
        preparados = []
        for i, (dest, texto, esp, en) in enumerate(audios):
            guion = temporal / f"{i}.guion.txt"
            mp3 = temporal / f"{i}.mp3"
            guion.write_text(texto, encoding="utf-8")
            if not sintetizar(guion, mp3, esp, en) or not mp3.is_file() or not mp3.stat().st_size:
                raise RuntimeError(f"No se pudo generar audio: {dest.name}")
            preparados.append((dest, mp3))
        for i, (dest, texto) in enumerate(textos):
            f = temporal / f"texto-{i}"
            f.write_text(texto, encoding="utf-8")
            preparados.append((dest, f))
        contenido = json.dumps(registro, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if registro and (not registro_path.exists() or registro_path.read_text() != contenido):
            f = temporal / "registro.json"
            f.write_text(contenido, encoding="utf-8")
            preparados.append((registro_path, f))
        for dest, f in preparados:
            dest.parent.mkdir(parents=True, exist_ok=True)
            f.replace(dest)
    print(f"Importados: {len(textos)} textos/guiones, {len(audios)} audios")


if __name__ == "__main__":
    entrada = Path(sys.argv[1])
    if len(sys.argv) == 3 and sys.argv[2] == "--descargar":
        descargar(entrada)
    else:
        main(entrada)
