"""Las políticas de cookies y de privacidad nombran los reproductores de video.

Una base que ya migró tiene en esas dos páginas el texto que les dieron `0007_legal_pages` y
`0010_privacy_ley_21719`, copiado abajo tal cual. La política que conserva ese texto pasa al
vigente de `apps/content/legal.py`; la que se editó en el panel, aunque sea en una letra, no se
toca. Una base nueva nace con el texto vigente, y en ella esta migración no cambia nada.
"""

from django.db import migrations

from apps.content import legal

_COOKIES_BEFORE = """
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

_PRIVACY_BEFORE = """
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

PREVIOUS_BODIES = {"cookies": _COOKIES_BEFORE.strip(), "privacidad": _PRIVACY_BEFORE.strip()}


def name_the_players(apps, schema_editor):
    """Cada política que conserva el texto anterior, entero, toma el vigente."""
    Page = apps.get_model("content", "Page")
    for slug, previous in PREVIOUS_BODIES.items():
        Page.objects.filter(slug=slug, body=previous).update(body=legal.pages()[slug].body)


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0023_body_images"),
    ]

    operations = [
        migrations.RunPython(name_the_players, migrations.RunPython.noop),
    ]
