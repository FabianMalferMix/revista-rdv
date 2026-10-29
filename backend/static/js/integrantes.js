// «Las voces» en la portada (D23): una fila de retratos y las demás esperando su turno,
// escondidas al final de la lista. Cuántos se ven lo dicen `data-a-la-vista` y
// `data-a-la-vista-telefono`, que la plantilla pone desde A_LA_VISTA (apps/content/views.py). Cada 1,8 s llega otra a uno de los
// lugares, bajo una pasada de tinta azul con el filo magenta, como el tambor de una risógrafo.
// Corre solo donde hay un puntero que pueda posarse y no se pidió menos movimiento (como la
// cinta, D1), y se detiene con el puntero encima o el foco dentro, fuera de la vista y con la
// pestaña oculta. En el teléfono, deslizar el dedo trae a otras. Sin este guion se ven las
// primeras y el botón a /integrantes/. Aquí solo se cambian `hidden` y el orden de la lista; la
// tinta es una capa con su clase en site.css (la CSP no admite estilos en línea).
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

  function montar(seccion) {
    const lista = seccion.querySelector('.integrantes-retratos');
    const n = lista.children.length;
    const aLaVista = Number(seccion.dataset.aLaVista);
    const enTelefono = Number(seccion.dataset.aLaVistaTelefono);
    let V = 0;
    let ocupado = 0;
    let turno = 0;
    let enVista = false;

    // Las que se ven son siempre las primeras de la lista.
    function ajustar() {
      V = Math.min(movil.matches ? enTelefono : aLaVista, n);
      [...lista.children].forEach((li, k) => { li.hidden = k >= V; });
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

    // Al lugar de `viejo` llega la que lleva más tiempo esperando (la primera escondida), y
    // `viejo` pasa al final de la espera.
    async function relevar(viejo, retraso, atras) {
      const anima = !quieto.matches && typeof Element.prototype.animate === 'function';
      ocupado += 1;
      let capa = null;
      if (anima) {
        capa = tinta(viejo, atras);
        await capa.animate([{ clipPath: ANTES(atras) }, { clipPath: LLENO }],
          { duration: CUBRE, delay: retraso, easing: CURVA, fill: 'both' }).finished.catch(() => {});
      }
      const nuevo = lista.children[V];
      if (nuevo && nuevo.hidden) {
        viejo.before(nuevo);
        nuevo.hidden = false;
        viejo.hidden = true;
        lista.append(viejo);
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
      if (!solo.matches || !enVista || document.hidden || ocupado || n <= V) return;
      if (seccion.matches(':hover, :focus-within')) return;
      const orden = salteado(V);
      relevar(lista.children[orden[turno % orden.length]], 0, false);
      turno += 1;
    }, CADA);

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
      if (ocupado || n <= V) return;
      const atras = dx < 0;
      const lugares = [...lista.children].slice(0, V);
      (atras ? lugares.reverse() : lugares).forEach((li, k) => relevar(li, k * 110, atras));
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
