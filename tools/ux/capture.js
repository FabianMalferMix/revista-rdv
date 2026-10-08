#!/usr/bin/env node
// Capturas y métricas computadas del sitio local. Ver README.md.
//
//   node tools/ux/capture.js <dirSalida> [--base URL] [--only a,b] [--sin-capturas]
//
// Por cada página de pages.txt y cada viewport (d1440, m390 y, si la página lleva
// «ancho», w1920) escribe <nombre>-<viewport>-view.png, -full.png y -metrics.json.
// Usa playwright-core con el Chrome del sistema: no descarga navegadores.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
if (!args[0] || args[0].startsWith('--')) {
  console.error('Uso: node tools/ux/capture.js <dirSalida> [--base URL] [--only a,b] [--sin-capturas]');
  process.exit(2);
}
const OUT = args[0];
const opt = (nombre, porDefecto) => {
  const i = args.indexOf(nombre);
  return i >= 0 ? args[i + 1] : porDefecto;
};
const BASE = opt('--base', process.env.UX_BASE || 'http://localhost:8000');
const ONLY = (opt('--only', '') || '').split(',').filter(Boolean);
const CAPTURAS = !args.includes('--sin-capturas');
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';

const PAGINAS = fs
  .readFileSync(path.join(__dirname, 'pages.txt'), 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith('#'))
  .map((l) => {
    const [nombre, ruta, ancho] = l.split(/\s+/);
    return { nombre, ruta, ancho: ancho === 'ancho' };
  })
  .filter((p) => !ONLY.length || ONLY.includes(p.nombre));

const UA_MOVIL =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const VIEWPORTS = [
  { id: 'd1440', ancho: 1440, alto: 900, escala: 1, movil: false, todas: true },
  { id: 'w1920', ancho: 1920, alto: 1080, escala: 1, movil: false, todas: false },
  { id: 'm390', ancho: 390, alto: 844, escala: 2, movil: true, todas: true },
];

// Se ejecuta DENTRO de la página.
const METRICAS = () => {
  const cs = (el) => getComputedStyle(el);
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = cs(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const familia = (el) => cs(el).fontFamily.split(',')[0].replace(/["']/g, '').trim();
  const tipo = (f) => (/mono|menlo|consolas|courier/i.test(f) ? 'mono' : /syne/i.test(f) ? 'display' : 'lectura');
  const describir = (sel) => {
    const el = [...document.querySelectorAll(sel)].find((e) => visible(e) && (e.innerText || '').trim());
    if (!el) return null;
    const s = cs(el);
    return {
      texto: el.innerText.trim().replace(/\s+/g, ' ').slice(0, 70),
      familia: familia(el),
      px: parseFloat(s.fontSize),
      peso: s.fontWeight,
      interlinea: s.lineHeight,
      mayus: s.textTransform === 'uppercase',
      ancho: Math.round(el.getBoundingClientRect().width),
    };
  };

  // Extensión horizontal del texto y elementos con texto propio.
  let minL = Infinity;
  let maxR = -Infinity;
  const conTexto = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const nodo = walker.currentNode;
    if (!nodo.nodeValue.trim()) continue;
    const el = nodo.parentElement;
    if (!el || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName)) continue;
    const s = cs(el);
    if (s.visibility === 'hidden' || s.display === 'none') continue;
    // Texto solo para lectores de pantalla (caja de 1 px) o transparente: no se ve.
    const caja = el.getBoundingClientRect();
    if (caja.width <= 1 || caja.height <= 1 || parseFloat(s.opacity) === 0) continue;
    const rango = document.createRange();
    rango.selectNodeContents(nodo);
    const r = rango.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    // Recorte: lo que un ancestro con overflow oculto deja fuera tampoco se ve
    // (las tarjetas de la cinta que aún no han entrado, por ejemplo).
    let izq = r.left;
    let der = r.right;
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const sa = cs(a);
      if (sa.overflowX !== 'visible') {
        const ra = a.getBoundingClientRect();
        izq = Math.max(izq, ra.left);
        der = Math.min(der, ra.right);
      }
    }
    if (der - izq <= 1) continue;
    conTexto.add(el);
    const arriba = r.top + scrollY;
    if (s.position === 'fixed' || arriba < 0 || arriba > 3000 || izq < 0 || der > innerWidth) continue;
    minL = Math.min(minL, izq);
    maxR = Math.max(maxR, der);
  }
  const porTipo = { mono: 0, display: 0, lectura: 0 };
  let mayusculas = 0;
  let bajo12 = 0;
  for (const el of conTexto) {
    const s = cs(el);
    porTipo[tipo(familia(el))] += 1;
    if (s.textTransform === 'uppercase') mayusculas += 1;
    if (parseFloat(s.fontSize) < 12) bajo12 += 1;
  }

  // Imágenes: ¿la caja respeta la proporción que el CSS o el archivo piden?
  const imagenes = [...document.querySelectorAll('img')]
    .filter((e) => visible(e) && e.getBoundingClientRect().width > 40)
    .map((e) => {
      const r = e.getBoundingClientRect();
      const s = cs(e);
      const caja = r.width / r.height;
      const natural = e.naturalWidth && e.naturalHeight ? e.naturalWidth / e.naturalHeight : null;
      const m = /^(\d*\.?\d+)\s*\/\s*(\d*\.?\d+)$/.exec(s.aspectRatio.trim());
      const pedida = m ? parseFloat(m[1]) / parseFloat(m[2]) : null;
      let desvio = false;
      if (pedida) desvio = Math.abs(caja / pedida - 1) > 0.02;
      else if (natural && s.objectFit === 'fill') desvio = Math.abs(caja / natural - 1) > 0.02;
      return {
        clase: (e.className || '').toString().split(/\s+/)[0] || e.parentElement.className || 'img',
        ancho: Math.round(r.width),
        alto: Math.round(r.height),
        natural: e.naturalWidth + 'x' + e.naturalHeight,
        ajuste: s.objectFit,
        arriba: Math.round(r.top + scrollY),
        desvio,
      };
    });

  // Objetivos pulsables.
  const objetivos = [...document.querySelectorAll('a, button, summary, select, textarea, label[for], input:not([type=hidden])')]
    .filter(visible)
    .map((e) => e.getBoundingClientRect());

  // Caracteres por línea: la línea más larga del primer párrafo con dos líneas o más.
  const cpl = (sel) => {
    for (const el of document.querySelectorAll(sel)) {
      if (!visible(el)) continue;
      const nodo = [...el.childNodes].find((n) => n.nodeType === 3 && n.nodeValue.trim().length > 40);
      if (!nodo) continue;
      const texto = nodo.nodeValue;
      const lineas = new Map();
      const rango = document.createRange();
      for (let i = 0; i < Math.min(texto.length, 1500); i += 1) {
        rango.setStart(nodo, i);
        rango.setEnd(nodo, i + 1);
        const rect = rango.getClientRects()[0];
        if (!rect) continue;
        const y = Math.round(rect.top);
        lineas.set(y, (lineas.get(y) || 0) + 1);
      }
      if (lineas.size >= 2) return Math.max(...lineas.values());
    }
    return null;
  };

  const cabecera = document.querySelector('header.masthead, header, [role=banner]');
  return {
    titulo: document.title,
    viewport: [innerWidth, innerHeight],
    altoPagina: document.documentElement.scrollHeight,
    desbordeHorizontal: document.documentElement.scrollWidth > innerWidth + 1,
    cuerpoPx: parseFloat(cs(document.body).fontSize),
    h1: describir('h1'),
    h2: describir('main h2'),
    h3: describir('main h3'),
    parrafo: describir('main p'),
    nav: describir('nav a'),
    boton: describir('.btn, button'),
    texto: {
      ancho: Math.round(maxR - minL),
      razon: +((maxR - minL) / innerWidth).toFixed(2),
      elementos: conTexto.size,
      porTipo,
      mayusculas,
      bajo12,
    },
    cpl: { articulo: cpl('.article .body p'), bajada: cpl('.dek'), manifiesto: cpl('.hero-manifesto') },
    imagenes: {
      total: imagenes.length,
      enPrimerViewport: imagenes.filter((i) => i.arriba < innerHeight && i.ancho > 80 && i.alto > 80).length,
      desviadas: imagenes.filter((i) => i.desvio).length,
      muestra: imagenes.slice(0, 30),
    },
    objetivos: {
      total: objetivos.length,
      bajo24: objetivos.filter((r) => r.height < 24 || r.width < 24).length,
      bajo44: objetivos.filter((r) => r.height < 44).length,
    },
    cabecera: cabecera
      ? { alto: Math.round(cabecera.getBoundingClientRect().height), posicion: cs(cabecera).position }
      : null,
  };
};

async function recorrer(page, alto) {
  const total = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < Math.min(total, 20000); y += Math.round(alto * 0.8)) {
    await page.evaluate((v) => window.scrollTo(0, v), y);
    await page.waitForTimeout(40);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--disable-gpu'] });
  let fallos = 0;
  for (const vp of VIEWPORTS) {
    const paginas = PAGINAS.filter((p) => vp.todas || p.ancho);
    if (!paginas.length) continue;
    const contexto = await browser.newContext({
      viewport: { width: vp.ancho, height: vp.alto },
      deviceScaleFactor: vp.escala,
      isMobile: vp.movil,
      hasTouch: vp.movil,
      locale: 'es-CL',
      ...(vp.movil ? { userAgent: UA_MOVIL } : {}),
    });
    const page = await contexto.newPage();
    for (const p of paginas) {
      const etiqueta = `${p.nombre}-${vp.id}`;
      try {
        const respuesta = await page.goto(BASE + p.ruta, { waitUntil: 'networkidle', timeout: 45000 });
        await recorrer(page, vp.alto);
        const metricas = await page.evaluate(METRICAS);
        metricas.ruta = p.ruta;
        metricas.estado = respuesta ? respuesta.status() : null;
        if (CAPTURAS) {
          await page.screenshot({ path: path.join(OUT, `${etiqueta}-view.png`) });
          await page.screenshot({ path: path.join(OUT, `${etiqueta}-full.png`), fullPage: true });
        }
        if (vp.movil) {
          // El suelo de reflow de WCAG 1.4.10: a 320 px no debe haber scroll horizontal.
          await page.setViewportSize({ width: 320, height: 700 });
          metricas.desborde320 = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
          await page.setViewportSize({ width: vp.ancho, height: vp.alto });
        }
        fs.writeFileSync(path.join(OUT, `${etiqueta}-metrics.json`), JSON.stringify(metricas, null, 1));
        console.log('OK   ', etiqueta, metricas.estado, 'alto', metricas.altoPagina);
      } catch (e) {
        fallos += 1;
        console.error('FALLO', etiqueta, String(e.message).slice(0, 160));
      }
    }
    await contexto.close();
  }
  await browser.close();
  process.exit(fallos ? 1 : 0);
})();
