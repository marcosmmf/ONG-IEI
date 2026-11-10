"""Wrapper + extractor de Canarias (mapping: docs/mappings/mappings-CAN.docx).

  1. wrapper():       abre el fichero (ya es JSON, aunque se llame "csv") y limpia espacios.
                      En la 2a entrega se separará y se expondrá como API REST.
  2. ExtractorCAN:    aplica el mapping al esquema global, repara / rechaza y carga el almacén.

La fuente no tiene CP ni coordenadas: se obtienen con Selenium a partir de la
dirección completa. Decisiones explicadas en docs/revision-mappings.md (Canarias).
"""
import json
import re
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

# Tipos de vía tal como aparecen en la fuente (en minúsculas) -> nombre completo
TIPOS_VIA = {
    "calle": "Calle", "c/": "Calle", "cl": "Calle",
    "avenida": "Avenida", "avda": "Avenida", "av": "Avenida",
    "carretera": "Carretera", "ctra": "Carretera", "carre": "Carretera",
    "camino": "Camino", "cmno": "Camino",
    "rambla": "Rambla", "rbla": "Rambla",
    "travesia": "Travesía", "trva": "Travesía",
    "subida": "Subida", "sbida": "Subida",
    "urb": "Urbanización", "psaje": "Pasaje", "pque": "Parque", "custa": "Cuesta",
    "muell": "Muelle", "barda": "Barriada", "disem": "Diseminado", "branc": "Barranco",
    "plaza": "Plaza", "paseo": "Paseo", "lugar": "Lugar", "loma": "Loma", "zona": "Zona", "senda": "Senda",
}


def separar_tipo(nombre_via):
    """Si el nombre ya empieza por un tipo de vía, lo separa:
    'C/ Doctor Verneau' -> ('Calle', 'Doctor Verneau');  'Lomo La Plana' -> (None, 'Lomo La Plana')."""
    m = re.match(r"\W*(\w+)([./]?)[\s./]*(.*)", nombre_via)
    if not m or not m.group(3):
        return None, nombre_via
    clave = m.group(1).lower() + ("/" if m.group(2) == "/" else "")
    if clave in TIPOS_VIA:
        return TIPOS_VIA[clave], m.group(3)
    return None, nombre_via


def montar_direccion(r):
    """Junta tipo, nombre, número y complemento sin repetir nada.
    Devuelve (dirección para guardar, dirección para Selenium)."""
    nombre_via = N.limpiar(r["direccion_nombre_via"])
    if not nombre_via:
        raise Rechazo("falta la dirección")

    tipo_en_nombre, nombre_via = separar_tipo(nombre_via)
    tipo = N.limpiar(r["direccion_tipo_via"])
    if tipo_en_nombre:
        tipo = tipo_en_nombre
    elif tipo:
        tipo = TIPOS_VIA.get(tipo.lower().rstrip("."), tipo)
    calle = f"{tipo} {nombre_via}" if tipo else nombre_via

    numero = N.limpiar(r["direccion_numero"])
    if numero and re.search(rf"\b{re.escape(numero)}(?!\w)", nombre_via, re.IGNORECASE):
        numero = None                                   # ya viene dentro del nombre
    if numero and numero.lower().rstrip(".") == "s/n":
        para_guardar, para_selenium = f"{calle} s/n", calle
    elif numero:
        para_guardar = para_selenium = f"{calle} {numero}"
    else:
        para_guardar = para_selenium = calle

    complemento = N.limpiar(r["direccion_complemento"])
    if complemento and re.search(r"\w", complemento):          # descarta rellenos como "- - - -"
        para_guardar = f"{para_guardar}, {complemento}"
    para_selenium = N.limpiar(re.sub(r"\(.*?\)", "", para_selenium)) or para_selenium   # los paréntesis le confunden
    return para_guardar, para_selenium


class ExtractorCAN(Extractor):
    FUENTE = "CAN"

    def id_origen(self, r):
        return r.get("numero_registro")

    def nombre_origen(self, r):
        return N.limpiar(r.get("denominacion"))

    def transformar(self, r):
        area, subarea = r["area_id"], r["subarea_id"]
        ambito = AMBITO_POR_AREA.get((area, subarea)) or AMBITO_POR_AREA.get((area, None))
        if not ambito:
            raise Rechazo(f"área/subárea sin correspondencia: {area}/{subarea}")

        localidad = self.municipio(r["direccion_municipio_nombre"])
        provincia = r["direccion_provincia_id"]
        if provincia not in self.almacen.provincias:
            raise Rechazo(f"provincia no válida: {provincia!r}")

        direccion, direccion_selenium = montar_direccion(r)
        cp, latitud, longitud = self.geolocalizar(direccion_selenium, localidad, provincia)

        return {
            "nombre": N.limpiar(r["denominacion"]),
            "ambito": ambito,
            "direccion": direccion,
            "codigo_postal": cp,
            "latitud": latitud,
            "longitud": longitud,
            "descripcion": N.limpiar(r["subarea_nombre"]) or N.limpiar(r["area_nombre"]),
            "contacto": N.unir_contacto(self.telefono(r["telefono_1"]), self.telefono(r["telefono_2"])),
            "url": self.web(r["pagina_web"]),
            "localidad": localidad,
            "cod_provincia": cp[:2],
        }

    def municipio(self, valor):
        """'Palmas de Gran Canaria (Las)' -> 'Las Palmas de Gran Canaria';  'Oliva La' -> 'La Oliva'."""
        if N.vacio(valor):
            raise Rechazo("municipio desconocido")
        nombre = N.reordenar_articulo(N.limpiar(valor))
        m = re.fullmatch(r"(.+) (La|El|Los|Las)", nombre)
        if m:
            nombre = f"{m.group(2)} {m.group(1)}"
            self.reparado("localidad", valor, nombre, "artículo al final")
        return nombre

    def geolocalizar(self, direccion, localidad, provincia):
        """Pregunta a Selenium por la dirección completa. Solo se acepta si devuelve
        un CP de la misma provincia que dice la fuente; si no, se rechaza."""
        nombre_provincia = self.almacen.provincias[provincia]
        if N.sin_tildes(nombre_provincia) == N.sin_tildes(localidad):     # "Madrid, Madrid" le confunde
            consulta = f"{direccion}, {localidad}, España"
        else:
            consulta = f"{direccion}, {localidad}, {nombre_provincia}, España"
        resultado = self.geocoder.directo(consulta)
        if not resultado or not resultado["cp"]:
            raise Rechazo("no se pudo obtener el código postal de la dirección")
        if resultado["cp"][:2] != provincia:
            raise Rechazo(f"el código postal obtenido ({resultado['cp']}) no es de la provincia {provincia}")
        return resultado["cp"], resultado["lat"], resultado["lon"]

    def telefono(self, valor):
        """'(34)928414484' -> '928414484'. Si no es un teléfono válido, se deja vacío y se avisa."""
        if N.vacio(valor):
            return None
        numero = N.telefono(valor.replace("(34)", "", 1))
        if not numero:
            self.incidencia("contacto", f"teléfono no válido: {valor}")
        elif "+34" in valor:
            self.reparado("contacto", valor, numero, "prefijo +34 repetido")
        return numero

    def web(self, valor):
        """Arregla la web ('wwwadepsi.org' -> 'https://www.adepsi.org'). Si no es una web, vacío y aviso."""
        if N.vacio(valor):
            return None
        web = N.url(valor)
        if not web:
            self.incidencia("url", f"no es una web: {valor}")
        elif valor.lower().strip("/") not in web.lower():
            self.reparado("url", valor, web, "web mal escrita")
        return web


if __name__ == "__main__":
    json.dump(wrapper(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
