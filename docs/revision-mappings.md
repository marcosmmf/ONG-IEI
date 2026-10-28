# Revisión de los mappings frente a las fuentes reales

Criterio del profe: arreglar lo esencial para el **buscador** (localidad, CP, provincia, tipo = ámbito)
y para el **mapa** (latitud/longitud). Lo demás, solo si es barato.

Leyenda: 🔴 esencial · 🟡 recomendable/barato · ⚪ opcional (no perder tiempo)

## Comunitat Valenciana (`mappingsCV.pdf`)

Criterios acordados tras revisar el mapping. El documento Word ya se ha corregido según lo indicado
por el responsable de CV; esta revisión distingue esas decisiones del trabajo pendiente en el código.
El PDF del repositorio se encuentra en `docs/mappings/mappingsCV.pdf`.

| # | Regla o aspecto | Qué hay en la fuente | Decisión y estado |
|---|---|---|---|
| 1 | R1, R9 y R14: identificadores y relación Entidad → Localidad | `id` y `cod_ine_mun` son identificadores de origen | ✅ `E.codigo_entidad` y `L.codigo` son automáticos. Buscar la localidad por nombre y provincia; reutilizar su código si existe o crearla si no existe. `E.localidad` (`cod_localidad` en SQL) referencia ese código, nunca el código INE. Ya implementado en el almacén. El `id` original se usa en el informe. |
| 2 | R4: obtención del código postal | No hay CP | 🔴 **Toda entidad de CV cargada debe tener un CP válido.** Obtenerlo por geocodificación inversa de coordenadas fiables o por geocodificación directa de la dirección cuando las coordenadas sean genéricas. Validar cinco dígitos y coherencia con la provincia y la ubicación. Si no se consigue, rechazar e informar; no cargar con CP nulo ni asignar uno aproximado. Implementado en el extractor y en su validación específica de CV; comprobado con geocodificación simulada. La carga real requiere respuestas en caché o activar `--geo`. |
| 3 | R3: dirección | 8 vacías; 3 de ellas comparten la coordenada genérica de València | 🔴 Copiar y limpiar `domici`. Si falta y las coordenadas son fiables, intentar recuperarla mediante geocodificación inversa. No usar el punto genérico para atribuir una dirección al centro. Si no se obtiene una dirección verificable, rechazar e informar. Implementada la recuperación; se rechazan los casos que no puedan resolverse. Pendiente comprobar cuántos recupera el servicio real. |
| 4 | "Quitar FK L → P" | — | ✅ Era una fila sin sentido del documento antiguo, que ya está quitada. La BD mantiene `localidad.cod_provincia → provincia` (relación Localidad–Provincia del esquema global). No hay que cambiar nada. |
| 5 | R11 y R12: provincia | `cod_ine_mun` conserva sus cinco caracteres; nombres como "València/Valencia" | ✅ Obtener `P.codigo` de los dos primeros caracteres del código INE y el nombre normalizado del catálogo `provincia`, común a las tres fuentes. Ya implementado. |
| 6 | R5: coordenadas UTM → WGS84 | 32 centros de València comparten el punto genérico `(725733, 4372816)` | 🔴 La conversión utiliza el par `x_25830, y_25830` para obtener ambas coordenadas. Para el punto genérico, geolocalizar por dirección, municipio y provincia, si hay dirección disponible. No deducir CP ni dirección del punto genérico. Si no se consiguen coordenadas fiables, dejarlas nulas e informar; solo cargar si se dispone de dirección, CP válido y los demás campos obligatorios. El registro sin coordenadas no se mostrará en el mapa. Tratamiento implementado y comprobado con respuestas simuladas. Una respuesta directa que solo identifica el municipio también se rechaza. |
| 7 | R7: contacto | `zero@gva.es` y 68 teléfonos con valor "0" | ✅ Omitir `zero@gva.es`, teléfonos "0" y valores vacíos o inválidos; concatenar los contactos válidos con ` / `. Si no queda ninguno, usar `NULL`. El tratamiento de "0" ya está implementado. |
| 8 | R6: descripción | Ejemplo: "Entidad Privada - PERSONAS MAYORES" | 🟡 **Decidido: mantener `leyenda + " - " + sector`.** No sustituirlo por `tipo_centro`. Extractor adaptado a esta decisión. |
| 9 | Duplicados | 30 filas repetidas (mismo nombre, domicilio y municipio) | ✅ La BD evita duplicados mediante `UNIQUE(nombre, direccion, cod_localidad)` y se contabilizan en el informe. Mantener este criterio documentado en el mapping. |
| 10 | R13 y regla de ámbito sin correspondencia | Todos los sectores actuales tienen regla | ✅ Sin correspondencia, **rechazar e informar**, nunca asignar `NULL`: la BD exige ámbito. Este rechazo ya está implementado. |
| 11 | Excepción de ámbito para `CLUBS DE CONVIVENCIA` | 3 registros con sector "POBLACIÓN EN GENERAL Y COLECTIVOS SOCIALMENTE DESFAVORECIDOS" | **Pendiente de decidir.** El mapping y el código actuales asignan `VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA` como correspondencia aproximada. Se ha propuesto usar `INCLUSION_SOCIAL` según el sector, pero esa propuesta no está acordada. No cambiar la excepción todavía. |

Las reparaciones efectivas deben anotarse en el informe. Una consulta sin resultado no es una
reparación: informar del rechazo si falta dirección o CP, o de la incidencia si el registro se carga
con coordenadas nulas. Estas decisiones de CV no modifican por sí solas las políticas de CAT y CAN
ni las restricciones compartidas de la BD. La obligatoriedad del CP se aplica en la validación
específica de CV. El informe incluye `incidencias` cuando hay registros cargados sin coordenadas
fiables, separado de `reparados`. Las pruebas utilizan un geocoder simulado y SQLite en memoria;
no verifican la disponibilidad ni la precisión del servicio web real.

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
