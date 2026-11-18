// animaciones de la portada: aparecer al bajar, parallax del collage, barra fija y contadores
(function () {
  document.body.classList.add("js-listo");
  const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const nav = document.getElementById("nav-portada");

  const visibles = document.querySelectorAll(".revelar");
  if ("IntersectionObserver" in window && !quieto) {
    const obs = new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("visible"); obs.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    visibles.forEach((el, i) => { el.style.transitionDelay = (i % 4) * 90 + "ms"; obs.observe(el); });
  } else {
    visibles.forEach((el) => el.classList.add("visible"));
  }

  const piezas = document.querySelectorAll("[data-parallax]");
  let pendiente = false;
  function mover() {
    const y = window.scrollY;
    nav.classList.toggle("solida", y > 40);
    if (!quieto) piezas.forEach((p) => { p.style.translate = `0 ${y * Number(p.dataset.parallax)}px`; });
    pendiente = false;
  }
  window.addEventListener("scroll", () => { if (!pendiente) { pendiente = true; requestAnimationFrame(mover); } }, { passive: true });
  mover();

  // los numeros cuentan desde cero la primera vez que se ven
  const numeros = document.querySelectorAll("[data-contar]");
  if (!quieto && "IntersectionObserver" in window) {
    const obs = new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        if (!e.isIntersecting) return;
        const el = e.target, fin = Number(el.dataset.contar), inicio = performance.now();
        const paso = (t) => {
          const k = Math.min(1, (t - inicio) / 1200);
          el.textContent = Math.round(fin * (1 - Math.pow(1 - k, 3))).toLocaleString("es-CO");
          if (k < 1) requestAnimationFrame(paso);
        };
        requestAnimationFrame(paso);
        obs.unobserve(el);
      });
    });
    numeros.forEach((n) => obs.observe(n));
  }

  // si el formulario volvio con errores, se baja hasta el
  const error = document.querySelector("#pedir .error-campo");
  if (error) document.getElementById("pedir").scrollIntoView();
})();
