"""Ficheros para la evaluación de la 1ª entrega: Informe_XXX.txt y Datos_XXX.xlsx (XXX = CV, CAT, CAN).

Para cada fuente se parte de una BD vacía, se carga solo esa fuente y se exporta:
  - Informe_XXX.txt: (i) nº de registros insertados, (ii) reparados con error y acción correctiva,
    (iii) rechazados con el error; después, el detalle registro a registro.
  - Datos_XXX.xlsx: las tablas del almacén (entidad, localidad, provincia, ámbito), una hoja por tabla.

    python entrega1.py                       # muestra de la demo, solo con la caché (sin Selenium ni Gemini)
    python entrega1.py --salida "Entrega 1"  # carpeta de salida (por defecto salida/entrega1)

OJO: deja almacen.db con la última fuente cargada (CAN).
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import json
import sqlite3

from ong.comun import informe as I

RAIZ = Path(__file__).resolve().parent
NOMBRES = I.NOMBRES


def _v(v):
    return I._valor(v)


def informe_txt(inf):
    f = inf["fuente"]
    regs = inf["registros"]
    reparados = [r for r in regs if r["resultado"] == "cargado" and r["reparaciones"]]
    rechazados = [r for r in regs if r["resultado"] == "rechazado"]
    duplicados = [r for r in regs if r["resultado"] == "duplicado"]
    avisos = [r for r in regs if r["resultado"] == "cargado" and r["incidencias"]]
    L = [f"INFORME DE CARGA — {NOMBRES[f]} ({f})",
         f"Generado: {datetime.now():%d/%m/%Y %H:%M} · Carga a partir de una BD vacía (solo esta fuente)",
         "=" * 78, "",
         "RESUMEN",
         f"  Registros leídos de la fuente ...........: {inf['leidos']}",
         f"  (i)   Registros correctos insertados .....: {inf['cargados']}"
         f"   (de ellos, {len(reparados)} tras ser reparados)",
         f"  (ii)  Registros reparados ...............: {len(reparados)}",
         f"  (iii) Registros rechazados ..............: {len(rechazados)}",
         f"  Duplicados (no se insertan otra vez) ....: {len(duplicados)}",
         f"  Comprobación: {inf['cargados']} insertados + {len(duplicados)} duplicados + "
         f"{len(rechazados)} rechazados = {inf['cargados'] + len(duplicados) + len(rechazados)} leídos",
         ""]

    L += ["-" * 78, f"(ii) REGISTROS REPARADOS ({len(reparados)})", "-" * 78]
    for r in reparados or []:
        L.append(f"[{r['id_origen']}] {r['nombre']}")
        for rep in r["reparaciones"]:
            L.append(f"    Campo:             {rep['campo']}")
            L.append(f"    Error y corrección: {rep['motivo'] or 'valor incorrecto en la fuente'}")
            L.append(f"    Valor:             {_v(rep['antes'])} (fuente) → {_v(rep['despues'])} (cargado)")
        L.append("")
    if not reparados:
        L += ["    (ninguno)", ""]

    L += ["-" * 78, f"(iii) REGISTROS RECHAZADOS ({len(rechazados)})", "-" * 78]
    for r in rechazados:
        L += [f"[{r['id_origen']}] {r['nombre']}", f"    Error: {r['motivo']}", ""]
    if not rechazados:
        L += ["    (ninguno)", ""]

    L += ["-" * 78, f"DUPLICADOS ({len(duplicados)})", "-" * 78]
    for r in duplicados:
        L += [f"[{r['id_origen']}] {r['nombre']}",
              "    Ya cargado antes (mismo nombre, dirección y localidad): no se inserta otra vez", ""]
    if not duplicados:
        L += ["    (ninguno)", ""]

    L += ["-" * 78, f"AVISOS EN REGISTROS INSERTADOS ({len(avisos)})", "-" * 78]
    for r in avisos:
        L.append(f"[{r['id_origen']}] {r['nombre']}")
        L += [f"    {inc['campo']}: {inc['motivo']}" for inc in r["incidencias"]]
        L.append("")
    if not avisos:
        L += ["    (ninguno)", ""]

    L += ["=" * 78, "DETALLE REGISTRO A REGISTRO (en el orden de la fuente)", "=" * 78, "", I.texto(inf)]
    return "\n".join(L)


def _tabla(con, titulo, sql):
    cur = con.execute(sql)
    cab = [d[0] for d in cur.description]
    filas = [["" if x is None else " ".join(str(x).split()) for x in fila] for fila in cur.fetchall()]
    anchos = [max([len(c)] + [len(f[i]) for f in filas]) for i, c in enumerate(cab)]
    linea = lambda vals: " | ".join(v.ljust(a) for v, a in zip(vals, anchos)).rstrip()
    sep = "-+-".join("-" * a for a in anchos)
    return [f"TABLA {titulo} ({len(filas)} filas)", linea(cab), sep] + [linea(f) for f in filas] + [""]


HOJAS = [   # (hoja, descripción, consulta)
    ("entidad", "Tabla entidad", "SELECT * FROM entidad ORDER BY cod_entidad"),
    ("localidad", "Tabla localidad", "SELECT * FROM localidad ORDER BY codigo"),
    ("ambito", "Tabla fija (precargada por el esquema)", "SELECT * FROM ambito ORDER BY id"),
    ("provincia", "Tabla fija (precargada por el esquema)", "SELECT * FROM provincia ORDER BY codigo"),
]


def datos_xlsx(bd, fuente, destino):
    """Una hoja por tabla: cabecera fija, filtros y columnas largas con ajuste de texto."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    con = sqlite3.connect(bd)
    wb = Workbook()
    wb.remove(wb.active)
    try:
        for hoja, desc, sql in HOJAS:
            cur = con.execute(sql)
            cab = [d[0] for d in cur.description]
            filas = cur.fetchall()
            ws = wb.create_sheet(hoja)
            ws.append([f"{NOMBRES[fuente]} ({fuente}) · {desc} · {len(filas)} filas"])
            ws["A1"].font = Font(bold=True, size=12)
            ws.append(cab)
            for c in ws[2]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="2F5597")
            for fila in filas:
                ws.append(list(fila))
            for i, col in enumerate(cab, 1):
                largo = max([len(col)] + [len(str(f[i - 1])) for f in filas if f[i - 1] is not None])
                ancho = min(max(largo + 2, 8), 45)
                ws.column_dimensions[get_column_letter(i)].width = ancho
                if largo > 45:
                    for fila in ws.iter_rows(min_row=3, min_col=i, max_col=i):
                        fila[0].alignment = Alignment(wrap_text=True, vertical="top")
            ws.freeze_panes = "B3"
            if filas:
                ws.auto_filter.ref = f"A2:{get_column_letter(len(cab))}{len(filas) + 2}"
        wb.save(destino)
    finally:
        con.close()


def datos_txt(bd, fuente):
    con = sqlite3.connect(bd)
    try:
        L = [f"DATOS DEL ALMACÉN — {NOMBRES[fuente]} ({fuente})",
             f"Generado: {datetime.now():%d/%m/%Y %H:%M} · Contenido de las tablas tras cargar solo esta fuente "
             "en una BD vacía (SQLite, almacen.db)",
             "=" * 78, ""]
        L += _tabla(con, "entidad", "SELECT * FROM entidad ORDER BY cod_entidad")
        L += _tabla(con, "localidad", "SELECT * FROM localidad ORDER BY codigo")
        L += ["Vista: entidad con sus claves ajenas resueltas (ámbito, localidad y provincia)", ""]
        L += _tabla(con, "entidad ⋈ ambito ⋈ localidad ⋈ provincia", """
            SELECT e.cod_entidad, e.nombre, a.nombre AS ambito, e.direccion, e.codigo_postal,
                   l.nombre AS localidad, p.nombre AS provincia, e.latitud, e.longitud
            FROM entidad e JOIN ambito a ON a.id = e.ambito JOIN localidad l ON l.codigo = e.cod_localidad
                 JOIN provincia p ON p.codigo = l.cod_provincia ORDER BY e.cod_entidad""")
        L += ["Tablas fijas (precargadas por el esquema, no dependen de la fuente)", ""]
        L += _tabla(con, "ambito", "SELECT * FROM ambito ORDER BY id")
        L += _tabla(con, "provincia", "SELECT * FROM provincia ORDER BY codigo")
        return "\n".join(L)
    finally:
        con.close()


def main():
    p = argparse.ArgumentParser(description="Genera Informe_XXX.txt y Datos_XXX.xlsx de la 1ª entrega")
    p.add_argument("--salida", default=str(RAIZ / "salida" / "entrega1"))
    p.add_argument("--reales", action="store_true", help="datos reales en vez de la muestra de la demo")
    p.add_argument("--con-selenium", action="store_true", help="consultar Selenium/Gemini lo que no esté en caché")
    args = p.parse_args()
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    for f in ("cv", "cat", "can"):
        # BD vacía de verdad: además de borrar las filas, se reinician los contadores AUTOINCREMENT
        # (sqlite_sequence), para que cod_entidad y localidad.codigo empiecen otra vez en 1.
        if (RAIZ / "almacen.db").exists():
            con = sqlite3.connect(RAIZ / "almacen.db")
            con.executescript("DELETE FROM entidad; DELETE FROM localidad; DELETE FROM sqlite_sequence;")
            con.close()
        cmd = [sys.executable, "cargar.py", f, "--borrar"]
        cmd += [] if args.reales else ["--muestra"]
        cmd += [] if args.con_selenium else ["--solo-cache"]
        subprocess.run(cmd, cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)
        inf = json.loads((RAIZ / "salida" / f"{f}_informe.json").read_text(encoding="utf-8"))
        F = f.upper()
        (out / f"Informe_{F}.txt").write_text(informe_txt(inf), encoding="utf-8")
        datos_xlsx(RAIZ / "almacen.db", F, out / f"Datos_{F}.xlsx")
        print(f"{F}: {inf['cargados']} insertados · {len(inf['reparados'])} reparados · "
              f"{len(inf['rechazados'])} rechazados · {inf['duplicados']} duplicados")
    print(f"Ficheros en {out}")


if __name__ == "__main__":
    main()
