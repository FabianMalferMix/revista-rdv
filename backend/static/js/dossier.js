// Botón "Imprimir / guardar como PDF" del dossier, sin handler inline
// (la CSP restrictiva no permite onclick=""). Enlaza el click al diálogo
// de impresión del navegador. El botón llega oculto: sin este archivo no
// haría nada, y se enseña al enlazarlo.
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.querySelector("[data-print]");
  if (btn) {
    btn.addEventListener("click", () => {
      window.print();
    });
    btn.hidden = false;
  }
});
