# Pendiente antes de la demo (revisión de `--muestra`, 15-11-2026)

Resultado de `python cargar.py todas --borrar --muestra --geo`:
CV 5 cargados / 6 rechazados / 1 duplicado · CAT 9 / 1 / 2 · CAN 6 / 4 / 2.

## ✅ CV resuelta
12 leídos → 10 cargados, 2 duplicados, 0 rechazados (también solo desde caché). Decisiones en `revision-mappings.md`.

## Decisiones pendientes (preguntas)

1. **CAT 324** — CP `17012` (Girona) con localidad Barcelona. Ahora se guarda Barcelona en la provincia 17 (mal).
   ¿Reparar con Selenium buscando sin CP (y rechazar si no lo encuentra) o rechazar siempre?
2. **CAN ERE2021TF00137** — `municipio_id` 35030 (Las Palmas) con municipio y provincia de Tenerife. Se carga sin aviso.
   ¿Cargar con aviso en el informe o rechazar?
3. **CV 207** (Dénia) — texto de provincia "València/Valencia" pero INE 03 (Alicante). Se carga sin aviso.
   ¿Reparar según el INE e informarlo, o rechazar?
4. **CV 1120, 911, 992** (registros sin modificar) — se rechazan porque Selenium nombra la pedanía/urbanización
   (El Perelló, Cales i Talaies, Mollón Blanc) en vez del municipio, aunque el CP es correcto.
   ¿Aceptar el CP de la geocodificación inversa si es de la misma provincia?
5. **Profe** — si hay CP/localidad/provincia/tipo pero Selenium no da coordenadas: ¿cargar sin mapa o rechazar?

## Fallos claros a arreglar (no necesitan decisión)

- **CV 66** — coordenada `4333847,00` (coma decimal): no se repara y acaba rechazado.
- **CAN ERE2026CA00016** — nombre vacío rechazado con motivo equivocado ("no se pudo obtener el CP"); debe ser "falta nombre" y comprobarse antes de Selenium/IA.
- **CAN** — el informe dice 0 reparados aunque repara "Laguna (La)" → "La Laguna" y "Calle Calle …".
- **Rechazados sin nombre** — en el informe salen como `None`.
- **CAT (estético)** — nombres "Associacióperla", "Asociaciónparala…Contrala"; direcciones "Martí19", "52local7e", "10àtic1a".

## Para que la demo sea reproducible

- Subir `cache/geocache.json` y `cache/ambito_cache.json` (Selenium y Gemini pueden fallar ese día).
- Repetir la carga solo desde caché y comprobar que da lo mismo.
- Instalar pytest y pasar los tests de CV antes y después de los cambios.
- Informe legible por registro en `cargar.py` (cargado / reparado / rechazado con motivo).
- Hacer commit del trabajo ya verificado (IA + muestra) antes de tocar los extractores.
