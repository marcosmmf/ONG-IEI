// Utilidades comunes de los dos formularios.

// Cada API está en su puerto, en la misma máquina que sirve la web (localhost o la VM).
const API = {
  carga: `${location.protocol}//${location.hostname}:8004`,
  busqueda: `${location.protocol}//${location.hostname}:8005`,
};

const TIPOS = {
  MAYORES: "Mayores",
  DISCAPACIDAD: "Discapacidad",
  SALUD_MENTAL: "Salud mental",
  INFANCIA_Y_JUVENTUD: "Infancia y juventud",
  MUJER: "Mujer",
  MIGRACION: "Migración",
  INCLUSION_SOCIAL: "Inclusión social",
  EDUCACION_Y_FORMACION: "Educación y formación",
  EMPLEO_E_INSERCION_LABORAL: "Empleo e inserción laboral",
  SALUD_Y_ATENCION_SOCIOSANITARIA: "Salud y atención sociosanitaria",
  VOLUNTARIADO_Y_PARTICIPACION_COMUNITARIA: "Voluntariado y participación comunitaria",
  CULTURA_Y_DESARROLLO_COMUNITARIO: "Cultura y desarrollo comunitario",
};

const FUENTES = { CV: "Comunitat Valenciana", CAT: "Catalunya", CAN: "Canarias" };

/** Escapa texto para meterlo en HTML. */
function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** fetch que devuelve el JSON o lanza un Error con el mensaje de la API. */
async function pedir(url, opciones) {
  let r;
  try {
    r = await fetch(url, opciones);
  } catch {
    throw new Error(`No se puede conectar con ${new URL(url).origin}. ¿Está lanzado ./arrancar.sh?`);
  }
  const datos = await r.json().catch(() => null);
  if (!r.ok) {
    const detalle = datos?.detail;
    throw new Error(Array.isArray(detalle) ? detalle.map(d => d.msg).join("; ") : detalle || `Error ${r.status}`);
  }
  return datos;
}

/** Ficha de una entidad (resultados de la búsqueda y ventana del marcador del mapa). */
function fichaEntidad(e) {
  const web = e.url ? (/^https?:\/\//i.test(e.url) ? e.url : `https://${e.url}`) : null;
  return `
    <h3>${esc(e.nombre)}</h3>
    <div class="meta"><span class="tipo">${esc(TIPOS[e.tipo] || e.tipo)}</span>
      <span class="tenue"><span class="punto ${esc(e.fuente)}"></span>${esc(FUENTES[e.fuente] || e.fuente)}</span></div>
    <p>${esc(e.direccion)}<br>${esc(e.codigo_postal || "")} ${esc(e.localidad)} <span class="tenue">(${esc(e.provincia)})</span></p>
    ${e.contacto ? `<p class="tenue">${esc(e.contacto)}</p>` : ""}
    ${web ? `<p><a href="${esc(web)}" target="_blank" rel="noopener">${esc(e.url)}</a></p>` : ""}
    ${e.descripcion ? `<p class="descripcion">${esc(e.descripcion)}</p>` : ""}`;
}

/** Pinta las barras de progreso de la carga a partir de GET /carga/estado. */
function pintarProgreso(contenedor, estado) {
  contenedor.innerHTML = estado.fuentes.map(f => {
    const pct = f.total ? Math.round(100 * f.hechos / f.total) : (f.estado === "terminado" ? 100 : 0);
    const cuenta = f.estado === "pendiente" ? "en espera"
      : f.estado === "leyendo" ? "leyendo…"
      : f.estado === "error" ? "error"
      : `${f.hechos.toLocaleString("es")} / ${f.total.toLocaleString("es")}`;
    return `<div class="fuente ${f.estado}">
        <span>${esc(f.nombre)}</span>
        <div class="barra"><span style="width:${pct}%"></span></div>
        <span class="cuenta">${cuenta}</span>
        ${f.mensaje ? `<span class="mensaje">${esc(f.mensaje)}</span>` : ""}
      </div>`;
  }).join("");
}

/** Consulta el estado de la carga cada medio segundo hasta que termina. */
async function esperarCarga(alCambiar) {
  for (;;) {
    const estado = await pedir(`${API.carga}/carga/estado`);
    alCambiar(estado);
    if (!estado.en_curso) return estado;
    await new Promise(r => setTimeout(r, 500));
  }
}
