#!/usr/bin/env node
// Prueba de humo en navegador: el sitio en Chrome a 951 px (la ventana del dueño) y a 375 px (un
// teléfono), con los guiones de backend/static/js/ ejecutándose de verdad. Una comprobación falla
// si lo que mide no se cumple, y también ante un error de página o de consola, un recurso propio
// que no carga o una petición a un tercero que nadie pidió. La corre el job `navegador` del CI.
//
//   node tools/ux/browser-smoke.js [--base URL]
//
// Usa playwright-core con el Chrome del sistema (variable CHROME para otra ruta) y las páginas
// de pages.txt, las mismas que mide capture.js. Sale con 1 si falla alguna comprobación.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : fallback;
};
const BASE = option('--base', process.env.UX_BASE || 'http://localhost:8000');
const ORIGIN = new URL(BASE).origin;
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';
// Objetivo pulsable de WCAG 2.5.5; el margen absorbe el redondeo de los subpíxeles.
const MIN_TARGET = 44 - 0.01;
// Lo que se espera tras cada comprobación, para que salgan los errores de las animaciones (la
// más larga, el giro del estante, dura 900 ms).
const SETTLE_MS = 1000;

const WINDOWS = {
  951: { viewport: { width: 951, height: 900 } },
  375: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};

const PAGES = fs
  .readFileSync(path.join(__dirname, 'pages.txt'), 'utf8')
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line && !line.startsWith('#'))
  .map((line) => line.split(/\s+/)[1]);

const routeOf = (url) => (url.startsWith(ORIGIN) ? url.slice(ORIGIN.length) : url);

// Una pestaña nueva por comprobación, que anota todo lo que cuenta como fallo.
async function openTab(browser, width) {
  const context = await browser.newContext(WINDOWS[width]);
  const page = await context.newPage();
  const problems = [];
  // Lo que va a un tercero: sin permiso es un fallo; con él (la persona pulsó), se anota aparte.
  const thirdParty = [];
  const allowed = new Set();
  const consented = [];
  const note = (text) => problems.push(`${routeOf(page.url())}: ${text}`);
  page.on('pageerror', (error) => note(`error de página: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') note(`consola: ${message.text()}`);
  });
  page.on('requestfailed', (request) => {
    // Al navegar, el navegador corta lo que quedaba por cargar de la página anterior.
    if (request.failure()?.errorText !== 'net::ERR_ABORTED') note(`no cargó ${routeOf(request.url())}`);
  });
  // Nada sale del sitio: lo que va a un tercero se anota y se responde vacío, sin red.
  await page.route('**/*', (route) => {
    const url = route.request().url();
    const origin = new URL(url).origin;
    if (origin === ORIGIN) return route.continue();
    (allowed.has(origin) ? consented : thirdParty).push(url);
    return route.fulfill({ status: 200, contentType: 'text/html', body: '' });
  });
  return { context, page, problems, thirdParty, allowed, consented };
}

async function visit(page, route) {
  const response = await page.goto(BASE + route, { waitUntil: 'load' });
  if (!response || response.status() !== 200) {
    throw new Error(`${route} respondió ${response ? response.status() : 'nada'}`);
  }
}

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

const CHECKS = [
  {
    name: 'Las páginas de pages.txt cargan sin errores y sin desbordar a lo ancho',
    widths: [951, 375],
    async run({ page }) {
      const overflowing = [];
      for (const route of PAGES) {
        await visit(page, route);
        const [scroll, client] = await page.evaluate(() => [
          document.documentElement.scrollWidth,
          document.documentElement.clientWidth,
        ]);
        if (scroll > client) overflowing.push(`${route} (${scroll} px en ${client})`);
      }
      expect(PAGES.length >= 10, `pages.txt solo tiene ${PAGES.length} páginas`);
      expect(!overflowing.length, `desbordan: ${overflowing.join(', ')}`);
    },
  },
  {
    name: 'Los controles de la cabecera miden 44 px o más (en el teléfono, con «Menú» abierto)',
    widths: [951, 375],
    async run({ page }, width) {
      await visit(page, '/registros/');
      if (width === 375) await page.click('.nav-disclosure summary');
      const controls = await page.evaluate(() =>
        [...document.querySelectorAll('.masthead a, .masthead summary, .masthead button')]
          .filter((el) => el.checkVisibility({ visibilityProperty: true }))
          .map((el) => ({
            label: (el.getAttribute('aria-label') || el.textContent).trim().replace(/\s+/g, ' '),
            height: el.getBoundingClientRect().height,
          }))
      );
      // Control: se midió la barra entera, no una cabecera vacía.
      expect(controls.length >= 8, `solo se ven ${controls.length} controles en la cabecera`);
      const small = controls.filter((c) => c.height < MIN_TARGET);
      expect(!small.length, `bajo 44 px: ${small.map((c) => `«${c.label}» ${c.height.toFixed(1)} px`).join(', ')}`);
    },
  },
  {
    name: '«Menú» abre el mapa del sitio y Escape lo cierra con el foco de vuelta',
    widths: [375],
    async run({ page }) {
      await visit(page, '/registros/');
      const menu = page.locator('.nav-disclosure');
      await menu.locator('summary').click();
      const links = await menu.evaluate((d) => [...d.querySelectorAll('a')].filter((a) => a.checkVisibility()).length);
      expect(links >= 5, `con «Menú» abierto se ven ${links} enlaces`);
      await page.keyboard.press('Escape');
      const [open, focusBack] = await menu.evaluate((d) => [d.open, document.activeElement === d.querySelector('summary')]);
      expect(!open, 'Escape no cierra el menú');
      expect(focusBack, 'al cerrar con Escape, el foco no vuelve a «Menú»');
    },
  },
  {
    name: 'La lupa abre el buscador con el foco en el campo, busca en vivo y Escape la cierra',
    widths: [951, 375],
    async run({ page }) {
      await visit(page, '/registros/');
      await page.click('.busqueda summary');
      // El evento `toggle` llega en una tarea posterior al clic: el foco se espera.
      const inField = await page
        .waitForFunction(() => document.activeElement.matches('.busqueda input[type="search"]'), null, { timeout: 2000 })
        .then(() => true, () => false);
      expect(inField, 'al abrir la lupa, el foco no va al campo');
      await page.keyboard.type('casa');
      const found = await page
        .waitForFunction(() => document.querySelector('#search-results a'), null, { timeout: 5000 })
        .then(() => true, () => false);
      expect(found, 'escribir «casa» no trae resultados al panel (htmx)');
      await page.keyboard.press('Escape');
      const [open, focusBack] = await page.evaluate(() => {
        const panel = document.querySelector('.busqueda');
        return [panel.open, document.activeElement === panel.querySelector('summary')];
      });
      expect(!open, 'Escape no cierra el buscador');
      expect(focusBack, 'al cerrar con Escape, el foco no vuelve a la lupa');
    },
  },
  {
    name: 'Al bajar, la cabecera pasa a la cápsula, y al volver arriba se recupera',
    widths: [951],
    async run({ page }) {
      await visit(page, '/registros/');
      const capsule = () => page.evaluate(() => document.documentElement.getAttribute('data-barra'));
      expect((await capsule()) === null, 'la página abre ya con la cápsula');
      await page.mouse.wheel(0, 800);
      const down = await page
        .waitForFunction(() => document.documentElement.getAttribute('data-barra') === 'pildora', null, { timeout: 3000 })
        .then(() => true, () => false);
      expect(down, 'al bajar no aparece la cápsula');
      await page.evaluate(() => window.scrollTo(0, 0));
      const up = await page
        .waitForFunction(() => !document.documentElement.hasAttribute('data-barra'), null, { timeout: 3000 })
        .then(() => true, () => false);
      expect(up, 'al volver arriba sigue la cápsula');
    },
  },
  {
    name: 'El estante saca otro libro al frente con el teclado',
    widths: [951, 375],
    async run({ page }) {
      await visit(page, '/');
      const shelf = page.locator('[data-estante]');
      const front = () =>
        shelf.evaluate((s) => [...s.querySelectorAll('.ejemplar')].findIndex((e) => e.classList.contains('es-frente')));
      const before = await front();
      const target = before === 0 ? 1 : 0;
      const spine = shelf.locator('.ejemplar').nth(target).locator('button.ejemplar-lomo');
      expect((await spine.count()) === 1, 'el lomo sigue siendo un enlace: estante.js no montó');
      await spine.focus();
      await page.keyboard.press('Enter');
      expect((await front()) === target, 'Enter sobre el lomo no saca ese libro al frente');
      await page.waitForTimeout(SETTLE_MS);
      const cards = await shelf.evaluate(
        (s, [now, then]) => {
          const all = [...s.querySelectorAll('.estante-ficha')];
          return {
            shown: !all[now].hidden,
            hidden: all[then].hidden,
            focus: document.activeElement === all[now].querySelector('.estante-titulo'),
          };
        },
        [target, before]
      );
      expect(cards.shown, 'la ficha del libro nuevo no se ve');
      expect(cards.hidden, 'la ficha del libro anterior sigue a la vista');
      expect(cards.focus, 'el foco no va al título de la ficha nueva');
    },
  },
  {
    name: 'La tirada responde a la hoja de contactos y a las flechas del teclado',
    widths: [951, 375],
    async run({ page }) {
      await visit(page, '/');
      const run = page.locator('[data-tirada]');
      expect(await run.evaluate((s) => s.classList.contains('con-js')), 'registros.js no montó la tirada');
      const current = () =>
        run.evaluate((s) => [...s.querySelectorAll('.pliego')].findIndex((p) => p.hasAttribute('aria-current')));
      expect((await current()) === 0, 'la tirada no abre con el primer registro arriba');
      const contact = run.locator('.tirada-contacto').nth(1);
      expect(await contact.evaluate((c) => c.checkVisibility()), 'la hoja de contactos no se ve');
      await contact.click();
      expect((await current()) === 1, 'pulsar el segundo contacto no sube ese registro');
      const [focused, announced] = await run.evaluate((s) => [
        document.activeElement === s.querySelectorAll('.pliego')[1].querySelector('.pliego-titulo a'),
        s.querySelector('[data-anuncio]').textContent,
      ]);
      expect(focused, 'el foco no va al título del registro elegido');
      expect(announced.startsWith('Registro 2 de '), `el anuncio dice «${announced}»`);
      await page.keyboard.press('ArrowRight');
      expect((await current()) === 2, 'la flecha derecha no pasa al registro siguiente');
      await page.keyboard.press('ArrowLeft');
      expect((await current()) === 1, 'la flecha izquierda no vuelve al anterior');
    },
  },
  {
    name: 'El reproductor externo solo se carga, y solo contacta al tercero, al pulsar',
    widths: [951, 375],
    async run({ page, thirdParty, allowed, consented }) {
      await visit(page, '/registros/');
      const recordings = await page.evaluate(() => [
        ...new Set([...document.querySelectorAll('a[href^="/registro/"]')].map((a) => a.getAttribute('href'))),
      ]);
      let player = null;
      for (const route of recordings) {
        await visit(page, route);
        const consent = page.locator('.player-consent');
        if (await consent.count()) {
          player = await consent.first().getAttribute('data-embed-src');
          break;
        }
      }
      expect(player, 'ningún registro tiene un reproductor externo con el que probar');
      expect((await page.locator('iframe').count()) === 0, 'hay un iframe antes de pulsar');
      expect(!thirdParty.length, `antes de pulsar ya se contactó a ${thirdParty[0]}`);
      // Desde aquí lo pide la persona: esas peticiones no cuentan como fallo.
      const host = new URL(player).origin;
      allowed.add(host);
      await page.click('.player-consent .embed-play');
      const loaded = await page
        .waitForSelector(`iframe[src="${player}"]`, { timeout: 3000 })
        .then(() => true, () => false);
      expect(loaded, 'pulsar no carga el reproductor');
      await page.waitForTimeout(SETTLE_MS);
      expect(consented.some((url) => url.startsWith(host)), `el reproductor no llegó a pedir ${host}`);
    },
  },
  {
    name: 'El dossier enseña su botón de imprimir y abre el diálogo de impresión',
    widths: [951],
    async run({ page }) {
      await page.addInitScript(() => {
        window.print = () => {
          window.printed = (window.printed || 0) + 1;
        };
      });
      await visit(page, '/dossier/');
      const button = page.locator('[data-print]');
      expect(await button.isVisible(), 'dossier.js no enseña el botón de imprimir');
      await button.click();
      expect((await page.evaluate(() => window.printed)) === 1, 'el botón no abre el diálogo de impresión');
    },
  },
];

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  let failures = 0;
  let total = 0;
  for (const check of CHECKS) {
    for (const width of check.widths) {
      total += 1;
      const tab = await openTab(browser, width);
      const problems = [];
      try {
        await check.run(tab, width);
        await tab.page.waitForTimeout(SETTLE_MS);
      } catch (error) {
        problems.push(error.message.split('\n')[0]);
      }
      problems.push(...tab.problems, ...tab.thirdParty.map((url) => `petición a un tercero: ${url}`));
      await tab.context.close();
      console.log(`${problems.length ? '✗' : '✓'} ${width} px · ${check.name}`);
      problems.forEach((problem) => console.log(`    ${problem}`));
      if (problems.length) failures += 1;
    }
  }
  await browser.close();
  console.log(`\n${total - failures} de ${total} comprobaciones en verde.`);
  process.exit(failures ? 1 : 0);
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
