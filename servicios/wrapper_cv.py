"""Wrapper CV (puerto 8001): CSV de la Comunitat Valenciana -> JSON.

    uvicorn servicios.wrapper_cv:app --port 8001      (o ./arrancar.sh, que lanza todo)
    GET http://localhost:8001/entidades               documentación: http://localhost:8001/docs
"""
import csv

from servicios.wrapper_base import crear_wrapper


def convertir(ruta):
    """CSV -> lista de dicts, conservando los campos y valores originales."""
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


EJEMPLO = {"WKT": "POINT (724558 4371330)", "id": "1491", "ni_centro": "11119", "tipo_centro": "VIVIENDAS TUTELADAS",
           "nombre": "Accem - V.T. colect. desfavorecidos Cuenca", "entidad": "ACCEM",
           "domici": "C/ Cuenca, nº 89, planta 1ª pta. 2", "cod_ine_mun": "46250", "provincia": "València/Valencia",
           "municipio": "València", "sector": "POBLACIÓN EN GENERAL Y COLECTIVOS SOCIALMENTE DESFAVORECIDOS",
           "email": "agomezc@accem.es", "telefono": "963496977", "x_25830": "724558", "y_25830": "4371330"}

app = crear_wrapper("cv", convertir, "CSV", EJEMPLO)
