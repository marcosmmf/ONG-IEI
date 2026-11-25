"""Parte común de los tres extractores.

Cada extractor (CV, CAT, CAN) solo tiene que implementar transformar(registro):
recibe UN registro tal cual sale de su wrapper y devuelve un dict con los campos
del esquema global:

    {"nombre", "ambito", "direccion", "codigo_postal", "latitud", "longitud",
     "descripcion", "contacto", "url", "localidad", "cod_provincia"}

Si un dato no se puede arreglar -> raise Rechazo("motivo")      (registro rechazado)
Si se arregla algo           -> self.reparado(campo, antes, despues, motivo)
Si un dato que la fuente NO trae se obtiene de fuera -> self.completado("Selenium", campo)
   (no es una reparación: forma parte del mapping; en el informe sale "(Selenium)")

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
        self._completados = {}

    # ---------------------------------------------------------- a implementar
    def transformar(self, registro):
        raise NotImplementedError

    def id_origen(self, registro):
        """Identificador del registro en la fuente, solo para el informe."""
        return None

    def nombre_origen(self, registro):
        """Nombre de la entidad en la fuente, para que los rechazados del informe se entiendan."""
        return None

    # ------------------------------------------------------------- utilidades
    def reparado(self, campo, antes, despues, motivo=""):
        """Anota una reparación en el informe del registro actual."""
        if antes != despues:
            self._reparaciones.append({"campo": campo, "antes": antes, "despues": despues, "motivo": motivo})

    def incidencia(self, campo, motivo):
        """Registra una limitación del registro cargado sin contarla como reparación."""
        self._incidencias.append({"campo": campo, "motivo": motivo})

    def completado(self, origen, *campos):
        """Marca datos que la fuente no trae y se obtienen de fuera ("Selenium", "IA Gemini").
        No es una reparación (no había nada mal en la fuente): en el informe sale el origen."""
        for campo in campos:
            self._completados[campo] = origen

    # ------------------------------------------------------------------ carga

    def cargar(self, registros, limite=None, progreso=None):
        """Carga los registros del wrapper. progreso(hechos, total), si se da, se llama tras cada
        registro (lo usa la API de carga para la barra de progreso)."""
        # "registros": el resultado de cada registro en el orden de la fuente (para el informe legible)
        informe = {"fuente": self.FUENTE, "leidos": 0, "cargados": 0, "duplicados": 0,
                   "reparados": [], "rechazados": [], "registros": []}
        registros = registros[:limite] if limite else registros
        for registro in registros:
            if progreso:
                progreso(informe["leidos"], len(registros))
            informe["leidos"] += 1
            self._reparaciones = []
            self._incidencias = []
            self._completados = {}
            ident = {"id_origen": self.id_origen(registro),
                     "nombre": self.nombre_origen(registro) or "(sin nombre)"}
            sin_consultar = self._sin_consultar()
            try:
                e = self.transformar(registro)
                ident["nombre"] = e.get("nombre") or ident["nombre"]
                self._validar(e)
                if not self.almacen.insertar_entidad(e, self.FUENTE):
                    informe["duplicados"] += 1
                    informe["registros"].append({**ident, "resultado": "duplicado"})
                    continue
                informe["cargados"] += 1
                informe["registros"].append({
                    **ident, "resultado": "cargado", "reparaciones": self._reparaciones,
                    "incidencias": self._incidencias, "completados": self._completados,
                    "entidad": {**{k: e.get(k) for k in ("ambito", "direccion", "localidad", "cod_provincia",
                                                         "codigo_postal", "latitud", "longitud")},
                                "provincia": self.almacen.provincias.get(e["cod_provincia"])}})
                if self._reparaciones:
                    informe["reparados"].append({**ident, "reparaciones": self._reparaciones})
                if self._incidencias:
                    informe.setdefault("incidencias", []).append({**ident, "incidencias": self._incidencias})
            except Rechazo as ex:
                motivo = str(ex)
                if self._sin_consultar() > sin_consultar:
                    # Selenium no llegó a preguntar: que el informe no lo confunda con "no existe"
                    motivo = "la dirección no está en la caché y Selenium está desactivado (--solo-cache)"
                informe["rechazados"].append({**ident, "motivo": motivo})
                informe["registros"].append({**ident, "resultado": "rechazado", "motivo": motivo})
        self.almacen.commit()
        if progreso:
            progreso(informe["leidos"], len(registros))
        return informe

    def _sin_consultar(self):
        """Búsquedas del geocoder que faltaban en la caché y no se hicieron (--solo-cache)."""
        n = getattr(self.geocoder, "sin_consultar", 0)
        return n if isinstance(n, int) else 0

    def _validar(self, e):
        """Comprobaciones comunes a las tres fuentes (lo que necesita el buscador)."""
        for campo in ("nombre", "direccion", "localidad"):
            if not e.get(campo):
                raise Rechazo(f"falta {campo}")
        if e.get("ambito") not in self.almacen.ambitos:
            raise Rechazo(f"ámbito no válido: {e.get('ambito')!r}")
        if e.get("cod_provincia") not in self.almacen.provincias:
            raise Rechazo(f"provincia no válida: {e.get('cod_provincia')!r}")

        # Norma del proyecto (confirmada por el profe): sin CP o sin coordenadas NO se carga.
        cp = e.get("codigo_postal")
        if not cp:
            raise Rechazo("falta código postal")
        if not re.fullmatch(r"\d{5}", cp) or cp[:2] != e["cod_provincia"]:
            raise Rechazo(f"el código postal {cp} no corresponde a la provincia {e['cod_provincia']}")

        lat, lon = e.get("latitud"), e.get("longitud")
        if lat is None or lon is None:
            raise Rechazo("faltan coordenadas: Selenium no ha localizado la dirección")
        if not (27 <= lat <= 44 and -19 <= lon <= 5):
            raise Rechazo(f"coordenadas fuera de España: {lat}, {lon}")
