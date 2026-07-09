// Inicializa TinyMCE sobre los textarea con clase .richtext en el admin.
// TinyMCE se carga por CDN (self-hosted build, sin API key). Para producción
// offline conviene vendorizarlo en static/.
window.addEventListener("load", function () {
  if (!window.tinymce) return;
  window.tinymce.init({
    selector: "textarea.richtext",
    menubar: false,
    plugins: "lists link autolink",
    toolbar:
      "undo redo | h2 h3 | bold italic | bullist numlist | blockquote link | removeformat",
    height: 480,
    branding: false,
    // Coincide con la lista blanca de nh3 (el servidor vuelve a sanitizar al guardar).
    valid_elements:
      "p,br,hr,blockquote,pre,code,em,strong,i,b,u,s,sub,sup,small,cite," +
      "h2,h3,h4,ul,ol,li,a[href|title],img[src|alt|title|width|height],figure,figcaption",
  });
});
