from django.db import migrations

# Texto base (para revisión legal) que actualiza la política de privacidad citando
# también la Ley 21.719 y detallando la conservación/retención de datos.
NEW_PRIVACIDAD = """
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


def update_privacy(apps, schema_editor):
    Page = apps.get_model("content", "Page")
    page = Page.objects.filter(slug="privacidad").first()
    if not page:
        return
    # Solo actualiza el texto SEMBRADO original (cita 19.628 pero aún no 21.719): no
    # pisa una edición manual posterior hecha en el admin.
    if "19.628" in page.body and "21.719" not in page.body:
        page.body = NEW_PRIVACIDAD.strip()
        page.save(update_fields=["body"])


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0009_search_vector_triggers"),
    ]

    operations = [
        migrations.RunPython(update_privacy, migrations.RunPython.noop),
    ]
