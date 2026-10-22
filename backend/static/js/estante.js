// El estante de la portada (D24): una publicación de frente y las demás de lomo. Sin este guion,
// cada lomo lleva a su ficha. Con él, el lomo es un botón que saca ese libro al frente: el que
// estaba vuelve a su lugar de lomo y al lado aparece la ficha del nuevo, con el foco en su
// título. Aquí solo se cambian clases y atributos; el aspecto vive en site.css (la CSP no admite
// estilos en línea). Nada se mueve solo.
(() => {
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)');

  function montar(seccion) {
    const ejemplares = [...seccion.querySelectorAll('.ejemplar')];
    const fichas = [...seccion.querySelectorAll('.estante-ficha')];
    if (ejemplares.length < 2) return;

    function alFrente(i) {
      if (ejemplares[i].classList.contains('es-frente')) return;
      ejemplares.forEach((li, k) => li.classList.toggle('es-frente', k === i));
      fichas.forEach((f, k) => { f.hidden = k !== i; });
      if (!quieto.matches && typeof Element.prototype.animate === 'function') {
        // Sale del estante y se apoya de frente; la ficha entra desde el lado.
        ejemplares[i].querySelector('.ejemplar-frente').animate(
          [{ transform: 'translateY(-60px) rotate(-8deg) scale(.9)', opacity: 0 }, { transform: 'none', opacity: 1 }],
          { duration: 520, easing: 'cubic-bezier(.2,.9,.3,1.2)' });
        fichas[i].animate([{ opacity: 0, transform: 'translateX(12px)' }, { opacity: 1, transform: 'none' }], { duration: 360 });
      }
      fichas[i].querySelector('.estante-titulo').focus({ preventScroll: true });
    }

    // Con el guion el lomo ya no lleva a la ficha: saca el libro al frente. Por eso deja de ser
    // un enlace y pasa a ser un botón, y un lector de pantalla oye «Sacar al frente» antes del
    // título y el año que se ven.
    ejemplares.forEach((li, i) => {
      const enlace = li.querySelector('.ejemplar-lomo');
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = enlace.className;
      const accion = document.createElement('span');
      accion.className = 'sr-only';
      accion.textContent = 'Sacar al frente: ';
      boton.append(accion, ...enlace.childNodes);
      enlace.replaceWith(boton);
      boton.addEventListener('click', () => alFrente(i));
    });
  }

  document.querySelectorAll('[data-estante]').forEach(montar);
})();
