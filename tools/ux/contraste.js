#!/usr/bin/env node
// Contraste en el navegador: axe-core, solo con su regla de contraste de color (WCAG 1.4.3, AA),
// sobre cada página de pages.txt a 951 px (la ventana del dueño) y a 375 px (un teléfono). La
// prueba de paleta (backend/tests/test_contraste_paleta.py) calcula los pares desde el CSS; esto
// mide lo que de verdad queda pintado, con los fondos heredados, los tamaños y los pesos de letra.
// La corre el job `navegador` del CI, después de la prueba de humo.
//
//   node tools/ux/contraste.js [--base URL]
//
// Sale con 1 si axe encuentra algún texto bajo el mínimo, o si una página no responde 200 o no
// le da nada que medir. Lo que axe deja «por revisar» (texto sobre una imagen o un degradado,
// letras sueltas) no cuenta como fallo. Se mide con «reducir movimiento», para que ninguna
// animación deje un texto a medio pintar.
const { chromium } = require('playwright-core');
const fs = require('fs');
const { CHROME, readPages, siteBase } = require('./common');

const BASE = siteBase(process.argv.slice(2));
// El guion de axe se evalúa por el protocolo del navegador: la CSP del sitio no admite scripts en
// línea, y así la página se mide con su CSP puesta.
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

const WINDOWS = {
  951: { viewport: { width: 951, height: 900 } },
  375: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};

const PAGES = readPages().map((page) => page.route);

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const failures = [];
  let measured = 0;
  for (const [width, device] of Object.entries(WINDOWS)) {
    const context = await browser.newContext({ ...device, reducedMotion: 'reduce' });
    const page = await context.newPage();
    for (const route of PAGES) {
      const response = await page.goto(BASE + route, { waitUntil: 'load' });
      if (!response || response.status() !== 200) {
        failures.push(`${width} px ${route}: respondió ${response ? response.status() : 'nada'}`);
        continue;
      }
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(AXE);
      const result = await page.evaluate(() =>
        window.axe.run(document, { runOnly: { type: 'rule', values: ['color-contrast'] } })
      );
      const passed = result.passes.reduce((sum, rule) => sum + rule.nodes.length, 0);
      if (!passed) failures.push(`${width} px ${route}: axe no encontró ningún texto que medir`);
      measured += passed;
      for (const node of result.violations.flatMap((rule) => rule.nodes)) {
        const data = node.any[0]?.data || {};
        failures.push(
          `${width} px ${route}: ${node.target.join(' ')} — ${data.fgColor} sobre ${data.bgColor} da ` +
            `${data.contrastRatio}:1 y pide ${data.expectedContrastRatio} (${data.fontSize}, ${data.fontWeight})`
        );
      }
    }
    await context.close();
  }
  await browser.close();
  failures.forEach((failure) => console.log(`✗ ${failure}`));
  const pages = PAGES.length * Object.keys(WINDOWS).length;
  console.log(`\n${pages} páginas medidas, ${measured} textos con contraste suficiente, ${failures.length} problemas.`);
  process.exit(failures.length ? 1 : 0);
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
