# Revisión de los mappings frente a las fuentes reales

Criterio del profe: arreglar lo esencial para el **buscador** (localidad, CP, provincia, tipo = ámbito)
y para el **mapa** (latitud/longitud). Lo demás, solo si es barato.

Leyenda: 🔴 esencial · 🟡 recomendable/barato · ⚪ opcional (no perder tiempo)

## Comunitat Valenciana (`mappings-CV.pdf`)

| # | Qué dice el mapping | Qué hay en la fuente | Propuesta |
|---|---|---|---|
| 1 | R1 `codigo_entidad ← id`, R9/R14 `L.codigo ← cod_ine_mun` | — | 🟡 Actualizar el documento: ahora son AUTO (corrección del profe). Solo es texto. |
| 2 | `codigo_postal ← NULL` | No hay CP | 🔴 El buscador filtra por CP: sacarlo de las coordenadas con el scraper (geocodificación inversa). Probado: devuelve el CP correcto. |
| 3 | `direccion ← domici` | 8 vacías | 🔴 Corrección del profe: obtenerla de las coordenadas (scraper inverso). Ahora se rechazan. |
| 4 | "Quitar FK L → P" | — | ✅ Era una fila sin sentido del documento antiguo, que ya está quitada. La BD mantiene `localidad.cod_provincia → provincia` (relación Localidad–Provincia del esquema global). No hay que cambiar nada. |
| 5 | `P.nombre ← provincia` (copia) | "València/Valencia" | 🟡 Ya resuelto: el nombre sale de la tabla `provincia` (igual para las 3 fuentes). |
| 6 | Coordenadas UTM → WGS84 | 32 centros de València con la misma coordenada genérica (centro de la ciudad) | ⚪ En el mapa saldrían amontonados. Se podría volver a geolocalizar su dirección. |
| 7 | `contacto`: descartar `zero@gva.es` | Además, 68 teléfonos son "0" | 🟡 Ya hecho: el "0" se trata como vacío. |
| 8 | `descripcion ← leyenda + sector` | Queda "Entidad Privada - PERSONAS MAYORES" | ⚪ `tipo_centro` describe mejor ("RESIDENCIA PARA PERSONAS MAYORES…"). Decidid; ahora usa `tipo_centro`. |
| 9 | — | 30 filas repetidas (mismo nombre, domicilio y municipio) | 🟡 La BD no las duplica (UNIQUE); salen como "duplicados" en el informe. Añadir una línea al documento. |
| 10 | Regla 10: sin correspondencia → `ambito NULL` | Todos los sectores tienen regla | 🟡 La BD exige ámbito: mejor "rechazar e informar" que NULL. |

## Catalunya (`mappings-CAT.docx`)

| # | Qué dice el mapping | Qué hay en la fuente | Propuesta |
|---|---|---|---|
| 1 | R1 `codigo_entidad ← n_mero_registre`, R10 `L.codigo ←` código INE | — | 🟡 Actualizar el documento: AUTO. Ya no hace falta la tabla INE. |
| 2 | Ámbito con API de IA, NULL si falla | No hay ningún campo de ámbito | 🔴 **Esencial** (filtro "Tipo" del buscador). Pendiente. Ojo: la BD tiene `ambito NOT NULL`, así que si la IA falla → **rechazar e informar** (no NULL). Guardar las respuestas en caché, como el geocoder, para que la carga sea reproducible y no gaste llamadas. |
| 3 | Nombre, dirección y municipio: copia directa | Todo sin espacios: "SantCugatdelVallès" | 🔴 Municipio: imprescindible para buscar por localidad → ya se recuperan los espacios ("Sant Cugat del Vallès"). 🔴 Dirección: con espacios el scraper geolocaliza a nivel de calle; sin ellos solo da el CP. 🟡 Nombre: misma función, coste cero. |
| 4 | CP válido solo si es de Barcelona/Girona/Lleida/Tarragona | `28003` (Madrid) y `00800` (Vilanova i la Geltrú) | 🟡 `28003` es un CP correcto de una entidad con sede en Madrid: aceptarlo (en Canarias también aceptamos sedes de fuera; la BD tiene las 52 provincias). `00800` → repararlo (es `08800`) con el scraper o rechazarlo e informar. |
| 5 | Coordenadas con Selenium | No hay coordenadas | 🔴 Esencial para el mapa. Pendiente (la función del scraper ya existe). |
| 6 | URL: copia directa "sin reparar" | Las 611 webs no tienen puntos (`http://wwwviaorges`) | 🟡 Tal cual son enlaces rotos. `N.url()` ya las arregla → `http://www.via.org.es`. Lo mismo con los emails (`N.email()`). |
| 7 | `contacto`: concatenar | 54 móviles con varios números separados por salto de línea | 🟡 Separar por salto de línea y validar cada uno. |

## Canarias (`mappings-CAN.docx`)

| # | Qué dice el mapping | Qué hay en la fuente | Propuesta |
|---|---|---|---|
| 1 | `P.codigo ←` "Dirección completa" | `direccion_provincia_id` existe | 🟡 Corregir el documento: `P.codigo ← direccion_provincia_id`; si es `_U`, los 2 primeros dígitos del CP. |
| 2 | Municipio `_U` → "deducido (IA ¿?)" | 8 registros: su `municipio_id` es en realidad un CP (35003, 38111…) | 🔴 Sin localidad no se pueden cargar: provincia = CP[:2] y localidad sacada del scraper. Sin IA. |
| 3 | CP y coordenadas con el scraper | No existen | 🔴 Esencial. Probado: la web devuelve calle + CP + coordenadas. |
| 4 | nif para detectar duplicados | 51 nif repetidos | 🟡 Quedarse con el primero e informar del resto. |
| 5 | Expandir abreviaturas (Avda → Avenida…) | 23 tipos de vía | ⚪ Estético; el scraper ya entiende "Avda". No merece la pena. |

## Cambios hechos en la BD (`sql/schema.sql`)

- `entidad.cod_entidad` y `localidad.codigo` → autonuméricos.
- `entidad.direccion` → NOT NULL (corrección de CV).
- `provincia` precargada con las 52 provincias (= diccionario CP → provincia).
- `localidad` → UNIQUE(nombre, cod_provincia); `entidad` → UNIQUE(nombre, direccion, cod_localidad).
- CHECKs de CP (5 dígitos) y de rango de latitud/longitud.
- Se ha quitado la coma final que daba error de sintaxis.
- Columna extra `fuente` (CV/CAT/CAN) para trazabilidad. **A debatir**: no está en el esquema global; se puede quitar.
