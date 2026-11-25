"""Wrapper CAN (puerto 8003): JSON de Canarias -> JSON (la fuente ya es JSON aunque se llame "csv").

    uvicorn servicios.wrapper_can:app --port 8003     (o ./arrancar.sh, que lanza todo)
    GET http://localhost:8003/entidades               documentación: http://localhost:8003/docs
"""
import json

from servicios.wrapper_base import crear_wrapper


def convertir(ruta):
    """JSON -> lista de dicts con los mismos campos que la fuente (solo se quitan espacios sobrantes)."""
    with open(ruta, encoding="utf-8-sig") as f:
        datos = json.load(f)
    return [{k: (v.strip() if isinstance(v, str) else v) for k, v in d.items()} for d in datos]


EJEMPLO = {"nif": "G38640769", "denominacion": "Asociacion De Mayores Viñatigos Centenarios",
           "numero_registro": "ERE2003CA00013", "direccion_tipo_via": "Calle", "direccion_nombre_via": "Real",
           "direccion_numero": "132", "direccion_complemento": "_U", "direccion_provincia_id": "99",
           "direccion_provincia_nombre": "Desconocida", "direccion_municipio_id": "38430",
           "direccion_municipio_nombre": "Tacoronte", "direccion_isla_nombre": "Tenerife",
           "telefono_1": "(34)922584030", "pagina_web": "_U", "area_id": "02", "area_nombre": "Tercera Edad",
           "subarea_id": "_U", "subarea_nombre": "_U"}

app = crear_wrapper("can", convertir, "JSON", EJEMPLO)
