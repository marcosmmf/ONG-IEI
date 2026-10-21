"""Wrapper de Catalunya: XML -> JSON.

Cada <entitat> pasa a ser un objeto JSON {etiqueta: texto}. Las etiquetas vacías
(<web/>) quedan como "".
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

FICHERO = Path(__file__).resolve().parents[2] / "datos" / "cat" / "Entitats_ONGD_pretty.xml"


def leer(ruta=FICHERO):
    raiz = ET.parse(ruta).getroot()
    return [{campo.tag: (campo.text or "").strip() for campo in entitat} for entitat in raiz.iter("entitat")]


if __name__ == "__main__":
    json.dump(leer(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
