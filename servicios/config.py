"""Configuración común de las 5 APIs: puertos, URLs y creación de la app FastAPI.

Cada API corre en su propio puerto (indicación del profe):

    web (formularios)   8000
    wrapper CV          8001
    wrapper CAT         8002
    wrapper CAN         8003
    API de carga        8004
    API de búsqueda     8005

Los formularios están en otro puerto que las APIs, por eso todas activan CORS.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

RAIZ = Path(__file__).resolve().parents[1]
HOST = os.environ.get("ONG_HOST", "127.0.0.1")

PUERTOS = {"web": 8000, "cv": 8001, "cat": 8002, "can": 8003, "carga": 8004, "busqueda": 8005}

# URL de cada wrapper (la API de carga los consume por HTTP)
URL_WRAPPER = {f: os.environ.get(f"URL_WRAPPER_{f.upper()}", f"http://{HOST}:{PUERTOS[f]}/entidades")
               for f in ("cv", "cat", "can")}

NOMBRE_FUENTE = {"cv": "Comunitat Valenciana", "cat": "Catalunya", "can": "Canarias"}

# Ficheros de cada fuente. Con DATOS=muestra los wrappers sirven la muestra de la demo (12 registros).
FICHEROS = {
    "cv": Path("cv") / "entidades_CV.csv",
    "cat": Path("cat") / "Entitats_ONGD_pretty.xml",
    "can": Path("can") / "datos-abiertos-csv-segundo-trimestre26.json",
}


def fichero(fuente, muestra=None):
    """Ruta del fichero de la fuente: el real o el de datos/muestra/ (variable DATOS=muestra)."""
    if muestra is None:
        muestra = os.environ.get("DATOS", "").lower() == "muestra"
    base = RAIZ / "datos" / ("muestra" if muestra else "")
    return base / FICHEROS[fuente]


def crear_app(titulo, descripcion, etiquetas=None, lifespan=None):
    """App FastAPI con la documentación OpenAPI (/docs Swagger, /redoc Redoc) y CORS."""
    app = FastAPI(title=titulo, description=descripcion, version="2.0",
                  openapi_tags=etiquetas, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    return app
