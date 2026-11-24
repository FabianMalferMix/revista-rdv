# Componentes de terceros

`LICENSE` declara el código de este repositorio como **propietario**. Esa declaración
cubre el código **propio** del proyecto y **no** los componentes de terceros que se
incluyen en el árbol, cada uno con su propia licencia. Este archivo los inventaría.

> **Este documento describe hechos, no es asesoría legal.** El punto de TinyMCE de más
> abajo conviene revisarlo con un abogado antes de considerar el asunto cerrado —igual
> que el texto de la política de privacidad.

## ⚠️ TinyMCE 8 — GPLv2-or-later

`backend/static/vendor/tinymce-<versión>/` (editor de texto enriquecido del panel editorial). La
versión exacta está en `backend/static/vendor/manifest.json`.

- **Licencia:** el paquete de npm ofrece dos, según su `license.md` (© Ephox Corporation DBA Tiny
  Technologies): la GNU General Public License v2 o posterior, o los términos de uso de Tiny,
  con su acuerdo de licencia autoalojada. El proyecto lo usa bajo la **GPL v2 o posterior** y se
  lo declara al editor con `license_key: "gpl"` (`backend/static/admin/richtext_init.js`), como
  indica la documentación de Tiny para quien lo autoaloja bajo la GPL. El código fuente en
  GitHub lleva solo la GPL; el texto doble se añade al empaquetarlo para npm.
- **La frase de aceptación:** ese `license.md` termina con «By use of this Software you have
  agreed to these Tiny Technologies, Inc Software Terms & Conditions of Use», sin distinguir
  entre las dos opciones. La documentación de Tiny y sus requisitos de atribución tratan el uso
  libre y autoalojado como uso bajo la GPL.
- **Origen:** <https://github.com/tinymce/tinymce>, en la etiqueta de esa versión. Lo
  vendorizado es el paquete `tinymce` de npm, verificado contra su integridad
  (`python3 tools/vendor/update.py check`).
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

**Decidido el 2026-11-10** (C36, en `docs/deferidos-y-decisiones.md`): seguir con TinyMCE bajo
la GPL v2 o posterior y este aviso. Quedan otras dos salidas: la licencia comercial de Tiny, que
elimina la obligación de copyleft y tiene coste, o sustituir el editor por uno permisivo
(MIT/BSD), que afecta a `backend/apps/content/admin.py` y a
`backend/static/admin/richtext_init.js`.

## Otros componentes

| Componente | Ubicación | Licencia | Obligaciones |
|---|---|---|---|
| htmx 2.0.11 | `backend/static/vendor/htmx/` | 0BSD | Ninguna (ni siquiera atribución) |
| Bricolage Grotesque, con el eje de peso recortado a 400-700 | `backend/static/fonts/` | SIL Open Font License 1.1 | Conservar el aviso y la licencia (`fonts/OFL-bricolage-grotesque.txt`); ver `fonts/NOTICE.txt` |
| Source Serif 4 (Adobe), modificada y renombrada «RdV Serif» | `backend/static/fonts/` | SIL Open Font License 1.1, con nombre reservado «Source» | Conservar el aviso y la licencia (`fonts/OFL-source-serif-4.txt`); una versión modificada no puede llamarse «Source»; ver `fonts/NOTICE.txt` |
| DOMPurify | dentro del bundle de TinyMCE | Apache-2.0 / MPL-2.0 | Ver `notices.txt`, en la carpeta de TinyMCE; la versión que se sirve, en `backend/static/vendor/VERSIONS.md` |
| Fotos de demostración (`event-*.jpg`): de Lorem Picsum, originadas en Unsplash y pasadas a escala de grises | `backend/datos_de_desarrollo/media/assets/2026/07/` | Licencia Unsplash (uso libre, también comercial) | Ninguna; son marcadores reemplazables. Las demás imágenes de esa copia son marcadores dibujados para el proyecto (`seed_material_generico`) |

Las versiones exactas y los `sha256` de lo vendorizado están en
[`backend/static/vendor/manifest.json`](backend/static/vendor/manifest.json); cómo se
actualiza, en [`backend/static/vendor/VERSIONS.md`](backend/static/vendor/VERSIONS.md).

## Contenido del sitio

Los derechos sobre el **contenido** (poemas, textos, fotografías, obras) pertenecen a sus
respectivos autores y no a este repositorio; ver la página «Términos y derechos» del sitio.
