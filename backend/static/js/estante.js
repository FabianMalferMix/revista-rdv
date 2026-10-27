// El estante de la portada (D24): una publicación de frente y las demás de lomo. Sin este guion,
// cada lomo lleva a su ficha. Con él, el lomo es un botón que saca ese libro al frente: el que
// estaba vuelve a su lugar de lomo y al lado aparece la ficha del nuevo, con el foco en su
// título. El cambio es suave (D27): cada libro se desliza desde donde estaba hasta su lugar
// nuevo, el elegido gira desde el lomo hasta quedar de frente y las fichas se funden. Y sin
// prisa (D32): con la curva de la tirada el libro arranca suave, viaja por el medio y se asienta
// despacio; con la de antes, casi todo el recorrido pasaba en los primeros 90 ms. Aquí solo
// se cambian clases y atributos y se anima con la API de animaciones; el aspecto vive en
// site.css (la CSP no admite estilos en línea). Nada se mueve solo.
(() => {
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)');
  const DESLIZA = 800;
  const GIRO = 900;
  const CURVA = 'cubic-bezier(.45,.05,.25,1)';
  // Las fichas, con la curva de las transiciones del sitio (--ease en site.css).
  const SUAVE = 'cubic-bezier(.22,.61,.36,1)';

  function montar(seccion) {
    const ejemplares = [...seccion.querySelectorAll('.ejemplar')];
    const fichas = [...seccion.querySelectorAll('.estante-ficha')];
    if (ejemplares.length < 2) return;

    function alFrente(i) {
      if (ejemplares[i].classList.contains('es-frente')) return;
      // Un cambio a medias se corta: las clases ya dicen dónde va cada uno.
      seccion.getAnimations({ subtree: true }).forEach((a) => a.cancel());
      const anima = !quieto.matches && typeof Element.prototype.animate === 'function';
      const previo = ejemplares.findIndex((li) => li.classList.contains('es-frente'));
      const antes = ejemplares.map((li) => li.getBoundingClientRect().left);
      ejemplares.forEach((li, k) => li.classList.toggle('es-frente', k === i));
      fichas.forEach((f, k) => { f.hidden = k !== i && k !== previo; });
      if (anima) {
        // Cada libro, desde donde estaba (FLIP): la diferencia entre antes y ahora se deshace.
        ejemplares.forEach((li, k) => {
          const dx = antes[k] - li.getBoundingClientRect().left;
          if (k === i) {
            li.animate([
              { transform: `translateX(${dx}px) perspective(900px) rotateY(-80deg)`, transformOrigin: 'left center', opacity: 0.5 },
              { transform: 'none', transformOrigin: 'left center', opacity: 1 },
            ], { duration: GIRO, easing: CURVA });
          } else if (k === previo) {
            li.animate([{ transform: `translateX(${dx}px)`, opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: DESLIZA, easing: CURVA });
          } else if (Math.abs(dx) > 0.5) {
            li.animate([{ transform: `translateX(${dx}px)` }, { transform: 'none' }], { duration: DESLIZA, easing: CURVA });
          }
        });
        // La ficha vieja se desvanece mientras llega la nueva, en la misma celda.
        // Si mientras tanto volvió al frente, no se esconde.
        const funde = fichas[previo].animate([{ opacity: 1 }, { opacity: 0 }], { duration: 320, easing: SUAVE, fill: 'forwards' });
        funde.finished.then(() => {
          if (!ejemplares[previo].classList.contains('es-frente')) fichas[previo].hidden = true;
          funde.cancel();
        }, () => {});
        // La nueva llega cuando el libro va a medio girar, y se asienta con él.
        fichas[i].animate([{ opacity: 0, transform: 'translateY(14px)' }, { opacity: 1, transform: 'none' }],
          { duration: 560, delay: 360, easing: SUAVE, fill: 'backwards' });
      } else {
        fichas[previo].hidden = true;
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
