# Estado de la demo (`--muestra`), 17-11-2026

Comando de la demo: `python cargar.py todas --borrar --muestra` (lo que falte en caché se consulta con Selenium).

| Fuente | Leídos | Cargados | Duplicados | Rechazados | Reparados | Avisos |
|---|---|---|---|---|---|---|
| CV  | 12 | 10 | 2 | 0 | 4  | 4 (5 en directo) |
| CAT | 12 | 8  | 2 | 2 | 8  | 1 |
| CAN | 12 | 7  | 2 | 3 | 6  | 1 |

Ninguna entidad cargada sin CP ni sin coordenadas. Con la caché de `cache/backup/` y en directo salen las
mismas cifras salvo los avisos de CV: en directo el mapa nombra «La Pedrera» para el punto de Dénia (207)
y sale un aviso más (la caché guardó «03749 Denia»). Se carga igual.

Cambios del 17-11-2026 (comprobados con la demo antes/después, en directo y con la caché de respaldo):
- CAT: no se acepta una respuesta del mapa sin calle (solo CP o municipio = centro de la zona); si no la
  encuentra, se reintenta con «Carrer de …» y solo vale si devuelve esa misma calle. Arregla 992 Kemonik.
- CAN: se rechaza si el mapa da otra calle en otro municipio. Rechaza 00013 Tacoronte.

## Reglas generales
- **Sin CP o sin coordenadas no se carga** (el profe: "mejor rechazar; facilidad adicional no significa opcional").
- Si un dato de la fuente contradice a los demás, manda lo que dicen la mayoría y lo confirma el mapa;
  si se confirma se carga y se informa del dato erróneo; si no, se rechaza.
- El nombre se comprueba al principio en las 3 fuentes; los rechazados sin nombre salen como "(sin nombre)".

## Casos de la muestra
- **CV**: 66 coma decimal (reparado) · 207 provincia ≠ INE (reparado con INE) · 364 coordenadas 9999999
  (reparadas con el mapa) · 1645 Y vacía + "Km 3" (coordenadas aproximadas, aviso) · 1120/911/992 pedanías
  (CP aceptado por coordenadas oficiales, aviso) · 1491/911 duplicados.
- **CAT**: 110 CP sin 0 (reparado) · 476 CP 99033 (reparado con el mapa: 08033) · 324 CP 17012 en Barcelona
  (rechazado: con ese CP el mapa la sitúa en Terrassa; existe una en Gràcia, 08012, pero ponerle ese CP sería
  adivinar) · 992 Kemonik (el mapa solo la encuentra como «Carrer de Josep Aguilera i Martí 19»: número
  exacto y mismo CP) · 612 sin nombre (rechazado) · 266/264 duplicados.
- **CAN**: 00012 provincia `_U` (reparada con el código de municipio, confirmado por el CP) · 00013 Tacoronte
  (rechazado: el mapa da «Calle Real Orotava, 38359 El Sauzal», otra calle y otro municipio) · TF00137
  municipio_id de Las Palmas (cargado con aviso) · CA00016 sin nombre (rechazado) ·
  Padisbalta (rechazado: el mapa no encuentra la calle) · 2 duplicados.

## Pendiente
- Informe legible por registro en `cargar.py` (hoy el detalle está en `salida/*_informe.json`).
- Carga completa de las 3 fuentes (`python cargar.py todas`) para llenar las cachés (varias horas).
