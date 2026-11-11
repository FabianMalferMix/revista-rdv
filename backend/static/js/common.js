// Lo que comparten los guiones del sitio: la consulta de «reducir movimiento», si se puede animar,
// las curvas de la hoja, el gesto de deslizar con el dedo y el montaje de cada componente. Es un
// guion clásico, como los demás (sin módulos y sin compilar: el navegador lo ejecuta tal cual),
// que base.html carga con defer antes que los guiones que lo usan. Todo queda en `window.common`
// al final: si algo falla antes, no queda a medias, y cada guion que no lo encuentra deja su
// componente como sin JavaScript.
(() => {
  // Quien pidió menos movimiento: nada se anima y los cambios van al instante.
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)');

  // Se anima con la API de animaciones solo si el navegador la tiene y no se pidió menos
  // movimiento. Se pregunta en cada cambio: la preferencia puede cambiar con la página abierta.
  const canAnimate = () => !quieto.matches && typeof Element.prototype.animate === 'function';

  // Las curvas viven en la hoja (tokens.css) y se leen al pedirlas, no al cargar este archivo:
  // así solo calcula estilos la página que anima.
  const rootStyle = () => getComputedStyle(document.documentElement);

  // Deslizar con el dedo (o el lápiz) sobre `surface`. Solo cuenta un gesto claramente
  // horizontal, de 40 px o más y una vez y media más ancho que alto: el vertical sigue bajando la
  // página (touch-action en componentes.css). `swiped` recibe el recorrido, negativo hacia la
  // izquierda. Un deslizamiento no abre lo que quedó debajo: el clic que le sigue en los 400 ms
  // siguientes se corta en `clicks`, en la fase de captura. Las escuchas cuelgan de `signal`.
  function onSwipe(surface, swiped, { clicks = surface, signal } = {}) {
    let x0 = null;
    let y0 = 0;
    let deslizado = 0;
    surface.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse') return;
      x0 = e.clientX;
      y0 = e.clientY;
    }, { signal });
    surface.addEventListener('pointerup', (e) => {
      if (x0 === null) return;
      const dx = e.clientX - x0;
      const dy = e.clientY - y0;
      x0 = null;
      if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      deslizado = e.timeStamp;
      swiped(dx);
    }, { signal });
    surface.addEventListener('pointercancel', () => { x0 = null; }, { signal });
    clicks.addEventListener('click', (e) => {
      if (deslizado && e.timeStamp - deslizado < 400) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, { capture: true, signal });
  }

  // Monta cada elemento que responde a `selector` una sola vez: queda marcado (data-mounted) antes
  // de montarse, así que otra pasada no duplica sus escuchas y un montaje que falló no se repite.
  // La marca no dice de qué componente es: cada elemento es la raíz de uno solo. Monta los que ya
  // están y, con htmx en la página, los que lleguen con él (htmx.onLoad recibe la raíz de lo que
  // llegó, que también puede ser el componente).
  function mountAll(selector, mount) {
    const mountIn = (root) => {
      const found = [...root.querySelectorAll(selector)];
      if (root.matches?.(selector)) found.unshift(root);
      found.forEach((element) => {
        if (element.hasAttribute('data-mounted')) return;
        element.setAttribute('data-mounted', '');
        mount(element);
      });
    };
    mountIn(document);
    if (window.htmx) window.htmx.onLoad(mountIn);
  }

  window.common = Object.freeze({
    quieto,
    canAnimate,
    // La de la tirada, que comparten la tirada y el estante.
    get CURVA() {
      return rootStyle().getPropertyValue('--ease-tirada').trim();
    },
    // La de las transiciones del sitio.
    get SUAVE() {
      return rootStyle().getPropertyValue('--ease').trim();
    },
    onSwipe,
    mountAll,
  });
})();
