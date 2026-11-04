"""Reglas del sistema visual que solo fallan al pintar.

La suite no tiene navegador. Estas pruebas fijan sobre la hoja de estilos las decisiones
del rediseño UX (docs/deferidos-y-decisiones.md) cuyo incumplimiento no rompe nada salvo lo
que se ve: una cubierta deformada, un título con las líneas sueltas, una columna de lectura de
cien letras. Las cifras en pantalla se miden aparte, con tools/ux.

La hoja se lee con tests/css.py: cada regla se busca por su contexto (`()` es el nivel de
arriba; `("@media (min-width:900px)",)`, dentro de ese bloque) y por su selector.
"""

import re
from pathlib import Path

from tests import css

DESKTOP = ("@media (min-width:900px)",)
PHONE = ("@media (max-width:899px)",)
NARROW_PHONE = ("@media (max-width:719px)",)
PRINT = ("@media print",)
MOTION = ("@media (prefers-reduced-motion:no-preference)",)
WIDE_ROWS = ("@container filas (min-width:700px)",)
READING_ROOM = ("@media (min-width:840px)",)
FIXED_ANCHOR = ("@media (min-width:840px) and (min-height:700px)",)


def _screen_rules():
    """Las reglas de pantalla: sin la hoja de impresión, que pinta todo en blanco a propósito."""
    return [r for r in css.rules() if "@media print" not in r.context]


def _contexts_where(selector, name, value):
    """Los contextos en los que una regla con ese selector declara ese valor."""
    return {r.context for r in css.rules() if r.selector == selector and r.get(name) == value}


def _header_breakpoint():
    """El bloque desde el que la cabecera mide 64 px: el corte de la cabecera de escritorio."""
    contexts = _contexts_where(":root", "--alto-cabecera", "64px")
    assert len(contexts) == 1, f"la cabecera de escritorio no tiene un solo corte: {contexts}"
    return contexts.pop()


# ── Imágenes ──────────────────────────────────────────────────────────────


def test_las_imagenes_no_heredan_el_alto_del_atributo_html():
    """`_responsive_img.html` emite width y height para reservar el hueco de la imagen.

    Sin `height:auto` ese alto se aplica literal y gana a `aspect-ratio`: las cubiertas
    se dibujaban a 180×780 y las fotos apaisadas de la galería como tiras verticales.
    Ninguna otra prueba lo veía porque el HTML era correcto.
    """
    regla = css.rule((), "img, video")
    assert regla["height"] == "auto", "sin height:auto el alto del atributo HTML se aplica literal"
    assert regla["max-width"] == "100%", "una imagen más ancha que su caja desbordaría la página"


def test_toda_imagen_con_proporcion_forzada_deja_el_alto_en_auto():
    """Si una regla fija `aspect-ratio` sobre una imagen, el alto debe quedar libre."""
    con_proporcion = [
        r for r in css.rules() if "aspect-ratio" in r and re.search(r"\bimg\b", r.selector)
    ]
    assert con_proporcion, "ninguna regla fija ya la proporción de una imagen"
    sin_auto = [r.selector for r in con_proporcion if r.get("height") != "auto"]
    assert not sin_auto, f"reglas con aspect-ratio sobre <img> sin height:auto: {sin_auto}"


# ── Tipografía ────────────────────────────────────────────────────────────

# El glifo ▾ del desplegable del menú: es un adorno, no texto que haya que leer.
EXENTOS_DEL_MINIMO = {".nav-disclosure summary::after"}


def test_ningun_texto_baja_de_12px():
    """Nueve reglas pintaban texto a 11px; el mínimo legible del sistema es 12. Los tamaños
    son tokens: se resuelven antes de comparar."""
    tamanos = [
        (r.selector, tam)
        for r in css.rules()
        if r.selector not in EXENTOS_DEL_MINIMO and r.selector != "html"
        for tam in r.values("font-size")
        if not tam.endswith("pt")
    ]
    assert tamanos, "la prueba dejó de encontrar los tamaños de letra de la hoja"
    pequenos = [(sel, tam) for sel, tam in tamanos if css.px_range(tam)[0] < 12]
    assert not pequenos, f"texto por debajo de 12px: {pequenos}"


def test_la_escala_es_la_unica_fuente_de_tamanos():
    """Había 25 tamaños escritos a mano: 17, 18, 19 y 20 px convivían sin que ninguno
    significara nada. Ahora cada `font-size` es un paso de la escala. Quedan fuera el
    cuerpo base de `html`, que crece con el monitor y del que cuelgan los `rem`, y la hoja
    de impresión, que mide en puntos. Son diez pasos: --t7, que era el nombre de la portada
    hasta que pasó a ser el logo (D18), volvió como el título de los pliegos de la tirada (D19)."""
    sueltos = [
        (r.selector, tam)
        for r in css.rules()
        if r.selector != "html"
        for tam in r.values("font-size")
        if not re.fullmatch(r"var\(--t-?\d\)", tam) and not tam.endswith("pt")
    ]
    assert not sueltos, f"tamaños fuera de la escala: {sueltos}"
    escala = {nombre for nombre in css.tokens() if re.fullmatch(r"--t-?\d", nombre)}
    assert len(escala) == 10, f"la escala tiene {len(escala)} pasos: {sorted(escala)}"
    minimos = [
        css.px_range(f"var({nombre})")[0] for nombre in sorted(escala, key=lambda n: int(n[3:]))
    ]
    assert minimos == sorted(minimos), f"la escala no crece de paso en paso: {minimos}"


def test_un_titulo_de_seccion_no_mide_menos_que_el_texto_que_encabeza():
    """Los títulos de sección eran rótulos de 12 px sobre párrafos de 17. El cuerpo crece
    hasta 19 px (119 % del tamaño del navegador): el título de sección empieza por encima."""
    minimo, _ = css.px_range(css.rule((), ".subhead")["font-size"])
    assert minimo > 19, f"el título de sección arranca en {minimo}px, por debajo del cuerpo"
    familias = {r.get("font-family") for r in css.rules_with((), ".subhead")} - {None}
    assert familias == {"var(--display)"}, "el título de sección debe ir en la de titulares"


def test_los_titulos_no_heredan_la_interlinea_de_lectura():
    """El 1.6 del cuerpo es para leer párrafos; en un título separa sus líneas."""
    interlinea = css.rule((), "h1, h2, h3")["line-height"]
    assert re.fullmatch(r"var\(--[\w-]+\)", interlinea), (
        "los títulos fijan su interlínea con un token"
    )
    assert float(css.resolve(interlinea)) <= 1.2


def test_el_cuerpo_de_lectura_tiene_medida():
    """A 18px en 780px el artículo corría a 102 letras por línea; lo legible es 45–75."""
    medida = re.fullmatch(r"(\d+)ch", css.tokens().get("--medida", ""))
    assert medida, "falta el token --medida"
    assert 45 <= int(medida.group(1)) <= 66, "la medida en ch quedó fuera del rango de lectura"
    for selector in (".article .body", ".dek", ".member-about"):
        assert css.rule((), selector)["max-width"] == "var(--medida)", (
            f"«{selector}» perdió la medida"
        )


def test_el_poema_no_se_parte_con_guiones():
    """El guionado automático empareja la prosa; en un poema el corte es del autor."""
    estrecha = css.rule(("@media (max-width:600px)",), ".article .body, .dek")
    assert estrecha["hyphens"] == "auto", "ya no hay guionado en pantallas estrechas"
    con_guiones = [r.selector for r in css.rules() if r.get("hyphens") == "auto"]
    assert not [s for s in con_guiones if "poem" in s], "el guionado alcanza a los poemas"


# ── Componentes ───────────────────────────────────────────────────────────


def test_ningun_estado_hover_se_marca_bajando_la_opacidad():
    """Tres botones se atenuaban al pasar el ratón: el texto perdía contraste justo al ir
    a pulsarlo. El estado se marca con color sólido."""
    estados = [r for r in css.rules() if ":hover" in r.selector]
    assert estados, "la hoja ya no tiene estados :hover"
    atenuados = [r.selector for r in estados if "opacity" in r]
    assert not atenuados, f"estados hover por opacidad: {atenuados}"


def test_todo_boton_comparte_una_receta():
    """Había cinco botones con cinco recetas. El del formulario y el del reproductor
    heredan ahora la de `.btn`; ninguno vuelve a fijar su tipografía por su cuenta."""
    recetas = [r for r in css.rules_with((), ".btn") if "font-family" in r]
    assert len(recetas) == 1, "desapareció la regla común de los botones"
    receta = recetas[0]
    for boton in (".form button", ".embed-play"):
        assert boton in receta.selectors, f"«{boton}» ya no comparte la receta del botón"
    assert receta["min-height"] == "44px", "el botón perdió su alto mínimo de 44 px"
    assert receta["text-transform"] == "none", "el botón volvió a las mayúsculas"
    sueltos = [
        r.selector
        for r in css.rules()
        if r.selector != receta.selector
        and re.search(r"\.btn|button|embed-play", r.selector)
        and "font-family" in r
    ]
    assert not sueltos, f"botones con tipografía propia: {sueltos}"


# Reglas que pintan texto en mayúsculas fuera de la receta de rótulo. Estaba la navegación,
# como deuda con fecha: salió en el ticket 2.3, al pasar a la tipografía de titulares.
MAYUSCULAS_PENDIENTES = set()
# Excepciones con motivo, no deudas: un timbre de goma va en mayúsculas (D31, tablero aprobado).
MAYUSCULAS_PERMITIDAS = {".home-cierre .pie-entidad a"}


def test_las_mayusculas_son_una_sola_receta():
    """Quince reglas ponían texto en mayúsculas, con seis espaciados distintos."""
    con_mayusculas = {r.selector for r in css.rules() if r.get("text-transform") == "uppercase"}
    receta = {sel for sel in con_mayusculas if sel.startswith(".rotulo")}
    assert len(receta) == 1, f"debe haber exactamente una receta de rótulo: {receta}"
    extra = con_mayusculas - receta - MAYUSCULAS_PENDIENTES - MAYUSCULAS_PERMITIDAS
    assert not extra, f"mayúsculas fuera de la receta de rótulo: {extra}"
    espaciado = css.rule((), receta.pop())["letter-spacing"]
    assert re.fullmatch(r"var\(--[\w-]+\)", espaciado) and css.resolve(espaciado) == ".1em"


def test_el_movimiento_usa_los_tokens_y_respeta_a_quien_pide_menos():
    tokens = css.tokens()
    for token in ("--r-1", "--dur-fast", "--dur-base", "--ease", "--edge"):
        assert token in tokens, f"falta el token {token}"
    transiciones = [(r.selector, t) for r in css.rules() for t in r.values("transition")]
    assert transiciones, "la hoja ya no anima ningún cambio de estado"
    sueltas = [sel for sel, t in transiciones if "var(--dur-" not in t]
    assert not sueltas, f"transiciones con duración escrita a mano: {sueltas}"
    # La regla alcanza a todo (*), no a una lista de componentes.
    menos = css.rule(("@media (prefers-reduced-motion:reduce)",), "*, *::before, *::after")
    for propiedad in ("transition-duration", "animation-duration"):
        assert menos[propiedad] == ".01ms" and menos.is_important(propiedad), propiedad


def test_los_campos_tienen_un_borde_que_se_ve():
    """El borde de un campo lo delimita: WCAG 1.4.11 pide 3:1. `--border` da 1,17:1."""
    campos = (".search input", ".form input, .form textarea, .form select", ".search-page input")
    for selector in campos:
        assert css.rule((), selector)["border"] == "1px solid var(--edge)", (
            f"«{selector}» sin borde visible"
        )


def test_el_foco_se_ve_sobre_la_placa_del_reproductor():
    """El anillo magenta del sitio da 1,32:1 sobre el azul de la placa."""
    assert css.rule((), ".player-consent :focus-visible")["outline-color"] == "#fff"


def test_el_panel_de_busqueda_se_cierra_al_dejar_de_usarlo():
    regla = css.rule((), ".search:not(:focus-within):not(:hover) #search-results")
    assert regla["display"] == "none"


# ── Fuente de titulares ───────────────────────────────────────────────────


def test_la_fuente_de_titulares_tiene_reserva_metrica_y_no_cae_a_la_serif():
    """La reserva era la serif de lectura, un 24 % más estrecha: al cargar la fuente de
    titulares (entonces Syne) el nombre del sitio pasaba de 231 a 292 px y todo lo de
    alrededor saltaba. Hoy es Bricolage Grotesque, con su reserva medida."""
    pila = css.tokens()["--display"]
    assert css.split_commas(pila)[:2] == ('"Bricolage Grotesque"', '"Bricolage Fallback"'), pila
    assert "var(--serif)" not in pila
    reservas = [c for c in css.at_rules("font-face") if c["font-family"] == '"Bricolage Fallback"']
    assert len(reservas) >= 2, "la reserva necesita al menos una cara normal y una negrita"
    for cara in reservas:
        assert "size-adjust" in cara and cara["src"].startswith("local(")


# ── Lienzo: los tres carriles ─────────────────────────────────────────────


def test_el_lienzo_declara_sus_tres_carriles():
    """El sitio tenía un solo contenedor de 820 px para todo, y el texto ocupaba el 54 %
    de una pantalla de 1440. Los carriles son líneas con nombre de una rejilla."""
    carriles = css.tokens().get("--carriles")
    assert carriles, "falta la plantilla de columnas del lienzo"
    for linea in (
        "full-start",
        "wide-start",
        "content-start",
        "content-end",
        "wide-end",
        "full-end",
    ):
        assert f"[{linea}]" in carriles, f"falta la línea «{linea}»"
    assert css.rule((), ".lienzo")["grid-template-columns"] == "var(--carriles)"
    assert css.rule((), ".lienzo > *")["grid-column"] == "content", (
        "por defecto se cae en el carril de lectura"
    )
    assert css.rule((), ".lienzo--ancho > *")["grid-column"] == "wide"
    assert css.rule((), ".lienzo > .sangre, .lienzo > .band")["grid-column"] == "full"


def test_la_columna_de_lectura_no_se_ensancha():
    """Lo que crece es el lienzo, no la línea: lo legible son 45–75 letras, en cualquier
    monitor. El carril de lectura mide lo que medía el contenido de la caja de 820 px."""
    tokens = css.tokens()
    assert tokens["--measure"] == "780px"
    ancho = re.fullmatch(r"(\d+)px", tokens["--wide"])
    assert ancho and 1200 <= int(ancho.group(1)) <= 1440
    assert css.rule((), ".wrap")["max-width"] == "820px", "la caja de siempre conserva su valor"


def test_ningun_ancho_usa_unidades_de_viewport():
    """100vw incluye la barra de desplazamiento: en un navegador de escritorio produce
    scroll horizontal. Los márgenes del lienzo salen de pistas 1fr."""
    valores = [d.value for _, d in css.declarations()]
    assert any("vw" in v for v in valores), "la prueba dejó de leer los valores de la hoja"
    assert not [v for v in valores if "100vw" in v]


def test_el_carril_ancho_de_cabecera_y_pie_coincide_con_el_del_lienzo():
    """Cabecera y pie viven fuera de <main>: su carril debe medir lo mismo y empezar en la
    misma vertical, o el nombre del sitio no quedaría alineado con el contenido."""
    regla = css.rule((), ".wrap-wide")
    assert regla["max-width"] == "calc(var(--wide) + 2 * var(--gutter))"
    assert regla["padding-inline"] == "var(--gutter)"


# ── Filas, miniaturas y cubiertas (ticket 2.2) ────────────────────────────


def test_la_fila_entera_es_el_enlace_de_su_titulo():
    """Solo era pulsable el texto del título. Una capa del propio enlace cubre la fila;
    los enlaces secundarios (sección, firmas) quedan por encima y siguen siendo propios."""
    assert css.rule((), ".fila")["position"] == "relative"
    capa = css.rule((), ".fila-titulo a::after")
    assert capa["content"] == '""' and capa["position"] == "absolute"
    # Lo que se pulsa es lo que se ilumina: la hoja clara del estado de la fila.
    assert capa["inset"] == css.rule((), ".fila::before")["inset"]
    secundarios = css.rule((), ".fila .kicker a, .fila-pie a")
    assert secundarios["position"] == "relative" and secundarios["z-index"] == "1"
    assert secundarios["padding-block"] == "6px", "su zona de pulsado bajaría de 24 px"


def test_el_estado_de_la_fila_es_una_hoja_mas_clara_y_no_alcanza_a_las_que_no_enlazan():
    """Un hito no lleva a ninguna parte: su fila no debe prometerlo al pasar el puntero.
    El estado se pinta detrás del contenido (`isolation`) para no tapar el texto."""
    assert css.rule((), ".fila")["isolation"] == "isolate"
    assert css.rule((), ".fila::before")["z-index"] == "-1"
    estado = css.rule((), ".fila:has(.fila-titulo a):hover::before, .fila:focus-within::before")
    assert estado["background-color"] == "var(--paper-2)"
    sueltos = [
        r.selector
        for r in css.rules()
        if r.selector.startswith(".fila")
        and ":hover" in r.selector
        and any("paper-2" in d.value for d in r.declarations)
        and ":has(" not in r.selector
    ]
    assert not sueltos, f"filas que reaccionan aunque no enlacen: {sueltos}"


def test_las_filas_se_disponen_segun_el_ancho_de_su_lista():
    """La misma parcial vive en el carril ancho, en el de lectura y en un teléfono: manda
    el ancho de la lista, no el de la ventana."""
    assert css.rule((), ".filas")["container"] == "filas / inline-size"
    assert css.rule(WIDE_ROWS, ".fila")["grid-template-areas"] == '"fecha cuerpo pie"'
    assert css.rule((), ".fila")["grid-template-areas"] == '"cuerpo cuerpo" "pie fecha"', (
        "sin sitio, el título va arriba y los datos debajo"
    )


def test_en_el_carril_ancho_el_poema_ocupa_una_sola_linea():
    """Con el primer verso bajo el título cabían siete poemas por pantalla; en su propia
    columna caben diez. La última columna es fija: si dependiera del largo de cada firma,
    los versos empezarían en una vertical distinta en cada fila."""
    ancho = ("@container filas (min-width:1000px)",)
    assert css.rule(ancho, ".fila--poema .fila-cuerpo")["display"] == "grid"
    assert css.rule(ancho, ".fila--poema")["grid-template-columns"].endswith(" 15rem"), (
        "la columna de la firma debe tener ancho fijo"
    )
    verso = css.rule(ancho, ".fila--poema .fila-verso")
    assert verso["white-space"] == "nowrap" and verso["text-overflow"] == "ellipsis"


def test_el_filete_y_la_hoja_clara_son_tokens():
    tokens = css.tokens()
    assert re.fullmatch(r"#[0-9a-f]{6}", tokens["--paper-2"])
    assert re.fullmatch(r"#[0-9a-f]{6}", tokens["--line"]), (
        "falta el valor para quien no conoce color-mix()"
    )
    mejora = css.tokens(("@supports (color:color-mix(in srgb, #000 50%, transparent))",))
    assert mejora["--line"] == "color-mix(in srgb, var(--ink) 22%, transparent)"
    assert css.rule((), ".fila")["border-top"] == "1px solid var(--line)"


def test_la_cubierta_se_ensena_como_un_objeto():
    """Sin esquinas redondeadas y con sombra plana; al señalarla la sombra pasa al color
    de estado. Nada se mueve: el sitio solo anima color, fondo y borde."""
    cubierta = css.rule((), ".pub-card img, .pub-cover-fallback")
    assert cubierta["box-shadow"] == "8px 8px 0 var(--line)"
    assert "border-radius" not in cubierta
    assert cubierta["aspect-ratio"] == "5 / 7"
    senaladas = [
        r
        for r in css.rules_with((), ".pub-card a:hover img")
        if ".pub-card a:focus-visible img" in r.selectors
    ]
    assert len(senaladas) == 1 and senaladas[0]["box-shadow"] == "8px 8px 0 var(--accent)"
    assert "transform" not in senaladas[0]


def test_un_catalogo_corto_no_se_arrincona():
    """Con tres títulos en una rejilla de cinco columnas, el 40 % de la pantalla quedaba
    vacío a la derecha. Es una mejora: sin :has() queda la rejilla general."""
    cuatro = css.rule(DESKTOP, ".pub-grid:not(:has(> :nth-child(5)))")
    assert cuatro["grid-template-columns"] == "repeat(4, minmax(0, 1fr))"
    tres = css.rule(DESKTOP, ".lienzo > .pub-grid:not(:has(> :nth-child(4)))")
    assert tres["grid-template-columns"] == "repeat(3, minmax(0, 1fr))"
    general = css.rule(("@media (min-width:720px)",), ".pub-grid")
    assert general["grid-template-columns"] == "repeat(auto-fill, minmax(240px, 1fr))"


def test_la_miniatura_de_registro_es_16_9_y_lleva_marca_de_reproduccion():
    miniatura = css.rule((), ".rec-miniatura")
    assert miniatura["aspect-ratio"] == "16 / 9" and miniatura["background"] == "var(--caratula)"
    # El cartel va en posición absoluta: la marca necesita z-index o queda debajo.
    for capa in (".rec-miniatura::before", ".rec-miniatura::after"):
        assert css.rule((), capa)["z-index"] == "1", f"«{capa}» quedaría tapada por el cartel"
    assert css.rule((), ".recording-card h2 a::after")["inset"] == "0", (
        "la tarjeta entera es el enlace"
    )


def test_rejillas_que_reparten_el_ancho_entre_lo_que_haya():
    """`auto-fill` deja columnas vacías a la derecha cuando hay pocos elementos; con
    `auto-fit` los que hay se reparten la fila. El tope evita que uno solo se estire."""
    for lista, tarjeta in (
        (".recording-list", ".recording-card"),
        (".album-grid", ".album-card"),
    ):
        assert css.rule((), lista)["grid-template-columns"].startswith("repeat(auto-fit, "), (
            f"«{lista}» vuelve a dejar columnas vacías"
        )
        assert "max-width" in css.rule((), tarjeta), f"«{tarjeta}» se estiraría de lado a lado"
    assert css.rule((), ".event-list")["grid-template-columns"].startswith("repeat(auto-fit, ")


def test_la_hoja_de_contactos_fija_la_proporcion_en_la_hoja_no_en_cada_foto():
    hoja = css.rule((), ".hoja")
    assert hoja["grid-template-columns"] == "2fr 1fr" and hoja["aspect-ratio"] == "9 / 4"
    fotos = css.rule((), ".hoja img")
    assert fotos["height"] == "100%" and fotos["object-fit"] == "cover"
    assert "aspect-ratio" not in fotos


# ── Serif de lectura y monoespaciada (ticket 2.3) ─────────────────────────


def test_la_serif_de_lectura_es_propia_y_tiene_reserva_metrica():
    """La pila de sistema daba Palatino en un Mac, Times en Linux y Georgia en Windows: el
    sitio tenía tres voces. Ahora la serif viaja con el sitio, y mientras llega la ocupa una
    reserva escalada para que el texto no salte al cambiar."""
    pila = css.split_commas(css.tokens()["--serif"])
    assert pila[:2] == ('"RdV Serif"', '"RdV Serif Fallback"'), pila
    caras = css.at_rules("font-face")
    propias = [c for c in caras if c["font-family"] == '"RdV Serif"']
    estilos = sorted(cara["font-style"] for cara in propias)
    assert estilos == ["italic", "normal"], f"faltan la redonda o la cursiva: {estilos}"
    for cara in propias:
        assert cara["font-display"] == "swap" and re.search(
            r'url\("\.\./fonts/rdv-serif[\w-]*\.woff2"\)', cara["src"]
        )
    reservas = [c for c in caras if c["font-family"] == '"RdV Serif Fallback"']
    assert len(reservas) >= 3, "la reserva necesita redonda, negrita y cursiva"
    for cara in reservas:
        assert (
            "size-adjust" in cara
            and 'local("Liberation Serif' in cara["src"]
            and "ascent-override" in cara
        )


def test_ninguna_familia_lleva_el_nombre_reservado_de_la_fuente():
    """Source Serif 4 tiene «Source» como nombre reservado (OFL, cláusula 3): una versión
    modificada —y el subconjunto lo es— no puede llamarse así."""
    familias = [
        nombre
        for _, d in css.declarations()
        if d.name in ("font-family", "--serif", "--display", "--mono")
        for nombre in re.findall(r'"([^"]+)"', d.value)
    ]
    assert familias, "no se encontró ninguna familia declarada"
    assert not [f for f in familias if "source" in f.lower()], familias


# Reglas que pueden pintar en monoespaciada, cada una por su papel. Decisión D3: la mono
# queda para rótulos y datos; lo demás se lee en la serif o en la de titulares.
MONO_PERMITIDA = {
    ".rotulo, .kicker, .foot-group h2, .reviewed h2, .event-month, .tag, "
    ".nav-disclosure summary, .member-role, .foot-group-titulo": (
        "rótulo, también el cargo de cada integrante y los grupos del menú del teléfono"
    ),
    ".meta, .muted": "dato: firma, fecha, lugar",
    ".ejemplar-lomo-anio": "dato: el año en el lomo de una publicación del estante",
    ".stats-strip": "etiquetas de las cifras",
    ".pagination-pages a, .pagination-pages span": "números de página",
    ".lightbox figcaption": "pie de foto",
    ".article .body pre": "texto preformateado del autor: una partitura, una tabla hecha con espacios",
    ".article .body code": "código o un nombre de archivo dentro de un texto",
    ".htmx-indicator": "indicador de carga",
}


def test_la_monoespaciada_queda_en_rotulos_y_datos():
    """La navegación, el pie, los botones y las cifras iban en monoespaciada: la voz del
    sitio era la de un panel de control. Una regla nueva que la use tiene que justificarse
    aquí."""
    con_mono = {r.selector for r in css.rules() if r.get("font-family") == "var(--mono)"}
    assert con_mono, "la monoespaciada ya no está en ninguna regla"
    sobrantes = con_mono - set(MONO_PERMITIDA)
    assert not sobrantes, f"monoespaciada fuera de rótulos y datos: {sorted(sobrantes)}"
    assert "font-family" not in css.rule((), ".nav a"), (
        "la navegación toma la familia de los titulares"
    )
    familias = {r.get("font-family") for r in css.rules_with((), ".nav a")} - {None}
    assert familias == {"var(--display)"}
    assert "font-family" not in css.rule((), ".site-foot"), "el pie hereda la serif del cuerpo"


# ── Sala de lectura, fichas y pie (ticket 2.4) ────────────────────────────


def test_la_sala_de_lectura_pone_la_ancla_al_lado_solo_si_cabe():
    """Ancla y texto lado a lado desde 840 px de ventana: por debajo no caben y la ancla
    va encima. El reparto es 4:7; la línea sigue limitada por --medida."""
    assert css.rule((), ".lectura-sala")["grid-template-columns"] == "minmax(0, 1fr)"
    dos = css.rule(READING_ROOM, ".lectura-sala")
    assert dos["grid-template-columns"] == "minmax(220px, 4fr) minmax(0, 7fr)"
    assert css.rule(FIXED_ANCHOR, ".lectura-ancla")["position"] == "sticky"
    fija = {
        r.context
        for r in css.rules()
        if r.selector.startswith(".lectura-ancla") and r.get("position") == "sticky"
    }
    assert fija == {FIXED_ANCHOR}, "la ancla solo acompaña si hay alto para ella"


def test_un_bloque_preformateado_no_empuja_la_pagina():
    """Con sus líneas enteras, la partitura de un ensayo de prueba empujaba la página hacia
    los lados a cualquier ancho: el bloque se desplaza dentro de su caja."""
    bloque = css.rule((), ".article .body pre")
    assert bloque["max-width"] == "100%" and bloque["overflow-x"] == "auto"


def test_la_columna_ancla_que_no_cabe_se_desplaza_por_dentro():
    """Una columna ancla más alta que la pantalla (un título de doscientas letras, cuatro
    firmas, ocho etiquetas) dejaba su final fuera de la vista durante toda la lectura."""
    ancla = css.rule(FIXED_ANCHOR, ".lectura-ancla")
    assert ancla["max-height"] == "calc(100dvh - var(--alto-cabecera) - 2 * var(--s3))"
    assert ancla["overflow-y"] == "auto"


def test_un_titulo_larguisimo_baja_un_paso_y_se_divide_con_guion():
    """Unas diez letras caben por línea en la columna ancla: una palabra más larga se partía
    por la mitad y sin guion. Donde el navegador sabe dividir en español, divide."""
    assert css.rule((), ".lectura-ancla h1")["hyphens"] == "auto"
    assert css.rule((), ".poem .lectura-ancla h1.titulo-largo")["font-size"] == "var(--t5)"
    assert css.rule((), ".article .lectura-ancla h1.titulo-largo")["font-size"] == "var(--t4)"


def test_un_verso_largo_continua_con_sangria_francesa():
    """Sin sangría francesa, la continuación de un verso que no cabe se lee como un verso
    nuevo. El salto de estrofa mide una línea: el que dejó el autor."""
    verso = css.rule((), ".verso")
    for propiedad, valor in (
        ("display", "block"),
        ("white-space", "pre-wrap"),
        ("padding-left", "1.5em"),
    ):
        assert verso.get(propiedad) == valor, f"al verso le falta «{propiedad}:{valor}»"
    assert verso["text-indent"] == f"-{verso['padding-left']}", (
        "la primera línea no sale a la izquierda"
    )
    assert css.rule((), ".estrofa + .estrofa")["margin-top"] == "calc(var(--lh-verso) * 1em)"


def test_cada_salida_del_pie_se_pulsa_entera():
    assert css.rule((), ".pie-entidad li")["position"] == "relative"
    capa = css.rule((), ".pie-entidad a::after")
    assert capa["content"] == '""' and capa["inset"] == "0"


def test_los_retratos_nuevos_no_son_circulos():
    """El retrato es 4:5, como el del colectivo; el círculo es el avatar de una app de
    mensajería (ticket 3.6). En los listados era un círculo de 72 px."""
    for selector in (
        ".firma-retrato",
        ".ficha-retrato",
        ".ficha-monograma",
        ".retrato",
        ".monograma",
    ):
        assert "border-radius" not in css.rule((), selector), f"«{selector}» redondea el retrato"
    for selector in (".ficha-retrato", ".retrato"):
        assert css.rule((), selector)["aspect-ratio"] == "4 / 5", f"«{selector}» no es 4:5"
    circulos = [
        bloque for bloque, d in css.declarations() if d.name == "border-radius" and "50%" in d.value
    ]
    assert not circulos, "queda un círculo en la hoja"


# ── Superficies, tinta y amarillo (tickets 3.1 y 3.2) ─────────────────────

# Lo único que puede ir en blanco: los campos de formulario, lo que flota sobre la página
# y los objetos (retratos, cubiertas, logotipos), más el botón y la marca de reproducción
# que se apoyan en la placa azul del reproductor.
BLANCO_PERMITIDO = {
    ".search input",
    ".search-page input",
    ".newsletter input[type=email]",
    ".form input, .form textarea, .form select",
    "#search-results:not(:empty)",
    ".pub-card img, .pub-cover-fallback",
    ".embed-play",
    ".embed-play:hover::after",
    ".rec-miniatura::before",
    ".recording-card:hover .rec-miniatura::after, .recording-card:focus-within .rec-miniatura::after",
}


def _backgrounds(reglas):
    """(selector, fondo) de cada `background` y `background-color` de esas reglas."""
    return [
        (r.selector, d.value)
        for r in reglas
        for d in r.declarations
        if d.name in ("background", "background-color")
    ]


def test_el_blanco_es_para_campos_y_objetos():
    """Las bandas y cinco avisos eran cajas blancas: el mismo blanco que los campos y las
    cubiertas, así que la página no se distinguía de las cosas que lleva encima (D6)."""
    blancas = {
        selector
        for selector, fondo in _backgrounds(_screen_rules())
        if re.match(r"(var\(--surface\)|#fff\b|#ffffff\b|white\b)", fondo)
    }
    assert ".search input" in blancas, "la prueba dejó de encontrar los fondos blancos"
    assert not blancas - BLANCO_PERMITIDO, f"superficies blancas: {blancas - BLANCO_PERMITIDO}"


def test_los_avisos_son_hoja_clara_sin_borde():
    """La fecha de la agenda, la próxima actividad, el contacto del dossier, la obra reseñada
    y los mensajes eran cajas blancas con borde de 1 px. Pasan a la hoja clara; los que
    llevan filete a la izquierda lo conservan, porque marca, no encierra."""
    for selector in (".event-date", ".next-event", ".dossier-contact", ".reviewed", ".flash"):
        aviso = css.rule((), selector)
        assert aviso["background"] == "var(--paper-2)", f"«{selector}» no está en la hoja clara"
        assert "border" not in aviso, f"«{selector}» sigue encerrado"
        assert "border-radius" not in aviso, f"«{selector}» sigue siendo una caja redondeada"


def test_la_banda_es_la_hoja_clara_y_la_fila_senalada_sobre_ella_pasa_al_papel():
    assert css.rule((), ".band")["background"] == "var(--paper-2)"
    # La hoja clara es también la fila señalada: sobre una banda, el estado sería invisible.
    estado = css.rule(
        (), ".band .fila:has(.fila-titulo a):hover::before, .band .fila:focus-within::before"
    )
    assert estado["background-color"] == "var(--paper)"


# Lo único que puede pintar un fondo de tinta: los botones y sus estados, el filete de
# 3 px que firma el territorio de prensa (una línea, no una superficie) y el pie.
TINTA_PERMITIDA = {
    ".btn:hover",
    ".index-head[data-territorio] h1::after, .seccion-cabeza[data-territorio] h2::after",
    ".btn--primary, .form button",
    ".pagination-pages a:hover",
    ".sello-convocatoria:hover",
    ".site-foot",
}


def test_la_tinta_como_superficie_es_solo_del_pie():
    """El registro destacado fue una banda de tinta de borde a borde. El dueño del sitio la
    descartó porque rompía la portada: la tinta como superficie queda para el pie."""
    con_tinta = {
        selector
        for selector, fondo in _backgrounds(_screen_rules())
        if fondo.startswith("var(--ink)")
    }
    assert ".site-foot" in con_tinta, "la prueba dejó de encontrar el fondo de tinta del pie"
    assert not con_tinta - TINTA_PERMITIDA, f"fondos de tinta: {con_tinta - TINTA_PERMITIDA}"


def test_la_placa_del_reproductor_fija_el_blanco_de_sus_datos():
    """El gris de `.meta` no se lee sobre el azul de la placa (2,12:1 con el de la tinta).
    Sin JavaScript la placa enseña un enlace al proveedor, que también es un dato."""
    assert css.rule((), ".player-consent .meta, .player-consent .meta a")["color"] == "#fff"


def test_el_pie_es_de_tinta():
    pie = css.rule((), ".site-foot")
    assert pie["background"] == "var(--ink)" and pie["color"] == "var(--muted-on-ink)"
    assert css.rule((), ".site-foot a")["color"] == "var(--paper)"
    assert css.rule((), ".site-foot :focus-visible")["outline-color"] == "var(--paper)"
    boton = css.rule((), ".site-foot .btn")
    assert boton["border-color"] == "var(--paper)" and boton["color"] == "var(--paper)"
    # Sin filete: la tinta ya separa el pie de la página.
    assert "border-top" not in pie


def test_al_imprimir_las_fotos_a_una_tinta_no_salen_en_blanco():
    """El duotono aclara la foto en gris sobre un fondo azul (`screen`), y el navegador no
    imprime los fondos: sobre el blanco de la hoja, la foto aclarada salía en blanco. Lo
    medido: los doce retratos de /integrantes/ impresos eran doce cajas vacías."""
    foto = css.rule(PRINT, ".riso-duo img")
    assert foto["filter"] == "none" and foto["mix-blend-mode"] == "normal"
    assert css.rule(PRINT, ".riso-duo::after")["content"] == "none"


def test_el_amarillo_es_el_trazo_de_las_cifras_del_dossier_y_nunca_texto():
    """El amarillo del cartel da 1,03:1 sobre el papel: solo puede entrar como fondo. Fue un
    plano de lado a lado del carril, que el dueño del sitio encontró invasivo, y después un
    trazo de marcador bajo las cifras de la portada (D5). Las quitó de la portada
    (2026-10-14) y el trazo pasó a las cifras del dossier (ticket 5.1): la mitad baja del
    número y no un plano. Los lomos del estante de la portada llevan el color de su tapa
    (D28): si es amarilla, el lomo también, pero no por el CSS. Y desde D31, la segunda tinta
    corrida de dos sellos de «Prensa y gestión»: un trazo fino de desregistro, no un plano (el
    dueño lo aprobó con el tablero)."""
    con_amarillo = {
        r.selector
        for r in _screen_rules()
        if r.selector != ":root" and any("riso-amarillo" in d.value for d in r.declarations)
    }
    assert con_amarillo == {
        ".dossier-cifras strong",
        ".home-cierre .pie-entidad li:nth-child(3)",
        ".home-cierre .pie-entidad li:nth-child(4)",
    }, f"el amarillo se salió del trazo: {con_amarillo}"
    trazo = css.rule((), ".dossier-cifras strong")
    assert trazo["background"].startswith(
        "linear-gradient(to top, transparent .06em, var(--riso-amarillo) .06em, "
    )
    assert trazo["print-color-adjust"] == "exact", "el trazo tiene que salir también en papel"
    como_texto = [
        b for b, d in css.declarations() if d.name == "color" and "riso-amarillo" in d.value
    ]
    assert not como_texto, "el amarillo del cartel no se lee como texto"


def test_la_firma_de_territorio_es_un_filete_de_tres_pixeles():
    """La misma en las cabeceras de índice y en las secciones de la portada (ticket 4.3):
    un solo selector por color, para que no se separen."""
    firma = css.rule(
        (), ".index-head[data-territorio] h1::after, .seccion-cabeza[data-territorio] h2::after"
    )
    assert firma["height"] == "3px" and firma["background-color"] == "var(--ink)"
    obra = css.rule(
        (),
        '.index-head[data-territorio="obra"] h1::after, '
        '.seccion-cabeza[data-territorio="obra"] h2::after',
    )
    assert obra["background-color"] == "var(--accent)"
    colectivo = css.rule(
        (),
        '.index-head[data-territorio="colectivo"] h1::after, '
        '.seccion-cabeza[data-territorio="colectivo"] h2::after',
    )
    assert colectivo["background-color"] == "var(--caratula)"


def test_el_sello_de_convocatoria_esta_quieto():
    """Un timbre girado, no un aviso que se mueve: nada que distraiga de leer."""
    assert css.rule((), ".sello-convocatoria")["transform"] == "rotate(-3deg)"
    for sello in (r for r in css.rules() if ".sello-convocatoria" in r.selectors):
        assert not [d.name for d in sello.declarations if d.name.startswith("animation")]
        assert not [d for d in sello.declarations if "riso-amarillo" in d.value]


# ── Ajustes tras la revisión del paso 13 ──────────────────────────────────


def test_el_pie_queda_abajo_en_una_pagina_corta():
    """En una página corta el pie terminaba a media altura y dejaba papel debajo: con el
    pie en tinta, un hueco. La página mide al menos la ventana y el lienzo crece."""
    cuerpo = css.rule((), "body")
    for propiedad, valor in (
        ("display", "flex"),
        ("flex-direction", "column"),
        ("min-height", "100dvh"),
    ):
        assert cuerpo.get(propiedad) == valor, f"a `body` le falta «{propiedad}:{valor}»"
    lienzo = css.rule((), ".lienzo")
    assert lienzo["flex"] == "1 0 auto", "el lienzo no crece hasta el pie"
    assert lienzo["align-content"] == "start", "el alto sobrante separaría las filas del lienzo"
    assert css.rule((), ".wrap-wide")["width"] == "100%", (
        "en una columna flexible, un hijo con margen automático se encoge a su contenido"
    )


def test_el_pie_usa_el_ancho_para_medir_menos_de_alto():
    """Medía 435 px a 951 de ancho. El orden es el del ticket 4.4 (la identidad, el mapa, el
    boletín y lo legal) sin volver a subir el alto: desde 900 px la identidad va al lado de
    los grupos y el boletín comparte línea con lo legal; desde 1100, todo en una fila. Entre
    720 y 899 la identidad va sola en su línea: al lado de los grupos, se salían."""
    rejillas = {
        (): '"identidad" "mapa" "news" "legal"',
        ("@media (min-width:720px)",): '"identidad identidad" "mapa mapa" "news legal"',
        DESKTOP: '"identidad mapa mapa" "news news legal"',
        ("@media (min-width:1100px)",): '"identidad mapa news" "identidad mapa legal"',
    }
    for contexto, areas in rejillas.items():
        assert css.rule(contexto, ".site-foot > .wrap-wide")["grid-template-areas"] == areas
    grupos = css.rule(("@media (min-width:720px)",), ".foot-groups")
    assert grupos["grid-template-columns"] == "repeat(4, max-content)", (
        "los cuatro grupos, a la medida de su contenido"
    )


def test_el_sello_del_pie_va_en_blanco_como_el_de_la_cabecera():
    """La regla de los enlaces del pie pinta los enlaces en el color del papel: el sello es
    un enlace y quedaba en ese azul claro sobre el magenta."""
    assert css.rule((), ".site-foot .brand")["color"] == "#fff"


def test_la_tirada_sin_js_es_una_fila_y_con_js_una_pila_que_se_mueve_si_se_puede():
    """La tirada (D19): sin JavaScript, un carril nativo con imán y la barra a la vista. Con
    JavaScript, la pila (D20): todos los pliegos en la misma celda, corridos desde el de
    arriba, y el gesto horizontal para el guion. Al cambiar de registro cambian las tintas
    (registradas con @property) y los pliegos se corren a su lugar (la excepción a «solo
    color» que se aprobó con la pila), solo para quien no pidió menos movimiento. El magenta es
    un estado: lo lleva el pliego de arriba, nunca uno en reposo."""
    carril = css.rule((), ".tirada-carril")
    for propiedad, valor in (
        ("overflow-x", "auto"),
        ("scroll-snap-type", "x mandatory"),
        ("scrollbar-width", "thin"),
    ):
        assert carril.get(propiedad) == valor, propiedad
    registradas = {a.prelude for a in css.at_rules("property")}
    for tinta in ("--tinta", "--sobre", "--trama", "--marca", "--sello"):
        assert tinta in registradas, f"la tinta {tinta} no está registrada"
    transicion = css.rule(MOTION, ".tirada.con-js .pliego")["transition"]
    propiedades = {item.split()[0] for item in css.split_commas(transicion)}
    assert propiedades <= {
        "--tinta",
        "--trama",
        "--marca",
        "--sello",
        "--sobre",
        "border-color",
        "outline-color",
        "translate",
        "rotate",
    }
    pila = css.rule((), ".tirada.con-js .pliego")
    assert pila["grid-area"] == "1 / 1" and pila["translate"] == "calc(66px + var(--x)) var(--y)"
    assert css.rule((), ".tirada.con-js .tirada-pista")["touch-action"] == "pan-y pinch-zoom"
    assert "grid-area" not in css.rule((), ".pliego"), (
        "sin JavaScript, la tirada sigue siendo una fila"
    )
    animadas = [
        (r.context, r.selector)
        for r in _screen_rules()
        if "pliego" in r.selector and any("translate" in t for t in r.values("transition"))
    ]
    assert animadas == [(MOTION, ".tirada.con-js .pliego")], (
        "el acomodo solo se anima con movimiento permitido"
    )
    sobre = [r.selector for r in css.rules() if r.get("--sobre") == "var(--accent)"]
    assert sobre == [".tirada.con-js .pliego[aria-current]"]
    assert css.rule((), ".pliego-titulo")["font-size"] == "var(--t7)"


def test_en_la_portada_el_poster_de_la_tirada_se_queda_a_una_tinta():
    """Decisión 3 del tablero de los registros: al señalar o enfocar un pliego, el póster no
    pasa al original a color (eso queda para la ficha)."""
    senalan = [
        r.selector for r in css.rules() if ".riso-duo" in r.selector and r.get("filter") == "none"
    ]
    assert senalan and not any("pliego" in sel or "tirada" in sel for sel in senalan)


# ── Duotono y retratos (tickets 3.3 y 3.6) ────────────────────────────────


def test_el_duotono_es_una_tinta_sobre_el_papel():
    """La tinta va de fondo, la foto en gris se aclara encima y el papel se multiplica por
    arriba: cada gris cae entre la tinta y el papel. Una sola tinta en todo el sitio, el
    azul del cartel; sin `isolation` la mezcla alcanzaría lo que hay detrás de la foto."""
    duo = css.rule((), ".riso-duo")
    assert duo["isolation"] == "isolate" and duo["background-color"] == "var(--caratula)"
    foto = css.rule((), ".riso-duo img")
    assert "grayscale(1)" in foto["filter"].split() and foto["mix-blend-mode"] == "screen"
    papel = css.rule((), ".riso-duo::after")
    assert papel["mix-blend-mode"] == "multiply" and papel["background-color"] == "var(--paper)"
    assert papel["pointer-events"] == "none", "la capa del papel no puede tapar el enlace"
    # La tinta es el fondo de las reglas del duotono que no son la capa del papel.
    tintas = {
        tinta.group(1)
        for r in css.rules()
        if "riso-duo" in r.selector and "::after" not in r.selector
        for fondo in r.values("background-color")
        if (tinta := re.fullmatch(r"var\((--[\w-]+)\)", fondo))
    }
    assert tintas == {"--caratula"}, f"más de una tinta de duotono: {tintas}"


def test_al_senalar_o_enfocar_se_ve_el_original():
    """Hay que quitar a la vez el filtro y la mezcla: si solo se quita uno, el original sale
    teñido. Y la capa del papel se vuelve transparente. Una sola regla con `:is()` dice
    dónde se señala: un enlace, las tarjetas, la placa, una fila. Solo la imagen señalada:
    la cinta (retirada en D22) las pintaba todas a la vez."""
    lugares = {"a", ".recording-card", ".event-card", ".player-consent", ".fila", ".next-event"}
    estado = ":is(:hover, :focus-within)"
    for capa, propiedad, valor in (
        (".riso-duo img", "filter", "none"),
        (".riso-duo::after", "background-color", "transparent"),
    ):
        reglas = [
            r for r in css.rules() if r.context == () and r.selector.endswith(f"{estado} {capa}")
        ]
        assert len(reglas) == 1, f"«{capa}» no tiene una sola regla de estado: {reglas}"
        donde = reglas[0].selector.removeprefix(":is(").split(")")[0].split(", ")
        assert lugares <= set(donde), reglas[0].selector
        assert reglas[0][propiedad] == valor
        if capa == ".riso-duo img":
            assert reglas[0]["mix-blend-mode"] == "normal"


# El duotono va en las imágenes de los listados: tarjetas de integrante (también las de la
# portada, D23), hoja de
# contactos, pósters de los registros (índice y placa, D10), imágenes de los textos y afiches
# de la agenda, la trayectoria y la próxima actividad de la portada. Las cubiertas de las
# publicaciones, los logos y las fichas se ven tal cual.
CON_DUOTONO = {
    "_member_card.html",
    "_member_card_portada.html",
    "gallery.html",
    "_player.html",
    "recording_index.html",
    "_article_card.html",
    "_event_card.html",
    "trayectoria.html",
    "home.html",
    # La placa y la hoja de contactos de la tirada de registros (D19).
    "_tirada.html",
}


def test_el_duotono_solo_va_en_los_listados():
    plantillas = Path(__file__).resolve().parent.parent / "templates"
    con_duo = {p.name for p in plantillas.rglob("*.html") if "riso-duo" in p.read_text("utf-8")}
    assert con_duo == CON_DUOTONO, f"duotono en: {sorted(con_duo)}"


def test_toda_la_tarjeta_de_integrante_es_el_enlace():
    """El rol y la reseña quedaban fuera del enlace: la capa del enlace cubre la tarjeta."""
    assert css.rule((), ".member-card")["position"] == "relative"
    capa = css.rule((), ".member-card > a::after")
    assert capa["content"] == '""' and capa["inset"] == "0"


# ── Reproductor: póster o carátula (ticket 3.4, D10) ──────────────────────


def test_el_mando_de_la_placa_es_un_panel_solido_con_la_marca_del_indice():
    """El aviso tiene que leerse sobre cualquier póster: va en un panel del azul de la
    placa. El botón es la marca de reproducción del índice, cuadrada (sin círculos)."""
    mando = css.rule((), ".player-mando")
    assert mando["position"] == "absolute" and mando["bottom"] == "0"
    aviso = css.rule((), ".embed-note")
    assert aviso["background"] == "var(--caratula)" and aviso["color"] == "#fff"
    boton = css.rule((), ".embed-play")
    assert boton["width"] == "64px" and boton["border-radius"] == "0"
    assert css.rule((), ".embed-play::after")["clip-path"].startswith("polygon("), (
        "el botón perdió su triángulo"
    )
    # El foco va por dentro del botón blanco: fuera quedaría sobre el póster, a 1,2:1.
    foco = css.rule((), ".player-consent .embed-play:focus-visible")
    assert foco["outline-offset"].startswith("-") and "var(--caratula-rotulo)" in foco["outline"]


def test_la_placa_no_tiene_marco_ni_esquinas():
    placa = css.rule((), ".player-frame")
    assert "border-radius" not in placa and "border" not in placa
    assert placa["container"] == "placa / inline-size", (
        "el título de la carátula crece con la placa"
    )


# ── Las imágenes del modelo en los listados (ticket 3.5) ──────────────────


def test_la_miniatura_de_una_fila_es_un_area_de_su_rejilla():
    """No un flotante: en una lista estrecha va junto al título, con la fecha debajo; con
    sitio, es la última columna. Se alinea arriba, no por la línea base del texto."""
    assert (
        css.rule((), ".fila--con-miniatura")["grid-template-areas"] == '"cuerpo mini" "pie fecha"'
    )
    ancha = css.rule(WIDE_ROWS, ".fila--con-miniatura")
    assert ancha["grid-template-areas"] == '"fecha cuerpo pie mini"'
    miniatura = css.rule((), ".fila-miniatura")
    assert miniatura["grid-area"] == "mini" and miniatura["align-self"] == "start"
    assert css.rule((), ".fila-miniatura img")["aspect-ratio"] == "3 / 4"


def test_los_logos_se_imprimen_en_gris_y_toman_color_al_senalar():
    """Multiplicados con el papel, el fondo blanco de un logo desaparece; en gris hasta que
    se señalan, el mismo gesto que las fotos a una tinta."""
    logo = css.rule((), ".partner-logo")
    for propiedad, valor in (
        ("width", "160px"),
        ("height", "80px"),
        ("object-fit", "contain"),
        ("filter", "grayscale(1)"),
        ("mix-blend-mode", "multiply"),
    ):
        assert logo.get(propiedad) == valor, f"al logo le falta «{propiedad}:{valor}»"
    senalado = css.rule(
        (), ".partner-item:hover .partner-logo, .partner-item:focus-within .partner-logo"
    )
    assert senalado["filter"] == "none"


def test_un_aliado_sin_logo_no_se_oscurece_al_mezclarse_con_el_papel():
    """La caja sin logo es la hoja clara: multiplicada con el papel, quedaba más oscura que
    él. Va sin mezcla ni filtro, y con su nombre en la tipografía de titulares."""
    caja = css.rule((), ".partner-logo--texto")
    for propiedad, valor in (
        ("mix-blend-mode", "normal"),
        ("filter", "none"),
        ("background", "var(--paper-2)"),
    ):
        assert caja.get(propiedad) == valor, f"a la caja le falta «{propiedad}:{valor}»"
    assert caja["font-family"] == "var(--display)"


# ── La ficha de un evento y sus fotos (ticket 5.2) ────────────────────────


def test_el_afiche_llega_a_420_px_si_al_texto_le_quedan_360():
    ficha = css.rule(("@media (min-width:720px)",), ".ficha-cabecera--afiche")
    assert ficha["grid-template-columns"] == "minmax(200px, 420px) minmax(360px, 1fr)"
    assert css.rule((), ".ficha-afiche")["box-shadow"] == "8px 8px 0 var(--line)", (
        "el afiche no es un objeto"
    )


def test_el_mosaico_no_deja_huecos_con_ninguna_cantidad_de_fotos():
    """Seis columnas: tercios por defecto; la primera a doble tamaño con tres fotos o con
    seis o más; a medias con dos o cuatro, y las dos primeras con cinco; a todo el ancho
    con una."""
    rejilla = css.rule((), ".photo-grid, .photo-grid-resto")
    assert rejilla["grid-template-columns"] == "repeat(6, minmax(0, 1fr))"
    celda = css.rule((), ".photo-grid > li, .photo-grid-resto > li")
    assert celda["grid-column"] == "span 2" and celda["aspect-ratio"] == "3 / 2"
    assert css.rule((), ".photo-grid > li:only-child")["grid-column"] == "1 / -1"
    medias = css.rule(
        (),
        ".photo-grid:has(> :nth-child(2):last-child) > li, "
        ".photo-grid:has(> :nth-child(4):last-child) > li, "
        ".photo-grid:has(> :nth-child(5):last-child) > li:nth-child(-n+2)",
    )
    assert medias["grid-column"] == "span 3"
    doble = css.rule(
        (),
        ".photo-grid:has(> :nth-child(3):last-child) > li:first-child, "
        ".photo-grid:has(> :nth-child(6)) > li:first-child",
    )
    assert doble["grid-column"] == "span 4" and doble["grid-row"] == "span 2"


def test_la_regla_de_las_miniaturas_no_alcanza_a_la_vista_ampliada():
    """`.photo-grid img` también recortaba a 8:5 la foto ampliada, que está dentro de la
    misma lista: no se veía entera. Las reglas del mosaico van por hijos directos."""
    selectores = {s for r in css.rules() for s in r.selectors}
    assert ".photo-grid img" not in selectores and ".photo-grid a" not in selectores
    miniatura = css.rule((), ".photo-grid > li > a img, .photo-grid-resto > li > a img")
    assert miniatura["object-fit"] == "cover"


def test_la_vista_ampliada_cubre_toda_la_pantalla():
    """Una <figure> trae márgenes (40 px a los lados): la capa no llegaba a los bordes y la
    foto quedaba corrida."""
    capa = css.rule((), ".lightbox")
    assert capa["position"] == "fixed" and capa["inset"] == "0" and capa["margin"] == "0"


def test_el_pie_de_la_vista_ampliada_se_lee():
    """Contador, pie y crédito a 13 px: a 12 era la letra más pequeña del sitio."""
    assert css.rule((), ".lightbox figcaption")["font-size"] == "var(--t-1)"


# ── La marca (ticket 3.7, con lo que eligió el dueño) ─────────────────────


def test_el_sello_de_la_cabecera_sigue_siendo_magenta_con_su_monograma():
    """El dueño se quedó con el sello magenta y le añadió el monograma RV dentro."""
    sello = css.rule((), ".brand")
    assert sello["background"] == "var(--accent)" and sello["color"] == "#fff"
    assert sello["display"] == "inline-flex", "el monograma y el nombre van en una fila"
    assert css.rule((), ".brand-mono-r")["fill"] == "#fff"
    assert css.rule((), ".brand-mono-v")["fill"] == "var(--celeste)"


# ── Cabecera de una fila (ticket 4.1) ─────────────────────────────────────


def test_la_cabecera_es_fija_y_lo_fijo_queda_debajo_de_ella():
    """La cabecera se queda arriba al bajar. Su alto es un token: la ancla de la lectura,
    el año de la trayectoria y el salto a un ancla lo usan para no quedar tapados."""
    cabecera = css.rule((), ".masthead")
    assert cabecera["position"] == "sticky" and cabecera["top"] == "0"
    assert "--alto-cabecera" in css.tokens()
    assert css.rule((), "html")["scroll-padding-top"].startswith("calc(var(--alto-cabecera)")
    # Todo lo fijo, también lo que se añada mañana: no solo los que hay hoy.
    fijos = [r for r in css.rules() if r.get("position") == "sticky"]
    assert {r.selector for r in fijos} >= {".masthead", ".lectura-ancla", ".year-mark"}
    for regla in fijos:
        if regla.selector == ".portada-arte":
            # La obra de la portada (D18) va bajo la franja a propósito: arriba de la portada
            # la franja está vacía. Lo que no debe quedar tapado es la hoja, que no es fija.
            assert regla["top"] == "0"
        elif regla.selector != ".masthead":
            assert regla.get("top", "").startswith("calc(var(--alto-cabecera)"), (
                f"«{regla.selector}» quedaría tapado por la cabecera fija"
            )


def test_los_enlaces_de_la_barra_se_pulsan_en_44_px():
    """Los enlaces de la barra y de la sub-fila del colectivo miden 44 px de alto o más. Cada
    uno es un elemento de una fila flexible, así que mide su línea (la letra por la
    interlínea) más el relleno de arriba y de abajo; la marca de la página actual es un
    subrayado, que va con el texto. Los de la cabecera los mide además la prueba de humo."""
    interlinea = css.rule((), "body")["line-height"]
    for fila, enlace in ((".nav", ".nav a"), (".subnav", ".subnav a")):
        assert css.rule((), fila)["display"] == "flex", (
            f"«{enlace}» ya no está en una fila flexible"
        )
        regla = css.rule((), enlace)
        letra, _ = css.px_range(regla["font-size"])
        linea = float(css.resolve(regla.get("line-height", interlinea)))
        relleno = [css.px_range(v)[0] for v in regla["padding-block"].split()]
        alto = letra * linea + relleno[0] + relleno[-1]
        assert alto >= 44, f"«{enlace}» mide {alto:.1f} px de alto"


def test_el_subrayado_de_la_pagina_actual_no_alcanza_al_separador():
    actual = css.rule((), ".nav a[aria-current], .subnav a[aria-current]")
    assert actual["text-decoration-thickness"] == "2px"
    assert css.rule((), ".nav a:not(:last-child)::after")["display"] == "inline-block", (
        "sin inline-block, el punto separador hereda el subrayado de la página actual"
    )


def test_en_el_telefono_el_boton_del_dossier_se_guarda_en_el_menu():
    """El botón le gana a la regla general de `.btn` solo con `.masthead` delante."""
    assert css.rule(PHONE, ".masthead .masthead-cta")["display"] == "none"


def test_la_cabecera_del_telefono_llega_hasta_donde_cabe_la_fila_entera():
    """La fila entera (sello, cinco enlaces, lupa y «Dossier») pide unos 880 px de ventana:
    con el corte en 720, a 768 y a 820 el botón quedaba fuera de la pantalla. Los dos cortes
    se tocan, para que ningún ancho se quede con las dos cabeceras o sin ninguna. En el
    teléfono los huecos son de 8 px: con los de 24, a 320 px «Menú» no cabía."""
    telefonos = _contexts_where(".masthead .masthead-cta", "display", "none")
    assert len(telefonos) == 1, f"el botón se guarda en más de un corte: {telefonos}"
    (telefono,) = telefonos
    hasta = re.fullmatch(r"@media \(max-width:(\d+)px\)", " ".join(telefono))
    desde = re.fullmatch(r"@media \(min-width:(\d+)px\)", " ".join(_header_breakpoint()))
    assert hasta and desde, (telefono, _header_breakpoint())
    assert int(hasta[1]) + 1 == int(desde[1]), "un ancho con dos cabeceras, o sin ninguna"
    assert int(desde[1]) >= 880, "la fila entera no cabe por debajo de unos 880 px"
    assert css.rule(telefono, ".masthead-fila")["column-gap"] == "8px"


def test_en_el_telefono_menu_va_en_tinta_como_la_lupa():
    """La receta de los rótulos, más abajo en la hoja, lo dejaba en gris: con `.masthead`
    delante gana la regla de la cabecera, y el magenta queda para el paso del ratón y para
    cuando está abierto, como en la lupa."""
    menu = css.rule(PHONE, ".masthead .nav-disclosure summary")
    assert menu["color"] == "var(--ink)", "«Menú» se queda en el gris de los rótulos"
    estado = css.rule(
        PHONE, ".masthead .nav-disclosure summary:hover, .masthead .nav-disclosure[open] summary"
    )
    assert estado["color"] == "var(--accent)"


def test_el_campo_del_buscador_ocupa_su_panel():
    """El «…» de htmx, invisible mientras no se busca, le quitaba al campo 35 px: va en el
    margen del panel. El panel acaba donde el botón «Dossier», no en el borde de la ventana."""
    assert css.rule((), ".search input")["flex"] == "1"
    assert css.rule((), ".busqueda .htmx-indicator")["position"] == "absolute"
    assert css.rule((), ".busqueda .search")["right"] == "var(--gutter)"


# ── Titular de la portada (ticket 4.2, la opción A del dueño) ─────────────


def test_la_obra_de_la_portada_llega_a_lo_alto_y_deja_asomar_la_hoja():
    """La portada como obra (D18): la obra sube bajo la franja vacía de la cabecera y se
    detiene antes del borde, donde asoma la hoja. Alto mínimo y no fijo: con el zoom al
    400 % nada se recorta. svh, con vh para quien no lo conoce."""
    obra = css.rule((), ".portada-arte")
    assert obra["margin-top"] == "calc(-1 * var(--alto-cabecera))"
    assert obra.values("min-height") == (
        "max(460px, 100vh - var(--asomo))",
        "max(460px, 100svh - var(--asomo))",
    )
    assert "height" not in obra, "un alto fijo recortaría la obra"
    assert not [d.name for d in obra.declarations if d.name.startswith("overflow")]
    assert obra["background"] == "var(--paper)", "sin la imagen, el papel"
    assert css.tokens()["--asomo"] == "112px"
    assert css.tokens(NARROW_PHONE)["--asomo"] == "96px"
    assert css.rule((), ".portada-imagen img")["object-fit"] == "cover"
    # Con un aviso entre la cabecera y <main>, la obra empieza debajo y no lo tapa.
    assert css.rule((), ".mensajes + .lienzo > .portada-arte")["margin-top"] == "0"


def test_el_logo_de_la_portada_va_en_tinta_sobreimpreso():
    """El logo cruza la obra al pie, de lado a lado, multiplicado como una plancha de riso. En
    el teléfono pasa a la versión en dos líneas."""
    mancheta = css.rule((), ".portada-mancheta")
    for propiedad, valor in (
        ("left", "var(--gutter)"),
        ("right", "var(--gutter)"),
        ("mix-blend-mode", "multiply"),
    ):
        assert mancheta.get(propiedad) == valor, propiedad
    assert css.rule((), ".portada-logo")["color"] == "var(--ink)"
    assert css.rule((), ".portada-logo svg")["width"] == "100%"
    assert css.rule(NARROW_PHONE, ".portada-logo .logo-horizontal")["display"] == "none"
    assert css.rule(NARROW_PHONE, ".portada-logo .logo-apilado")["display"] == "block"
    forzados = css.rule(("@media (forced-colors:active)",), ".portada-mancheta")
    assert forzados["background"] == "Canvas"


def test_el_telon_solo_con_movimiento_y_si_la_obra_cabe():
    """La obra se queda quieta y la hoja sube encima, solo para quien no pide menos
    movimiento y en una ventana donde la obra cabe entera: más alta que la ventana, quieta
    arriba, su pie no se vería nunca."""
    telon = ("@media (prefers-reduced-motion:no-preference) and (min-height:460px)",)
    obra = css.rule(telon, ".portada-arte")
    assert obra["position"] == "sticky" and obra["top"] == "0"
    assert css.rule(telon, ".portada-arte:focus-within")["z-index"] == "2"
    assert _contexts_where(".portada-arte", "position", "sticky") == {telon}, (
        "la obra solo es fija dentro de su bloque"
    )
    hoja = css.rule((), ".portada-telon")
    for propiedad, valor in (
        ("position", "relative"),
        ("z-index", "1"),
        ("background", "var(--paper)"),
        ("grid-template-columns", "var(--carriles)"),
    ):
        assert hoja.get(propiedad) == valor, propiedad


def test_el_boton_del_titular_se_oculta_donde_aparece_el_de_la_cabecera():
    """Un solo botón principal por pantalla: el dossier del titular se oculta en el mismo
    ancho en el que la cabecera enseña el suyo."""
    assert css.rule(_header_breakpoint(), ".hero-dossier")["display"] == "none"


# ── La portada completa (ticket 4.3) ──────────────────────────────────────


def test_la_obra_va_a_dos_columnas_solo_con_poemas_y_textos():
    """Con una sola de las dos listas va a todo el ancho: en media columna quedaba un hueco."""
    assert css.rule(DESKTOP, ".home-obra-columnas:has(> :nth-child(2))")["display"] == "grid"


def test_las_puertas_del_cierre_van_en_una_fila_sin_huecos():
    """Una columna por puerta desde 900 px, tres o cuatro según haya correo: en la rejilla de
    tres, «Escríbenos» quedaba sola en la segunda fila. En el teléfono, de dos en dos."""
    assert css.rule(DESKTOP, ".home-cierre .pie-entidad ul")["grid-auto-flow"] == "column"
    puertas = css.rule((), ".home-cierre .pie-entidad ul")
    assert puertas["grid-template-columns"] == "repeat(2, minmax(0, 1fr))"


def test_hidden_attribute_beats_any_author_display():
    """`hidden` oculta siempre: sin `!important`, el `display` de un componente (flex, grid,
    el de `.btn`) le gana al del navegador. La prueba de humo mide en el navegador que los
    componentes ocultos con el atributo no se ven."""
    oculto = css.rule((), "[hidden]")
    assert oculto.declarations == (css.Declaration("display", "none", important=True),)
