"""Carga del almacén de datos: wrapper -> JSON -> extractor -> almacén.

Ejemplos:
    python cargar.py --borrar              # solo vacía el almacén (inicio de la demo)
    python cargar.py todas                 # carga las 3 fuentes (geolocaliza solo con la caché)
    python cargar.py cv cat --borrar       # vacía el almacén y carga CV y CAT
    python cargar.py can --solo-cache      # sin Selenium: solo lo que ya esté en la caché (rápido, para probar)
    python cargar.py cat --limite 20       # solo los 20 primeros registros (para probar)
    python cargar.py todas --borrar --muestra   # demo: carga datos/muestra/ (12 por fuente)
    python cargar.py todas --muestra --abrir    # ... y abre el informe HTML en el navegador
    python cargar.py --vaciar-cache             # borra las cachés: la próxima carga usa Selenium y Gemini de verdad
    python cargar.py --restaurar-cache          # vuelve a poner las cachés de cache/backup/ (si Selenium o la IA fallan)

Cachés (cache/geocache.json de Selenium y cache/ambito_cache.json de Gemini), consulta a consulta:
  - lo que ya está guardado se aprovecha (no se vuelve a preguntar);
  - lo que no está se consulta en directo (Selenium / Gemini) y se guarda.
  La copia de seguridad está en cache/backup/ y no se toca nunca.

Al terminar se escribe en consola (con colores) el informe registro a registro (cargados con sus
datos, reparados con antes/después y motivo, avisos, rechazados con motivo y duplicados) y se
guarda en salida/informe.txt y salida/informe.html (con resumen y filtros); el detalle en JSON
queda en salida/<fuente>_informe.json.
"""
import argparse
import json
import shutil
import sys
import webbrowser
from pathlib import Path

from ong.comun import informe as I
from ong.comun.almacen import Almacen
from ong.comun.ambito_ia import CACHE_POR_DEFECTO as CACHE_IA
from ong.comun.geocoder import CACHE as CACHE_GEO, Geocoder
from ong.extractores import extractor_can, extractor_cat, extractor_cv

FUENTES = {
    "cv": (extractor_cv.wrapper, extractor_cv.ExtractorCV),
    "cat": (extractor_cat.wrapper, extractor_cat.ExtractorCAT),
    "can": (extractor_can.wrapper, extractor_can.ExtractorCAN),
}
SALIDA = Path(__file__).parent / "salida"
CACHES = (CACHE_GEO, CACHE_IA)
BACKUP = CACHE_GEO.parent / "backup"
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
    p.add_argument("--solo-cache", action="store_true",
                   help="no abrir Selenium: lo que no esté en la caché de coordenadas se rechaza")
    p.add_argument("--geo", action="store_true", help=argparse.SUPPRESS)   # antiguo: ahora es lo normal
    p.add_argument("--visible", action="store_true", help="ver el navegador de Selenium")
    p.add_argument("--limite", type=int, help="cargar solo los N primeros registros de cada fuente")
    p.add_argument("--muestra", action="store_true", help="cargar la muestra de datos/muestra/ (demo)")
    p.add_argument("--abrir", action="store_true", help="abrir salida/informe.html en el navegador al terminar")
    p.add_argument("--vaciar-cache", action="store_true",
                   help="borrar las cachés de Selenium y Gemini (la copia de cache/backup/ se conserva)")
    p.add_argument("--restaurar-cache", action="store_true", help="copiar las cachés de cache/backup/")
    args = p.parse_args()
    color = sys.stdout.isatty()                  # colores solo en la terminal, no al redirigir a un fichero
    if not args.fuentes and not (args.borrar or args.vaciar_cache or args.restaurar_cache):
        p.error("indica qué fuentes cargar (cv, cat, can o todas), o --borrar para vaciar el almacén")
    if args.vaciar_cache and args.restaurar_cache:
        p.error("--vaciar-cache y --restaurar-cache no se pueden usar a la vez")

    if args.vaciar_cache:
        BACKUP.mkdir(exist_ok=True)
        for f in CACHES:
            if f.exists() and not (BACKUP / f.name).exists():
                shutil.copy2(f, BACKUP / f.name)          # sin copia previa, se hace antes de borrar
            f.unlink(missing_ok=True)
        print("Cachés vaciadas: la próxima carga consultará Selenium y Gemini en directo "
              "(copia en cache/backup/; para volver: python cargar.py --restaurar-cache).")
    if args.restaurar_cache:
        for f in CACHES:
            if (BACKUP / f.name).exists():
                shutil.copy2(BACKUP / f.name, f)
                print(f"Caché restaurada: cache/{f.name}")
            else:
                print(f"No hay copia de cache/{f.name} en cache/backup/")

    fuentes = list(FUENTES) if "todas" in args.fuentes else args.fuentes
    almacen = Almacen()
    if args.borrar:
        almacen.borrar()
        print("Almacén vaciado (se conservan las tablas fijas: provincias y ámbitos).")
    if not fuentes:
        almacen.cerrar()
        return

    # Lo que está en la caché se aprovecha; lo que falta se consulta con Selenium (salvo --solo-cache).
    geocoder = Geocoder(usar_web=not args.solo_cache, visible=args.visible)
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
            texto.append(I.texto(informe))                       # sin colores, para el .txt
            print(I.texto(informe, color=color))
    finally:
        geocoder.cerrar()
        almacen.cerrar()

    print(I._c("═══ Resumen de la carga ═══", "negrita", color=color))
    print(I.tabla_resumen(informes, color=color))
    final = "═══ Resumen de la carga ═══\n" + I.tabla_resumen(informes)
    (SALIDA / "informe.txt").write_text("\n".join(texto) + "\n" + final, encoding="utf-8")
    pagina = SALIDA / "informe.html"
    pagina.write_text(I.html(informes, "Informe de carga" + (" (muestra)" if args.muestra else "")),
                      encoding="utf-8")
    print("Informe guardado en salida/informe.txt y salida/informe.html · ver la BD: python ver_bd.py")
    if args.abrir:
        webbrowser.open(pagina.resolve().as_uri())


if __name__ == "__main__":
    main()
