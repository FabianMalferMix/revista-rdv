// Los reproductores externos se cargan al pulsar. El iframe de YouTube o Vimeo conecta con
// ese tercero en cuanto se inserta, y le envía la IP y el agente de usuario de quien abre la
// página: aquí solo se crea cuando la persona lo pide. Un único escuchador delegado en el
// documento cubre todos los reproductores, incluidos los que llegan por htmx.
(() => {
  "use strict";

  function reproducir(contenedor) {
    const src = contenedor.getAttribute("data-embed-src");
    if (!src) return;

    // El clic en la placa ya es la orden de reproducir: el reproductor arranca al cargar
    // (`autoplay=1`, que entienden YouTube y Vimeo), y el iframe recibe el permiso de sonar,
    // que el navegador no le da por su cuenta a una página de otro origen.
    const url = new URL(src);
    url.searchParams.set("autoplay", "1");

    const iframe = document.createElement("iframe");
    iframe.setAttribute("src", url.href);
    iframe.setAttribute("title", contenedor.getAttribute("data-embed-title") || "Video");
    iframe.setAttribute("allowfullscreen", "");
    iframe.setAttribute("allow", "accelerometer; autoplay; encrypted-media; picture-in-picture");
    // La página no les dice su dirección a otros sitios (`Referrer-Policy: same-origin`), pero
    // YouTube no reproduce sin saber en qué sitio está incrustado, y Vimeo tampoco cuando el
    // video solo se ve en ciertos dominios: el iframe les envía el origen del sitio, nunca la
    // dirección de la página.
    iframe.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
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
