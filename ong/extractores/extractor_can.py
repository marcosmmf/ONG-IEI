"""Wrapper + extractor de Canarias (mapping: docs/mappings/mappings-CAN.docx).

  1. wrapper():       abre el fichero (ya es JSON, aunque se llame "csv") y limpia espacios.
                      En la 2a entrega se separará y se expondrá como API REST.
  2. ExtractorCAN:    aplica el mapping al esquema global, repara / rechaza y carga el almacén.

ESQUELETO: hace lo básico para que la carga funcione. Lo marcado con TODO es
el trabajo pendiente para repartir.
"""
import json
import sys
from pathlib import Path

from ong.comun import normalizar as N
from ong.extractores.base import Extractor, Rechazo

FICHERO = Path(__file__).resolve().parents[2] / "datos" / "can" / "datos-abiertos-csv-segundo-trimestre26.json"


def wrapper(ruta=FICHERO):
    """JSON -> lista de dicts con los mismos campos que la fuente."""
    with open(ruta, encoding="utf-8-sig") as f:
        datos = json.load(f)
    return [{k: (v.strip() if isinstance(v, str) else v) for k, v in d.items()} for d in datos]

# Anexo del mapping: (area_id, subarea_id) -> ámbito. None = cualquier subárea
AMBITO_POR_AREA = {
    ("01", None): "INFANCIA_Y_JUVENTUD",
    ("02", None): "MAYORES",
    ("03", None): "DISCAPACIDAD",
    ("04", None): "SALUD_Y_ATENCION_SOCIOSANITARIA",
    ("05", None): "MUJER",
    ("06", None): "INCLUSION_SOCIAL",
    ("07", None): "DISCAPACIDAD",
    ("08", "A"): "VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA",
    ("08", "B"): "INCLUSION_SOCIAL",
    ("08", "C"): "INCLUSION_SOCIAL",
    ("08", "D"): "MIGRACION",
    ("08", "E"): "CULTURA_Y_DESARROLLO_COMUNITARIO",
    ("08", "F"): "CULTURA_Y_DESARROLLO_COMUNITARIO",
    ("08", "G"): "EMPLEO_E_INSERCION_LABORAL",
    ("08", "H"): "SALUD_Y_ATENCION_SOCIOSANITARIA",
    ("08", "I"): "INCLUSION_SOCIAL",
    ("08", "_U"): "INCLUSION_SOCIAL",
    ("09", None): "VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA",
}


class ExtractorCAN(Extractor):
    FUENTE = "CAN"

    def id_origen(self, r):
        return r.get("numero_registro")

    def transformar(self, r):
        area, subarea = r["area_id"], r["subarea_id"]
        ambito = AMBITO_POR_AREA.get((area, subarea)) or AMBITO_POR_AREA.get((area, None))
        if not ambito:
            raise Rechazo(f"área/subárea sin correspondencia: {area}/{subarea}")

        # TODO: expandir abreviaturas (Avda -> Avenida...) y no repetir tipo/número si ya están en el nombre
        direccion = N.limpiar(" ".join(x for x in (r["direccion_tipo_via"], r["direccion_nombre_via"],
                                                   r["direccion_numero"]) if not N.vacio(x)))

        localidad = N.reordenar_articulo(N.limpiar(r["direccion_municipio_nombre"]) or "")
        cod_provincia = r["direccion_provincia_id"]
        # TODO: 8 registros con municipio/provincia "_U": su municipio_id es en realidad un CP
        #       -> cod_provincia = CP[:2] y localidad sacada del geocoder

        # TODO: CP y coordenadas con el scraper:
        #       res = self.geocoder.directo(f"{direccion}, {localidad}, España")
        #       -> res["cp"], res["lat"], res["lon"]  (comprobar que el CP es de la provincia)

        # TODO: duplicados por nif (51 entidades repetidas)
        # TODO: reparar web con N.url ("wwwadepsi.org", "hhtps://"...)

        return {
            "nombre": N.limpiar(r["denominacion"]),
            "ambito": ambito,
            "direccion": direccion,
            "codigo_postal": None,
            "latitud": None,
            "longitud": None,
            "descripcion": N.limpiar(r["subarea_nombre"]) or N.limpiar(r["area_nombre"]),
            "contacto": N.unir_contacto(N.telefono(r["telefono_1"]), N.telefono(r["telefono_2"])),
            "url": N.limpiar(r["pagina_web"]),
            "localidad": localidad or None,
            "cod_provincia": cod_provincia,
        }


if __name__ == "__main__":
    json.dump(wrapper(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
