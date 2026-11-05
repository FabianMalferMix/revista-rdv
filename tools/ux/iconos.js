#!/usr/bin/env node
// Iconos del colectivo: el de la pestaña, el de la pantalla del teléfono y la tarjeta que
// aparece al compartir un enlace. Se dibujan con la fuente de titulares del sitio, la primera
// familia de la propiedad --display, que se lee en la página: el SVG se pinta dentro de una
// página del sitio de desarrollo, que sirve esa fuente, y se fotografía. Si la fuente no carga,
// se detiene antes de escribir nada: el icono saldría en la letra de reserva.
//
//   node tools/ux/iconos.js
//
// Escribe:
//   backend/static/img/icono-32.png    pestaña (esquinas redondeadas, fondo transparente)
//   backend/static/img/icono-180.png   pantalla de inicio del teléfono (cuadrado entero: el
//                                      teléfono redondea; con transparencia, el iPhone pone negro)
//   backend/static/img/favicon.ico     16, 32 y 48 px, para quien pide /favicon.ico
//   tools/ux/out/tarjeta-para-compartir.png   1200 × 630: se sube desde el panel como
//                                      «imagen para compartir» (og_image) del perfil del sitio
//
// Necesita el sitio arriba en UX_BASE (http://localhost:8000) y Pillow en python3 para el .ico.
// Los SVG viven aquí y no en static/: la hoja no admite archivos .svg (test_security_csp).
// Diseño elegido por el dueño del sitio tras el paso 17: «RdV» en blanco sobre el magenta
// del sello (icono) y el sello a toda la tarjeta, con el monograma RV (tarjeta).

const { chromium } = require('playwright-core');
const { execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { CHROME, displayFamily, siteBase } = require('./common');

const BASE = siteBase();
const RAIZ = path.resolve(__dirname, '..', '..');
const IMG = path.join(RAIZ, 'backend', 'static', 'img');
const OUT = path.join(__dirname, 'out');

const MAGENTA = '#b8086b';
const CELESTE = '#9cc3ea';
const letra = (familia) => `font-family="'${familia}'" font-weight="700"`;

// «RdV» ajustado al ancho del cuadrado (textLength), sea cual sea la letra: en negrita, una de
// titulares ancha no deja a su ancho natural margen para las tres letras.
const icono = (familia, lado, radio) => `<svg xmlns="http://www.w3.org/2000/svg" width="${lado}" height="${lado}" viewBox="0 0 40 40">
  <rect width="40" height="40" rx="${radio}" fill="${MAGENTA}"/>
  <text ${letra(familia)} x="4" y="27" fill="#fff" textLength="32" lengthAdjust="spacingAndGlyphs"><tspan font-size="17">R</tspan><tspan font-size="13">d</tspan><tspan font-size="17">V</tspan></text>
</svg>`;

const tarjeta = (familia, nombre, lema) => {
  const [primera, ...resto] = nombre.split(' ');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="${MAGENTA}"/>
  <text ${letra(familia)} fill="#fff" x="80" y="290" font-size="92">${primera}</text>
  <text ${letra(familia)} fill="#fff" x="80" y="392" font-size="92">${resto.join(' ')}</text>
  <text ${letra(familia)} fill="${CELESTE}" x="84" y="470" font-size="34">${lema}</text>
  <text ${letra(familia)} fill="#fff" x="770" y="470" font-size="300">R</text>
  <text ${letra(familia)} fill="${CELESTE}" x="935" y="490" font-size="300">V</text>
</svg>`;
};

(async () => {
  fs.mkdirSync(IMG, { recursive: true });
  fs.mkdirSync(OUT, { recursive: true });
  const navegador = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox'] });
  const pagina = await (await navegador.newContext({ viewport: { width: 1300, height: 800 }, bypassCSP: true })).newPage();
  await pagina.goto(BASE + '/', { waitUntil: 'networkidle' });
  const familia = await displayFamily(pagina);
  // El nombre sin el monograma: `.brand` lleva dentro el SVG del «RV».
  const nombre = await pagina.evaluate(() =>
    (document.querySelector('.brand-nombre') || document.querySelector('.brand')).textContent.trim()
  );
  const lema = await pagina.evaluate(() => document.querySelector('.hero-tagline')?.textContent.trim() || 'Colectivo de poesía');

  const fotografiar = async (svg, destino) => {
    // Sin el papel del sitio detrás: las esquinas redondeadas del icono quedan transparentes.
    await pagina.evaluate((s) => {
      document.documentElement.style.background = 'transparent';
      document.body.style.background = 'transparent';
      document.body.innerHTML = '<div id="lienzo-icono" style="display:inline-block; line-height:0">' + s + '</div>';
    }, svg);
    // `document.fonts.check` da por buena una familia que ninguna @font-face sirve (no hay nada
    // que esperar): `load` devuelve las caras que cargó, y ninguna quiere decir letra de reserva.
    const caras = await pagina.evaluate((f) => document.fonts.load(`700 20px "${f}"`).then((c) => c.length), familia);
    if (!caras) throw new Error(`La fuente de titulares del sitio («${familia}») no cargó: el icono saldría en otra letra.`);
    await pagina.evaluate(() => document.fonts.ready);
    await pagina.locator('#lienzo-icono svg').screenshot({ path: destino, omitBackground: true });
    console.log('escrito', path.relative(RAIZ, destino));
  };

  await fotografiar(icono(familia, 32, 6), path.join(IMG, 'icono-32.png'));
  await fotografiar(icono(familia, 180, 0), path.join(IMG, 'icono-180.png'));
  const grande = path.join(OUT, 'icono-64.png');
  await fotografiar(icono(familia, 64, 6), grande);
  await fotografiar(tarjeta(familia, nombre, lema), path.join(OUT, 'tarjeta-para-compartir.png'));
  await navegador.close();

  // El .ico lleva 16, 32 y 48 px, reducidos del de 64 con Pillow.
  const ico = path.join(IMG, 'favicon.ico');
  execFileSync('python3', ['-c', `from PIL import Image
Image.open(${JSON.stringify(grande)}).save(${JSON.stringify(ico)}, sizes=[(16, 16), (32, 32), (48, 48)])`]);
  console.log('escrito', path.relative(RAIZ, ico));
})();
