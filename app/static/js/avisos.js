// pide permiso para avisar al celular y guarda la suscripcion del navegador (pantalla N1)
(function () {
  const hoja = document.getElementById("hoja-avisos");
  const caja = document.getElementById("seguimiento");
  if (!hoja || !caja) return;

  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const soportado = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  const estado = document.getElementById("estado-avisos");
  const mostrar = (texto) => { if (estado) { estado.textContent = texto; estado.classList.remove("oculto"); } };

  if (!soportado) {
    // por ejemplo en http sin certificado o en iphone sin agregar a inicio
    mostrar(window.isSecureContext
      ? "Este navegador no permite avisos. Deja esta página abierta y aquí te avisamos."
      : "Los avisos al celular necesitan una conexión segura (https). Deja esta página abierta y aquí te avisamos.");
    return;
  }

  function aBytes(base64) {
    const relleno = "=".repeat((4 - (base64.length % 4)) % 4);
    const crudo = atob((base64 + relleno).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from([...crudo].map((c) => c.charCodeAt(0)));
  }

  async function suscribir() {
    const registro = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
    const { clave } = await (await fetch("/avisos/clave")).json();
    let sus = await registro.pushManager.getSubscription();
    if (!sus) {
      sus = await registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: aBytes(clave) });
    }
    const r = await fetch(caja.dataset.suscripcion, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify(sus),
    });
    if (!r.ok) throw new Error("no se guardo");
  }

  if (Notification.permission === "granted") {
    // ya habia dado permiso en otro pedido: se renueva la suscripcion sin preguntar
    suscribir().then(() => mostrar("Avisos activados: te llegará una notificación cuando esté listo."))
      .catch(() => mostrar("No se pudieron activar los avisos. Deja esta página abierta."));
    return;
  }
  if (Notification.permission === "denied") {
    mostrar("Bloqueaste los avisos de UBite. Deja esta página abierta y aquí te avisamos.");
    return;
  }
  if (sessionStorage.getItem("ubite-avisos") === "no") return;

  hoja.classList.remove("oculto");
  document.getElementById("avisos-no").addEventListener("click", () => {
    hoja.classList.add("oculto");
    try { sessionStorage.setItem("ubite-avisos", "no"); } catch (e) {}
    mostrar("Sin avisos al celular. Deja esta página abierta y aquí te avisamos.");
  });
  document.getElementById("avisos-si").addEventListener("click", async () => {
    hoja.classList.add("oculto");
    // el permiso tiene que pedirse justo despues de tocar el boton (asi lo exige iphone)
    const permiso = await Notification.requestPermission();
    if (permiso !== "granted") {
      mostrar("No diste permiso. Deja esta página abierta y aquí te avisamos.");
      return;
    }
    try {
      await suscribir();
      mostrar("Avisos activados: te llegará una notificación cuando esté listo.");
    } catch (e) {
      mostrar("No se pudieron activar los avisos. Deja esta página abierta.");
    }
  });
})();
