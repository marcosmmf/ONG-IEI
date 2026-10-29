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
python cargar.py can --geo          # geolocaliza con Selenium lo que no esté en caché (LENTO)
python cargar.py can --geo --visible  # igual, pero viendo el navegador
```
Cada carga deja en `salida/` el JSON del wrapper y el informe de la carga.
Para ver la BD: `sqlite3 almacen.db` o DB Browser for SQLite.

### Clasificación del ámbito de Catalunya

La clase `ong/comun/ambito_ia.py` prepara la clasificación de las entidades
catalanas mediante Gemini Flash. Lee automáticamente las variables del archivo
`.env` situado en la raíz del proyecto:

```text
GEMINI_API_KEY=tu-clave-nueva
GEMINI_MODEL=gemini-3.8-flash
```

El archivo `.env` está excluido de Git y no debe compartirse. Se incluye
`.env.example` como plantilla.

Las respuestas se guardan en `cache/ambito_cache.json`. Si una entidad ya está
en la caché, no se realiza otra llamada a la API; si Gemini falla o devuelve
un ámbito que no existe en la tabla `ambito`, la clase informa del error para
que el extractor pueda rechazar el registro.

## Demo de la 1ª entrega

El profesor quiere ver: (1) la base de datos **vacía**, (2) ejecutar la carga, (3) qué se ha llenado y cómo,
y qué se ha rechazado. Por eso el **informe de la carga tiene que ser claro y legible** (cargados, reparados
con antes/después y motivo, rechazados con motivo, duplicados). Hoy es solo `salida/*_informe.json`:
pendiente mejorarlo (p. ej. resumen en consola y/o informe más legible) antes de la demo.

## Estado y reparto

Los extractores son un **esqueleto**: ya cargan, pero lo marcado con `TODO` está pendiente.
Busca `TODO` en `ong/extractores/` para ver qué falta. Resultado actual (sin geolocalizar):

| Fuente | Leídos | Cargados | Rechazados | Duplicados | Falta lo principal |
|---|---|---|---|---|---|
| CV  | 1697 | 1659 | 8 (sin dirección) | 30 | CP por geocodificación inversa |
| CAT | 765  | 764  | 1 (CP 00800)      | 0  | coordenadas, ámbito con IA |
| CAN | 810  | 740  | 8 (municipio `_U`) | 62 | CP y coordenadas |

Propuesta de reparto:

1. **Extractor CV**: CP y direcciones vacías con `geocoder.inverso()`, coordenada genérica de València.
2. **Extractor CAT**: coordenadas con `geocoder.directo()`, reparar nombre/email/web/teléfonos, CP 00800.
3. **Extractor CAN**: CP y coordenadas con `geocoder.directo()`, municipios `_U`, abreviaturas, duplicados por NIF, webs.
4. **Ámbito CAT con API de IA** (`clasificar_ambito()` en `extractor_cat.py`).
5. **Documentación**: actualizar los mappings (ver `docs/revision-mappings.md`), lanzar la
   geolocalización completa con `--geo` para llenar la caché y preparar la demo en la VM.

**Pendiente de decidir:** el profe sugiere usar una *muestra representativa* para no esperar al
scraper con todos los registros. De momento se puede probar con `--limite N`; falta decidir cómo
elegir la muestra (que incluya los casos con errores de cada fuente).

Funciones ya hechas que podéis usar (`ong/comun/normalizar.py`): `limpiar`, `telefono`, `email`, `url`,
`codigo_postal`, `separar_toponimo` (recupera espacios de CAT), `reordenar_articulo` ("Palmas (Las)" →
"Las Palmas"), `unir_contacto`. Para anotar una reparación en el informe: `self.reparado(campo, antes, despues, motivo)`.
Para rechazar un registro: `raise Rechazo("motivo")`.
