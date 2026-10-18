// service worker: recibe el aviso del servidor y lo muestra aunque la pagina este cerrada
self.addEventListener("push", (evento) => {
  let datos = {};
  try { datos = evento.data.json(); } catch (e) { datos = { titulo: "UBite", cuerpo: evento.data ? evento.data.text() : "" }; }
  evento.waitUntil(
    self.registration.showNotification(datos.titulo || "UBite", {
      body: datos.cuerpo || "",
      icon: "/static/img/icono-192.png",
      badge: "/static/img/icono-192.png",
      tag: datos.codigo || "ubite",
      renotify: true,
      requireInteraction: true,
      data: { url: datos.url || "/" },
    })
  );
});

// al tocar el aviso se abre (o se enfoca) la pagina del pedido
self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  const url = evento.notification.data.url;
  evento.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((ventanas) => {
      for (const v of ventanas) {
        if (v.url.startsWith(url) && "focus" in v) return v.focus();
      }
      return clients.openWindow(url);
    })
  );
});
