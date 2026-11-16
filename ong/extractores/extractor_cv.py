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
    """CSV -> lista de dicts, conservando los campos y valores originales."""
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# Reglas de ámbito del mapping, en orden: primero tipo_centro (más específico), luego sector
AMBITO_POR_TIPO_CENTRO = {
    "TALLER PRELABORAL DE INSERCIÓN SOCIAL": "EMPLEO_E_INSERCION_LABORAL",
}
# Los clubs de convivencia se clasifican por su sector como INCLUSION_SOCIAL.
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

    def nombre_origen(self, r):
        return N.limpiar(r.get("nombre"))

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
        # La provincia sale del código INE (oficial); si el texto de la fuente dice otra, se informa.
        texto_provincia = N.limpiar(r.get("provincia"))
        if texto_provincia and not self._nombres(texto_provincia) & self._nombres(self.almacen.provincias[provincia]):
            self.reparado("provincia", texto_provincia, self.almacen.provincias[provincia],
                          f"no coincide con el código INE del municipio ({codigo_ine}); se usa el INE")

        lat = lon = None
        try:
            utm = {}
            for campo in ("x_25830", "y_25830"):
                texto = str(r.get(campo) or "").strip()
                if re.fullmatch(r"[0-9]+,[0-9]+", texto):           # "4333847,00": coma decimal
                    self.reparado(campo, texto, texto.replace(",", "."), "coma decimal en vez de punto")
                    texto = texto.replace(",", ".")
                utm[campo] = texto
            x, y = float(utm["x_25830"]), float(utm["y_25830"])
            if (x, y) != self.COORDENADA_GENERICA and 100000 <= x <= 900000 and 0 <= y <= 10000000:
                lat, lon = self._coordenadas(*utm_a_latlon(x, y))
        except (TypeError, ValueError, OverflowError):
            pass

        direccion = N.limpiar(r.get("domici"))
        resultado = self.geocoder.inverso(lat, lon) if lat is not None else None
        # Las coordenadas son las oficiales de la fuente: el CP de ese punto vale si es de la
        # provincia, aunque el geocoder nombre una pedanía o urbanización ("El Perelló" en Sueca).
        if resultado and self._cp(resultado.get("cp"), provincia):
            if not self._resultado_coherente(resultado, provincia, localidad):
                self.incidencia("localidad", f"el mapa nombra '{resultado.get('localidad')}' (núcleo de "
                                             f"{localidad}); se acepta el CP por las coordenadas oficiales")
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
            # "Carretera Plá de Quart, Km 3": el punto kilométrico confunde al buscador.
            # Se reintenta sin él; las coordenadas serán las de la carretera (aproximadas).
            sin_km = N.limpiar(re.sub(r",?\s*\bkm\.?\s*[0-9]+(?:[.,][0-9]+)?", "", direccion, flags=re.I))
            aproximada = False
            if not self._resultado_coherente(resultado, provincia, localidad) and sin_km and sin_km != direccion:
                resultado = self.geocoder.directo(f"{sin_km.strip(' ,')}, {localidad}, "
                                                  f"{self.almacen.provincias[provincia]}, España")
                aproximada = True
            if not self._resultado_coherente(resultado, provincia, localidad):
                raise Rechazo("no se obtuvo un código postal válido y coherente con la localidad y provincia")
            if not self._direccion_recuperada(resultado, localidad, self.almacen.provincias[provincia]):
                raise Rechazo("la geocodificación directa no identifica una dirección verificable")
            nuevas_lat, nuevas_lon = self._coordenadas(resultado.get("lat"), resultado.get("lon"))
            lat_generica, lon_generica = utm_a_latlon(*self.COORDENADA_GENERICA)
            if nuevas_lat is not None and abs(nuevas_lat - lat_generica) < 0.000001 and abs(nuevas_lon - lon_generica) < 0.000001:
                raise Rechazo("la geocodificación devuelve el punto genérico de València; CP no verificable")
            if nuevas_lat is not None:
                utm_fuente = f"UTM ({r.get('x_25830') or 'vacía'}, {r.get('y_25830') or 'vacía'})"
                self.reparado("coordenadas", {"lat": lat, "lon": lon} if lat is not None else utm_fuente,
                              {"lat": nuevas_lat, "lon": nuevas_lon},
                              "geocodificación directa sin el punto kilométrico" if aproximada
                              else "geocodificación directa")
                if aproximada:
                    self.incidencia("coordenadas", "coordenadas aproximadas: punto de la carretera, "
                                                   "no del kilómetro exacto")
            lat, lon = nuevas_lat, nuevas_lon

        codigo_postal = self._cp(resultado.get("cp"), provincia)
        self.reparado("codigo_postal", None, codigo_postal, "obtenido mediante geocodificación")

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
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(wrapper(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
