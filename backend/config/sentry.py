"""Sentry, con la redacción de datos personales y de secretos probada.

`init_sentry()` vive aquí, y no en settings.py, para que una prueba pueda arrancarla con un
transporte que guarda los eventos en vez de enviarlos (tests/test_sentry_redaction.py).
"""

import sentry_sdk

from config.redaction import sentry_before_breadcrumb, sentry_before_send

BROWSER_HEADERS = [
    "accept",
    "accept-language",
    "content-length",
    "content-type",
    "host",
    "hx-request",
    "user-agent",
]


def init_sentry(dsn, *, environment, release=None, traces_sample_rate=0.0, transport=None):
    return sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        # Lo que el SDK recoge por su cuenta, y que por defecto incluye el cuerpo de las
        # peticiones (el formulario del boletín, un envío con su texto), las variables de
        # cada marco (el correo, las URL con token) y las cabeceras: nada de la identidad de
        # la persona, ni cookies, ni cuerpos, ni variables, ni datos de las colas; de las
        # cabeceras, solo las que describen el navegador.
        data_collection={
            "user_info": False,
            "cookies": {"mode": "off"},
            "http_headers": {"request": {"mode": "allowlist", "terms": BROWSER_HEADERS}},
            "http_bodies": [],
            "url_query_params": {"mode": "off"},
            "stack_frame_variables": False,
            "database_query_data": False,
            "queues": False,
        },
        max_request_body_size="never",
        before_send=sentry_before_send,
        before_breadcrumb=sentry_before_breadcrumb,
        transport=transport,
    )
