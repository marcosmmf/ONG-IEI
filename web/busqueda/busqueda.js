// Página de búsqueda: formulario (API de búsqueda, GET /entidades) y mapa (mashup, GET /entidades/mapa).
// El formulario y el mapa son independientes: buscar NO cambia lo que se ve en el mapa.

const COLOR = { CV: "#c2552d", CAT: "#2f5f98", CAN: "#c99a1c" };
const ESPANA = [[27.4, -18.4], [43.9, 4.4]];   // península, Baleares y Canarias

// ------------------------------------------------------------- 1) carga inicial
async function esperarAlmacen() {
  const pantalla = document.getElementById("cargando");
  const error = document.getElementById("error-carga");
  for (;;) {
    try {
      const estado = await esperarCarga(e => {
        if (e.en_curso) {
          pantalla.hidden = false;
          pintarProgreso(document.getElementById("progreso"), e);
        }
      });
      const fallidas = estado.fuentes.filter(f => f.estado === "error");
      if (fallidas.length && !pantalla.hidden) {
        error.textContent = "Algunas fuentes no se han podido cargar. Puedes reintentarlo desde la página de Carga.";
        error.hidden = false;
        await new Promise(r => setTimeout(r, 2500));
      }
      pantalla.hidden = true;
      return;
    } catch (e) {                      // la API de carga aún no responde: se sigue esperando
      pantalla.hidden = false;
      error.textContent = e.message;
      error.hidden = false;
      await new Promise(r => setTimeout(r, 1500));
    }
  }
}

// --------------------------------------------------------------- 2) formulario
async function rellenarDesplegables() {
  const tipo = document.getElementById("tipo");
  for (const [valor, texto] of Object.entries(TIPOS)) tipo.add(new Option(texto, valor));
  try {
    const provincias = await pedir(`${API.busqueda}/provincias`);
    document.getElementById("provincias").innerHTML =
      provincias.map(p => `<option value="${esc(p.nombre)}">`).join("");
  } catch { /* la lista es solo una ayuda */ }
}

async function buscar(evento) {
  evento.preventDefault();
  const datos = new FormData(evento.target);
  const parametros = new URLSearchParams();
  for (const [clave, valor] of datos) if (valor.trim()) parametros.set(clave, valor.trim());

  const caja = document.getElementById("resultados");
  const total = document.getElementById("total");
  if (![...parametros.keys()].length) {
    caja.innerHTML = `<p class="tenue">Rellena al menos un campo.</p>`;
    total.textContent = "";
    return;
  }
  caja.innerHTML = `<p class="tenue">Buscando…</p>`;
  try {
    const r = await pedir(`${API.busqueda}/entidades?${parametros}`);
    total.textContent = `· ${r.total.toLocaleString("es")}`;
    caja.innerHTML = r.entidades.length
      ? r.entidades.map(e => `<article class="entidad">${fichaEntidad(e)}</article>`).join("") +
        (r.total > r.entidades.length ? `<p class="tenue">Se muestran las ${r.entidades.length} primeras.</p>` : "")
      : `<p class="tenue">No hay entidades con esos criterios.</p>`;
  } catch (e) {
    total.textContent = "";
    caja.innerHTML = `<p class="aviso">${esc(e.message)}</p>`;
  }
}

function cancelar() {
  document.getElementById("total").textContent = "";
  document.getElementById("resultados").innerHTML = `<p class="tenue">Rellena algún campo y pulsa Buscar.</p>`;
}

// --------------------------------------------------------------------- 3) mapa
function iniciarMapa() {
  const mapa = L.map("mapa", { minZoom: 4 }).fitBounds(ESPANA);
  // Teselas: CARTO Voyager si hay clave en web/config.js; si no, OpenStreetMap (no necesita clave)
  const clave = window.CONFIG?.CARTO_KEY;
  const osm = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
  L.tileLayer(clave
    ? `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(clave)}`
    : "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, subdomains: "abcd",
    attribution: clave ? `${osm} &copy; <a href="https://carto.com/attributions">CARTO</a>` : osm,
  }).addTo(mapa);

  const grupos = L.markerClusterGroup({
    showCoverageOnHover: false, maxClusterRadius: 45, spiderfyOnMaxZoom: true,
    iconCreateFunction: g => {
      const n = g.getChildCount();
      const lado = n < 10 ? 30 : n < 100 ? 36 : 44;
      return L.divIcon({ html: `<div class="grupo" style="width:${lado}px;height:${lado}px">${n}</div>`,
                         className: "", iconSize: [lado, lado] });
    },
  }).addTo(mapa);

  // Marcadores pintados, por id de entidad. Al mover el mapa solo se añaden los nuevos y se quitan los que
  // ya no están: así no se cierra la ventana de un marcador abierto.
  const pintados = new Map();
  function crearMarcador(m) {
    const marcador = L.circleMarker([m.latitud, m.longitud], {
      radius: 7, weight: 2, color: "#fff", fillColor: COLOR[m.fuente] || "#1e6b57", fillOpacity: 1,
    });
    marcador.bindTooltip(m.nombre, { direction: "top", offset: [0, -6] });
    marcador.bindPopup(`<div class="popup"><p class="tenue">Cargando…</p></div>`, { maxWidth: 320 });
    marcador.on("popupopen", () => mostrarDetalle(marcador, m.id));
    return marcador;
  }

  let peticion = null, espera = null;
  async function actualizar() {
    const b = mapa.getBounds().pad(0.1);
    peticion?.abort();
    peticion = new AbortController();
    const url = `${API.busqueda}/entidades/mapa?lat_min=${b.getSouth()}&lat_max=${b.getNorth()}` +
                `&lon_min=${b.getWest()}&lon_max=${b.getEast()}`;
    try {
      const marcadores = await pedir(url, { signal: peticion.signal });
      const ids = new Set(marcadores.map(m => m.id));
      const fuera = [...pintados].filter(([id]) => !ids.has(id));
      grupos.removeLayers(fuera.map(([, marcador]) => marcador));
      fuera.forEach(([id]) => pintados.delete(id));
      const nuevos = marcadores.filter(m => !pintados.has(m.id));
      nuevos.forEach(m => pintados.set(m.id, crearMarcador(m)));
      grupos.addLayers(nuevos.map(m => pintados.get(m.id)));
      const visibles = marcadores.filter(m => mapa.getBounds().contains([m.latitud, m.longitud])).length;
      document.getElementById("en-zona").textContent = `${visibles.toLocaleString("es")} en esta zona`;
    } catch (e) {
      if (e.name !== "AbortError") document.getElementById("en-zona").textContent = "Sin conexión con la API de búsqueda";
    }
  }
  mapa.on("moveend", () => { clearTimeout(espera); espera = setTimeout(actualizar, 200); });
  actualizar();
}

async function mostrarDetalle(marcador, id) {
  try {
    const e = await pedir(`${API.busqueda}/entidades/${id}`);
    marcador.setPopupContent(`<div class="popup">${fichaEntidad(e)}</div>`);
  } catch (e) {
    marcador.setPopupContent(`<div class="popup"><p class="aviso">${esc(e.message)}</p></div>`);
  }
}

// ---------------------------------------------------------------------- inicio
(async () => {
  const formulario = document.getElementById("formulario");
  formulario.addEventListener("submit", buscar);
  formulario.addEventListener("reset", cancelar);
  await esperarAlmacen();
  rellenarDesplegables();
  iniciarMapa();
})();
