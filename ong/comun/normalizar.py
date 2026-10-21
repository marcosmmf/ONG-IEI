"""Funciones de limpieza comunes a las tres fuentes.

Cada función devuelve el valor limpio; si además 'repara' algo, el extractor lo
anota en el informe comparando entrada y salida.
"""
import re

VACIOS = {"", "_U", "0", "-", "NULL", "NONE", "N/A", "S/D"}

MAYUS = "A-ZÁÉÍÓÚÀÈÒÏÜÑÇ"
MINUS = "a-záéíóúàèòïüñç"


def vacio(valor):
    return valor is None or str(valor).strip().upper() in VACIOS


def limpiar(texto):
    """Trim + espacios dobles -> uno. Devuelve None si está vacío."""
    if vacio(texto):
        return None
    return re.sub(r"\s+", " ", str(texto)).strip(" ,;")


def reordenar_articulo(nombre):
    """'Palmas de Gran Canaria (Las)' -> 'Las Palmas de Gran Canaria';
    "Hospitalet de Llobregat (L')" -> "L'Hospitalet de Llobregat"."""
    m = re.match(r"^(.*?)\s*\(([^)]+)\)$", nombre)
    if not m:
        return nombre
    base, art = m.group(1).strip(), m.group(2).strip()
    return f"{art}{base}" if art.endswith("'") else f"{art} {base}"


# ---------------------------------------------------------------------------
# Catalunya: el XML viene sin espacios ("SantCugatdelVallès"). Se recuperan
# separando por mayúsculas y, en topónimos, por partículas (de, del, i...).
# ---------------------------------------------------------------------------
_PARTICULAS = {"dels": "dels", "dela": "de la", "deles": "de les", "del": "del", "de": "de",
               "i": "i", "y": "y"}


def separar_camel(texto):
    if not texto:
        return texto
    t = re.sub(rf"(?<=[{MINUS}0-9º\.\)])(?=[{MAYUS}])", " ", texto)   # aB -> a B
    t = re.sub(rf"(?<=[{MAYUS}])(?=[{MAYUS}][{MINUS}])", " ", t)      # YEl -> Y El
    t = re.sub(r",(?=\S)", ", ", t)                                    # a,b -> a, b
    t = re.sub(r"(?<=[A-Za-zÀ-ÿ])(?=\()", " ", t)                      # a( -> a (
    return limpiar(t)


def separar_toponimo(texto):
    """'SantCugatdelVallès' -> 'Sant Cugat del Vallès'."""
    if not texto:
        return texto
    alternativas = "|".join(sorted(_PARTICULAS, key=len, reverse=True))
    t = re.sub(rf"(?<=[{MINUS}])({alternativas})(?=[{MAYUS}])",
               lambda m: " " + _PARTICULAS[m.group(1)] + " ", texto)
    return separar_camel(t)


# ---------------------------------------------------------------------------
# Contacto
# ---------------------------------------------------------------------------
def telefono(valor):
    """'(34)928414484' / '+34 928...' -> '928414484'. None si no es válido."""
    if vacio(valor):
        return None
    digitos = re.sub(r"\D", "", str(valor))
    if digitos.startswith("0034"):
        digitos = digitos[4:]
    elif digitos.startswith("34") and len(digitos) == 11:
        digitos = digitos[2:]
    return digitos if re.fullmatch(r"[6789]\d{8}", digitos) else None


_TLDS = ["org.es", "com.es", "info", "cat", "org", "com", "net", "eus", "gal", "edu", "eu", "es"]


def _arreglar_dominio(dominio):
    """Inserta los puntos que faltan: 'wwwviaorges' -> 'www.via.org.es'."""
    if dominio.startswith("www") and len(dominio) > 3 and dominio[3] != ".":
        dominio = "www." + dominio[3:]
    if dominio.count(".") > (1 if dominio.startswith("www.") else 0):
        return dominio
    for tld in _TLDS:
        plano = tld.replace(".", "")
        if dominio.endswith(plano) and len(dominio) > len(plano) + 1 and not dominio.endswith("." + plano):
            return dominio[: -len(plano)] + "." + tld
    return dominio


def url(valor):
    """Normaliza una web. None si no es una URL razonable."""
    if vacio(valor):
        return None
    u = re.sub(r"\s+", "", str(valor)).strip("/")
    u = re.sub(r"^hh?tt?ps?:/*", lambda m: "https://" if "s" in m.group(0) else "http://", u, flags=re.I)
    if "@" in u:
        return None
    esquema = "http://" if u.lower().startswith("http://") else "https://"
    resto = re.sub(r"^https?://", "", u, flags=re.I)
    dominio, _, ruta = resto.partition("/")
    dominio = _arreglar_dominio(dominio.lower())
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", dominio):
        return None
    return esquema + dominio + ("/" + ruta if ruta else "")


def email(valor):
    if vacio(valor):
        return None
    e = re.sub(r"\s+", "", str(valor)).lower()
    usuario, arroba, dominio = e.partition("@")
    if not arroba or not usuario or "@" in dominio:
        return None
    dominio = _arreglar_dominio(dominio)
    return f"{usuario}@{dominio}" if "." in dominio else None


def unir_contacto(*partes):
    vistos = []
    for p in partes:
        if p and p not in vistos:
            vistos.append(p)
    return " / ".join(vistos) or None


# ---------------------------------------------------------------------------
# Código postal
# ---------------------------------------------------------------------------
def codigo_postal(valor):
    """Devuelve el CP de 5 dígitos (rellena el 0 inicial perdido) o None."""
    if vacio(valor):
        return None
    d = re.sub(r"\D", "", str(valor))
    if len(d) == 4:
        d = "0" + d
    if len(d) != 5 or not ("01" <= d[:2] <= "52"):
        return None
    return d
