"""Prueba los tres extractores con las entradas JSON de la muestra."""
import json
from pathlib import Path

from ong.comun.almacen import Almacen
from ong.comun.geocoder import Geocoder
from ong.comun.informe import html, tabla_resumen
from ong.extractores.extractor_can import ExtractorCAN
from ong.extractores.extractor_cat import ExtractorCAT
from ong.extractores.extractor_cv import ExtractorCV


RAIZ = Path(__file__).resolve().parent
MUESTRA = RAIZ / "datos" / "muestra" / "extractores"
SALIDA = RAIZ / "salida" / "extractores"


def mostrar_estado(almacen, momento):
    entidades, localidades = almacen.con.execute(
        "SELECT (SELECT count(*) FROM entidad), (SELECT count(*) FROM localidad)"
    ).fetchone()
    print(f"{momento}: {entidades} entidades y {localidades} localidades.")


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    almacen = Almacen(SALIDA / "demo.db")
    geocoder = Geocoder(usar_web=False)
    informes = []
    try:
        almacen.borrar()
        mostrar_estado(almacen, "Antes de ejecutar los extractores")
        for extractor in (ExtractorCV, ExtractorCAT, ExtractorCAN):
            ruta = MUESTRA / f"{extractor.FUENTE.lower()}.json"
            registros = json.loads(ruta.read_text(encoding="utf-8"))
            informes.append(extractor(almacen, geocoder).cargar(registros))
        print(tabla_resumen(informes))
        mostrar_estado(almacen, "Después de ejecutar los extractores")
    finally:
        almacen.cerrar()
        geocoder.cerrar()

    informe = SALIDA / "informe.html"
    informe.write_text(html(informes, "Prueba de los tres extractores"), encoding="utf-8")
    print(f"Informe por registro: {informe}")


if __name__ == "__main__":
    main()
