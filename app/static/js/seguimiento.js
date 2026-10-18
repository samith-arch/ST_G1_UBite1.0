// Seguimiento del pedido: consulta el estado cada 8 segundos y recarga la
// página cuando cambia. Es el respaldo de la notificación al celular.
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
    } catch (e) { /* sin conexión: se intenta en la siguiente vuelta */ }
  }, 8000);
})();
