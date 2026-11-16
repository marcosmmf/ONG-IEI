# Revisión de los mappings frente a las fuentes reales

Solo se recogen tareas pendientes de revisión, implementación o comprobación real.
Los puntos resueltos se han retirado de esta lista.

Criterio del profe: priorizar localidad, CP, provincia y tipo = ámbito para el **buscador**,
y latitud/longitud para el **mapa**. Lo demás, solo si es barato.

Leyenda: 🔴 esencial · 🟡 recomendable/barato · ⚪ opcional.

## Comunitat Valenciana (`docs/mappings/mappingsCV.pdf`)

El contenido del mapping está actualizado y el wrapper/extractor está adaptado.
Las pruebas automatizadas utilizan geocodificación simulada. Ya se ha realizado una prueba real
de ocho registros, incluidos los cinco iniciales y casos especiales; falta lo siguiente:

| Prioridad | Pendiente | Qué comprobar o corregir |
|---|---|---|
| 🔴 | Ampliar la prueba de geocodificación real | Probar más direcciones vacías y centros con el punto genérico de València, incluido un caso que pueda recuperarse mediante geocodificación directa. Verificar que el resultado corresponda al centro y no solo al municipio o provincia. Revisar reparaciones, rechazos e incidencias; la muestra inicial no valida los 1.697 registros. |
| ⚪ | Presentación del mapping | Eliminar la página 3 vacía y actualizar o retirar el bloque final «Después faltaría», que enumera tareas ya implementadas. |

### Decisiones tomadas con la muestra de la demo (15-11-2026)

| Caso | Decisión |
|---|---|
| Pedanías / urbanizaciones (El Perelló en Sueca…) | Con las coordenadas oficiales de la fuente, el CP de la geocodificación inversa se acepta si es de la provincia aunque el mapa nombre un núcleo distinto del municipio; se informa como aviso. En la geocodificación directa (a partir de la dirección) se sigue exigiendo que coincida el municipio. |
| Coordenada UTM con coma decimal (`4333847,00`) | Se repara a punto decimal y se informa. |
| Texto de `provincia` distinto del código INE | Manda el código INE (oficial, y coincide con coordenadas y CP); se informa como reparado. |
| Dirección con punto kilométrico (`Carretera …, Km 3`) que el mapa no encuentra | Se reintenta sin el "Km X"; se carga con el CP obtenido y aviso de coordenadas aproximadas. |

## Catalunya (`docs/mappings/mappings-CAT.docx`)

| Prioridad | Pendiente | Qué falta |
|---|---|---|
| 🟡 | Sincronizar los identificadores en el documento | La tabla principal ya indica generación automática, pero R1 y R10 y la tabla de reglas todavía copian `n_mero_registre` o buscan el código INE. Actualizar esas reglas y retirar las referencias a la búsqueda de códigos INE. |
| 🔴 | Clasificar el ámbito con IA | Implementar la llamada a la API, validar uno de los 12 ámbitos y guardar las respuestas en caché. El extractor sigue devolviendo un ámbito fijo. Corregir en el mapping «NULL si falla» por «rechazar e informar» cuando no se consiga un ámbito válido. |
| 🔴 | Completar la normalización de textos | Localidad y dirección ya pasan por las funciones de recuperación de espacios; reflejarlo en las reglas que aún indican copia directa y comprobar los resultados antes de geocodificar. Aplicar la recuperación de espacios también al nombre de la entidad. |
| 🟡 | Revisar las reglas de CP | Corregir el documento para aceptar sedes de fuera de Catalunya, como el registro con CP `28003`, ya aceptado por el código. Intentar reparar `00800` mediante geocodificación; el rechazo con informe ya existe si no puede recuperarse. |
| 🔴 | Obtener coordenadas | El mapping ya contempla Selenium, pero el extractor todavía no llama a `geocoder.directo()`. Implementar la consulta y validar su resultado. |
| 🟡 | Reparar emails y webs | Aplicar `N.email()` y `N.url()` donde sea posible e informar de las reparaciones. Actualizar la regla R9, que todavía exige copiar la URL «sin reparar». |
| 🟡 | Tratar teléfonos múltiples | Separar los números que vienen juntos, incluidos los separados por saltos de línea; validar cada uno y concatenar los contactos válidos. |

### Decisiones tomadas con la muestra de la demo (16-11-2026)

| Caso | Decisión |
|---|---|
| CP y coordenadas (sin coordenadas no se carga, indicación del profe) | 1) formato del CP (`8006` → `08006`); 2) se busca "calle número, CP municipio"; 3) si no aparece en el municipio, se busca sin CP; 4) si no aparece en el municipio de ninguna forma → rechazar. "En el municipio" = mismo nombre o exactamente el CP de la fuente (cubre pedanías). El CP de la fuente manda si es de la provincia donde está la dirección; si es imposible (`99033`) o de otra provincia, se usa el del mapa y se informa. |
| CP de otra provincia irreparable (324: `17012` en Barcelona; sin CP el mapa da una calle homónima en Terrassa) | Rechazar e informar dónde la sitúa el mapa. |
| Espacios | Nombres: se separan `per la`, `para la`, `contra la`… pegados (33 nombres). Direcciones: se separa el número del texto y de `local`, `baixos`, `àtic`… (268); los casos ambiguos (`442n1a`) se dejan. La consulta al mapa usa la dirección original (no cambia la caché). |
| Rechazados | Se informan con el nombre ya separado; los que no tienen nombre, como "(sin nombre)". |

## Canarias (`docs/mappings/mappings-CAN.docx`)

Las decisiones de abajo están implementadas en `ong/extractores/extractor_can.py` (la 8, en
`Almacen.localidad()`). Prueba real con 50 registros aleatorios: 36 cargados y 14 rechazados (13
porque Selenium no encuentra la calle y solo devuelve el municipio o nada; 1 por municipio `_U`).
2 de los cargados quedan en otro municipio de la misma provincia (Arona y Puerto de la Cruz en vez de
Santa Cruz de Tenerife), limitación asumida en la decisión 3.
El profe confirma que, si no se obtiene el CP, se rechaza: el CP es un criterio de búsqueda.

| Prioridad | Pendiente | Qué falta |
|---|---|---|
| 🔴 | Consultar al profe la caché del geocoder | Si se puede usar, ejecutar `python cargar.py can --geo` una vez (~20-25 min) para llenarla; si no, la carga consulta siempre la web. |
| 🟡 | Actualizar el Word | Pasar las correcciones del profe y las decisiones de esta tabla; borrar los comentarios en rojo. |

| # | Qué dice el mapping | Qué hay en la fuente | Decisión |
|---|---|---|---|
| 1 | `P.codigo ←` "Dirección completa" (corrección del profe) | `direccion_provincia_id` existe | ✅ **Decidido:** `P.codigo` = 2 primeros dígitos del CP que devuelve Selenium, que debe coincidir con `direccion_provincia_id` (ver #3). |
| 2 | Municipio `_U` → "deducido (IA ¿?)" | 8 registros: su `municipio_id` es en realidad un CP (35003, 38111…) | ✅ **Decidido:** rechazar e informar ("municipio desconocido"), sin consultar a Selenium. Sin IA. |
| 3 | CP y coordenadas con Selenium (corrección del profe) | No existen | ✅ **Decidido:** consultar a Selenium con la dirección completa (`tipo vía + nombre + número, municipio, provincia, España`). Se acepta solo si devuelve un CP cuyos 2 primeros dígitos coinciden con `direccion_provincia_id`; entonces se guardan CP, latitud y longitud. Si no devuelve CP o es de otra provincia → rechazar e informar ("no se pudo obtener el código postal"). No se compara el nombre del municipio (limitación asumida: no detecta una calle homónima en otro municipio de la misma provincia). |
| 3b | `L.codigo` ← código INE (corrección del profe) | — | ✅ Autonumérico en las 3 fuentes; quitar la tabla INE del documento. |
| 4 | nif para detectar duplicados | 810 filas y 745 nif distintos (misma entidad en varias áreas) | ✅ **Decidido (indicación del profe):** no se depura la fuente antes de cargar. Los duplicados se detectan después del mapping, justo antes de insertar: si ya existe una entidad con el mismo nombre, dirección y localidad, no se inserta y se informa como duplicada (ya implementado con `UNIQUE(nombre, direccion, cod_localidad)`). No se usa el nif porque no está en el esquema global. Limitación asumida: un mismo nif con direcciones distintas se carga como sedes distintas. |
| 5 | Dirección: concatenar y expandir abreviaturas (Avda → Avenida…) | 23 tipos de vía (algunos raros: Carre, Sbida, Branc…); ~100 nombres que ya incluyen el tipo y ~13 que ya incluyen el número | ✅ **Decidido:** expandir abreviaturas con una tabla; no repetir el tipo si el nombre ya empieza por él, ni el número si ya está en el nombre. Se guarda `tipo + nombre + número + complemento`. A Selenium se le pasa sin complemento y sin número si es "S/n". |
| 6 | Contacto: quitar "(34)", solo dígitos, unir con " / " | 7 entidades sin teléfono válido: 1 con prefijo doble `(34)+34650393946`, 6 con dígitos de más o de menos (`(34)6`) | ✅ **Decidido:** reparar el prefijo doble (→ `650393946`) e informar como reparado. Los otros 6: contacto vacío, la entidad se carga igual y se informa como incidencia ("teléfono no válido"). No se rechaza: el teléfono no es obligatorio. |
| 7 | URL: reparar con `N.url` | 191 webs; las reparables (`wwwadepsi.org`, `www. raiz…`, `hhtps://`) ya se arreglan; 3 con tilde o ñ (`www.acciónaborigen.com` ×2, `asociacionacompañame.com`) se pierden | ✅ **Decidido:** aceptar dominios con tilde o ñ. Las 5 que no son webs (texto libre, email, "facebook: …") → vacío; la entidad se carga igual y se informa como incidencia. Las reparadas se informan con antes/después. |
| 8 | `L.nombre`: reordenar artículo | `Palmas de Gran Canaria (Las)` ya se arregla; `Oliva La` (6, sin paréntesis) no; CAN escribe "Valencia" y CV "València" | ✅ **Decidido:** reparar `Oliva La` → `La Oliva` e informarlo. Además, en `Almacen.localidad()` (común a las 3 fuentes) buscar la localidad comparando el nombre sin tildes ni mayúsculas, para que el mismo municipio escrito distinto en dos fuentes sea una sola localidad (se queda el nombre del primero que se cargó). **Avisar al resto del equipo**: afecta a CV y CAT. |
| 9 | `E.descripcion` ← subárea, o área si la subárea es `_U` (comentario en rojo: "opcional dejar NULL") | Siempre hay área | ✅ **Decidido:** mantener la regla (ya implementada) y borrar el comentario en rojo del Word. |
| 10 | Provincia `_U` o inexistente (`99`) con municipio conocido (casos de la muestra) | En los 802 registros con provincia, las 2 primeras cifras de `municipio_id` son siempre la provincia | ✅ **Decidido (16-11):** deducir la provincia de `municipio_id`; se acepta solo si el CP de Selenium es de esa provincia. Se informa como reparado. (Los 8 `_U` sin nombre de municipio siguen rechazándose, #2.) |
| 11 | `municipio_id` de otra provincia que el municipio y la provincia (muestra: 35030 en Santa Cruz de Tenerife) | — | ✅ **Decidido (16-11):** mandan nombre del municipio y provincia (los confirma el CP del mapa); se carga y se informa como aviso. |
| 12 | Reparaciones que no salían en el informe | "Laguna (La)", "Calle" + "Calle Alcalde…" | ✅ Se informan como reparadas (artículo delante, tipo de vía repetido). Nombre vacío: se rechaza al principio ("falta nombre"), sin consultar a Selenium. |

## Decisión pendiente sobre la BD

- Decidir si se mantiene la columna técnica `fuente` (CV/CAT/CAN), que no aparece en el esquema global. Actualmente se utiliza para trazabilidad y borrado por fuente.
