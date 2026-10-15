// La lupa de la cabecera abre el buscador en un panel (un <details> nativo: sin
// JavaScript abre igual y el formulario lleva a /buscar/). Esto solo afina:
//   · al abrirlo, el foco va al campo, que es lo que se quiere hacer;
//   · Escape cierra el panel abierto (o el menú del teléfono) y devuelve el foco a su botón.
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
})();
