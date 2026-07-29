# Dependencias JavaScript vendorizadas

Estas librerías se sirven **auto-hospedadas** (sin CDN) para que la CSP restrictiva
pueda limitar `script-src` a `'self'`. El precio es que quedan fuera del radar de todo
el utillaje de seguridad del proyecto: **ni Dependabot, ni pip-audit, ni trivy las ven**
(hallazgo S-31). Este archivo es el registro que sustituye a ese radar.

## Al actualizar cualquiera de estas librerías

1. Descarga el artefacto **oficial** y verifica su integridad contra el registro de
   origen (npm publica `dist.integrity`, un sha512 en base64) — nunca desde un CDN sin
   comprobar nada.
2. Sustituye el archivo, recalcula el `sha256` y **actualiza la tabla de abajo**.
3. Ejecuta la suite y comprueba a mano el buscador en vivo (htmx) o el editor del
   panel (TinyMCE), según corresponda.

El CI comprueba que la versión declarada aquí coincide con la que hay dentro del
bundle, para que una actualización sin registrar no pase inadvertida.

## Inventario

| Librería | Versión | Fecha de la versión | sha256 del bundle principal | Origen |
|---|---|---|---|---|
| htmx | 2.0.10 | 2026-04 | `71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de` | `https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.10.tgz` → `dist/htmx.min.js` |
| TinyMCE | 7.9.3 | 2025 | `ca7a4ae9354b117b3133d5b449b4f807ac1484e66b5019c1381e1990ebb1ecd3` | <https://github.com/tinymce/tinymce> (release 7.9.3) |

- **htmx** — `htmx/htmx.min.js`. Un solo archivo. Se carga en todas las páginas
  (`base.html`) y mueve el buscador en vivo.
- **TinyMCE** — `tinymce/` (14 archivos: núcleo, tema, modelo, iconos, 3 plugins y
  skins). Solo se carga en el panel editorial. El subárbol está **exento del hash del
  manifiesto** de WhiteNoise (`config/staticfiles.py`) porque carga sus recursos con
  rutas relativas en tiempo de ejecución.

## Licencias

Ver [`../../../NOTICE.md`](../../../NOTICE.md). **TinyMCE 7.x es GPLv2-or-later**, lo que
tiene consecuencias para un repositorio que se declara propietario: está documentado
allí.

## Historial

- **2026-07-29** — htmx 2.0.3 → 2.0.10 (7 releases de parche, ~21 meses de retraso; sin
  CVE conocido en 2.0.3). Se crea este registro.
