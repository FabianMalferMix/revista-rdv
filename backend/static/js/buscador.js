// La lupa de la cabecera abre el campo de búsqueda en la fila (un <details> nativo: sin
// JavaScript abre igual y el formulario lleva a /buscar/). Esto solo afina:
//   · al abrirlo, el foco va al campo, que es lo que se quiere hacer;
//   · Escape cierra el panel abierto (o el menú del teléfono) y devuelve el foco a su botón;
//   · si el foco sale del panel (o del menú), el panel se cierra y el foco se queda donde la
//     persona lo llevó: en el teléfono, el menú tapa lo que hay debajo;
//   · con una sola letra htmx no busca (minlength y hx-validate en base.html), y lo que había
//     de la búsqueda anterior se quita, porque ya no corresponde a lo escrito.
(function () {
  "use strict";

  // `toggle` no burbujea: se escucha en la fase de captura.
  document.addEventListener(
    "toggle",
    function (evento) {
      var panel = evento.target;
      if (!panel.matches || !panel.matches(".busqueda") || !panel.open) return;
      var campo = panel.querySelector('input[type="search"]');
      // Sin desplazar: el campo está en la cabecera fija, siempre a la vista.
      if (campo) campo.focus({ preventScroll: true });
    },
    true
  );

  document.addEventListener("keydown", function (evento) {
    if (evento.key !== "Escape") return;
    var abierto = document.querySelector(".busqueda[open], .nav-disclosure[open]");
    if (!abierto) return;
    abierto.open = false;
    var boton = abierto.querySelector("summary");
    // Sin desplazar la página: la cabecera está a la vista, y enfocar la lupa a mitad de
    // página la hacía saltar unos 450 px.
    if (boton) boton.focus({ preventScroll: true });
  });

  // Se mira adónde llegó el foco una vez terminado el cambio: si es la ventana entera la que lo
  // pierde, el foco sigue dentro del panel y el panel no se cierra. Tampoco si se apretó dentro
  // y el foco no fue a ninguna parte: Safari lo suelta al apretar un resultado, antes del clic.
  var apretado = null;
  document.addEventListener(
    "pointerdown",
    function (evento) {
      apretado = evento.target;
    },
    true
  );
  document.addEventListener("focusout", function (evento) {
    var panel = evento.target.closest && evento.target.closest(".busqueda[open], .nav-disclosure[open]");
    if (!panel) return;
    setTimeout(function () {
      var foco = document.activeElement;
      if (!panel.open || !document.hasFocus() || panel.contains(foco)) return;
      if ((!foco || foco === document.body) && panel.contains(apretado)) return;
      panel.open = false;
    });
  });

  document.addEventListener("htmx:validation:failed", function (evento) {
    var panel = evento.target.closest && evento.target.closest(".busqueda");
    if (!panel) return;
    panel.querySelectorAll("#search-results, #search-status").forEach(function (region) {
      region.textContent = "";
    });
  });
})();
