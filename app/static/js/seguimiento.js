// revisa el estado del pedido cada 8 s y recarga si cambio
(function () {
  const caja = document.getElementById("seguimiento");
  if (!caja) return;
  const { url, estado, posicion } = caja.dataset;
  if (estado === "entregado" || estado === "cancelado") return;

  setInterval(async () => {
    try {
      const r = await fetch(url, { cache: "no-store" });
      if (!r.ok) return;
      const d = await r.json();
      if (d.estado !== estado || String(d.posicion) !== posicion) location.reload();
    } catch (e) {}
  }, 8000);
})();
