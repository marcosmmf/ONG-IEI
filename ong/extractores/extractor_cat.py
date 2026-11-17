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
    """Recupera los espacios del nombre sin partir las palabras de NO_PARTIR.
    Además separa preposición + artículo pegados en minúscula delante de una mayúscula:
    'AssociacióperlaInserció' -> 'Associació per la Inserció'."""
    t = re.sub(r"(?<=[a-zà-ÿ])([Pp]er|[Pp]ara|[Cc]ontra|[Ss]obre)(la|les|el|els|los|las)(?=[A-ZÀ-Ý])",
               r" \1 \2 ", texto)
    protegido = re.sub(rf"({'|'.join(NO_PARTIR)})(?=[A-ZÀ-Ý])", r"\1 ", t)
    return N.limpiar(N.separar_toponimo(protegido))


def separar_numeros(direccion):
    """Separa los números pegados al texto en la dirección:
    'Martí19' -> 'Martí 19';  '52local7e' -> '52 local 7e';  '10àtic1a' -> '10 àtic 1a'.
    No toca '2n', '1a', '7è' (piso/puerta) ni separa números entre sí: '442n1a' es ambiguo
    (¿44, 2n 1a o 442?) y se deja como viene. Solo afecta a lo que se guarda; al mapa se le
    pregunta con direccion_para_mapa() sobre la dirección original."""
    d = re.sub(r"(?<=[A-Za-zÀ-ÿ]{2})(?=\d)", " ", direccion)
    d = re.sub(r"(?<=\d)(?=(?:local|baixos|baix|bxs|àtic|atic|planta|pral|principal|entresol"
               r"|entl|despatx|oficina|porta|esc)\b)", " ", d, flags=re.I)
    return N.limpiar(d)


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
        """Nombre para el informe (también de los rechazados), ya con los espacios recuperados."""
        return separar_nombre(r.get("nom_de_l_entitat") or "") or None

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
        self.reparado("localidad", r["municipi"], localidad,
                      "artículo pasado delante y espacios recuperados" if "(" in r["municipi"]
                      else "espacios recuperados")
        direccion_fuente = N.separar_toponimo(r["adre_a"])
        direccion = separar_numeros(direccion_fuente)       # lo que se guarda ("Martí 19")
        if not localidad or not direccion:
            raise Rechazo("falta localidad" if not localidad else "falta direccion")

        # ------------------------------------- CP y coordenadas (geocodificación)
        # Sin CP o sin coordenadas no se carga (indicación del profe). Las coordenadas solo
        # salen del mapa, así que la dirección TIENE que encontrarse en su municipio:
        #   1. formato del CP de la fuente ("8006" -> "08006"; "99033" o vacío -> no vale)
        #   2. se busca "calle número, CP municipio"; si aparece en el municipio -> vale
        #   3. si no, se busca sin el CP; si aparece en el municipio -> vale
        #   4. si no aparece en el municipio de ninguna forma -> rechazo
        # El CP de la fuente manda si es de la provincia donde está la dirección; si es
        # imposible o de otra provincia, se usa el del mapa y se informa.
        cp_fuente = N.codigo_postal(r["codi_postal"])            # None si no es válido ("00800")
        if cp_fuente:
            self.reparado("codigo_postal", r["codi_postal"], cp_fuente, "faltaba el 0 inicial")
        calle = direccion_para_mapa(direccion_fuente)              # sin piso ni puerta

        def en_su_municipio(geo):
            """El mapa ha encontrado la dirección en el municipio de la fuente (mismo nombre,
            o exactamente el CP de la fuente) y ha dado CP y coordenadas."""
            return bool(geo and geo.get("cp") and geo.get("lat") is not None and (
                N.sin_tildes(geo.get("localidad") or "") == N.sin_tildes(localidad)
                or geo["cp"] == cp_fuente))

        geo = self.geocoder.directo(f"{calle}, {cp_fuente} {localidad}, España") if cp_fuente else None
        if not en_su_municipio(geo):
            primera = geo
            geo = self.geocoder.directo(f"{calle}, {localidad}, España")
            if not en_su_municipio(geo):
                donde = (geo or primera or {}).get("direccion")
                raise Rechazo(f"Selenium no encuentra la dirección en {localidad}"
                              + (f" (la sitúa en «{donde}»)" if donde else "")
                              + "; sin coordenadas no se puede cargar")

        if cp_fuente and cp_fuente[:2] == geo["cp"][:2]:
            codigo_postal = cp_fuente
        else:
            codigo_postal = geo["cp"]
            self.reparado("codigo_postal", r["codi_postal"], codigo_postal,
                          f"el CP {cp_fuente} es de otra provincia; se usa el que da Selenium para la dirección"
                          if cp_fuente else
                          "CP no válido; se busca la dirección sin CP y se usa el que da Selenium")
        lat, lon = geo["lat"], geo["lon"]
        self.completado("Selenium", "coordenadas")       # la fuente no trae coordenadas

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
                self.reparado("email", trozo, email, "faltaba el punto del dominio"
                              if email.count(".") > trozo.count(".") else "email normalizado")
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

        ambito = self.clasificar_ambito(nombre, descripcion)
        self.completado("IA Gemini", "ambito")             # la fuente no trae el tipo
        return {
            "nombre": nombre,
            "ambito": ambito,
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
