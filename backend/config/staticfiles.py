"""Storage de estáticos que exime a TinyMCE del hashing del manifiesto.

En runtime TinyMCE se auto-carga pidiendo `themes/silver/theme.min.js`,
`skins/ui/oxide/skin.min.css`, `plugins/lists/plugin.min.js`, etc. relativos a
`tinymce.min.js`. Si el `ManifestStaticFilesStorage` renombra esos archivos con
hash, esas peticiones darían 404. Por eso su carpeta se sirve sin hash: queda en el
manifiesto con su nombre tal cual (así `{% static %}` sigue resolviéndolo con
`manifest_strict=True`), pero no se hashea ni se reescribe. La carpeta lleva la versión
(`vendor/tinymce-7.9.3/`), tomada del manifiesto de lo vendorizado: al actualizar, la URL
cambia y ningún navegador sigue con la copia vieja en caché.
"""

import json
from pathlib import Path

from whitenoise.storage import CompressedManifestStaticFilesStorage

_VENDOR = json.loads(
    (Path(__file__).resolve().parent.parent / "static" / "vendor" / "manifest.json").read_text(
        "utf-8"
    )
)
# La carpeta de TinyMCE, con su versión, relativa a STATIC_URL: «vendor/tinymce-7.9.3/».
TINYMCE_DIR = "vendor/" + _VENDOR["tinymce"]["target"].format(version=_VENDOR["tinymce"]["version"])


class VendoredStaticFilesStorage(CompressedManifestStaticFilesStorage):
    # Prefijos (relativos a STATIC_URL) servidos sin hash ni post-proceso.
    unhashed_prefixes = (TINYMCE_DIR,)

    def _is_vendored(self, name):
        return self.clean_name(name).startswith(self.unhashed_prefixes)

    def post_process(self, paths, dry_run=False, **options):
        if dry_run:
            return

        vendored = {k: v for k, v in paths.items() if self._is_vendored(k)}
        others = {k: v for k, v in paths.items() if not self._is_vendored(k)}

        # Procesa (hash + reescritura de refs + compresión + manifiesto) todo lo demás.
        yield from super().post_process(others, dry_run=dry_run, **options)

        # Registra los vendidos en el manifiesto con su nombre tal cual (sin hash)
        # y re-guarda; así {% static %} los resuelve aun con manifest_strict.
        for name in vendored:
            clean = self.clean_name(name)
            self.hashed_files[self.hash_key(clean)] = clean
            yield name, clean, True
        if vendored:
            self.save_manifest()
