// «Las voces» en la portada: una fila de retratos y las demás esperando su turno. Cuántos se ven
// lo dicen `data-a-la-vista` y `data-a-la-vista-telefono`, que la plantilla pone desde A_LA_VISTA
// (apps/content/views.py). Cada 1,8 s llega otra a uno de los lugares, bajo una pasada de tinta
// azul con el filo magenta, como el tambor de una risógrafo. Corre solo donde hay un puntero que
// pueda posarse y no se pidió menos movimiento, y se detiene con el puntero encima o el foco
// dentro, fuera de la vista y con la pestaña oculta. En el teléfono, deslizar el dedo trae a
// otras. Sin este guion se ven las primeras y el botón a /integrantes/.
//
// El relevo es solo de la vista: la lista no cambia de orden, así que el lector de pantalla la
// recorre siempre entera y igual, aunque los retratos cambien mientras lee. Las que esperan
// quedan fuera de la fila (sr-only) y del tabulador, y el lugar de cada retrato en la fila es su
// `order`, la única propiedad que escribe el guion: la CSP bloquea el atributo style, no el
// CSSOM. La tinta es una capa con su clase en site.css.
(() => {
  const CADA = 1800;
  const CUBRE = 240;
  const DESTAPA = 300;
  const CURVA = 'cubic-bezier(.65,0,.35,1)';
  // A qué lugar llega cada relevo: salteado, para que no parezca una cola. Primero el del medio
  // y después los de los extremos, hacia dentro: con cinco, 2, 0, 4, 1, 3; con tres, 1, 0, 2.
  const salteado = (v) => {
    const medio = Math.floor(v / 2);
    const orden = [medio];
    for (let i = 0; orden.length < v; i += 1) {
      if (i !== medio) orden.push(i);
      const espejo = v - 1 - i;
      if (espejo !== medio && espejo !== i && orden.length < v) orden.push(espejo);
    }
    return orden;
  };
  const solo = window.matchMedia('(hover: hover) and (prefers-reduced-motion: no-preference)');
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)');
  const movil = window.matchMedia('(max-width: 719px)');
  // El recorte de la capa: entra por un lado y sale por el otro; `atras`, de derecha a izquierda.
  const LLENO = 'inset(0 0 0 0)';
  const ANTES = (atras) => (atras ? 'inset(0 0 0 100%)' : 'inset(0 100% 0 0)');
  const DESPUES = (atras) => (atras ? 'inset(0 100% 0 0)' : 'inset(0 0 0 100%)');
  const enlace = (li) => li.querySelector('a');

  function montar(seccion) {
    const lista = seccion.querySelector('.integrantes-retratos');
    const aLaVista = Number(seccion.dataset.aLaVista);
    const enTelefono = Number(seccion.dataset.aLaVistaTelefono);
    const todas = lista ? [...lista.children] : [];
    // Sin la fila, sin cuántas se ven o sin el enlace de cada retrato, «Las voces» quedan como
    // están: las primeras en la fila.
    if (!lista || !(aLaVista > 0) || !(enTelefono > 0) || todas.some((li) => !enlace(li))) return;
    // Quién ocupa cada lugar de la fila, y la espera, con la que lleva más tiempo primero. Al
    // montarse, como sin el guion: a la vista, las primeras de la lista.
    let lugares = [];
    let espera = todas;
    let ocupado = 0;
    let turno = 0;
    let enVista = false;

    function pintar() {
      lugares.forEach((li, k) => {
        li.hidden = false;
        li.classList.remove('sr-only');
        li.classList.toggle('integrante--par', k % 2 === 1);
        li.style.order = String(k);
        enlace(li).removeAttribute('tabindex');
      });
      espera.forEach((li) => {
        li.hidden = false;
        li.classList.add('sr-only');
        li.classList.remove('integrante--par');
        li.style.order = '';
        enlace(li).tabIndex = -1;
      });
    }

    // Al pasar a la pantalla ancha llegan las que más esperan; al volver al teléfono, las que no
    // caben pasan al principio de la espera.
    function ajustar() {
      const V = Math.min(movil.matches ? enTelefono : aLaVista, todas.length);
      if (lugares.length > V) espera = [...lugares.splice(V), ...espera];
      else lugares.push(...espera.splice(0, V - lugares.length));
      pintar();
    }
    ajustar();
    movil.addEventListener('change', ajustar);
    seccion.classList.add('con-js');

    function tinta(li, atras) {
      const capa = document.createElement('span');
      capa.className = atras ? 'integrante-tinta integrante-tinta--atras' : 'integrante-tinta';
      capa.setAttribute('aria-hidden', 'true');
      li.append(capa);
      return capa;
    }

    // Al lugar `k` llega la que lleva más tiempo esperando, y la que se va pasa al final de la
    // espera. Si el retrato que se va tiene el foco, se queda: el foco no puede quedar escondido.
    async function relevar(k, retraso, atras) {
      const anima = !quieto.matches && typeof Element.prototype.animate === 'function';
      const viejo = lugares[k];
      ocupado += 1;
      let capa = null;
      if (anima) {
        capa = tinta(viejo, atras);
        await capa.animate([{ clipPath: ANTES(atras) }, { clipPath: LLENO }],
          { duration: CUBRE, delay: retraso, easing: CURVA, fill: 'both' }).finished.catch(() => {});
      }
      const nuevo = espera[0];
      if (nuevo && lugares[k] === viejo && !viejo.matches(':focus-within')) {
        espera = [...espera.slice(1), viejo];
        lugares[k] = nuevo;
        pintar();
        if (anima) {
          const destapa = tinta(nuevo, atras);
          capa.remove();
          await destapa.animate([{ clipPath: LLENO }, { clipPath: DESPUES(atras) }],
            { duration: DESTAPA, easing: CURVA, fill: 'both' }).finished.catch(() => {});
          destapa.remove();
        }
      }
      capa?.remove();
      ocupado -= 1;
    }

    new IntersectionObserver(([e]) => { enVista = e.isIntersecting; }, { threshold: 0.3 }).observe(seccion);
    setInterval(() => {
      if (!solo.matches || !enVista || document.hidden || ocupado || !espera.length) return;
      if (seccion.matches(':hover, :focus-within')) return;
      const orden = salteado(lugares.length);
      relevar(orden[turno % orden.length], 0, false);
      turno += 1;
    }, CADA);

    // El tabulador recorre la fila en el orden en que se ve, que con el relevo ya no es el de la
    // lista: entra por el primer lugar (por el último si viene de abajo), pasa al de al lado y
    // sale de la fila por los extremos.
    lista.addEventListener('focusin', (e) => {
      if (lista.contains(e.relatedTarget) || !e.target.matches(':focus-visible')) return;
      const vistos = lugares.map(enlace);
      const desdeAbajo = e.relatedTarget && lista.compareDocumentPosition(e.relatedTarget) & Node.DOCUMENT_POSITION_FOLLOWING;
      const puerta = desdeAbajo ? vistos[vistos.length - 1] : vistos[0];
      if (vistos.includes(e.target) && puerta !== e.target) puerta.focus();
    });
    lista.addEventListener('keydown', (e) => {
      if (e.key !== 'Tab' || e.altKey || e.ctrlKey || e.metaKey) return;
      const vistos = lugares.map(enlace);
      const k = vistos.indexOf(e.target);
      if (k < 0) return;
      const otro = vistos[k + (e.shiftKey ? -1 : 1)];
      if (otro) {
        e.preventDefault();
        otro.focus();
        return;
      }
      // Desde un extremo, el foco sale con el orden de la página: los demás retratos, que en la
      // lista pueden ir después, quedan fuera del tabulador hasta que el foco se fue.
      const resto = vistos.filter((a) => a !== e.target);
      resto.forEach((a) => { a.tabIndex = -1; });
      e.target.addEventListener('blur', () => resto.forEach((a) => a.removeAttribute('tabindex')), { once: true });
    });

    // Deslizar con el dedo (o el lápiz) sobre los retratos trae a otras, con la tinta en el
    // sentido del gesto. Solo un gesto claramente horizontal: el vertical sigue bajando la página
    // (touch-action en site.css). Un deslizamiento no abre la ficha de debajo.
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
      if (ocupado || !espera.length) return;
      const atras = dx < 0;
      const ks = [...lugares.keys()];
      (atras ? ks.reverse() : ks).forEach((k, j) => relevar(k, j * 110, atras));
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
