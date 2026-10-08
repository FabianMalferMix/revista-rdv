#!/usr/bin/env node
// Capturas sueltas, a cualquier ancho y de cualquier ruta, con aviso de scroll horizontal.
//
//   node tools/ux/ver.js <dirSalida> <ancho> <alto> nombre=ruta [nombre=ruta …]
//   node tools/ux/ver.js tools/ux/out/prueba 768 900 poemas=/poemas/ seccion=/seccion/resenas/
//
// capture.js mide las páginas de pages.txt a 1440, 390 y 1920. Esto es para lo demás: un
// ancho intermedio (768, 1024), una ruta que no está en la lista, una comprobación rápida.
// Escribe <nombre>-<ancho>.png (página entera) y, por cada ruta, una línea con el estado
// HTTP, el alto y la palabra DESBORDA si la página tiene scroll horizontal. Sale con
// código 1 si alguna desborda o no responde 200.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const [, , OUT, ANCHO, ALTO, ...PARES] = process.argv;
if (!OUT || !ANCHO || !ALTO || !PARES.length) {
  console.error('Uso: node tools/ux/ver.js <dirSalida> <ancho> <alto> nombre=ruta [nombre=ruta …]');
  process.exit(2);
}
const BASE = process.env.UX_BASE || 'http://localhost:8000';
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const navegador = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox'] });
  const contexto = await navegador.newContext({
    viewport: { width: +ANCHO, height: +ALTO },
    deviceScaleFactor: +ANCHO < 500 ? 2 : 1,
  });
  const pagina = await contexto.newPage();
  let fallos = 0;
  for (const par of PARES) {
    const corte = par.indexOf('=');
    const nombre = par.slice(0, corte);
    const ruta = par.slice(corte + 1);
    const respuesta = await pagina.goto(BASE + ruta, { waitUntil: 'networkidle' });
    await pagina.evaluate(() => document.fonts.ready);
    // Recorrer la página: las imágenes con loading="lazy" no cargan hasta que se ven.
    const total = await pagina.evaluate(() => document.documentElement.scrollHeight);
    for (let y = 0; y < total; y += 600) {
      await pagina.evaluate((v) => window.scrollTo(0, v), y);
      await pagina.waitForTimeout(60);
    }
    await pagina.evaluate(() => window.scrollTo(0, 0));
    await pagina.waitForTimeout(150);
    const desborda = await pagina.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    await pagina.screenshot({ path: path.join(OUT, `${nombre}-${ANCHO}.png`), fullPage: true });
    if (desborda || respuesta.status() !== 200) fallos += 1;
    console.log(respuesta.status(), nombre, 'alto', total, desborda ? 'DESBORDA' : '');
  }
  await navegador.close();
  process.exit(fallos ? 1 : 0);
})();
