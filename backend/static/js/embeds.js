// Click-to-play de los reproductores externos (hallazgo de seguridad S-19).
//
// El iframe de YouTube/Vimeo se insertaba con la página, así que el navegador contactaba
// con ese tercero —enviándole IP, agente de usuario y referente— en cuanto se abría
// cualquier ficha de registro y también la PORTADA, sin que nadie hubiera pulsado nada y
// mientras /cookies/ afirma que no se comparte información con terceros.
//
// Aquí el iframe solo se crea cuando la persona lo pide. Un único escuchador delegado en
// el documento cubre todos los reproductores, incluidos los que llegan por htmx.
(function () {
  "use strict";

  function reproducir(contenedor) {
    var src = contenedor.getAttribute("data-embed-src");
    if (!src) return;

    var iframe = document.createElement("iframe");
    iframe.setAttribute("src", src);
    iframe.setAttribute("title", contenedor.getAttribute("data-embed-title") || "Video");
    iframe.setAttribute("allowfullscreen", "");
    iframe.setAttribute("allow", "accelerometer; encrypted-media; picture-in-picture");
    // Se reproduce en cuanto se pide: quien pulsó ya expresó su intención.
    iframe.setAttribute("loading", "eager");

    contenedor.textContent = "";
    contenedor.classList.remove("player-consent");
    contenedor.appendChild(iframe);
    iframe.focus();
  }

  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest(".embed-play");
    if (!boton) return;
    var contenedor = boton.closest(".player-consent");
    if (contenedor) reproducir(contenedor);
  });
})();
