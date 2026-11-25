"""Extractor de Canarias (mapping: docs/mappings/mappings-CAN.docx).

Recibe el JSON del wrapper CAN (servicios/wrapper_can.py, API en el puerto 8003), aplica el mapping
al esquema global, repara / rechaza y carga el almacén.

La fuente no tiene CP ni coordenadas: se obtienen con Selenium a partir de la
dirección completa. Decisiones explicadas en docs/revision-mappings.md (Canarias).
"""
import re

from ong.comun import normalizar as N
from ong.extractores.base import Extractor, Rechazo


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
        nombre = N.limpiar(r["denominacion"])
        if not nombre:                      # al principio, como en CV y CAT: sin gastar consulta a Selenium
            raise Rechazo("falta nombre")

        area, subarea = r["area_id"], r["subarea_id"]
        ambito = AMBITO_POR_AREA.get((area, subarea)) or AMBITO_POR_AREA.get((area, None))
        if not ambito:
            raise Rechazo(f"área/subárea sin correspondencia: {area}/{subarea}")

        localidad = self.municipio(r["direccion_municipio_nombre"])
        provincia = r["direccion_provincia_id"]
        nota = None         # reparación / aviso de la provincia: se escribe cuando Selenium da el CP
        if provincia not in self.almacen.provincias:
            # En toda la fuente, las 2 primeras cifras del código de municipio son la provincia
            # (802 de 802). Si la provincia falta o no existe ('_U', '99') se deduce de ahí;
            # geolocalizar() la confirma después: el CP del mapa tiene que ser de esa provincia.
            municipio_id = str(r.get("direccion_municipio_id") or "")
            deducida = municipio_id[:2] if re.fullmatch(r"\d{5}", municipio_id) else None
            if deducida not in self.almacen.provincias:
                raise Rechazo(f"provincia no válida: {provincia!r}")
            antes = "vacía" if N.vacio(provincia) else f"{provincia} ({r.get('direccion_provincia_nombre')})"
            nota = lambda cp, p=deducida, m=municipio_id, antes=antes: self.reparado(
                "provincia", antes, f"{p} ({self.almacen.provincias[p]})",
                f"la provincia de la fuente no existe; se toma de las 2 primeras cifras del código de "
                f"municipio ({m} → {p}) y el CP que da Selenium para la dirección ({cp}) también es de la {p}")
            provincia = deducida
        else:
            # El código de municipio contradice a la provincia (y al nombre del municipio):
            # mandan nombre + provincia, que confirma el CP del mapa; se avisa del código erróneo.
            municipio_id = str(r.get("direccion_municipio_id") or "")
            if re.fullmatch(r"\d{5}", municipio_id) and municipio_id[:2] != provincia:
                otra = municipio_id[:2]
                nota = lambda cp, p=provincia, m=municipio_id, otra=otra: self.incidencia(
                    "localidad", f"el código de municipio {m} indica la provincia {otra} "
                    f"({self.almacen.provincias.get(otra, 'desconocida')}), pero el nombre del municipio "
                    f"({localidad}) y la provincia de la fuente son de la {p}, y el CP que da Selenium ({cp}) "
                    f"también es de la {p}: se ignora el código de municipio")

        direccion, direccion_selenium = montar_direccion(r)
        tipo_en_nombre, _ = separar_tipo(N.limpiar(r["direccion_nombre_via"]) or "")
        if tipo_en_nombre and N.limpiar(r["direccion_tipo_via"]):
            self.reparado("direccion", f"{r['direccion_tipo_via']} {r['direccion_nombre_via']}",
                          direccion, "tipo de vía repetido")
        cp, latitud, longitud = self.geolocalizar(direccion_selenium, localidad, provincia)
        self.completado("Selenium", "codigo_postal", "coordenadas")     # la fuente no los trae
        if nota:
            nota(cp)

        return {
            "nombre": nombre,
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
        # "Laguna (La)" -> "La Laguna"; "Oliva La" -> "La Oliva"
        self.reparado("localidad", valor, nombre, "artículo al final pasado delante")
        return nombre

    def geolocalizar(self, direccion, localidad, provincia):
        """Pregunta a Selenium por la dirección completa. Solo se acepta si devuelve un CP de la
        misma provincia que dice la fuente y la dirección está en el municipio (o es la misma calle);
        si no, se rechaza."""
        nombre_provincia = self.almacen.provincias[provincia]
        if N.sin_tildes(nombre_provincia) == N.sin_tildes(localidad):     # "Madrid, Madrid" le confunde
            consulta = f"{direccion}, {localidad}, España"
        else:
            consulta = f"{direccion}, {localidad}, {nombre_provincia}, España"
        resultado = self.geocoder.directo(consulta)
        if not resultado or not resultado["cp"]:
            raise Rechazo("Selenium no encuentra la dirección: sin CP ni coordenadas no se puede cargar")
        # El mapa tiene que confirmar el municipio o, si nombra un núcleo ('La Cuesta' en La Laguna),
        # la misma calle. Si da otra calle en otro municipio ('Calle Real Orotava, 38359 El Sauzal' para
        # 'Calle Real 132, Tacoronte'), su CP y sus coordenadas no son de esta dirección.
        mismo_municipio = N.sin_tildes(resultado["localidad"] or "") == N.sin_tildes(localidad)
        calle = N.sin_tildes(separar_tipo(re.sub(r"\s+\S*\d\S*$", "", direccion))[1])
        misma_calle = any(N.sin_tildes(separar_tipo(parte.strip())[1]) == calle
                          for parte in resultado["direccion"].split(","))
        if not (mismo_municipio or misma_calle):
            raise Rechazo(f"Selenium sitúa la dirección en otra calle y otro municipio "
                          f"(«{resultado['direccion']}»); sin CP ni coordenadas fiables no se puede cargar")
        if resultado["cp"][:2] != provincia:
            raise Rechazo(f"el CP que da Selenium ({resultado['cp']}) no es de la provincia {provincia}")
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

