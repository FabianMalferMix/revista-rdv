// La cabecera al bajar (opción C, elegida por el dueño el 2026-10-15). Arriba, la cabecera
// de siempre (en la portada, nada: la hoja de estilos la esconde); al pasar lo que mide, una
// cápsula pequeña y centrada. Este archivo solo pone y quita data-barra="pildora" en <html>:
// el aspecto está en site.css («La cabecera al bajar»). Sin JavaScript queda la cabecera fija.
(function () {
  "use strict";

  var raiz = document.documentElement;
  var portada = !!document.querySelector(".hero-nombre");
  var quieto = window.matchMedia("(prefers-reduced-motion: reduce)");
  var arriba = true;
  var primera = true;

  function poner(capsula) {
    if ((raiz.getAttribute("data-barra") === "pildora") === capsula) return;
    var aplicar = function () {
      if (capsula) raiz.setAttribute("data-barra", "pildora");
      else raiz.removeAttribute("data-barra");
    };
    // Fuera de la portada cambia la forma (de la cabecera a la cápsula): lo anima una
    // transición de vista. En la portada, la cápsula aparece con la hoja de estilos. La
    // primera decisión (una página que abre ya bajada) va sin animación.
    var animar = !portada && !primera && !quieto.matches && !document.hidden;
    if (animar && document.startViewTransition) document.startViewTransition(aplicar);
    else aplicar();
  }

  function decidir() {
    // Con la lupa o «Menú» abiertos, la cabecera no cambia de forma.
    if (document.querySelector(".masthead details[open]")) return;
    poner(!arriba);
  }

  if (!("IntersectionObserver" in window)) return;
  var centinela = document.createElement("div");
  centinela.className = "barra-centinela";
  centinela.setAttribute("aria-hidden", "true");
  document.body.insertBefore(centinela, document.body.firstChild);
  new IntersectionObserver(function (entradas) {
    arriba = entradas[0].isIntersecting;
    decidir();
    primera = false;
  }).observe(centinela);
  // Al cerrar un panel, la cabecera se pone al día.
  document.addEventListener("toggle", decidir, true);
})();
