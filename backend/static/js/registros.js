// La tirada de la portada (D19), apilada (D20): un pliego arriba y los demás debajo, corridos
// y apenas girados, como impresos sobre la mesa. Sin este guion la tirada es una fila con imán
// y todos los pliegos a dos tintas. Se pasa de uno a otro con la hoja de contactos (desde 1100 px,
// un índice al lado de la pila, D29), el teclado o el dedo: sin flechas. Aquí se cambian clases y
// atributos (aria-current, hidden) y se anima el reparto; las posiciones de la pila viven en
// site.css (la CSP no admite estilos en línea). Nada avanza solo y no se toca la dirección
// ni el historial.
(() => {
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)');
  // El reparto dura un poco más que el acomodo de los demás (0,66 s en site.css): el que pasa
  // arriba sale de la pila por su lado y vuelve encima, como una carta que se reparte.
  const REPARTO = 700;
  const CURVA = 'cubic-bezier(.45,.05,.25,1)';

  function montar(seccion) {
    const pliegos = [...seccion.querySelectorAll('.pliego')];
    const n = pliegos.length;
    if (n < 2) return;
    const mesa = seccion.querySelector('.tirada-pista-inexistente');
    const enlaces = pliegos.map((p) => p.querySelector('.pliego-titulo a'));
    const titulos = pliegos.map((p) => p.dataset.titulo);
    const contactos = [...seccion.querySelectorAll('.tirada-contacto')];
    const anuncio = seccion.querySelector('[data-anuncio]');
    let actual = -1;

    seccion.classList.add('con-js');
    seccion.querySelectorAll('.tirada-contactos[hidden]').forEach((e) => { e.hidden = false; });

    // El reparto. Cada pliego conserva su altura en la pila hasta el final, así nadie salta por
    // encima de otro mientras se cruzan; el que pasa arriba sale por su lado (por la derecha si
    // viene de los que siguen, por la izquierda si viene de los ya vistos), sube cuando ya no
    // pisa a nadie y vuelve encima. Los demás se acomodan con la transición de site.css.
    function repartir(desde, hacia, antes) {
      const entra = pliegos[hacia];
      const lado = hacia > desde ? 1 : -1;
      pliegos.forEach((p, j) => {
        if (j !== hacia && getComputedStyle(p).zIndex !== antes[j].z) {
          p.animate([{ zIndex: antes[j].z }, { zIndex: antes[j].z }], { duration: REPARTO });
        }
      });
      entra.classList.add('pliego--repartiendo');
      const fin = getComputedStyle(entra);
      const afuera = `calc(${fin.translate.split(' ')[0]} ${lado > 0 ? '+' : '-'} 105%) -3%`;
      const giro = `${lado * 7}deg`;
      const animacion = entra.animate([
        { translate: antes[hacia].translate, rotate: antes[hacia].rotate, zIndex: antes[hacia].z },
        { translate: afuera, rotate: giro, zIndex: antes[hacia].z, offset: 0.42 },
        { translate: afuera, rotate: giro, zIndex: 30, offset: 0.43 },
        { translate: fin.translate, rotate: fin.rotate, zIndex: 30 },
      ], { duration: REPARTO, easing: CURVA });
      animacion.addEventListener('finish', () => entra.classList.remove('pliego--repartiendo'));
      animacion.addEventListener('cancel', () => entra.classList.remove('pliego--repartiendo'));
    }

    // El pliego de arriba: lo marca aria-current (de ahí cuelgan la pila y las tintas en
    // site.css), la hoja de contactos lo señala y la región viva lo anuncia.
    function marcar(i, avisar) {
      if (i === actual) return;
      const previo = actual;
      // Un reparto a medias se termina antes del siguiente: cada uno sale de donde quedó.
      pliegos.forEach((p) => p.getAnimations().forEach((a) => { if (!(a instanceof CSSTransition)) a.finish(); }));
      const antes = pliegos.map((p) => { const e = getComputedStyle(p); return { translate: e.translate, rotate: e.rotate, z: e.zIndex }; });
      actual = i;
      pliegos.forEach((p, j) => (j === i ? p.setAttribute('aria-current', 'true') : p.removeAttribute('aria-current')));
      contactos.forEach((c, j) => (j === i ? c.setAttribute('aria-current', 'true') : c.removeAttribute('aria-current')));
      if (avisar) anuncio.textContent = `Registro ${i + 1} de ${n}: ${titulos[i]}`;
      if (previo >= 0 && !quieto.matches && typeof Element.prototype.animate === 'function') repartir(previo, i, antes);
    }
    function ir(i, avisar = true) {
      marcar(Math.max(0, Math.min(n - 1, i)), avisar);
    }
    marcar(0, false);

    // Elegir en la hoja de contactos lleva el foco al título del registro elegido.
    contactos.forEach((c) => c.addEventListener('click', () => {
      const i = Number(c.dataset.marcador);
      ir(i);
      enlaces[i].focus({ preventScroll: true });
    }));
    // El teclado: el foco que llega al título de un pliego de abajo lo sube (sin anunciarlo: ya
    // se lee su título), y las flechas del teclado pasan de un pliego al de al lado.
    seccion.addEventListener('focusin', (e) => {
      const j = enlaces.indexOf(e.target);
      if (j >= 0 && j !== actual && e.target.matches(':focus-visible')) ir(j, false);
    });
    seccion.addEventListener('keydown', (e) => {
      const j = enlaces.indexOf(e.target);
      if (j < 0 || e.altKey || e.ctrlKey || e.metaKey) return;
      const k = e.key === 'ArrowRight' ? j + 1 : e.key === 'ArrowLeft' ? j - 1 : -1;
      if (k < 0 || k >= n) return;
      e.preventDefault();
      enlaces[k].focus({ preventScroll: true });
      ir(k, false);
    });

    // Deslizar con el dedo (o el lápiz) sobre la pila: hacia la izquierda, el siguiente; hacia
    // la derecha, el anterior. Solo un gesto claramente horizontal: el vertical sigue bajando
    // la página (touch-action en site.css). Un deslizamiento no abre la ficha que quedó debajo.
    let x0 = null;
    let y0 = 0;
    let deslizado = 0;
    mesa.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse') return;
      x0 = e.clientX;
      y0 = e.clientY;
    });
    mesa.addEventListener('pointerup', (e) => {
      if (x0 === null) return;
      const dx = e.clientX - x0;
      const dy = e.clientY - y0;
      x0 = null;
      if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      deslizado = e.timeStamp;
      ir(actual + (dx < 0 ? 1 : -1));
    });
    mesa.addEventListener('pointercancel', () => { x0 = null; });
    seccion.addEventListener('click', (e) => {
      if (deslizado && e.timeStamp - deslizado < 400) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, true);

    // Pulsar un pliego de abajo lo sube; su título, en cambio, siempre lleva a la ficha.
    seccion.addEventListener('click', (e) => {
      const p = e.target.closest('.pliego');
      if (!p || p.hasAttribute('aria-current') || e.target.closest('a')) return;
      ir(pliegos.indexOf(p));
    });
  }

  document.querySelectorAll('[data-tirada]').forEach(montar);
})();
