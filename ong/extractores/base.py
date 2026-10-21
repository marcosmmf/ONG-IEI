"""Parte común de los tres extractores.

Cada extractor (CV, CAT, CAN) solo tiene que implementar transformar(registro):
recibe UN registro tal cual sale de su wrapper y devuelve un dict con los campos
del esquema global:

    {"nombre", "ambito", "direccion", "codigo_postal", "latitud", "longitud",
     "descripcion", "contacto", "url", "localidad", "cod_provincia"}

Si un dato no se puede arreglar -> raise Rechazo("motivo")      (registro rechazado)
Si se arregla algo           -> self.reparado(campo, antes, despues, motivo)

La clase base se encarga de validar, insertar en el almacén y hacer el informe
(cargados / reparados / rechazados / duplicados), que es lo que mostrará el
formulario de carga en la 2a entrega.
"""
import re


class Rechazo(Exception):
    """El registro no se puede cargar."""


class Extractor:
    FUENTE = None           # "CV", "CAT", "CAN"

    def __init__(self, almacen, geocoder):
        self.almacen = almacen
        self.geocoder = geocoder
        self._reparaciones = []
        self._incidencias = []

    # ---------------------------------------------------------- a implementar
    def transformar(self, registro):
        raise NotImplementedError

    def id_origen(self, registro):
        """Identificador del registro en la fuente, solo para el informe."""
        return None

    # ------------------------------------------------------------- utilidades
    def reparado(self, campo, antes, despues, motivo=""):
        """Anota una reparación en el informe del registro actual."""
        if antes != despues:
            self._reparaciones.append({"campo": campo, "antes": antes, "despues": despues, "motivo": motivo})

    # ------------------------------------------------------------------ carga
    def incidencia(self, campo, motivo):
        """Registra una limitación del registro cargado sin contarla como reparación."""
        self._incidencias.append({"campo": campo, "motivo": motivo})

    def cargar(self, registros, limite=None):
        informe = {"fuente": self.FUENTE, "leidos": 0, "cargados": 0, "duplicados": 0,
                   "reparados": [], "rechazados": []}
        for registro in registros[:limite] if limite else registros:
            informe["leidos"] += 1
            self._reparaciones = []
            self._incidencias = []
            ident = {"id_origen": self.id_origen(registro)}
            try:
                e = self.transformar(registro)
                ident["nombre"] = e.get("nombre")
                self._validar(e)
                if not self.almacen.insertar_entidad(e, self.FUENTE):
                    informe["duplicados"] += 1
                    continue
                informe["cargados"] += 1
                if self._reparaciones:
                    informe["reparados"].append({**ident, "reparaciones": self._reparaciones})
                if self._incidencias:
                    informe.setdefault("incidencias", []).append({**ident, "incidencias": self._incidencias})
            except Rechazo as ex:
                informe["rechazados"].append({**ident, "motivo": str(ex)})
        self.almacen.commit()
        return informe

    def _validar(self, e):
        """Comprobaciones comunes a las tres fuentes (lo que necesita el buscador)."""
        for campo in ("nombre", "direccion", "localidad"):
            if not e.get(campo):
                raise Rechazo(f"falta {campo}")
        if e.get("ambito") not in self.almacen.ambitos:
            raise Rechazo(f"ámbito no válido: {e.get('ambito')!r}")
        if e.get("cod_provincia") not in self.almacen.provincias:
            raise Rechazo(f"provincia no válida: {e.get('cod_provincia')!r}")

        cp = e.get("codigo_postal")
        if cp and (not re.fullmatch(r"\d{5}", cp) or cp[:2] != e["cod_provincia"]):
            self.reparado("codigo_postal", cp, None, "CP no corresponde a la provincia; se descarta")
            e["codigo_postal"] = None

        lat, lon = e.get("latitud"), e.get("longitud")
        if lat is not None and not (27 <= lat <= 44 and -19 <= lon <= 5):     # fuera de España
            self.reparado("coordenadas", f"{lat},{lon}", None, "fuera de España; se descartan")
            e["latitud"] = e["longitud"] = None
