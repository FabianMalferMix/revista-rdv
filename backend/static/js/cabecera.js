// La cabecera al bajar. Arriba, la cabecera de siempre (en la portada, nada: la hoja de estilos
// la esconde); al pasar lo que mide, una cápsula pequeña y centrada. Este archivo solo pone la
// marca data-barra en <html>, «arriba» o «pildora»: el aspecto está en estados.css («La cabecera
// al bajar»), que sin la marca deja la cabecera fija. Se carga en el <head>, sin defer, para que
// la marca esté antes de la primera pintura y la portada no enseñe la cabecera un instante. Si
// algo falla al montarse, o falta common.js, la marca se quita y queda la cabecera fija, como sin
// JavaScript.
(() => {
  "use strict";

  const raiz = document.documentElement;
  raiz.setAttribute("data-barra", "arriba");

  function montar(common) {
    const { quieto } = common;
    // La portada la marca su <body>, como para la hoja de estilos.
    const portada = document.body.dataset.pagina === "portada";
    let arriba = true;
    let primera = true;

    function poner(capsula) {
      const marca = capsula ? "pildora" : "arriba";
      if (raiz.getAttribute("data-barra") === marca) return;
      const aplicar = () => {
        raiz.setAttribute("data-barra", marca);
      };
      // Fuera de la portada cambia la forma (de la cabecera a la cápsula): lo anima una
      // transición de vista. En la portada, la cápsula aparece con la hoja de estilos. La
      // primera decisión (una página que abre ya bajada) va sin animación.
      const animar = !portada && !primera && !quieto.matches && !document.hidden;
      if (animar && document.startViewTransition) document.startViewTransition(aplicar);
      else aplicar();
    }

    function decidir() {
      // Con la lupa o «Menú» abiertos, la cabecera no cambia de forma.
      if (document.querySelector(".masthead details[open]")) return;
      poner(!arriba);
    }

    const centinela = document.createElement("div");
    centinela.className = "barra-centinela";
    centinela.setAttribute("aria-hidden", "true");
    document.body.insertBefore(centinela, document.body.firstChild);
    new IntersectionObserver((entradas) => {
      arriba = entradas[0].isIntersecting;
      decidir();
      primera = false;
    }).observe(centinela);
    // Al cerrar un panel, la cabecera se pone al día.
    document.addEventListener("toggle", decidir, true);
  }

  function intentar() {
    // common.js va con defer: cuando la página terminó de leerse, ya corrió.
    const { common } = window;
    if (!common) {
      raiz.removeAttribute("data-barra");
      return;
    }
    try {
      montar(common);
    } catch (error) {
      raiz.removeAttribute("data-barra");
      throw error;
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", intentar);
  else intentar();
})();
