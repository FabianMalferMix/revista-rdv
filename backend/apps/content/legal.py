"""El texto vigente de las páginas legales: privacidad, cookies y términos.

Lo leen las migraciones de datos que crean y actualizan estas páginas (`0007_legal_pages` y
`0010_privacy_ley_21719`) y el fixture `legal_pages` de las pruebas, así que una base recién
migrada y la de pruebas tienen el mismo texto. Una base que ya migró no vuelve a leer este
archivo: cambiar el texto de una página publicada se hace con una migración de datos nueva que
actualice las bases existentes, no editando este archivo a secas. De sus slugs sale también
`LEGAL_PAGES` (models.py): las páginas a las que el panel no deja cambiar el slug, despublicar
ni borrar.

Como lo importan migraciones, este módulo no importa modelos (cada migración le pasa el suyo, el
histórico), y `pages` y `create_pages` conservan su nombre y su firma.
"""

from typing import NamedTuple


class LegalPage(NamedTuple):
    title: str
    body: str


_PRIVACY = """
<p>Esta política describe cómo el colectivo trata los datos personales que recoge a través de este
sitio, conforme a la <strong>Ley N.º 19.628</strong> sobre protección de la vida privada y a la
<strong>Ley N.º 21.719</strong> que la moderniza (Chile). Es un texto base que conviene revisar con
asesoría legal antes de considerarlo definitivo.</p>
<h2>Responsable</h2>
<p>El responsable del tratamiento es el colectivo, contactable en el correo publicado en este sitio.</p>
<h2>Qué datos recogemos y para qué</h2>
<ul>
<li><strong>Suscripción a novedades:</strong> tu correo electrónico, para enviarte información sobre
publicaciones y actividades. Solo tras confirmar tu suscripción (doble opt-in).</li>
<li><strong>Envíos y convocatorias:</strong> nombre, correo y los archivos que nos envíes, para
evaluar tu propuesta.</li>
<li><strong>Integrantes:</strong> nombre, biografía, foto y enlaces, publicados con tu consentimiento.</li>
</ul>
<h2>Base de licitud</h2>
<p>Tratamos estos datos con tu <strong>consentimiento</strong>, que puedes retirar en cualquier
momento sin que ello afecte la licitud del tratamiento previo.</p>
<h2>Conservación</h2>
<p>Conservamos los datos solo mientras dure la finalidad para la que se recogieron:</p>
<ul>
<li>Las suscripciones <strong>no confirmadas</strong> se eliminan automáticamente pasado un tiempo.</li>
<li>Los <strong>envíos rechazados o retirados</strong> (con su material adjunto) se eliminan pasado
un tiempo desde su resolución.</li>
<li>Los datos de suscriptores confirmados se conservan hasta que te des de baja.</li>
</ul>
<h2>Terceros y seguridad</h2>
<p>Los datos se alojan en nuestra infraestructura de servidor y no se venden ni ceden a terceros con
fines comerciales. Aplicamos medidas de seguridad razonables; el material de los envíos se guarda en
almacenamiento privado, no accesible públicamente.</p>
<h2>Tus derechos</h2>
<p>Puedes ejercer tus derechos de <strong>acceso, rectificación, cancelación (supresión), oposición y
portabilidad</strong> escribiéndonos al correo de contacto publicado en este sitio. Puedes darte de
baja de las novedades desde el enlace incluido en cada correo.</p>
<p><em>Texto base para revisión legal.</em></p>
"""

_COOKIES = """
<p>Este sitio usa <strong>solo cookies técnicas y estrictamente necesarias</strong> para su
funcionamiento. No usamos cookies de analítica, publicidad ni seguimiento de terceros.</p>
<h2>Qué cookies usamos</h2>
<ul>
<li><strong>Sesión:</strong> mantiene la sesión iniciada en el panel de administración.</li>
<li><strong>CSRF:</strong> protege los formularios contra falsificación de solicitudes.</li>
</ul>
<p>Al ser necesarias para operar el sitio, no requieren consentimiento previo. No se comparte
información con terceros mediante cookies.</p>
"""

_TERMS = """
<h2>Titularidad</h2>
<p>Este sitio es operado por el colectivo. El código y el diseño están sujetos a los derechos de sus
autores.</p>
<h2>Derechos sobre las obras</h2>
<p>Los poemas, textos, fotografías y demás obras publicadas pertenecen a sus respectivos autores,
quienes <strong>conservan todos sus derechos</strong>. El colectivo cuenta con autorización para
difundirlas en este sitio y en sus actividades. No se permite la reproducción total o parcial de las
obras sin autorización de sus autores.</p>
<h2>Enlaces externos</h2>
<p>El sitio puede enlazar a sitios de terceros (medios, editoriales, plataformas de video); no nos
hacemos responsables de sus contenidos ni políticas.</p>
<h2>Contacto</h2>
<p>Para consultas sobre derechos o uso de contenidos, escríbenos al correo de contacto publicado en
este sitio.</p>
"""


def pages():
    """Cada página legal por su slug, con su título y su cuerpo en HTML."""
    return {
        "privacidad": LegalPage("Política de privacidad", _PRIVACY.strip()),
        "cookies": LegalPage("Política de cookies", _COOKIES.strip()),
        "terminos": LegalPage("Términos y derechos", _TERMS.strip()),
    }


def create_pages(page_model):
    """Crea, publicadas, las páginas legales que falten. Las que ya existen no se tocan: su texto
    se edita en el panel."""
    for slug, page in pages().items():
        page_model.objects.get_or_create(
            slug=slug, defaults={"title": page.title, "body": page.body, "status": "published"}
        )
