# Buscador de ONGD — IEI 2026-27 (Equipo 4)

## Entrega 2: APIs, formularios y mapa

```
   Formulario de búsqueda + mapa          Formulario de carga            web/   (puerto 8000)
   localhost:8000/busqueda/               localhost:8000/carga/
            │  JSON                                │  JSON
     API de búsqueda (8005) ◄── almacen.db ◄── API de carga (8004)        servicios/
                                                   │  extractores CV / CAT / CAN (ong/extractores/)
                                                   │  HTTP, JSON
               Wrapper CV (8001)       Wrapper CAT (8002)       Wrapper CAN (8003)
               datos/cv/*.csv          datos/cat/*.xml          datos/can/*.json
```

### Las 5 APIs

Cada una corre en su puerto. Documentación OpenAPI en `/docs` (Swagger, se puede probar desde ahí) y
`/redoc`; la especificación exportada está en `docs/apis/*.openapi.json`
(se regenera con `python -m servicios.exportar_openapi`).

| API | Puerto | Endpoints | Parámetros |
|---|---|---|---|
| Wrapper CV  | 8001 | `GET /entidades` → CSV de la fuente en JSON | ninguno |
| Wrapper CAT | 8002 | `GET /entidades` → XML de la fuente en JSON | ninguno |
| Wrapper CAN | 8003 | `GET /entidades` → JSON de la fuente | ninguno |
| Carga       | 8004 | `POST /carga` `{"fuentes": ["cv","cat","can"]}` · `GET /carga/estado` (progreso) · `GET /carga/informe` · `DELETE /almacen` | fuentes |
| Búsqueda    | 8005 | `GET /entidades?localidad=&cp=&provincia=&tipo=` (formulario) · `GET /entidades/mapa?lat_min=&lat_max=&lon_min=&lon_max=` (mapa) · `GET /entidades/{id}` · `GET /tipos` · `GET /provincias` | filtros / zona |

- Los **wrappers** solo cambian el formato (la conversión a JSON que antes estaba en cada extractor).
- La **API de carga** pide el JSON a cada wrapper por HTTP, aplica el extractor y llena el almacén. La carga va
  en segundo plano: los formularios consultan `GET /carga/estado` para la barra de progreso.
- **Al arrancar se carga todo** (indicación del profe): la API de carga vacía el almacén y carga las tres fuentes.
  Mientras dura, la página de búsqueda enseña el progreso; al terminar aparecen el formulario y el mapa.
- **El mapa no depende de la búsqueda**: cada vez que se mueve o se hace zoom pide las entidades de la zona visible
  (`/entidades/mapa`); al pulsar un marcador se piden sus datos (`/entidades/{id}`). Buscar en el formulario no cambia el mapa.
- El campo **Tipo** del formulario es el ámbito de la entidad (tabla `ambito`).

### Arrancar

```bash
source .venv/bin/activate
pip install -r requirements.txt
./arrancar.sh --muestra          # demo: muestra de 12 registros por fuente
./arrancar.sh                    # datos reales
```

Desde Antigravity / VS Code: **Terminal → Run Task…** y elegir **Arrancar: datos de demo (muestra)** o
**Arrancar: datos completos** (`.vscode/tasks.json`). Para parar, Ctrl+C en el terminal de la tarea o cerrarlo.

Opciones: `--solo-cache` (sin Selenium), `--visible` (ver Selenium), `--sin-carga` (no cargar al arrancar),
`--red` (escuchar en todas las interfaces, para entrar a la VM desde otro equipo). Ctrl+C para todo.

### Cachés (demo y completa)

Cada modo tiene su caché de Selenium (`geocache.json`) y de Gemini (`ambito_cache.json`), con su propia copia
de seguridad en `backup/`:

| Caché | Carpeta | La usan |
|---|---|---|
| demo | `cache/demo/` | `./arrancar.sh --muestra`, `cargar.py --muestra`, tarea «datos de demo» |
| completa | `cache/completa/` | `./arrancar.sh`, `cargar.py` sin `--muestra`, tarea «datos completos» |

```bash
python cache.py                          # estado de las dos y de sus copias
python cache.py vaciar demo              # borra la caché (si no hay copia, la hace antes)
python cache.py restaurar demo           # vuelve a poner la copia de backup/
python cache.py guardar-copia completa   # la caché actual pasa a ser la copia de seguridad
python cache.py borrar-copia completa    # elimina la copia de seguridad
```

En Antigravity: tarea **Caché: ver, vaciar, restaurar o borrar copia** (pregunta la acción y la caché).
Mejor con la aplicación parada.

Con los datos completos, lo que no esté en `cache/completa/` se geolocaliza con Selenium (aprox. 1-2 s por
dirección): la primera carga tarda horas. Conviene llenarla una vez (`python cargar.py todas`) y después
`python cache.py guardar-copia completa`; las siguientes cargas salen de la caché.

**Mapa:** usa las teselas de CARTO si hay clave en `web/config.js` (no se sube a Git; plantilla en
`web/config.example.js`). Sin ese fichero usa OpenStreetMap, que no necesita clave.

### Estructura

```
servicios/   config.py (puertos), wrapper_cv/cat/can.py, api_carga.py, api_busqueda.py, exportar_openapi.py
web/         busqueda/ (formulario + mapa Leaflet), carga/ (formulario de carga), estilo.css, comun.js
ong/         extractores y utilidades de la Entrega 1 (almacén, geocoder, IA, informe)
docs/apis/   especificación OpenAPI de las 5 APIs
arrancar.sh  lanza todo
```

### Demo de la Entrega 2

1. `./arrancar.sh --muestra` y abrir `http://localhost:8000/busqueda/`: se ve la carga inicial y después el mapa con las tres fuentes.
2. Mover el mapa y hacer zoom: los marcadores cambian según la zona. Pulsar uno: metadatos de la entidad.
3. Buscar en el formulario (p. ej. provincia `valencia`, tipo `Mayores`): resultados en la lista; el mapa no cambia.
4. Página de Carga: borrar el almacén, cargar una fuente y ver el progreso y el informe (rechazados, reparados, duplicados).
5. Enseñar la documentación de cada API en `http://localhost:800X/docs`.

---

## Entrega 1

### Cómo funciona

```
                    extractor_cv.py            extractor_cat.py           extractor_can.py
datos/cv/*.csv   ─► wrapper ─► JSON ─┐
datos/cat/*.xml  ─► wrapper() ─► JSON ─┼─► ExtractorXX (aplica mappings, repara, rechaza, informe) ─► almacen.db (SQLite)
datos/can/*.json ─► wrapper() ─► JSON ─┘                          │
                                                                  └── geocoder (Selenium + caché)
```

En la 1ª entrega wrapper y extractor iban en el mismo archivo; en la 2ª la conversión a JSON
(`convertir()`) se ha llevado a `servicios/wrapper_{cv,cat,can}.py`, que además la sirven como API.
`cargar.py` sigue funcionando por consola llamando a esas funciones directamente.

- **Wrapper** (`servicios/wrapper_*.py`): solo convierte el formato de la fuente (CSV/XML/JSON) a una lista
  JSON con los campos *originales*.
- **`ExtractorXX`**: aplica el mapping semántico de su fuente (documentos en `docs/mappings/`) y devuelve
  una entidad del esquema global. La parte común (validar, insertar, informe de cargados / reparados /
  rechazados / duplicados) está en `ong/extractores/base.py`.
- **Geocoder** (`ong/comun/geocoder.py`): scraper con Selenium sobre coordenadas-gps.com, siguiendo
  el esquema del T07 (ir a la página → localizar elemento → `send_keys`/`click` → `WebDriverWait`).
  Las respuestas se guardan en `cache/demo/` o `cache/completa/` (se suben al repo) para no repetir consultas.
- **Almacén**: `sql/schema.sql` (SQLite, el que usa el código). `sql/schema_postgres.sql` es la misma
  estructura en PostgreSQL.

## Instalación (Mac o la VM Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Hace falta Google Chrome instalado (Selenium descarga solo el driver).

En Windows, activa el entorno virtual con `.venv\Scripts\Activate.ps1`.

## Uso

```bash
python cargar.py todas --borrar     # vacía el almacén y carga las 3 fuentes
python cargar.py cat --limite 20    # prueba rápida con 20 registros
python cargar.py can                # lo que no esté en caché se consulta con Selenium (LENTO la 1ª vez)
python cargar.py can --visible      # igual, pero viendo el navegador
python cargar.py can --solo-cache   # sin Selenium: solo lo que ya esté en la caché
python cargar.py todas --borrar --muestra   # DEMO: carga la muestra de datos/muestra/
```

### Muestra para la demo (`datos/muestra/`)
12 registros por fuente, con el mismo formato y nombre de fichero que el original. Incluye
casos modificados a propósito para que se vean reparaciones y rechazos: CP sin el 0 inicial
o de otra provincia, coordenadas imposibles o vacías, nombre vacío, provincia `_U` o desconocida,
municipio que no corresponde a la provincia…
Cada carga deja en `salida/` el JSON del wrapper y el informe de la carga.
Para ver la BD: `sqlite3 almacen.db` o DB Browser for SQLite.

### Clasificación del ámbito de Catalunya

La clase `ong/comun/ambito_ia.py` prepara la clasificación de las entidades
catalanas mediante Gemini Flash. Lee automáticamente las variables del archivo
`.env` situado en la raíz del proyecto:

```text
GEMINI_API_KEY=tu-clave-nueva
# GEMINI_MODEL=gemini-flash-lite-latest   (opcional: por defecto ya usa el último Flash-Lite)
```

El archivo `.env` está excluido de Git y no debe compartirse. Se incluye
`.env.example` como plantilla.

Las respuestas se guardan en `ambito_cache.json`, en la carpeta de caché del modo. Si una entidad ya está
en la caché, no se realiza otra llamada a la API; si Gemini falla o devuelve
un ámbito que no existe en la tabla `ambito`, la clase informa del error para
que el extractor pueda rechazar el registro.

## Demo de la 1ª entrega

El profesor quiere ver: (1) la base de datos **vacía**, (2) ejecutar la carga, (3) qué se ha llenado y cómo,
y qué se ha rechazado. Guion (con las cachés del repo no hace falta Selenium ni Gemini):

```bash
python cargar.py --borrar          # 1. vaciar el almacén
python ver_bd.py                   #    ... y enseñar que está vacío (solo provincias y ámbitos)
python cargar.py todas --muestra --abrir   # 2. cargar la muestra: informe en consola y en el navegador
python ver_bd.py                   # 3. enseñar las entidades cargadas (tipo, localidad, provincia, CP, lat/lon)
```

### Consola de opciones (`python demo.py`) o comandos a mano

Las dos formas hacen lo mismo: cada opción de `demo.py` enseña el comando que ejecuta antes de lanzarlo.
Por defecto usa la muestra y el navegador de Selenium visible (opciones 10-12 para cambiarlo).

| Para qué | Comando |
|---|---|
| Activar el entorno (lo primero, una vez por terminal) | `source .venv/bin/activate` |
| Consola de opciones | `python demo.py` |
| Vaciar la BD | `python cargar.py --borrar` |
| Ver la BD | `python ver_bd.py` (o `python ver_bd.py --fuente cv`) |
| Cargar una fuente de la muestra | `python cargar.py cv --muestra --abrir` |
| Cargar una fuente con los datos reales | `python cargar.py cv --abrir` |
| Ver el navegador de Selenium | añadir `--visible` al comando de carga |
| No usar Selenium (solo la caché) | añadir `--solo-cache` al comando de carga |
| Vaciar la caché | `python cache.py vaciar demo` (o `completa`) |
| Restaurar la caché | `python cache.py restaurar demo` (o `completa`) |
| Reabrir el informe | `open salida/informe.html` |

### Cachés en la demo (Selenium y Gemini en directo)

- Cachés de Selenium y Gemini, consulta a consulta: lo que **ya está** se aprovecha; lo que **falta** se
  consulta en directo y se guarda (salvo `--solo-cache`). Hay una para la muestra (`cache/demo/`) y otra
  para los datos completos (`cache/completa/`), cada una con su copia en `backup/` (ver «Cachés» arriba).

```bash
python cache.py vaciar demo                                # borra la caché demo (la copia queda en backup/)
python cargar.py cv --borrar --muestra --visible --abrir   # carga en directo viendo el navegador de Selenium
python cache.py restaurar demo                             # si algo falla: vuelve a poner la copia y se repite la carga
```
Con la caché vacía, CAT necesita internet y la clave de Gemini en `.env`.

El informe sale en consola (con colores) y se guarda en `salida/informe.txt` y en `salida/informe.html`
(página con tarjetas de resumen por fuente y filtros: cargados, rechazados, duplicados, con reparaciones, con avisos;
`--abrir` la abre en el navegador): por cada registro, **✔ cargado** (con sus
datos, las reparaciones antes → después y su motivo, y los avisos), **✖ rechazado** (con el motivo) o
**= duplicado**; al final, una tabla resumen por fuente. El detalle en JSON queda en `salida/<fuente>_informe.json`.
Para navegar por la BD con ventanas: [DB Browser for SQLite](https://sqlitebrowser.org), abriendo `almacen.db`.

Reglas: sin CP o sin coordenadas no se carga (indicación del profe). Los casos de la muestra y las
decisiones están en `docs/pendiente-demo.md` y `docs/revision-mappings.md`.

## Estado y reparto

Los extractores son un **esqueleto**: ya cargan, pero lo marcado con `TODO` está pendiente.
Busca `TODO` en `ong/extractores/` para ver qué falta. Resultado actual (sin geolocalizar):

| Fuente | Leídos | Cargados | Rechazados | Duplicados | Falta lo principal |
|---|---|---|---|---|---|
| CV  | 1697 | 1659 | 8 (sin dirección) | 30 | CP por geocodificación inversa |
| CAT | 765  | 764 | 1 (CP 00800)      | 0  | coordenadas |
| CAN | 810  | —    | —                  | —  | hecho; falta llenar la caché (carga completa) |

Propuesta de reparto:

1. **Extractor CV**: CP y direcciones vacías con `geocoder.inverso()`, coordenada genérica de València.
2. **Extractor CAT**: coordenadas con `geocoder.directo()`, reparar nombre/email/web/teléfonos, CP 00800.
3. **Extractor CAN**: CP y coordenadas con `geocoder.directo()`, municipios `_U`, abreviaturas, duplicados por NIF, webs.
4. **Ámbito CAT con API de IA**: integrado mediante `ong/comun/ambito_ia.py` y
   conectado en `extractor_cat.py`; si la API falla, el registro se rechaza y se informa.
5. **Documentación**: actualizar los mappings (ver `docs/revision-mappings.md`), lanzar la
   geolocalización completa (`python cargar.py todas`) para llenar la caché y preparar la demo en la VM.

**Pendiente de decidir:** el profe sugiere usar una *muestra representativa* para no esperar al
scraper con todos los registros. De momento se puede probar con `--limite N`; falta decidir cómo
elegir la muestra (que incluya los casos con errores de cada fuente).

Funciones ya hechas que podéis usar (`ong/comun/normalizar.py`): `limpiar`, `telefono`, `email`, `url`,
`codigo_postal`, `separar_toponimo` (recupera espacios de CAT), `reordenar_articulo` ("Palmas (Las)" →
"Las Palmas"), `unir_contacto`. Para anotar una reparación en el informe: `self.reparado(campo, antes, despues, motivo)`.
Para rechazar un registro: `raise Rechazo("motivo")`.
