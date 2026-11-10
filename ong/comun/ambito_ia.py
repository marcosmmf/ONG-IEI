"""Clasificación de entidades mediante Gemini y caché local de resultados."""

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


RAIZ = Path(__file__).resolve().parents[2]
CACHE_POR_DEFECTO = RAIZ / "cache" / "ambito_cache.json"
MODELO_POR_DEFECTO = "gemini-3.8-flash"
load_dotenv(RAIZ / ".env")


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
        timeout=30,
    ):
        self.ambitos = tuple(sorted(almacen.ambitos))
        if not self.ambitos:
            raise AmbitoIAError("no hay ámbitos definidos en el almacén")
        self.cache_path = Path(cache_path)
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
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise AmbitoIAError(f"error al consultar Gemini: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AmbitoIAError("respuesta no válida de Gemini") from exc

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            return result["ambito"].strip()
        except (KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise AmbitoIAError("Gemini no devolvió un ámbito JSON válido") from exc

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
        texto = f"{nombre}\n{descripcion}".encode("utf-8")
        return hashlib.sha256(texto).hexdigest()
