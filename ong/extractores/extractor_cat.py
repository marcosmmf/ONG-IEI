"""Wrapper + extractor de Catalunya (mapping: docs/mappings/mappings-CAT.docx).

  1. wrapper():       abre el XML y lo convierte a JSON (solo cambia el formato, sin mappings).
                      En la 2a entrega se separará y se expondrá como API REST.
  2. ExtractorCAT:    aplica el mapping al esquema global, repara / rechaza y carga el almacén.

La fuente viene sin espacios ni puntos, y sin coordenadas ni ámbito: los espacios se
recuperan, las coordenadas se piden al geocoder (Selenium) y el ámbito a la IA.
"""
import json
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ong.comun import normalizar as N
from ong.comun.ambito_ia import AmbitoIA, AmbitoIAError
from ong.extractores.base import Extractor, Rechazo

FICHERO = Path(__file__).resolve().parents[2] / "datos" / "cat" / "Entitats_ONGD_pretty.xml"

# Campos que usa el extractor. Si a un registro le falta alguno, se trata como vacío.
CAMPOS = ("nom_de_l_entitat", "naturalesa", "adre_a", "codi_postal", "municipi",
          "tel_fon", "tel_fon_m_bil", "correu_electr_nic", "web")

# Palabras que acaban en "i" / "de" / "O" pero NO llevan conjunción detrás:
# "JordiEstapé" es "Jordi Estapé", no "Jord i Estapé".
NO_PARTIR = ("Jordi", "Mundi", "Mali", "Sri", "Beni", "Servei", "Esplai", "Yakali",
             "Langutani", "Amizade", "UNESCO")

# Piso, puerta, local... que van pegados al número de la calle ("2962n1a" = 296, 2n 1a)
PISO = (r"(?:1er|1r|2n|2on|3er|3r|4t|4rt|5è|6è|\d[aªº]|bis|baixos|bxs|baix|local|ppal|pral|principal"
        r"|entl|entresol|àtic|atic|soterrani|planta|oficina|despatx|esc|es carrer)")


def wrapper(ruta=FICHERO):
    """XML -> lista de dicts: cada <entitat> es {etiqueta: texto}; las etiquetas vacías (<web/>) quedan como ""."""
    raiz = ET.parse(ruta).getroot()
    return [{campo.tag: (campo.text or "").strip() for campo in entitat} for entitat in raiz.iter("entitat")]


def separar_nombre(texto):
    """Recupera los espacios del nombre sin partir las palabras de NO_PARTIR."""
    protegido = re.sub(rf"({'|'.join(NO_PARTIR)})(?=[A-ZÀ-Ý])", r"\1 ", texto)
    return N.separar_toponimo(protegido)


def separar_municipio(texto):
    """'VilanovailaGeltrú' -> 'Vilanova i la Geltrú';  "LaBisbald'Empordà" -> "La Bisbal d'Empordà"."""
    t = re.sub(r"(?<=[a-zà-ÿ])ila(?=[A-ZÀ-Ý])", " i la ", texto)
    t = re.sub(r"(?<=[a-zà-ÿ])(d['’])(?=[A-ZÀ-Ý])", r" \1", t)
    return N.reordenar_articulo(N.separar_toponimo(t))


def direccion_para_mapa(direccion):
    """Deja solo calle y número, que es lo que entiende el mapa:
    'Balmes, 2962n1a' -> 'Balmes 296'.  La dirección completa se guarda aparte."""
    d = re.sub(r"\(.*?\)", "", direccion)
    m = re.match(rf"(.*?\D)\s*(\d{{1,3}}?)(?=\s*{PISO}|[^\d]|$)", d, re.I)
    return f"{m.group(1).strip(' ,')} {m.group(2)}" if m else d


def quitar_carrer(texto):
    """En la fuente, 'c.' aparece cambiado por 'Carrer' dentro de webs y emails:
    'idhCarrerorg' -> 'idhc.org'."""
    return texto.replace("Carrer", "c.")


class ExtractorCAT(Extractor):
    FUENTE = "CAT"

    def __init__(self, almacen, geocoder):
        super().__init__(almacen, geocoder)
        self.ambito_ia = AmbitoIA(almacen)

    def id_origen(self, r):
        return r.get("n_mero_registre")

    def nombre_origen(self, r):
        return N.limpiar(r.get("nom_de_l_entitat"))

    def clasificar_ambito(self, nombre, descripcion):
        """Clasifica una entidad y transforma los errores de IA en rechazos."""
        try:
            return self.ambito_ia.clasificar(nombre, descripcion)
        except AmbitoIAError as exc:
            raise Rechazo(f"no se pudo clasificar el ámbito: {exc}") from exc

    def transformar(self, r):
        # Un campo que falte en el registro cuenta como vacío (no debe tumbar la carga)
        r = {campo: r.get(campo) or "" for campo in CAMPOS}

        # ---------------------------------------------------------- nombre
        # El XML viene sin espacios: "AccióSolidàriadelVallès" -> "Acció Solidària del Vallès"
        nombre = separar_nombre(r["nom_de_l_entitat"])
        if not nombre:
            raise Rechazo("falta nombre")
        self.reparado("nombre", r["nom_de_l_entitat"], nombre, "espacios recuperados")

        # ------------------------------------------- localidad y dirección
        localidad = separar_municipio(r["municipi"])
        self.reparado("localidad", r["municipi"], localidad, "espacios recuperados")
        direccion = N.separar_toponimo(r["adre_a"])
        if not localidad or not direccion:
            raise Rechazo("falta localidad" if not localidad else "falta direccion")

        # ------------------------------------------------- geocodificación
        # Al mapa se le pregunta por "calle número, CP localidad" (sin piso ni puerta)
        cp_fuente = N.codigo_postal(r["codi_postal"])            # None si no es válido ("00800")
        calle = direccion_para_mapa(direccion)
        if cp_fuente:
            geo = self.geocoder.directo(f"{calle}, {cp_fuente} {localidad}, España")
        else:
            geo = self.geocoder.directo(f"{calle}, {localidad}, España")

        # --------------------------------------------------- código postal
        if cp_fuente:
            self.reparado("codigo_postal", r["codi_postal"], cp_fuente, "faltaba el 0 inicial")
        # El CP del mapa solo sirve para reparar si el mapa ha encontrado la misma localidad
        misma_localidad = bool(geo and geo["cp"]
                               and N.sin_tildes(geo["localidad"] or "") == N.sin_tildes(localidad))
        if cp_fuente and not (misma_localidad and geo["cp"][:2] != cp_fuente[:2]):
            codigo_postal = cp_fuente
        elif misma_localidad:
            codigo_postal = geo["cp"]
            motivo = ("el CP era de otra provincia; reparado con geocoder" if cp_fuente
                      else "CP no válido; reparado con geocoder")
            self.reparado("codigo_postal", r["codi_postal"], codigo_postal, motivo)
        else:
            raise Rechazo(f"código postal no válido: {r['codi_postal']!r}")

        # ----------------------------------------------------- coordenadas
        # Solo se aceptan si el mapa contesta con un CP de la misma provincia
        lat = lon = None
        if not geo:
            self.incidencia("coordenadas", "dirección no encontrada en el mapa; no se mostrará en el mapa")
        elif geo["cp"] and geo["cp"][:2] == codigo_postal[:2]:
            lat, lon = geo["lat"], geo["lon"]
        else:
            self.incidencia("coordenadas", f"el mapa devuelve otra zona ({geo['direccion']}); se carga sin coordenadas")

        # -------------------------------------------------------------- web
        url = None
        if not N.vacio(r["web"]):
            web = quitar_carrer(r["web"])
            web = re.sub(r"^(?:h+t+p+s?:/+)+", "http://", web, flags=re.I)     # "http://https://..." -> "http://..."
            url = N.url(web)
            if url:
                self.reparado("url", r["web"], url, "puntos añadidos y dominios reparados")
            else:
                self.incidencia("url", f"web no válida: {r['web']!r}")

        # ----------------------------------------------------------- emails
        emails = []
        for trozo in re.split(r"[\n,;/\s]+", r["correu_electr_nic"]):
            if N.vacio(trozo):
                continue
            email = N.email(quitar_carrer(trozo))
            if email:
                emails.append(email)
                self.reparado("email", trozo, email, "email normalizado")
            else:
                self.incidencia("contacto", f"email no válido: {trozo!r}")

        # -------------------------------------------------------- teléfonos
        # Puede haber varios, uno por línea, y con extensión: "932065910 Ext187" -> "932065910"
        tels = []
        for campo in (r["tel_fon"], r["tel_fon_m_bil"]):
            for linea in campo.splitlines():
                if not linea.strip():
                    continue
                tel = N.telefono(re.split(r"(?i)\s*(?:ext|/|\()", linea)[0])
                if tel:
                    tels.append(tel)
                    self.reparado("telefono", linea, tel, "número reparado")
                else:
                    self.incidencia("contacto", f"teléfono no válido: {linea!r}")

        descripcion = N.separar_camel(r["naturalesa"])           # "AssociacióEstatal" -> "Associació Estatal"

        return {
            "nombre": nombre,
            "ambito": self.clasificar_ambito(nombre, descripcion),
            "direccion": direccion,
            "codigo_postal": codigo_postal,
            "latitud": lat,
            "longitud": lon,
            "descripcion": descripcion,
            "contacto": N.unir_contacto(*tels, *emails),
            "url": url,
            "localidad": localidad,
            "cod_provincia": codigo_postal[:2],          # diccionario CP -> provincia = tabla provincia
        }


if __name__ == "__main__":
    json.dump(wrapper(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
