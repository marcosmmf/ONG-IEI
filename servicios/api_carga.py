"""API de carga (puerto 8004): wrappers -> extractores -> almacén.

    uvicorn servicios.api_carga:app --port 8004       (o ./arrancar.sh, que lanza todo)
    documentación: http://localhost:8004/docs

Al arrancar vacía el almacén y carga las tres fuentes (variable CARGA_INICIAL=0 para no hacerlo).
La carga va en segundo plano: POST /carga la empieza y GET /carga/estado dice cómo va, que es lo
que usan los formularios para pintar la barra de progreso.

Variables de entorno: SOLO_CACHE=1 (no abrir Selenium: solo lo que haya en la caché del modo, ver ong/comun/caches.py),
SELENIUM_VISIBLE=1 (ver el navegador de Selenium).
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from ong.comun import caches
from ong.comun import informe as I
from ong.comun.almacen import Almacen
from ong.comun.geocoder import Geocoder
from ong.extractores.extractor_can import ExtractorCAN
from ong.extractores.extractor_cat import ExtractorCAT
from ong.extractores.extractor_cv import ExtractorCV
from servicios.config import NOMBRE_FUENTE, RAIZ, URL_WRAPPER, crear_app

EXTRACTORES = {"cv": ExtractorCV, "cat": ExtractorCAT, "can": ExtractorCAN}
SALIDA = RAIZ / "salida"
Fuente = Literal["cv", "cat", "can"]


# --------------------------------------------------------------------------- estado de la carga
# Solo puede haber una carga a la vez. El hilo de la carga escribe aquí y GET /carga/estado lo lee.
_cerrojo = threading.Lock()
_estado = {"en_curso": False, "inicio": None, "fin": None, "fuentes": {}, "informes": []}


def _fuente_pendiente(f):
    return {"fuente": f, "nombre": NOMBRE_FUENTE[f], "estado": "pendiente", "hechos": 0, "total": 0,
            "mensaje": ""}


def _actualizar(f, **cambios):
    with _cerrojo:
        _estado["fuentes"][f].update(cambios)


def _pedir_wrapper(f, intentos=30):
    """GET al wrapper de la fuente. Al arrancar todo a la vez el wrapper puede no estar listo aún:
    se reintenta durante unos segundos."""
    for i in range(intentos):
        try:
            with urllib.request.urlopen(URL_WRAPPER[f], timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, ConnectionError) as e:
            if i == intentos - 1:
                raise RuntimeError(f"no responde el wrapper {f.upper()} ({URL_WRAPPER[f]}): {e}")
            time.sleep(1)


def _cargar(fuentes, borrar_antes):
    """Lo ejecuta el hilo de la carga (mismo proceso que cargar.py, pero leyendo los wrappers por HTTP)."""
    almacen = geocoder = None
    informes = []
    try:
        almacen = Almacen()
        geocoder = Geocoder(usar_web=os.environ.get("SOLO_CACHE") != "1",
                            visible=os.environ.get("SELENIUM_VISIBLE") == "1",
                            cache=caches.geocache())      # cache/demo/ con DATOS=muestra, si no cache/completa/
        if borrar_antes:
            almacen.borrar()
        for f in fuentes:
            try:
                _actualizar(f, estado="leyendo", mensaje=f"Pidiendo los datos al wrapper {f.upper()}…")
                registros = _pedir_wrapper(f)                                   # 1) wrapper (HTTP, JSON)
                _actualizar(f, estado="cargando", total=len(registros), mensaje="")
                informe = EXTRACTORES[f](almacen, geocoder).cargar(              # 2) extractor -> almacén
                    registros, progreso=lambda hechos, total, f=f: _actualizar(f, hechos=hechos, total=total))
                informes.append(informe)
                _actualizar(f, estado="terminado")
            except Exception as e:                                               # que no pare las demás
                _actualizar(f, estado="error", mensaje=str(e))
            with _cerrojo:
                _estado["informes"] = list(informes)
    except Exception as e:                       # no se ha podido ni abrir el almacén: todas fallan
        for f in fuentes:
            if _estado["fuentes"][f]["estado"] != "terminado":
                _actualizar(f, estado="error", mensaje=str(e))
    finally:
        if geocoder:
            geocoder.cerrar()
        if almacen:
            almacen.cerrar()
        _guardar_informe(informes)
        with _cerrojo:
            _estado["en_curso"] = False
            _estado["fin"] = datetime.now().isoformat(timespec="seconds")


def _guardar_informe(informes):
    """Mismo informe que cargar.py, en salida/ (JSON por fuente y la página HTML)."""
    try:
        SALIDA.mkdir(exist_ok=True)
        for inf in informes:
            (SALIDA / f"{inf['fuente'].lower()}_informe.json").write_text(
                json.dumps(inf, ensure_ascii=False, indent=2), encoding="utf-8")
        (SALIDA / "informe.html").write_text(I.html(informes, "Informe de carga"), encoding="utf-8")
    except OSError:
        pass


def empezar_carga(fuentes, borrar_antes=False):
    """Pone en marcha la carga en segundo plano. False si ya había una en curso."""
    with _cerrojo:
        if _estado["en_curso"]:
            return False
        _estado.update(en_curso=True, inicio=datetime.now().isoformat(timespec="seconds"), fin=None,
                       informes=[], fuentes={f: _fuente_pendiente(f) for f in fuentes})
    threading.Thread(target=_cargar, args=(list(fuentes), borrar_antes), daemon=True).start()
    return True


def _resumen(inf):
    return {"fuente": inf["fuente"], "leidos": inf["leidos"], "cargados": inf["cargados"],
            "reparados": len(inf["reparados"]), "rechazados": len(inf["rechazados"]),
            "duplicados": inf["duplicados"]}


def _foto_estado():
    with _cerrojo:
        return {"en_curso": _estado["en_curso"], "inicio": _estado["inicio"], "fin": _estado["fin"],
                "fuentes": [dict(v) for v in _estado["fuentes"].values()],
                "resumen": [_resumen(i) for i in _estado["informes"]]}


# --------------------------------------------------------------------------- API
@asynccontextmanager
async def al_arrancar(app):
    # Indicación del profe: al iniciar el programa se cargan ya todas las fuentes.
    if os.environ.get("CARGA_INICIAL", "1") != "0":
        empezar_carga(["cv", "cat", "can"], borrar_antes=True)
    yield


app = crear_app(
    "API de carga",
    """Carga el almacén de datos a partir de las tres fuentes y permite vaciarlo.

* **Objetivo:** llenar el almacén. Para cada fuente pedida: llama a su **wrapper** (que devuelve la fuente
  en JSON), aplica el **extractor** (mappings, reparaciones y rechazos, coordenadas con Selenium) e inserta
  las entidades. Devuelve el informe: cargados, reparados, rechazados y duplicados.
* **Recursos:** `carga` (una carga del almacén, con su estado y su informe) y `almacen` (las entidades guardadas).
* La carga es **asíncrona** (puede tardar si hay que geolocalizar con Selenium): `POST /carga` la empieza y
  `GET /carga/estado` devuelve el progreso de cada fuente. Al arrancar la API se hace una carga completa.
* Fuentes: `cv` (Comunitat Valenciana), `cat` (Catalunya), `can` (Canarias).""",
    etiquetas=[{"name": "carga", "description": "Cargar fuentes y consultar el progreso y el informe"},
               {"name": "almacen", "description": "Vaciar el almacén de datos"}],
    lifespan=al_arrancar)


class PeticionCarga(BaseModel):
    fuentes: list[Fuente] = Field(min_length=1, description="Fuentes a cargar (sin repetir)",
                                  examples=[["cv", "cat", "can"]])


class EstadoFuente(BaseModel):
    fuente: Fuente
    nombre: str = Field(examples=["Comunitat Valenciana"])
    estado: Literal["pendiente", "leyendo", "cargando", "terminado", "error"]
    hechos: int = Field(description="Registros procesados", examples=[340])
    total: int = Field(description="Registros que ha devuelto el wrapper", examples=[765])
    mensaje: str = Field(description="Qué está haciendo o por qué ha fallado", examples=[""])


class Resumen(BaseModel):
    fuente: str = Field(examples=["CV"])
    leidos: int
    cargados: int
    reparados: int
    rechazados: int
    duplicados: int


class Estado(BaseModel):
    en_curso: bool = Field(description="True mientras la carga no ha terminado")
    inicio: str | None = Field(examples=["2026-11-25T18:30:00"])
    fin: str | None
    fuentes: list[EstadoFuente]
    resumen: list[Resumen] = Field(description="Totales de las fuentes ya terminadas")


@app.post("/carga", tags=["carga"], status_code=202, response_model=Estado,
          summary="Cargar las fuentes seleccionadas",
          responses={409: {"description": "Ya hay una carga en curso"},
                     422: {"description": "Fuente desconocida o lista vacía"}})
def cargar(peticion: PeticionCarga):
    """Empieza la carga de las fuentes indicadas (sin borrar lo que ya hay: lo repetido sale como duplicado).
    Responde enseguida con 202; el progreso se consulta en `GET /carga/estado` y el informe en `GET /carga/informe`."""
    fuentes = list(dict.fromkeys(peticion.fuentes))
    if not empezar_carga(fuentes):
        raise HTTPException(409, "Ya hay una carga en curso")
    return _foto_estado()


@app.get("/carga/estado", tags=["carga"], response_model=Estado, summary="Progreso de la carga")
def estado():
    """Estado de la última carga (o de la que está en curso): progreso por fuente y resumen de las terminadas."""
    return _foto_estado()


@app.get("/carga/informe", tags=["carga"], summary="Informe detallado de la última carga",
         responses={200: {"content": {"application/json": {"example": [{
             "fuente": "CV", "leidos": 12, "cargados": 9, "duplicados": 0,
             "reparados": [{"id_origen": "24", "nombre": "Centro X", "reparaciones": [
                 {"campo": "codigo_postal", "antes": "3001", "despues": "03001", "motivo": "faltaba el 0 inicial"}]}],
             "rechazados": [{"id_origen": "31", "nombre": "Centro Y", "motivo": "falta código postal"}],
             "registros": ["… resultado de cada registro en el orden de la fuente …"]}]}}}})
def informe():
    """Informe registro a registro de cada fuente terminada: cargados (con sus datos), reparados
    (antes → después y motivo), rechazados (con motivo) y duplicados."""
    with _cerrojo:
        return _estado["informes"]


class Borrado(BaseModel):
    borradas: int = Field(description="Entidades eliminadas", examples=[2563])


@app.delete("/almacen", tags=["almacen"], response_model=Borrado, summary="Borrar el almacén de datos",
            responses={409: {"description": "Hay una carga en curso"}})
def borrar_almacen(fuente: Fuente | None = None):
    """Elimina todas las entidades (o solo las de `fuente`). Las tablas fijas (provincias y ámbitos) se conservan."""
    with _cerrojo:
        if _estado["en_curso"]:
            raise HTTPException(409, "Hay una carga en curso: espera a que termine")
        almacen = Almacen()
        try:
            consulta = "SELECT COUNT(*) FROM entidad" + (" WHERE fuente = ?" if fuente else "")
            n = almacen.con.execute(consulta, (fuente.upper(),) if fuente else ()).fetchone()[0]
            almacen.borrar(fuente.upper() if fuente else None)
        finally:
            almacen.cerrar()
        _estado.update(fuentes={}, informes=[], inicio=None, fin=None)
    return {"borradas": n}
