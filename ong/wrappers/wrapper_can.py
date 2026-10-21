"""Wrapper de Canarias: la fuente ya es JSON (aunque el fichero se llame "csv").

Se mantiene como wrapper para que las tres fuentes tengan la misma interfaz:
leer() -> lista de diccionarios.
"""
import json
import sys
from pathlib import Path

FICHERO = Path(__file__).resolve().parents[2] / "datos" / "can" / "datos-abiertos-csv-segundo-trimestre26.json"


def leer(ruta=FICHERO):
    with open(ruta, encoding="utf-8-sig") as f:
        datos = json.load(f)
    return [{k: (v.strip() if isinstance(v, str) else v) for k, v in d.items()} for d in datos]


if __name__ == "__main__":
    json.dump(leer(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
