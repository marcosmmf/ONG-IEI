"""Guarda la especificación OpenAPI de las 5 APIs en docs/apis/ (para entregarla junto al código).

    python -m servicios.exportar_openapi

Con la aplicación arrancada, la misma documentación se ve en /docs (Swagger) y /redoc de cada API.
"""
import json

from servicios import api_busqueda, api_carga, wrapper_can, wrapper_cat, wrapper_cv
from servicios.config import PUERTOS, RAIZ

APIS = {"wrapper_cv": (wrapper_cv, "cv"), "wrapper_cat": (wrapper_cat, "cat"), "wrapper_can": (wrapper_can, "can"),
        "api_carga": (api_carga, "carga"), "api_busqueda": (api_busqueda, "busqueda")}

if __name__ == "__main__":
    destino = RAIZ / "docs" / "apis"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, (modulo, puerto) in APIS.items():
        especificacion = modulo.app.openapi()
        especificacion["servers"] = [{"url": f"http://localhost:{PUERTOS[puerto]}"}]
        (destino / f"{nombre}.openapi.json").write_text(
            json.dumps(especificacion, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"docs/apis/{nombre}.openapi.json")
