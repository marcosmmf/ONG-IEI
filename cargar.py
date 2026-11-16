"""Carga del almacén de datos: wrapper -> JSON -> extractor -> almacén.

Ejemplos:
    python cargar.py --borrar              # solo vacía el almacén (inicio de la demo)
    python cargar.py todas                 # carga las 3 fuentes (geolocaliza solo con la caché)
    python cargar.py cv cat --borrar       # vacía el almacén y carga CV y CAT
    python cargar.py can --geo             # usa Selenium para lo que no esté en caché (lento)
    python cargar.py cat --limite 20       # solo los 20 primeros registros (para probar)
    python cargar.py todas --borrar --muestra   # demo: carga datos/muestra/ (12 por fuente)

Al terminar se escribe en consola el informe registro a registro (cargados con sus datos,
reparados con antes/después y motivo, avisos, rechazados con motivo y duplicados) y se guarda
en salida/informe.txt; el detalle en JSON queda en salida/<fuente>_informe.json.
"""
import argparse
import json
from pathlib import Path

from ong.comun import informe as I
from ong.comun.almacen import Almacen
from ong.comun.geocoder import Geocoder
from ong.extractores import extractor_can, extractor_cat, extractor_cv

FUENTES = {
    "cv": (extractor_cv.wrapper, extractor_cv.ExtractorCV),
    "cat": (extractor_cat.wrapper, extractor_cat.ExtractorCAT),
    "can": (extractor_can.wrapper, extractor_can.ExtractorCAN),
}
SALIDA = Path(__file__).parent / "salida"
# Muestra representativa para la demo: mismo formato y nombre que el fichero original de cada
# fuente, con casos que se cargan, se reparan y se rechazan.
MUESTRA = {
    "cv": extractor_cv.FICHERO.parents[1] / "muestra" / "cv" / extractor_cv.FICHERO.name,
    "cat": extractor_cat.FICHERO.parents[1] / "muestra" / "cat" / extractor_cat.FICHERO.name,
    "can": extractor_can.FICHERO.parents[1] / "muestra" / "can" / extractor_can.FICHERO.name,
}


def main():
    p = argparse.ArgumentParser(description="Carga del almacén de datos de ONG")
    p.add_argument("fuentes", nargs="*", choices=[*FUENTES, "todas"],
                   help="fuentes a cargar (ninguna + --borrar = solo vaciar el almacén)")
    p.add_argument("--borrar", action="store_true", help="vaciar el almacén antes de cargar")
    p.add_argument("--geo", action="store_true", help="usar Selenium para lo que no esté en caché")
    p.add_argument("--visible", action="store_true", help="ver el navegador de Selenium")
    p.add_argument("--limite", type=int, help="cargar solo los N primeros registros de cada fuente")
    p.add_argument("--muestra", action="store_true", help="cargar la muestra de datos/muestra/ (demo)")
    args = p.parse_args()
    if not args.fuentes and not args.borrar:
        p.error("indica qué fuentes cargar (cv, cat, can o todas), o --borrar para vaciar el almacén")

    fuentes = list(FUENTES) if "todas" in args.fuentes else args.fuentes
    almacen = Almacen()
    if args.borrar:
        almacen.borrar()
        print("Almacén vaciado (se conservan las tablas fijas: provincias y ámbitos).")
    if not fuentes:
        almacen.cerrar()
        return

    geocoder = Geocoder(usar_web=args.geo, visible=args.visible)
    SALIDA.mkdir(exist_ok=True)
    informes, texto = [], []
    try:
        for nombre in fuentes:
            wrapper, Extractor = FUENTES[nombre]
            registros = wrapper(MUESTRA[nombre]) if args.muestra else wrapper()   # 1) wrapper: fuente -> JSON
            (SALIDA / f"{nombre}_wrapper.json").write_text(
                json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")

            informe = Extractor(almacen, geocoder).cargar(registros, args.limite)   # 2) extractor
            (SALIDA / f"{nombre}_informe.json").write_text(
                json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
            informes.append(informe)
            texto.append(I.texto(informe))
            print(texto[-1])
    finally:
        geocoder.cerrar()
        almacen.cerrar()

    final = "═══ Resumen de la carga ═══\n" + I.tabla_resumen(informes)
    print(final)
    (SALIDA / "informe.txt").write_text("\n".join(texto) + "\n" + final, encoding="utf-8")
    print("Informe guardado en salida/informe.txt · ver la BD: python ver_bd.py")


if __name__ == "__main__":
    main()
