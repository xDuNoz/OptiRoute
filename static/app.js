// OptiRoute: interfaz del modelo de Transporte.
const estado = {
  origenes: ["Origen 1", "Origen 2"],
  destinos: ["Destino 1", "Destino 2"],
  oferta: [0, 0],
  demanda: [0, 0],
  costos: [[0, 0], [0, 0]],
  coordenadas: {},
  resultado: null,
  iter: 0,
  base: null,          // { datos, resultado } del escenario base
};
let mapa = null;
let capaRutas = null;

const $ = (id) => document.getElementById(id);
const fmt = (v, dec = 2) =>
  v === null || v === undefined ? "" :
  Number(v).toLocaleString("es-MX", { maximumFractionDigits: dec });
const dinero = (v) => "$" + Number(v).toLocaleString("es-MX", { minimumFractionDigits: 0, maximumFractionDigits: 2 });

// ---------------------------------------------------------------------------
// Tabla de captura
// ---------------------------------------------------------------------------
function entrada(valor, alCambiar, clase = "") {
  const inp = document.createElement("input");
  inp.value = valor;
  if (clase) inp.className = clase;
  inp.addEventListener("input", () => { alCambiar(inp.value); actualizarBalance(); });
  return inp;
}

function dibujarDatos() {
  const t = $("tabla-datos");
  t.innerHTML = "";
  const enc = t.insertRow();
  enc.appendChild(Object.assign(document.createElement("th"), { textContent: "Origen \\ Destino" }));
  estado.destinos.forEach((d, j) => {
    const th = document.createElement("th");
    th.appendChild(entrada(d, (v) => (estado.destinos[j] = v), "nombre"));
    enc.appendChild(th);
  });
  enc.appendChild(Object.assign(document.createElement("th"), { textContent: "Oferta", className: "total" }));

  estado.origenes.forEach((o, i) => {
    const fila = t.insertRow();
    const th = document.createElement("th");
    th.appendChild(entrada(o, (v) => (estado.origenes[i] = v), "nombre"));
    fila.appendChild(th);
    estado.destinos.forEach((_, j) => {
      fila.insertCell().appendChild(entrada(estado.costos[i][j], (v) => (estado.costos[i][j] = v)));
    });
    const c = fila.insertCell();
    c.className = "total";
    c.appendChild(entrada(estado.oferta[i], (v) => (estado.oferta[i] = v)));
  });

  const filaD = t.insertRow();
  filaD.appendChild(Object.assign(document.createElement("th"), { textContent: "Demanda", className: "total" }));
  estado.destinos.forEach((_, j) => {
    const c = filaD.insertCell();
    c.className = "total";
    c.appendChild(entrada(estado.demanda[j], (v) => (estado.demanda[j] = v)));
  });
  filaD.insertCell().className = "total";
  actualizarBalance();
}

function actualizarBalance() {
  const of = estado.oferta.reduce((a, b) => a + Number(b || 0), 0);
  const de = estado.demanda.reduce((a, b) => a + Number(b || 0), 0);
  const aviso = $("aviso-balance");
  if (Math.abs(of - de) < 1e-9) {
    aviso.className = "aviso ok";
    aviso.textContent = `Problema balanceado: oferta total = demanda total = ${fmt(of)}.`;
  } else if (of > de) {
    aviso.className = "aviso info";
    aviso.textContent = `Oferta (${fmt(of)}) > demanda (${fmt(de)}): se agregará un destino ficticio con demanda ${fmt(of - de)} y costo 0.`;
  } else {
    aviso.className = "aviso info";
    aviso.textContent = `Demanda (${fmt(de)}) > oferta (${fmt(of)}): se agregará un origen ficticio con oferta ${fmt(de - of)} y costo 0.`;
  }
}

function agregarOrigen() {
  estado.origenes.push(`Origen ${estado.origenes.length + 1}`);
  estado.oferta.push(0);
  estado.costos.push(estado.destinos.map(() => 0));
  dibujarDatos();
}
function quitarOrigen() {
  if (estado.origenes.length <= 1) return;
  estado.origenes.pop(); estado.oferta.pop(); estado.costos.pop();
  dibujarDatos();
}
function agregarDestino() {
  estado.destinos.push(`Destino ${estado.destinos.length + 1}`);
  estado.demanda.push(0);
  estado.costos.forEach((f) => f.push(0));
  dibujarDatos();
}
function quitarDestino() {
  if (estado.destinos.length <= 1) return;
  estado.destinos.pop(); estado.demanda.pop(); estado.costos.forEach((f) => f.pop());
  dibujarDatos();
}

async function cargarEjemplo() {
  const d = await (await fetch("/api/ejemplo")).json();
  Object.assign(estado, {
    origenes: d.origenes, destinos: d.destinos, oferta: d.oferta,
    demanda: d.demanda, costos: d.costos, coordenadas: d.coordenadas || {},
  });
  dibujarDatos();
}

// ---------------------------------------------------------------------------
// Resolver
// ---------------------------------------------------------------------------
async function resolverProblema() {
  $("error").textContent = "";
  const cuerpo = {
    origenes: estado.origenes, destinos: estado.destinos,
    oferta: estado.oferta.map(Number), demanda: estado.demanda.map(Number),
    costos: estado.costos.map((f) => f.map(Number)), metodo: $("metodo").value,
  };
  if ([...cuerpo.oferta, ...cuerpo.demanda, ...cuerpo.costos.flat()].some((v) => Number.isNaN(v))) {
    $("error").textContent = "Revisa los datos: todos los valores deben ser numéricos.";
    return;
  }
  const resp = await fetch("/api/resolver", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
  });
  const r = await resp.json();
  if (!resp.ok) { $("error").textContent = r.error; return; }
  estado.resultado = r;
  estado.iter = 0;
  mostrarResultados();
}

function mostrarResultados() {
  const r = estado.resultado;
  $("resultados").hidden = false;
  const ini = r.iniciales[r.metodo_inicial];
  const ahorro = ini.costo - r.optimo.costo;
  $("resumen").innerHTML = `
    <div class="tarjeta"><div class="etq">Costo óptimo</div><div class="valor">${dinero(r.optimo.costo)}</div>
      <div class="det">Z* por periodo</div></div>
    <div class="tarjeta"><div class="etq">Solución inicial (${ini.metodo})</div><div class="valor">${dinero(ini.costo)}</div>
      <div class="det">${ahorro > 0 ? "MODI mejoró " + dinero(ahorro) : "Ya era óptima"}</div></div>
    <div class="tarjeta"><div class="etq">Iteraciones MODI</div><div class="valor">${r.iteraciones.length - 1}</div>
      <div class="det">hasta costos reducidos ≥ 0</div></div>
    <div class="tarjeta"><div class="etq">Validación</div><div class="valor">${r.coincide ? "Coincide" : "Difiere"}</div>
      <div class="det">${r.solver.nombre}</div></div>`;
  mostrarComparacion();
  mostrarIteracion();
  mostrarOptimo();
  mostrarSensibilidad();
  mostrarEscenario();
  mostrarMapa();
  $("resultados").scrollIntoView({ behavior: "smooth" });
}

function mostrarComparacion() {
  const r = estado.resultado;
  const opt = r.optimo.costo;
  const filas = ["noroeste", "costo_minimo", "vogel"].map((k) => {
    const s = r.iniciales[k];
    const dif = opt ? ((s.costo - opt) / opt) * 100 : 0;
    return `<tr class="${k === r.metodo_inicial ? "sel" : ""}"><td>${s.metodo}</td>
      <td>${dinero(s.costo)}</td><td>${dif < 1e-9 ? "Óptima" : "+" + fmt(dif, 1) + "%"}</td></tr>`;
  });
  $("comparacion").innerHTML = `<table class="comp"><tr><th>Método</th><th>Costo</th><th>Contra el óptimo</th></tr>
    ${filas.join("")}<tr><td><b>Óptimo (MODI)</b></td><td><b>${dinero(opt)}</b></td><td>—</td></tr></table>`;
  $("pasos-inicial").innerHTML = r.iniciales[r.metodo_inicial].pasos.map((p) => `<li>${p}</li>`).join("");
}

function matrizHTML(it, conMultiplicadores) {
  const p = estado.resultado.problema;
  const basicas = new Set(it.basicas.map((c) => c.join(",")));
  const signos = {};
  (it.ciclo || []).forEach((c, k) => (signos[c.join(",")] = k % 2 === 0 ? "+" : "−"));
  const entra = it.entra ? it.entra.join(",") : null;
  const sale = it.sale ? it.sale.join(",") : null;

  let h = "<table class='matriz'><tr><th></th>";
  p.destinos.forEach((d) => (h += `<th class="${d === "Ficticio" ? "ficticio" : ""}">${d}</th>`));
  h += "<th class='total'>Oferta</th>" + (conMultiplicadores ? "<th class='mult'>u<sub>i</sub></th>" : "") + "</tr>";
  p.origenes.forEach((o, i) => {
    h += `<tr class="${o === "Ficticio" ? "ficticio" : ""}"><th>${o}</th>`;
    p.destinos.forEach((_, j) => {
      const k = `${i},${j}`;
      let clase = basicas.has(k) ? "basica" : "";
      if (k === entra) clase = "entra";
      if (k === sale) clase = "sale";
      let contenido;
      if (basicas.has(k)) contenido = `<span class="cant">${fmt(it.asignacion[i][j])}</span>`;
      else if (conMultiplicadores && it.reducidos) {
        const rd = it.reducidos[i][j];
        contenido = `<span class="red ${rd < -1e-9 ? "neg" : ""}">${fmt(rd)}</span>`;
      } else contenido = "";
      const signo = signos[k] ? `<span class="signo">${signos[k]}</span>` : "";
      h += `<td class="${clase}"><span class="costo">${fmt(p.costos[i][j])}</span>${contenido}${signo}</td>`;
    });
    h += `<td class="total">${fmt(p.oferta[i])}</td>`;
    if (conMultiplicadores) h += `<td class="mult">${fmt(it.u[i])}</td>`;
    h += "</tr>";
  });
  h += "<tr><th class='total'>Demanda</th>";
  p.destinos.forEach((_, j) => (h += `<td class="total">${fmt(p.demanda[j])}</td>`));
  h += "<td class='total'></td>" + (conMultiplicadores ? "<td></td>" : "") + "</tr>";
  if (conMultiplicadores) {
    h += "<tr><th class='mult'>v<sub>j</sub></th>";
    p.destinos.forEach((_, j) => (h += `<td class="mult">${fmt(it.v[j])}</td>`));
    h += "<td></td><td></td></tr>";
  }
  return h + "</table>";
}

function mostrarIteracion() {
  const r = estado.resultado;
  const p = r.problema;
  const it = r.iteraciones[estado.iter];
  const total = r.iteraciones.length;
  $("etiqueta-iter").textContent = `Iteración ${it.numero} de ${total} · Costo ${dinero(it.costo)}`;
  $("btn-ant").disabled = estado.iter === 0;
  $("btn-sig").disabled = estado.iter === total - 1;
  const nombre = (c) => `(${p.origenes[c[0]]}, ${p.destinos[c[1]]})`;
  let nota;
  if (it.entra) {
    const rd = it.reducidos[it.entra[0]][it.entra[1]];
    nota = `El costo reducido más negativo es <b>${fmt(rd)}</b> en ${nombre(it.entra)}: esa celda <b>entra</b> a la base.
      El ciclo es ${it.ciclo.map(nombre).join(" → ")}. La menor cantidad en las celdas con signo − es
      θ = <b>${fmt(it.theta)}</b>, así que <b>sale</b> ${nombre(it.sale)}. El costo baja en
      ${fmt(-rd)} × ${fmt(it.theta)} = <b>${dinero(-rd * it.theta)}</b>.`;
  } else {
    nota = `Todos los costos reducidos son ≥ 0: <b>la solución es óptima</b>.
      ${it.reducidos.flat().some((v) => v !== null && Math.abs(v) < 1e-9)
        ? "Hay costos reducidos iguales a 0, lo que indica óptimos alternos."
        : "Ningún costo reducido es 0, así que el óptimo es único."}`;
  }
  $("iteracion").innerHTML = `<div class="tabla-scroll">${matrizHTML(it, true)}</div><p class="nota-iter">${nota}</p>`;
}

function mostrarOptimo() {
  const r = estado.resultado;
  const p = r.problema;
  const final = r.iteraciones[r.iteraciones.length - 1];
  const envios = [];
  p.origenes.forEach((o, i) => p.destinos.forEach((d, j) => {
    const q = r.optimo.asignacion[i][j];
    if (q > 1e-9 && o !== "Ficticio" && d !== "Ficticio")
      envios.push(`<tr><td>${o}</td><td>${d}</td><td>${fmt(q)}</td><td>${dinero(p.costos[i][j])}</td><td>${dinero(q * p.costos[i][j])}</td></tr>`);
  }));
  const ociosa = [];
  p.origenes.forEach((o, i) => p.destinos.forEach((d, j) => {
    const q = r.optimo.asignacion[i][j];
    if (q > 1e-9 && d === "Ficticio") ociosa.push(`${o}: ${fmt(q)} unidades sin enviar`);
    if (q > 1e-9 && o === "Ficticio") ociosa.push(`${d}: ${fmt(q)} unidades de demanda no atendida`);
  }));
  $("optimo").innerHTML = `
    <div class="tabla-scroll">${matrizHTML({ ...final, ciclo: null, entra: null, sale: null }, false)}</div>
    <h3>Plan de envíos</h3>
    <table class="comp"><tr><th>Origen</th><th>Destino</th><th>Cantidad</th><th>Costo unitario</th><th>Subtotal</th></tr>
      ${envios.join("")}<tr><td colspan="4"><b>Costo total</b></td><td><b>${dinero(r.optimo.costo)}</b></td></tr></table>
    ${ociosa.length ? `<p class="ayuda">${ociosa.join(" · ")}</p>` : ""}`;
  $("validacion").innerHTML = `<div class="valido ${r.coincide ? "si" : "no"}">
    Validación con ${r.solver.nombre}: estado <b>${r.solver.estado}</b>, costo ${dinero(r.solver.costo)}.
    ${r.coincide ? "El resultado de MODI coincide con el solver de Programación Lineal." : "Los resultados no coinciden; revisa los datos."}</div>`;
}

// ---------------------------------------------------------------------------
// Sensibilidad
// ---------------------------------------------------------------------------
const rangoTxt = (r) => !r ? "—" :
  `${r[0] === null ? "−∞" : fmt(r[0])} a ${r[1] === null ? "∞" : fmt(r[1])}`;

function mostrarSensibilidad() {
  const s = estado.resultado.sensibilidad;
  $("interpretacion").innerHTML = "<ul>" + s.interpretacion.map((t) => `<li>${t}</li>`).join("") + "</ul>";
  $("sens-oferta").innerHTML = `<table class="comp"><tr><th>Origen</th><th>Capacidad</th><th>Usado</th>
    <th>Holgura</th><th>Precio sombra</th><th>Rango de validez</th></tr>
    ${s.oferta.map((o) => `<tr><td>${o.nombre}</td><td>${fmt(o.valor)}</td><td>${fmt(o.usado)}</td>
      <td>${fmt(o.holgura)}</td><td>${fmt(o.precio_sombra)}</td><td>${rangoTxt(o.rango)}</td></tr>`).join("")}</table>`;
  $("sens-demanda").innerHTML = `<table class="comp"><tr><th>Destino</th><th>Demanda</th>
    <th>Precio sombra</th><th>Rango de validez</th></tr>
    ${s.demanda.map((d) => `<tr><td>${d.nombre}</td><td>${fmt(d.valor)}</td>
      <td>${fmt(d.precio_sombra)}</td><td>${rangoTxt(d.rango)}</td></tr>`).join("")}</table>`;
  const filas = [...s.rutas].sort((a, b) => (b.basica - a.basica) || (a.costo_reducido - b.costo_reducido));
  $("sens-rutas").innerHTML = `<table class="comp"><tr><th>Ruta</th><th>En el plan</th><th>Cantidad</th>
    <th>Costo actual</th><th>Costo reducido</th><th>Costo mínimo</th><th>Costo máximo</th></tr>
    ${filas.map((r) => `<tr><td>${r.origen} → ${r.destino}</td><td>${r.basica ? "Sí" : "No"}</td>
      <td>${fmt(r.cantidad)}</td><td>${dinero(r.costo)}</td><td>${fmt(r.costo_reducido)}</td>
      <td>${r.minimo === null ? "Sin límite" : dinero(r.minimo)}</td>
      <td>${r.maximo === null ? "Sin límite" : dinero(r.maximo)}</td></tr>`).join("")}</table>
    <p class="ayuda">Precio sombra de oferta negativo = ahorro por cada unidad adicional de capacidad.
    Precio sombra de demanda = costo de atender una unidad adicional. Dentro de los rangos de costo, el plan de
    envíos no cambia (solo cambia el costo total).</p>`;
}

// ---------------------------------------------------------------------------
// Escenarios
// ---------------------------------------------------------------------------
function copiaDatos() {
  return JSON.parse(JSON.stringify({
    origenes: estado.origenes, destinos: estado.destinos, oferta: estado.oferta,
    demanda: estado.demanda, costos: estado.costos,
  }));
}

function fijarBase() {
  if (!estado.resultado) return;
  estado.base = { datos: copiaDatos(), resultado: estado.resultado };
  $("btn-restaurar").disabled = false;
  mostrarEscenario();
}

function restaurarBase() {
  if (!estado.base) return;
  Object.assign(estado, JSON.parse(JSON.stringify(estado.base.datos)));
  dibujarDatos();
  resolverProblema();
}

function envios(r) {
  const m = {};
  r.problema.origenes.forEach((o, i) => r.problema.destinos.forEach((d, j) => {
    if (o !== "Ficticio" && d !== "Ficticio") m[`${o} → ${d}`] = r.optimo.asignacion[i][j];
  }));
  return m;
}

function mostrarEscenario() {
  const caja = $("comparacion-escenario");
  if (!estado.base) {
    $("estado-base").textContent = "No hay escenario base guardado.";
    caja.innerHTML = "";
    return;
  }
  const b = estado.base.resultado, a = estado.resultado;
  $("estado-base").textContent = `Base guardada: costo ${dinero(b.optimo.costo)}.`;
  if (a === b) { caja.innerHTML = "<p class='ayuda'>Cambia algún dato y vuelve a resolver para comparar.</p>"; return; }
  const dif = a.optimo.costo - b.optimo.costo;
  const eb = envios(b), ea = envios(a);
  const rutas = [...new Set([...Object.keys(eb), ...Object.keys(ea)])]
    .filter((k) => Math.abs((eb[k] || 0) - (ea[k] || 0)) > 1e-9 || (eb[k] || 0) > 1e-9 || (ea[k] || 0) > 1e-9);
  const cambios = [];
  b.problema.destinos.forEach((d, j) => {
    const k = a.problema.destinos.indexOf(d);
    if (k >= 0 && b.problema.demanda[j] !== a.problema.demanda[k] && d !== "Ficticio")
      cambios.push(`demanda de ${d}: ${fmt(b.problema.demanda[j])} → ${fmt(a.problema.demanda[k])}`);
  });
  b.problema.origenes.forEach((o, i) => {
    const k = a.problema.origenes.indexOf(o);
    if (k >= 0 && b.problema.oferta[i] !== a.problema.oferta[k] && o !== "Ficticio")
      cambios.push(`capacidad de ${o}: ${fmt(b.problema.oferta[i])} → ${fmt(a.problema.oferta[k])}`);
    b.problema.destinos.forEach((d, j) => {
      const l = a.problema.destinos.indexOf(d);
      if (k >= 0 && l >= 0 && o !== "Ficticio" && d !== "Ficticio" && b.problema.costos[i][j] !== a.problema.costos[k][l])
        cambios.push(`costo ${o} → ${d}: ${dinero(b.problema.costos[i][j])} → ${dinero(a.problema.costos[k][l])}`);
    });
  });
  caja.innerHTML = `
    <div class="resumen" style="margin-top:14px">
      <div class="tarjeta"><div class="etq">Costo base</div><div class="valor">${dinero(b.optimo.costo)}</div></div>
      <div class="tarjeta"><div class="etq">Costo del escenario</div><div class="valor">${dinero(a.optimo.costo)}</div></div>
      <div class="tarjeta"><div class="etq">Diferencia</div><div class="valor">${dif >= 0 ? "+" : "−"}${dinero(Math.abs(dif))}</div>
        <div class="det">${b.optimo.costo ? fmt((dif / b.optimo.costo) * 100, 1) + "% contra la base" : ""}</div></div>
    </div>
    ${cambios.length ? `<p><b>Cambios en los datos:</b> ${cambios.join("; ")}.</p>` : ""}
    <table class="comp"><tr><th>Ruta</th><th>Base</th><th>Escenario</th><th>Cambio</th></tr>
    ${rutas.map((k) => {
      const d = (ea[k] || 0) - (eb[k] || 0);
      return `<tr class="${Math.abs(d) > 1e-9 ? "cambio" : ""}"><td>${k}</td><td>${fmt(eb[k] || 0)}</td><td>${fmt(ea[k] || 0)}</td>
        <td class="${d > 1e-9 ? "pos" : d < -1e-9 ? "neg" : ""}">${Math.abs(d) > 1e-9 ? (d > 0 ? "+" : "−") + fmt(Math.abs(d)) : "—"}</td></tr>`;
    }).join("")}</table>`;
}

// ---------------------------------------------------------------------------
// Mapa
// ---------------------------------------------------------------------------
function mostrarMapa() {
  const r = estado.resultado, p = r.problema, c = estado.coordenadas || {};
  const aviso = $("mapa-aviso");
  const nombres = [...p.origenes, ...p.destinos].filter((n) => n !== "Ficticio");
  const conCoord = nombres.filter((n) => c[n]);
  if (typeof L === "undefined") {
    $("mapa").classList.add("oculto");
    aviso.textContent = "El mapa necesita conexión a internet para cargar la biblioteca Leaflet.";
    return;
  }
  if (conCoord.length < 2) {
    $("mapa").classList.add("oculto");
    aviso.textContent = "Los orígenes y destinos actuales no tienen coordenadas registradas.";
    return;
  }
  $("mapa").classList.remove("oculto");
  aviso.textContent = conCoord.length < nombres.length ? "Algunos puntos no tienen coordenadas y no se muestran." : "";
  if (!mapa) {
    mapa = L.map("mapa");
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap", maxZoom: 18,
    }).addTo(mapa);
  }
  if (capaRutas) capaRutas.remove();
  capaRutas = L.layerGroup().addTo(mapa);
  const max = Math.max(...r.optimo.asignacion.flat());
  p.origenes.forEach((o, i) => p.destinos.forEach((d, j) => {
    const q = r.optimo.asignacion[i][j];
    if (q > 1e-9 && c[o] && c[d]) {
      L.polyline([c[o], c[d]], { color: "#0f5f8c", weight: 2 + 10 * (q / max), opacity: 0.75 })
        .bindTooltip(`${o} → ${d}: ${fmt(q)} unidades · ${dinero(q * p.costos[i][j])}`).addTo(capaRutas);
    }
  }));
  p.origenes.forEach((o, i) => {
    if (!c[o]) return;
    L.circleMarker(c[o], { radius: 10, color: "#0f5f8c", fillColor: "#0f5f8c", fillOpacity: 0.9 })
      .bindTooltip(`<b>${o}</b> (almacén)<br>Capacidad ${fmt(p.oferta[i])}`, { permanent: true, direction: "top" })
      .addTo(capaRutas);
  });
  p.destinos.forEach((d, j) => {
    if (!c[d]) return;
    L.circleMarker(c[d], { radius: 8, color: "#c9772c", fillColor: "#f0a04b", fillOpacity: 0.95 })
      .bindTooltip(`<b>${d}</b><br>Demanda ${fmt(p.demanda[j])}`, { permanent: true, direction: "bottom" })
      .addTo(capaRutas);
  });
  mapa.fitBounds(conCoord.map((n) => c[n]), { padding: [40, 40] });
  setTimeout(() => mapa.invalidateSize(), 100);
}

// ---------------------------------------------------------------------------
$("btn-fijar").onclick = fijarBase;
$("btn-restaurar").onclick = restaurarBase;
$("btn-ejemplo").onclick = cargarEjemplo;
$("btn-mas-origen").onclick = agregarOrigen;
$("btn-menos-origen").onclick = quitarOrigen;
$("btn-mas-destino").onclick = agregarDestino;
$("btn-menos-destino").onclick = quitarDestino;
$("btn-resolver").onclick = resolverProblema;
$("btn-ant").onclick = () => { estado.iter--; mostrarIteracion(); };
$("btn-sig").onclick = () => { estado.iter++; mostrarIteracion(); };
cargarEjemplo();
