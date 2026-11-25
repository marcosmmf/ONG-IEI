"""Parte común de los tres wrappers (CV, CAT, CAN).

Un wrapper es una API REST que simula la API de la administración: lee el fichero de su
fuente, lo convierte a JSON SIN aplicar ningún mapping (mismos campos y valores que la
fuente) y lo devuelve. No tiene parámetros: siempre devuelve la fuente entera.
"""
from typing import Any

from fastapi import HTTPException

from servicios.config import NOMBRE_FUENTE, crear_app, fichero


def crear_wrapper(fuente, convertir, formato, ejemplo):
    nombre = NOMBRE_FUENTE[fuente]
    app = crear_app(
        f"Wrapper {fuente.upper()} — {nombre}",
        f"""Simula la API de datos abiertos de **{nombre}**.

* **Objetivo:** ofrecer los datos de la fuente en JSON para que el extractor {fuente.upper()} de la API de carga
  pueda consumirlos.
* **Recurso:** `entidades` (las entidades tal como vienen en la fuente, formato original **{formato}**).
* **Transformación:** solo de formato ({formato} → JSON). Los campos y valores son los de la fuente; los
  mappings al esquema global los aplica el extractor, no el wrapper.
* **Parámetros:** ninguno.""",
        etiquetas=[{"name": "entidades", "description": f"Entidades de {nombre} en JSON"}])

    @app.get("/entidades", tags=["entidades"], response_model=list[dict[str, Any]],
             summary=f"Todas las entidades de {nombre} en JSON",
             responses={200: {"description": "Lista de entidades con los campos originales de la fuente",
                              "content": {"application/json": {"example": [ejemplo]}}},
                        503: {"description": "No se puede leer el fichero de la fuente"}})
    def entidades():
        """Lee el fichero de la fuente, lo convierte a JSON y devuelve todas sus entidades."""
        ruta = fichero(fuente)
        try:
            return convertir(ruta)
        except (OSError, ValueError) as e:
            raise HTTPException(503, f"No se puede leer {ruta.name}: {e}")

    return app
