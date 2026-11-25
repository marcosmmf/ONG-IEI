#!/usr/bin/env bash
# Arranca toda la aplicación: las 5 APIs (cada una en su puerto) y la web de los formularios.
#
#   ./arrancar.sh                 datos reales (lo que no esté en la caché se geolocaliza con Selenium: lento)
#   ./arrancar.sh --muestra       muestra de la demo (datos/muestra/, 12 registros por fuente)
#   ./arrancar.sh --solo-cache    no abrir Selenium: lo que no esté en cache/geocache.json se rechaza
#   ./arrancar.sh --visible       ver el navegador de Selenium mientras geolocaliza
#   ./arrancar.sh --sin-carga     no cargar al arrancar (se usa lo que ya hay en el almacén)
#   ./arrancar.sh --red           escuchar en todas las interfaces (para entrar a la VM desde fuera)
#
# Ctrl+C para todo.
cd "$(dirname "$0")"

export DATOS="" SOLO_CACHE=0 SELENIUM_VISIBLE=0 CARGA_INICIAL=1 ONG_HOST=127.0.0.1
for opcion in "$@"; do
  case "$opcion" in
    --muestra)    DATOS=muestra ;;
    --solo-cache) SOLO_CACHE=1 ;;
    --visible)    SELENIUM_VISIBLE=1 ;;
    --sin-carga)  CARGA_INICIAL=0 ;;
    --red)        ESCUCHA=0.0.0.0 ;;
    *) echo "Opción desconocida: $opcion (ver la cabecera de arrancar.sh)"; exit 1 ;;
  esac
done
ESCUCHA=${ESCUCHA:-127.0.0.1}

if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi

pids=()
parar() { echo; echo "Parando…"; kill "${pids[@]}" 2>/dev/null; wait 2>/dev/null; exit 0; }
trap parar INT TERM

lanzar() {   # nombre módulo puerto
  "$PY" -m uvicorn "servicios.$2:app" --host "$ESCUCHA" --port "$3" --log-level warning &
  pids+=($!)
  printf "  %-18s http://localhost:%s/docs\n" "$1" "$3"
}

echo "APIs (documentación Swagger en /docs, Redoc en /redoc):"
lanzar "Wrapper CV"      wrapper_cv   8001
lanzar "Wrapper CAT"     wrapper_cat  8002
lanzar "Wrapper CAN"     wrapper_can  8003
lanzar "API de carga"    api_carga    8004
lanzar "API de búsqueda" api_busqueda 8005

"$PY" -m http.server 8000 --bind "$ESCUCHA" --directory web >/dev/null 2>&1 &
pids+=($!)
echo
echo "Formularios:"
echo "  Búsqueda   http://localhost:8000/busqueda/"
echo "  Carga      http://localhost:8000/carga/"
[ "$CARGA_INICIAL" = 1 ] && echo && echo "Cargando el almacén con las 3 fuentes${DATOS:+ (muestra)}… (el progreso se ve en la web)"
echo "Ctrl+C para parar."
wait
