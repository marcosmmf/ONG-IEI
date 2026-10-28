"""Wrapper + extractor de la Comunitat Valenciana (mapping: docs/mappings/mappingsCV.pdf).

  1. wrapper():       abre el CSV y lo convierte a JSON (solo cambia el formato, sin mappings).
                      En la 2a entrega se separará y se expondrá como API REST.
  2. ExtractorCV:     aplica el mapping al esquema global, repara / rechaza y carga el almacén.

Recupera dirección y CP con el geocoder. Rechaza registros sin dirección o CP
válidos y evita utilizar el punto genérico de València como ubicación real.
"""
import csv
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

from ong.comun import normalizar as N
from ong.comun.utm import utm_a_latlon
from ong.extractores.base import Extractor, Rechazo

FICHERO = Path(__file__).resolve().parents[2] / "datos" / "cv" / "entidades_CV.csv"


def wrapper(ruta=FICHERO):
    """CSV -> lista de dicts con los mismos campos que la fuente."""
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in fila.items()} for fila in csv.DictReader(f)]


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
    COORDENADA_GENERICA = (725733, 4372816)

    def id_origen(self, r):
        return r.get("id")

    @staticmethod
    def _coordenadas(lat, lon):
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError, OverflowError):
            return None, None
        if math.isfinite(lat) and math.isfinite(lon) and 27 <= lat <= 44 and -19 <= lon <= 5:
            return lat, lon
        return None, None

    @staticmethod
    def _cp(valor, provincia):
        cp = str(valor).strip() if valor is not None else ""
        return cp if re.fullmatch(r"[0-9]{5}", cp) and cp[:2] == provincia else None

    @staticmethod
    def _nombres(nombre):
        """Compara variantes bilingües, acentos y artículos pospuestos."""
        variantes = set()
        for parte in (nombre or "").split("/"):
            parte = N.reordenar_articulo(parte.strip())
            parte = unicodedata.normalize("NFKD", parte.casefold())
            variantes.add("".join(c for c in parte if c.isalnum() and not unicodedata.combining(c)))
        return variantes - {""}

    def _resultado_coherente(self, resultado, provincia, localidad):
        if not resultado or not self._cp(resultado.get("cp"), provincia):
            return False
        municipio = N.limpiar(resultado.get("localidad"))
        return not municipio or bool(self._nombres(municipio) & self._nombres(localidad))

    def _direccion_recuperada(self, resultado, localidad, provincia):
        direccion = N.limpiar(resultado.get("direccion"))
        if not direccion:
            return None
        # Una respuesta que solo identifica el municipio no recupera una calle.
        primera_parte = re.sub(r"\b[0-9]{5}\b", "", direccion.split(",")[0]).strip()
        lugares = self._nombres(localidad) | self._nombres(provincia) | {"espana", "spain"}
        nombres = self._nombres(primera_parte)
        return direccion if nombres and not nombres & lugares else None

    def _validar(self, e):
        # La validación compartida permite CP nulos; la carga de CV no.
        super()._validar(e)
        if not self._cp(e.get("codigo_postal"), e.get("cod_provincia")):
            raise Rechazo("falta código postal válido para la provincia")

    def transformar(self, r):
        tipo = (N.limpiar(r.get("tipo_centro")) or "").upper()
        sector = N.limpiar(r.get("sector"))
        ambito = AMBITO_POR_TIPO_CENTRO.get(tipo) or AMBITO_POR_SECTOR.get((sector or "").upper())
        if not ambito:
            raise Rechazo(f"sector sin correspondencia: {sector!r}")

        nombre = N.limpiar(r.get("nombre"))
        localidad = N.limpiar(r.get("municipio"))
        for campo, valor in (("nombre", nombre), ("localidad", localidad)):
            if not valor:
                raise Rechazo(f"falta {campo}")
        codigo_ine = str(r.get("cod_ine_mun") or "").strip().zfill(5)
        provincia = codigo_ine[:2]
        if not re.fullmatch(r"[0-9]{5}", codigo_ine) or provincia not in self.almacen.provincias:
            raise Rechazo(f"código INE de municipio no válido: {r.get('cod_ine_mun')!r}")

        lat = lon = None
        try:
            x, y = float(r.get("x_25830")), float(r.get("y_25830"))
            if (x, y) != self.COORDENADA_GENERICA and 100000 <= x <= 900000 and 0 <= y <= 10000000:
                lat, lon = self._coordenadas(*utm_a_latlon(x, y))
        except (TypeError, ValueError, OverflowError):
            pass

        direccion = N.limpiar(r.get("domici"))
        resultado = self.geocoder.inverso(lat, lon) if lat is not None else None
        if self._resultado_coherente(resultado, provincia, localidad):
            if not direccion:
                direccion = self._direccion_recuperada(resultado, localidad, self.almacen.provincias[provincia])
                if direccion:
                    self.reparado("direccion", r.get("domici"), direccion, "geocodificación inversa")
        else:
            resultado = None

        if not direccion:
            raise Rechazo("no se pudo recuperar una dirección verificable")

        # También permite recuperar registros con UTM ausentes o incorrectas.
        if resultado is None:
            consulta = f"{direccion}, {localidad}, {self.almacen.provincias[provincia]}, España"
            resultado = self.geocoder.directo(consulta)
            if not self._resultado_coherente(resultado, provincia, localidad):
                raise Rechazo("no se obtuvo un código postal válido y coherente con la localidad y provincia")
            if not self._direccion_recuperada(resultado, localidad, self.almacen.provincias[provincia]):
                raise Rechazo("la geocodificación directa no identifica una dirección verificable")
            nuevas_lat, nuevas_lon = self._coordenadas(resultado.get("lat"), resultado.get("lon"))
            lat_generica, lon_generica = utm_a_latlon(*self.COORDENADA_GENERICA)
            if nuevas_lat is not None and abs(nuevas_lat - lat_generica) < 0.000001 and abs(nuevas_lon - lon_generica) < 0.000001:
                raise Rechazo("la geocodificación devuelve el punto genérico de València; CP no verificable")
            if nuevas_lat is not None:
                self.reparado("coordenadas", {"lat": lat, "lon": lon},
                              {"lat": nuevas_lat, "lon": nuevas_lon}, "geocodificación directa")
            lat, lon = nuevas_lat, nuevas_lon

        codigo_postal = self._cp(resultado.get("cp"), provincia)
        self.reparado("codigo_postal", None, codigo_postal, "obtenido mediante geocodificación")
        if lat is None:
            self.incidencia("coordenadas", "sin coordenadas fiables; no se mostrará en el mapa")

        descripcion = " - ".join(p for p in (N.limpiar(r.get("leyenda")), sector) if p) or None
        email = N.limpiar(r.get("email"))

        return {
            "nombre": nombre,
            "ambito": ambito,
            "direccion": direccion,
            "codigo_postal": codigo_postal,
            "latitud": lat,
            "longitud": lon,
            "descripcion": descripcion,
            "contacto": N.unir_contacto(N.telefono(r.get("telefono")),
                                        None if email and email.lower() == "zero@gva.es" else N.email(email)),
            "url": None,                                          # la fuente no tiene web
            "localidad": localidad,
            "cod_provincia": provincia,
        }


if __name__ == "__main__":
    json.dump(wrapper(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
