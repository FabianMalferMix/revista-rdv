// Lo que comparten las herramientas de tools/ux/: la dirección del sitio que se mide, el
// Chrome con que se mide, las páginas de pages.txt y la fuente de titulares del sitio.
const fs = require('fs');
const path = require('path');

const DEFAULT_BASE = 'http://localhost:8000';

// La raíz del repositorio.
const REPO_ROOT = path.resolve(__dirname, '..', '..');

// El Chrome del sistema: playwright-core no descarga navegadores. CHROME, para otra ruta.
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';

// La dirección del sitio: la de la opción --base, en las herramientas que la aceptan (se les
// pasan sus argumentos), o la variable UX_BASE, o el sitio de desarrollo.
function siteBase(args = []) {
  const i = args.indexOf('--base');
  if (i < 0) return process.env.UX_BASE || DEFAULT_BASE;
  const base = args[i + 1];
  if (!base || base.startsWith('--')) {
    console.error('--base necesita una dirección: --base http://127.0.0.1:8000');
    process.exit(2);
  }
  return base;
}

// Las páginas de pages.txt, en su orden: una por línea, «nombre ruta [ancho]», donde «ancho»
// pide la captura a 1920 px. Las líneas en blanco y las que empiezan por # no cuentan.
function readPages() {
  return fs
    .readFileSync(path.join(__dirname, 'pages.txt'), 'utf8')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .map((line) => {
      const [name, route, wide] = line.split(/\s+/);
      return { name, route, wide: wide === 'ancho' };
    });
}

// La familia de titulares del sitio: la primera de la propiedad --display, leída en la página
// cargada. Las herramientas no la nombran, así que siguen a la hoja cuando la fuente cambia. Si
// la página no define --display, falla: sin ella no se sabe qué letra medir ni con cuál dibujar.
async function displayFamily(page) {
  const stack = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--display')
  );
  const family = stack.split(',')[0].replace(/["']/g, '').trim();
  if (!family) throw new Error(`${page.url()} no define --display: no se sabe cuál es la fuente de titulares`);
  return family;
}

module.exports = { CHROME, REPO_ROOT, displayFamily, readPages, siteBase };
