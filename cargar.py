"""Carga del almacén de datos: wrapper -> JSON -> extractor -> almacén.

Ejemplos:
    python cargar.py todas                 # carga las 3 fuentes (geolocaliza solo con la caché)
    python cargar.py cv cat --borrar       # vacía el almacén y carga CV y CAT
    python cargar.py can --geo             # usa Selenium para lo que no esté en caché (lento)
    python cargar.py cat --limite 20       # solo los 20 primeros registros (para probar)
"""
import argparse
import json
from pathlib import Path

from ong.comun.almacen import Almacen
from ong.comun.geocoder import Geocoder
from ong.extractores import extractor_can, extractor_cat, extractor_cv

FUENTES = {
    "cv": (extractor_cv.wrapper, extractor_cv.ExtractorCV),
    "cat": (extractor_cat.wrapper, extractor_cat.ExtractorCAT),
    "can": (extractor_can.wrapper, extractor_can.ExtractorCAN),
}
SALIDA = Path(__file__).parent / "salida"


def main():
    p = argparse.ArgumentParser(description="Carga del almacén de datos de ONG")
    p.add_argument("fuentes", nargs="+", choices=[*FUENTES, "todas"])
    p.add_argument("--borrar", action="store_true", help="vaciar el almacén antes de cargar")
    p.add_argument("--geo", action="store_true", help="usar Selenium para lo que no esté en caché")
    p.add_argument("--visible", action="store_true", help="ver el navegador de Selenium")
    p.add_argument("--limite", type=int, help="cargar solo los N primeros registros de cada fuente")
    args = p.parse_args()

    fuentes = list(FUENTES) if "todas" in args.fuentes else args.fuentes
    almacen = Almacen()
    geocoder = Geocoder(usar_web=args.geo, visible=args.visible)
    SALIDA.mkdir(exist_ok=True)
    if args.borrar:
        almacen.borrar()

    try:
        for nombre in fuentes:
            wrapper, Extractor = FUENTES[nombre]
            registros = wrapper()                                        # 1) wrapper: fuente -> JSON
            (SALIDA / f"{nombre}_wrapper.json").write_text(
                json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")

            informe = Extractor(almacen, geocoder).cargar(registros, args.limite)   # 2) extractor
            (SALIDA / f"{nombre}_informe.json").write_text(
                json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{informe['fuente']:>3}: leídos {informe['leidos']}, cargados {informe['cargados']}, "
                  f"reparados {len(informe['reparados'])}, rechazados {len(informe['rechazados'])}, "
                  f"duplicados {informe['duplicados']}   -> salida/{nombre}_informe.json")
    finally:
        geocoder.cerrar()
        almacen.cerrar()


if __name__ == "__main__":
    main()
