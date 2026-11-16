# Estado de la demo (`--muestra`), 16-11-2026

Comando de la demo: `python cargar.py todas --borrar --muestra` (añadir `--geo` si falta algo en caché).
Con las cachés del repo da lo mismo con o sin Selenium.

| Fuente | Leídos | Cargados | Duplicados | Rechazados | Reparados | Avisos |
|---|---|---|---|---|---|---|
| CV  | 12 | 10 | 2 | 0 | 10 | 4 |
| CAT | 12 | 8  | 2 | 2 | 8  | 1 |
| CAN | 12 | 8  | 2 | 2 | 7  | 1 |

Ninguna entidad cargada sin CP ni sin coordenadas.

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
  (rechazado: la dirección no aparece en Barcelona) · 612 sin nombre (rechazado) · 266/264 duplicados.
- **CAN**: 00013 provincia 99 y 00012 provincia `_U` (reparadas con el código de municipio, confirmado por el
  CP) · TF00137 municipio_id de Las Palmas (cargado con aviso) · CA00016 sin nombre (rechazado) ·
  Padisbalta (rechazado: el mapa no encuentra la calle) · 2 duplicados.

## Pendiente
- Informe legible por registro en `cargar.py` (hoy el detalle está en `salida/*_informe.json`).
- Carga completa de las 3 fuentes con `--geo` para llenar las cachés (varias horas).
