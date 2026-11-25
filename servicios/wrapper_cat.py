"""Wrapper CAT (puerto 8002): XML de Catalunya -> JSON.

    uvicorn servicios.wrapper_cat:app --port 8002     (o ./arrancar.sh, que lanza todo)
    GET http://localhost:8002/entidades               documentación: http://localhost:8002/docs
"""
import xml.etree.ElementTree as ET

from servicios.wrapper_base import crear_wrapper


def convertir(ruta):
    """XML -> lista de dicts: cada <entitat> es {etiqueta: texto}; las etiquetas vacías (<web/>) quedan como ""."""
    raiz = ET.parse(ruta).getroot()
    return [{campo.tag: (campo.text or "").strip() for campo in entitat} for entitat in raiz.iter("entitat")]


EJEMPLO = {"n_mero_registre": "612", "nom_de_l_entitat": "AssociacióAmicsdelPoble", "naturalesa": "Associació",
           "cif_entitat": "G85579191", "adre_a": "CarrerNicaragua106,7è3a", "codi_postal": "08029",
           "municipi": "Barcelona", "tel_fon": "931662475", "tel_fon_m_bil": "602300084",
           "correu_electr_nic": "ahcama427@gmailcom", "web": ""}

app = crear_wrapper("cat", convertir, "XML", EJEMPLO)
