// «El colectivo» en la portada (D22), en pliegos de seis. «Otras seis» y la flecha reparten
// las siguientes o las anteriores, y en el teléfono se desliza sobre los retratos. Sin este
// guion se ven las seis primeras y el botón a /integrantes/. Aquí solo se cambian atributos
// (hidden) y el orden de las tarjetas en la lista; las posiciones viven en site.css (la CSP
// no admite estilos en línea). Nada avanza solo.
(() => {
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)');
  // Las seis salen como cartas que se recogen y entran las siguientes, una tras otra.
  const SALIDA = 240;
  const ENTRADA = 380;
  const PASO = 45;
  const CURVA = 'cubic-bezier(.45,.05,.25,1)';

  function montar(seccion) {
    const lista = seccion.querySelector('.integrantes-pliego');
    const todas = [...lista.children];
    const n = todas.length;
    const pliego = todas.filter((li) => !li.hidden).length;
    if (n <= pliego) return;
    const anuncio = seccion.querySelector('[data-anuncio]');
    let inicio = 0;
    let repartiendo = false;

    seccion.classList.add('con-js');
    seccion.querySelector('.integrantes-mandos').hidden = false;

    // Las seis que tocan desde `desde`, dando la vuelta: el último pliego se completa con las
    // primeras, así siempre hay seis y nadie queda sola en una fila.
    const ventana = (desde) => Array.from({ length: pliego }, (_, k) => todas[(desde + k) % n]);

    function poner(desde) {
      const visibles = ventana(desde);
      todas.forEach((li) => { li.hidden = !visibles.includes(li); });
      // Las que se ven van primero y en orden: así se leen y se recorren con el tabulador
      // como se ven, y la columna corrida (nth-child en site.css) cae en la del medio.
      lista.prepend(...visibles);
      // Los retratos del pliego siguiente se piden ya, para que no lleguen en blanco.
      ventana(desde + pliego).forEach((li) => li.querySelectorAll('img').forEach((i) => { i.loading = 'eager'; }));
    }

    function animar(tarjetas, desde, hasta, duracion) {
      return Promise.all(tarjetas.map((li, k) => li.animate([desde, hasta], {
        duration: duracion, delay: k * PASO, easing: CURVA, fill: 'both',
      }).finished.catch(() => {})));
    }

    // paso: 1, las siguientes; -1, las anteriores.
    async function ir(paso) {
      if (repartiendo) return;
      const salen = ventana(inicio);
      inicio = (((inicio + paso * pliego) % n) + n) % n;
      const entran = ventana(inicio);
      const mueve = !quieto.matches && typeof Element.prototype.animate === 'function';
      repartiendo = true;
      if (mueve) {
        const lado = -paso;
        await animar(salen, { transform: 'none', opacity: 1 },
          { transform: `translateX(${lado * 28}px) rotate(${lado * 3}deg)`, opacity: 0 }, SALIDA);
        salen.forEach((li) => li.getAnimations().forEach((a) => a.cancel()));
      }
      poner(inicio);
      anuncio.textContent = `Ahora: ${entran.map((li) => li.querySelector('.member-name').textContent.trim()).join(', ')}.`;
      if (mueve) {
        await animar(entran, { transform: `translateX(${paso * 36}px) rotate(${paso * 3}deg)`, opacity: 0 },
          { transform: 'none', opacity: 1 }, ENTRADA);
        entran.forEach((li) => li.getAnimations().forEach((a) => a.cancel()));
      }
      repartiendo = false;
    }

    seccion.querySelector('[data-siguientes]').addEventListener('click', () => ir(1));
    seccion.querySelector('[data-anteriores]').addEventListener('click', () => ir(-1));

    // Deslizar con el dedo (o el lápiz) sobre los retratos: hacia la izquierda, las siguientes;
    // hacia la derecha, las anteriores. Solo un gesto claramente horizontal: el vertical sigue
    // bajando la página (touch-action en site.css). Un deslizamiento no abre la ficha de debajo.
    let x0 = null;
    let y0 = 0;
    let deslizado = 0;
    lista.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse') return;
      x0 = e.clientX;
      y0 = e.clientY;
    });
    lista.addEventListener('pointerup', (e) => {
      if (x0 === null) return;
      const dx = e.clientX - x0;
      const dy = e.clientY - y0;
      x0 = null;
      if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      deslizado = e.timeStamp;
      ir(dx < 0 ? 1 : -1);
    });
    lista.addEventListener('pointercancel', () => { x0 = null; });
    lista.addEventListener('click', (e) => {
      if (deslizado && e.timeStamp - deslizado < 400) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, true);
  }

  document.querySelectorAll('[data-integrantes]').forEach(montar);
})();
