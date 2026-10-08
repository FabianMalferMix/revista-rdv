#!/usr/bin/env node
// Hoja de contactos: varias capturas reducidas en una sola imagen, para revisarlas de un
// vistazo antes de abrir ninguna.
//
//   node tools/ux/hoja.js <dirCapturas> <salida.png> <sufijo> <anchoCelda> <columnas> nombre [nombre …]
//   node tools/ux/hoja.js tools/ux/out/prueba tools/ux/out/prueba/hoja.png -d1440-full.png 620 3 home poemas textos
//
// <sufijo> es lo que sigue al nombre de página en el archivo: «-d1440-full.png»,
// «-m390-view.png» (capture.js) o «-768.png» (ver.js).
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const [, , DIR, OUT, SUFIJO, ANCHO, COLUMNAS, ...NOMBRES] = process.argv;
if (!DIR || !OUT || !SUFIJO || !ANCHO || !COLUMNAS || !NOMBRES.length) {
  console.error('Uso: node tools/ux/hoja.js <dirCapturas> <salida.png> <sufijo> <anchoCelda> <columnas> nombre [nombre …]');
  process.exit(2);
}
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';

(async () => {
  const celdas = NOMBRES.map(
    (n) => `<figure><img src="file://${path.resolve(DIR, n + SUFIJO)}"><figcaption>${n}</figcaption></figure>`
  ).join('');
  const html = `<!doctype html><meta charset="utf-8"><style>
    body{margin:0;padding:10px;background:#333;font:12px sans-serif;color:#fff}
    .g{display:grid;grid-template-columns:repeat(${COLUMNAS},${ANCHO}px);gap:10px;align-items:start}
    figure{margin:0}img{width:${ANCHO}px;display:block;background:#fff}figcaption{padding:3px 0}
  </style><div class="g">${celdas}</div>`;
  const temporal = path.join(path.dirname(path.resolve(OUT)), '.hoja.html');
  fs.mkdirSync(path.dirname(temporal), { recursive: true });
  fs.writeFileSync(temporal, html);
  const navegador = await chromium.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--allow-file-access-from-files'],
  });
  const pagina = await navegador.newPage({ viewport: { width: COLUMNAS * (+ANCHO + 10) + 10, height: 800 } });
  await pagina.goto('file://' + temporal);
  await pagina.waitForTimeout(500);
  await pagina.screenshot({ path: OUT, fullPage: true });
  await navegador.close();
  fs.unlinkSync(temporal);
})();
