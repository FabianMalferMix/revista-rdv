from django.db import migrations

PRIVACIDAD = """
<p>Esta política describe cómo el colectivo trata los datos personales que recoge a través de este
sitio, conforme a la Ley N.º 19.628 sobre protección de la vida privada (Chile). Es un texto base
que conviene revisar con asesoría legal antes de considerarlo definitivo.</p>
<h2>Qué datos recogemos y para qué</h2>
<ul>
<li><strong>Suscripción a novedades:</strong> tu correo electrónico, para enviarte información sobre
publicaciones y actividades. Solo tras confirmar tu suscripción (doble opt-in).</li>
<li><strong>Envíos y convocatorias:</strong> nombre, correo y los archivos que nos envíes, para
evaluar tu propuesta.</li>
<li><strong>Integrantes:</strong> nombre, biografía, foto y enlaces, publicados con tu consentimiento.</li>
</ul>
<h2>Base de licitud</h2>
<p>Tratamos estos datos con tu <strong>consentimiento</strong>, que puedes retirar en cualquier momento.</p>
<h2>Conservación y terceros</h2>
<p>Conservamos los datos mientras dure la finalidad para la que se recogieron. Se alojan en nuestra
infraestructura de servidor y no se venden ni ceden a terceros con fines comerciales.</p>
<h2>Tus derechos</h2>
<p>Puedes acceder, rectificar, cancelar u oponerte al tratamiento de tus datos escribiéndonos al
correo de contacto publicado en este sitio. Puedes darte de baja de las novedades desde el enlace
incluido en cada correo.</p>
"""

COOKIES = """
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

TERMINOS = """
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

PAGES = [
    ("privacidad", "Política de privacidad", PRIVACIDAD),
    ("cookies", "Política de cookies", COOKIES),
    ("terminos", "Términos y derechos", TERMINOS),
]


def create_pages(apps, schema_editor):
    """Crea las páginas legales base (idempotente; no pisa ediciones posteriores)."""
    Page = apps.get_model("content", "Page")
    for slug, title, body in PAGES:
        Page.objects.get_or_create(
            slug=slug, defaults={"title": title, "body": body.strip(), "status": "published"}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0006_alter_article_owner_poem_collectionpoem_and_more"),
    ]

    operations = [
        migrations.RunPython(create_pages, migrations.RunPython.noop),
    ]
