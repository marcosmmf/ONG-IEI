"""Informe de carga legible (consola y salida/informe.txt).

Convierte el informe que devuelve Extractor.cargar() en texto, registro a registro y en el
orden de la fuente: qué se ha cargado (y con qué datos), qué se ha reparado (antes -> después
y por qué), qué avisos hay, qué se ha rechazado (y por qué) y qué estaba duplicado.
"""

NOMBRES = {"CV": "Comunitat Valenciana", "CAT": "Catalunya", "CAN": "Canarias"}
ANCHO_NOMBRE = 60


def _valor(v):
    """Valor de una reparación en una línea: None -> '—'; coordenadas -> 'lat, lon'."""
    if v is None or v == "":
        return "—"
    if isinstance(v, dict) and {"lat", "lon"} <= v.keys():
        return "—" if v["lat"] is None else f"{v['lat']}, {v['lon']}"
    return repr(v) if isinstance(v, str) else str(v)


def _nombre(texto):
    texto = texto or "(sin nombre)"
    return texto if len(texto) <= ANCHO_NOMBRE else texto[:ANCHO_NOMBRE - 1] + "…"


def resumen(informe):
    return (f"{informe['leidos']} leídos · {informe['cargados']} cargados · "
            f"{informe['duplicados']} duplicados · {len(informe['rechazados'])} rechazados · "
            f"{len(informe['reparados'])} con reparaciones · "
            f"{len(informe.get('incidencias', []))} con avisos")


def texto(informe):
    """Informe de una fuente, registro a registro."""
    fuente = informe["fuente"]
    lineas = [f"═══ {NOMBRES.get(fuente, fuente)} ({fuente}) ═══",
              resumen(informe), ""]
    for r in informe.get("registros", []):
        cabecera = f"[{r['id_origen']}] {_nombre(r['nombre'])}"
        if r["resultado"] == "rechazado":
            lineas.append(f"  ✖ RECHAZADO   {cabecera}")
            lineas.append(f"        motivo: {r['motivo']}")
        elif r["resultado"] == "duplicado":
            lineas.append(f"  = DUPLICADO   {cabecera}")
            lineas.append("        ya cargado antes (mismo nombre, dirección y localidad); no se inserta otra vez")
        else:
            e = r["entidad"]
            lineas.append(f"  ✔ CARGADO     {cabecera}")
            lineas.append(f"        {e['ambito']} · {e['localidad']} (prov. {e['cod_provincia']}) · "
                          f"CP {e['codigo_postal']} · {e['latitud']:.5f}, {e['longitud']:.5f}")
            for rep in r["reparaciones"]:
                lineas.append(f"        reparado  {rep['campo']}: {_valor(rep['antes'])} → "
                              f"{_valor(rep['despues'])}" + (f"  ({rep['motivo']})" if rep["motivo"] else ""))
            for inc in r["incidencias"]:
                lineas.append(f"        aviso     {inc['campo']}: {inc['motivo']}")
    return "\n".join(lineas) + "\n"


def tabla_resumen(informes):
    """Tabla final con los totales de todas las fuentes cargadas."""
    cab = f"{'Fuente':<22}{'Leídos':>7}{'Cargados':>10}{'Duplic.':>9}{'Rechaz.':>9}{'Reparados':>11}{'Avisos':>8}"
    filas = [cab, "─" * len(cab)]
    for i in informes:
        filas.append(f"{NOMBRES.get(i['fuente'], i['fuente']):<22}{i['leidos']:>7}{i['cargados']:>10}"
                     f"{i['duplicados']:>9}{len(i['rechazados']):>9}{len(i['reparados']):>11}"
                     f"{len(i.get('incidencias', [])):>8}")
    return "\n".join(filas) + "\n"
