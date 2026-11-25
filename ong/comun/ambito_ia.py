"""Clasificación de entidades mediante Gemini y caché local de resultados."""

import json
import os
import ssl
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import certifi
from dotenv import load_dotenv

from ong.comun import caches


RAIZ = Path(__file__).resolve().parents[2]
CACHE_POR_DEFECTO = None      # None = la caché del modo (ong/comun/caches.py)
# Alias de Google que apunta siempre al último Flash-Lite: si retiran un modelo concreto, no se rompe.
# Se usa Lite porque el Flash normal da 503 (saturado) y timeouts; Lite responde en <1 s.
# GEMINI_MODEL en el .env es opcional; si ese modelo deja de existir (404) se vuelve a este alias.
MODELO_POR_DEFECTO = "gemini-flash-lite-latest"
load_dotenv(RAIZ / ".env")

# Certificados de certifi: el Python de python.org en macOS no trae los del sistema
# y urllib falla con CERTIFICATE_VERIFY_FAILED al conectar con Google.
_SSL = ssl.create_default_context(cafile=certifi.where())


class AmbitoIAError(RuntimeError):
    """Error al clasificar una entidad con la API de Gemini."""


class AmbitoIA:
    """Clasifica entidades en los ámbitos existentes en el almacén.

    ``almacen`` debe exponer el diccionario ``ambitos`` que ya carga
    :class:`ong.comun.almacen.Almacen`, con el nombre como clave.
    """

    def __init__(
        self,
        almacen,
        cache_path=CACHE_POR_DEFECTO,
        api_key=None,
        model=None,
        timeout=20,
    ):
        self.ambitos = tuple(sorted(almacen.ambitos))
        if not self.ambitos:
            raise AmbitoIAError("no hay ámbitos definidos en el almacén")
        self.cache_path = Path(cache_path) if cache_path else caches.ambito()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", MODELO_POR_DEFECTO)
        self.timeout = timeout
        self._cache = self._leer_cache()

    def clasificar(self, nombre, descripcion=""):
        """Devuelve el nombre de un ámbito válido para la entidad."""
        nombre = (nombre or "").strip()
        descripcion = (descripcion or "").strip()
        if not nombre:
            raise AmbitoIAError("no se puede clasificar una entidad sin nombre")

        clave = self._clave_cache(nombre, descripcion)
        if clave in self._cache:
            ambito = self._cache[clave]
            self._validar_ambito(ambito)
            return ambito

        if not self.api_key:
            raise AmbitoIAError("falta la variable de entorno GEMINI_API_KEY")

        ambito = self._consultar_gemini(nombre, descripcion)
        self._validar_ambito(ambito)
        self._cache[clave] = ambito
        self._guardar_cache()
        return ambito

    def _consultar_gemini(self, nombre, descripcion):
        prompt = (
            "Clasifica una organización no gubernamental española en exactamente "
            "uno de estos ámbitos permitidos:\n"
            f"{', '.join(self.ambitos)}\n\n"
            "Devuelve únicamente un objeto JSON con esta forma: "
            '{"ambito":"NOMBRE_DEL_AMBITO"}.\n'
            "No inventes categorías. Usa la descripción para decidir; si está "
            "vacía, infiere solo a partir del nombre.\n\n"
            f"Nombre: {nombre}\n"
            f"Descripción: {descripcion or '(sin descripción)'}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "ambito": {
                            "type": "STRING",
                            "enum": list(self.ambitos),
                        }
                    },
                    "required": ["ambito"],
                },
            },
        }
        datos = json.dumps(body, ensure_ascii=False).encode("utf-8")
        # La clave va en la cabecera (no en la URL) para que no salga en logs ni errores.
        cabeceras = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

        try:
            try:
                data = self._peticion(datos, cabeceras)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    # Límite de peticiones por minuto: se espera un poco y se reintenta UNA vez
                    time.sleep(5)
                elif exc.code == 404 and self.model != MODELO_POR_DEFECTO:
                    # El modelo del .env ya no existe: se usa el último Flash
                    self.model = MODELO_POR_DEFECTO
                else:
                    raise
                data = self._peticion(datos, cabeceras)
        except urllib.error.HTTPError as exc:
            detalle = exc.read().decode("utf-8", "replace")[:200]
            raise AmbitoIAError(f"Gemini respondió HTTP {exc.code}: {detalle}") from exc

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)["ambito"].strip()
        except (KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise AmbitoIAError(f"Gemini no devolvió un ámbito: {str(data)[:200]}") from exc

    def _peticion(self, datos, cabeceras):
        """Una llamada a Gemini. Los errores de red se convierten en AmbitoIAError
        (el registro se rechaza); los HTTPError se dejan pasar para tratar 429 y 404."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        request = urllib.request.Request(url, data=datos, headers=cabeceras, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=_SSL) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError:                # subclase de URLError: hay que dejarla pasar antes
            raise
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AmbitoIAError(f"error al consultar Gemini: {exc}") from exc

    def _validar_ambito(self, ambito):
        if ambito not in self.ambitos:
            raise AmbitoIAError(f"Gemini devolvió un ámbito no válido: {ambito!r}")

    def _leer_cache(self):
        if not self.cache_path.exists():
            return {}
        try:
            contenido = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AmbitoIAError(f"no se puede leer la caché {self.cache_path}: {exc}") from exc
        if not isinstance(contenido, dict):
            raise AmbitoIAError(f"formato inválido de la caché {self.cache_path}")
        return contenido

    def _guardar_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporal = tempfile.mkstemp(
            prefix=f"{self.cache_path.name}.",
            suffix=".tmp",
            dir=self.cache_path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fichero:
                json.dump(self._cache, fichero, ensure_ascii=False, indent=2)
                fichero.write("\n")
            os.replace(temporal, self.cache_path)
        except OSError as exc:
            try:
                os.unlink(temporal)
            except OSError:
                pass
            raise AmbitoIAError(f"no se puede guardar la caché: {exc}") from exc

    @staticmethod
    def _clave_cache(nombre, descripcion):
        """Clave legible ("nombre | descripción") para poder revisar la caché a mano."""
        return f"{nombre} | {descripcion}"
