# Componentes de terceros

`LICENSE` declara el código de este repositorio como **propietario**. Esa declaración
cubre el código **propio** del proyecto y **no** los componentes de terceros que se
incluyen en el árbol, cada uno con su propia licencia. Este archivo los inventaría.

> **Este documento describe hechos, no es asesoría legal.** El punto de TinyMCE de más
> abajo conviene revisarlo con un abogado antes de considerar el asunto cerrado —igual
> que el texto de la política de privacidad.

## ⚠️ TinyMCE 7.9.3 — GPLv2-or-later

`backend/static/vendor/tinymce/` (editor de texto enriquecido del panel editorial).

- **Licencia:** GNU General Public License v2 o posterior, según
  `backend/static/vendor/tinymce/license.md` (© Ephox Corporation DBA Tiny Technologies).
- **Origen:** <https://github.com/tinymce/tinymce>, release 7.9.3.
- **Por qué importa:** el proyecto **sirve** ese JavaScript minificado a los navegadores.
  Distribuir la forma compilada de un programa GPLv2 obliga a acompañarla de su licencia
  y a ofrecer el código fuente correspondiente (GPLv2 §3). Un repositorio que se declara
  «todos los derechos reservados» sin excepción contradecía esa obligación.
- **Alcance del copyleft:** GPLv2 **no** es AGPL. El código Django de este proyecto es un
  programa separado que se limita a servir el editor, no una obra derivada de él, así que
  usar TinyMCE **no** obliga a liberar el código propio. Lo que sí obliga es a no
  presentar el propio TinyMCE como propietario y a ofrecer su fuente.
- **Estado:** se cumple señalándolo aquí, conservando `license.md` y `notices.txt` en el
  árbol y enlazando la release oficial como fuente correspondiente.

**Decisión pendiente del colectivo** (las tres son válidas; solo la primera es de coste
cero y es la que está aplicada):

1. **Dejarlo así** — mantener TinyMCE bajo GPLv2 y este aviso.
2. **Licencia comercial de TinyMCE** — elimina la obligación de copyleft; tiene coste.
3. **Sustituir el editor** por uno permisivo (MIT/BSD) si se prefiere no tener GPL en el
   árbol. Afecta a `backend/apps/content/admin.py` y a `backend/static/admin/richtext_init.js`.

## Otros componentes

| Componente | Ubicación | Licencia | Obligaciones |
|---|---|---|---|
| htmx 2.0.10 | `backend/static/vendor/htmx/` | 0BSD | Ninguna (ni siquiera atribución) |
| Fraunces | `backend/static/fonts/` | SIL Open Font License 1.1 | Conservar el aviso; ver `fonts/NOTICE.txt` |
| DOMPurify | dentro del bundle de TinyMCE | Apache-2.0 / MPL-2.0 | Ver `vendor/tinymce/notices.txt` |
| Imágenes de demostración | `backend/apps/content/management/commands/seed_assets/` | CC0 y Licencia Unsplash | Ninguna; son marcadores reemplazables (ver su `NOTICE.txt`) |

Las versiones exactas y los `sha256` de lo vendorizado están en
[`backend/static/vendor/VERSIONS.md`](backend/static/vendor/VERSIONS.md).

## Contenido del sitio

Los derechos sobre el **contenido** (poemas, textos, fotografías, obras) pertenecen a sus
respectivos autores y no a este repositorio; ver la página «Términos y derechos» del sitio.
