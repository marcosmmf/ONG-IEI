"""Wrapper + extractor de Catalunya (mapping: docs/mappings/mappings-CAT.docx).

  1. wrapper():       abre el XML y lo convierte a JSON (solo cambia el formato, sin mappings).
                      En la 2a entrega se separará y se expondrá como API REST.
  2. ExtractorCAT:    aplica el mapping al esquema global, repara / rechaza y carga el almacén.

ESQUELETO: hace lo básico para que la carga funcione. Lo marcado con TODO es
el trabajo pendiente para repartir.
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ong.comun import normalizar as N
from ong.extractores.base import Extractor, Rechazo

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

    def nombre_origen(self, r):
        return N.limpiar(r.get("nom_de_l_entitat"))

    def transformar(self, r):
        # El XML viene sin espacios: "SantCugatdelVallès" -> "Sant Cugat del Vallès"
        localidad = N.reordenar_articulo(N.separar_toponimo(r["municipi"]))
        self.reparado("localidad", r["municipi"], localidad, "espacios recuperados")

        codigo_postal = N.codigo_postal(r["codi_postal"])
        if not codigo_postal:
            raise Rechazo(f"código postal no válido: {r['codi_postal']!r}")
        # TODO: CP 00800 (Vilanova i la Geltrú) -> repararlo con el geocoder en vez de rechazar

        direccion = N.separar_toponimo(r["adre_a"])

        # TODO: coordenadas -> self.geocoder.directo(f"{direccion}, {codigo_postal} {localidad}, España")
        # TODO: reparar nombre, email (sin puntos) y web (sin puntos) con N.separar_toponimo / N.email / N.url
        # TODO: teléfonos con varios números separados por salto de línea

        return {
            "nombre": N.limpiar(r["nom_de_l_entitat"]),
            "ambito": clasificar_ambito(r),
            "direccion": direccion,
            "codigo_postal": codigo_postal,
            "latitud": None,
            "longitud": None,
            "descripcion": N.limpiar(r["naturalesa"]),
            "contacto": N.unir_contacto(N.telefono(r["tel_fon"]), N.telefono(r["tel_fon_m_bil"]),
                                        N.limpiar(r["correu_electr_nic"])),
            "url": N.limpiar(r["web"]),
            "localidad": localidad,
            "cod_provincia": codigo_postal[:2],          # diccionario CP -> provincia = tabla provincia
        }


if __name__ == "__main__":
    json.dump(wrapper(*sys.argv[1:2]), sys.stdout, ensure_ascii=False, indent=2)
