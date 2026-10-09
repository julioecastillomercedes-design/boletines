#!/usr/bin/env python3
"""Regenera audios a partir de guiones/<esp>-<slug>(.en).guion.txt (sobrescribe audio/<esp>-<slug>(-en).mp3).
Uso: python tools/regen_audio.py <shard> <total>   (reparte los guiones entre trabajos en paralelo)"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importar_drive as d  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAT = re.compile(r"^(?P<esp>[a-z-]+?)-(?P<slug>\d{4}-\d{2}-\d{2}(?:-viene)?)(?P<en>\.en)?\.guion\.txt$")


def main(shard: int, total: int) -> None:
    files = sorted(p for p in (ROOT / "guiones").glob("*.guion.txt") if PAT.match(p.name))
    mine = [p for i, p in enumerate(files) if i % total == shard]
    print(f"shard {shard}/{total}: {len(mine)} guiones")
    for p in mine:
        m = PAT.match(p.name)
        if m["esp"] not in d.SPECS:
            print("  ! especialidad desconocida:", p.name)
            continue
        en = bool(m["en"])
        out = ROOT / "audio" / f"{m['esp']}-{m['slug']}{'-en' if en else ''}.mp3"
        tmp = out.with_suffix(".nuevo.mp3")
        if d.sintetizar(p, tmp, m["esp"], en):
            tmp.replace(out)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
