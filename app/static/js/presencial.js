(function () {
  const pesos = (v) => Math.round(v).toLocaleString("es-CO");
  const lineas = document.getElementById("lineas");
  const recibido = document.getElementById("recibido");
  let total = 0;

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
    document.getElementById("total-boton").textContent = pesos(total);
    vuelto();
  }

  function vuelto() {
    const r = Number(recibido.value.replace(/\D/g, "")) || 0;
    document.getElementById("cambio").textContent = r >= total ? pesos(r - total) : "falta " + pesos(total - r);
  }

  document.addEventListener("cantidades", resumen);
  recibido.addEventListener("input", vuelto);

  document.getElementById("presencial").addEventListener("submit", (e) => {
    const r = Number(recibido.value.replace(/\D/g, "")) || 0;
    if (total === 0) { e.preventDefault(); alert("Agrega al menos un producto."); }
    else if (r && r < total) { e.preventDefault(); alert("El efectivo recibido no alcanza para el total."); }
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
