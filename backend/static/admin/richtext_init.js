// Inicializa TinyMCE sobre los textarea con clase .richtext en el admin.
// TinyMCE va auto-hospedado en static/vendor/tinymce-<versión>/ (sin CDN, sin API key);
// su cargador resuelve el resto de recursos relativos a tinymce.min.js.
//
// Las etiquetas y atributos que admite el editor llegan en el atributo data-valid-elements de
// cada cuadro (RichTextWidget): son los que deja pasar nh3 al guardar, de la misma lista. Un
// cuadro sin esa lista se queda sin editor y lo dice en la consola: con la suya por defecto,
// TinyMCE enseñaría lo que el servidor después quita.
window.addEventListener("load", () => {
  if (!window.tinymce) return;
  document.querySelectorAll("textarea.richtext").forEach((textarea) => {
    const validElements = textarea.getAttribute("data-valid-elements");
    if (!validElements) {
      console.error(`richtext_init: el cuadro ${textarea.name} no trae data-valid-elements`);
      return;
    }
    window.tinymce.init({
      target: textarea,
      menubar: false,
      plugins: "lists link autolink",
      // Una imagen pegada viaja como data: y la limpieza del HTML la borra al guardar: mejor
      // que no entre. Las imágenes del texto se suben como recurso.
      paste_data_images: false,
      toolbar:
        "undo redo | h2 h3 | bold italic | bullist numlist | blockquote link | removeformat",
      height: 480,
      branding: false,
      valid_elements: validElements,
    });
  });
});
