"""Cachés de Selenium (coordenadas) y Gemini (ámbitos), separadas por modo de datos.

    cache/demo/       muestra de la demo (datos/muestra/)   geocache.json, ambito_cache.json, backup/
    cache/completa/   datos completos (datos/)               geocache.json, ambito_cache.json, backup/

Cada modo tiene su propia copia de seguridad en backup/, que solo cambia cuando se pide
(guardar_copia / borrar_copia). Se maneja con:  python cache.py
"""
import json
import os
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CARPETA = RAIZ / "cache"
MODOS = {"demo": "muestra de la demo", "completa": "datos completos"}
FICHEROS = {"geocache.json": "Selenium (coordenadas)", "ambito_cache.json": "Gemini (ámbitos CAT)"}


def modo(muestra=None):
    """'demo' o 'completa'. Sin indicarlo, lo decide la variable DATOS (=muestra) que pone arrancar.sh."""
    if muestra is None:
        muestra = os.environ.get("DATOS", "").lower() == "muestra"
    return "demo" if muestra else "completa"


def _modo(m):
    m = m if m in MODOS else modo(m)
    return m


def carpeta(m=None):
    return CARPETA / _modo(m)


def geocache(m=None):
    return carpeta(m) / "geocache.json"


def ambito(m=None):
    return carpeta(m) / "ambito_cache.json"


def copia(m=None):
    return carpeta(m) / "backup"


def contar(fichero):
    """Número de consultas guardadas, o None si el fichero no existe."""
    try:
        return len(json.loads(Path(fichero).read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return -1


def estado():
    """[(modo, fichero, guardadas, guardadas en la copia)] para enseñarlo."""
    return [(m, f, contar(carpeta(m) / f), contar(copia(m) / f)) for m in MODOS for f in FICHEROS]


def vaciar(m):
    """Borra las cachés del modo (la próxima carga consulta Selenium y Gemini en directo).
    Si aún no hay copia de seguridad, la hace antes de borrar."""
    m = _modo(m)
    if not copia(m).exists():
        guardar_copia(m)
    for f in FICHEROS:
        (carpeta(m) / f).unlink(missing_ok=True)
    return f"Caché {m} vaciada (la copia de cache/{m}/backup/ se conserva)."


def restaurar(m):
    """Vuelve a poner las cachés del modo desde su copia de seguridad."""
    m = _modo(m)
    hechos = []
    for f in FICHEROS:
        if (copia(m) / f).exists():
            carpeta(m).mkdir(parents=True, exist_ok=True)
            shutil.copy2(copia(m) / f, carpeta(m) / f)
            hechos.append(f)
    if not hechos:
        return f"No hay copia de seguridad de la caché {m} (cache/{m}/backup/)."
    return f"Caché {m} restaurada desde cache/{m}/backup/: {', '.join(hechos)}."


def guardar_copia(m):
    """Copia las cachés actuales del modo a su backup/ (sustituye la copia anterior)."""
    m = _modo(m)
    copia(m).mkdir(parents=True, exist_ok=True)
    hechos = []
    for f in FICHEROS:
        if (carpeta(m) / f).exists():
            shutil.copy2(carpeta(m) / f, copia(m) / f)
            hechos.append(f)
    return f"Copia de la caché {m} guardada en cache/{m}/backup/: {', '.join(hechos) or 'no había nada que copiar'}."


def borrar_copia(m):
    """Elimina la copia de seguridad del modo."""
    m = _modo(m)
    if not copia(m).exists():
        return f"La caché {m} no tenía copia de seguridad."
    shutil.rmtree(copia(m))
    return f"Copia de seguridad de la caché {m} borrada (cache/{m}/backup/)."
