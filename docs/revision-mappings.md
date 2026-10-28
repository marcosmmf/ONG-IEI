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

## Canarias (`docs/mappings/mappings-CAN.docx`)

| Prioridad | Pendiente | Qué falta |
|---|---|---|
| 🟡 | Corregir la regla de provincia | En el documento, sustituir `P.codigo ← Dirección completa` por `direccion_provincia_id`; si es `_U`, obtener el código de provincia de un CP válido recuperado. El código ya utiliza `direccion_provincia_id`, pero falta el tratamiento del valor desconocido. |
| 🔴 | Recuperar municipios `_U` | Para los 8 registros afectados, validar como CP el valor de `direccion_municipio_id` cuando corresponda, deducir provincia por sus dos primeros dígitos y recuperar la localidad con el geocoder. Sustituir la referencia «IA ¿?» del mapping por esta regla e implementarla en el extractor. |
| 🔴 | Obtener CP y coordenadas | La geocodificación ya está prevista en el mapping. Implementar la llamada a `geocoder.directo()` en el extractor, validar el CP frente a la provincia y comprobar las coordenadas. |
| 🟡 | Detectar duplicados por NIF | La detección por NIF ya está indicada en el mapping. Concretar e implementar qué registro se conserva y cómo se informa de los descartados; propuesta: conservar el primero válido e informar del resto. La restricción actual de nombre/dirección/localidad no sustituye esta comprobación. |
| 🟡 | Reparar webs | El mapping ya describe reparaciones, pero el extractor todavía copia `pagina_web` con limpieza básica. Aplicar la normalización y validación e informar de reparaciones o valores descartados. |
| ⚪ | Revisar las transformaciones de dirección | Decidir si se retira del mapping la expansión de abreviaturas, que no es prioritaria. Revisar también el requisito de evitar repetir tipo de vía o número, todavía pendiente en el extractor. |

## Decisión pendiente sobre la BD

- Decidir si se mantiene la columna técnica `fuente` (CV/CAT/CAN), que no aparece en el esquema global. Actualmente se utiliza para trazabilidad y borrado por fuente.
