// Los reproductores externos se cargan al pulsar. El iframe de YouTube o Vimeo conecta con
// ese tercero en cuanto se inserta, y le envía la IP y el agente de usuario de quien abre la
// página: aquí solo se crea cuando la persona lo pide. Un único escuchador delegado en el
// documento cubre todos los reproductores, incluidos los que llegan por htmx.
(() => {
  "use strict";

  function reproducir(contenedor) {
    const src = contenedor.getAttribute("data-embed-src");
    if (!src) return;

    const iframe = document.createElement("iframe");
    iframe.setAttribute("src", src);
    iframe.setAttribute("title", contenedor.getAttribute("data-embed-title") || "Video");
    iframe.setAttribute("allowfullscreen", "");
    iframe.setAttribute("allow", "accelerometer; encrypted-media; picture-in-picture");
    // Se carga en cuanto se pide: quien pulsó ya expresó su intención.
    iframe.setAttribute("loading", "eager");

    contenedor.textContent = "";
    contenedor.classList.remove("player-consent");
    contenedor.appendChild(iframe);
    iframe.focus();
  }

  document.addEventListener("click", (evento) => {
    const boton = evento.target.closest(".embed-play");
    if (!boton) return;
    const contenedor = boton.closest(".player-consent");
    if (contenedor) reproducir(contenedor);
  });
})();
