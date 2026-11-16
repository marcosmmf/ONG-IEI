"""Enseña el contenido del almacén (almacen.db): para la demo, antes y después de la carga.

    python ver_bd.py              # filas de cada tabla + las entidades cargadas
    python ver_bd.py --fuente cat # solo las entidades de una fuente
    python ver_bd.py --limite 100 # cuántas entidades enseñar como máximo (por defecto 60)

Para navegar por la BD con ventanas: DB Browser for SQLite (https://sqlitebrowser.org), abrir almacen.db.
"""
import argparse

from ong.comun.almacen import Almacen


def recortar(texto, ancho):
    texto = "" if texto is None else str(texto)
    return texto if len(texto) <= ancho else texto[:ancho - 1] + "…"


def main():
    p = argparse.ArgumentParser(description="Ver el contenido del almacén de datos")
    p.add_argument("--fuente", choices=["cv", "cat", "can"], help="solo las entidades de esta fuente")
    p.add_argument("--limite", type=int, default=60, help="máximo de entidades a enseñar")
    args = p.parse_args()

    almacen = Almacen()
    con = almacen.con
    try:
        print("Tablas del almacén (almacen.db)")
        for tabla, que in (("provincia", "diccionario fijo"), ("ambito", "los 12 tipos, fijo"),
                           ("localidad", "se crean al cargar"), ("entidad", "se crean al cargar")):
            n = con.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]
            print(f"  {tabla:<10} {n:>5} filas   ({que})")

        por_fuente = con.execute("SELECT fuente, count(*) FROM entidad GROUP BY fuente ORDER BY fuente").fetchall()
        if not por_fuente:
            print("\nNo hay entidades cargadas: el almacén está vacío.")
            return
        print("\nEntidades por fuente: " + " · ".join(f"{f} {n}" for f, n in por_fuente))

        filtro, params = ("WHERE e.fuente = ?", (args.fuente.upper(),)) if args.fuente else ("", ())
        filas = con.execute(f"""
            SELECT e.fuente, e.nombre, a.nombre, l.nombre, p.nombre, e.codigo_postal, e.latitud, e.longitud
            FROM entidad e JOIN ambito a ON a.id = e.ambito
                 JOIN localidad l ON l.codigo = e.cod_localidad
                 JOIN provincia p ON p.codigo = l.cod_provincia
            {filtro} ORDER BY e.fuente, l.nombre, e.nombre""", params).fetchall()

        cab = (f"{'Fuente':<6} {'Nombre':<42} {'Tipo':<28} {'Localidad':<24} {'Provincia':<20} "
               f"{'CP':<5} {'Latitud':>10} {'Longitud':>11}")
        print("\n" + cab + "\n" + "─" * len(cab))
        for f, nombre, ambito, loc, prov, cp, lat, lon in filas[:args.limite]:
            print(f"{f:<6} {recortar(nombre, 42):<42} {recortar(ambito, 28):<28} {recortar(loc, 24):<24} "
                  f"{recortar(prov, 20):<20} {cp:<5} {lat:>10.5f} {lon:>11.5f}")
        if len(filas) > args.limite:
            print(f"… y {len(filas) - args.limite} más (usa --limite o DB Browser for SQLite para verlas todas)")
    finally:
        almacen.cerrar()


if __name__ == "__main__":
    main()
