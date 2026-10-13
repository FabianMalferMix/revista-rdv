"""Reglas del sistema visual que solo fallan al pintar.

La suite no tiene navegador. Estas pruebas fijan sobre la hoja de estilos las decisiones
del backlog UX (docs/backlog-ux-ui.md) cuyo incumplimiento no rompe nada salvo lo que se
ve: una cubierta deformada, un título con las líneas sueltas, una columna de lectura de
cien letras. Las cifras en pantalla se miden aparte, con tools/ux.
"""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "site.css"


def _css():
    """La hoja sin comentarios: varios citan llaves y selectores a modo de ejemplo."""
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)


def _reglas():
    """(selector, declaraciones sin espacios) de cada regla, también dentro de @media."""
    return [
        (selector.strip(), re.sub(r"\s+", "", cuerpo))
        for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", _css())
    ]


def _tokens():
    """Las variables de :root con su valor, sin espacios: {"--t2": "19px", ...}."""
    raiz = re.search(r":root\{(.*?)\n\}", _css(), re.S).group(1)
    return {
        nombre: re.sub(r"\s+", "", valor)
        for nombre, valor in re.findall(r"(--[\w-]+):([^;]+);", raiz)
    }


def _px(valor):
    """Valor de un tamaño en px, resolviendo un token. Para un clamp(), (mínimo, máximo)."""
    valor = re.sub(r"\s+", "", valor)
    token = re.fullmatch(r"var\((--[\w-]+)\)", valor)
    if token:
        valor = _tokens()[token.group(1)]
    pinza = re.fullmatch(r"clamp\(([\d.]+)px,[^,]+,([\d.]+)px\)", valor)
    if pinza:
        return float(pinza.group(1)), float(pinza.group(2))
    fijo = re.fullmatch(r"([\d.]+)px", valor)
    assert fijo, f"tamaño que no sé leer: {valor}"
    return float(fijo.group(1)), float(fijo.group(1))


def _regla(selector):
    """La PRIMERA regla con ese selector: la de pantalla. Las que la sobrescriben dentro
    de un @media (impresión, pantalla estrecha) vienen después en la hoja."""
    encontradas = [cuerpo for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel) == selector]
    assert encontradas, f"no existe la regla «{selector}» en site.css"
    return encontradas[0]


# ── Imágenes ──────────────────────────────────────────────────────────────


def test_las_imagenes_no_heredan_el_alto_del_atributo_html():
    """`_responsive_img.html` emite width y height para reservar el hueco de la imagen.

    Sin `height:auto` ese alto se aplica literal y gana a `aspect-ratio`: las cubiertas
    se dibujaban a 180×780 y las fotos apaisadas de la galería como tiras verticales.
    Ninguna otra prueba lo veía porque el HTML era correcto.
    """
    cuerpo = _regla("img,video")
    assert "height:auto" in cuerpo, "sin height:auto el alto del atributo HTML se aplica literal"
    assert "max-width:100%" in cuerpo, "una imagen más ancha que su caja desbordaría la página"


def test_toda_imagen_con_proporcion_forzada_deja_el_alto_en_auto():
    """Si una regla fija `aspect-ratio` sobre una imagen, el alto debe quedar libre."""
    sin_auto = [
        selector
        for selector, cuerpo in _reglas()
        if "aspect-ratio" in cuerpo
        and re.search(r"\bimg\b", selector)
        and "height:auto" not in cuerpo
    ]
    assert not sin_auto, f"reglas con aspect-ratio sobre <img> sin height:auto: {sin_auto}"


# ── Tipografía ────────────────────────────────────────────────────────────

# El glifo ▾ del desplegable del menú: es un adorno, no texto que haya que leer.
EXENTOS_DEL_MINIMO = {".nav-disclosure summary::after"}


def test_ningun_texto_baja_de_12px():
    """Nueve reglas pintaban texto a 11px; el mínimo legible del sistema es 12. Los tamaños
    son tokens: se resuelven antes de comparar."""
    pequenos = [
        (selector, tam)
        for selector, cuerpo in _reglas()
        if selector not in EXENTOS_DEL_MINIMO and selector != "html"
        for tam in re.findall(r"font-size:([^;]+)", cuerpo)
        if not tam.endswith("pt") and _px(tam)[0] < 12
    ]
    assert not pequenos, f"texto por debajo de 12px: {pequenos}"


def test_la_escala_es_la_unica_fuente_de_tamanos():
    """Había 25 tamaños escritos a mano: 17, 18, 19 y 20 px convivían sin que ninguno
    significara nada. Ahora cada `font-size` es un paso de la escala. Quedan fuera el
    cuerpo base de `html`, que crece con el monitor y del que cuelgan los `rem`, y la hoja
    de impresión, que mide en puntos."""
    sueltos = [
        (selector, tam)
        for selector, cuerpo in _reglas()
        if selector != "html"
        for tam in re.findall(r"font-size:([^;]+)", cuerpo)
        if not re.fullmatch(r"var\(--t-?\d\)", tam) and not tam.endswith("pt")
    ]
    assert not sueltos, f"tamaños fuera de la escala: {sueltos}"
    escala = {
        nombre: valor for nombre, valor in _tokens().items() if re.fullmatch(r"--t-?\d", nombre)
    }
    assert len(escala) == 10, f"la escala tiene {len(escala)} pasos: {sorted(escala)}"
    minimos = [_px(f"var({nombre})")[0] for nombre in sorted(escala, key=lambda n: int(n[3:]))]
    assert minimos == sorted(minimos), f"la escala no crece de paso en paso: {minimos}"


def test_un_titulo_de_seccion_no_mide_menos_que_el_texto_que_encabeza():
    """Los títulos de sección eran rótulos de 12 px sobre párrafos de 17. El cuerpo crece
    hasta 19 px (119 % del tamaño del navegador): el título de sección empieza por encima."""
    minimo, _ = _px(re.search(r"font-size:([^;]+)", _regla(".subhead")).group(1))
    assert minimo > 19, f"el título de sección arranca en {minimo}px, por debajo del cuerpo"
    titulares = next(sel for sel, cuerpo in _reglas() if "font-family:var(--display)" in cuerpo)
    assert ".subhead" in titulares, "el título de sección debe ir en la tipografía de titulares"


def test_los_titulos_no_heredan_la_interlinea_de_lectura():
    """El 1.6 del cuerpo es para leer párrafos; en un título separa sus líneas."""
    interlinea = re.search(r"line-height:var\((--[\w-]+)\)", _regla("h1,h2,h3"))
    assert interlinea, "los títulos deben fijar su interlínea con un token"
    assert float(_tokens()[interlinea.group(1)]) <= 1.2


def test_el_cuerpo_de_lectura_tiene_medida():
    """A 18px en 780px el artículo corría a 102 letras por línea; lo legible es 45–75."""
    medida = re.search(r"--medida:\s*(\d+)ch", _css())
    assert medida, "falta el token --medida"
    assert 45 <= int(medida.group(1)) <= 66, "la medida en ch quedó fuera del rango de lectura"
    for selector in (".article.body", ".dek", ".member-about", ".rec-sumario"):
        assert "max-width:var(--medida)" in _regla(selector), f"«{selector}» perdió la medida"


def test_el_poema_no_se_parte_con_guiones():
    """El guionado automático empareja la prosa; en un poema el corte es del autor."""
    con_guiones = [selector for selector, cuerpo in _reglas() if "hyphens:auto" in cuerpo]
    assert con_guiones, "ya no hay guionado en pantallas estrechas"
    assert not [s for s in con_guiones if "poem" in s], "el guionado alcanza a los poemas"


# ── Componentes ───────────────────────────────────────────────────────────


def test_ningun_estado_hover_se_marca_bajando_la_opacidad():
    """Tres botones se atenuaban al pasar el ratón: el texto perdía contraste justo al ir
    a pulsarlo. El estado se marca con color sólido."""
    atenuados = [sel for sel, cuerpo in _reglas() if ":hover" in sel and "opacity:" in cuerpo]
    assert not atenuados, f"estados hover por opacidad: {atenuados}"


def test_todo_boton_comparte_una_receta():
    """Había cinco botones con cinco recetas. El del formulario y el del reproductor
    heredan ahora la de `.btn`; ninguno vuelve a fijar su tipografía por su cuenta."""
    receta = [
        (sel, cuerpo) for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel).startswith(".btn,")
    ]
    assert receta, "desapareció la regla común de los botones"
    selector, cuerpo = receta[0]
    for boton in (".btn", ".form button", ".embed-play"):
        assert boton in selector, f"«{boton}» ya no comparte la receta del botón"
    assert "min-height:44px" in cuerpo, "el botón perdió su alto mínimo de 44 px"
    assert "text-transform:none" in cuerpo, "el botón volvió a las mayúsculas"
    sueltos = [
        sel
        for sel, cuerpo in _reglas()
        if sel != selector
        and re.search(r"\.btn|button|embed-play", sel)
        and "font-family" in cuerpo
    ]
    assert not sueltos, f"botones con tipografía propia: {sueltos}"


# Reglas que pintan texto en mayúsculas fuera de la receta de rótulo. Estaba la navegación,
# como deuda con fecha: salió en el ticket 2.3, al pasar a la tipografía de titulares.
MAYUSCULAS_PENDIENTES = set()


def test_las_mayusculas_son_una_sola_receta():
    """Quince reglas ponían texto en mayúsculas, con seis espaciados distintos."""
    con_mayusculas = {sel for sel, cuerpo in _reglas() if "text-transform:uppercase" in cuerpo}
    receta = {sel for sel in con_mayusculas if sel.startswith(".rotulo")}
    assert len(receta) == 1, f"debe haber exactamente una receta de rótulo: {receta}"
    extra = con_mayusculas - receta - MAYUSCULAS_PENDIENTES
    assert not extra, f"mayúsculas fuera de la receta de rótulo: {extra}"
    espaciado = re.search(r"letter-spacing:var\((--[\w-]+)\)", dict(_reglas())[receta.pop()])
    assert espaciado and _tokens()[espaciado.group(1)] == ".1em"


def test_el_movimiento_usa_los_tokens_y_respeta_a_quien_pide_menos():
    css = _css()
    for token in ("--r-1:", "--dur-fast:", "--dur-base:", "--ease:", "--edge:"):
        assert token in css, f"falta el token {token}"
    sueltas = [
        (sel, cuerpo)
        for sel, cuerpo in _reglas()
        if "transition:" in cuerpo and "var(--dur-" not in cuerpo
    ]
    assert not sueltas, f"transiciones con duración escrita a mano: {[s for s, _ in sueltas]}"
    menos = re.search(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\n\}", css, re.S)
    assert menos, "falta el bloque global de prefers-reduced-motion"
    assert re.search(r"\*,\s*\*::before,\s*\*::after\{", menos.group(1)), (
        "el bloque debe alcanzar a todo (*), no a una lista de componentes"
    )


def test_los_campos_tienen_un_borde_que_se_ve():
    """El borde de un campo lo delimita: WCAG 1.4.11 pide 3:1. `--border` da 1,17:1."""
    campos = (".search input", ".form input, .form textarea, .form select", ".search-page input")
    for selector in campos:
        cuerpos = [cuerpo for sel, cuerpo in _reglas() if sel == selector]
        assert any("border:1pxsolidvar(--edge)" in c for c in cuerpos), (
            f"«{selector}» sin borde visible"
        )


def test_el_foco_se_ve_sobre_la_placa_del_reproductor():
    """El anillo magenta del sitio da 1,32:1 sobre el azul de la placa."""
    assert "outline-color:#fff" in _regla(".player-consent:focus-visible")


def test_el_panel_de_busqueda_se_cierra_al_dejar_de_usarlo():
    regla = _regla(".search:not(:focus-within):not(:hover)#search-results")
    assert "display:none" in regla


# ── Fuente de titulares ───────────────────────────────────────────────────


def test_syne_tiene_reserva_metrica_y_no_cae_a_la_serif():
    """La reserva era la serif de lectura, un 24 % más estrecha: al cargar Syne el nombre
    del sitio pasaba de 231 a 292 px y todo lo de alrededor saltaba."""
    css = _css()
    pila = re.search(r"--display:([^;]+);", css).group(1)
    assert '"Syne Fallback"' in pila and "var(--serif)" not in pila
    reservas = re.findall(r'@font-face\{[^}]*"Syne Fallback"[^}]*\}', css)
    assert len(reservas) >= 2, "la reserva necesita al menos una cara normal y una negrita"
    for cara in reservas:
        assert "size-adjust:" in cara and "local(" in cara


# ── Lienzo: los tres carriles ─────────────────────────────────────────────


def test_el_lienzo_declara_sus_tres_carriles():
    """El sitio tenía un solo contenedor de 820 px para todo, y el texto ocupaba el 54 %
    de una pantalla de 1440. Los carriles son líneas con nombre de una rejilla."""
    carriles = re.search(r"--carriles:([^;]+);", _css())
    assert carriles, "falta la plantilla de columnas del lienzo"
    for linea in (
        "full-start",
        "wide-start",
        "content-start",
        "content-end",
        "wide-end",
        "full-end",
    ):
        assert f"[{linea}]" in carriles.group(1), f"falta la línea «{linea}»"
    assert "grid-template-columns:var(--carriles)" in _regla(".lienzo")
    assert "grid-column:content" in _regla(".lienzo>*"), (
        "por defecto se cae en el carril de lectura"
    )
    assert "grid-column:wide" in _regla(".lienzo--ancho>*")
    assert "grid-column:full" in _regla(".lienzo>.sangre,.lienzo>.band")


def test_la_columna_de_lectura_no_se_ensancha():
    """Lo que crece es el lienzo, no la línea: lo legible son 45–75 letras, en cualquier
    monitor. El carril de lectura mide lo que medía el contenido de la caja de 820 px."""
    css = _css()
    assert re.search(r"--measure:\s*780px", css)
    ancho = re.search(r"--wide:\s*(\d+)px", css)
    assert ancho and 1200 <= int(ancho.group(1)) <= 1440
    assert "max-width:820px" in _regla(".wrap"), "la caja de siempre conserva su valor"


def test_ningun_ancho_usa_unidades_de_viewport():
    """100vw incluye la barra de desplazamiento: en un navegador de escritorio produce
    scroll horizontal. Los márgenes del lienzo salen de pistas 1fr."""
    assert "100vw" not in _css()


def test_las_bandas_no_pintan_su_fondo_con_una_sombra():
    """La banda vivía dentro de la caja estrecha y sacaba su fondo hacia fuera con una
    sombra de 100vmax recortada con clip-path. Ahora ocupa el carril a sangre."""
    banda = _regla(".band")
    assert "box-shadow" not in banda and "clip-path" not in banda
    assert "100vmax" not in _css()


def test_el_carril_ancho_de_cabecera_y_pie_coincide_con_el_del_lienzo():
    """Cabecera y pie viven fuera de <main>: su carril debe medir lo mismo y empezar en la
    misma vertical, o el nombre del sitio no quedaría alineado con el contenido."""
    regla = _regla(".wrap-wide")
    assert "max-width:calc(var(--wide)+2*var(--gutter))" in regla
    assert "padding-inline:var(--gutter)" in regla


# ── Filas, miniaturas y cubiertas (ticket 2.2) ────────────────────────────


def _bloque(cabecera):
    """Las reglas de dentro de un bloque @ (media, container), como texto sin espacios."""
    css = _css()
    inicio = css.index(cabecera)
    abre = css.index("{", inicio)
    nivel, i = 1, abre + 1
    while nivel:
        nivel += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return re.sub(r"\s+", "", css[abre + 1 : i - 1])


def test_la_fila_entera_es_el_enlace_de_su_titulo():
    """Solo era pulsable el texto del título. Una capa del propio enlace cubre la fila;
    los enlaces secundarios (sección, firmas) quedan por encima y siguen siendo propios."""
    assert "position:relative" in _regla(".fila")
    capa = _regla(".fila-tituloa::after")
    assert 'content:""' in capa and "position:absolute" in capa and "inset:0" in capa
    secundarios = _regla(".fila.kickera,.fila-piea")
    assert "position:relative" in secundarios and "z-index:1" in secundarios
    assert "padding-block:6px" in secundarios, "su zona de pulsado bajaría de 24 px"


def test_el_estado_de_la_fila_es_una_hoja_mas_clara_y_no_alcanza_a_las_que_no_enlazan():
    """Un hito no lleva a ninguna parte: su fila no debe prometerlo al pasar el puntero.
    El estado se pinta detrás del contenido (`isolation`) para no tapar el texto."""
    assert "isolation:isolate" in _regla(".fila")
    assert "z-index:-1" in _regla(".fila::before")
    estado = _regla(".fila:has(.fila-tituloa):hover::before,.fila:focus-within::before")
    assert "background-color:var(--paper-2)" in estado
    sueltos = [
        sel
        for sel, cuerpo in _reglas()
        if sel.startswith(".fila")
        and ":hover" in sel
        and "paper-2" in cuerpo
        and ":has(" not in sel
    ]
    assert not sueltos, f"filas que reaccionan aunque no enlacen: {sueltos}"


def test_las_filas_se_disponen_segun_el_ancho_de_su_lista():
    """La misma parcial vive en el carril ancho, en el de lectura y en un teléfono: manda
    el ancho de la lista, no el de la ventana."""
    assert "container:filas/inline-size" in _regla(".filas")
    tres_columnas = _bloque("@container filas (min-width:700px)")
    assert 'grid-template-areas:"fechacuerpopie"' in tres_columnas
    apilada = _regla(".fila")
    assert 'grid-template-areas:"cuerpocuerpo""piefecha"' in apilada, (
        "sin sitio, el título va arriba y los datos debajo"
    )


def test_en_el_carril_ancho_el_poema_ocupa_una_sola_linea():
    """Con el primer verso bajo el título cabían siete poemas por pantalla; en su propia
    columna caben diez. La última columna es fija: si dependiera del largo de cada firma,
    los versos empezarían en una vertical distinta en cada fila."""
    ancho = _bloque("@container filas (min-width:1000px)")
    assert ".fila--poema.fila-cuerpo{display:grid;" in ancho
    assert re.search(r"\.fila--poema\{grid-template-columns:[^;}]*15rem\}", ancho), (
        "la columna de la firma debe tener ancho fijo"
    )
    verso = re.search(r"\.fila--poema\.fila-verso\{([^}]*)\}", ancho).group(1)
    assert "white-space:nowrap" in verso and "text-overflow:ellipsis" in verso


def test_el_filete_y_la_hoja_clara_son_tokens():
    css = _css()
    assert re.search(r"--paper-2:\s*#[0-9a-f]{6}", css)
    assert re.search(r"--line:\s*#[0-9a-f]{6}", css), (
        "falta el valor para quien no conoce color-mix()"
    )
    mejora = _bloque("@supports (color:color-mix(")
    assert ":root{--line:color-mix(insrgb,var(--ink)22%,transparent)}" in mejora
    assert "border-top:1pxsolidvar(--line)" in _regla(".fila")


def test_la_cubierta_se_ensena_como_un_objeto():
    """Sin esquinas redondeadas y con sombra plana; al señalarla la sombra pasa al color
    de estado. Nada se mueve: el sitio solo anima color, fondo y borde."""
    cubierta = _regla(".pub-cardimg,.pub-cover-fallback")
    assert "box-shadow:8px8px0var(--line)" in cubierta
    assert "border-radius" not in cubierta
    assert "aspect-ratio:5/7" in cubierta
    senalada = [
        cuerpo
        for sel, cuerpo in _reglas()
        if ".pub-card a:hover img" in sel and ".pub-card a:focus-visible img" in sel
    ]
    assert senalada and "box-shadow:8px8px0var(--accent)" in senalada[0]
    assert "transform" not in senalada[0]


def test_un_catalogo_corto_no_se_arrincona():
    """Con tres títulos en una rejilla de cinco columnas, el 40 % de la pantalla quedaba
    vacío a la derecha. Es una mejora: sin :has() queda la rejilla general."""
    desde_900 = _bloque("@media (min-width:900px){\n  .pub-grid")
    assert (
        ".pub-grid:not(:has(>:nth-child(5))){grid-template-columns:repeat(4,minmax(0,1fr))}"
        in desde_900
    )
    assert (
        ".lienzo>.pub-grid:not(:has(>:nth-child(4))){grid-template-columns:repeat(3,minmax(0,1fr))}"
        in desde_900
    )
    assert "minmax(240px,1fr)" in _bloque("@media (min-width:720px){\n  .pub-grid")


def test_la_miniatura_de_registro_es_16_9_y_lleva_marca_de_reproduccion():
    miniatura = _regla(".rec-miniatura")
    assert "aspect-ratio:16/9" in miniatura and "background:var(--caratula)" in miniatura
    # El cartel va en posición absoluta: la marca necesita z-index o queda debajo.
    for capa in (".rec-miniatura::before", ".rec-miniatura::after"):
        assert "z-index:1" in _regla(capa), f"«{capa}» quedaría tapada por el cartel"
    assert "inset:0" in _regla(".recording-cardh2a::after"), "la tarjeta entera es el enlace"


def test_rejillas_que_reparten_el_ancho_entre_lo_que_haya():
    """`auto-fill` deja columnas vacías a la derecha cuando hay pocos elementos; con
    `auto-fit` los que hay se reparten la fila. El tope evita que uno solo se estire."""
    for lista, tarjeta in (
        (".recording-list", ".recording-card"),
        (".album-grid", ".album-card"),
    ):
        assert "repeat(auto-fit," in _regla(lista), f"«{lista}» vuelve a dejar columnas vacías"
        assert "max-width:" in _regla(tarjeta), f"«{tarjeta}» se estiraría de lado a lado"
    assert "repeat(auto-fit," in _regla(".event-list")


def test_la_hoja_de_contactos_fija_la_proporcion_en_la_hoja_no_en_cada_foto():
    hoja = _regla(".hoja")
    assert "grid-template-columns:2fr1fr" in hoja and "aspect-ratio:9/4" in hoja
    fotos = _regla(".hojaimg")
    assert "height:100%" in fotos and "object-fit:cover" in fotos
    assert "aspect-ratio" not in fotos


# ── Serif de lectura y monoespaciada (ticket 2.3) ─────────────────────────


def test_la_serif_de_lectura_es_propia_y_tiene_reserva_metrica():
    """La pila de sistema daba Palatino en un Mac, Times en Linux y Georgia en Windows: el
    sitio tenía tres voces. Ahora la serif viaja con el sitio, y mientras llega la ocupa una
    reserva escalada para que el texto no salte al cambiar."""
    css = _css()
    pila = re.search(r"--serif:([^;]+);", css).group(1)
    assert pila.startswith('"RdV Serif","RdV Serif Fallback"'), pila
    propias = re.findall(r'@font-face\{[^}]*font-family:"RdV Serif";[^}]*\}', css)
    estilos = sorted(re.search(r"font-style:(\w+)", cara).group(1) for cara in propias)
    assert estilos == ["italic", "normal"], f"faltan la redonda o la cursiva: {estilos}"
    for cara in propias:
        assert "font-display:swap" in cara and re.search(
            r'url\("\.\./fonts/rdv-serif[\w-]*\.woff2"\)', cara
        )
    reservas = re.findall(r'@font-face\{[^}]*"RdV Serif Fallback"[^}]*\}', css)
    assert len(reservas) >= 3, "la reserva necesita redonda, negrita y cursiva"
    for cara in reservas:
        assert (
            "size-adjust:" in cara
            and 'local("Liberation Serif' in cara
            and "ascent-override:" in cara
        )


def test_ninguna_familia_lleva_el_nombre_reservado_de_la_fuente():
    """Source Serif 4 tiene «Source» como nombre reservado (OFL, cláusula 3): una versión
    modificada —y el subconjunto lo es— no puede llamarse así."""
    familias = re.findall(r'font-family:\s*"([^"]+)"', _css())
    assert familias, "no se encontró ninguna familia declarada"
    assert not [f for f in familias if "source" in f.lower()], familias


# Reglas que pueden pintar en monoespaciada, cada una por su papel. Decisión D3: la mono
# queda para rótulos y datos; lo demás se lee en la serif o en la de titulares.
MONO_PERMITIDA = {
    ".rotulo,.kicker,.dossier-doc.subhead,.foot-grouph2,.reviewedh2,.event-month,.tag,"
    ".cinta-piea,.nav-disclosuresummary,.member-role": "rótulo, también el cargo de cada integrante",
    ".meta,.muted": "dato: firma, fecha, lugar",
    ".stats-strip": "etiquetas de las cifras",
    ".pagination-pagesa,.pagination-pagesspan": "números de página",
    ".lightboxfigcaption": "pie de foto",
    ".htmx-indicator": "indicador de carga",
}


def test_la_monoespaciada_queda_en_rotulos_y_datos():
    """La navegación, el pie, los botones y las cifras iban en monoespaciada: la voz del
    sitio era la de un panel de control. Una regla nueva que la use tiene que justificarse
    aquí."""
    con_mono = {
        re.sub(r"\s+", "", sel) for sel, cuerpo in _reglas() if "font-family:var(--mono)" in cuerpo
    }
    sobrantes = con_mono - set(MONO_PERMITIDA)
    assert not sobrantes, f"monoespaciada fuera de rótulos y datos: {sorted(sobrantes)}"
    assert "font-family" not in _regla(".nava"), "la navegación toma la familia de los titulares"
    titulares = next(sel for sel, cuerpo in _reglas() if "font-family:var(--display)" in cuerpo)
    assert ".nav a" in titulares
    assert "font-family" not in _regla(".site-foot"), "el pie hereda la serif del cuerpo"


# ── Sala de lectura, fichas y pie (ticket 2.4) ────────────────────────────


def test_la_sala_de_lectura_pone_la_ancla_al_lado_solo_si_cabe():
    """Ancla y texto lado a lado desde 840 px de ventana: por debajo no caben y la ancla
    va encima. El reparto es 4:7; la línea sigue limitada por --medida."""
    assert "grid-template-columns:minmax(0,1fr)" in _regla(".lectura-sala")
    dos = _bloque("@media (min-width:840px){\n  .lectura-sala")
    assert ".lectura-sala{grid-template-columns:minmax(220px,4fr)minmax(0,7fr)" in dos
    fija = _bloque("@media (min-width:840px) and (min-height:700px)")
    assert ".lectura-ancla{position:sticky;" in fija, "la ancla solo acompaña si hay alto para ella"
    assert "position:sticky" not in _regla(".lectura-ancla>:first-child")


def test_un_verso_largo_continua_con_sangria_francesa():
    """Sin sangría francesa, la continuación de un verso que no cabe se lee como un verso
    nuevo. El salto de estrofa mide una línea: el que dejó el autor."""
    verso = _regla(".verso")
    for declaracion in (
        "display:block",
        "white-space:pre-wrap",
        "padding-left:1.5em",
        "text-indent:-1.5em",
    ):
        assert declaracion in verso, f"al verso le falta «{declaracion}»"
    assert "margin-top:calc(var(--lh-verso)*1em)" in _regla(".estrofa+.estrofa")


def test_cada_salida_del_pie_se_pulsa_entera():
    assert "position:relative" in _regla(".pie-entidadli")
    assert 'content:""' in _regla(".pie-entidada::after") and "inset:0" in _regla(
        ".pie-entidada::after"
    )


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
        assert "border-radius" not in _regla(selector), f"«{selector}» redondea el retrato"
    for selector in (".ficha-retrato", ".retrato"):
        assert "aspect-ratio:4/5" in _regla(selector), f"«{selector}» no es 4:5"
    assert "border-radius:50%" not in _css(), "queda un círculo en la hoja"


# ── Superficies, tinta y amarillo (tickets 3.1 y 3.2) ─────────────────────


def _pantalla():
    """Las reglas de pantalla: sin la hoja de impresión, que pinta todo en blanco a propósito."""
    css = _css()
    inicio = css.index("@media print")
    abre = css.index("{", inicio)
    nivel, i = 1, abre + 1
    while nivel:
        nivel += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return [
        (re.sub(r"\s+", " ", selector.strip()), re.sub(r"\s+", "", cuerpo))
        for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css[:inicio] + css[i:])
    ]


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
    ".partner-logo",
    ".embed-play",
    ".rec-miniatura::before",
    ".recording-card:hover .rec-miniatura::after, .recording-card:focus-within .rec-miniatura::after",
}


def test_el_blanco_es_para_campos_y_objetos():
    """Las bandas y cinco avisos eran cajas blancas: el mismo blanco que los campos y las
    cubiertas, así que la página no se distinguía de las cosas que lleva encima (D6)."""
    blancas = {
        selector
        for selector, cuerpo in _pantalla()
        if re.search(r"background(-color)?:(var\(--surface\)|#fff\b|#ffffff\b|white\b)", cuerpo)
    }
    assert not blancas - BLANCO_PERMITIDO, f"superficies blancas: {blancas - BLANCO_PERMITIDO}"


def test_los_avisos_son_hoja_clara_sin_borde():
    """La fecha de la agenda, la próxima actividad, el contacto del dossier, la obra reseñada
    y los mensajes eran cajas blancas con borde de 1 px. Pasan a la hoja clara; los que
    llevan filete a la izquierda lo conservan, porque marca, no encierra."""
    for selector in (".event-date", ".next-event", ".dossier-contact", ".reviewed", ".flash"):
        cuerpo = _regla(selector)
        assert "background:var(--paper-2)" in cuerpo, f"«{selector}» no está en la hoja clara"
        assert not re.search(r"(?<![-\w])border:", cuerpo), f"«{selector}» sigue encerrado"
        assert "border-radius" not in cuerpo, f"«{selector}» sigue siendo una caja redondeada"


def test_la_banda_es_la_hoja_clara_y_la_fila_senalada_sobre_ella_pasa_al_papel():
    assert "background:var(--paper-2)" in _regla(".band")
    # La hoja clara es también la fila señalada: sobre una banda, el estado sería invisible.
    estado = _regla(".band.fila:has(.fila-tituloa):hover::before,.band.fila:focus-within::before")
    assert "background-color:var(--paper)" in estado


# Lo único que puede pintar un fondo de tinta: los botones y sus estados, el filete de
# 3 px que firma el territorio de prensa (una línea, no una superficie) y el pie.
TINTA_PERMITIDA = {
    ".btn:hover",
    ".index-head[data-territorio] h1::after",
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
        for selector, cuerpo in _pantalla()
        if re.search(r"background(-color)?:var\(--ink\)", cuerpo)
    }
    assert not con_tinta - TINTA_PERMITIDA, f"fondos de tinta: {con_tinta - TINTA_PERMITIDA}"
    plantillas = Path(__file__).resolve().parent.parent / "templates"
    con_banda = [
        p.name for p in plantillas.rglob("*.html") if "band--tinta" in p.read_text("utf-8")
    ]
    assert not con_banda, f"plantillas con banda de tinta: {con_banda}"


def test_la_placa_del_reproductor_fija_el_blanco_de_sus_datos():
    """El gris de `.meta` no se lee sobre el azul de la placa (2,12:1 con el de la tinta).
    Sin JavaScript la placa enseña un enlace al proveedor, que también es un dato."""
    assert "color:#fff" in _regla(".player-consent.meta,.player-consent.metaa")


def test_el_pie_es_de_tinta():
    pie = _regla(".site-foot")
    assert "background:var(--ink)" in pie and "color:var(--muted-on-ink)" in pie
    assert "color:var(--paper)" in _regla(".site-foota")
    assert "outline-color:var(--paper)" in _regla(".site-foot:focus-visible")
    boton = _regla(".site-foot.btn")
    assert "border-color:var(--paper)" in boton and "color:var(--paper)" in boton
    # Sin filete: la tinta ya separa el pie de la página.
    assert "border-top" not in pie


def test_el_amarillo_es_un_trazo_bajo_las_cifras_y_nunca_texto():
    """El amarillo del cartel da 1,03:1 sobre el papel: solo entra como fondo. Fue un plano
    de lado a lado del carril y el dueño del sitio lo encontró invasivo; ahora es un trazo
    de marcador detrás de la mitad baja de cada cifra de la portada (D5)."""
    con_amarillo = [
        (selector, cuerpo)
        for selector, cuerpo in _pantalla()
        if "riso-amarillo" in cuerpo and selector != ":root"
    ]
    assert [s for s, _ in con_amarillo] == [".hero-stats strong"], (
        f"el amarillo está fuera de las cifras: {[s for s, _ in con_amarillo]}"
    )
    trazo = con_amarillo[0][1]
    assert "background:linear-gradient(" in trazo and "width:fit-content" in trazo
    assert "background" not in _regla(".hero-stats"), "las cifras volvieron a un plano"
    assert not re.search(r"(?<![-\w])color:var\(--riso-amarillo\)", _css())


def test_la_firma_de_territorio_es_un_filete_de_tres_pixeles():
    firma = _regla(".index-head[data-territorio]h1::after")
    assert "height:3px" in firma and "background-color:var(--ink)" in firma
    assert "background-color:var(--accent)" in _regla(
        '.index-head[data-territorio="obra"]h1::after'
    )
    assert "background-color:var(--caratula)" in _regla(
        '.index-head[data-territorio="colectivo"]h1::after'
    )


def test_el_sello_de_convocatoria_esta_quieto():
    """Un timbre girado, no un aviso que se mueve: nada que distraiga de leer."""
    sello = _regla(".sello-convocatoria")
    assert "transform:rotate(-3deg)" in sello
    assert "animation" not in sello and "riso-amarillo" not in sello


# ── Ajustes tras la revisión del paso 13 ──────────────────────────────────


def _todas(selector):
    """Todas las reglas con ese selector, también las de dentro de un @media, en orden."""
    return [cuerpo for sel, cuerpo in _reglas() if re.sub(r"\s+", "", sel) == selector]


def test_el_pie_queda_abajo_en_una_pagina_corta():
    """En una página corta el pie terminaba a media altura y dejaba papel debajo: con el
    pie en tinta, un hueco. La página mide al menos la ventana y el lienzo crece."""
    cuerpo = _regla("body")
    for declaracion in ("display:flex", "flex-direction:column", "min-height:100dvh"):
        assert declaracion in cuerpo, f"a `body` le falta «{declaracion}»"
    lienzo = _regla(".lienzo")
    assert "flex:10auto" in lienzo, "el lienzo no crece hasta el pie"
    assert "align-content:start" in lienzo, "el alto sobrante separaría las filas del lienzo"
    assert "width:100%" in _regla(".wrap-wide"), (
        "en una columna flexible, un hijo con margen automático se encoge a su contenido"
    )


def test_el_pie_usa_el_ancho_para_medir_menos_de_alto():
    """Medía 435 px a 951 de ancho. Desde 720 px, formulario y línea legal comparten la
    primera línea; desde 1100, todo va en una fila."""
    rejillas = " ".join(_todas(".site-foot>.wrap-wide"))
    assert 'grid-template-areas:"newslegal""mapamapa"' in rejillas
    assert 'grid-template-areas:"newsmapa""legalmapa"' in rejillas
    grupos = " ".join(_todas(".foot-groups"))
    assert "grid-template-columns:repeat(4,max-content)" in grupos, (
        "el correo de gestión no cabe en una columna de un cuarto"
    )


def test_el_destacado_va_a_dos_columnas_sobre_el_papel():
    """Con reproductor, la placa a la izquierda y la ficha a la derecha. La regla va después
    del tope de ancho de la placa, o el tope le gana."""
    reglas = [re.sub(r"\s+", "", sel) for sel, _ in _reglas()]
    dos_columnas = ".featured:has(>.player-frame,>video)"
    cuerpo = _todas(dos_columnas)
    assert cuerpo and 'grid-template-areas:"placaficha""placaenlace"' in cuerpo[0]
    assert reglas.index(".featured>.player-frame,.featured>video") > reglas.index(
        ".featured.player-frame"
    )
    assert "max-width:none" in _regla(".featured>.player-frame,.featured>video")


# ── Duotono y retratos (tickets 3.3 y 3.6) ────────────────────────────────


def test_el_duotono_es_una_tinta_sobre_el_papel():
    """La tinta va de fondo, la foto en gris se aclara encima y el papel se multiplica por
    arriba: cada gris cae entre la tinta y el papel. Una sola tinta en todo el sitio, el
    azul del cartel; sin `isolation` la mezcla alcanzaría lo que hay detrás de la foto."""
    duo = _regla(".riso-duo")
    assert "isolation:isolate" in duo and "background-color:var(--caratula)" in duo
    foto = _regla(".riso-duoimg")
    assert "filter:grayscale(1)" in foto and "mix-blend-mode:screen" in foto
    papel = _regla(".riso-duo::after")
    assert "mix-blend-mode:multiply" in papel and "background-color:var(--paper)" in papel
    assert "pointer-events:none" in papel, "la capa del papel no puede tapar el enlace"
    # La tinta es el fondo de las reglas del duotono que no son la capa del papel.
    tintas = {
        tinta
        for selector, cuerpo in _reglas()
        if "riso-duo" in selector and "::after" not in selector
        for tinta in re.findall(r"background-color:var\((--[\w-]+)\)", cuerpo)
    }
    assert tintas == {"--caratula"}, f"más de una tinta de duotono: {tintas}"


def test_al_senalar_o_enfocar_se_ve_el_original():
    """Hay que quitar a la vez el filtro y la mezcla: si solo se quita uno, el original sale
    teñido. Y la capa del papel se vuelve transparente."""
    original = _regla(
        "a:hover.riso-duoimg,a:focus-visible.riso-duoimg,"
        ".cinta-caja:hover.riso-duoimg,.cinta-caja:focus-within.riso-duoimg"
    )
    assert "filter:none" in original and "mix-blend-mode:normal" in original
    papel = _regla(
        "a:hover.riso-duo::after,a:focus-visible.riso-duo::after,"
        ".cinta-caja:hover.riso-duo::after,.cinta-caja:focus-within.riso-duo::after"
    )
    assert "background-color:transparent" in papel


# El duotono, solo en los listados: tarjetas de integrante, cinta y hoja de contactos. Las
# cubiertas, los afiches, los logos y las fichas se ven tal cual.
CON_DUOTONO = {"_member_card.html", "_member_card_cinta.html", "gallery.html"}


def test_el_duotono_solo_va_en_los_listados():
    plantillas = Path(__file__).resolve().parent.parent / "templates"
    con_duo = {p.name for p in plantillas.rglob("*.html") if "riso-duo" in p.read_text("utf-8")}
    assert con_duo == CON_DUOTONO, f"duotono en: {sorted(con_duo)}"


def test_toda_la_tarjeta_de_integrante_es_el_enlace():
    """El rol y la reseña quedaban fuera del enlace: la capa del enlace cubre la tarjeta."""
    assert "position:relative" in _regla(".member-card")
    capa = _regla(".member-card>a::after")
    assert 'content:""' in capa and "inset:0" in capa
