// Botón "Imprimir / guardar como PDF" del dossier, sin handler inline
// (la CSP restrictiva no permite onclick=""). Enlaza el click al diálogo
// de impresión del navegador.
document.addEventListener("DOMContentLoaded", function () {
  var btn = document.querySelector("[data-print]");
  if (btn) {
    btn.addEventListener("click", function () {
      window.print();
    });
  }
});
