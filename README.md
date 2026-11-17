# Buscador de ONGD — IEI 2026-27 (Equipo 4)

Entrega 1: almacén de datos + wrappers + extractores de las tres fuentes
(Comunitat Valenciana, Catalunya y Canarias).

## Cómo funciona

```
                    extractor_cv.py            extractor_cat.py           extractor_can.py
datos/cv/*.csv   ─► wrapper() ─► JSON ─┐
datos/cat/*.xml  ─► wrapper() ─► JSON ─┼─► ExtractorXX (aplica mappings, repara, rechaza, informe) ─► almacen.db (SQLite)
datos/can/*.json ─► wrapper() ─► JSON ─┘                          │
                                                                  └── geocoder (Selenium + caché)
```

Por indicación del profesor, en la 1ª entrega wrapper y extractor van **en el mismo archivo, uno por fuente**
(`ong/extractores/extractor_{cv,cat,can}.py`). Cada archivo hace: 1) abrir el fichero, 2) convertir a JSON
(`wrapper()`), 3) aplicar los mappings (`ExtractorXX`). Para ver solo el JSON del wrapper:
`python -m ong.extractores.extractor_cv`.

- **`wrapper()`**: solo convierte el formato de la fuente (CSV/XML/JSON) a una lista JSON con los campos
  *originales*. En la 2ª entrega se separará y cada wrapper será una API REST.
- **`ExtractorXX`**: aplica el mapping semántico de su fuente (documentos en `docs/mappings/`) y devuelve
  una entidad del esquema global. La parte común (validar, insertar, informe de cargados / reparados /
  rechazados / duplicados) está en `ong/extractores/base.py`.
- **Geocoder** (`ong/comun/geocoder.py`): scraper con Selenium sobre coordenadas-gps.com, siguiendo
  el esquema del T07 (ir a la página → localizar elemento → `send_keys`/`click` → `WebDriverWait`).
  Las respuestas se guardan en `cache/geocache.json` (se sube al repo) para no repetir consultas.
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

Las respuestas se guardan en `cache/ambito_cache.json`. Si una entidad ya está
en la caché, no se realiza otra llamada a la API; si Gemini falla o devuelve
un ámbito que no existe en la tabla `ambito`, la clase informa del error para
que el extractor pueda rechazar el registro.

## Demo de la 1ª entrega con solo los extractores

Con el entorno virtual activo, desde la raíz del repositorio:

```bash
python cargar.py --restaurar-cache
python demo_extractores.py
```

1. El script vacía las tablas de entidades y localidades de su base de demostración, `salida/extractores/demo.db`, y muestra ambos recuentos. Provincias y ámbitos son catálogos de referencia.
2. Cada extractor recibe directamente su lista JSON de `datos/muestra/extractores/`, con 12 registros y los campos de su fuente. Las cachés del repositorio cubren esta muestra.
3. La consola muestra el resumen por fuente y el recuento final de SQLite. Abre `salida/extractores/informe.html` para enseñar las reparaciones, avisos, duplicados y motivos de rechazo. Puedes inspeccionar `demo.db` con DB Browser for SQLite.

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
| Vaciar la caché | `python cargar.py --vaciar-cache` |
| Restaurar la caché | `python cargar.py --restaurar-cache` |
| Reabrir el informe | `open salida/informe.html` |

### Cachés en la demo (Selenium y Gemini en directo)

- `cache/geocache.json` (Selenium) y `cache/ambito_cache.json` (Gemini), consulta a consulta: lo que
  **ya está** se aprovecha; lo que **falta** se consulta en directo y se guarda (salvo `--solo-cache`).
- `cache/backup/` guarda una copia que no se toca nunca, por si Selenium o la IA fallan en la demo.

```bash
python cargar.py --vaciar-cache                       # borra las cachés (la copia queda en cache/backup/)
python cargar.py cv --borrar --muestra --visible --abrir   # carga en directo viendo el navegador de Selenium
python cargar.py --restaurar-cache                    # si algo falla: vuelve a poner la copia y se repite la carga
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
