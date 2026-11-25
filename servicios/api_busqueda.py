"""API de búsqueda (puerto 8005): consultas sobre el almacén de datos.

    uvicorn servicios.api_busqueda:app --port 8005    (o ./arrancar.sh, que lanza todo)
    documentación: http://localhost:8005/docs

Tiene dos clientes distintos que NO se mezclan:
  * el formulario de búsqueda  -> GET /entidades?localidad=&cp=&provincia=&tipo=
  * el mapa (mashup)           -> GET /entidades/mapa?lat_min=&lat_max=&lon_min=&lon_max=  (zona visible)
                                  GET /entidades/{id}  (metadatos al pulsar un pin)
"""
import sqlite3
from enum import Enum

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

from ong.comun.almacen import BD
from ong.comun.normalizar import sin_tildes
from servicios.config import crear_app

# Los 12 ámbitos de la tabla `ambito` (sql/schema.sql). En el formulario es el campo "Tipo".
Tipo = Enum("Tipo", {n: n for n in (
    "MAYORES", "DISCAPACIDAD", "SALUD_MENTAL", "INFANCIA_Y_JUVENTUD", "MUJER", "MIGRACION",
    "INCLUSION_SOCIAL", "EDUCACION_Y_FORMACION", "EMPLEO_E_INSERCION_LABORAL",
    "SALUD_Y_ATENCION_SOCIOSANITARIA", "VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA",
    "CULTURA_Y_DESARROLLO_COMUNITARIO")}, type=str)

CONSULTA = """
    SELECT e.cod_entidad AS id, e.nombre, a.nombre AS tipo, e.direccion, e.codigo_postal,
           l.nombre AS localidad, p.nombre AS provincia, e.latitud, e.longitud,
           e.descripcion, e.contacto, e.url, e.fuente
      FROM entidad e
      JOIN localidad l ON l.codigo = e.cod_localidad
      JOIN provincia p ON p.codigo = l.cod_provincia
      JOIN ambito    a ON a.id     = e.ambito
"""


def conectar():
    """Conexión de solo lectura por petición. sin_tildes() permite buscar 'valencia' y encontrar 'València'."""
    if not BD.exists():
        raise HTTPException(503, "El almacén de datos todavía no existe: haz una carga primero")
    con = sqlite3.connect(f"file:{BD}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.create_function("sin_tildes", 1, lambda t: sin_tildes(t or ""), deterministic=True)
    return con


app = crear_app(
    "API de búsqueda",
    """Consulta las entidades del almacén de datos.

* **Objetivo:** dar servicio al formulario de búsqueda y al mapa de la aplicación.
* **Recurso:** `entidades` (entidades de acción social del almacén, con su localidad, provincia y tipo).
* **Formulario de búsqueda:** `GET /entidades` filtra por localidad, código postal, provincia y tipo.
* **Mapa:** `GET /entidades/mapa` devuelve las entidades que caen en la zona visible del mapa (se llama cada
  vez que el usuario mueve el mapa o cambia el zoom) y `GET /entidades/{id}` los metadatos de una entidad
  (al pulsar su marcador). El mapa no depende de la búsqueda del formulario.
* **Tablas auxiliares:** `GET /tipos` y `GET /provincias` para rellenar los desplegables.""",
    etiquetas=[{"name": "formulario", "description": "Búsqueda por los campos del formulario"},
               {"name": "mapa", "description": "Entidades por zona del mapa y detalle de una entidad"},
               {"name": "auxiliares", "description": "Valores posibles de los campos"}])


class Entidad(BaseModel):
    id: int = Field(examples=[17])
    nombre: str = Field(examples=["Accem - V.T. colect. desfavorecidos Cuenca"])
    tipo: str = Field(description="Ámbito de la entidad", examples=["INCLUSION_SOCIAL"])
    direccion: str = Field(examples=["Calle Cuenca, 89"])
    codigo_postal: str | None = Field(examples=["46008"])
    localidad: str = Field(examples=["València"])
    provincia: str = Field(examples=["Valencia/València"])
    latitud: float | None = Field(examples=[39.4669])
    longitud: float | None = Field(examples=[-0.3893])
    descripcion: str | None
    contacto: str | None = Field(examples=["963496977 · agomezc@accem.es"])
    url: str | None
    fuente: str = Field(description="CV, CAT o CAN", examples=["CV"])


class ResultadoBusqueda(BaseModel):
    total: int = Field(description="Entidades que cumplen los filtros (aunque se devuelvan menos)")
    entidades: list[Entidad]


class Marcador(BaseModel):
    id: int
    nombre: str
    tipo: str
    latitud: float
    longitud: float
    fuente: str


@app.get("/entidades", tags=["formulario"], response_model=ResultadoBusqueda,
         summary="Buscar entidades por localidad, código postal, provincia y tipo")
def buscar(
    localidad: str | None = Query(None, max_length=100, description="Parte del nombre (sin importar tildes ni mayúsculas)",
                                  examples=["valencia"]),
    cp: str | None = Query(None, pattern=r"^\d{1,5}$", description="Código postal o su principio (p. ej. `46` = provincia de Valencia)",
                           examples=["46008"]),
    provincia: str | None = Query(None, max_length=100, description="Parte del nombre o código de 2 dígitos",
                                  examples=["Barcelona"]),
    tipo: Tipo | None = Query(None, description="Ámbito de la entidad"),
    limite: int = Query(500, ge=1, le=5000, description="Máximo de entidades devueltas"),
):
    """Devuelve las entidades que cumplen **todos** los filtros indicados (los vacíos no filtran),
    ordenadas por nombre."""
    condiciones, valores = [], []
    if localidad and localidad.strip():
        condiciones.append("sin_tildes(l.nombre) LIKE '%' || sin_tildes(?) || '%'")
        valores.append(localidad.strip())
    if cp:
        condiciones.append("e.codigo_postal LIKE ? || '%'")
        valores.append(cp)
    if provincia and provincia.strip():
        condiciones.append("(p.codigo = ? OR sin_tildes(p.nombre) LIKE '%' || sin_tildes(?) || '%')")
        valores += [provincia.strip().zfill(2), provincia.strip()]
    if tipo:
        condiciones.append("a.nombre = ?")
        valores.append(tipo.value)
    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with conectar() as con:
        total = con.execute(f"SELECT COUNT(*) FROM ({CONSULTA}{where})", valores).fetchone()[0]
        filas = con.execute(f"{CONSULTA}{where} ORDER BY e.nombre LIMIT ?", [*valores, limite]).fetchall()
    return {"total": total, "entidades": [dict(f) for f in filas]}


@app.get("/entidades/mapa", tags=["mapa"], response_model=list[Marcador],
         summary="Entidades dentro de la zona visible del mapa")
def en_zona(
    lat_min: float = Query(..., ge=-90, le=90, description="Latitud del borde sur", examples=[38.9]),
    lat_max: float = Query(..., ge=-90, le=90, description="Latitud del borde norte", examples=[39.8]),
    lon_min: float = Query(..., ge=-180, le=180, description="Longitud del borde oeste", examples=[-1.0]),
    lon_max: float = Query(..., ge=-180, le=180, description="Longitud del borde este", examples=[0.2]),
):
    """Marcadores (id, nombre, tipo y coordenadas) de todas las entidades del rectángulo indicado.
    Solo lo justo para pintar el mapa: los metadatos se piden con `GET /entidades/{id}` al pulsar el marcador."""
    if lat_min > lat_max or lon_min > lon_max:
        raise HTTPException(422, "lat_min/lon_min deben ser menores que lat_max/lon_max")
    with conectar() as con:
        filas = con.execute(
            """SELECT e.cod_entidad AS id, e.nombre, a.nombre AS tipo, e.latitud, e.longitud, e.fuente
                 FROM entidad e JOIN ambito a ON a.id = e.ambito
                WHERE e.latitud BETWEEN ? AND ? AND e.longitud BETWEEN ? AND ?""",
            (lat_min, lat_max, lon_min, lon_max)).fetchall()
    return [dict(f) for f in filas]


@app.get("/entidades/{id}", tags=["mapa"], response_model=Entidad, summary="Metadatos de una entidad",
         responses={404: {"description": "No existe ninguna entidad con ese id"}})
def detalle(id: int):
    """Todos los datos de la entidad (lo que se enseña al pulsar su marcador en el mapa)."""
    with conectar() as con:
        fila = con.execute(f"{CONSULTA} WHERE e.cod_entidad = ?", (id,)).fetchone()
    if not fila:
        raise HTTPException(404, f"No existe la entidad {id}")
    return dict(fila)


class Provincia(BaseModel):
    codigo: str = Field(examples=["46"])
    nombre: str = Field(examples=["Valencia/València"])
    entidades: int = Field(description="Entidades de la provincia en el almacén", examples=[812])


@app.get("/tipos", tags=["auxiliares"], response_model=list[str], summary="Tipos (ámbitos) posibles")
def tipos():
    """Los valores que acepta el parámetro `tipo` de `GET /entidades`."""
    return [t.value for t in Tipo]


@app.get("/provincias", tags=["auxiliares"], response_model=list[Provincia], summary="Provincias")
def provincias():
    """Las 52 provincias con el número de entidades que tiene cada una en el almacén."""
    with conectar() as con:
        filas = con.execute("""SELECT p.codigo, p.nombre, COUNT(e.cod_entidad) AS entidades
                                 FROM provincia p
                                 LEFT JOIN localidad l ON l.cod_provincia = p.codigo
                                 LEFT JOIN entidad e ON e.cod_localidad = l.codigo
                                GROUP BY p.codigo ORDER BY p.nombre""").fetchall()
    return [dict(f) for f in filas]
