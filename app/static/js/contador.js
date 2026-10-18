// botones + y - para los campos de cantidad (modificar pedido y pedido en caja)
(function () {
  const pasos = document.querySelectorAll(".stepper");
  const total = document.getElementById("total");

  function actualizar() {
    let suma = 0;
    pasos.forEach((p) => {
      const campo = p.querySelector("input");
      const n = Number(campo.value) || 0;
      suma += n * Number(p.dataset.precio);
      p.querySelector(".menos").disabled = n <= 0;
      p.querySelector(".mas").disabled = n >= Number(campo.max);
      p.closest(".fila-menu")?.classList.toggle("elegido", n > 0);
    });
    if (total) total.textContent = suma.toLocaleString("es-CO");
    document.dispatchEvent(new CustomEvent("cantidades"));
  }

  pasos.forEach((p) => {
    const campo = p.querySelector("input");
    const cambiar = (d) => {
      const n = Math.min(Number(campo.max), Math.max(0, (Number(campo.value) || 0) + d));
      campo.value = n;
      actualizar();
    };
    p.querySelector(".menos").addEventListener("click", () => cambiar(-1));
    p.querySelector(".mas").addEventListener("click", () => cambiar(1));
    campo.addEventListener("input", actualizar);
  });
  actualizar();
})();
