// Página de carga: elegir fuentes, cargar (POST /carga), ver el progreso y el informe, borrar el almacén.

const formulario = document.getElementById("formulario");
const casillas = [...formulario.querySelectorAll('input[name="fuente"]')];
const todas = document.getElementById("todas");
const mensaje = document.getElementById("mensaje");
const botones = [...formulario.querySelectorAll("button")];

function avisar(texto, ok = false) {
  mensaje.textContent = texto;
  mensaje.className = ok ? "aviso ok" : "aviso";
  mensaje.hidden = !texto;
}

todas.addEventListener("change", () => casillas.forEach(c => (c.checked = todas.checked)));
casillas.forEach(c => c.addEventListener("change", () => {
  todas.checked = casillas.every(x => x.checked);
  todas.indeterminate = !todas.checked && casillas.some(x => x.checked);
}));

formulario.addEventListener("reset", () => {
  todas.indeterminate = false;
  avisar("");
});

formulario.addEventListener("submit", async evento => {
  evento.preventDefault();
  const fuentes = casillas.filter(c => c.checked).map(c => c.value);
  if (!fuentes.length) return avisar("Selecciona al menos una fuente.");
  avisar("");
  try {
    await pedir(`${API.carga}/carga`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fuentes }),
    });
    await seguirCarga();
  } catch (e) {
    avisar(e.message);
  }
});

document.getElementById("borrar").addEventListener("click", async () => {
  if (!confirm("¿Borrar todas las entidades del almacén de datos? No se puede deshacer.")) return;
  try {
    const r = await pedir(`${API.carga}/almacen`, { method: "DELETE" });
    avisar(`Almacén vaciado: se han borrado ${r.borradas.toLocaleString("es")} entidades.`, true);
    pintarInforme([], null, "El almacén está vacío.");
  } catch (e) {
    avisar(e.message);
  }
});

/** Enseña las barras mientras dura la carga y, al acabar, el informe. */
async function seguirCarga() {
  const seccion = document.getElementById("seccion-progreso");
  botones.forEach(b => (b.disabled = true));
  try {
    const estado = await esperarCarga(e => {
      seccion.hidden = !e.en_curso;
      if (e.en_curso) pintarProgreso(document.getElementById("progreso"), e);
    });
    const fallidas = estado.fuentes.filter(f => f.estado === "error");
    if (fallidas.length) avisar(fallidas.map(f => `${f.nombre}: ${f.mensaje}`).join(" · "));
    pintarInforme(await pedir(`${API.carga}/carga/informe`), estado.fin);
  } finally {
    seccion.hidden = true;
    botones.forEach(b => (b.disabled = false));
  }
}

// ------------------------------------------------------------------ informe
function pintarInforme(informes, fin, vacio = "Todavía no se ha hecho ninguna carga.") {
  const caja = document.getElementById("resultados");
  document.getElementById("cuando").textContent =
    fin ? `· ${new Date(fin).toLocaleString("es", { dateStyle: "short", timeStyle: "short" })}` : "";
  if (!informes.length) {
    caja.innerHTML = `<p class="tenue">${esc(vacio)}</p>`;
    return;
  }
  const filas = informes.map(i => `<tr>
      <td><span class="punto ${i.fuente}"></span>${esc(FUENTES[i.fuente])}</td>
      <td>${i.leidos}</td><td class="ok">${i.cargados}</td><td>${i.reparados.length}</td>
      <td class="${i.rechazados.length ? "mal" : ""}">${i.rechazados.length}</td><td>${i.duplicados}</td></tr>`).join("");
  const suma = k => informes.reduce((s, i) => s + (Array.isArray(i[k]) ? i[k].length : i[k]), 0);
  caja.innerHTML = `
    <div class="tabla"><table>
      <thead><tr><th>Fuente</th><th>Leídos</th><th>Cargados</th><th>Reparados</th><th>Rechazados</th><th>Duplicados</th></tr></thead>
      <tbody>${filas}</tbody>
      ${informes.length > 1 ? `<tfoot><tr><td><b>Total</b></td><td>${suma("leidos")}</td><td class="ok">${suma("cargados")}</td>
        <td>${suma("reparados")}</td><td>${suma("rechazados")}</td><td>${suma("duplicados")}</td></tr></tfoot>` : ""}
    </table></div>
    ${informes.map(detalleFuente).join("")}`;
}

function nombre(r) {
  return `<b>${esc(r.nombre)}</b>${r.id_origen ? ` <span class="tenue">#${esc(r.id_origen)}</span>` : ""}`;
}

function valor(v) {
  return v === null || v === undefined || v === "" ? "(vacío)" : esc(v);
}

function detalleFuente(i) {
  const duplicados = i.registros.filter(r => r.resultado === "duplicado");
  const grupo = (titulo, lista, pinta) => lista.length
    ? `<div class="grupo-informe"><h3>${titulo} (${lista.length})</h3><ul>${lista.map(r => `<li>${pinta(r)}</li>`).join("")}</ul></div>` : "";
  const cuerpo =
    grupo("Rechazados", i.rechazados, r => `${nombre(r)} — <span class="motivo">${esc(r.motivo)}</span>`) +
    grupo("Reparados", i.reparados, r => nombre(r) + r.reparaciones.map(c =>
      `<span class="cambio">${esc(c.campo)}: <s>${valor(c.antes)}</s> → <b>${valor(c.despues)}</b>${c.motivo ? ` · ${esc(c.motivo)}` : ""}</span>`).join("")) +
    grupo("Duplicados", duplicados, r => `${nombre(r)} <span class="tenue">— ya estaba en el almacén</span>`);
  return `<details>
      <summary><span class="punto ${i.fuente}"></span>${esc(FUENTES[i.fuente])}
        <span class="tenue">· ${i.rechazados.length} rechazados, ${i.reparados.length} reparados, ${duplicados.length} duplicados</span></summary>
      ${cuerpo || `<div class="grupo-informe"><p class="tenue">Todos los registros se han cargado sin cambios.</p></div>`}
    </details>`;
}

// -------------------------------------------------------------------- inicio
// Si hay una carga en marcha (por ejemplo, la del arranque) se sigue; si no, se enseña el último informe.
seguirCarga().catch(e => avisar(e.message));
