(function () {
  const pesos = (v) => Math.round(v).toLocaleString("es-CO");
  const lineas = document.getElementById("lineas");
  const recibido = document.getElementById("recibido");
  const formulario = document.getElementById("presencial");
  const barra = document.getElementById("barra-cobro");
  const error = document.getElementById("error-cobro");
  let total = 0;

  function avisar(texto) {
    error.textContent = texto;
    error.classList.toggle("oculto", !texto);
  }

  function resumen() {
    const filas = [];
    total = 0;
    document.querySelectorAll(".stepper").forEach((p) => {
      const n = Number(p.querySelector("input").value) || 0;
      if (n > 0) {
        const sub = n * Number(p.dataset.precio);
        total += sub;
        filas.push(`<div class="fila"><span>${p.dataset.nombre} ×${n}</span><span class="mono">${pesos(sub)}</span></div>`);
      }
    });
    lineas.innerHTML = filas.join("") || '<p class="small suave mb-0">Todavía no hay productos.</p>';
    for (const id of ["total", "total-boton", "total-barra"]) document.getElementById(id).textContent = pesos(total);
    barra.classList.toggle("oculto", total === 0 || resumenVisible);
    formulario.classList.toggle("con-productos", total > 0);
    if (total > 0) avisar("");
    vuelto();
  }

  function vuelto() {
    const r = Number(recibido.value.replace(/\D/g, "")) || 0;
    document.getElementById("cambio").textContent = !r ? "—" : r >= total ? pesos(r - total) : "falta " + pesos(total - r);
  }

  document.addEventListener("cantidades", resumen);
  recibido.addEventListener("input", vuelto);

  // en el celular la barra de cobro se esconde cuando el resumen ya se ve en pantalla
  let resumenVisible = false;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(([e]) => {
      resumenVisible = e.isIntersecting;
      barra.classList.toggle("oculto", total === 0 || resumenVisible);
    }).observe(document.getElementById("resumen"));
  }

  barra.querySelector("button").addEventListener("click", () => {
    document.getElementById("resumen").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  formulario.addEventListener("submit", (e) => {
    const r = Number(recibido.value.replace(/\D/g, "")) || 0;
    let texto = "";
    if (total === 0) texto = "Agrega al menos un producto antes de cobrar.";
    else if (r && r < total) texto = "El efectivo recibido no alcanza: faltan $ " + pesos(total - r) + ".";
    if (texto) {
      e.preventDefault();
      avisar(texto);
      error.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  // busqueda y filtro por categoria
  const buscar = document.getElementById("buscar");
  const categoria = document.getElementById("categoria");
  function filtrar() {
    const texto = buscar.value.trim().toLowerCase();
    document.querySelectorAll("section.categoria").forEach((sec) => {
      let hay = 0;
      sec.querySelectorAll(".fila-menu").forEach((f) => {
        const ok = (!categoria.value || sec.dataset.categoria === categoria.value) && f.dataset.nombre.includes(texto);
        f.classList.toggle("oculto", !ok);
        if (ok) hay++;
      });
      sec.classList.toggle("oculto", hay === 0);
    });
  }
  buscar.addEventListener("input", filtrar);
  categoria.addEventListener("change", filtrar);
  resumen();
})();
