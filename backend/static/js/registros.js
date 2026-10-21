// La tirada de la portada (D19): un pliego al frente y los demás como pruebas en trama.
// Sin este guion la tirada es una fila con imán y todos los pliegos a dos tintas. Aquí solo
// se cambian clases y atributos (aria-current, aria-label, disabled, hidden) y se desplaza el
// carril: nada avanza solo, no se toca la dirección ni el historial, y el aspecto vive en
// site.css (la CSP no admite estilos en línea).
(() => {
  function montar(seccion) {
    const pliegos = [...seccion.querySelectorAll('.pliego')];
    const n = pliegos.length;
    if (n < 2) return;
    const carril = seccion.querySelector('.tirada-carril');
    const enlaces = pliegos.map((p) => p.querySelector('.pliego-titulo a'));
    const titulos = pliegos.map((p) => p.dataset.titulo);
    const contactos = [...seccion.querySelectorAll('.tirada-contacto')];
    const anterior = seccion.querySelector('[data-anterior]');
    const siguiente = seccion.querySelector('[data-siguiente]');
    const anuncio = seccion.querySelector('[data-anuncio]');
    const quieto = window.matchMedia('(prefers-reduced-motion: reduce)');
    let actual = -1;

    seccion.classList.add('con-js');
    seccion.querySelectorAll('.tirada-mandos[hidden], .tirada-contactos[hidden]').forEach((e) => { e.hidden = false; });

    // El pliego al frente: lo marca aria-current (de ahí cuelgan las tintas en site.css), las
    // flechas dicen adónde llevan y se apagan en los extremos, y la región viva lo anuncia.
    function marcar(i, avisar) {
      if (i === actual) return;
      actual = i;
      pliegos.forEach((p, j) => (j === i ? p.setAttribute('aria-current', 'true') : p.removeAttribute('aria-current')));
      contactos.forEach((c, j) => (j === i ? c.setAttribute('aria-current', 'true') : c.removeAttribute('aria-current')));
      anterior.disabled = i === 0;
      siguiente.disabled = i === n - 1;
      anterior.setAttribute('aria-label', i > 0 ? `Anterior: «${titulos[i - 1]}»` : 'Anterior');
      siguiente.setAttribute('aria-label', i < n - 1 ? `Siguiente: «${titulos[i + 1]}»` : 'Siguiente');
      if (avisar) anuncio.textContent = `Registro ${i + 1} de ${n}: ${titulos[i]}`;
    }
    // El carril se alinea con el pliego: deslizándose, salvo si se pidió menos movimiento.
    function borde() {
      return parseFloat(getComputedStyle(carril).scrollPaddingLeft) || 0;
    }
    function ir(i, avisar = true) {
      const k = Math.max(0, Math.min(n - 1, i));
      carril.scrollTo({ left: pliegos[k].offsetLeft - borde(), behavior: quieto.matches ? 'auto' : 'smooth' });
      marcar(k, avisar);
    }
    function cercano() {
      const x = carril.scrollLeft + borde();
      let mejor = 0;
      pliegos.forEach((p, j) => { if (Math.abs(p.offsetLeft - x) < Math.abs(pliegos[mejor].offsetLeft - x)) mejor = j; });
      return mejor;
    }
    marcar(0, false);

    anterior.addEventListener('click', () => ir(actual - 1));
    siguiente.addEventListener('click', () => ir(actual + 1));
    // Elegir en la hoja de contactos lleva el foco al título del registro elegido.
    contactos.forEach((c) => c.addEventListener('click', () => {
      const i = Number(c.dataset.marcador);
      ir(i);
      enlaces[i].focus({ preventScroll: true });
    }));
    // Con el dedo o el trackpad: el pliego al frente se decide cuando el carril se detiene.
    let espera;
    const alDetenerse = () => marcar(cercano(), true);
    if ('onscrollend' in window) carril.addEventListener('scrollend', alDetenerse);
    else carril.addEventListener('scroll', () => { clearTimeout(espera); espera = setTimeout(alDetenerse, 150); });
    // El teclado: el foco que entra en una prueba la trae al frente (sin anunciarla: ya se
    // lee su título), y las flechas del teclado pasan de un pliego al de al lado.
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
    // Pulsar una prueba la trae al frente; su título, en cambio, siempre lleva a la ficha.
    seccion.addEventListener('click', (e) => {
      const p = e.target.closest('.pliego');
      if (!p || p.hasAttribute('aria-current') || e.target.closest('a')) return;
      ir(pliegos.indexOf(p));
    });
  }

  document.querySelectorAll('[data-tirada]').forEach(montar);
})();
