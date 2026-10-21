"""Wrapper de la Comunitat Valenciana: CSV -> JSON.

Solo cambia el formato (no aplica mappings): cada fila del CSV pasa a ser un
objeto JSON con los mismos campos que la fuente. En la 2a entrega este wrapper
se expondrá como API REST que devuelve este mismo JSON.
"""
import csv
import json
import sys
from pathlib import Path

FICHERO = Path(__file__).resolve().parents[2] / "datos" / "cv" / "entidades_CV.csv"


def leer(ruta=FICHERO):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in fila.items()} for fila in csv.DictReader(f)]


if __name__ == "__main__":
    json.dump(leer(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
