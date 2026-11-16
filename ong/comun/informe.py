"""Informe de carga legible: consola (con colores), salida/informe.txt y salida/informe.html.

Convierte los informes que devuelve Extractor.cargar() en texto o en una página HTML,
registro a registro y en el orden de la fuente: qué se ha cargado (y con qué datos), qué se
ha reparado (antes -> después y por qué), qué avisos hay, qué se ha rechazado (y por qué) y
qué estaba duplicado.
"""
import html as _html
from datetime import datetime

NOMBRES = {"CV": "Comunitat Valenciana", "CAT": "Catalunya", "CAN": "Canarias"}
ANCHO_NOMBRE = 60

# Colores ANSI para la terminal (solo si se pide color=True; el .txt va sin colores)
_ANSI = {"verde": "32", "rojo": "31", "gris": "90", "azul": "36", "amarillo": "33",
         "negrita": "1", "tenue": "2"}


def _c(texto, *estilos, color=True):
    if not color:
        return texto
    return "".join(f"\033[{_ANSI[e]}m" for e in estilos) + texto + "\033[0m"


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


def resumen(informe, color=False):
    partes = [(f"{informe['leidos']} leídos", ()),
              (f"{informe['cargados']} cargados", ("verde",)),
              (f"{informe['duplicados']} duplicados", ("gris",)),
              (f"{len(informe['rechazados'])} rechazados", ("rojo",)),
              (f"{len(informe['reparados'])} con reparaciones", ("azul",)),
              (f"{len(informe.get('incidencias', []))} con avisos", ("amarillo",))]
    return " · ".join(_c(t, *e, color=color) if e else t for t, e in partes)


# ------------------------------------------------------------------------------- texto
def texto(informe, color=False):
    """Informe de una fuente, registro a registro (color=True para la terminal)."""
    fuente = informe["fuente"]
    lineas = [_c(f"═══ {NOMBRES.get(fuente, fuente)} ({fuente}) ═══", "negrita", color=color),
              resumen(informe, color), ""]
    for r in informe.get("registros", []):
        cabecera = f"[{r['id_origen']}] {_nombre(r['nombre'])}"
        if r["resultado"] == "rechazado":
            lineas.append("  " + _c("✖ RECHAZADO ", "rojo", "negrita", color=color) + "  " + cabecera)
            lineas.append("        " + _c(f"motivo: {r['motivo']}", "rojo", color=color))
        elif r["resultado"] == "duplicado":
            lineas.append("  " + _c(f"= DUPLICADO   {cabecera}", "gris", color=color))
            lineas.append("        " + _c("ya cargado antes (mismo nombre, dirección y localidad); "
                                          "no se inserta otra vez", "gris", color=color))
        else:
            e = r["entidad"]
            lineas.append("  " + _c("✔ CARGADO   ", "verde", "negrita", color=color) + "  " + cabecera)
            lineas.append("        " + _c(f"{e['ambito']} · {e['localidad']} (prov. {e['cod_provincia']}) · "
                                          f"CP {e['codigo_postal']} · {e['latitud']:.5f}, {e['longitud']:.5f}",
                                          "tenue", color=color))
            for rep in r["reparaciones"]:
                lineas.append("        " + _c("reparado", "azul", color=color) + f"  {rep['campo']}: "
                              f"{_valor(rep['antes'])} → {_valor(rep['despues'])}"
                              + (_c(f"  ({rep['motivo']})", "tenue", color=color) if rep["motivo"] else ""))
            for inc in r["incidencias"]:
                lineas.append("        " + _c("aviso   ", "amarillo", color=color) + f"  {inc['campo']}: {inc['motivo']}")
    return "\n".join(lineas) + "\n"


def tabla_resumen(informes, color=False):
    """Tabla final con los totales de todas las fuentes cargadas."""
    cab = f"{'Fuente':<22}{'Leídos':>7}{'Cargados':>10}{'Duplic.':>9}{'Rechaz.':>9}{'Reparados':>11}{'Avisos':>8}"
    filas = [_c(cab, "negrita", color=color), "─" * len(cab)]
    for i in informes:
        filas.append(f"{NOMBRES.get(i['fuente'], i['fuente']):<22}{i['leidos']:>7}"
                     + _c(f"{i['cargados']:>10}", "verde", color=color)
                     + _c(f"{i['duplicados']:>9}", "gris", color=color)
                     + _c(f"{len(i['rechazados']):>9}", "rojo", color=color)
                     + _c(f"{len(i['reparados']):>11}", "azul", color=color)
                     + _c(f"{len(i.get('incidencias', [])):>8}", "amarillo", color=color))
    return "\n".join(filas) + "\n"


# -------------------------------------------------------------------------------- HTML
_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2330;--muted:#6b7280;--line:#e5e7eb;
--ok:#15803d;--ok-bg:#dcfce7;--ko:#b91c1c;--ko-bg:#fee2e2;--dup:#6b7280;--dup-bg:#f3f4f6;
--rep:#1d4ed8;--rep-bg:#dbeafe;--av:#a16207;--av-bg:#fef3c7}
@media (prefers-color-scheme:dark){:root{--bg:#111318;--card:#1a1d24;--text:#e5e7eb;--muted:#9ca3af;
--line:#2b2f38;--ok:#4ade80;--ok-bg:#14301f;--ko:#f87171;--ko-bg:#3a1717;--dup:#9ca3af;--dup-bg:#24272e;
--rep:#93c5fd;--rep-bg:#172a46;--av:#fcd34d;--av-bg:#3a2e10}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{margin:0 0 4px;font-size:26px}h2{margin:32px 0 12px;font-size:20px}
.sub{color:var(--muted);margin:0 0 20px}
.tarjetas{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.tarjeta{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.tarjeta h3{margin:0 0 8px;font-size:15px}.cifras{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:600}
.ok{color:var(--ok);background:var(--ok-bg)}.ko{color:var(--ko);background:var(--ko-bg)}
.dup{color:var(--dup);background:var(--dup-bg)}.rep{color:var(--rep);background:var(--rep-bg)}
.av{color:var(--av);background:var(--av-bg)}
.filtros{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 4px}
.filtros button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;
padding:6px 14px;font:inherit;cursor:pointer}.filtros button.activo{border-color:var(--text);font-weight:600}
.reg{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--line);
border-radius:10px;padding:10px 14px;margin:8px 0}
.reg.cargado{border-left-color:var(--ok)}.reg.rechazado{border-left-color:var(--ko)}
.reg.duplicado{border-left-color:var(--dup);opacity:.75}
.cab{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.id{color:var(--muted);font-size:13px}
.nombre{font-weight:600}.datos{color:var(--muted);font-size:13px;margin-top:4px}
ul{margin:6px 0 0;padding:0;list-style:none}li{margin:3px 0;font-size:14px}
li .chip{font-size:11px;padding:1px 8px;margin-right:6px}
.antes{text-decoration:line-through;color:var(--muted)}.motivo{color:var(--muted)}
.ko-txt{color:var(--ko)}code{font-size:13px}.vacio{color:var(--muted);font-style:italic;margin:4px 0}
@media (max-width:600px){h1{font-size:22px}}
"""

_JS = """
document.querySelectorAll('.filtros button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.filtros button').forEach(x=>x.classList.remove('activo'));
 b.classList.add('activo');const f=b.dataset.f;
 document.querySelectorAll('.reg').forEach(r=>{r.hidden=!(f==='todos'||r.classList.contains(f)||
  (f==='reparado'&&r.dataset.rep==='1')||(f==='aviso'&&r.dataset.av==='1'))});
 document.querySelectorAll('section').forEach(s=>{
  s.querySelector('.vacio').hidden=[...s.querySelectorAll('.reg')].some(r=>!r.hidden)});
});
"""


def _e(t):
    return _html.escape("" if t is None else str(t))


def _registro_html(r):
    rep = r.get("reparaciones") or []
    inc = r.get("incidencias") or []
    etiqueta = {"cargado": ("ok", "✔ Cargado"), "rechazado": ("ko", "✖ Rechazado"),
                "duplicado": ("dup", "= Duplicado")}[r["resultado"]]
    partes = [f'<div class="reg {r["resultado"]}" data-rep="{int(bool(rep))}" data-av="{int(bool(inc))}">',
              f'<div class="cab"><span class="chip {etiqueta[0]}">{etiqueta[1]}</span>'
              f'<span class="id">[{_e(r["id_origen"])}]</span><span class="nombre">{_e(r["nombre"])}</span></div>']
    if r["resultado"] == "rechazado":
        partes.append(f'<div class="datos ko-txt">Motivo: {_e(r["motivo"])}</div>')
    elif r["resultado"] == "duplicado":
        partes.append('<div class="datos">Ya cargado antes (mismo nombre, dirección y localidad); no se inserta otra vez.</div>')
    else:
        e = r["entidad"]
        partes.append(f'<div class="datos">{_e(e["ambito"])} · {_e(e["localidad"])} (prov. {_e(e["cod_provincia"])}) · '
                      f'CP {_e(e["codigo_postal"])} · {e["latitud"]:.5f}, {e["longitud"]:.5f}</div>')
        if rep or inc:
            partes.append("<ul>")
            for x in rep:
                partes.append(f'<li><span class="chip rep">reparado</span><code>{_e(x["campo"])}</code>: '
                              f'<span class="antes">{_e(_valor(x["antes"]))}</span> → <b>{_e(_valor(x["despues"]))}</b>'
                              + (f' <span class="motivo">({_e(x["motivo"])})</span>' if x["motivo"] else "") + "</li>")
            for x in inc:
                partes.append(f'<li><span class="chip av">aviso</span><code>{_e(x["campo"])}</code>: {_e(x["motivo"])}</li>')
            partes.append("</ul>")
    partes.append("</div>")
    return "".join(partes)


def html(informes, titulo="Informe de carga"):
    """Página HTML autocontenida con el resumen por fuente y el detalle filtrable."""
    total = {k: sum(i[k] for i in informes) for k in ("leidos", "cargados", "duplicados")}
    total["rechazados"] = sum(len(i["rechazados"]) for i in informes)
    tarjetas = []
    for i in informes:
        tarjetas.append(
            f'<div class="tarjeta"><h3>{_e(NOMBRES.get(i["fuente"], i["fuente"]))} ({_e(i["fuente"])})</h3>'
            f'<div class="cifras"><span class="chip dup">{i["leidos"]} leídos</span>'
            f'<span class="chip ok">{i["cargados"]} cargados</span>'
            f'<span class="chip ko">{len(i["rechazados"])} rechazados</span>'
            f'<span class="chip dup">{i["duplicados"]} duplicados</span>'
            f'<span class="chip rep">{len(i["reparados"])} con reparaciones</span>'
            f'<span class="chip av">{len(i.get("incidencias", []))} con avisos</span></div></div>')
    secciones = []
    for i in informes:
        secciones.append(f'<section><h2>{_e(NOMBRES.get(i["fuente"], i["fuente"]))} ({_e(i["fuente"])})</h2>'
                         + "".join(_registro_html(r) for r in i.get("registros", []))
                         + '<p class="vacio" hidden>Ninguno en esta fuente.</p></section>')
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(titulo)}</title><style>{_CSS}</style></head><body><main>
<h1>{_e(titulo)} · Buscador de ONGD</h1>
<p class="sub">{datetime.now():%d/%m/%Y %H:%M} · {total["leidos"]} registros leídos ·
<b>{total["cargados"]}</b> cargados · <b>{total["rechazados"]}</b> rechazados · {total["duplicados"]} duplicados.
Sin CP o sin coordenadas no se carga.</p>
<div class="tarjetas">{"".join(tarjetas)}</div>
<div class="filtros">
<button class="activo" data-f="todos">Todos</button><button data-f="cargado">✔ Cargados</button>
<button data-f="rechazado">✖ Rechazados</button><button data-f="duplicado">= Duplicados</button>
<button data-f="reparado">Con reparaciones</button><button data-f="aviso">Con avisos</button></div>
{"".join(secciones)}
</main><script>{_JS}</script></body></html>
"""
