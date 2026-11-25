"""Consola de opciones para la demo:  python demo.py

Cada opción enseña el comando que ejecuta y lo lanza, así que todo se puede hacer igual
escribiendo los comandos a mano (cargar.py y ver_bd.py siguen funcionando como siempre).

Por defecto: datos de muestra y navegador de Selenium visible (una sola ventana de Chrome por
carga, y solo si hay que consultar algo que no está en la caché).
"""
import os
import shlex
import sqlite3
import subprocess
import sys
from pathlib import Path

from ong.comun import caches

RAIZ = Path(__file__).resolve().parent
BD = RAIZ / "almacen.db"
INFORME = RAIZ / "salida" / "informe.html"
NOMBRES = {"cv": "Comunitat Valenciana (CV)", "cat": "Catalunya (CAT)", "can": "Canarias (CAN)"}

opciones = {"muestra": True, "visible": True, "solo_cache": False}


# ------------------------------------------------------------------------------ estado
def entidades():
    if not BD.exists():
        return {}
    try:
        con = sqlite3.connect(BD)
        try:
            return dict(con.execute("SELECT fuente, count(*) FROM entidad GROUP BY fuente"))
        finally:
            con.close()
    except sqlite3.Error:
        return {}


def modo():
    return caches.modo(opciones["muestra"])         # caché demo con la muestra, completa con los datos reales


def cache(nombre):
    n = caches.contar(caches.carpeta(modo()) / nombre)
    return "vacía (se consulta en directo)" if n is None else ("ilegible" if n < 0 else f"{n} guardadas")


def cabecera():
    n = entidades()
    bd = " · ".join(f"{f.upper()} {n.get(f.upper(), 0)}" for f in NOMBRES)
    backup = "sí" if (caches.copia(modo()) / "geocache.json").exists() else "NO"
    print("══════════════ Demo Buscador de ONGD ══════════════")
    print(f" BD:       {bd} entidades")
    print(f" Caché {modo()}: Selenium {cache('geocache.json')} · Gemini {cache('ambito_cache.json')} · copia en backup: {backup}")
    print(f" Datos:    {'muestra (12 por fuente)' if opciones['muestra'] else 'REALES (fichero completo)'}"
          f" · navegador Selenium: {'visible' if opciones['visible'] else 'oculto'}"
          f" · Selenium: {'NO, solo caché (--solo-cache)' if opciones['solo_cache'] else 'sí, para lo que no esté en caché'}")
    print("───────────────────────────────────────────────────")


# ---------------------------------------------------------------------------- comandos
def ejecutar(args):
    """Enseña el comando (tal como se escribiría a mano) y lo ejecuta."""
    print("\n$ " + " ".join(shlex.quote(a) for a in args) + "\n", flush=True)
    comando = [sys.executable if a == "python" else a for a in args]
    try:
        subprocess.run(comando, cwd=RAIZ)
    except FileNotFoundError as e:
        print(f"No se pudo ejecutar: {e}")


def cargar(fuente):
    args = ["python", "cargar.py", fuente]
    if opciones["muestra"]:
        args.append("--muestra")
    if opciones["solo_cache"]:
        args.append("--solo-cache")
    elif opciones["visible"]:
        args.append("--visible")
    args.append("--abrir")
    ejecutar(args)


def ver_bd():
    fuente = input("¿Qué fuente? (cv, cat, can; Enter = todas): ").strip().lower()
    if fuente and fuente not in NOMBRES:
        print("Fuente no válida.")
        return
    ejecutar(["python", "ver_bd.py"] + (["--fuente", fuente] if fuente else []))


def abrir_informe():
    if not INFORME.exists():
        print("Todavía no hay informe: haz antes una carga.")
        return
    abrir = {"darwin": "open", "win32": "start"}.get(sys.platform, "xdg-open")
    if sys.platform == "win32":
        print("\n$ start salida\\informe.html\n")
        os.startfile(INFORME)                      # noqa: S606 (solo Windows)
    else:
        ejecutar([abrir, "salida/informe.html"])


def cambiar(clave):
    opciones[clave] = not opciones[clave]
    if clave == "muestra" and not opciones["muestra"]:
        print("Ojo: con los datos reales se usa la caché completa. Lo que no esté en ella lo consultan\n"
              "Selenium (y Gemini en CAT): la primera vez son miles de registros y tarda horas.")


MENU = [
    ("1", "Ver la base de datos", ver_bd),
    ("2", "Vaciar la base de datos", lambda: ejecutar(["python", "cargar.py", "--borrar"])),
    ("3", f"Cargar {NOMBRES['cv']}", lambda: cargar("cv")),
    ("4", f"Cargar {NOMBRES['cat']}", lambda: cargar("cat")),
    ("5", f"Cargar {NOMBRES['can']}", lambda: cargar("can")),
    ("6", "Cargar las tres fuentes", lambda: cargar("todas")),
    ("7", "Reabrir el último informe (HTML)", abrir_informe),
    ("8", "Vaciar la caché (Selenium y Gemini en directo)", lambda: ejecutar(["python", "cache.py", "vaciar", modo()])),
    ("9", "Restaurar la caché desde backup", lambda: ejecutar(["python", "cache.py", "restaurar", modo()])),
    ("10", "Cambiar datos: muestra ↔ reales", lambda: cambiar("muestra")),
    ("11", "Cambiar navegador de Selenium: visible ↔ oculto", lambda: cambiar("visible")),
    ("12", "Cambiar Selenium: usarlo ↔ solo caché", lambda: cambiar("solo_cache")),
    ("0", "Salir", None),
]


def main():
    acciones = {clave: accion for clave, _, accion in MENU}
    while True:
        print("\033[2J\033[H", end="")              # limpia la pantalla
        cabecera()
        for clave, texto, _ in MENU:
            print(f" {clave:>2}. {texto}")
        try:
            eleccion = input("\nOpción: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if eleccion == "0":
            return
        if eleccion not in acciones:
            input("Opción no válida. Enter para volver al menú…")
            continue
        try:
            acciones[eleccion]()
        except KeyboardInterrupt:
            print("\nInterrumpido.")
        try:
            input("\nEnter para volver al menú…")
        except (EOFError, KeyboardInterrupt):
            print()
            return


if __name__ == "__main__":
    main()
