# Diferidos y decisiones — referencia para desarrollo futuro

Documento vivo que consolida **las decisiones importantes** (con su porqué) y **todo
lo diferido conscientemente**, desde las tres primeras auditorías y sus remediaciones
(PRs #5–#72) hasta la auditoría de código de octubre de 2026. Objetivo: que quien retome
el proyecto entienda *qué se decidió y por qué*, y *qué quedó pendiente, por qué, y cómo
abordarlo*.

Las auditorías anteriores y sus planes se retiraron del árbol el 2026-10-27 y siguen en git,
en `git show 38fdf03:docs/<archivo>`. Las tres primeras son `auditoria-mvp.md` (#1),
`auditoria-post-fase3.md` (#2) y `auditoria-qa.md` (#3, con su plan de remediación), y
cerraron con **P0+P1+P2 y los accionables de P3 completos, CI verde**. La vigente es
`docs/auditoria-codigo.md`, con su backlog, `docs/backlog-codigo.md`.

---

## 1. Decisiones importantes (y su porqué)

### Decisiones de producto/negocio

- **D2 — Newsletter como lista LATENTE** (`apps/community`). Se decidió **no construir
  el camino de envío** (sin campañas ni comando de difusión): solo se capta y confirma
  con doble opt-in, y los suscriptores nunca confirmados se purgan periódicamente
  (`purge_stale_data`, beat lunes 04:30). *Porqué:* minimización de datos; no hay uso
  real todavía. *Implicación:* construir el envío (con `List-Unsubscribe-Post` de
  un-clic y confirmación por POST) recién cuando exista una campaña.

- **Tienda = solo vitrina.** El catálogo (`showcase.Publication` + `WhereToBuy`) no
  procesa pagos; enlaza a puntos de venta externos. *Porqué:* el sitio es un dossier
  vivo de un colectivo de poesía, no un e-commerce.

- **Texto legal de privacidad (Ley 21.719) es un BORRADOR.** Redactado por la IA,
  aplicado en la migración de datos `content.0010`. **Debe revisarse con un abogado
  antes de considerarlo definitivo.**

### Decisiones técnicas transversales

- **D1 — Resolución de IP unificada tras el proxy** (`config/clientip.py`). Un único
  resolver `client_ip` (django-ipware, `proxy_order='right-most'`) lo comparten
  `django-ratelimit` (`RATELIMIT_IP_META_KEY`) y `django-axes` (`AXES_CLIENT_IP_CALLABLE`)
  para que ambos cuenten por la misma IP. *Porqué:* toma la IP que Caddy añade al final
  de `X-Forwarded-For` (a prueba de spoofing). **Supuesto crítico:** Caddy es el ÚNICO
  proxy de borde. **Si se antepone un CDN/balanceador, hay que revisar cuántos proxies
  de confianza hay** (el right-most dejaría de ser la IP real del cliente).

- **D3 — Búsqueda insensible a acentos** (`unaccent`). Implementado: migración
  `content.0011` con funciones de trigger propias que construyen el `search_vector` con
  `to_tsvector('spanish', unaccent(...))`, y `_strip_accents()` en la vista de búsqueda.
  **Supuesto:** el usuario de la BD puede `CREATE EXTENSION` (el Postgres propio del
  proyecto corre como superusuario). **En una BD gestionada (RDS, etc.), un admin debe
  pre-crear la extensión `unaccent`** o la migración fallará.

- **D4 — Rendimiento: guardia de queries sí, carga con umbral no (aún).** Se añadieron
  presupuestos de consultas anti-N+1 (`django_assert_max_num_queries`, `test_performance.py`).
  El smoke de carga (k6/locust) con umbral p95 se difirió: empezar sin umbral bloqueante
  y calibrar (ver §2).

- **FTS por trigger de Postgres, no `GeneratedField`.** El `search_vector` lo mantiene un
  trigger (migraciones 0009→0011). *Porqué:* `unaccent` no es `IMMUTABLE`, así que no
  sirve en un `GeneratedField`/índice de expresión; el trigger sí lo permite y además
  cubre `bulk_update`/`QuerySet.update`/imports (que no pasan por `save()`). **Reabierta
  el 2026-10-28 (C23).**

- **`CACHES` → Redis (db 2) en prod, LocMem en dev/tests.** Necesario para que los
  contadores de `django-ratelimit` se compartan entre workers. Seguro con `noeviction`
  gracias a los TTLs. **Reabierta el 2026-10-28 (C25).**

- **`CELERY_TASK_ALWAYS_EAGER` en tests** (`"pytest" in sys.modules`). *Porqué:*
  hermeticidad. *Consecuencia importante:* **la suite normal NO ejecuta reintentos ni
  concurrencia de Celery** (en eager las tareas no reintentan — es diseño de Celery). Por
  eso la concurrencia se prueba aparte con `transaction=True` + hilos (`test_concurrency.py`,
  marcados `integration`) y la política de reintento con tests de contrato.

- **`serialized_rollback` descartado.** Los tests `transaction=True` vacían la tabla y
  con ella las páginas legales de migración; se intentó `serialized_rollback=True` pero
  es **inestable con `--reuse-db`**. Solución adoptada: fixture `legal_pages` (reutiliza
  las funciones `RunPython` de las migraciones 0007/0010) en los tests que las consultan.

- **`filterwarnings = error` + `pytest-randomly`.** Los warnings fallan la suite (obliga
  a atender deprecations de cara a Django 6.x) y el orden se aleatoriza (detecta
  dependencias de orden). Hay un `ignore` acotado para el warning benigno de WhiteNoise
  «No directory at: staticfiles/» (en tests no se corre collectstatic).

### Decisiones del rediseño UX/UI (D1 a D14, 2026-10-08)

> Numeración propia del backlog del rediseño (§1 de `git show 38fdf03:docs/backlog-ux-ui.md`):
> **no son las D1 y D2 de arriba**. El dueño del sitio delegó las catorce el 2026-10-08; la
> última columna dice cómo quedaron, con lo que él cambió al ver cada paso. La verificación
> está en `git show 38fdf03:docs/auditoria-ux-ui-verificacion.md`.

| # | Decisión | Porqué | Cómo quedó |
|---|---|---|---|
| D1 | Cinta de integrantes sin control de pausa (sin efecto: la cinta se retiró en D22) | Se detiene al señalarla y con el foco dentro; en táctil es una fila; con «menos movimiento», quieta | El dueño descartó dos veces el control (un rótulo y un icono). WCAG 2.2.2 queda discutible; no volver a proponerlo salvo que él lo pida |
| D2 | El buscador, plegado en una lupa | Sitio pequeño; el sitio de la cabecera va al botón «Dossier» | Lupa con panel (paso 18). La búsqueda cubre personas, registros, publicaciones y actividades, por grupos (paso 24, #134) |
| D3 | La monoespaciada, solo para rótulos y datos | La voz dominante es la de lectura | Navegación y títulos en Syne, cuerpo en serif (paso 11). La portada queda en 38 % de elementos en mono (meta: 30) por los cargos de la cinta (medido antes de D22, que la retiró) |
| D4 | Serif de lectura autoalojada | La misma voz en todos los sistemas | «RdV Serif», un subconjunto de Source Serif 4 renombrado por la OFL; fuentes en 120 KB (paso 11) |
| D5 | El amarillo del cartel, solo como fondo | Como texto da 1,03:1 | El dueño rechazó el plano amarillo («invasivo»); queda el trazo de marcador bajo las cifras, que hoy solo están en el dossier (pasos 13 y 22). Los lomos del estante llevan el color de su tapa (D28): amarillos solo si la tapa lo es. Y es la segunda tinta de dos sellos de «Prensa y gestión» (D31): un trazo corrido, no un plano |
| D6 | Bandas de tinta, dos por página como mucho | Peso visual dentro de una paleta clara | El dueño rechazó la banda oscura del destacado; la tinta queda solo en el pie (paso 13) |
| D7 | Tres carriles: lectura, ancho y sangre | Usar el ancho sin alargar la línea de lectura | Paso 9. El dossier y el formulario siguen en el de lectura |
| D8 | El nombre del colectivo como titular | El lema era una categoría genérica | El dueño eligió el nombre en dos líneas con la cubierta del catálogo al lado (paso 19) |
| D9 | Barra de cinco enlaces y «Dossier»; prensa y aliados como línea de respaldo | Lo de gestores vivía solo en el pie | Barra hecha (paso 18). La línea de respaldo de la portada la quitó el dueño (#128, #129) |
| D10 | La placa azul del reproductor, nunca vacía | Figura y fondo | Póster a una tinta o carátula tipográfica (paso 15) |
| D11 | Cifras del dossier en grande | Es lo primero que busca un jurado | Syne de 34 a 56 px con el trazo amarillo, también al imprimir (paso 22) |
| D12 | La cinta, desde 12 integrantes (reemplazada por D22) | La cinta no era el problema; sus tarjetas sí | Retratos 4:5 a una tinta; fila con scroll en táctil (paso 14) |
| D13 | Títulos de sección en Syne con cejilla | Un título no puede medir menos que su texto | En todo el sitio; en el dossier desde el paso 22 |
| D14 | Estados por color, radios y filetes en tokens | Acabado consistente; WCAG 1.4.11 | `--r-1`, `--line` y `--edge` (paso 6) |
| D15 | La cabecera al bajar: opción C (2026-10-15) | Una primera vista limpia de la portada, camino a una portada más estética | Arriba, la cabecera sin filete; en la portada, nada. Al bajar 64 px (56 en el teléfono), una cápsula «Objeto» con el velo (menos en la portada; el velo se quitó en D34). Cambia, solo para la cabecera, «nada de revelado al scroll» y la navegación a la vista arriba de la portada; el «Ver el dossier» vuelve al titular. Sin JavaScript, la cabecera fija de siempre |
| D16 | El buscador en la barra (2026-10-15) | El panel bajo la cabecera se veía genérico | La lupa abre el campo dentro de la fila, en el lugar de los enlaces (en la cápsula, la cápsula se vuelve el buscador); los resultados, en una tarjeta con el acabado de la cápsula. Sin `:has()`, el panel de antes (C26 lo retira, 2026-10-28) |
| D17 | Bricolage Grotesque en lugar de Syne (2026-10-20) | Una grotesca con más carácter; sus muescas de imprenta conversan con lo risográfico | Titulares, nombre de la portada, barra, botones y sello. Autoalojada (`static/fonts/bricolage-grotesque.woff2`, peso 400–700 y tamaño óptico), con reserva métrica. La lectura sigue en RdV Serif; las cubiertas de demostración son imágenes y conservan Syne |
| D18 | La portada como obra: mancheta de afiche con telón (2026-10-20) | La primera vista parecía la de cualquier landing; se pidió una de sitio de arte y diseño | Una obra a sangre y, al pie, el logo horizontal en tinta y multiplicado (en el teléfono, el apilado). La hoja que sigue (cejilla, manifiesto en letra grande, botones y sello) asoma 88 px a 951 y 72 en el teléfono; la cubierta del titular ya no va. Telón: la obra queda quieta y la hoja sube encima, solo sin «reducir movimiento» y si la obra cabe en la ventana; cambia, solo para esto, «nada de revelado al scroll». La obra se elige en el perfil (`hero_image` y `hero_image_phone`, migración showcase 0008) y sale en AVIF y WebP hasta 2560 px, sin servir el original; sin ella, la lámina de `static/img/portada/`. El logo es un redibujo en vector, en línea en la plantilla, hasta que llegue el original |
| D19 | La tirada de registros (2026-10-21) | El registro destacado era uno solo, como la tarjeta de una plataforma | Los registros que el colectivo marca como destacados, en su orden y hasta cinco, son pliegos de una tirada en un carril que sangra por la derecha: el del frente a dos tintas (título en `--t7`, el décimo paso de la escala, con corrimiento magenta como estado), los demás como pruebas en trama, hoja de contactos con títulos y colofón. Cada pliego lleva a su ficha: la portada no reproduce (el click-to-play queda en la ficha). Nada avanza solo; las tintas cambian solo de color (`@property`). El póster queda a una tinta también al señalarlo. Imagen: el póster o la primera foto del evento. Sin ninguno marcado, el registro destacado del perfil hace de respaldo; sin registros, vuelve el poema destacado. Sin migración (`Recording.featured` y `position` ya existían) |
| D20 | La tirada apilada (2026-10-22) | Con la tirada en fila se veía un pliego entero y un trozo: «solo 2 columnas» | Entre cinco variaciones sobre la sección real, el dueño eligió «La pila»: con JavaScript los pliegos se apilan (el de arriba derecho; los que siguen, debajo, corridos y girados; los ya vistos asoman por la izquierda) y se ven los cinco. Al cambiar, el que pasa arriba sale de la pila por su lado y vuelve encima (animación de 0,7 s con la API de animaciones) y los demás se corren en tres `--dur-base`: excepción a «solo color», aprobada con la pila; con menos movimiento, de golpe. En el teléfono, deslizar el dedo pasa de registro (`touch-action: pan-y`). Sin JavaScript sigue la fila con imán |
| D21 | Duración de los registros y el panel en castellano (2026-10-22) | El sello del pliego no podía decir cuánto dura un registro, y el panel mostraba «Featured», «Position» y «Featured recording» | `Recording.duration_minutes` (migración media 0006): el sello dice «Video · 42 min» (o «1 h 05 min») en la portada, el índice y la ficha. Los rótulos de «Registro» y de «Perfil del sitio» (con sus redes) pasan al castellano (media 0006 y showcase 0009, solo nombres). El resto de los modelos sigue con rótulos en inglés |
| D22 | «El colectivo» en la portada: la plana, en pliegos de seis (2026-10-22; la reemplazó D23) | La sección gastaba mucho alto para decir poco: la cinta enseñaba tres tarjetas y media sin enlace a su ficha, y con menos de 12 integrantes la portada ponía una rejilla de 1231 px a 951 | Entre las cuatro opciones del tablero «El colectivo en portada», el dueño eligió A, «La plana»: la cabeza a la izquierda con «Conoce al colectivo →»; a la derecha, seis retratos con el nombre y el rol en una etiqueta y la columna del medio más abajo. Cada retrato lleva a su ficha y al señalarlo solo él pasa a color. El título dice «Las voces», sin cifra. Con más de seis, pliegos de seis, sin tope: «Otras seis →», «←» o deslizar en el teléfono; reparto animado salvo con «menos movimiento»; sin JavaScript, las seis primeras. Se retiraron la cinta y su umbral (D1, D12). `static/js/integrantes.js`, `tests/test_integrantes_portada.py` |
| D23 | «Las voces» en relevo (2026-10-22) | Con D22 la sección medía 600 px a 951 (61 % de la pantalla), los retratos eran grandes, quedaba mucho hueco entre «Las voces» y los retratos, y había que pulsar «Otras seis» | Entre cuatro opciones con video (tablero «Las voces en relevo»), el dueño eligió la 3, «De a una», con la pasada de tinta de la 2: la cabeza a 216 px y a 40 de una fila de cinco retratos con el nombre debajo (tres en el teléfono). Cada 1,8 s llega otra integrante a uno de los lugares, bajo una franja de tinta azul con el filo magenta. Corre solo con un puntero que pueda posarse y sin «menos movimiento» (como la cinta, D1), y se detiene con el puntero encima o el foco dentro. En el teléfono, deslizar trae a otras tres. Sin botones; 328 px a 951. `static/js/integrantes.js`, `tests/test_integrantes_portada.py` |
| D24 | El estante de publicaciones (2026-10-22) | La sección parecía una tienda: el mismo esquema de las demás (título a la izquierda, fila de tarjetas), tapas planas y sin decir de qué trata cada publicación | Entre cuatro opciones con video (tablero «El catálogo en portada»), el dueño eligió la 3, «Estante», y aceptó las recomendaciones: una publicación de frente y hasta cinco de lomo (`ESTANTE = 6`), de pie sobre la tabla, con la ficha de la de frente al lado (tipo, año, editorial, sinopsis y «Ver la publicación →»). Va de frente la marcada «Featured» y, si no hay, la primera según «Position». Lomos por tipo (libro, plaquette, fanzine) y por lugar en las tintas del sitio: azul, magenta, amarillo (aprobado aunque D5 reservaba el amarillo) y blanco con filete. Sin JavaScript el lomo lleva a la ficha; con `static/js/estante.js` es un botón que saca el libro al frente. 515 px a 951. `tests/test_estante.py` |
| D25 | El estante, más largo (2026-10-22) | Con diez publicaciones de prueba, el dueño pidió un estante más largo, una ficha mucho más angosta y que «Ver catálogo» se viera: era un enlace discreto en la cabecera y quien busca una publicación que no está en el estante no lo encontraba | Ficha de 15rem (240 px) con el título un paso más chico; la tabla ocupa el resto y lleva hasta ocho (`ESTANTE = 8`: una de frente y siete de lomo, los lomos algo más delgados para que quepan a 951 px). «Ver todo el catálogo →» pasa a ser un botón lleno bajo el extremo de la tabla; sale de la cabecera. 586 px a 951 |
| D26 | El estante, a la medida de sus libros (2026-10-22) | Con el tope de ocho, la tabla de D25 era más larga que los libros y dejaba un tramo vacío; la ficha podía ser algo más ancha | La tabla mide lo que sus libros (`fit-content`), con «Ver todo el catálogo →» bajo su extremo, y la ficha ocupa el resto: 288 px a 951. Por debajo de 900 px la ficha va bajo el estante |
| D27 | El estante, con aire y un cambio suave (2026-10-22) | Ceñida a sus libros, la tabla se veía saturada; antes, medio vacía. Y al elegir otro libro, los lomos saltaban de lugar | La tabla sigue un tramo después del último libro, proporcional a la pantalla (`clamp(40px, 6vw, 120px)`: 57 px a 951); la ficha, 261 px. Al cambiar de libro, cada uno se desliza desde donde estaba (FLIP), el elegido gira desde el lomo hasta quedar de frente, el que estaba vuelve a lomo con un fundido y las fichas, apiladas en la misma celda, se funden. Con «reducir movimiento», al instante |
| D28 | El lomo, del color de su tapa (2026-10-22) | Los lomos tomaban las tintas del sitio según su lugar en la tabla: un libro azul de lomo salía blanco de frente | Cada lomo lleva el color del borde de su tapa (la mediana del anillo exterior, medida una vez por archivo con Pillow y guardada en la caché: `MediaAsset.color_de_borde()`), y el canto de la tapa de frente, ese color más oscuro (`Publication.lomo`). Se pintan con rectángulos de SVG (`fill` no es un estilo en línea: la CSP del sitio sigue sin admitirlos). El texto del lomo va en tinta o en blanco, el que más contraste dé. Sin tapa legible, la hoja clara con filete. Sin migraciones |
| D29 | La tirada con el índice al lado y sin flechas (2026-10-27) | A 1900 px la pila ocupaba unos 1076 px de un carril de 1440 y empezaba en su borde izquierdo: quedaban unos 360 px vacíos antes de las flechas y la sección se veía corrida | Entre tres encuadres (tablero «La tirada en su carril»), el dueño eligió la C, «Índice al lado», y pidió quitar las flechas: desde 1100 px la hoja de contactos va a la derecha como índice vertical, con miniatura y título entero, y es la manera de pasar de un registro a otro. El pliego y el abanico se ajustan al hueco que deja el índice. Por debajo, la hoja de contactos sigue bajo la pila; el teclado y el dedo siguen sirviendo |
| D30 | El estante, más grande en pantallas anchas (2026-10-27) | A 1900 px el estante y su ficha llegaban a unos 1310 px de un carril que termina en 1670: quedaban unos 360 px vacíos a la derecha | Entre tres arreglos (tablero «El estante en su carril»), el dueño eligió la B: desde 1400 px la tapa de frente pasa de 200 a 270 px, los lomos crecen en alto y grueso, y el título y la sinopsis de la ficha suben un paso. Por debajo, como antes. «La obra» (poemas y textos) se deja como está |
| D31 | «Prensa y gestión», sellos en risografía (2026-10-27) | El cierre eran cuatro enlaces de texto entre dos filetes: correcto, pero lo único de la portada sin objeto ni gesto, y desentonaba con el resto | Entre tres maneras (tablero «Prensa y gestión, con gesto») el dueño prefirió los sellos y pidió más variaciones en risografía; de las cuatro (tablero «Sellos en risografía») eligió la B2, «Desregistro a dos tintas». Cada puerta es un sello girado: marco de 3 px y palabra grande en mayúsculas en su tinta (magenta o azul) y, corrida 3–4 px, una segunda pasada en otra tinta (azul, magenta o amarillo) multiplicada sobre el papel; todo con grano (una máscara de ruido en SVG, como `data:`, que la CSP admite). La palabra pequeña no lleva la segunda pasada, para que se lea. Al señalarlo, el sello se endereza y crece un poco, solo sin «reducir movimiento». Desde 900 px los cuatro en una fila; en el teléfono, de dos en dos. Tres excepciones al sistema, con motivo y en las pruebas: el amarillo como segunda tinta (aprobado por el dueño, ver D5), las mayúsculas fuera de `.rotulo` (un timbre de goma va en mayúsculas) y el magenta en reposo (son objetos en su tinta, no texto suelto). `tests/test_portada.py` |
| D32 | El cambio de libro, sin prisa (2026-10-27) | El dueño vio demasiado rápido el cambio de publicación en el estante: duraba 460 ms con una curva que hacía casi todo el recorrido en los primeros 90 ms, y el resto era un asiento que apenas se veía | Los libros se deslizan en 800 ms y el elegido gira en 900, con la curva de la tirada (`cubic-bezier(.45,.05,.25,1)`): arrancan suave, viajan por el medio y se asientan despacio. La ficha vieja se desvanece en 320 ms y la nueva llega cuando el libro va a medio girar (a los 360 ms, en 560), con la curva de las transiciones del sitio. Con «reducir movimiento», al instante, como antes. `tests/test_estante.py` |
| D33 | La hoja, lámina a dos tintas (2026-10-27) | La presentación era una columna de unos 440 px pegada a la izquierda, en letra mediana: a 1900 px dejaba más de 900 px vacíos y se leía como una nota al pie de la obra, no como la presentación del colectivo. Y el manifiesto se cortaba en la palabra 28, a media frase («donde no suelen …») | Entre cuatro opciones (tablero «La presentación, al frente»: protagonista, centrada y dos en risografía), el dueño eligió la C. Desde 900 px, a la izquierda la cejilla, el manifiesto en letra de cartel (`--t5`; `--t6` desde 1600 px) y tinta azul con grano, y los botones; a la derecha, un círculo de trama magenta que recoge el de la obra, con el sello de la convocatoria estampado encima (sin convocatoria, la trama queda sola). El azul como texto sobre el papel da 3,88:1: no sirve en letra corriente (sigue prohibido), sí en letra de cartel, donde AA pide 3:1. El grano se quita cuando «Conócenos» tiene el foco. El grano de la risografía pasa a `:root` y lo comparten los sellos del cierre. En todas las anchuras, el manifiesto termina en su primera pausa (filtro `primera_pausa`: punto, dos puntos o punto y coma —cerrados con punto—, o cierre de pregunta o exclamación); si llega después de 36 palabras, la palabra 28, como antes. Por debajo de 900 px, la columna de siempre. `tests/test_portada.py` |
| D34 | La cápsula sin velo, en todas las páginas (2026-10-27) | Fuera de la portada, al bajar, una franja de papel de lado a lado (el «velo» de D15) tapaba lo que pasaba a la altura de la cápsula y cortaba el contenido legible; en la portada no estaba, y ahí la cápsula se ve como un objeto sobre la página | El dueño pidió que en todas las páginas la barra deje ver lo que hay a su altura. Se quitó el velo: con la cápsula, la franja de la cabecera es transparente y no recibe el puntero en todas las páginas, así que lo de los lados se lee y se pulsa; solo la cápsula tapa lo que tiene detrás. Arriba de las demás páginas la cabecera abierta sigue con su papel, y sin JavaScript queda la cabecera fija de siempre. Una prueba impide que vuelva: ninguna regla de la cápsula puede darle fondo a la franja (ni a sus pseudoelementos), para todas las páginas o para algunas. `tests/test_cabecera_capsula.py` |

### Decisiones de la auditoría de código (C1 a C30, 2026-10-28 y 2026-10-29)

> Las tomó el dueño el 2026-10-28, al pasar `docs/auditoria-codigo.md` (commit `38fdf03`) a
> `docs/backlog-codigo.md`. Entre paréntesis, la ficha de la auditoría; en la última columna, los
> tickets del backlog que aplican cada decisión (su estado se sigue allí). Lo que se decidió
> diferir o no hacer está en §3.

| # | Decisión | Porqué | Se aplica en |
|---|---|---|---|
| C1 | Aún no hay producción: lo que fija direcciones, identificadores o permisos se corrige antes del lanzamiento y sin compatibilidad hacia atrás | Ningún enlace, suscriptor ni buscador depende todavía de ellos | B15, B28 |
| C2 | Rol editor: todo el contenido (textos, poemas, catálogo, medios, colectivo, propuestas, boletín, agenda, publicaciones, prensa y aliados), salvo el perfil del sitio y las cuentas. Rol autor: sus textos y sus poemas; puede añadir obras al catálogo, pero no editar las existentes. La matriz de roles vive en un módulo y se sincroniza de forma aditiva en cada release | Los permisos quedaron congelados en el primer commit, antes de que existieran la agenda, el escaparate y los poemas (AGE-2) | B15, B16 |
| C3 | Idioma del código: identificadores nuevos de Python (y de JavaScript) en inglés; castellano en los textos visibles y en el vocabulario del diseño, es decir, las clases CSS y los nombres de componentes como tirada, estante, pliego o cápsula, que se usan tal cual también dentro de nombres en inglés. Lo existente no se renombra, salvo los nombres trampa | No había regla, y ya había nombres gemelos con significados distintos (MAN-1) | B02, B77 |
| C4 | Copia de desarrollo: solo lo publicado, más una lista explícita de piezas de demostración del flujo editorial; solo los medios que algo usa; nombres ficticios evidentes en lugar de medios, fondos, librerías y editoriales reales. El historial de git no se reescribe | Va a un repositorio público y llevaba borradores y citas inventadas atribuidas a medios reales (HER-1, HER-2) | B07, B64 |
| C5 | La ficha de cada texto pasa de `/articulo/<slug>/` a `/texto/<slug>/`, sin redirección. Desde el lanzamiento, las rutas públicas son permanentes: renombrar una exige dejar la vieja con una redirección permanente | El sitio los llama «textos» y, antes de lanzar, renombrar no rompe nada (COM-12) | B02, B28 |
| C6 | El slug se puede editar mientras la pieza no es pública; una vez pública, es de solo lectura en el panel | Cambiarlo dejaba la dirección vieja en 404 y cambiaba el GUID de los feeds (COM-5) | B02, B28 |
| C7 | Subidas: audio hasta 50 MB, PDF hasta 20 MB e imágenes hasta 12 MB (JPEG, PNG o WebP). Los vídeos se publican solo con un enlace a YouTube o Vimeo | Caddy rechazaba todo lo que pasara de 12 MB, también en el panel, y un vídeo alojado ocupa disco, respaldo y un proceso del servidor mientras sube (OPE-5) | B08, B33 |
| C8 | Avisos: Sentry (plan gratuito) para los errores y un monitor externo tipo healthchecks.io para la caída del sitio y el latido de las tareas. Antes de definir `SENTRY_DSN`, la redacción de datos personales y secretos tiene que estar probada | Nadie se enteraba de un fallo, y la página de error prometía lo contrario (RES-6, RES-3) | B30, B31, B32 |
| C9 | Registros: un campo «Transcripción», visible junto al reproductor; el panel avisa, sin bloquear, si se publica un audio sin poema enlazado ni transcripción. Un poema sigue enlazando un solo registro | Alternativa en texto para el audio (WCAG 1.2.1) sin volverla una obligación para el equipo (COM-3) | B51 |
| C10 | Flujo editorial: vista previa de borradores para el equipo, «Desprogramar» (programada → aprobada) y «Reabrir» (rechazada → borrador). Programar exige una fecha, y publicar una pieza programada fija su fecha en el momento de publicar | Había que publicar para ver una pieza, una programada no se podía retirar y una rechazada no tenía salida (DOM-1, DOM-3) | B17, B18 |
| C11 | Se quitan los campos sin efecto: `featured` de Article, Poem, Event y PressMention, `ReviewedWork.is_primary`, `Work.language` y `nav_sections`. `Article.og_image` se conecta como imagen para compartir | El panel ofrecía controles que no cambiaban nada en el sitio (DAT-5, ARQ-5) | B25 |
| C12 | Una obra, una editorial o un autor de libro solo tienen ficha pública si algo publicado los respalda; una persona, si es integrante o tiene obra publicada. Lo demás responde 404 | Cualquier obra creada en el panel publicaba sus datos y la intención de reseñarla (WEB-1) | B14 |
| C13 | El original de cada imagen se reescribe siempre sin metadatos; si no se puede, la subida se rechaza con un mensaje claro | El control fallaba abierto y publicaba el GPS del original (RES-1) | B08 |
| C14 | En el panel, el estado y las fechas de consentimiento de un suscriptor no se editan a mano, y agregar a alguien a mano le envía la confirmación. Los envíos cambian de estado con acciones que registran la fecha | El doble opt-in es la base del consentimiento (D2 de producto), y el panel permitía saltárselo (DOM-5) | B39 |
| C15 | Cada transición editorial guarda el título de la pieza y el nombre de quien la hizo, y no se puede editar ni borrar | El «rastro inmutable» se borraba junto con la pieza (DOM-6) | B48 |
| C16 | El audio y los PDF de lo que no está publicado dejan de servirse: pasan por Django, que comprueba el estado | Despublicar no retiraba los archivos (DOM-4) | B37 |
| C17 | Con Redis caído, las vistas con límite de tasa siguen cerradas, pero con un mensaje veraz («no está disponible en este momento») | Fallar cerrado protege los formularios; el mensaje de «demasiados intentos» confundía (TAR-8, RES-9) | B36 |
| C18 | `SITE_URL` fijo y obligatorio en producción, sin `www` (si existe el DNS de `www`, redirige) | Las URL absolutas salían del Host de cada petición (COM-6) | B29 |
| C19 | Un servicio `release` del compose migra, sincroniza los roles y recoge los estáticos antes de arrancar web, worker y beat | El procedimiento arrancaba el código nuevo antes de migrar (OPE-1) | B06 |
| C20 | restic respalda los volúmenes directamente, sin tar.gz, y el CI prueba la restauración desde restic de punta a punta | La retención no borraba nada y no existía la restauración desde restic (OPE-3) | B05 |
| C21 | La galería se pagina como los demás índices | Cargaba todos los eventos con todas sus fotos (REN-6) | B76 |
| C22 | «Las voces» no lleva control de pausa (siguen D1 y D23 del rediseño); solo se corrige que el relevo reordene el DOM bajo el lector de pantalla | La decisión del dueño sigue en pie; el reordenamiento no lo cubría (COM-4) | B54 |
| C23 | Reabre «FTS por trigger de Postgres, no `GeneratedField`» y D3 (técnicas): una configuración de búsqueda sin tildes al indexar y al buscar, con un solo plegado de acentos. `GeneratedField` se prueba en una rama; si no sirve, el trigger se queda, con una prueba que lo ate al modelo | El motivo del trigger tiene un rodeo conocido, y D3 sumó un segundo plegado con otra semántica (DAT-3) | B50 |
| C24 | Reabre qa-21: la redacción de los eventos de Sentry se prueba con un transporte de prueba del SDK | Con `send_default_pii=False`, el SDK igual envía cuerpos, variables locales y cabeceras (RES-3) | B31 |
| C25 | Reabre «`CACHES` → Redis»: la caché va en un Redis aparte con `allkeys-lru`; `noeviction` queda solo para el broker | Ya hay una clave sin caducidad (D28 del rediseño), y el camino más probable a un Redis lleno es el propio broker (RES-5) | B36 |
| C26 | Modifica D16 del rediseño: se retira el panel del buscador para navegadores sin `:has()` (Firefox anterior a la versión 121, de diciembre de 2023) | Era peso muerto que complicaba la cascada de la cabecera (FRO-4) | B72 |
| C27 | Reabre en parte #33: prueba de humo en navegador y axe en el CI. Lighthouse y k6 siguen diferidos | Sin navegador en el CI, el JavaScript no se ejecutaba nunca y las garantías visuales eran búsquedas de texto (PRU-2, COM-2) | B11, B55 |
| C28 | Reabre «Extracción `SiteProfile` → app `siteconfig`» como una app del sitio para lo transversal, por etapas. Mover `SiteProfile` sigue diferido | El problema era más ancho que `SiteProfile`: `content` se había vuelto el núcleo implícito (ARQ-4) | B67 |
| C29 | «CD real» sigue diferido, con la premisa corregida: el VPS reconstruye la imagen y el CI no cargaba el compose de producción. El CI pasa a cargarlo | Lo que el CI probaba no era lo que se desplegaba (OPE-4) | B41 |
| C30 | Hasta el lanzamiento, un cambio de esquema puede ir en un solo paso; desde el lanzamiento, siempre en dos (primero añadir, después quitar). Tomada el 2026-10-29 | La regla de los dos pasos protege el código anterior mientras se despliega, y aún no hay producción ni código anterior corriendo (C1 no hablaba del esquema) | B25 |

---

## 2. Diferidos que dependen de INFRAESTRUCTURA del usuario

Estos esperan que el usuario provea DNS/SMTP/registry. Las partes que no necesitaban
infra ya se hicieron (se indican).

| Ítem | Qué falta | Cómo retomar |
|---|---|---|
| **Correo SMTP / deliverability** | Servidor SMTP real + **SPF/DKIM/DMARC** en DNS. La estructura MIME (`EmailMessage`) y la cabecera `List-Unsubscribe` **ya están** (`community/tasks.py`). | Configurar `EMAIL_HOST/PORT/USER/PASSWORD/USE_TLS` y `DEFAULT_FROM_EMAIL`; publicar SPF/DKIM/DMARC; smoke de entrega contra un buzón real. |
| **Respaldo off-site (restic)** | Un repo restic (S3/BackBlaze/rclone) + `RESTIC_REPOSITORY`/`RESTIC_PASSWORD`. El **roundtrip `pg_dump`/`pg_restore` ya se verifica en CI** (job `backup-restore`). | Definir el repo y las credenciales; `infra/backup/backup.sh` ya tiene la rama restic. Probar un `restic restore` real en staging (RTO/RPO). |
| **CD real** | Registry de contenedores + target de despliegue + rollback. | Job de release que taggee la imagen (`docker build --target prod`), la publique y despliegue con estrategia de rollback. El `build-prod` de CI construye y valida una imagen, pero el VPS reconstruye la suya y el CI no cargaba el compose de producción (C29). |
| **Alerta de fallo de respaldo (dead-man's-switch)** | `BACKUP_PING_URL` (healthchecks.io o similar). El script ya hace el ping OK/fail. | Definir la URL y probar que un fallo dispara la alerta. |

---

## 3. Diferidos por BAJO VALOR o esfuerzo desproporcionado

Decisiones conscientes de no hacer (aún); documentadas para no re-descubrir el análisis.

- **qa-21 — Test de captura de Sentry + ping de backup.** La integración de Sentry es
  *inline* en `config/settings.py` (opt-in por `SENTRY_DSN`). Un test con valor exigiría
  extraerla a una función (`init_sentry`) y mockear `sentry_sdk.init`; para algo que es
  opt-in estándar y bien entendido, el refactor no se justifica ahora. *Si se retoma:*
  extraer `init_sentry(dsn, debug)` y afirmar `send_default_pii=False` y
  `traces_sample_rate` por defecto (guardas de privacidad/costo). **Reabierto el
  2026-10-28 (C24).**

- **qa-23 — Test de DST + higiene de beat.** El `celerybeat-schedule` **ya está en
  `.gitignore`**. `publish_due_items` ya es **DST-safe por diseño** (compara `published_at`
  vs `timezone.now()` en UTC); un test con `freezegun` solo *confirmaría* eso, y añadir la
  dependencia no se justifica. El fallback htmx sin-JS ya se cubrió (qa-10).

- **#33 — a11y/rendimiento automatizados (pa11y/axe, Lighthouse, k6).** Requieren Node +
  un servidor corriendo en CI (setup propio). La a11y ya mejoró (qa-9) y hay aserciones
  estructurales con BeautifulSoup (qa-11). *Si se retoma:* `pa11y-ci` o `axe-core` sobre
  las páginas clave levantando la app; k6 nocturno con presupuesto p95 (empezar sin
  umbral bloqueante — D4). **Reabierto en parte el 2026-10-28 (C27):** la prueba de humo
  en navegador y axe; Lighthouse y k6 siguen aquí.

- **#27 — Restringir `/readyz` al monitor.** El endpoint está **diseñado para monitoreo
  externo de uptime**, así que restringirlo bien depende de la capa de monitoreo que se
  elija (token compartido, allowlist de IPs, o restricción en el proxy). Se aborda cuando
  se defina esa capa; hoy expone solo estado BD/broker (fuga menor, info). La capa quedó
  definida el 2026-10-28 (C8); restringir el endpoint sigue valiendo poco (RES-6 de la
  auditoría de código).

- **mypy + type hints incremental.** Bajo valor/alto esfuerzo a esta escala.

- **Extracción `SiteProfile` → app `siteconfig`.** Migración cross-app de 2 modelos + FKs;
  severidad baja (cohesión). Hacer aparte si el proyecto crece. **Reabierta en parte el
  2026-10-28 (C28):** la app del sitio se hace por etapas; mover `SiteProfile` sigue
  diferido hasta después de sus dos primeras etapas.

### De la auditoría de código (2026-10-28)

Lo que `docs/auditoria-codigo.md` recomendaba y el dueño decidió diferir o no hacer. Entre
paréntesis, la ficha de la auditoría y el ticket de `docs/backlog-codigo.md` que deja el resto hecho.

- **Fiabilidad del envío masivo del boletín.** Límites y `acks_late` por tarea, idempotencia de
  cada envío y reencolado tras un timeout. No hay envío masivo (D2 de producto). *Si se
  retoma:* al construirlo, con el punto 4 de TAR-1.
- **Sacar los tokens del boletín de la ruta** (que el enlace los canjee y redirija a una URL sin
  secreto). Con `Referrer-Policy: no-referrer` en esas páginas y la redacción probada (B30, B31),
  el token ya no sale por las cabeceras ni por Sentry. *Si se retoma:* con el envío masivo (RES-3).
- **Sustituir django-ratelimit.** El proyecto sigue en Django 5.2 LTS y una prueba de
  comportamiento lo protege. *Si se retoma:* antes de subir a Django 6 (OPE-8).
- **Segundo factor para entrar al panel (django-otp).** Hay pocas cuentas de staff, y axes
  bloqueará por usuario e IP (B34). *Si se retoma:* cuando crezcan las cuentas de autor (SEG-3).
- **Anonimizar a una persona con obra publicada.** El panel impedirá borrarla y pedirá
  reasignar sus textos (B46). *Si se retoma:* con el primer pedido real de supresión de datos o
  con la revisión legal (DAT-2).
- **Git LFS para los medios de desarrollo.** Hoy son 84 archivos y 5,7 MB. *Si se retoma:*
  cuando crezcan (HER-8).
- **Subtítulos `.vtt` y varias lecturas por poema.** Los vídeos se publican por enlace (C7) y un
  poema enlaza un solo registro (C9) (COM-3).
- **No se añade autoheal.** Reiniciar los contenedores enfermos exige montar el socket de
  Docker, que equivale a ser root en el anfitrión; el monitor externo (C8) avisa en su lugar
  (RES-6).
- **No se parte `settings.py` en módulos.** Basta un settings de pruebas explícito (B57; OPE-2).

---

## 4. Menores / nice-to-have pendientes

- **Portada de podcast cuadrada (`itunes:image`).** Para publicar el feed
  `/feed/registros/` en Apple Podcasts falta un asset cuadrado ≥1400px en `SiteProfile`.
  El namespace iTunes ya se emite (`media/feeds.py`).
- **Configurar la identidad del sitio en producción.** En desarrollo ya está:
  `tools/ux/preparar-entorno.sh` pone el nombre, el lema y las redes, y el comando
  `seed_material_generico`, que el mismo guion corre, la imagen para compartir (genérica). En
  una base nueva de producción hay que ponerlos en el panel (Perfil del sitio): afectan al
  título, al Open Graph y al JSON-LD.
- **Índice `Event(published, starts_at)`** y epigraph en el trigger FTS de Poem —
  micro-optimizaciones de la auditoría #2, sin impacto observado. (El `LIMIT` de la búsqueda
  ya viaja al SQL desde el hallazgo S-04, y `prefers-reduced-motion` se respeta desde el
  rediseño UX.)

### Del rediseño UX/UI (cierre, 2026-10-14)

Lo que la verificación (`git show 38fdf03:docs/auditoria-ux-ui-verificacion.md`) deja sin
cumplir, con su causa.
Los cuatro primeros son decisiones del dueño del sitio: no se «arreglan» sin preguntarle.

- **La portada mide 4092 px a 1440** (meta: 3300). Eligió conservar las publicaciones (paso 20).
- **Sin cifras en la portada** (#128): «aún somos un grupo pequeño». Están en el dossier.
- **Poca tinta en la primera pantalla de la portada** (16,5 %; meta: 50 %): sin planos de color
  ni bandas oscuras, que descartó al verlos (paso 13).
- **Cuatro índices de filas con poca tinta** (textos, agenda, trayectoria y aliados, entre 3 % y
  9 %; meta: 20 %). Subiría con más imágenes reales: miniaturas en textos, afiches en la agenda.
- **Monoespaciada y mayúsculas en la portada** (38 % y 26; metas: 30 % y 15). Casi la mitad eran
  los cargos de la cinta, que se repetía para dar la vuelta; sin ella (D22) la cifra baja, pero no
  se ha vuelto a medir.
- **El manifiesto del dossier a 49 letras por línea** (meta: 60 a 75), por ir al lado de la
  ficha. Si molesta, a todo el ancho del carril de lectura.
- **Los enlaces del pie, de 17 a 21 px de alto** (meta: 44). Cumplen WCAG 2.5.8 por separación;
  a 44 px el pie crecería, y el dueño lo quiere bajo.
- **En el teléfono, Textos y el dossier a dos toques**, dentro de «Menú» (paso 18).
- **La vista ampliada de las fotos sin «anterior» ni «siguiente»**: se cierra y se abre otra.
  Hacerlo sin JavaScript pide un enlace por lado en cada foto.
- **Sin comprobar con un lector de pantalla** (no hay uno en el entorno): cómo anuncia la región
  `aria-live` del panel de la lupa los resultados agrupados, y el orden de lectura de la vista
  ampliada.
- **LCP y CLS medidos en desarrollo**, con la red y la CPU estranguladas (2,1 s y 0). Repetir en
  la vista previa de producción, que comprime y cachea los estáticos.
- **Fotos, afiches y cubiertas reales**: el material es genérico hasta que el colectivo aporte el
  suyo (`docs/contenido-visual.md`).
- **El poema en prosa se compone como versos.** El dueño aprobó el cierre sin pedir otra cosa
  (2026-10-14): se queda así mientras no lo pida.
  Cada párrafo es una línea del cuerpo, así que la ficha le da la sangría francesa de un verso
  largo: la primera línea al margen y las siguientes adentro. Lo destapó el poema de prueba
  «Inventario del patio» (`seed_textos_largos`). La portada y el índice ya citan solo su
  arranque. Si se quiere componer como prosa, hay dos caminos: tratar como párrafo toda línea
  de más de unas 300 letras (una heurística: una oda de versos larguísimos tiene versos de 200),
  o que el poema diga que es en prosa, que pide un campo y una migración.
- **La división con guion de los títulos** depende del navegador: Safari, macOS, iOS y Android la
  traen en español; Chrome de escritorio descarga el diccionario la primera vez que lo necesita.
  Donde no la hay, una palabra muy larga en un título corto se sigue partiendo sin guion. Los
  títulos de más de noventa letras bajan un paso de tamaño en todos los navegadores.
- ~~**Páginas 404 y 500 con la identidad del sitio.**~~ **CERRADO** (`fix-paginas-error`,
  2026-09-02). El 404 pasa de 179 a 5117 bytes con cabecera, pie y cuatro salidas.

  Las dos plantillas se tratan **distinto a propósito**: 404.html extiende `base.html`
  —`page_not_found` renderiza con request y procesadores de contexto, y en un 404 el sitio
  está sano—, pero **500.html no hereda de nada**. `server_error` renderiza sin contexto, y
  el procesador `site_profile` hace `SiteProfile.load()`, una CONSULTA: la causa más común
  de un 500 es que la base no responda, así que una página de error que la consultara
  fallaría justo cuando se la necesita. La prueba usa `django_assert_num_queries(0)` para
  que nadie "unifique" ambas más adelante.

- ~~**Rótulos del panel a medias en inglés.**~~ **CERRADO** (`i18n-rotulos-panel`,
  2026-09-02). `verbose_name` en los AppConfig de content, people, reviews y community
  —que ni siquiera tenían `apps.py`—, en los nueve modelos de relación y auditoría, y en
  los campos que se leen como cabecera de la ficha. El índice queda entero en español.

  Se tradujo además la pantalla de bloqueo por intentos fallidos vía
  `AXES_LOCKOUT_TEMPLATE`, que era el rótulo sin traducir **más visible del proyecto**: no
  está en el panel sino en `/admin/login/`, y la veía cualquiera, no solo el equipo.

  **Residuo conocido:** la sección «Axes» y sus tres modelos siguen en inglés.
  `LANGUAGE_CODE = "es"` y `USE_I18N = True` están bien puestos; el motivo es que
  django-axes **no distribuye traducción al español** (trae ar, de, fa, fr, id, pl, ru,
  tr). Cerrarlo exigiría mantener un catálogo propio de una app de terceros que solo ve el
  superusuario. Se deja así a conciencia.

- ~~**La firma de archivo no distingue un `.docx` de un ZIP cualquiera.**~~ **CERRADO**
  (`fix-firma-zip`, 2026-09-02). Para docx y odt ya no basta la firma `PK`: se lee el
  ÍNDICE del contenedor y se exigen las piezas que el formato obliga a llevar
  —`[Content_Types].xml` y `word/document.xml`; `META-INF/manifest.xml` y `content.xml`—.

  Solo se llama a `namelist()`, es decir el directorio central: no se extrae ni se
  descomprime nada, así que un zip bomba no tiene por dónde entrar. Y el tamaño ya está
  acotado antes, porque `clean_file` comprueba extensión, luego tamaño y solo después
  contenido.

  La mitad que más importaba de las pruebas es la contraria: que un .docx y un .odt
  legítimos sigan entrando. Una validación más estricta que rechace envíos reales sería
  peor que la laxa.

- **El endurecimiento de permisos no alcanza a los respaldos ya existentes.** `backup.sh`
  aplica `umask 077` desde el lote sec-6, así que los respaldos NUEVOS quedan en `700`/`600`
  —verificado—. Pero los anteriores a esa corrección siguen como se crearon: en la máquina
  de desarrollo había tres directorios de julio en `755` con sus archivos en `644`, es
  decir el volcado completo de la base —correos de suscriptores, hashes de contraseñas— y
  los manuscritos, legibles por cualquier usuario local. Una corrección de permisos no es
  retroactiva y eso es fácil de pasar por alto: en un servidor real la exposición sobrevive
  a la remediación que supuestamente la cerró. Se cierra con `chmod -R go-rwx` sobre el
  directorio de respaldos, y conviene comprobarlo tras cualquier despliegue que cambie el
  usuario o el `umask` del sidecar. *Detectado en las pruebas manuales del §10, 2026-08-26;
  los del entorno local ya se ajustaron.*

- ~~**`Article` no tiene `get_absolute_url`.**~~ **CERRADO** (`fix-get-absolute-url`,
  2026-09-02). Añadido a Article, Page y Collection siguiendo el patrón de Poem, así que
  el panel vuelve a ofrecer «Ver en el sitio». La prueba sigue la redirección
  `/admin/r/<tipo>/<id>/` con sesión de staff y afirma dónde aterriza: que el método
  devolviera una cadena con buena pinta no bastaba.

- **test** — ruff, pip-audit, `makemigrations --check`, **reversibilidad de migraciones**,
  pytest con cobertura (piso 80% + **umbrales por-módulo** para sanitize/feeds/sitemaps),
  `check --deploy`.
- **build-prod** — build de la imagen prod + smoke gunicorn + **collectstatic DEBUG=0** +
  **trivy** (informativo).
- **security** — **gitleaks** (con `.gitleaks.toml`) + **bandit** + dependency-review
  (informativo).
- **prod-runtime** — levanta la imagen prod en DEBUG=0 y verifica cabeceras de seguridad,
  `/readyz`, estático hasheado y los healthchecks de web/worker/beat.
- **backup-restore** — roundtrip `pg_dump`/`pg_restore` del esquema real (DR).
