#!/usr/bin/env node
// Superficies: lo que el ticket 3.1 y el 3.2 prometen, medido en la página pintada.
//
//   node tools/ux/superficies.js <ancho> <alto> [nombre …]
//   node tools/ux/superficies.js 951 900                 # todas las páginas de pages.txt
//   node tools/ux/superficies.js 390 800 home dossier    # solo esas
//
// Por cada página, una fila con:
//   tinta     bandas de tinta: lo que tiene de fondo el color --ink y ocupa casi todo el
//             ancho (el pie cuenta). Meta: 2 o menos.
//   amarillo  planos de --riso-amarillo que coinciden en una misma pantalla, en el peor
//             punto del recorrido. Meta: 1 o menos.
//   cajas     cajas blancas con borde que no son un campo ni una imagen. Meta: 0.
//   <AA       textos por debajo de 4,5:1 (3:1 si son grandes) contra el fondo que tienen
//             debajo, buscado hacia arriba en el árbol. Meta: 0. Se nombran los peores.
// Sale con código 1 si alguna página no cumple, o si no responde 200.

const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const [, , ANCHO, ALTO, ...SOLO] = process.argv;
if (!ANCHO || !ALTO) {
  console.error('Uso: node tools/ux/superficies.js <ancho> <alto> [nombre …]');
  process.exit(2);
}
const BASE = process.env.UX_BASE || 'http://localhost:8000';
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';

const paginas = fs
  .readFileSync(path.join(__dirname, 'pages.txt'), 'utf8')
  .split('\n')
  .filter((l) => l.trim() && !l.startsWith('#'))
  .map((l) => l.trim().split(/\s+/))
  .filter(([nombre]) => !SOLO.length || SOLO.includes(nombre));

// Se ejecuta dentro de la página.
function medir() {
  const raiz = getComputedStyle(document.documentElement);
  const rgb = (hex) => {
    const h = hex.trim().replace('#', '');
    const n = parseInt(h.length === 3 ? h.replace(/./g, '$&$&') : h, 16);
    return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
  };
  const TINTA = rgb(raiz.getPropertyValue('--ink'));
  const AMARILLO = rgb(raiz.getPropertyValue('--riso-amarillo'));
  const BLANCO = 'rgb(255, 255, 255)';
  const opaco = (c) => c && c !== 'transparent' && !/rgba\(.*,\s*0\)$/.test(c);
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const fondo = (el) => getComputedStyle(el).backgroundColor;
  const exterior = (el, color) => !el.parentElement || fondo(el.parentElement) !== color;
  const todos = [...document.querySelectorAll('body *')].filter(visible);

  const tinta = todos.filter(
    (el) => fondo(el) === TINTA && exterior(el, TINTA)
      && el.getBoundingClientRect().width >= 0.9 * innerWidth && el.getBoundingClientRect().height >= 48,
  );

  const amarillos = todos.filter((el) => fondo(el) === AMARILLO && exterior(el, AMARILLO));
  const alto = document.documentElement.scrollHeight;
  let amarilloPorPantalla = 0;
  for (let y = 0; y <= Math.max(0, alto - innerHeight); y += 50) {
    const enPantalla = amarillos.filter((el) => {
      const r = el.getBoundingClientRect();
      const arriba = r.top + scrollY;
      return arriba < y + innerHeight && arriba + r.height > y;
    }).length;
    amarilloPorPantalla = Math.max(amarilloPorPantalla, enPantalla);
  }

  const OBJETOS = new Set(['INPUT', 'TEXTAREA', 'SELECT', 'IMG', 'VIDEO', 'AUDIO', 'IFRAME', 'BUTTON']);
  const cajas = todos
    .filter((el) => !OBJETOS.has(el.tagName) && fondo(el) === BLANCO)
    .filter((el) => {
      const s = getComputedStyle(el);
      return ['Top', 'Right', 'Bottom', 'Left'].some(
        (lado) => parseFloat(s[`border${lado}Width`]) >= 1 && s[`border${lado}Style`] !== 'none',
      );
    })
    .map((el) => el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).trim().split(/\s+/).join('.') : ''));

  const luminancia = (c) => {
    const [r, g, b] = c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number).map((v) => {
      v /= 255;
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contraste = (a, b) => {
    const [x, y] = [luminancia(a), luminancia(b)];
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  };
  const fondoEfectivo = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const c = fondo(n);
      if (opaco(c)) return c;
    }
    return BLANCO;
  };
  const bajos = [];
  for (const el of todos) {
    const conTexto = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!conTexto) continue;
    const s = getComputedStyle(el);
    const tam = parseFloat(s.fontSize);
    const grande = tam >= 24 || (tam >= 18.66 && parseInt(s.fontWeight, 10) >= 700);
    const ratio = contraste(s.color, fondoEfectivo(el));
    if (ratio < (grande ? 3 : 4.5)) {
      const texto = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
      bajos.push({ ratio: Math.round(ratio * 100) / 100, texto: texto.slice(0, 32), color: s.color, fondo: fondoEfectivo(el) });
    }
  }
  bajos.sort((a, b) => a.ratio - b.ratio);
  return { tinta: tinta.length, amarillo: amarilloPorPantalla, cajas, bajos };
}

(async () => {
  const navegador = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox'] });
  const contexto = await navegador.newContext({ viewport: { width: +ANCHO, height: +ALTO } });
  const pagina = await contexto.newPage();
  let fallos = 0;
  console.log(`${'página'.padEnd(14)} tinta amarillo cajas  <AA   (a ${ANCHO}×${ALTO})`);
  for (const [nombre, ruta] of paginas) {
    const respuesta = await pagina.goto(BASE + ruta, { waitUntil: 'networkidle' });
    await pagina.evaluate(() => document.fonts.ready);
    const m = await pagina.evaluate(medir);
    const mal = respuesta.status() !== 200 || m.tinta > 2 || m.amarillo > 1 || m.cajas.length || m.bajos.length;
    if (mal) fallos += 1;
    console.log(
      `${nombre.padEnd(14)} ${String(m.tinta).padStart(5)} ${String(m.amarillo).padStart(8)} ${String(m.cajas.length).padStart(5)} ${String(m.bajos.length).padStart(4)}`
        + (respuesta.status() !== 200 ? `   HTTP ${respuesta.status()}` : ''),
    );
    for (const caja of m.cajas.slice(0, 5)) console.log(`${''.padEnd(16)}caja: ${caja}`);
    for (const b of m.bajos.slice(0, 5)) console.log(`${''.padEnd(16)}${b.ratio}:1 «${b.texto}» ${b.color} sobre ${b.fondo}`);
  }
  await navegador.close();
  process.exit(fallos ? 1 : 0);
})();
