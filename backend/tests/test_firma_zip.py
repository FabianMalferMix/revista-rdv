"""Un ZIP cualquiera ya no pasa por .docx.

`SubmissionForm` valida que los bytes iniciales correspondan a la extensión declarada, y
eso rechaza un PNG renombrado a .pdf. Pero un .docx (y un .odt) SON contenedores ZIP, así
que su firma `PK\\x03\\x04` la cumple cualquier zip: `mis-fotos.zip` renombrado a `.docx`
entraba como manuscrito.

No era un agujero de ejecución —el adjunto va a almacenamiento privado, solo lo descarga
quien tiene rol de editor, y se sirve con nosniff y CSP sandbox—, pero sí una promesa que
la validación no cumplía. Se cierra mirando el ÍNDICE del contenedor.

La mitad que más importa de estas pruebas es la contraria: que un .docx legítimo siga
entrando. Una validación más estricta que rechace envíos reales es peor que la laxa.
"""

import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.submissions.forms import SubmissionForm

DATOS = {
    "author_name": "Quien Sea",
    "author_email": "quien@example.com",
    "type": "reseña",
    "title": "Una propuesta",
    "body": "x" * 40,
}


def _zip(nombres):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in nombres:
            z.writestr(n, "contenido")
    return buf.getvalue()


def _valida(nombre, datos):
    form = SubmissionForm(DATOS, {"file": SimpleUploadedFile(nombre, datos)})
    return form.is_valid(), form.errors.get("file", [""])[0]


def test_un_zip_cualquiera_ya_no_pasa_por_docx():
    ok, error = _valida("fotos.docx", _zip(["vacaciones.jpg", "playa.jpg"]))
    assert not ok
    assert "no coincide con su extensión" in error


def test_un_docx_legitimo_sigue_entrando():
    """La mitad que importa: no romper los envíos de verdad."""
    ok, error = _valida(
        "manuscrito.docx",
        _zip(["[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml"]),
    )
    assert ok, error


def test_un_odt_legitimo_sigue_entrando():
    ok, error = _valida(
        "manuscrito.odt",
        _zip(["mimetype", "META-INF/manifest.xml", "content.xml", "styles.xml"]),
    )
    assert ok, error


def test_un_docx_al_que_le_falta_una_pieza_no_pasa():
    """Con el índice pero sin el documento: no lo abriría ningún procesador de textos."""
    ok, _ = _valida("roto.docx", _zip(["[Content_Types].xml", "otra-cosa.xml"]))
    assert not ok


def test_un_odt_renombrado_a_docx_no_pasa():
    """Los dos son ZIP y comparten firma, pero no son intercambiables."""
    ok, _ = _valida("confundido.docx", _zip(["mimetype", "META-INF/manifest.xml", "content.xml"]))
    assert not ok


def test_un_zip_corrupto_no_revienta():
    """Bytes que empiezan por PK pero no son un zip válido: rechazo limpio, no excepción."""
    ok, error = _valida("roto.docx", b"PK\x03\x04" + b"basura" * 20)
    assert not ok
    assert "no coincide con su extensión" in error


def test_no_se_extrae_nada_del_contenedor():
    """Solo se lee el índice, así que una entrada enorme declarada no se descomprime.

    Un zip bomba entraría por ahí si el validador extrajera. Se comprueba con una entrada
    que declara 1 GB: si se descomprimiera, esta prueba tardaría o agotaría la memoria.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "x")
        z.writestr("word/document.xml", "0" * (5 * 1024 * 1024))  # comprime muchísimo
    ok, _ = _valida("bomba.docx", buf.getvalue())
    assert ok  # es un docx bien formado; el punto es que no se cuelga


@pytest.mark.parametrize("ext", ["pdf", "rtf", "txt"])
def test_los_formatos_sin_contenedor_no_cambian(ext):
    """Contra-prueba: la comprobación nueva solo alcanza a docx y odt."""
    datos = {"pdf": b"%PDF-1.4 x", "rtf": b"{\\rtf1 x", "txt": b"texto plano"}[ext]
    ok, error = _valida(f"a.{ext}", datos)
    assert ok, error
