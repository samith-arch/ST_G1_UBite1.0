// Menú del cliente: suma o resta productos sin recargar la página.
// Si el JavaScript no carga, los formularios funcionan igual recargando.
(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const aviso = document.getElementById("aviso");
  const pesos = (v) => Math.round(v).toLocaleString("es-CO");

  document.querySelectorAll("form.contador").forEach((form) => {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const datos = new FormData(form);
      datos.set("delta", ev.submitter ? ev.submitter.value : "1");
      try {
        const r = await fetch(form.action, {
          method: "POST", body: datos,
          headers: { "X-Requested-With": "fetch", "X-CSRF-Token": csrf },
        });
        if (!r.ok) throw new Error();
        const d = await r.json();
        const cant = form.querySelector(".cant");
        const menos = form.querySelector(".menos");
        const mas = form.querySelector(".mas");
        cant.textContent = d.cantidad;
        cant.classList.toggle("oculto", d.cantidad === 0);
        menos.classList.toggle("oculto", d.cantidad === 0);
        mas.disabled = d.cantidad >= Number(mas.dataset.stock);
        document.getElementById("unidades").textContent = d.unidades;
        document.getElementById("total").textContent = pesos(d.total);
        document.getElementById("barra-pedido").classList.toggle("oculta", d.unidades === 0);
        aviso.textContent = d.aviso || "";
        aviso.classList.toggle("oculto", !d.aviso);
      } catch (e) {
        form.submit();
      }
    });
  });

  // Búsqueda y filtro por categoría
  const buscar = document.getElementById("buscar");
  let filtro = "";
  function aplicar() {
    const texto = buscar.value.trim().toLowerCase();
    document.querySelectorAll("section.categoria").forEach((sec) => {
      let visibles = 0;
      sec.querySelectorAll(".fila-menu").forEach((fila) => {
        const ok = (!filtro || sec.dataset.categoria === filtro) && fila.dataset.nombre.includes(texto);
        fila.classList.toggle("oculto", !ok);
        if (ok) visibles++;
      });
      sec.classList.toggle("oculto", visibles === 0);
    });
  }
  buscar.addEventListener("input", aplicar);
  document.querySelectorAll(".filtros a").forEach((a) => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      document.querySelectorAll(".filtros a").forEach((x) => x.classList.remove("activo"));
      a.classList.add("activo");
      filtro = a.dataset.filtro;
      aplicar();
    });
  });
})();
