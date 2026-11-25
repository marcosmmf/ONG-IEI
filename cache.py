"""Gestión de las cachés de Selenium y Gemini, separadas por modo (demo / completa).

    python cache.py                              estado de las dos cachés y de sus copias
    python cache.py vaciar        demo|completa  borra la caché (la próxima carga consulta en directo)
    python cache.py restaurar     demo|completa  vuelve a poner la copia de seguridad
    python cache.py guardar-copia demo|completa  copia la caché actual a su backup/ (sustituye la anterior)
    python cache.py borrar-copia  demo|completa  elimina la copia de seguridad

demo = cache/demo/ (la usa ./arrancar.sh --muestra y cargar.py --muestra)
completa = cache/completa/ (la usan ./arrancar.sh y cargar.py con los datos completos)
"""
import argparse

from ong.comun import caches

ACCIONES = {
    "vaciar": caches.vaciar,
    "restaurar": caches.restaurar,
    "guardar-copia": caches.guardar_copia,
    "borrar-copia": caches.borrar_copia,
}


def ver_estado():
    def n(x):
        return "—" if x is None else ("ilegible" if x < 0 else str(x))
    print(f"{'Caché':<10} {'Fichero':<32} {'Guardadas':>9} {'En la copia':>12}")
    for m, f, actual, copia in caches.estado():
        print(f"{m:<10} {caches.FICHEROS[f]:<32} {n(actual):>9} {n(copia):>12}")
    print("\n— = no existe. Carpetas: cache/demo/ y cache/completa/ (copia en backup/ dentro de cada una).")


def main():
    p = argparse.ArgumentParser(description="Cachés de Selenium y Gemini (demo / completa)")
    p.add_argument("accion", nargs="?", choices=["estado", *ACCIONES], default="estado")
    p.add_argument("modo", nargs="?", choices=list(caches.MODOS), help="demo o completa")
    args = p.parse_args()
    if args.accion == "estado":
        return ver_estado()
    if not args.modo:
        p.error(f"indica qué caché: python cache.py {args.accion} demo|completa")
    print(ACCIONES[args.accion](args.modo))
    print()
    ver_estado()


if __name__ == "__main__":
    main()
