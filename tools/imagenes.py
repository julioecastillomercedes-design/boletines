#!/usr/bin/env python3
"""Genera las imágenes de marca: og-en.png (vista previa en redes) y las portadas del podcast (3000x3000)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BG, INK, INK2, ACC, LINE = (249, 247, 243), (29, 26, 22), (95, 92, 88), (184, 66, 47), (216, 212, 204)
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANSB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def f(path, size):
    return ImageFont.truetype(path, size)


def logo(d, x, y, s):
    d.rounded_rectangle([x, y, x + s, y + s], radius=s * 0.18, fill=ACC)
    h = s * 0.1
    for i, w in enumerate((0.66, 0.66, 0.42)):
        yy = y + s * (0.28 + i * 0.25)
        d.rounded_rectangle([x + s * 0.17, yy - h / 2, x + s * (0.17 + w), yy + h / 2], radius=h / 2, fill=BG)


def og(name, title, tagline, bullets, url, credit):
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 14], fill=ACC)
    logo(d, 70, 100, 91)
    d.text((186, 108), title, font=f(SERIF, 64), fill=INK)
    d.text((188, 190), tagline, font=f(SANS, 28), fill=INK2)
    for i, b in enumerate(bullets):
        d.text((70, 272 + i * 52), "•  " + b, font=f(SANS, 33), fill=INK)
    d.line([70, 536, 1130, 536], fill=LINE, width=2)
    d.text((70, 555), url, font=f(SANSB, 34), fill=ACC)
    cw = d.textlength(credit, font=f(SANS, 24))
    d.text((1130 - cw, 562), credit, font=f(SANS, 24), fill=INK2)
    im.save(ROOT / "static" / name, optimize=True)


def cover(name, title, lines, credit):
    S = 3000
    im = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, S, 60], fill=ACC)
    logo(d, 1200, 420, 600)
    ft = f(SERIF, 300 if len(title) < 14 else 250)
    tw = d.textlength(title, font=ft)
    d.text(((S - tw) / 2, 1200), title, font=ft, fill=INK)
    for i, ln in enumerate(lines):
        fl = f(SANS, 140)
        lw = d.textlength(ln, font=fl)
        d.text(((S - lw) / 2, 1700 + i * 210), ln, font=fl, fill=INK2)
    fc = f(SANSB, 120)
    cw = d.textlength(credit, font=fc)
    d.text(((S - cw) / 2, 2600), credit, font=fc, fill=ACC)
    im.convert("RGB").save(ROOT / "static" / name, quality=88)


og("og-en.png", "MedBulletins", "What is new and verified in each specialty",
   ["15 specialties, with critical appraisal", "5–7 minute audio newscast", "Free, no account needed"],
   "boletinesmedicos.com/en", "Curated by Aura Celeste Vascular")
cover("podcast-en.jpg", "MedBulletins", ["Verified medical updates", "15 specialties · audio newscast"],
      "Curated by Aura Celeste Vascular")
cover("podcast-es.jpg", "Boletines Médicos", ["Actualización médica verificada", "15 especialidades · noticiero"],
      "Curado por Aura Celeste Vascular")
print("ok")
