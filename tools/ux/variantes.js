#!/usr/bin/env node
// Variantes: la misma página con distintas versiones de una pieza, para que el dueño del
// sitio elija viéndolas. Cada variante es CSS (y, si hace falta, un poco de JS) que se
// inyecta en la página real; nada se escribe en el repositorio.
//
//   node tools/ux/variantes.js <dirSalida> <ancho> <alto> <ruta> <selector|ventana> nombre=archivo[+archivo…] …
//   node tools/ux/variantes.js tools/ux/out/cifras 951 900 / .hero hoy=- marcador=marcador.css
//
// · `nombre=-` captura la página tal como está: la referencia «hoy».
// · Un archivo `.css` se inyecta en la página; uno `.js` se ejecuta en ella antes del CSS
//   (sirve para quitar o poner una clase). Se combinan con `+`: `c=sin-banda.js+dos-col.css`.
// · `<selector>` recorta la captura a esa pieza, con 30 px de aire arriba y abajo;
//   `ventana` captura la pantalla que se ve al abrir la página.
// Escribe <nombre>.png en <dirSalida>. La CSP del sitio no admite estilos en línea: este
// navegador la desactiva (bypassCSP) solo para capturar; el sitio no cambia.
// Así se eligieron las cifras y el destacado de la portada tras el paso 13 del plan.

const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const [, , OUT, ANCHO, ALTO, RUTA, PIEZA, ...VARIANTES] = process.argv;
if (!OUT || !ANCHO || !ALTO || !RUTA || !PIEZA || !VARIANTES.length) {
  console.error('Uso: node tools/ux/variantes.js <dirSalida> <ancho> <alto> <ruta> <selector|ventana> nombre=archivo[+archivo…] …');
  process.exit(2);
}
const BASE = process.env.UX_BASE || 'http://localhost:8000';
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const navegador = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox'] });
  const contexto = await navegador.newContext({ viewport: { width: +ANCHO, height: +ALTO }, bypassCSP: true });
  const pagina = await contexto.newPage();
  let fallos = 0;
  for (const variante of VARIANTES) {
    const corte = variante.indexOf('=');
    const nombre = variante.slice(0, corte);
    const archivos = variante.slice(corte + 1) === '-' ? [] : variante.slice(corte + 1).split('+');
    const respuesta = await pagina.goto(BASE + RUTA, { waitUntil: 'networkidle' });
    for (const archivo of archivos.filter((a) => a.endsWith('.js'))) {
      await pagina.evaluate(fs.readFileSync(archivo, 'utf8'));
    }
    for (const archivo of archivos.filter((a) => a.endsWith('.css'))) {
      await pagina.addStyleTag({ content: fs.readFileSync(archivo, 'utf8') });
    }
    await pagina.evaluate(() => document.fonts.ready);
    await pagina.waitForTimeout(250);
    const destino = path.join(OUT, `${nombre}.png`);
    if (PIEZA === 'ventana') {
      await pagina.screenshot({ path: destino });
    } else {
      const caja = await pagina.evaluate((selector) => {
        const e = document.querySelector(selector);
        if (!e) return null;
        const r = e.getBoundingClientRect();
        return { x: 0, y: Math.max(0, r.top + scrollY - 30), width: innerWidth, height: r.height + 60 };
      }, PIEZA);
      if (!caja) {
        console.log(`${nombre}: no hay ningún «${PIEZA}» en ${RUTA}`);
        fallos += 1;
        continue;
      }
      await pagina.screenshot({ path: destino, clip: caja, fullPage: true });
    }
    if (respuesta.status() !== 200) fallos += 1;
    console.log(respuesta.status(), nombre, archivos.join(' + ') || '(tal como está)');
  }
  await navegador.close();
  process.exit(fallos ? 1 : 0);
})();
