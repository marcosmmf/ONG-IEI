"""Wrapper + extractor de Catalunya (mapping: docs/mappings/mappings-CAT.docx).

  1. wrapper():       abre el XML y lo convierte a JSON (solo cambia el formato, sin mappings).
                      En la 2a entrega se separará y se expondrá como API REST.
  2. ExtractorCAT:    aplica el mapping al esquema global, repara / rechaza y carga el almacén.

ESQUELETO: hace lo básico para que la carga funcione. Lo marcado con TODO es
el trabajo pendiente para repartir.
"""
import json
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ong.comun import normalizar as N
from ong.extractores.base import Extractor, Rechazo
from ong.comun.geocoder import Geocoder

FICHERO = Path(__file__).resolve().parents[2] / "datos" / "cat" / "Entitats_ONGD_pretty.xml"


def wrapper(ruta=FICHERO):
    """XML -> lista de dicts: cada <entitat> es {etiqueta: texto}; las etiquetas vacías (<web/>) quedan como ""."""
    raiz = ET.parse(ruta).getroot()
    return [{campo.tag: (campo.text or "").strip() for campo in entitat} for entitat in raiz.iter("entitat")]


def clasificar_ambito(r):
    """TODO: clasificar con una API de IA (nombre, naturalesa, municipi, web -> 1 de los 12 ámbitos).
    De momento devuelve un valor fijo para que la carga funcione."""
    return "VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA"


class ExtractorCAT(Extractor):
    FUENTE = "CAT"

    def id_origen(self, r):
        return r.get("n_mero_registre")

    def transformar(self, r):
        # El XML viene sin espacios: "SantCugatdelVallès" -> "Sant Cugat del Vallès"
        localidad = N.reordenar_articulo(N.separar_toponimo(r["municipi"]))
        self.reparado("localidad", r["municipi"], localidad, "espacios recuperados")

        direccion = N.separar_toponimo(r["adre_a"])
        geo = self.geocoder.directo(f"{direccion}, {localidad}, España")
        # TODO: CP 00800 (Vilanova i la Geltrú) -> repararlo con el geocoder en vez de rechazar
        if r["codi_postal"] == "00800":
            # Reparar el código postal con el geocoder
            if geo and geo["cp"]:
                codigo_postal = geo["cp"]
                self.reparado("codigo_postal", r["codi_postal"], codigo_postal, "código postal reparado con geocoder")
            else: 
                raise Rechazo(f"código postal no válido: {r['codi_postal']!r}")
        else:
            codigo_postal = N.codigo_postal(r["codi_postal"])
            if not codigo_postal:
                raise Rechazo(f"código postal no válido: {r['codi_postal']!r}")

        # TODO: coordenadas -> self.geocoder.directo(f"{direccion}, {codigo_postal} {localidad}, España")
        lat = geo["lat"] if geo and geo["lat"] else None
        lon = geo["lon"] if geo and geo["lon"] else None

        # TODO: reparar nombre, email (sin puntos) y web (sin puntos) con N.separar_toponimo / N.email / N.url
        nombre = N.separar_toponimo(r["nom_de_l_entitat"])
        self.reparado("nombre", r["nom_de_l_entitat"], nombre, "espacios recuperados")
        url = N.url(r["web"])
        if not N.vacio(r["web"]):
            if url:
                self.reparado("url", r["web"], url, "puntos añadidos y dominios reparados")
            else:
                self.incidencia("url", f"web no válida: {r['web']!r}")

        emails = []
        for trozo in re.split(r"[\n,;/\s]+", r["correu_electr_nic"]):
            if N.vacio(trozo):
                continue
            email = N.email(trozo)
            if email:
                emails.append(email)
                self.reparado("email", trozo, email, "email normalizado")
            else:
                self.incidencia("contacto", f"email no válido: {trozo!r}")
        # TODO: teléfonos con varios números separados por salto de línea
        tels = []
        for campo in (r["tel_fon"], r["tel_fon_m_bil"]):
            for linea in campo.splitlines():
                if linea.strip():
                    tel = N.telefono(linea)
                    if tel:
                        tels.append(tel)
                        self.reparado("telefono", linea, tel, "número reparado")
                    else:
                        self.incidencia("contacto", f"teléfono no válido: {linea!r}")
        contacto = N.unir_contacto(*tels, *emails)
        descripcion = N.limpiar(r["naturalesa"])

        return {
            "nombre": nombre,
            "ambito": clasificar_ambito(r),
            "direccion": direccion,
            "codigo_postal": codigo_postal,
            "latitud": lat,
            "longitud": lon,
            "descripcion": descripcion,
            "contacto": contacto,
            "url": url,
            "localidad": localidad,
            "cod_provincia": codigo_postal[:2],          # diccionario CP -> provincia = tabla provincia
        }


if __name__ == "__main__":
    json.dump(wrapper(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
