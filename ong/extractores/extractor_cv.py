"""Extractor Comunitat Valenciana (mapping: docs/mappings/mappings-CV.pdf).

ESQUELETO: hace lo básico para que la carga funcione. Lo marcado con TODO es
el trabajo pendiente para repartir.
"""
from ong.comun import normalizar as N
from ong.comun.utm import utm_a_latlon
from ong.extractores.base import Extractor, Rechazo

# Reglas de ámbito del mapping, en orden: primero tipo_centro (más específico), luego sector
AMBITO_POR_TIPO_CENTRO = {
    "TALLER PRELABORAL DE INSERCIÓN SOCIAL": "EMPLEO_E_INSERCION_LABORAL",
    "CLUBS DE CONVIVENCIA": "VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA",
}
AMBITO_POR_SECTOR = {
    "PERSONAS MAYORES": "MAYORES",
    "PERSONAS CON DISCAPACIDAD": "DISCAPACIDAD",
    "PERSONAS CON ENFERMEDAD MENTAL": "SALUD_MENTAL",
    "INFANCIA": "INFANCIA_Y_JUVENTUD",
    "MUJERES": "MUJER",
    "PERSONAS MIGRANTES": "MIGRACION",
    "POBLACIÓN EN GENERAL Y COLECTIVOS SOCIALMENTE DESFAVORECIDOS": "INCLUSION_SOCIAL",
}


class ExtractorCV(Extractor):
    FUENTE = "CV"

    def id_origen(self, r):
        return r.get("id")

    def transformar(self, r):
        ambito = AMBITO_POR_TIPO_CENTRO.get(r["tipo_centro"]) or AMBITO_POR_SECTOR.get(r["sector"])
        if not ambito:
            raise Rechazo(f"sector sin correspondencia: {r['sector']!r}")

        try:
            lat, lon = utm_a_latlon(float(r["x_25830"]), float(r["y_25830"]))
        except ValueError:
            lat = lon = None

        direccion = N.limpiar(r["domici"])
        # TODO: si direccion es None -> sacarla de las coordenadas (corrección del profe):
        #       res = self.geocoder.inverso(lat, lon); direccion = res["direccion"]; self.reparado(...)

        # TODO: CP -> la fuente no lo tiene, pero el buscador filtra por CP.
        #       Sacarlo con self.geocoder.inverso(lat, lon)["cp"]
        codigo_postal = None

        # TODO: 32 centros de València comparten la coordenada genérica (725733, 4372816):
        #       volver a geolocalizar su dirección con self.geocoder.directo(...)

        return {
            "nombre": N.limpiar(r["nombre"]),
            "ambito": ambito,
            "direccion": direccion,
            "codigo_postal": codigo_postal,
            "latitud": lat,
            "longitud": lon,
            "descripcion": N.limpiar(r["tipo_centro"]),          # TODO: decidir (mapping dice leyenda + sector)
            "contacto": N.unir_contacto(N.telefono(r["telefono"]),
                                        None if r["email"].lower() == "zero@gva.es" else N.email(r["email"])),
            "url": None,                                          # la fuente no tiene web
            "localidad": N.limpiar(r["municipio"]),
            "cod_provincia": r["cod_ine_mun"].zfill(5)[:2],
        }
