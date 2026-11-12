#!/usr/bin/env node
// Prueba de humo en navegador: el sitio en Chrome a 951 px (la ventana del dueño) y a 375 px (un
// teléfono), y lo que pide cada imagen a 951 y a 390 px, con los guiones de backend/static/js/
// ejecutándose de verdad. Una comprobación falla si lo que mide no se cumple, y también ante un
// error de página o de consola, un recurso propio que no carga o una petición a un tercero que
// nadie pidió. La corre el job `navegador` del CI.
//
//   node tools/ux/browser-smoke.js [--base URL]
//
// Usa playwright-core con el Chrome del sistema (variable CHROME para otra ruta) y las páginas
// de pages.txt, las mismas que mide capture.js. Sale con 1 si falla alguna comprobación.
const { chromium } = require('playwright-core');
const { CHROME, readPages, siteBase } = require('./common');

const BASE = siteBase(process.argv.slice(2));
const ORIGIN = new URL(BASE).origin;
// Objetivo pulsable de WCAG 2.5.5; el margen absorbe el redondeo de los subpíxeles.
const MIN_TARGET = 44 - 0.01;
// Lo que se espera tras cada comprobación, para que salgan los errores de las animaciones (la
// más larga, el giro del estante, dura 900 ms).
const SETTLE_MS = 1000;

const WINDOWS = {
  951: { viewport: { width: 951, height: 900 } },
  390: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
  375: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};
// Lo que pide una imagen (`sizes`) vale si cae entre lo que mide su caja y lo que mide dibujada
// (con object-fit puede desbordarla), con un 5 % y 2 px de margen. El navegador elige la copia más
// cercana por encima de lo que pide, así que un 5 % solo cambia de copia cerca del límite entre
// dos; los 2 px son el redondeo de los subpíxeles en las imágenes de pocos píxeles.
const SIZES_MARGIN = 0.05;
const SIZES_SLACK = 2;

const PAGES = readPages().map((page) => page.route);
// Para lo que pide cada imagen, también lo que pages.txt no enseña: las tapas en la ficha de una
// editorial y el afiche de un registro de audio, en el carril de lectura.
const IMAGE_PAGES = [...PAGES, '/editorial/ediciones-ceniza/', '/registro/umbral-lectura/'];

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

// Un deslizamiento del dedo sobre lo que señala `locator`: hacia la izquierda si `dx` es negativo,
// y hacia abajo `dy` px. Los guiones solo miran el tipo de puntero (`pointerType`, otro que el
// dedo si se pide) y dónde empieza y termina el gesto.
const swipe = (locator, dx, { pointerType = 'touch', dy = 0 } = {}) =>
  locator.evaluate((element, [distance, drop, kind]) => {
    const box = element.getBoundingClientRect();
    const at = (x, y) => ({ pointerType: kind, isPrimary: true, bubbles: true, clientX: x, clientY: y });
    const middle = box.left + box.width / 2;
    const middleY = box.top + box.height / 2;
    element.dispatchEvent(new PointerEvent('pointerdown', at(middle - distance / 2, middleY - drop / 2)));
    element.dispatchEvent(new PointerEvent('pointerup', at(middle + distance / 2, middleY + drop / 2)));
  }, [dx, dy, pointerType]);

// El estante montado: cada lomo es un botón que dice una sola vez «Sacar al frente», y Enter sobre
// uno saca ese libro al frente.
async function expectMountedShelf(page, label) {
  const shelf = page.locator('[data-estante]');
  const actions = await shelf.locator('.ejemplar-lomo').evaluateAll((spines) =>
    spines.map((spine) =>
      spine.tagName === 'BUTTON'
        ? [...spine.querySelectorAll('.sr-only')].filter((s) => s.textContent.startsWith('Sacar al frente')).length
        : 0
    )
  );
  expect(
    actions.length >= 2 && actions.every((n) => n === 1),
    `${label}: los lomos dicen «Sacar al frente» ${actions.join(', ')} veces`
  );
  const front = () =>
    shelf.evaluate((s) => [...s.querySelectorAll('.ejemplar')].findIndex((e) => e.classList.contains('es-frente')));
  const target = (await front()) === 0 ? 1 : 0;
  await shelf.locator('.ejemplar').nth(target).locator('.ejemplar-lomo').focus();
  await page.keyboard.press('Enter');
  expect((await front()) === target, `${label}: Enter sobre el lomo no saca ese libro al frente`);
}

// Espera a que `condition` se cumpla, hasta `timeout` ms.
async function until(condition, timeout) {
  for (const end = Date.now() + timeout; Date.now() < end; await new Promise((done) => setTimeout(done, 100))) {
    if (await condition()) return true;
  }
  return false;
}

// Los retratos de «Las voces» que se ven, de izquierda a derecha, con su lugar en la lista
// (`index`). Las que esperan su turno quedan en la lista para el lector, fuera de la fila (1 px).
const portraitsInView = async (section) =>
  (
    await section.locator('.integrante').evaluateAll((cards) =>
      cards.map((li, index) => {
        const box = li.getBoundingClientRect();
        const shown = getComputedStyle(li).display !== 'none' && box.width > 1;
        return { index, shown, name: li.querySelector('.member-name').textContent, left: box.left, top: box.top };
      })
    )
  )
    .filter((card) => card.shown)
    .sort((a, b) => a.left - b.left);

// En la página: cada imagen con copias (`srcset` en `w`) que ocupa sitio, con lo que pide su
// `sizes` (o el de la <source> que elige su <picture>), lo que mide su caja sin transformar
// (`width` calculado: los pliegos de la tirada van girados) y lo que mide dibujada. `natural` es
// lo que pidió según Chrome, si ya cargó: el ancho de la imagen corregido por su densidad.
function measureImages() {
  // Las comas o los blancos de primer nivel: los de dentro de min() o calc() no parten.
  const split = (text, separator) => {
    const parts = [''];
    let depth = 0;
    for (const char of text) {
      if (char === '(') depth += 1;
      if (char === ')') depth -= 1;
      if (depth === 0 && (separator === ' ' ? /\s/.test(char) : char === separator)) parts.push('');
      else parts[parts.length - 1] += char;
    }
    return parts.map((part) => part.trim()).filter(Boolean);
  };
  const ruler = document.createElement('div');
  ruler.style.cssText = 'position:absolute; left:0; top:0; height:0; padding:0; border:0; visibility:hidden';
  document.body.append(ruler);
  const measure = (length) => {
    ruler.style.width = length;
    return ruler.getBoundingClientRect().width;
  };
  const requested = (sizes) => {
    for (const entry of split(sizes, ',')) {
      const words = split(entry, ' ');
      const length = words.pop();
      if (!words.length || matchMedia(words.join(' ')).matches) return measure(length);
    }
    return measure('100vw');
  };
  const px = (value) => parseFloat(value) || 0;
  const found = [];
  for (const img of document.querySelectorAll('img[srcset]')) {
    if (!img.getClientRects().length) continue;
    const picture = img.parentElement.tagName === 'PICTURE' ? img.parentElement : null;
    const sources = picture ? [...picture.querySelectorAll('source')] : [];
    const source = sources.find((s) => !s.media || matchMedia(s.media).matches) || img;
    if (!/\s\d+w(,|$)/.test(source.getAttribute('srcset'))) continue;
    const style = getComputedStyle(img);
    const border = style.boxSizing === 'border-box';
    const box = px(style.width) - (border ? px(style.paddingLeft) + px(style.paddingRight)
      + px(style.borderLeftWidth) + px(style.borderRightWidth) : 0);
    const height = px(style.height) - (border ? px(style.paddingTop) + px(style.paddingBottom)
      + px(style.borderTopWidth) + px(style.borderBottomWidth) : 0);
    // Lo que mide un píxel no se pinta: se oculta a la vista y no al lector (`sr-only`), como las
    // voces que esperan su relevo.
    if (box <= 1) continue;
    const [w, h] = [Number(source.getAttribute('width')), Number(source.getAttribute('height'))];
    const ratio = w > 0 && h > 0 ? w / h : img.naturalWidth / img.naturalHeight || box / height;
    let drawn = box;
    if (style.objectFit === 'cover') drawn = Math.max(box, height * ratio);
    if (style.objectFit === 'contain') drawn = Math.min(box, height * ratio);
    const holder = img.closest('[class]:not(.riso-duo)');
    found.push({
      name: holder ? `.${holder.className.split(' ')[0]}` : 'img',
      requested: requested(source.getAttribute('sizes') || '100vw'),
      box,
      drawn,
      natural: img.complete && img.naturalWidth ? img.naturalWidth : null,
    });
  }
  ruler.remove();
  return found;
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
    name: 'Cada imagen pide con su sizes el ancho al que se pinta',
    widths: [951, 390],
    async run({ page }) {
      const wrong = new Map();
      let measured = 0;
      let confirmed = 0;
      const round = (value) => Math.round(value);
      for (const route of IMAGE_PAGES) {
        await visit(page, route);
        await page.evaluate(() => document.fonts.ready);
        for (const image of await page.evaluate(measureImages)) {
          measured += 1;
          const problems = [];
          if (image.natural !== null) {
            confirmed += 1;
            // Si Chrome no pidió lo que lee esta prueba, la prueba no sabe leer ese `sizes`.
            if (Math.abs(image.natural - image.requested) > 1) {
              problems.push(`Chrome pidió ${image.natural} px y la prueba leyó ${round(image.requested)}`);
            }
          }
          const low = Math.min(image.box, image.drawn) * (1 - SIZES_MARGIN) - SIZES_SLACK;
          const high = Math.max(image.box, image.drawn) * (1 + SIZES_MARGIN) + SIZES_SLACK;
          if (image.requested < low || image.requested > high) {
            const drawn = round(image.drawn) === round(image.box) ? '' : ` (dibujada, ${round(image.drawn)})`;
            problems.push(`pide ${round(image.requested)} px y se pinta a ${round(image.box)}${drawn}`);
          }
          for (const problem of problems) {
            const key = `${route} ${image.name}: ${problem}`;
            wrong.set(key, (wrong.get(key) || 0) + 1);
          }
        }
      }
      // Control: hay imágenes que medir, y en las que ya cargaron Chrome dice lo mismo que la prueba.
      expect(measured >= IMAGE_PAGES.length && confirmed > 0, `solo se midieron ${measured} imágenes (${confirmed} cargadas)`);
      const listed = [...wrong].map(([key, count]) => (count > 1 ? `${key} (×${count})` : key));
      expect(!listed.length, `no piden lo que pintan: ${listed.join('; ')}`);
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
    name: 'Al tabular fuera de «Menú» abierto, el menú se cierra sin mover el foco y lo enfocado se ve',
    widths: [375],
    async run({ page }) {
      await visit(page, '/registros/');
      const menu = page.locator('.nav-disclosure');
      await menu.locator('summary').click();
      expect(await menu.evaluate((d) => d.open), '«Menú» no abre');
      // Dónde está el foco, y si lo que hay en su centro es él o lo tapa otra cosa.
      const focus = () =>
        page.evaluate(() => {
          const el = document.activeElement;
          const box = el.getBoundingClientRect();
          const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
          return {
            label: (el.getAttribute('aria-label') || el.textContent).trim().replace(/\s+/g, ' ').slice(0, 40),
            inMenu: !!el.closest('.nav-disclosure'),
            inPage: !!el.closest('main'),
            open: document.querySelector('.nav-disclosure').open,
            covered: !el.contains(hit),
          };
        });
      let state = await focus();
      for (let i = 0; i < 40 && state.inMenu; i += 1) {
        await page.keyboard.press('Tab');
        state = await focus();
      }
      expect(!state.inMenu, 'el tabulador no sale de «Menú»');
      // El guion mira adónde llegó el foco una vez terminado el cambio: el cierre llega después.
      await until(async () => !(await menu.evaluate((d) => d.open)), 1000);
      state = await focus();
      expect(!state.open, `con el foco en «${state.label}», «Menú» sigue abierto`);
      expect(state.label === 'Buscar', `al cerrarse, el foco no se queda en lo que sigue a «Menú» sino en «${state.label}»`);
      for (let i = 0; i < 10 && !state.inPage; i += 1) {
        await page.keyboard.press('Tab');
        state = await focus();
      }
      expect(state.inPage, 'el tabulador no llega a la página');
      expect(!state.covered, `«${state.label}» tiene el foco y queda tapado`);
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
    name: 'La lupa no busca con una letra y anuncia una sola vez cuántos resultados hay, sin leerlos',
    widths: [951, 375],
    async run({ page }) {
      await visit(page, '/registros/');
      const searches = [];
      page.on('request', (request) => {
        if (request.url().includes('/buscar/')) searches.push(request.url());
      });
      await page.click('.busqueda summary');
      await page.waitForFunction(() => document.activeElement.matches('.busqueda input[type="search"]'), null, { timeout: 2000 });
      // Lo que oye el lector: cada texto nuevo de la región de estado de la lupa.
      await page.evaluate(() => {
        const status = document.querySelector('.busqueda [role="status"]');
        window.announced = [];
        new MutationObserver(() => {
          const text = status.textContent.trim();
          if (text) window.announced.push(text);
        }).observe(status, { childList: true, characterData: true, subtree: true });
      });
      await page.keyboard.type('c');
      await page.waitForTimeout(SETTLE_MS);
      expect(!searches.length, 'con una sola letra, la lupa busca igual');
      await page.keyboard.type('asa');
      const found = await page
        .waitForFunction(() => document.querySelector('#search-results a'), null, { timeout: 5000 })
        .then(() => true, () => false);
      expect(found, 'escribir «casa» no trae resultados al panel (htmx)');
      await page.waitForTimeout(SETTLE_MS);
      const [announced, live] = await page.evaluate(() => [
        window.announced,
        !!document.querySelector('#search-results').closest('[aria-live], [role="status"], [role="alert"], [role="log"]'),
      ]);
      expect(!live, 'los resultados van en una región viva: el lector los lee enteros en cada pausa');
      expect(
        announced.length === 1 && /^\d+ resultados? para “casa”$/.test(announced[0]),
        `la lupa anunció ${JSON.stringify(announced)}`
      );
      // Al borrar hasta dejar una letra, se va lo que ya no corresponde a lo escrito.
      for (let i = 0; i < 3; i += 1) await page.keyboard.press('Backspace');
      await page.waitForTimeout(SETTLE_MS);
      const left = await page.evaluate(() =>
        ['#search-results', '.busqueda [role="status"]'].map((s) => document.querySelector(s).textContent.trim()).join('')
      );
      expect(!left, `con una letra queda «${left.slice(0, 60)}»`);
      expect(searches.length === 1, `la lupa buscó ${searches.length} veces`);
    },
  },
  {
    name: 'Un correo que el sitio no acepta vuelve a su campo, con lo escrito, el error al lado y el foco',
    widths: [951, 375],
    async run({ page }) {
      await visit(page, '/textos/');
      const field = page.locator('footer input[name="email"]');
      // «ana@correo» lo acepta el navegador (no pide punto en el dominio) y Django no.
      await field.fill('ana@correo');
      await Promise.all([page.waitForURL('**/novedades/'), field.press('Enter')]);
      const state = await page.evaluate(() => {
        const input = document.activeElement;
        const error = document.getElementById(`${input.id}_error`);
        const [a, b] = [input, error].map((e) => e && e.getBoundingClientRect());
        const hit = a && document.elementFromPoint(a.left + a.width / 2, a.top + a.height / 2);
        return {
          focused: input.name,
          value: input.value,
          fields: document.querySelectorAll('input[name="email"]').length,
          error: error ? error.textContent.trim() : null,
          near: !!(a && b) && b.top >= a.top && b.top - a.bottom < 80,
          covered: !input.contains(hit),
        };
      });
      expect(state.focused === 'email', `el foco está en «${state.focused}», no en el correo`);
      expect(state.value === 'ana@correo', `el campo trae «${state.value}»`);
      expect(state.fields === 1, `la página tiene ${state.fields} campos de correo`);
      expect(state.error === 'Revisa el correo ingresado.', `el error dice «${state.error}»`);
      expect(state.near, 'el error no está junto al campo');
      expect(!state.covered, 'el campo con el foco queda tapado');
    },
  },
  {
    name: 'Los campos trampa de los formularios no se ven',
    widths: [951, 375],
    async run({ page }) {
      for (const route of ['/textos/', '/enviar/']) {
        await visit(page, route);
        const traps = await page.locator('input[name="apodo"]').evaluateAll((inputs) =>
          inputs.map((input) => input.checkVisibility({ opacityProperty: true }))
        );
        expect(traps.length > 0, `${route}: no hay campo trampa que medir`);
        expect(!traps.some(Boolean), `${route}: el campo trampa se ve`);
      }
    },
  },
  {
    name: 'Al bajar, la cabecera pasa a la cápsula, y al volver arriba se recupera',
    widths: [951],
    async run({ page }) {
      await visit(page, '/registros/');
      const capsule = () => page.evaluate(() => document.documentElement.getAttribute('data-barra'));
      expect((await capsule()) === 'arriba', `la página abre con data-barra=${await capsule()}`);
      await page.mouse.wheel(0, 800);
      const down = await page
        .waitForFunction(() => document.documentElement.getAttribute('data-barra') === 'pildora', null, { timeout: 3000 })
        .then(() => true, () => false);
      expect(down, 'al bajar no aparece la cápsula');
      await page.evaluate(() => window.scrollTo(0, 0));
      const up = await page
        .waitForFunction(() => document.documentElement.getAttribute('data-barra') === 'arriba', null, { timeout: 3000 })
        .then(() => true, () => false);
      expect(up, 'al volver arriba sigue la cápsula');
    },
  },
  {
    name: 'La portada se reconoce por su marca: arriba no tiene cabecera y la cápsula llega sin transición de vista',
    widths: [951],
    async run({ page }) {
      // Las transiciones de vista que pide cabecera.js, contadas: solo las pide fuera de la portada,
      // donde la cápsula llega con la hoja de estilos.
      await page.addInitScript(() => {
        window.viewTransitions = 0;
        const start = Document.prototype.startViewTransition;
        if (!start) return;
        Document.prototype.startViewTransition = function (...args) {
          window.viewTransitions += 1;
          return start.apply(this, args);
        };
      });
      for (const [route, home] of [['/', true], ['/registros/', false]]) {
        await visit(page, route);
        await page.waitForTimeout(SETTLE_MS);
        const shown = await page.evaluate(() => getComputedStyle(document.querySelector('.masthead-fila')).opacity === '1');
        expect(shown !== home, home ? 'arriba de la portada se ve la cabecera' : `arriba de ${route} no se ve la cabecera`);
        await page.mouse.wheel(0, 800);
        const down = await page
          .waitForFunction(() => document.documentElement.getAttribute('data-barra') === 'pildora', null, { timeout: 3000 })
          .then(() => true, () => false);
        expect(down, `${route}: al bajar no aparece la cápsula`);
        const animated = (await page.evaluate(() => window.viewTransitions)) > 0;
        expect(animated !== home, home ? 'en la portada la cápsula llega con una transición de vista' : `en ${route} la cápsula llega sin transición de vista`);
      }
    },
  },
  {
    name: 'Arriba de la portada, la cápsula que se abre con el teclado busca con el mismo ancho que al bajar',
    widths: [951, 375],
    async run({ page }) {
      // Lo que miden la cápsula, el campo y los resultados mientras se busca «casa», con la lupa
      // abierta desde el teclado: arriba de la portada la cápsula está escondida y aparece al
      // recibir el foco. El foco va directo a la lupa: tabular desde el principio pasaría por
      // «Saltar al contenido», que devuelve la página arriba.
      const measure = async (scrolled) => {
        await visit(page, '/');
        if (scrolled) {
          await page.mouse.wheel(0, 800);
          await page.waitForFunction(() => document.documentElement.getAttribute('data-barra') === 'pildora', null, { timeout: 3000 });
        }
        await page.focus('.busqueda summary');
        await page.keyboard.press('Enter');
        await page.waitForFunction(() => document.activeElement.matches('.busqueda input[type="search"]'), null, { timeout: 2000 });
        await page.keyboard.type('casa');
        await page.waitForFunction(() => document.querySelector('#search-results a'), null, { timeout: 5000 });
        await page.waitForTimeout(SETTLE_MS);
        return page.evaluate(() =>
          ['.masthead-fila', '.busqueda input[type="search"]', '#search-results'].map((s) =>
            Math.round(document.querySelector(s).getBoundingClientRect().width)
          )
        );
      };
      const down = await measure(true);
      const up = await measure(false);
      expect(
        up.every((width, i) => width === down[i]),
        `la cápsula, el campo y los resultados miden ${up.join(', ')} px arriba de la portada y ${down.join(', ')} px al bajar`
      );
    },
  },
  {
    name: 'Sin cada guion de la portada o sin lo que comparten, sin un nodo que necesita o si falla al montarse, la página sigue siendo usable',
    widths: [951, 375],
    async run({ context }, width) {
      // Cada caso, en una pestaña aparte: el fallo es el que se provoca, no uno que anotar. Un
      // guion roto se sirve con un error justo después de lo que tiene que deshacer, y a la
      // portada sin un nodo se le quita en el HTML: el guion sale sin tocar nada y sin errores.
      const portada = async (script, { broken = null, html = null } = {}) => {
        const tab = await context.browser().newContext(WINDOWS[width]);
        const page = await tab.newPage();
        const errors = [];
        page.on('pageerror', (error) => errors.push(error.message));
        const edit = async (route, [from, to], label) => {
          const response = await route.fetch();
          const original = await response.text();
          const body = original.split(from).join(to);
          expect(body !== original, `${label}: no está «${from}»`);
          return route.fulfill({ response, body });
        };
        await page.route(`**/js/${script}*.js*`, (route) => {
          if (html) return route.continue();
          if (!broken) return route.abort();
          return edit(route, [broken, `${broken}\nthrow new Error('montaje roto');`], script);
        });
        if (html) await page.route(BASE + '/', (route) => edit(route, html, 'la portada'));
        await visit(page, '/');
        const unexpected = () => errors.filter((message) => !(broken && message.includes('montaje roto')));
        return { tab, page, unexpected };
      };
      const header = (page) => page.evaluate(() => {
        const row = document.querySelector('.masthead-fila').getBoundingClientRect();
        return {
          marked: document.documentElement.hasAttribute('data-barra'),
          shown: getComputedStyle(document.querySelector('.masthead-fila')).opacity === '1',
          inView: row.height > 0 && row.top >= 0 && row.bottom <= window.innerHeight,
        };
      });
      // La cabecera clásica, arriba y al bajar: sin la marca data-barra, y a la vista.
      const expectHeader = async (page, label) => {
        for (const y of [0, 2500]) {
          await page.evaluate((top) => window.scrollTo(0, top), y);
          await page.waitForTimeout(SETTLE_MS);
          const state = await header(page);
          expect(!state.marked, `${label}: queda la marca data-barra`);
          expect(state.shown && state.inView, `${label}: a ${y} px no se ve la cabecera clásica`);
        }
      };
      // La tirada en una fila, sin la hoja de contactos y con cada título enlazado.
      const expectRun = async (page, label) => {
        const run = await page.locator('[data-tirada]').evaluate((s) => {
          const sheets = [...s.querySelectorAll('.pliego')].map((p) => p.getBoundingClientRect());
          return {
            js: s.classList.contains('con-js'),
            contacts: s.querySelector('.tirada-contactos').hidden,
            current: s.querySelectorAll('[aria-current]').length,
            row: sheets.every((r, i) => i === 0 || r.left >= sheets[i - 1].right - 1),
            links: [...s.querySelectorAll('.pliego-titulo a')].every((a) => a.href && a.checkVisibility()),
          };
        });
        expect(!run.js && run.contacts && !run.current, `${label}: la tirada queda a medio montar`);
        expect(run.row && run.links, `${label}: la tirada no queda en una fila con sus títulos enlazados`);
      };
      // «Las voces» como sin su guion: a la vista, las que dice la portada, cada una con su enlace.
      const expectVoices = async (page, label) => {
        const voices = await page.locator('[data-integrantes]').evaluate((s) => {
          const phone = window.matchMedia(s.dataset.telefono).matches;
          const shown = [...s.querySelectorAll('.integrante')]
            .filter((li) => li.checkVisibility() && li.getBoundingClientRect().width > 1);
          return {
            js: s.classList.contains('con-js'),
            shown: shown.length,
            expected: Number(phone ? s.dataset.aLaVistaTelefono : s.dataset.aLaVista),
            links: shown.every((li) => li.querySelector('a')?.href),
          };
        });
        expect(
          !voices.js && voices.expected > 0 && voices.shown === voices.expected && voices.links,
          `${label}: «Las voces» no quedan como sin su guion (se ven ${voices.shown} de ${voices.expected})`
        );
      };
      // Cada lomo del estante lleva a su ficha. Al pulsar uno se sale de la portada: va al final.
      const expectShelf = async (page, label) => {
        const spines = page.locator('[data-estante] .ejemplar-lomo');
        const hrefs = await spines.evaluateAll((links) => links.map((a) => a.getAttribute('href')));
        expect(hrefs.length >= 2 && new Set(hrefs).size === hrefs.length, `${label}: los lomos no llevan cada uno a su ficha`);
        await Promise.all([page.waitForURL(BASE + hrefs[1]), spines.nth(1).click()]);
      };
      for (const broken of [null, 'document.body.insertBefore(centinela, document.body.firstChild);']) {
        const label = broken ? 'cabecera.js roto' : 'sin cabecera.js';
        const { tab, page, unexpected } = await portada('cabecera', { broken });
        try {
          await expectHeader(page, label);
          expect(!unexpected().length, `${label}: ${unexpected().join(' | ')}`);
        } finally {
          await tab.close();
        }
      }
      const tirada = [
        ['sin registros.js', {}],
        ['registros.js roto', { broken: 'hoja.hidden = false;' }],
        ['la tirada sin su región de anuncios', { html: [' data-anuncio>', '>'] }],
      ];
      for (const [label, options] of tirada) {
        const { tab, page, unexpected } = await portada('registros', options);
        try {
          await expectRun(page, label);
          expect(!unexpected().length, `${label}: ${unexpected().join(' | ')}`);
        } finally {
          await tab.close();
        }
      }
      const estante = [
        ['sin estante.js', {}],
        ['el estante sin los id de sus fichas', { html: ['class="estante-ficha" id=', 'class="estante-ficha" data-id='] }],
      ];
      for (const [label, options] of estante) {
        const { tab, page, unexpected } = await portada('estante', options);
        try {
          expect(!unexpected().length, `${label}: ${unexpected().join(' | ')}`);
          await expectShelf(page, label);
        } finally {
          await tab.close();
        }
      }
      // Sin lo que comparten los guiones (common.js), o si falla antes de dejarlo en
      // `window.common`, cada guion deja su componente como sin JavaScript: todos a la vez.
      const common = [
        ['sin common.js', {}],
        ['common.js roto', { broken: "const canAnimate = () => !quieto.matches && typeof Element.prototype.animate === 'function';" }],
      ];
      for (const [label, options] of common) {
        const { tab, page, unexpected } = await portada('common', options);
        try {
          await expectRun(page, label);
          await expectVoices(page, label);
          await expectHeader(page, label);
          expect(!unexpected().length, `${label}: ${unexpected().join(' | ')}`);
          await expectShelf(page, label);
        } finally {
          await tab.close();
        }
      }
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
    name: 'La tirada responde a la hoja de contactos, al teclado y al dedo, y solo anuncia lo que no mueve el foco',
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
      // El lector ya lee el título al que llega el foco: la región viva no lo repite.
      expect(!announced, `al pulsar un contacto, además de llevar el foco al título, se anuncia «${announced}»`);
      await page.keyboard.press('ArrowRight');
      expect((await current()) === 2, 'la flecha derecha no pasa al registro siguiente');
      await page.keyboard.press('ArrowLeft');
      expect((await current()) === 1, 'la flecha izquierda no vuelve al anterior');
      // Deslizar no mueve el foco: eso sí se anuncia.
      const track = run.locator('.tirada-pista');
      await swipe(track, -160);
      expect((await current()) === 2, 'deslizar hacia la izquierda no pasa al registro siguiente');
      const said = await run.evaluate((s) => s.querySelector('[data-anuncio]').textContent);
      expect(said.startsWith('Registro 3 de '), `al deslizar se anuncia «${said}»`);
      // Solo cuenta el gesto del dedo o del lápiz, de 40 px o más y claramente horizontal: con el
      // ratón, uno corto o uno casi vertical (que baja la página) no pasan de registro.
      for (const [gesture, dx, options] of [
        ['con el ratón', -160, { pointerType: 'mouse' }],
        ['de 20 px', -20, {}],
        ['casi vertical', -60, { dy: 50 }],
      ]) {
        await swipe(track, dx, options);
        expect((await current()) === 2, `un deslizamiento ${gesture} pasa de registro`);
      }
      // Un deslizamiento no abre lo que quedó debajo: el clic que le sigue se corta, y no sube el
      // pliego que toca. Pasado el gesto, pulsar un pliego de abajo sí lo sube.
      const tapBelow = () =>
        run.evaluate((s) => {
          const sheets = [...s.querySelectorAll('.pliego')];
          const before = sheets.findIndex((p) => p.hasAttribute('aria-current'));
          const below = sheets.findIndex((p) => !p.hasAttribute('aria-current'));
          const click = new MouseEvent('click', { bubbles: true, cancelable: true });
          const cut = !sheets[below].dispatchEvent(click);
          return { before, below, cut, after: sheets.findIndex((p) => p.hasAttribute('aria-current')) };
        });
      await swipe(track, 160);
      const early = await tapBelow();
      expect(early.before === 1, 'deslizar hacia la derecha no vuelve al registro anterior');
      expect(early.cut && early.after === 1, 'el clic que sigue a un deslizamiento sube el pliego que toca');
      await page.waitForTimeout(500);
      const late = await tapBelow();
      expect(!late.cut && late.after === late.below, 'pasado el gesto, pulsar un pliego de abajo no lo sube');
    },
  },
  {
    name: 'Montar otra vez la portada no duplica las escuchas: un gesto o una tecla, un solo efecto',
    widths: [951, 375],
    async run({ page }, width) {
      await visit(page, '/');
      // Otra pasada por cada camino de montaje: lo que llega con htmx (htmx:load, sobre toda la
      // página) y los tres guiones, cargados otra vez.
      const again = await page.evaluate(() => {
        window.htmx.trigger(document.body, 'htmx:load');
        const scripts = [...document.querySelectorAll('script[src]')]
          .filter((script) => /\/js\/(registros|integrantes|estante)\./.test(script.src));
        const load = (old) =>
          new Promise((done, fail) => {
            const script = document.createElement('script');
            script.src = old.src;
            script.onload = done;
            script.onerror = () => fail(new Error(`no cargó ${old.src}`));
            document.head.append(script);
          });
        return Promise.all(scripts.map(load)).then(() => scripts.length);
      });
      expect(again === 3, `la portada carga ${again} de los tres guiones que se montan`);
      // La tirada: un deslizamiento pasa un solo registro y se anuncia una sola vez.
      const run = page.locator('[data-tirada]');
      const current = () =>
        run.evaluate((s) => [...s.querySelectorAll('.pliego')].findIndex((p) => p.hasAttribute('aria-current')));
      await run.evaluate((s) => {
        window.anuncios = 0;
        new MutationObserver((records) => {
          window.anuncios += records.length;
        }).observe(s.querySelector('[data-anuncio]'), { childList: true, characterData: true, subtree: true });
      });
      const before = await current();
      await swipe(run.locator('.tirada-pista'), -160);
      await page.waitForTimeout(100);
      const [after, said] = [await current(), await page.evaluate(() => window.anuncios)];
      expect(after === before + 1, `un deslizamiento pasa del registro ${before + 1} al ${after + 1}`);
      expect(said === 1, `un deslizamiento se anuncia ${said} veces`);
      // «Las voces», en el teléfono (en la pantalla ancha llegan solas): un deslizamiento trae a
      // una a cada lugar, cada una bajo su pasada de tinta. Se cuentan en el mismo instante: cada
      // relevo pone su capa al empezar.
      if (width === 375) {
        const voices = await page.locator('[data-integrantes] .integrantes-retratos').evaluate((list) => {
          const box = list.getBoundingClientRect();
          const at = (x) => ({ pointerType: 'touch', isPrimary: true, bubbles: true, clientX: x, clientY: box.top + box.height / 2 });
          list.dispatchEvent(new PointerEvent('pointerdown', at(box.left + box.width / 2 + 80)));
          list.dispatchEvent(new PointerEvent('pointerup', at(box.left + box.width / 2 - 80)));
          return {
            inks: list.querySelectorAll('.integrante-tinta').length,
            places: [...list.children].filter((li) => !li.classList.contains('sr-only')).length,
          };
        });
        expect(
          voices.places > 0 && voices.inks === voices.places,
          `un deslizamiento pone ${voices.inks} pasadas de tinta en ${voices.places} lugares`
        );
      }
      await expectMountedShelf(page, 'montado otra vez');
    },
  },
  {
    name: 'Lo que llega con htmx se monta: un estante nuevo saca libros al frente con el teclado',
    widths: [951],
    async run({ page }) {
      await visit(page, '/');
      // El estante, otra vez del servidor, en lugar del que está: llega sin montar.
      await page.evaluate(() => {
        window.estanteViejo = document.querySelector('[data-estante]');
        return window.htmx.ajax('GET', '/', { target: '[data-estante]', select: '[data-estante]', swap: 'outerHTML' });
      });
      const arrived = await until(
        () =>
          page.evaluate(() => {
            const shelf = document.querySelector('[data-estante]');
            return shelf !== window.estanteViejo && !!shelf.querySelector('button.ejemplar-lomo');
          }),
        3000
      );
      expect(arrived, 'el estante que llega con htmx queda sin montar: sus lomos siguen siendo enlaces');
      await expectMountedShelf(page, 'el estante que llega con htmx');
    },
  },
  {
    name: 'Con «reducir movimiento» nada se anima, y la tirada, el estante, «Las voces» y la cabecera cambian igual',
    widths: [951, 375],
    async run({ page }, width) {
      // Lo que piden los guiones en cada página, contado: animaciones (las transiciones y los
      // @keyframes de la hoja son otra cosa) y transiciones de vista.
      await page.addInitScript(() => {
        window.moved = 0;
        window.viewTransitions = 0;
        const animate = Element.prototype.animate;
        Element.prototype.animate = function (...args) {
          window.moved += 1;
          return animate.apply(this, args);
        };
        const start = Document.prototype.startViewTransition;
        if (!start) return;
        Document.prototype.startViewTransition = function (...args) {
          window.viewTransitions += 1;
          return start.apply(this, args);
        };
      });
      const counted = () => page.evaluate(() => ({ moved: window.moved, transitions: window.viewTransitions }));
      // Sin la preferencia, lo mismo se anima: es el control de que se cuenta lo que hay que contar.
      for (const reducedMotion of ['no-preference', 'reduce']) {
        const still = reducedMotion === 'reduce';
        const label = still ? 'con «reducir movimiento»' : 'sin «reducir movimiento»';
        await page.emulateMedia({ reducedMotion });
        await visit(page, '/');
        const run = page.locator('[data-tirada]');
        const current = () =>
          run.evaluate((s) => [...s.querySelectorAll('.pliego')].findIndex((p) => p.hasAttribute('aria-current')));
        const before = await current();
        await swipe(run.locator('.tirada-pista'), -160);
        expect((await current()) === before + 1, `${label}, deslizar no pasa de registro`);
        await expectMountedShelf(page, label);
        // «Las voces», en el teléfono, cambian con el dedo (en la pantalla ancha, solas y solo sin
        // la preferencia); sin animar, el relevo es inmediato.
        if (width === 375) {
          const voices = page.locator('[data-integrantes] .integrantes-retratos');
          const shown = () =>
            voices.evaluate((list) =>
              [...list.querySelectorAll('.integrante')]
                .filter((li) => li.checkVisibility() && li.getBoundingClientRect().width > 1)
                .map((li) => li.querySelector('a').getAttribute('href'))
                .join(' ')
            );
          const first = await shown();
          await swipe(voices, -160);
          if (still) expect((await shown()) !== first, `${label}, deslizar sobre «Las voces» no trae a otras`);
        }
        const home = await counted();
        expect(still ? home.moved === 0 : home.moved > 0, `${label}, en la portada los guiones piden ${home.moved} animaciones`);
        // La cabecera pasa a la cápsula con una transición de vista fuera de la portada.
        if (width === 951) {
          await visit(page, '/registros/');
          await page.waitForTimeout(SETTLE_MS);
          await page.mouse.wheel(0, 800);
          const down = await page
            .waitForFunction(() => document.documentElement.getAttribute('data-barra') === 'pildora', null, { timeout: 3000 })
            .then(() => true, () => false);
          expect(down, `${label}, al bajar no aparece la cápsula`);
          const { transitions } = await counted();
          expect(still ? transitions === 0 : transitions > 0, `${label}, la cápsula llega con ${transitions} transiciones de vista`);
        }
      }
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
  {
    name: 'Las voces enseñan en una fila las que dice la portada, con el guion y sin él',
    widths: [951, 375],
    async run({ page, context }, width) {
      // Cuántas se ven lo deciden A_LA_VISTA y A_LA_VISTA_TELEFONO en Python, que llegan en los
      // atributos data- de la sección con el corte del teléfono: ni la hoja ni el guion repiten
      // el número.
      const expectRow = async (tab, label) => {
        await visit(tab, '/');
        const row = await tab.evaluate(() => {
          const section = document.querySelector('[data-integrantes]');
          const phone = window.matchMedia(section.dataset.telefono).matches;
          const shown = [...section.querySelectorAll('.integrante')]
            .filter((li) => getComputedStyle(li).display !== 'none')
            .map((li) => li.getBoundingClientRect())
            .filter((box) => box.width > 1);
          return {
            expected: Number(phone ? section.dataset.aLaVistaTelefono : section.dataset.aLaVista),
            shown: shown.length,
            columns: new Set(shown.map((r) => Math.round(r.left))).size,
            oneRow: shown.every((r) => r.top < shown[0].bottom && r.bottom > shown[0].top),
            width: shown.length ? Math.round(shown[0].width) : 0,
          };
        });
        expect(row.expected > 0, `${label}: la sección no dice cuántas se ven`);
        expect(row.shown === row.expected, `${label}: se ven ${row.shown} y la portada dice ${row.expected}`);
        expect(row.columns === row.shown && row.oneRow, `${label}: las que se ven no van en una fila`);
        return row.width;
      };
      const withScript = await expectRow(page, 'con el guion');
      const noScripts = await context.browser().newContext({ ...WINDOWS[width], javaScriptEnabled: false });
      try {
        const bare = await expectRow(await noScripts.newPage(), 'sin el guion');
        // Las que esperan no le quitan sitio a la fila: cada retrato mide lo mismo que sin el guion.
        expect(withScript === bare, `con el guion, cada retrato mide ${withScript} px; sin él, ${bare}`);
      } finally {
        await noScripts.close();
      }
    },
  },
  {
    name: '«Las voces»: el relevo solo cambia lo que se ve, y el lector recibe la lista entera y quieta',
    widths: [951, 375],
    async run({ page }, width) {
      await visit(page, '/');
      const section = page.locator('[data-integrantes]');
      await section.scrollIntoViewIfNeeded();
      const look = async () => {
        const row = await portraitsInView(section);
        return {
          names: row.map((card) => card.name),
          lefts: row.map((card) => Math.round(card.left)),
          tops: row.map((card) => Math.round(card.top)),
        };
      };
      const tree = () => section.locator('.integrantes-retratos').ariaSnapshot();
      const roster = await section.locator('.member-name').allTextContents();
      const before = await look();
      const treeBefore = await tree();
      // En la pantalla ancha llega sola cada 1,8 s; en el teléfono, al deslizar el dedo.
      if (width === 375) await swipe(section.locator('.integrantes-retratos'), -160);
      const moved = await until(async () => (await look()).names.join() !== before.names.join(), 5000);
      expect(moved, 'en 5 s no llega ninguna otra integrante');
      await page.waitForTimeout(SETTLE_MS);
      const after = await look();
      const items = (treeBefore.match(/- listitem/g) || []).length;
      expect(items === roster.length, `el lector recibe ${items} de las ${roster.length} integrantes`);
      expect((await tree()) === treeBefore, 'el relevo cambia lo que recibe el lector de pantalla');
      expect(after.lefts.join() === before.lefts.join(), 'el relevo mueve los lugares de la fila');
      const pairsLower = (tops) => tops.every((top, i) => i % 2 === 0 || top > tops[i - 1]);
      expect(pairsLower(before.tops) && pairsLower(after.tops), 'los pares de la fila no van más abajo');
      // Llega la que más esperaba, al lugar de la que se va, y las demás no se mueven.
      const arrived = after.names.filter((name) => !before.names.includes(name));
      const waiting = roster.filter((name) => !before.names.includes(name));
      expect(
        arrived.length && arrived.every((name) => waiting.slice(0, arrived.length).includes(name)),
        `llegan ${arrived.join(', ')}, y las que más esperaban eran ${waiting.slice(0, arrived.length).join(', ')}`
      );
      expect(
        after.names.every((name, i) => name === before.names[i] || arrived.includes(name)),
        `la fila pasa de ${before.names.join(', ')} a ${after.names.join(', ')}: alguna cambió de lugar`
      );
    },
  },
  {
    name: 'El tabulador recorre «Las voces» en el orden en que se ven, también después del relevo',
    widths: [951],
    async run({ page }) {
      await visit(page, '/');
      const section = page.locator('[data-integrantes]');
      await section.scrollIntoViewIfNeeded();
      // Tras el primer relevo, la fila ya no va en el orden de la lista.
      const scrambled = await until(
        async () => (await portraitsInView(section)).some((card, i, row) => i && card.index < row[i - 1].index),
        5000
      );
      expect(scrambled, 'en 5 s ningún relevo cambia el orden de la fila: no hay nada que medir');
      // Con el foco dentro, el relevo se detiene: la fila queda quieta mientras se tabula.
      await section.locator('.integrantes-cta a').focus();
      await page.waitForTimeout(SETTLE_MS);
      const row = (await portraitsInView(section)).map((card) => card.name);
      const focused = () =>
        page.evaluate(() => {
          const el = document.activeElement;
          return {
            name: el.closest('.integrante')?.querySelector('.member-name').textContent ?? null,
            below: !!(document.querySelector('[data-integrantes]').compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING),
          };
        });
      const visited = [];
      for (let i = 0; i < row.length; i += 1) {
        await page.keyboard.press('Tab');
        visited.push((await focused()).name);
      }
      expect(visited.join() === row.join(), `el tabulador va por ${visited.join(', ')}, y la fila es ${row.join(', ')}`);
      await page.keyboard.press('Tab');
      const out = await focused();
      expect(!out.name && out.below, 'desde el último retrato, el tabulador no sale de la fila hacia lo que sigue');
      await page.keyboard.press('Shift+Tab');
      const back = await focused();
      expect(back.name === row[row.length - 1], `volviendo desde abajo, el tabulador entra por ${back.name}`);
    },
  },
  {
    name: 'Toda la tarjeta lleva a su ficha, y los demás enlaces de la tarjeta, a lo suyo',
    widths: [951, 375],
    async run({ page }) {
      // Adónde lleva pulsar en el centro de cada pieza de la primera tarjeta que tiene todas: el
      // enlace que recibe el pulsado, o nada. Una pieza que dibuja un seudoelemento («.x::before»)
      // no tiene nodo propio: su caja es la que el navegador le resuelve dentro de su elemento.
      const landings = (card, pieces) =>
        page.evaluate(
          ([card, pieces]) => {
            const found = document.querySelector(card);
            if (!found) return null;
            found.scrollIntoView({ block: 'center' });
            const own = found.querySelector('.enlace-total')?.getAttribute('href') ?? 'sin enlace-total';
            const measured = Object.entries(pieces).map(([piece, selector]) => {
              const [element, pseudo] = selector.split(/(?=::)/);
              const node = found.querySelector(element);
              const box = node.getBoundingClientRect();
              if (!pseudo) return { piece, node, x: box.left + box.width / 2, y: box.top + box.height / 2 };
              const drawn = getComputedStyle(node, pseudo);
              const x = box.left + parseFloat(drawn.left) + parseFloat(drawn.width) / 2;
              const y = box.top + parseFloat(drawn.top) + parseFloat(drawn.height) / 2;
              return { piece, node, x, y };
            });
            const at = measured.map(({ piece, x, y }) => [piece, document.elementFromPoint(x, y)?.closest('a')?.getAttribute('href') ?? null]);
            const links = measured.map(({ piece, node }) => [piece, node.closest('a')?.getAttribute('href') ?? own]);
            return { at: Object.fromEntries(at), links: Object.fromEntries(links) };
          },
          [card, pieces]
        );
      // Una fila de texto con sección, firma y miniatura: la sección y la firma llevan a lo suyo;
      // la fecha y la miniatura, que no son enlaces, al texto.
      await visit(page, '/textos/');
      const fila = await landings('.fila:has(.kicker a):has(.fila-pie a):has(.fila-miniatura)', {
        sección: '.kicker a',
        firma: '.fila-pie a',
        fecha: '.fila-fecha',
        miniatura: '.fila-miniatura',
      });
      expect(fila, '/textos/: no hay una fila con sección, firma y miniatura que medir');
      expect(JSON.stringify(fila.at) === JSON.stringify(fila.links), `/textos/: la fila lleva a ${JSON.stringify(fila.at)} y debía llevar a ${JSON.stringify(fila.links)}`);
      // Una tarjeta de registro con su evento: el evento lleva al evento; la miniatura y la marca ▶
      // de su esquina, que va por encima de la capa del enlace, al registro.
      await visit(page, '/registros/');
      const tarjeta = await landings('.recording-card:has(.meta a)', {
        evento: '.meta a',
        miniatura: '.rec-miniatura',
        marca: '.rec-miniatura::before',
      });
      expect(tarjeta, '/registros/: no hay una tarjeta con evento que medir');
      expect(JSON.stringify(tarjeta.at) === JSON.stringify(tarjeta.links), `/registros/: la tarjeta lleva a ${JSON.stringify(tarjeta.at)} y debía llevar a ${JSON.stringify(tarjeta.links)}`);
    },
  },
  {
    name: 'Lo que lleva hidden no se ve, con los guiones y sin ellos',
    widths: [951, 375],
    async run({ page, context }, width) {
      // Se mide cada elemento con el atributo: si un `display` del autor le gana a `hidden`, se ve.
      // `components` son los que tienen que estar entre los medidos, para que no pase en vacío.
      const expectHidden = async (tab, route, components) => {
        await visit(tab, route);
        const shown = await tab.evaluate(() =>
          [...document.querySelectorAll('[hidden]')]
            .filter((e) => getComputedStyle(e).display !== 'none')
            .map((e) => e.className || e.tagName)
        );
        expect(!shown.length, `${route}: se ven aunque llevan hidden: ${shown.join(', ')}`);
        for (const selector of components) {
          const count = await tab.locator(`${selector}[hidden]`).count();
          expect(count > 0, `${route}: no hay ningún ${selector} oculto que medir`);
        }
      };
      // Con los guiones: las fichas del estante que no están al frente. Las voces que esperan
      // turno ya no llevan hidden: quedan en la lista para el lector, fuera de la fila.
      await expectHidden(page, '/', ['.estante-ficha']);
      // Sin ellos: la hoja de contactos de la tirada, las voces que esperan y el botón de
      // imprimir del dossier.
      const noScripts = await context.browser().newContext({ ...WINDOWS[width], javaScriptEnabled: false });
      try {
        const bare = await noScripts.newPage();
        await expectHidden(bare, '/', ['.tirada-contactos', '.integrante']);
        await expectHidden(bare, '/dossier/', ['[data-print]']);
      } finally {
        await noScripts.close();
      }
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
