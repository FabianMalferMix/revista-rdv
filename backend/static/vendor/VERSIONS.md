# Dependencias JavaScript vendorizadas

Estas librerías se sirven **auto-hospedadas** (sin CDN) para que la CSP restrictiva
pueda limitar `script-src` a `'self'`. El precio es que quedan fuera del radar de todo
el utillaje de seguridad del proyecto: **ni Dependabot, ni pip-audit, ni trivy las ven**
(hallazgo S-31). Este archivo es el registro que sustituye a ese radar.

El radar es triple: `manifest.json` dice qué hay (paquete de npm, versión, integridad del
paquete y sha256 de cada archivo), `package.json` (que no se instala) deja que Dependabot avise
de cada versión nueva, y `tests/test_vendored_assets.py` falla si el árbol no es exactamente el
del manifiesto o si `package.json` pide otra versión.

## Al actualizar cualquiera de estas librerías

1. `python3 tools/vendor/update.py update <librería> <versión>` (desde la raíz del
   repositorio). Baja el paquete de npm, lo verifica contra su `dist.integrity`, pone sus
   archivos en su carpeta y reescribe `manifest.json` y `package.json`. La carpeta de TinyMCE
   lleva la versión (`tinymce-7.9.3/`): la URL cambia con ella, y ningún navegador sigue con
   la copia vieja.
2. Revisa el cambio y ejecuta la suite. Comprueba a mano el buscador en vivo (htmx) o el
   editor del panel (TinyMCE), según corresponda.
3. Si cambia la lista de archivos (un plugin nuevo en `richtext_init.js`), añádelos al
   manifiesto antes de correr el guion: la prueba exige que cada plugin pedido exista.

`python3 tools/vendor/update.py check` comprueba, sin cambiar nada, que lo vendorizado es lo
publicado en npm.

## Inventario

- **htmx** — `htmx/htmx.min.js`, del paquete `htmx.org` (`dist/htmx.min.js`). Un solo
  archivo. Se carga en todas las páginas (`base.html`) y mueve el buscador en vivo. Va con
  `includeIndicatorStyles: false` (la etiqueta `htmx-config` de `base.html`): por defecto mete
  sus estilos de indicador en un `<style>` en línea que la CSP bloquea. Esos estilos viven en
  `site.css`; al actualizar htmx, comprobar que la opción sigue existiendo y que la consola no
  avisa de la CSP.
- **TinyMCE** — `tinymce-<versión>/` (14 archivos del paquete `tinymce`: núcleo, tema, modelo,
  iconos, 3 plugins, pieles y licencias). Solo se carga en el panel editorial. La carpeta está
  **exenta del hash del manifiesto** de estáticos (`config/staticfiles.py`, que toma la
  versión de `manifest.json`) porque carga sus recursos con rutas relativas en tiempo de
  ejecución. Caddy no la marca como inmutable: la revalida en cada uso.

## Licencias

Ver [`../../../NOTICE.md`](../../../NOTICE.md). **TinyMCE 7.x es GPLv2-or-later**, lo que
tiene consecuencias para un repositorio que se declara propietario: está documentado
allí.

## Historial

- **2026-07-29** — htmx 2.0.3 → 2.0.10 (7 releases de parche, ~21 meses de retraso; sin
  CVE conocido en 2.0.3). Se crea este registro.
- **2026-11-03** — Sin cambio de versión. Lo vendorizado pasa a `manifest.json`, con el sha256
  de los 15 archivos, verificado contra los paquetes de npm; TinyMCE pasa a
  `tinymce-7.9.3/`, y Dependabot vigila `package.json`.
